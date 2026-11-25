# 1C UUID Check — duplicate-identity detection in an XML dump

Scans a Configurator XML dump for **duplicate UUIDs** and optionally regenerates them. A UUID is an object's identity: two objects claiming the same one makes the configuration fail to load, or — worse — load with one object silently shadowing the other.

Two carriers are checked:

- `uuid="..."` attributes — objects, attributes, tabular sections, `ThisNode` of exchange plans;
- `<xr:TypeId>` / `<xr:ValueId>` elements inside `<InternalInfo>` — generated types.

## When to run

- After **bulk generation** of metadata (`meta-compile`, `cf-init`, scaffolding several objects in one pass) — the usual source of collisions is a UUID copied between objects instead of generated per object.
- After **hand-editing** metadata XML outside this skill (see `metadata-xml-workarounds.md`).
- After **merging branches** that both added metadata objects.
- Before loading a dump into an infobase, when the previous load failed with an identity / type-collision diagnostic.

Slash command: `/check-uuid` (source: `content/commands/check-uuid.md`).

## Usage

```
1c-uuid-check <ConfigPath> [-IncludeIntra] [-Fix] [-Filter <mask>] [-MaxReported <n>] [-OutFile <path>]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ConfigPath | yes | — | `src/` root of the dump, or a single XML file |
| IncludeIntra | no | off | Also report / repair duplicates **within one file** |
| Fix | no | off | Regenerate every duplicate except the first occurrence |
| Filter | no | `*.xml` | File mask to scan |
| MaxReported | no | `50` | Cap on duplicate groups printed per section |
| OutFile | no | — | Write the report to a file instead of stdout |

## Command

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File skills/1c-metadata-manage/tools/1c-uuid-check/scripts/uuid-check.ps1 -ConfigPath "<src>" [-IncludeIntra] [-Fix]
```

Exit codes: `0` — clean (or repaired), `1` — duplicates found.

## Cross-file vs intra-file

- **Cross-file** duplicates — the same UUID in two different files. Always a collision, always reported.
- **Intra-file** duplicates — the same UUID twice inside one file. Reported only with `-IncludeIntra`, but the run always states how many were suppressed. In the Configurator XML format these are usually genuine errors too (each generated type gets its own `TypeId` and `ValueId`), so inspect them after bulk generation rather than assuming they are benign.

## `-Fix` — read before using

`-Fix` keeps the **first** occurrence of each duplicate and regenerates the rest. That choice is positional, not semantic — the script cannot know which object is meant to keep the identity.

- **Safe** on freshly generated sources that have never been loaded into an infobase.
- **Dangerous** on sources already loaded: changing an object's `uuid` makes the platform treat it as a *new* object on the next load, orphaning the existing data. When the dump is already in use, decide by hand which occurrence keeps the identity and fix the other one.

The repair preserves the file byte-for-byte apart from the replaced GUIDs — BOM and line endings are kept as they were (`metadata-xml-workarounds.md` covers why that matters).

After a repair: re-run without `-Fix` to confirm the dump is clean, then validate the affected objects (`meta-validate`, `cf-validate`) before loading.

## Notes

- Point `ConfigPath` at **one** configuration root. Scanning a folder that contains both `src/` and a build copy of the same configuration reports every UUID in it as a cross-file duplicate.
- The tool is read-only without `-Fix`; running it as a check costs nothing and is a reasonable step after any bulk metadata generation.
