# repo-ops — Operation Reference

One script drives every repository operation:

```powershell
powershell -NoProfile -File "skills/1c-repository-manage/tools/1c-repo-ops/scripts/repo-ops.ps1" -Operation <op> [parameters]
```

Connection defaults come from `.dev.env` (`PLATFORM_PATH`, `INFOBASE_KIND`, `INFOBASE_PATH`, `IB_USER`, `IB_PASSWORD`, `REPOSITORY_PATH`, `REPOSITORY_USER`, `REPOSITORY_PASSWORD`); explicit script parameters override them. A relative infobase path is anchored at the `.dev.env` directory. Repository operations always run through the Designer (`1cv8.exe`) — `ibcmd` has no repository mode, and the script refuses it.

`-Objects` accepts a comma-separated string of exact metadata full names (Russian or English type names both work; the platform always answers in Russian): `"Справочник.Номенклатура,Документ.ЗаказКлиента"`. The script builds the temporary `-Objects` XML itself and deletes it afterwards. What to name:

| You change | Name in `-Objects` |
|---|---|
| An attribute, tabular section, dimension, resource or module of an object | the object itself: `Справочник.Контрагенты` — a part is substituted with its owner automatically (with a `[note]`) |
| An existing form, template or command | that object: `Справочник.Контрагенты.Форма.ФормаЭлемента` |
| A new form, template or command | its owner; at commit name the new object too |
| A new top-level object | the root alone: `Конфигурация` (the object does not exist yet, so it cannot be locked); at commit name the root and the new object |

`-IncludeChildObjects` extends an entry to its forms, templates and commands; with the root it would be the whole configuration and is refused.

