---
name: v8unpack-cf
description: "Read and write 1C binary artifacts without the 1C:Enterprise platform. Two workflows: an ordinary form (обычная форма) `Ext/Form.bin` through the `unpack_ordinary_form` / `build_ordinary_form` MCP tools, and a whole CF / CFE / EPF through the `v8unpack` CLI. Use when the task mentions `Form.bin`, обычные формы, a form with no `Form.xml`, or when you have a binary artifact and no infobase / Designer / `ibcmd`."
---

# v8unpack-cf — read and write 1C binary artifacts

Two workflows live here, and they are not variants of one thing:

| You have | Route | Section |
|---|---|---|
| One **ordinary form** — `.../Forms/<Форма>/Ext/Form.bin` | MCP tools `unpack_ordinary_form` / `build_ordinary_form` | *Ordinary forms — `Form.bin`* |
| A whole **CF / CFE / EPF** binary | `v8unpack` CLI (`-E` / `-B`) | *Whole binaries — CF / CFE / EPF* |

Use either when the 1C:Enterprise platform is not at hand. When the configuration
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

**An ordinary form is not XML.** In a Designer file export a managed form writes
`Forms/<Имя>/Ext/Form.xml`; an ordinary form writes `Forms/<Имя>/Ext/Form.bin` — a
1C container holding two payload entries: `form` (the layout, a brace tree) and
`module` (the form module, BSL). The sidecar `Forms/<Имя>.xml` declares which model
it is, via `<FormType>Ordinary</FormType>`.

Find them with `**/Forms/*/Ext/Form.bin`. A form whose `Form.xml` appears to be
"missing" is almost always an ordinary form, not a broken export.

### The MCP contract — `ordinary-form/1`

The same two tools, with the same arguments and the same result payload, are
published by **`1c-code-metadata-mcp`** and **`1c-graph-metadata-mcp`**. Learn them
once. On the graph server the payload arrives in the envelope's `data` section; on
the code server it is the result itself.

#### `unpack_ordinary_form`

| Parameter | Default | Meaning |
|---|---|---|
| `form_path` | — | The `Form.bin` to read. Absolute path; Cyrillic is normal. |
| `workspace_path` | — | Where to materialise the workspace. New, empty, or a workspace this tool wrote. |
| `overwrite` | `false` | Replace an existing workspace **of this contract**. A non-empty directory the tool did not write is refused whatever this says. |
| `include` | `"summary"` | Which bounded preview to embed: `summary` (paths only), `structure`, `module`, `all`. |
| `max_chars` | `4000` | Bound on each embedded preview (server cap 20 000). |

Result: `status`, `contract`, `tool`, `workspace_path`, `manifest_path`, `source`
(`path` / `size` / `sha256`), `container`, `entries`, `entries_truncated`, `notes`,
`warnings` — plus `structure` / `structure_truncated` and `module_text` /
`module_truncated` when `include` asks for them. Each entry carries `name`, `kind`
(`brace_tree` / `bsl_module` / `text` / `container` / `binary`), `size`, `sha256`,
`encoding`, `deflated`, `path` and `decoded_path`.

#### `build_ordinary_form`

| Parameter | Default | Meaning |
|---|---|---|
| `workspace_path` | — | A workspace written by `unpack_ordinary_form`. |
| `output_path` | — | The `Form.bin` to write. Never replaced silently. |
| `overwrite` | `false` | Replace an existing output file. |
| `verify` | `true` | Re-read the result and compare the payload. Leave it on. |

Result: `status`, `contract`, `tool`, `workspace_path`, `output_path`, `output`
(`path` / `size` / `sha256`), `source`, `binary_identical`, `verified`,
`verification` (`match` / `mismatch` / `skipped`, with per-entry hashes),
`changed_entries`, `notes`.

#### Errors

A refusal is `status="error"` with an `error_code` and an actionable `hint`. The
codes: `dependency_missing`, `path_invalid`, `path_not_found`, `not_a_file`,
`not_a_container`, `unsupported_container_layout`, `workspace_not_empty`,
`workspace_exists`, `workspace_invalid`, `manifest_missing`, `manifest_invalid`,
`payload_missing`, `derived_edit_detected`, `output_exists`, `unpack_failed`,
`build_failed`, `verify_failed`.

### The workspace

```text
<workspace>/
  ordinary-form.json    # manifest: source, entries, hashes. Generated — never hand-edit.
  payload/
    form                # the layout brace tree, UTF-8 BOM + CRLF   <- SOURCE OF TRUTH
    module              # the form module, BSL, UTF-8 BOM + CRLF    <- SOURCE OF TRUTH
  decoded/
    form.json           # the layout as JSON-compatible data        <- derived, read-only
    module.bsl          # the module, for BSL tooling               <- derived, read-only
```

**Edit `payload/`.** `decoded/` is regenerated on every unpack and is never read
back. Editing a derived view and then building is refused with
`derived_edit_detected` rather than silently dropped — but only that refusal saves
the work, so do not rely on noticing.

