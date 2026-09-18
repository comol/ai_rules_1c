# Repository-Bound SDLC — Process Integration

Loaded when `.dev.env` `REPOSITORY_PATH` is set and the task mutates configuration objects or runs infobase config operations. This file changes **when** things happen in the standard 1c-rules cycle; the operations themselves stay in [repo-ops.md](repo-ops.md).

## What repository binding changes

In a repository-bound infobase an object is **read-only until locked** in the repository, and a change is **invisible to the team until committed**. Therefore the standard cycle (triage → plan → mutate → verify → deploy → report) gains three fixed points:

```
status ─→ lock(-Revised) ─→ [standard cycle: mutate → verify → update DB → test] ─→ commit ─→ report
```

1. **Before the first mutation** — `status` (connectivity + latest version), then `lock` the exact objects from the plan with `-Revised` (locking a stale copy invites a merge at commit). The plan's object list **is** the lock list: locking more than the plan needs blocks teammates; locking less fails at save time.
2. **During the work** — nothing changes: metadata mutations still go through the `1c-metadata-manage` skill, BSL edits and verification gates run as usual. If the work grows to an object that is not locked, lock it before mutating it, not after the save fails.
3. **After verification passes** — `commit` the same object list with a task-referenced comment. Uncommitted verified work at the end of a task is a decision, not a default: either commit, or report explicitly that changes are left locked-and-uncommitted and why.

## Interplay with slash commands and tools

| Command / tool | In repository mode |
|---|---|
| `/update1cbase` (sources → IB, `/UpdateDBCfg`) | Loading changed objects into a repository-bound IB requires those objects **locked first**; otherwise the load fails or silently skips read-only objects. Lock before running; a "configuration is read-only / object locked" error in its log routes here, not to a retry loop. |
| `/loadfrom1cbase`, `/getconfigfiles` (IB → sources) | Read-only with respect to the repository — no locks needed. |
| `1c-metadata-manage` mutating tools | Same gate: the XML they edit corresponds to configuration objects that must be locked before the change lands in the IB. The mutation itself stays in that skill; this skill owns only the lock/commit envelope. Wrapper `-Preview` is not a repository step (`METADATA_PREVIEW`, default `auto`). |
| `/build-release` | Prefer `dump -Version <N>` from the repository (fixed, team-visible version) over the local working copy when the release must match what the team committed. |
| `/deploy-and-test` | Deploy steps inherit the `/update1cbase` rule above; test steps are unaffected. |

**The lock list comes from the plan, not from a preview.** Lock every object the plan names, including the owner object of a form, layout, rights or module being changed. A wrapper `-Preview` is not a repository step; never hold locks across a write-then-rollback pause (`content/skills/1c-metadata-manage/docs/edit-preview.md → When preview runs`).

## Conflict and divergence handling

- **Lock held by another developer** → report who holds it (the platform names the user) and stop that branch of work. Options belong to the user: wait, ask the colleague to release, or re-scope. Never `-Force`.
- **Local copy differs from repository head before lock** (seen via `diff`) → `update` the objects first (or lock with `-Revised`), then mutate. Mutating a stale copy produces a merge at commit — the Designer's interactive merge is not available in batch mode, so prevention is the only strategy.
- **Commit rejected because the repository moved** → `update -Revised` the objects, re-verify, re-commit. Two rejections in a row = stop and report.

## Boundaries

- **Unbind is forbidden** while `REPOSITORY_PATH` is set (`/ConfigurationRepositoryUnbindCfg` and any equivalent, including the Designer action «Отключиться от хранилища»). A lock conflict, a read-only object, or a failed load is not a reason to disconnect — follow the conflict handling above. Canon: `SKILL.md → Safety invariants`.
- Binding an unbound IB to a repository, creating repositories, and repository user administration are user-run one-shot acts — out of scope (see `SKILL.md → Safety invariants`).
- The git source dump (`EXPORT_PATH`) and the configuration repository are **two independent version stores**. Committing to the repository does not update the git dump and vice versa; when a task must keep both current, run `/loadfrom1cbase` after the repository commit and say so in the report.

## End-of-task checklist

Before the final report of any task that touched repository-bound objects:

1. Every mutated object was locked before mutation and is now committed (or its uncommitted state is explicitly reported with a reason).
2. No locks are left that the task no longer needs (`-KeepLocked` continuation is fine — name it).
3. The report contains the one-line trail: `Repository tooling: repo-ops <operations>`.
