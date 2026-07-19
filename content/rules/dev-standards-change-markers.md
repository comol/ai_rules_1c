---
description: Modification markers and metadata naming — typical-code change banners, new-object placement comments, naming rules, and object-type selection
alwaysApply: false
category: development
---

# Development Standards — Change Markers and Metadata Naming

**When to load this file:** when modifying typical configuration code, emitting modification comments, naming or placing metadata objects / attributes / form elements / roles, or selecting a metadata object type.

Section numbers 3–4 are preserved from the former monolithic `dev-standards-core.md` for stable references.

## 3. Modification Comments

Modification markers are used **only when modifying typical (standard) code** in typical configuration modules **and only when both `COMPANY` and `DEVELOPER` are set in `.dev.env`**. If either parameter is empty — skip markers entirely (see `dev-standards-env.md §1 → "Advisory parameters"`); removed typical code is still commented out instead of deleted, but without the `// +++ … / // --- …` banners.

### Format
- Opening comment: value of `{COMMENT_OPEN}` from `.dev.env`
- Closing comment: value of `{COMMENT_CLOSE}` from `.dev.env`
- A space is mandatory after `//`

### Typical Code Modification
Removed typical code — **comment out, DO NOT delete**:

```bsl
// {COMMENT_OPEN}
НовоеЗначение = {PREFIX}ПреобразоватьЗначение(Значение1);
// ТиповаяПроцедура(Значение1, Значение2);
ТиповаяПроцедура(НовоеЗначение, Значение2);
// {COMMENT_CLOSE}
```

### New Procedures in Typical Modules
Comment is placed **inside** the procedure, after the header:

```bsl
Функция НоваяФункция(Параметр) Экспорт
	// {COMMENT_OPEN}
	// ... code ...
	Возврат Результат;
	// {COMMENT_CLOSE}
КонецФункции
```

### Entirely New (Non-Typical) Objects
In modules of new objects (with `{PREFIX}`) — markers per method are **NOT NEEDED**. Instead — **a single block at the module header** describing the object.

### General Rules
- `TODO` / `FIXME` must contain a task reference: `// TODO No.14752: description`
- **Pseudo-regions via comments are PROHIBITED** — use only `#Область` / `#КонецОбласти`

## 4. Metadata Naming

| Element | Rule |
|---|---|
| New metadata objects | Prefix `{PREFIX}` in name (e.g., `{PREFIX}ContractAmount`) |
| Object synonyms | No prefix. If conflicts — add `({COMPANY})` |
| New roles | Prefix `{PREFIX}` |
| Subsystems | `{PREFIX}AddedObjects` and `{PREFIX}ModifiedObjects` |
| Attributes of typical objects | Prefix `{PREFIX}` |
| Form elements on typical forms | Prefix `{PREFIX}` |

**When `PREFIX` is empty in `.dev.env`** — the placeholder `{PREFIX}` resolves to an empty string in every rule above (e.g. `{PREFIX}ContractAmount` → `ContractAmount`, `{PREFIX}AddedObjects` → `AddedObjects`). The `({COMPANY})` synonym disambiguator also disappears if `COMPANY` is empty. See `dev-standards-env.md §1 → "Advisory parameters"`.

**Inside non-typical (new) objects** (name already has `{PREFIX}`):
- Attributes, tabular sections, form elements, commands, procedures — **WITHOUT prefix**

- Place all new objects into subsystems
- Composite types used repeatedly — via `DefinedType`

### Object Type Selection

| Task | Object Type |
|---|---|
| Reference data | `Catalog` |
| Business transactions | `Document` |
| Quantity/amount accumulation | `AccumulationRegister` |
| Arbitrary data with dimensions | `InformationRegister` |
| User reports | `Report` (with DCS) |
| Data processing | `DataProcessor` |
| Fixed set of values | `Enum` |

