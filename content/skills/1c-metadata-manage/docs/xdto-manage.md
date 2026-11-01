# 1C XDTO Manage — Packages, Types, Schemas

Analyze, create, edit, export and validate **XDTO packages** — the type model 1C uses for exchanges, integrations, web services and any external XML format.

A package lives in the configuration sources as `XDTOPackages/<Name>.xml` (the metadata object) plus `XDTOPackages/<Name>/Ext/Package.bin` (the model — despite the extension, plain XML), and is registered in `Configuration.xml`.

**Never hand-edit `Package.bin` or the package XML.** Use the tools below: they keep the model, the metadata object and the `Configuration.xml` registration consistent.

---

## Choosing the tool

| Need | Tool |
|------|------|
| "What packages exist / what does this type look like when I fill it in code?" | `xdto-info` |
| Add a package from a partner's XSD | `xdto-compile` |
| Change one type / property in an existing package | `xdto-edit` |
| Rework a schema wholesale, or hand it to a counterparty | `xdto-decompile` → edit XSD → `xdto-compile -Force` |
| Check a package before loading into the base | `xdto-validate` |

Reading `Package.bin` directly to "just have a look" is the anti-pattern this group replaces: `xdto-info` gives the same answer in 1C terms, `xdto-decompile` gives the full schema.

---

## 1. Info — Analyze Package Structure

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-xdto-manage/scripts/xdto-info.ps1 -PackagePath "<path>"
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `PackagePath` | yes | Package directory **or** the configuration sources root. Alias — `-Path` |
| `Namespace` | no | Pick the package by namespace URI (when the path is the sources root) |
| `Package` | no | Pick the package by metadata object name |
| `Name` | no | Type name. Without a selected package, searched across the whole configuration |
| `Depth` | no | Expansion depth for nested objects. Default 1 |
| `RequiredOnly` | no | Keep only mandatory properties — the skeleton for "fill in what is required" |
| `Mode` | no | `used-by` — show what references the type |
| `Limit` / `Offset` | no | Pagination. Default 150 lines |
| `OutFile` | no | Write the result to a file (UTF-8 BOM) |

The entry point is derived from the path: sources root → list of packages; package directory → its contents.

| Call | Result |
|------|--------|
| `-PackagePath src` | all configuration packages: name, type count, namespace |
| `-PackagePath src/XDTOPackages/ОбменСБанком` | imports, entry points, type lists |
| `... -Name ПлатежныйДокумент` | type structure ready for filling in code |
| `... -Name ПлатежныйДокумент -Depth 3` | same, with nested objects expanded |
| `... -Mode used-by -Name СуммаТип` | what references the type, neighbouring packages included |

Properties are reported the way they will be filled in code: value type in 1C notation with restrictions (`Строка(6)`, `Число(18,2)`), mandatory / collection as flags, allowed values listed for enumerated types. An unflagged property is optional.

**Usual case — namespace and type known, package name not.** That is exactly what `ФабрикаXDTO.Тип(<namespace>, <type>)` gives you in the code:

```powershell
... -PackagePath src -Namespace "urn:1C.ru:ClientBankExchange" -Name ПлатежныйДокумент
```

With only a type name, pass `-Name` plus the sources root — the type is found across all packages; on multiple hits the tool shows where, so you can narrow it down.

---

## 2. Compile — Build a Package from an XML Schema

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-xdto-manage/scripts/xdto-compile.ps1 -XsdPath "<schema.xsd>" -OutputDir "<sources-dir>"
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `XsdPath` | one of two | Path to the XML schema file. Alias — `-Path` |
| `Xsd` | one of two | Schema as a string, instead of `-XsdPath` |
| `OutputDir` | yes | Configuration or extension sources directory — the one holding `Configuration.xml` |
| `Name` | no | Metadata object name. Default: from `xs:appinfo`, else the XSD file name sanitized into a 1C identifier |
| `Synonym` | no | Synonym. Default: from `xs:appinfo`, else the package name. For several languages set it in the schema via `xs:appinfo` |
| `Comment` | no | Comment. Default: from `xs:appinfo` |
| `Force` | no | Overwrite an existing package. Without it the tool refuses to clobber an assembled package |

