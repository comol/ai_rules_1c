---
name: v8unpack-cf
description: "Unpack and repack 1C binary files (CF / CFE / EPF) with the Python `v8unpack` utility — no 1C platform required. Use when you need to extract a configuration, extension or data processor into human-readable sources (JSON + BSL), or build a binary back from sources, and the 1C:Enterprise platform is not available."
---

# v8unpack-cf — unpack and repack 1C binary files

`v8unpack` is a Python utility that unpacks 1C binary files (CF / CFE / EPF) into a
human-readable source tree (JSON + BSL) **without the 1C:Enterprise platform**, and
builds the binary back from those sources.

Use this skill when you only have a binary artifact (a `.cf` configuration dump, a
`.cfe` extension, or an `.epf` external data processor) and no running infobase or
Designer / `ibcmd` at hand. When the configuration lives in an infobase, extract it
through the platform instead — see the `getconfigfiles` rule.

## Dependency

- `v8unpack` Python package — install with `pip install v8unpack` (or a dev install
  from its repository). Verify with `python -m v8unpack --help`.

## Commands

### Extract (`-E`)

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

### Build (`-B`)

```bash
python -m v8unpack -B "<sources_dir>" "<file.cf>"
```

| Parameter | Description |
|-----------|-------------|
| `<sources_dir>` | Folder with the unpacked sources |
| `<file.cf>` | Path to the output CF / CFE / EPF file |
| `--index <path>` | JSON table-of-contents file (maps files across folders) |
| `--version XYYZZ` | Compatibility-mode version (for extensions), e.g. `80306` = 8.3.6 |
| `--descent XYYZZZ` | Configuration version suffix |

### Index (`-I`)

```bash
python -m v8unpack -I "<sources_dir>" --index index.json --core core
```

Generates / updates `index.json` — the table-of-contents file that controls how sources
are laid out across subfolders.

### Batch operations (`-EA`, `-BA`, `-IA`)

```bash
python -m v8unpack -EA products.json              # extract all products
python -m v8unpack -BA products.json              # build all products
python -m v8unpack -BA products.json --index KEY  # build a specific product
```

`products.json` describes several products with their individual build parameters.

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

## Examples

### Extract a configuration

```bash
python -m v8unpack -E "<project>/1Cv8.cf" "<project>/src" --temp "<project>/temp"
```

### Build it back

```bash
python -m v8unpack -B "<project>/src" "<project>/1Cv8_new.cf"
```

### Extract an external data processor

```bash
python -m v8unpack -E "MyDataProcessor.epf" "src_epf"
```

### Extract an extension

```bash
python -m v8unpack -E "MyExtension.cfe" "src_cfe" --descent 3000112
```

### Build an extension

```bash
python -m v8unpack -B "src_cfe" "bin/ext.cfe" --index cmd/index.json --descent 3000112 --version 80316
```

## Version compatibility

The utility version is recorded in `Configuration.json` (`"v8unpack": "1.2.6"`). On
build, `major.minor` must match. If the versions differ:

1. Build with the old version.
2. Upgrade the utility.
3. Re-extract with the new version.
4. Commit.

## Intermediate stages (`--temp`)

| Stage | Description |
|-------|-------------|
| `decode_stage_0/` | Extraction from the 1C container |
| `decode_stage_1/` | Decompression (zlib), bracket-files |
| `decode_stage_3/` | Metadata parsing → tree |
| Destination folder | Code organization (include, form elements) |

## Limitations

- Object properties and form layout are stored in `header` / `raw` as raw arrays.
- Files larger than 1 MB (layouts, HTML) are stored as `.bin` without decoding.
- Encrypted modules are kept in binary form.
- With `--auto_include`, nested objects are sorted alphabetically.

## Relationship to other rules

- `getconfigfiles` — extracts configuration objects from a running infobase through the
  platform. Prefer it when an infobase is available; use `v8unpack-cf` when you only have
  a binary artifact and no platform.
- `1c-metadata-manage` — MCP-based skill for operating on the metadata structure once the
  sources are unpacked.