### Workflow — edit an ordinary form

```powershell
# 1. Read it
unpack_ordinary_form(
    form_path="C:\src\Catalogs\Товары\Forms\Форма\Ext\Form.bin",
    workspace_path="C:\work\Форма")

# 2. Edit C:\work\Форма\payload\module (BSL) or payload\form (the layout tree).
#    Keep the UTF-8 BOM and the CRLF line endings.

# 3. Write it back, and prove nothing was lost
build_ordinary_form(
    workspace_path="C:\work\Форма",
    output_path="C:\src\Catalogs\Товары\Forms\Форма\Ext\Form.bin",
    overwrite=$true)
```

Check `verification.status == "match"`. Then load the export into the infobase the
normal way (`/update1cbase`) — this skill writes a file, it does not touch an
infobase.

Paths with spaces or Cyrillic go in double quotes, always. In PowerShell prefer
single-quoted literals (`'C:\src\...\Form.bin'`) when the path contains `$`.

### Warnings — read before the first call

- **`Form.bin` is a binary 1C container, not a document. Never edit it directly,
  never read it as XML, never open it with an XML tool.** A text editor corrupts
  it silently. It is *one* container: the reference ordinary form holds exactly two
  entries, `form` and `module`, stored verbatim. A file holding more than one
  container is a whole CF / CFE / EPF and is refused with
  `unsupported_container_layout`; an entry that is itself a container is kept whole
  rather than descended into, which is what keeps the round trip lossless.
- **Never Deflate the entries of a `Form.bin`.** 1C:Enterprise reads the `form` and
  `module` streams of a standalone ordinary form only as plain UTF-8 BOM text; a
  deflated stream is «Ошибка формата потока» and the thick client exits (observed on
  8.3.27.2074, in Designer and in Enterprise alike — a 728 KB form packed to 114 KB
  never opened again until it was repacked plain). Designer writes them plain.
  `build_ordinary_form` writes every entry plain whatever the manifest's `deflated`
  flag says (the flag records how the *source* stored the entry; a deflated source
  is reported in `warnings` on unpack and in `notes` on build). Do not "optimise"
  a `Form.bin` with any repacking tool's `-deflate` / `-pack` — the size it saves is
  the form it loses.
- **Do not judge a round trip by the final SHA-256.** `v8unpack` stamps container
  records with the current time, so a rebuilt `Form.bin` differs byte for byte from
  its source even when nothing changed. `binary_identical: false` together with
  `verification.status: "match"` is the **normal, correct** outcome. The equality
  that means "nothing was lost" is the logical payload — entry names, sizes and
  SHA-256 — which is what `verification` reports.
- **Preserve the workspace manifest and `payload/`.** They are what a build reads.
  A workspace without `ordinary-form.json` is not a workspace (`manifest_missing`),
  and a missing payload entry is refused (`payload_missing`) rather than built
  around.
- **A standalone `Form.bin` names nothing.** Its brace tree is positional: it is
  structurally parseable, and no token in it says "this is a button called X". Do
  not invent element names, types or handlers from it. Named element trees
  (`*.elem.json`) come from high-level CF / CFE / EPF extraction, where the
  surrounding metadata supplies the names — and even there v8unpack 1.2.6 writes a
  populated tree only for **managed** forms (see *Limitations*).
- **On Windows use `--processes 1`** for the CLI unless parallel processing has
  been validated for the artifact at hand. The MCP tools spawn no processes at all.
- **Nothing is overwritten silently.** An existing workspace needs
  `overwrite=true`; an existing output file needs `overwrite=true`; a non-empty
  directory the tool did not write is refused outright, `overwrite` or not.

### Which route for a form

| Situation | Route |
|---|---|
| One ordinary form, sources already on disk | `unpack_ordinary_form` / `build_ordinary_form` |
| Every form of a `.cf` / `.cfe` / `.epf` at once | CLI `-E`, then the per-form files it writes |
| The infobase is available and you want XML sources | `/getconfigfiles` — not this skill |
| A managed form (`Ext/Form.xml`) | `1c-metadata-manage` skill — not this skill |

## Whole binaries — CF / CFE / EPF

### CLI commands

#### Extract (`-E`)

```bash
python -m v8unpack -E "<file.cf>" "<sources_dir>" --temp "<temp_dir>"
```

| Parameter | Description |
|-----------|-------------|
| `<file.cf>` | Path to a CF, CFE or EPF file |
| `<sources_dir>` | Destination for the unpacked sources (created automatically) |
| `--temp <path>` | Folder for intermediate data (kept, not deleted — useful for debugging) |
| `--processes N` | Number of worker processes (default: `cpu_count - 2`) |
| `--descent XYYZZZ` | Extension versioning mode (configuration version suffix) |
| `--auto_include` | Build the table of contents dynamically from the folder, not from the header |
| `--prefix STR` | Prefix for first-level metadata names |

#### Build (`-B`)

```bash
python -m v8unpack -B "<sources_dir>" "<file.cf>"
```