The package is stamped with the format version of `Configuration.xml` (2.17 only when there is none); 2.21 adds the `xmlns:pal` header. Registration in `Configuration.xml` is a one-line raw-text insertion placed by `NEW_OBJECT_POSITION` (`.dev.env`; default `end` of the `XDTOPackage` group, `byName` on request). `xdto-compile` and `xdto-edit` share the support guard of the other tools ([support-manage.md](support-manage.md)).

The input is an ordinary XML schema — written the same way as for any other tool.

### Read the warnings

XSD is more expressive than the XDTO model. Anything that does not map one-to-one is carried over **approximately, with a warning**:

```
Предупреждения (2) — конструкции XSD без точного соответствия в модели XDTO:
  ! Документ : вложенная xs:choice уплощена в последовательность — выбор одного из вариантов не сохранён
  ! Документ : кратность на вложенной частице (<xs:sequence minOccurs/maxOccurs>) не выражается в модели XDTO
```

The package is assembled, but the schema was simplified. If the simplification is unacceptable — change the schema (e.g. split `xs:choice` variants into separate types), do not ignore the warning.

Carried over approximately: nested `xs:sequence` / `xs:choice` (flattened into a plain property list), `xs:all` (becomes a sequence), particle cardinality, `substitutionGroup`, `xs:key` / `keyref` / `unique`, `xs:redefine`. `xs:group` and `xs:attributeGroup` are expanded by reference. `xs:include` is ignored — XDTO resolves dependencies by namespace only, so an included schema must be built as its own package and the `include` replaced with an `import`.

### Dependencies between packages

`<xs:import namespace="…"/>` is resolved by namespace among the packages of the configuration or extension. **If no package with that namespace exists, the platform silently substitutes `xs:anyType` on load — without an error.** Build dependencies first, then the dependent package, and check the result with `xdto-validate`.

Two things the XDTO model has and XML Schema does not — `nillable` on an attribute and `qualified` on an individual property — are written as attributes from the model namespace (`xdto:nillable="true"`); the schema stays valid, validators ignore them. Full XSD ↔ XDTO mapping table: [xsd-reference.md](../tools/1c-xdto-manage/xsd-reference.md).

---

