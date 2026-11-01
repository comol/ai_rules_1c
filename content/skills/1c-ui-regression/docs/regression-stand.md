# Regression stand — roles, reference base, licences

Practices for a saved web-client suite that brings up its own test base. They follow the sample application suite `regress-example/` of upstream cc-1c-skills (MIT); only the practices are taken over, no code or reference base. Every stand step still runs under the gates of [SKILL.md](../SKILL.md): an authorized dev/test base, `UI_TESTING`, and the infobase tools of `content/skills/1c-metadata-manage/SKILL.md` for every load.

## 1. A suite context is a role

Each context of the suite (one browser session) is one infobase user, chosen for the role under test: `initiator`, `approver`, `auditor`. Name contexts and step helpers by role, not by person. A process across roles hands data from one context to the next inside the test (a document number), never through shared state.

Bind a context to its user one of two ways:

| Way | How | Fits when |
|---|---|---|
| Publication per user | One publication per role with its own `-AppName` and `-UserName` (`content/skills/1c-metadata-manage/docs/web-manage.md`, parallel publications); the URL itself says who logs in | Roles are stable; people also check by link. Changing a user means republishing — an Apache restart that drops open sessions |
| `user` per context | One publication without a user; the context logs in through `POST <pub>/e1cib/start` (`content/rules/web-client-driving.md → Login as another user, file choice`) with the password from an environment variable per user (`AUDITOR_PWD`) | Users change often. A context without a user on such a publication stops at the 1C login form |

Passwords never go into the suite, its committed config or the report. Every live context is a separate 1C session and holds a licence: cap concurrent contexts at the licences available, and close a context as soon as its role is no longer needed.

## 2. Reference base and its manifest

The stand is restored from a reference `.dt` that already holds the data the scenarios rely on; the current sources are layered on top. Next to the `.dt` keep `<name>.dt.manifest.json`:

```json
{ "cfHash": "<fingerprint of the configuration sources>",
  "ext": { "<ExtensionName>": "<fingerprint of its sources>" },
  "sourceCommit": "<commit the reference was built from>",
  "builtAt": "<ISO-8601 time>" }
```

- **Fingerprint** = the git tree id of the source directory plus the content of its uncommitted changes, so editing an already-modified file changes it too. One definition per project, used both when the manifest is written and when it is read.
- **Sources match the manifest** → skip the configuration and extension loads.
- **Configuration differs, the source directory has no uncommitted changes and `sourceCommit` is an ancestor of `HEAD`** (`git merge-base --is-ancestor <sourceCommit> HEAD`) → load only the delta: `db-load-git -Source Commit -CommitRange <sourceCommit>..HEAD` (`content/skills/1c-metadata-manage/docs/db-manage.md`, `-DryRun` plan first), then `db-update`. Any other case — uncommitted changes, history rewritten by rebase or squash — loads the whole configuration.
- **After any configuration load, reload every extension**: the load can reset their binding. An extension loaded from sources comes up in safe mode, which silently disables interception of object modules — set its properties after each load (`content/rules/qa-testclient.md → Extensions under test: safe mode`).
- **Build the manifest from committed sources only**: it names a commit, and changes outside it would not be in the reference.
- Keep the `.dt` and its manifest **out of git** (size, real data): `DT_SNAPSHOT_PATH` points at the file, the manifest sits beside it. Rebuild the reference when the scenario data or the base platform changes; source changes are layered automatically.

## 3. `down` releases the licences

Give the stand an explicit `down` step and run it after the suite, and whenever a run fails with «Не обнаружено свободной лицензии». `down` stops the stand's own web server (`web-stop`, `content/skills/1c-metadata-manage/docs/web-manage.md`): the sessions its publications hold end and their licences are freed. The base and the publications stay, so the next `up` takes seconds. Sessions a crashed or aborted run left open hold their licences until they time out or the server stops.

Never free licences by killing client or browser processes: under the developer licence a killed client keeps its place (`content/rules/qa-testclient.md → Starting and connecting`).

Report stand failures (licence, login, client start) as infrastructure, not as test failures, and do not edit a test to get past them.