`.dev.env` `INFOBASE_ROLE=prod` — `lock` / `update` / `commit` / `unlock` through the project infobase are refused before the platform starts ([repo-sdlc.md → Boundaries](repo-sdlc.md#boundaries)); `status` / `history` / `diff` / `dump` run.

For an **extension repository** add `-Extension "<Name>"` (its own `REPOSITORY_PATH` — pass `-RepositoryPath` if it differs from the main one). Not applicable to `diff`.

## Operations

### status — connectivity check and latest version

```powershell
... -Operation status
```

Latest-version report (`/ConfigurationRepositoryReport -NBegin -1`). The cheapest full check of the chain platform → infobase → repository → credentials. Run it first in a session before planning repository work, and after any failure before retrying.

### history — version report

```powershell
... -Operation history -BeginVersion 120 -EndVersion 140 -GroupBy object
```

`-BeginVersion` / `-EndVersion` bound the range (omit for full history — on a long-lived repository prefer explicit bounds), `-GroupBy version|object|comment` selects the grouping (`/ConfigurationRepositoryReport [-NBegin] [-NEnd] [-GroupByObject|-GroupByComment]`).

### diff — local main configuration vs repository version

```powershell
... -Operation diff                       # against the latest version
... -Operation diff -Version 135          # against version 135
... -Operation diff -Objects "Справочник.Номенклатура"   # narrowed to objects
```

`/CompareCfg -FirstConfigurationType MainConfiguration -SecondConfigurationType ConfigurationRepository`, Brief report with changed/added/deleted objects. Use before `commit` to verify the change set matches the plan, and before `lock` to see whether local copies are stale.

The platform has no "latest" for the repository side: without `-SecondVersion` it answers «Не указана версия хранилища». Without `-Version` the script therefore reads the head number first (the same one-version report as `status`) and prints `Comparing with the repository head: version N`. The comparison needs an infobase bound to this repository — on an unbound one the platform answers «Конфигурация 'Конфигурация хранилища' недоступна»; `status`, `history` and `dump` work from any infobase.

### lock — take objects for editing

```powershell
... -Operation lock -Objects "Справочник.Номенклатура" [-IncludeChildObjects] [-Revised]
```

`/ConfigurationRepositoryLock`. `-Revised` pre-updates the objects to the repository head before locking (recommended: locking a stale copy invites a merge at commit). `-IncludeChildObjects` extends the lock to subordinate objects — use when the plan touches forms/templates/commands of the object.

The lock is **not atomic**, and the script reports per object:

- `Locked by you now` — taken by this call.
- `Locked by another user — NOT taken` with the holder — a conflict (Safety invariant 3): exit `1`. A `[partial]` line says the objects of the first list (and requested ones the platform did not mention) are held by you anyway.
- `Already locked by you` — the platform prints nothing for objects you hold; exit `0`, no change.
- `objects received from the repository` (with `-Revised`) — see [Received objects](#received-objects).

### update — refresh local copies from the repository

```powershell
... -Operation update -Objects "Справочник.Номенклатура" [-Version 135] [-Revised]
```

`/ConfigurationRepositoryUpdateCfg -Objects …`. Omitted `-Version` = repository head. After an update that changed objects, the DB structure may need `/update1cbase` (see [repo-sdlc.md](repo-sdlc.md)). `Nothing to receive` means the objects are current. A success without the repository operation block in the log is refused (exit `1`): it means the infobase is probably not bound, and on an unbound infobase this command replaces the whole configuration.

### commit — put changes into the repository

```powershell
... -Operation commit -Objects "Справочник.Номенклатура" -Comment "TASK-123: добавлен реквизит Артикул" [-KeepLocked] [-IncludeChildObjects]
```

`/ConfigurationRepositoryCommit`. `-Comment` is mandatory (task reference + what changed; multi-line comments allowed — each line is passed separately). `-KeepLocked` keeps the lock after commit for continued work. Commit only objects that are verified (`verification-gates.md`) — a commit is visible to the whole team immediately.

The output lists `Committed to the repository` and `Unchanged — not committed`; when nothing was committed it says that **no new version was created**. A failed commit gets a bare «Ошибка помещения изменений объектов в хранилище» from the platform, the same for every cause — the script prints the checklist (locked by you? held by someone else? commit right? repository moved?).

### unlock — release locks

```powershell
... -Operation unlock -Objects "Справочник.Номенклатура" [-IncludeChildObjects]
```

`/ConfigurationRepositoryUnLock` without force releases **own** locks on unchanged objects. «Объект не захвачен для редактирования» is reported as `Not locked by you — nothing to release (no-op)` with exit `0`. Objects with local changes refuse the whole call («Объект '…' был изменен», exit `1`, the objects are named): commit them, or discard them with `-Force -ConfirmDiscardChanges` — the forced unlock receives the repository version back and the local changes are gone.

An object locked by another user is named by the platform («Объект захвачен для редактирования другим пользователем: … (<holder>)»), the lock stays, and the platform still reports success. Without `-Force` the script lists it as `Locked by another user — not yours, nothing to release` with exit `0`. With `-Force` the lock is still not released — in batch mode, even for a repository administrator — so the script lists it as `NOT released` and exits `1`.

### dump — export a repository version to CF/CFE

```powershell
... -Operation dump -OutputFile "C:\Release\1.2.3.cf" [-Version 135]
```

`/ConfigurationRepositoryDumpCfg`. Extension `.cf` (main) / `.cfe` (extension repository with `-Extension`). Use for release builds from a fixed repository version instead of the local working copy.

Unbind (`/ConfigurationRepositoryUnbindCfg`) is **not** an operation of this script and must not be composed ad-hoc while `REPOSITORY_PATH` is set — canon [SKILL.md → Safety invariant 5](../SKILL.md).

### Received objects

`lock -Revised`, `update` and `unlock -Force` silently bring newer versions into the infobase. The script then prints `[warning] … objects received from the repository`, saves the owner objects one per line to `%TEMP%\1c-repo-reports\received-<stamp>.txt` and prints the ready export command:

```powershell
powershell -NoProfile -File "<skills>/1c-metadata-manage/tools/1c-db-ops/scripts/db-dump-xml.ps1" -InfoBasePath "<ib>" -ConfigDir "<EXPORT_PATH>" -Mode Partial -ObjectsFile "<list>"
```

Run it (or the `/getconfigfiles` selected-object export with that list) **before** editing those files, and stop first if a file to refresh carries local edits ([repo-sdlc.md → Source files follow the infobase](repo-sdlc.md#source-files-follow-the-infobase)). A received root is not exportable by name — use the incremental `/loadfrom1cbase changes`.

## Force variants — user-approved maintenance only

| Call | Effect | Gate |
|---|---|---|
| `update -Force -ConfirmForce` | Overwrites locally changed objects with the repository version | `REPOSITORY_ALLOW_FORCE=true` + switch |
| `commit -Force -ConfirmForce` | Commits despite warnings the platform would otherwise stop on | `REPOSITORY_ALLOW_FORCE=true` + switch |
| `unlock -Force -ConfirmDiscardChanges` | Releases **own** locks **discarding uncommitted changes**. Another user's lock is not released in batch mode, even with repository admin rights (exit `1`, see [unlock](#unlock--release-locks)) | `REPOSITORY_ALLOW_FORCE=true` + switch |

Both halves of each gate are the user's decision: never edit `REPOSITORY_ALLOW_FORCE` and never add the confirmation switch without the user's explicit approval of that specific operation in that specific call.

## Output contract

- Success = exit `0` **and** `/DumpResult` `0` (a missing result file fails the run) **and** no fatal line in the `/Out` log **and**, for `lock` / `update` / `commit` / `unlock`, the per-object verdict above. The log scan elevates hidden failures («Ошибка работы с хранилищем конфигурации», «Соединение с хранилищем конфигурации не установлено», «Загруженный список объектов пуст», auth errors, …) to exit `1` even when the platform exits `0`; the per-object lines are read line by line instead of by substring, so an unlock no-op is not a failure and a partial lock is visible.
- `Error: objects not found in the configuration` (the platform's «Объекты, отсутствующие в обеих конфигурациях») — a typo, an infobase behind the repository (`update` first), or a part of an object instead of its owner.
- Reports (`status`/`history`/`diff`) go to `%TEMP%\1c-repo-reports\<op>-<stamp>.txt` (override with `-ReportFile`); the console shows the first 16000 chars (`-MaxReportChars`) plus the file path — read the file for anything beyond the excerpt. Object lists longer than 20 names are cut in the console and saved beside the reports.
- Passwords never appear in the printed command line.
- `-TimeoutSeconds N` kills a hung Designer after N seconds (default: no timeout).

## Failure handling — retry discipline

Same iterative discipline as DB updates (`content/skills/1c-metadata-manage/docs/db-manage.md → Update retry discipline`): read the log lines the script surfaced → classify → fix the cause → re-run. Typical classes:

| Log evidence | Cause | Action |
|---|---|---|
| `Locked by another user — NOT taken … held by <X>` («Объект захвачен для редактирования другим пользователем») | Lock conflict | Report to the user; do **not** force-unlock. Objects listed as locked by you stay yours |
| `Not locked by you — lock them first` on commit, or the bare commit failure | Committing objects that were never locked | `lock` the missing objects, re-commit |
| `Locked by another user — NOT released` on `unlock -Force` | A batch forced unlock does not release another user's lock | Report the holder to the user; the holder releases it |
| `Конфигурация 'Конфигурация хранилища' недоступна` on `diff` | The infobase is not bound to this repository | Compare from a bound infobase, or `dump` the version and compare the files |
| `[connection] credentials rejected` (`Неправильное имя или пароль…`) | Wrong `REPOSITORY_USER`/`REPOSITORY_PASSWORD` or IB credentials | Re-ask the user once, per the `dev-standards-env.md` credential policy |
| `[connection] repository credentials missing` («Соединение с хранилищем конфигурации не установлено», `REPOSITORY_USER` empty) | The platform gives this message for missing credentials too | Ask the user for the repository user / password |
| `[connection] repository server unreachable at <host>:<port>` (same message, `tcp://` address, user set) | Repository server down, wrong port (default 1542), server version ≠ platform | Verify the server and address with the user |
| `Не удалось подключиться к хранилищу`, path not reachable | Wrong `REPOSITORY_PATH` / share unavailable | Verify the address with the user |
| `/DumpResult was not written` / `reports <N>` | The batch run failed without saying so in the exit code | Read the log; see `content/rules/designer-batch-checks.md` |
| Designer exits non-zero, empty log | Startup problem (license, another Configurator session holding the IB) | Close competing sessions; see `db-manage.md` session handling |
| Timeout kill | Hung dialog / dead network | `status` first, then retry once with a larger `-TimeoutSeconds` |

Two identical failures in a row = stop and report; never loop the same failing call.

## Changes

- **2026-11-12 — repo-ops v1.2.** Checked against a live file repository on 8.3.27.2342 (two repository users, three infobases). Fixed: a quote in a `commit` comment is doubled (`""`) — the former `\"` stored the comment cut at the quote and dropped the rest of the line; `diff` without `-Version` reads the head number first — it used to fail with «Не указана версия хранилища»; `unlock -Force` that leaves another user's lock in place exits `1` instead of `0` («Nothing was released»), and the plain unlock names the holder. Docs: unlock with local changes is refused, not "loses nothing"; a batch forced unlock does not release another user's lock even for an administrator; `diff` needs a bound infobase. Confirmed on the live repository as documented: `status` (`-NBegin -1` is exactly the head), `history` grouping, partial lock, "already yours", missing objects, empty list, `dump` / `update` with `-Version`, `status` / `history` / `dump` from an unbound infobase. Regression cases added for the three fixes.
- **2026-11-01 — repo-ops v1.1.** Ported from upstream `db-repo` (cc-1c-skills 478e7489, 33633aaf, 3e816d3e, 1eb565b1, 1c74843c, 4a49eea4; the skill itself is not vendored — it binds / unbinds infobases and administers repositories, which Safety invariants 5–6 forbid): line-by-line verdict per object for `lock` / `update` / `commit` / `unlock` (partial lock, silent "already yours", unlock no-op, "no new version", unbound-infobase check on `update`); root-only lock; owner substitution; received objects saved with a ready `db-dump-xml -ObjectsFile` command; connection hints that tell an unreachable `tcp://` server from missing or rejected credentials. Local additions: `/DumpResult` and `/DisableStartupMessages` on every launch, the `INFOBASE_ROLE=prod` refusal enforced by the script, a relative infobase path anchored at `.dev.env`, `PositionalBinding=$false`, a `trap` against a false exit `0`, a bounded output drain (no hang when a child keeps the pipes open). `-Objects` on `status` / `history` / `dump` is now refused instead of ignored. Kept as before: the double `-Force` gate, no whole-configuration operations, `diff`, `-TimeoutSeconds`, the freshness check of [repo-sdlc.md](repo-sdlc.md). Offline tests: `tools/tests/repo-ops-regression.ps1` (fake platform, sample logs from the platform's message texts); not yet verified against a live repository.
