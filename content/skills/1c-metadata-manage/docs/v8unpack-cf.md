# v8unpack — unpack and rebuild 1C binary files (CF / CFE / EPF)

`v8unpack` is a Python utility that unpacks CF, CFE, and EPF binary files into human-readable sources (JSON + BSL) with a metadata tree — **without the 1C platform installed**. Useful for diff/merge in source control when only binaries are available, for offline inspection of third-party configurations and extensions, and for partial rebuild pipelines.

Install: `pip install v8unpack` (or dev install from the repository).

> Use this when the standard tools under `tools/1c-cf-manage/`, `tools/1c-cfe-manage/`, `tools/1c-epf-*` cannot be applied because the 1C platform is not available on the host (e.g. CI runner, Linux box without `1cv8.exe`).

## Commands

### Extract (`-E`)

```bash
python -m v8unpack -E "<file.cf>" "<sources_folder>" --temp "<temp_folder>"
```

| Parameter | Description |
|-----------|-------------|
| `<file.cf>` | Path to a CF, CFE, or EPF file |
| `<sources_folder>` | Where to unpack (created automatically) |
| `--temp <path>` | Folder for intermediate data (kept for debugging) |
| `--processes N` | Worker count (default `cpu_count - 2`) |
| `--descent XYYZZZ` | Versioning mode for extensions (configuration version suffix) |
| `--auto_include` | Build dynamic table of contents from the folder, not the header |
| `--prefix STR` | Prefix for first-level metadata names |

### Build (`-B`)

```bash
python -m v8unpack -B "<sources_folder>" "<file.cf>"
```

| Parameter | Description |
|-----------|-------------|
| `<sources_folder>` | Folder with unpacked sources |
| `<file.cf>` | Path to the output CF / CFE / EPF file |
| `--index <path>` | JSON index file (mapping of files to folders) |
| `--version XYYZZ` | Compatibility-mode version (for extensions), e.g. `80306` = 8.3.6 |
| `--descent XYYZZZ` | Configuration version suffix |

### Index (`-I`)

```bash
python -m v8unpack -I "<sources_folder>" --index index.json --core core
```

Generates / updates `index.json` — the table of contents used to lay sources out across subfolders.

### Batch operations (`-EA`, `-BA`, `-IA`)

```bash
python -m v8unpack -EA products.json              # extract all products
python -m v8unpack -BA products.json              # build all products
python -m v8unpack -BA products.json --index KEY  # build a specific product
```

`products.json` describes several products with individual build parameters.

## Python API

```python
import v8unpack

v8unpack.extract('d:/sample.cf', 'd:/src')
v8unpack.extract('d:/sample.cf', 'd:/src', temp_dir='d:/temp',
                 options={'descent': 4100200, 'auto_include': True})

v8unpack.build('d:/src', 'd:/repacked.cf')
v8unpack.build('d:/src', 'd:/repacked.cf', index='index.json',
               options={'descent': 4100200, 'version': '80306'})
```

## Common workflows

### Unpack a configuration

```bash
python -m v8unpack -E "<project>/1Cv8.cf" "<project>/src" --temp "<project>/temp"
```

### Build it back

```bash
python -m v8unpack -B "<project>/src" "<project>/1Cv8_new.cf"
```

### Unpack an external data processor

```bash
python -m v8unpack -E "MyProcessor.epf" "src_epf"
```

### Unpack an extension

```bash
python -m v8unpack -E "MyExtension.cfe" "src_cfe" --descent 3000112
```

### Build an extension

```bash
python -m v8unpack -B "src_cfe" "bin/ext.cfe" --index cmd/index.json --descent 3000112 --version 80316
```

## Version compatibility

The utility version is recorded in `Configuration.json` (`"v8unpack": "1.2.6"`). Build checks for `major.minor` match. If versions differ:

1. Build with the old version
2. Upgrade the utility
3. Unpack with the new version
4. Commit the result

## Intermediate stages (`--temp`)

| Stage | Description |
|-------|-------------|
| `decode_stage_0/` | Extracted from the 1C container |
| `decode_stage_1/` | Decompressed (zlib), bracket files |
| `decode_stage_3/` | Metadata parsed → tree |
| Destination folder | Code organization (include, form elements) |

## Source layout produced by v8unpack

