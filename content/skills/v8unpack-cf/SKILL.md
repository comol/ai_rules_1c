---
name: v8unpack-cf
description: "Read and write a whole 1C binary — CF / CFE / EPF — without the platform via the `v8unpack` CLI. Use for a binary with no infobase / Designer / `ibcmd`; one ordinary form (`Form.bin`, `form.frm`) is the form-ordinary skill."
---

# v8unpack-cf — read and write 1C binary artifacts

This skill owns whole binaries. One ordinary form is not one of them:

| You have | Route | Section |
|---|---|---|
| One **ordinary form** — `.../Forms/<Форма>/Ext/Form.bin` or `form.frm` | skill `form-ordinary` (`content/skills/form-ordinary/SKILL.md`); MCP `unpack_ordinary_form` / `build_ordinary_form` only as its fallback | *Ordinary forms — `Form.bin`* |
| A whole **CF / CFE / EPF** binary | `v8unpack` CLI (`-E` / `-B`) | *Whole binaries — CF / CFE / EPF* |

Use this skill when the 1C:Enterprise platform is not at hand. When the configuration
lives in an infobase, extract it through the platform instead — see the
`getconfigfiles` rule.

## Dependency

- `v8unpack` Python package — `pip install "v8unpack>=1.2.6,<2"`. Verify with
  `python -m v8unpack --help`.
- Both MCP servers declare it in their own requirements, so the tools work in a
  built image. When it is missing they answer `status="error"`,
  `error_code="dependency_missing"` with the install line in `hint` — that is the
  answer, not a crash.

## Ordinary forms — `Form.bin`

An ordinary form is the `form-ordinary` skill's (`content/skills/form-ordinary/SKILL.md`): a named format map, edit operations, validation, rendering and the `Form.bin` round trip, with no MCP server. Fall back to the MCP pair `unpack_ordinary_form` / `build_ordinary_form` only when that skill cannot run here (no Python ≥ 3.12, a failing `selftest`) and the task is a lossless container round trip; then read [ordinary-forms.md](docs/ordinary-forms.md) first — exact MCP contract, workspace, workflow and warnings. Never edit `Form.bin` directly or deflate its entries.

## Whole binaries — CF / CFE / EPF

Before whole-binary extraction, build, indexing or Python API use, read [whole-binaries.md](docs/whole-binaries.md). On Windows use `--processes 1` unless parallel processing is validated for the artifact. A rebuilt current-configuration `.cf` is not a loadable substitute for a platform-written file; the limitations below apply.

## Limitations

Of the CLI route:

- Object properties and form layout are stored in `header` / `raw` as raw arrays.
- Files larger than 1 MB (layouts, HTML) are stored as `.bin` without decoding.
- Encrypted modules are kept in binary form.
- With `--auto_include`, nested objects are sorted alphabetically.

Of ordinary forms specifically — measured on a real extraction (`1C-Gitter`
1.1.0.8, 170 form artifacts, v8unpack 1.2.6), not assumed:

- **`*.elem.json` is populated for managed forms and empty for ordinary ones.**
  23 of 23 managed forms (`Тип формы` = `1`) came back with a named `tree`;
  147 of 147 ordinary forms (`Тип формы` = `0`, element version `''` or `0-5-1`)
  came back empty, because neither version is in v8unpack's
  `FormCore.supported_form_versions` (`0-26`, `0-27`, `1`). So for the ordinary
  forms of a modern configuration the CLI route yields no named elements; read
  their layout from `Form.bin` with `form-ordinary` (`decode` names positions by
  its format map).
- **`v8unpack` 1.2.6 cannot write a container with compressed entries through
  `Container.build(nested=False)`** — it raises `struct.error`, because
  `Document.compress` returns no table-of-contents offset. Irrelevant for a
  `Form.bin`: its entries must be plain anyway (see [ordinary-form warnings](docs/ordinary-forms.md#warnings--read-before-the-first-call)), and the MCP codec
  writes them plain with verbatim (`nested=True`) container records. Relevant only
  if you drive the library directly for a whole CF / CFE / EPF.
- **A `.cf` rebuilt with `-B` from a current configuration is not the
  configuration** — see [whole-binary build](docs/whole-binaries.md#build--b). Observed metadata degradation on
  8.3.27; the platform is the only writer of a loadable configuration file.
- A rebuilt binary's SHA-256 always differs from its source (write timestamps).
  Compare logical payload, not the container hash (see [ordinary-form warnings](docs/ordinary-forms.md#warnings--read-before-the-first-call)).

## Relationship to other rules

- `getconfigfiles` — extracts configuration objects from a running infobase through the
  platform. Prefer it when an infobase is available; use `v8unpack-cf` when you only have
  a binary artifact and no platform.
- `1c-metadata-manage` — MCP-based skill for operating on the metadata structure once the
  sources are unpacked. It owns **managed** forms (`Ext/Form.xml`); ordinary forms
  are `form-ordinary`'s, because there is no XML for it to edit.
- `form-ordinary` — ordinary forms (`Form.bin`, `form.frm`): reading, editing,
  generation, rendering, `pack` / `unpack`, and `epf-copyinfo` for an `.epf` built
  by `ibcmd`.
- `forms.md` — the router for managed-form work. It sends ordinary forms to
  `form-ordinary`.
- `mcp-1c-tools` — the MCP catalog. `unpack_ordinary_form` / `build_ordinary_form`
  are listed there under both `1c-code-metadata-mcp` and `1c-graph-metadata-mcp`;
  [ordinary-forms.md](docs/ordinary-forms.md) is the contract they share — the
  fallback route.