**`-B` rebuilds what `-E` wrote — it is not a way to produce a `.cf` for loading
into an infobase of a current configuration.** On a real 8.3.27 configuration the
round trip degraded the metadata: XML descriptors of version 3 came back as
version 2 (`Задача`), standard attributes broke, objects dropped out of the
exchange-plan content (УРБД). The library decodes metadata through its own,
version-bounded parsers, and what it does not know it does not write back. Use it
for a data processor / extension you extracted with the same version, or to
inspect; a configuration goes back into an infobase only through the platform
(`/LoadConfigFromFiles` from the Designer file export, or `/LoadCfg` of a file the
platform wrote).

| Parameter | Description |
|-----------|-------------|
| `<sources_dir>` | Folder with the unpacked sources |
| `<file.cf>` | Path to the output CF / CFE / EPF file |
| `--index <path>` | JSON table-of-contents file (maps files across folders) |
| `--version XYYZZ` | Compatibility-mode version (for extensions), e.g. `80306` = 8.3.6 |
| `--descent XYYZZZ` | Configuration version suffix |

#### Index (`-I`)

```bash
python -m v8unpack -I "<sources_dir>" --index index.json --core core
```

Generates / updates `index.json` — the table-of-contents file that controls how sources
are laid out across subfolders.

#### Batch operations (`-EA`, `-BA`, `-IA`)

```bash
python -m v8unpack -EA products.json              # extract all products
python -m v8unpack -BA products.json              # build all products
python -m v8unpack -BA products.json --index KEY  # build a specific product
```

`products.json` describes several products with their individual build parameters.

### Python API

```python
import v8unpack

v8unpack.extract('d:/sample.cf', 'd:/src')
v8unpack.extract('d:/sample.cf', 'd:/src', temp_dir='d:/temp',
                 options={'descent': 4100200, 'auto_include': True})

v8unpack.build('d:/src', 'd:/repacked.cf')
v8unpack.build('d:/src', 'd:/repacked.cf', index='index.json',
               options={'descent': 4100200, 'version': '80306'})
```

### Examples

#### Extract a configuration

```bash
python -m v8unpack -E "<project>/1Cv8.cf" "<project>/src" --temp "<project>/temp"
```

#### Build it back

```bash
python -m v8unpack -B "<project>/src" "<project>/1Cv8_new.cf"
```

#### Extract an external data processor

```bash
python -m v8unpack -E "MyDataProcessor.epf" "src_epf"
```

#### Extract an extension

```bash
python -m v8unpack -E "MyExtension.cfe" "src_cfe" --descent 3000112
```

#### Build an extension

```bash
python -m v8unpack -B "src_cfe" "bin/ext.cfe" --index cmd/index.json --descent 3000112 --version 80316
```

### Version compatibility

The utility version is recorded in `Configuration.json` (`"v8unpack": "1.2.6"`). On
build, `major.minor` must match. If the versions differ:

1. Build with the old version.
2. Upgrade the utility.
3. Re-extract with the new version.
4. Commit.

### Intermediate stages (`--temp`)

| Stage | Description |
|-------|-------------|
| `decode_stage_0/` | Extraction from the 1C container |
| `decode_stage_1/` | Decompression (zlib), bracket-files |
| `decode_stage_3/` | Metadata parsing → tree |
| Destination folder | Code organization (include, form elements) |

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
  forms of a modern configuration the CLI route yields no named elements, and the
  layout has to be read from `Form.bin` — positionally.
- **`v8unpack` 1.2.6 cannot write a container with compressed entries through
  `Container.build(nested=False)`** — it raises `struct.error`, because
  `Document.compress` returns no table-of-contents offset. Irrelevant for a
  `Form.bin`: its entries must be plain anyway (see *Warnings*), and the MCP codec
  writes them plain with verbatim (`nested=True`) container records. Relevant only
  if you drive the library directly for a whole CF / CFE / EPF.
- **A `.cf` rebuilt with `-B` from a current configuration is not the
  configuration** — see *Build (`-B`)* above. Observed metadata degradation on
  8.3.27; the platform is the only writer of a loadable configuration file.
- A rebuilt binary's SHA-256 always differs from its source (write timestamps).
  See the warning above.

## Relationship to other rules

- `getconfigfiles` — extracts configuration objects from a running infobase through the
  platform. Prefer it when an infobase is available; use `v8unpack-cf` when you only have
  a binary artifact and no platform.
- `1c-metadata-manage` — MCP-based skill for operating on the metadata structure once the
  sources are unpacked. It owns **managed** forms (`Ext/Form.xml`); ordinary forms
  are this skill's, because there is no XML for it to edit.
- `forms.md` — the router for managed-form work. It sends ordinary forms here.
- `mcp-1c-tools` — the MCP catalog. `unpack_ordinary_form` / `build_ordinary_form`
  are listed there under both `1c-code-metadata-mcp` and `1c-graph-metadata-mcp`;
  this file is the contract they share.