### Configuration root

```
src/
  Configuration.json          ← configuration metadata
  Configuration.seance.bsl    ← session module
  Configuration.app.bsl       ← managed application module
  Configuration.802.bsl       ← ordinary application module
  Configuration.con.bsl       ← external connection module
  Configuration.4.json        ← additional configuration data
  help.html                   ← help
  Заставка                    ← splash (binary)
  Catalog/                    ← catalogs
  Document/                   ← documents
  CommonModule/               ← common modules
  InformationRegister/        ← information registers
  AccumulationRegister/       ← accumulation registers
  Report/                     ← reports
  DataProcessor/              ← data processors
  Enum/                       ← enumerations
  ...                         ← other metadata types
```

### Per-object folder (Catalog example)

```
Catalog/Номенклатура/
  Catalog.id.json           ← {"uuid": "..."}
  Catalog.json              ← metadata (name, name2, header)
  Catalog.obj.bsl           ← object module
  Catalog.mgr.bsl           ← manager module (if any)
  Catalog.html              ← help (if any)
  CatalogForm/
    ФормаЭлемента/
      CatalogForm.id.json
      CatalogForm.json
      CatalogForm.obj.bsl   ← form module
      CatalogForm.elem.json ← form elements
  Template/
    МакетПечати.mxl
    МакетПечати.json
```

### Module file suffixes

| Object type | Module suffixes |
|-------------|-----------------|
| Configuration | `.seance.bsl`, `.app.bsl`, `.802.bsl`, `.con.bsl` |
| Catalog, Document, DataProcessor | `.obj.bsl` (object), `.mgr.bsl` (manager) |
| CommonModule | `.obj.bsl` (module code) |
| `*Form` | `.obj.bsl` (form module) |

### Form structure

Each form is a named folder with 4 files:

| File | Content |
|------|---------|
| `*.id.json` | Form UUID |
| `*.json` | Form metadata + type + version |
| `*.obj.bsl` | Form module (BSL code) |
| `*.elem.json` | Form elements (tree + data + attributes + commands + parameters) |

`Тип формы` values: `"0"` — ordinary form, `"1"` — managed form.
`Версия элементов формы` values: `"0-26"` (ordinary 8.0/8.1), `"0-27"` (ordinary 8.2), `"1"` (managed 8.3+).

## What is safe to edit by hand

Safe:

- `*.obj.bsl` — module code
- `name`, `name2`, `comment` in `*.json`

Do **not** edit by hand:

- `header`, `form` in `*.json`
- `raw` in `*.elem.json`
- `tree` / `data` in `*.elem.json` (analysis only, not manual editing)

`v8unpack` is **not** designed to create new metadata objects from scratch. It works with existing binaries. To create new objects, use the regular Designer / EDT or the scripts under `tools/1c-meta-compile/`, then unpack/build with `v8unpack` if needed.

## Limitations

- Object properties and form layout live in `header` / `raw` as raw arrays
- Files > 1 MB (layouts, HTML) are stored as `.bin` without decoding
- Encrypted modules are stored as binary
- With `--auto_include`, nested objects are sorted alphabetically

## include / includr regions

```bsl
#Область include_core_form3_test
    // code is saved into ../core/form3/test.bsl
#КонецОбласти
```

- `include_*` — editable region (refreshed on extract)
- `includr_*` — read-only region (only substituted on build)

## descent — extension versioning

Configuration version suffix in the form `XYYZZZ` (4 segments × 3 digits, first segment of arbitrary length):

| Configuration version | Suffix |
|----------------------|--------|
| 4.10.2 | 4010002 |
| 3.0.112 | 3000112 |
| 2.5.6 | 2005006 |

Files with suffix: `DocumentForm.obj.4010002.bsl` — code for version 4.10.2. On build with `--descent X`, the file with the largest suffix `≤ X` is taken.

## index.json — file mapping

```json
{
  "ExternalDataProcessor.json": "core/ExternalDataProcessor.json",
  "Form": {
    "API": {
      "API.obj.bsl": "core/Form/API.obj.bsl",
      "*": "core/Form/API"
    }
  },
  "index.json": ["submodule/index.json"]
}
```

- Specific file → specific path
- `"*"` → all files in the folder
- `null` → exclude from `*`
- Array → include nested `index.json` files
