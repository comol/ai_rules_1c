# Third-party notices — `1c-metadata-manage`

This skill vendors tool scripts from a third-party project. The notice below is
reproduced as the licence requires; it applies to the vendored files listed here
and travels with every copy of this skill, including installed ones
(`<tool>/skills/1c-metadata-manage/NOTICE.md`).

## Nikolay-Shirokov/cc-1c-skills

- Upstream: <https://github.com/Nikolay-Shirokov/cc-1c-skills>
- Pinned commit: `ecd289fe11733028d87b55284ea9fb5feff8f513`
- Licence: MIT

Vendored under `tools/`, with local modifications documented in each file's
header and in `docs/`:

**Python entry points — exactly five, all vendored from the pinned commit above.**
Each was taken from that immutable commit, not from a moving `HEAD`, and each
carries its downstream deltas in its own file header:

- `tools/1c-form-scaffold/scripts/remove-form.py` — Python runtime of
  `form-remove`. Downstream deltas: input validation (1C identifiers, no
  traversal / separators / UNC / symlinked targets), the `-DryRun` / `-Force`
  safety gate, path containment anchored at `-SrcDir` (a symlink or junction on
  any component of the chain is refused before the first mutation), a
  transactional mutation path whose quarantine is discarded only after every
  payload is verifiably back or the transaction has committed, and
  byte-preserving `ChildObjects` editing. Upstream base: v1.4.
- `tools/1c-form-compile/scripts/form-compile.py` — Python runtime of
  `form-compile`. Downstream deltas: one event normalizer for all three DSL
  spellings (`events`, `on` + `handlers`, standalone `handlers`), an explicit
  non-zero refusal when two spellings are given at once or an event name is
  unknown, and the corrected `OnEditEnd` → `ПриОкончанииРедактирования` suffix
  (upstream spells the key `OnEndEdit`, so the auto-name fell through);
  from-object document choice forms get `ChoiceMode`, the document item preset
  writes `AutoTime` / `UsePostingMode` / `RepostOnWrite`, `Description` is bound
  only when `DescriptionLength > 0`, form-property enum values are a closed set,
  and a missing `Configuration.xml` is reported instead of assuming 2.17.
- `tools/1c-form-scaffold/scripts/form-add.py` — Python runtime of `form-add`,
  the managed-form scaffolder. Downstream deltas: `.dev.env` support guard via
  `tools/_common/dev_env.py`, and XML escaping of the user-supplied `-FormName` /
  `-Synonym` in the generated descriptor (upstream interpolates them verbatim, so
  an ordinary `A & B` produced a descriptor no parser accepts); `-FormName` must be
  a 1C identifier, and an information register's object form names its
  `RecordManager` main attribute `Запись`.
- `tools/1c-meta-edit/scripts/meta-edit.py` — Python runtime of `meta-edit`.
  Downstream deltas: `add-form` is refused before any mutation and redirected to
  `form-add`, in every key spelling the dispatcher itself accepts and across the
  whole definition; the auto-validator is resolved under the downstream directory name
  (`1c-meta-validate`), its absence is a refusal raised *before* the edit is
  written, `-NoValidate` is the single explicit opt-out, and the validator's
  exit code propagates instead of being discarded.
- `tools/1c-meta-validate/scripts/meta-validate.py` — Python runtime of
  `meta-validate`. Downstream deltas: checks 6a–6d — a `ChildObjects/Form`
  registration must be a scalar reference (6a), it must resolve to
  `Forms/<Name>.xml` on disk (6b), that descriptor must parse as XML (6c), and the
  name it declares must be the name that was registered (6d); versions equal to
  `Configuration.xml` (1e, 6e), required and exactly named GeneratedTypes (2),
  default-form references and roles (6f), `Description` / `Code` bindings (6g, 6h),
  case-insensitive cross-kind name uniqueness (8), information-register forbidden
  properties (12) and export-folder type names (16a).
- `tools/_common/dev_env.py` — not upstream code: the Python peer of the local
  `DevEnv.ps1`, so both runtimes read project parameters from `.dev.env`.

Everything else under `tools/` is PowerShell-only; **no other Python port is
shipped.** The pin above is not to be advanced without re-running
`tools/tests/python-ports-regression.py` and re-recording the deltas here.

- the PowerShell tool scripts under `tools/` synced from the same upstream
  (per-tool versions and local changes: `docs/*.md`, section "Upstream sync").

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
