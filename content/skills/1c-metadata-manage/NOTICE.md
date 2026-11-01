# Third-party notices — `1c-metadata-manage`

This skill vendors tool scripts from a third-party project. The notice below is
reproduced as the licence requires; it applies to the vendored files listed here
and travels with every copy of this skill, including installed ones
(`<tool>/skills/1c-metadata-manage/NOTICE.md`).

## Nikolay-Shirokov/cc-1c-skills

- Upstream: <https://github.com/Nikolay-Shirokov/cc-1c-skills>
- Pinned commit: `2e75b0f483eb020e9f09562d1a7be1982bc5ac6e`
- Licence: MIT

Vendored under `tools/`, with local modifications documented in each file's
header and in `docs/`:

**Five metadata Python entry points vendored from the pinned commit above.**
Each was taken from that immutable commit, not from a moving `HEAD`, and each
carries its downstream deltas in its own file header:

- `tools/1c-form-scaffold/scripts/remove-form.py` — Python runtime of
  `form-remove`. Downstream deltas: input validation (1C identifiers, no
  traversal / separators / UNC / symlinked targets), the `-DryRun` / `-Force`
  safety gate, path containment anchored at `-SrcDir` (a symlink or junction on
  any component of the chain is refused before the first mutation), a
  transactional mutation path whose quarantine is discarded only after every
  payload is verifiably back or the transaction has committed, and
  byte-preserving `ChildObjects` editing. From upstream (synced at `2e75b0f`,
  v1.11) only the reference check of 93d9511a is taken — full-reference matching
  (the old `Form.<Name>` tail match blanked other objects' and `CommonForm` slots)
  and a scan of the rest of the configuration — plus case-insensitive parameter
  names; cleaning foreign references is the separate `-CleanReferences` switch
  inside the same transaction, where upstream's `-Force` does it implicitly.
- `tools/1c-form-compile/scripts/form-compile.py` — Python runtime of
  `form-compile`, synced at `2e75b0f` (v1.224). Downstream deltas: one event
  normalizer for all three DSL spellings (`events`, `on` + `handlers`, standalone
  `handlers`), an explicit non-zero refusal when two spellings are given at once,
  when a `handlers` key is absent from `on`, or when the event name is in no
  element's event catalog (upstream only warns); `.dev.env` support guard, fail
  closed; from-object document choice forms get `ChoiceMode`, the document item
  preset writes `AutoTime` / `UsePostingMode` / `RepostOnWrite`, `Description` is
  bound only when `DescriptionLength > 0`, and a missing `Configuration.xml` is
  reported instead of assuming 2.17. The handler suffixes (`OnEditEnd` →
  `ПриОкончанииРедактирования`, `Selection` → `Выбор`, `DragEnd` →
  `ОкончаниеПеретаскивания`) and the closed form-property enum sets are upstream's
  since the event catalog (052ee035) and the XSD enum normalization (7c1a3318).
- `tools/1c-form-scaffold/scripts/form-add.py` — Python runtime of `form-add`,
  the managed-form scaffolder. Downstream deltas: `.dev.env` support guard via
  `tools/_common/dev_env.py`, and XML escaping of the user-supplied `-FormName` /
  `-Synonym` in the generated descriptor (upstream interpolates them verbatim, so
  an ordinary `A & B` produced a descriptor no parser accepts); `-FormName` must be
  a 1C identifier. Synced at `2e75b0f` (v1.34); the information register's record
  form with main attribute `Запись` is upstream's now (`-Purpose Record`, the
  register's primary form).
- `tools/1c-meta-edit/scripts/meta-edit.py` — Python runtime of `meta-edit`,
  upstream base v1.73 (`2e75b0f`). Downstream deltas: `add-form` and
  `add-template` are refused before any mutation (exit 2) and redirected to
  `form-add` / `add-template`, in every key spelling the dispatcher itself
  accepts and across the whole definition; the auto-validator is resolved under
  the downstream directory names (`1c-meta-validate`, and for an external data
  processor or report the PowerShell `1c-epf-validate` script run through
  `pwsh` / Windows PowerShell), a missing validator or PowerShell host is a
  refusal raised *before* the edit is written, `-NoValidate` is the single
  explicit opt-out, and the validator's exit code propagates instead of being
  discarded; the support guard reads `.dev.env` `SUPPORT_GUARD` first and fails
  closed on an unreadable support state.
- `tools/1c-meta-validate/scripts/meta-validate.py` — Python runtime of
  `meta-validate`, upstream base v1.45 (`2e75b0f`). Downstream deltas, the same in
  both runtimes: checks 6a–6d — a `ChildObjects/Form` registration must be a
  scalar reference (6a), it must resolve to `Forms/<Name>.xml` on disk (6b), that
  descriptor must parse as XML (6c), and the name it declares must be the name
  that was registered (6d); required and exactly named GeneratedTypes (2);
  default-form roles (6f, on top of upstream check 20); `Description` / `Code`
  bindings (6g, 6h); case-insensitive name uniqueness shared by attributes,
  tabular sections, dimensions, resources, addressing attributes and accounting
  flags (8); information-register forbidden properties (12) and export-folder
  type names (16a). Format versions follow upstream check 24; the former local
  1e / 6e are retired.
- `tools/_common/dev_env.py` — not upstream code: the Python peer of the local
  `DevEnv.ps1`, so both runtimes read project parameters from `.dev.env`.

**Four local web ports**, derived from the existing vendored PowerShell
publication layout rather than copied from upstream Python:

- `tools/1c-web-ops/scripts/web-publish.py` — publication creation/update.
- `tools/1c-web-ops/scripts/web-info.py` — publication and process status.
- `tools/1c-web-ops/scripts/web-stop.py` — scoped managed-process shutdown.
- `tools/1c-web-ops/scripts/web-unpublish.py` — preview and guarded removal.
- `tools/1c-web-ops/scripts/web_common.py` — shared local implementation:
  standalone Apache, loopback binding, no downloads, path/ownership checks and
  rollback on failed publication updates; since 2026-11-01 it also publishes
  extension web services (`<ws publishExtensionsByDefault>`) and anchors a
  relative `-InfoBasePath` at the `.dev.env` root, as the PowerShell scripts do.
  Runtime differences are documented in `docs/web-manage.md`; offline checks are
  in `tools/tests/web-python-regression.py` (and, for the PowerShell scripts,
  `tools/tests/web-ops-regression.ps1`) in the ruleset source.

Other tool commands remain PowerShell-only. The upstream pin above is not to be advanced without re-running
`tools/tests/python-ports-regression.py` and re-recording the deltas here.

- the PowerShell tool scripts under `tools/` synced from the same upstream
  (per-tool versions and local changes: `docs/CHANGELOG.md`, section "Upstream
  sync 2026-11-01 (2e75b0f)"), including the tools first vendored at this pin:
  `tools/1c-role-edit/` (`role-edit`), `tools/1c-db-ops/scripts/db-cfe-admin.ps1`
  (`db-cfe-admin`) and `tools/1c-v8-xsd-fetch/` (`v8-xsd-fetch`). Copies of
  shared functions across these scripts are held together by
  `tools/tests/vendored-drift.ps1` in the ruleset source.

Not part of this skill, listed for completeness: the ruleset source also
carries a port of upstream `hooks/support-guard.mjs` for Claude Code
(`plugins/1c-rules/hooks/`, not installed with the skill), with its own copy of
this notice in `plugins/1c-rules/hooks/NOTICE.md`.

### MIT licence text

```
MIT License

Copyright (c) 2025-2026 Nick Shirokov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### `1c-uuid-check`

`tools/1c-uuid-check/scripts/uuid-check.ps1` is a port of
`check_uuid_duplicates.py` from <https://github.com/Desko77/claude-code-skills-1c>
(MIT), adapted to the Configurator XML format. The MIT terms above apply to it
under that project's own copyright.
