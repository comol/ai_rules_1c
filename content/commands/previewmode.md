---
description: Toggle the metadata preview mode — set METADATA_PREVIEW (on|auto|off) in .dev.env, or run a one-off preview for the current task
argumentHint: "[on|auto|off|once|status]"
---

# /previewmode — metadata preview before the write

Control when `Invoke-1CEdit.ps1 -Preview` (run the tool, show a unified diff, restore the tree) runs before a metadata write. Canonical behaviour and the case list — `content/skills/1c-metadata-manage/docs/edit-preview.md → When preview runs`; the `METADATA_PREVIEW` key, its values and default — `content/rules/dev-standards-env.md → "METADATA_PREVIEW"` (installed copies; match by file name per the path convention in `AGENTS.md`). Load `content/skills/1c-metadata-manage/docs/edit-preview.md` before acting.

Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for.

Two scopes, do not mix them:

- **Persistent (project-wide, edits `.dev.env`):** `on` / `auto` / `off` write the `METADATA_PREVIEW` key and take effect in every chat, including new ones.
- **Session-only (no file change):** `once` previews the next metadata write of the current task and then returns to the persisted value.

Parse the argument: `on` (or empty) → set `on`; `auto` → set `auto`; `off` → set `off`; `once` → session-only preview; `status` → report without editing. Matching is case-insensitive and tolerates trailing punctuation; an unrecognised argument is reported back, never guessed. The command edits **only** the `METADATA_PREVIEW` line in `.dev.env` — never other keys, never other files. Rewrite the `METADATA_PREVIEW=` line in place, or append `METADATA_PREVIEW=<value>` at the end; if `.dev.env` is missing, run the installer (`install.ps1 init`) instead of creating a partial file — until then apply the mode for the current session only.

## on / auto / off

1. Read `.dev.env`: the `METADATA_PREVIEW` key.
2. Set `METADATA_PREVIEW=<value>` (`on` | `auto` | `off`).
3. **No re-render needed.** The key is read directly from `.dev.env` at task time — editing the file is enough, no `install.ps1 update` and no client restart.
4. Apply the new mode immediately — from this message on, in this session.
5. Confirm to the user in 2–3 lines, in Russian:
   - что записано в `.dev.env` (`METADATA_PREVIEW=<value>`) и что действует для проекта, включая новые чаты;
   - что означает значение — для `auto` перечисли кейсы одной строкой по канону `content/skills/1c-metadata-manage/docs/edit-preview.md`;
   - как переключить обратно (`/previewmode on|auto|off`) и что разовый показ — `/previewmode once`.

## once

Session-only, no file write: preview the **next** metadata write of the current task, then apply it. Useful before an unfamiliar operation on a configuration you do not want to guess about. If the watched tree is already dirty, say so in one line and apply without preview — never stash or commit the user's work to force a preview.

## status

Read `.dev.env` and report, without editing anything:

- the `METADATA_PREVIEW` value (or the default when the file / key is absent or the value is invalid) and what it means;
- for `auto` — which cases trigger a preview (canon `content/skills/1c-metadata-manage/docs/edit-preview.md`);
- whether a `once` preview is pending in this session.

## Constraints (always)

The mode decides only whether the **wrapper** preview runs. It never disables the native `-DryRun` / `-Force` gate on deletions (`remove-form`, `meta-remove`, `remove-template`, `web-unpublish`), never replaces validation (`meta-validate`, `verify_xml`, `syntaxcheck`), and never turns preview into a verification gate. `off` still allows an explicit user request; `on` still previews only the wrapper's own script writes (a dirty tree applies with a note; host-made edits and BSL rewrite proposals never pass through it).