## 3. Edit — Point Edits of an Existing Package

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-xdto-manage/scripts/xdto-edit.ps1 -PackagePath "<path>" -Operation <op> -Target "<address>" -Value "<value>"
```

Changes a single element without reading and rewriting the whole schema — for big packages (`EnterpriseData` is about a megabyte) this is the only practical path.

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `PackagePath` | yes | Package directory, `Ext/Package.bin` or `<Name>.xml`. Alias — `-Path` |
| `Operation` | yes | Operation from the table below |
| `Target` | depends | Address: type name or `Type.Property` path |
| `Value` | depends | XSD fragment, literal, URI or text. `@path` — take the content from a file |
| `NoValidate` | no | Skip the automatic `xdto-validate` after the edit |

### Operations

| Operation | `-Target` | `-Value` |
|-----------|-----------|----------|
| `add-property` | type name | `<xs:element>` or `<xs:attribute>` |
| `replace-property` | `Type.Property` | the new declaration in full |
| `remove-property` | `Type.Property` | — |
| `add-type` | — | `<xs:complexType>` or `<xs:simpleType>` |
| `remove-type` | type name | — |
| `add-enum` | value type name | literal |
| `add-import` | — | namespace URI |
| `rename` | — | new metadata object name |
| `set-synonym` | — | synonym |
| `set-comment` | — | comment |
| `set-namespace` | — | new namespace URI |

Batching via `;;` where enumeration makes sense: `remove-property`, `remove-type`, `add-enum`, `add-import`.

```powershell
... -Operation add-property -Target "Платёж" -Value '<xs:element name="Комментарий" type="xs:string" minOccurs="0"/>'
... -Operation remove-property -Target "Платёж.Комментарий ;; Платёж.Черновик"
... -Operation add-enum -Target "ВидДокумента" -Value "Инкассо ;; Аккредитив"
```

Content is always described as an XML-schema fragment — the same language as in `xdto-compile`. There are no `-MinOccurs`-style parameters: to change a property, give its new declaration in full via `replace-property`. Length limits and other facets go into a nested type. Pass a multi-line fragment as a file (`-Value "@frag.xsd"`); inline is reliable only for single-line fragments without nested quotes.

### Addressing

Path is `Type.Property`; the dot is safe because both are 1C identifiers. The path continues into embedded types: `ПлатежныйДокумент.ДатаСписано.ИдПлатежа`. Before changing an existing type run `xdto-info -Mode used-by -Name <Type>` — it shows who will be affected.

`rename` changes the name in the metadata object, renames `<Name>.xml` and the `<Name>/` directory, and fixes the registration in `Configuration.xml`. `set-namespace` changes `targetNamespace`, all internal references to own types and `<Namespace>` of the metadata object — but packages **importing** the old namespace are deliberately left alone (for versioning they should keep pointing at the previous URI); the tool lists them so you can decide.

`xdto-validate` runs automatically after the edit unless `-NoValidate` is passed. Its non-zero exit — or a validator missing from the same `scripts` directory — is the exit code of `xdto-edit`; the edit itself is already written. `xdto-decompile` / `xdto-compile` must sit beside `xdto-edit`: without them structural operations are refused before any change.

---

## 4. Decompile — Export a Package to an XML Schema

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-xdto-manage/scripts/xdto-decompile.ps1 -PackagePath "<path>" -OutFile "<schema.xsd>"
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `PackagePath` | yes | Package directory, `Ext/Package.bin` or the `<Name>.xml` metadata object. Alias — `-Path` |
| `OutFile` | no | Write the schema to a file (UTF-8 with BOM). Without it — stdout |

`xdto-decompile` → edit XSD → `xdto-compile -Force` round-trips the package without loss, name / synonym / comment included (they travel in `xs:annotation/xs:appinfo`).

The same path produces a **versioned copy**: change `targetNamespace` in the schema and build it with a new `-Name`. When changing the namespace, fix the `xmlns` declaration carrying the same URI as well — internal references use it as a prefix. Do not blind-replace every occurrence of the URI string: an import whose namespace has the old URI as a prefix (`urn:пример:обмен` vs `urn:пример:обмен:legacy`) would be damaged.

The exported XSD can be handed to a counterparty as-is. It is better than the Designer's built-in "Export XML schema", which loses `nillable` on attribute-properties.

---

## 5. Validate — Check a Package

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-xdto-manage/scripts/xdto-validate.ps1 -PackagePath "<path>"
```

| Parameter | Required | Description |
|-----------|:--------:|-------------|
| `PackagePath` | yes | Package directory, `Ext/Package.bin` or `<Name>.xml`. Alias — `-Path` |
| `ConfigDir` | no | Sources root. By default derived from the package location |
| `Detailed` | no | Show passing checks too, not just problems |
| `MaxErrors` | no | Stop after N errors. Default 20 |
| `OutFile` | no | Write the report to a file |

`[ERROR]` — the platform will either reject the package or accept it incorrectly. `[WARN]` — the package works, but there is a risk worth knowing about. Exit code `1` on errors.

**Why run it if the package loads anyway:** the platform does not diagnose an unresolved type from a foreign namespace — it silently substitutes `xs:anyType`, the package looks loaded, and the defect only surfaces at runtime when `ФабрикаXDTO` returns a structureless value. That is visible statically, before loading into the base.

---

## Typical Workflows

**New package from a partner's XSD:**

1. `xdto-compile -XsdPath <file> -OutputDir <sources>` — and read the warnings
2. `xdto-validate <sources>/XDTOPackages/<Name>` — make sure types resolved
3. `db-load-xml` + `db-update` ([db-manage.md](db-manage.md))

**Change an existing package:**

1. `xdto-info <package>` — find the type
2. `xdto-info <package> -Mode used-by -Name <Type>` — see who is affected
3. `xdto-edit <package> -Operation <op> …` (auto-validates)
4. `db-load-xml` + `db-update`

**Write code that fills an XDTO object:**

1. `xdto-info src -Namespace "<URI>" -Name <Type> -Depth 2` — structure in 1C terms
2. `... -RequiredOnly` — the mandatory-only skeleton
3. Write the code against that, no `Package.bin` reading needed

An exchange format is an interface contract: when a package is added or changed under a tracked spec, the namespace, the package version and the counterparty belong in the integration spec (`content/rules/sdd-integrations.md`), not only in the sources.
