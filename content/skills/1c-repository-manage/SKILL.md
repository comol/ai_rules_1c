---
name: 1c-repository-manage
description: "1C configuration repository (хранилище) — status, history, diff, lock, update, commit, unlock, dump; lock before edit, commit after verify. Use when .dev.env REPOSITORY_PATH is set or the task mentions the configuration repository / хранилище."
---

# 1C Repository Manage — Configuration Repository Skill

Use this skill when the project's configuration is **bound to a 1C configuration repository (хранилище конфигурации)** or the task explicitly concerns one.

## Activation — the master switch

`.dev.env` `REPOSITORY_PATH` is the explicit project statement "we work with a configuration repository":

- **`REPOSITORY_PATH` is set** → repository mode is ON for the whole SDLC. Load [docs/repo-sdlc.md](docs/repo-sdlc.md) before the first mutation of configuration objects in the session: metadata edits, config loads and DB updates are constrained by repository locks, and finished work must be committed. Ignoring the binding is a defect — the local edit will either fail to save or diverge from the team's repository. Disconnecting the configuration from the repository is **forbidden** for as long as this mode is on (Safety invariant 5).
- **`REPOSITORY_PATH` is empty** and the user asks for a repository operation → ask once for the repository address, write it to `REPOSITORY_PATH`, proceed.
- **`REPOSITORY_PATH` is empty** and nothing in the task mentions a repository → this skill does not apply; never ask about it up front.

Parameter canon (classes, empty-value behavior): `content/rules/dev-standards-env.md → Infobase / deployment parameters`.

## Hard rule

Every repository operation — report, history, compare, lock, update, commit, unlock, dump — is executed **through this skill's script** (`skills/1c-repository-manage/tools/1c-repo-ops/scripts/repo-ops.ps1`). Composing an ad-hoc `1cv8.exe /ConfigurationRepository*` command line from memory while the skill is available is a **defect**, same standing as ad-hoc infobase command lines (`AGENTS.md → Skills and Subagents`). The script encodes what an ad-hoc line loses: the exact object-list XML (`http://v8.1c.ru/8.3/config/objects`), `/Out` encoding detection, failures hidden behind exit code 0, secret masking, and the safety gates below.

The only exceptions mirror the metadata skill: the skill is not exposed in the session (state it once, then follow [docs/repo-ops.md](docs/repo-ops.md) manually with every safety rule intact), or a read-only question answerable without running the platform.

## Safety invariants (do not route around)

Invariants 1–4 are enforced by the script. Invariants 5–6 are agent refusals: the script has no bind/unbind operations, and composing them ad-hoc is the defect.

1. **Explicit object lists only.** `lock` / `update` / `commit` / `unlock` require `-Objects` with exact metadata full names. An empty list, `*`, or the configuration root is refused: the official CLI without `-Objects` applies the operation to the **whole configuration**.
2. **Force is double-gated.** `-Force` needs `REPOSITORY_ALLOW_FORCE=true` in `.dev.env` **and** a per-call confirmation switch (`-ConfirmForce`; for `unlock` — `-ConfirmDiscardChanges`, because a forced unlock discards uncommitted changes). Never set `REPOSITORY_ALLOW_FORCE` yourself — that value is the user's decision.
3. **A lock conflict is a report, not an obstacle.** "Объект уже захвачен пользователем …" means another developer holds the object: report to the user and stop. Never resolve it with a forced unlock on your own initiative.
4. **Commit comments are mandatory** — task reference plus what changed; the script refuses an empty comment.
5. **Never unbind while repository mode is on.** With `REPOSITORY_PATH` set, disconnecting the configuration from the repository is **forbidden**: `/ConfigurationRepositoryUnbindCfg`, the Designer action «Отключиться от хранилища», and any equivalent. A lock conflict, a read-only object, a failed `/update1cbase` load, or a user request to "just unbind so we can edit" is not a reason — a refusal is the correct outcome (same standing as routing around vendor support). Never empty `REPOSITORY_PATH` to drop this prohibition as a step of the current task.
6. **Never bind** an unbound infobase to a repository (`/ConfigurationRepositoryBindCfg`), create repositories, or manage repository users — these are one-shot administrative acts outside this skill's scope; report the need to the user.

## Dispatch

| Task | Operation | Doc |
|---|---|---|
| Check binding / latest version / connectivity | `-Operation status` | [repo-ops.md](docs/repo-ops.md) |
| Version history, who committed what | `-Operation history` | [repo-ops.md](docs/repo-ops.md) |
| What differs between local config and repository | `-Operation diff` | [repo-ops.md](docs/repo-ops.md) |
| Take objects for editing | `-Operation lock` | [repo-ops.md](docs/repo-ops.md) |
| Refresh local copies of objects from the repository | `-Operation update` | [repo-ops.md](docs/repo-ops.md) |
| Put finished changes into the repository | `-Operation commit` | [repo-ops.md](docs/repo-ops.md) |
| Release locks (no changes / after commit with `-KeepLocked`) | `-Operation unlock` | [repo-ops.md](docs/repo-ops.md) |
| Export a repository version to CF/CFE | `-Operation dump` | [repo-ops.md](docs/repo-ops.md) |
| How repository binding changes the dev cycle, `/update1cbase`, metadata mutations, conflict handling | — | [repo-sdlc.md](docs/repo-sdlc.md) |
| Refresh source files after `lock -Revised` / `update`; freshness check before loading them into the IB | — | [repo-sdlc.md → Source files follow the infobase](docs/repo-sdlc.md#source-files-follow-the-infobase) |

Reports (`status` / `history` / `diff`) are written to a file and only an excerpt is printed — read the report file for targeted analysis instead of pulling megabytes into context.

## Path conventions

The prefix `skills/1c-repository-manage/...` is relative to the active tool's skills directory (`.claude/skills/...`, `.cursor/skills/...`, etc.), exactly as described in `content/skills/1c-metadata-manage/SKILL.md → Path conventions`. In the `1c-rules` source repository prepend `content/`.

Run the script per the `powershell-windows` skill conventions:

```powershell
powershell -NoProfile -File "skills/1c-repository-manage/tools/1c-repo-ops/scripts/repo-ops.ps1" -Operation status
```

## Reporting

Any task that ran repository operations names them in the final answer in one line: `Repository tooling: repo-ops <operations>` (e.g. `Repository tooling: repo-ops lock, commit`). A task that mutated repository-bound objects without a matching `lock` → `commit` trail must explain why (e.g. commit deferred at the user's request — with the lock still held and reported).
