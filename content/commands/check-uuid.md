---
description: Check a 1C XML configuration dump for duplicate UUIDs, and optionally regenerate them
argumentHint: "[path] [--fix] [--include-intra]"
---

# /check-uuid — duplicate UUID check in a configuration dump

Detects objects that claim the same identity. The full description of the tool — carriers, cross-file vs intra-file duplicates, and the `-Fix` safety rules — is owned by **`content/skills/1c-metadata-manage/docs/uuid-check.md`**. Read it before running a repair.

## Arguments

`$ARGUMENTS` may contain, in any order:

- a **path** — folder or single XML file to scan;
- `--fix` — repair duplicates;
- `--include-intra` — also report duplicates inside a single file.

## Steps

1. **Resolve the path.** Use the path from `$ARGUMENTS` when given. Otherwise locate the configuration sources in the current project (typically `src/`); if there is more than one candidate root, ask the user which one — scanning two copies of the same configuration reports every UUID as a duplicate.

2. **Run the check.**

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File skills/1c-metadata-manage/tools/1c-uuid-check/scripts/uuid-check.ps1 -ConfigPath "<path>" [-IncludeIntra]
   ```

   (In the `1c-rules` source repository, prefix the script path with `content/` — `SKILL.md → Path conventions`.)

3. **Report the result.**
   - Exit `0` — no duplicates; say so, and pass on the count of suppressed intra-file duplicates if the run reported any.
   - Exit `1` — show the duplicate groups with their files and line numbers.

4. **Repair only on request.** Do **not** pass `-Fix` unless the user asked for it in this task (`--fix` in `$ARGUMENTS`, or an explicit confirmation).

   Before repairing, state the risk in one line: `-Fix` keeps the *first* occurrence and regenerates the rest, which is positional rather than semantic. If the dump has already been loaded into an infobase, regenerating a `uuid` makes the platform treat the object as new on the next load and orphans its data — in that case have the user decide which occurrence keeps the identity.

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File skills/1c-metadata-manage/tools/1c-uuid-check/scripts/uuid-check.ps1 -ConfigPath "<path>" [-IncludeIntra] -Fix
   ```

5. **Confirm.** After a repair, re-run without `-Fix` and report the clean result. Then validate the affected objects (`meta-validate` / `cf-validate` — `content/skills/1c-metadata-manage/docs/meta-manage.md`, `content/skills/1c-metadata-manage/docs/cf-manage.md`) before the dump is loaded.

Do not hand-edit UUIDs in the XML to resolve duplicates — that is a metadata mutation and belongs to the `1c-metadata-manage` skill (`AGENTS.md → Skills and Subagents`).
