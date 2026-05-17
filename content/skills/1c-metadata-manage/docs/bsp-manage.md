# 1C BSP Manage — Registration, Commands

BSP/SSL integration: add registration function (ExternalDataProcessorInfo) and manage commands for external data processors.

---

## 1. Registration — Add BSP Registration Function

Adds the `СведенияОВнешнейОбработке()` function to the object module, required for registering external data processors/reports in the SSL "Additional Reports and Data Processors" subsystem.

### Usage

```
1c-bsp-registration <ProcessorName> <Kind> [TargetObjects...]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ProcessorName | yes | — | Processor name (must be created via `1c-epf-scaffold`) |
| Kind | yes | — | Processor kind (see mapping below) |
| TargetObjects | * | — | Metadata objects for assignable kinds |
| SrcDir | no | `src` | Source directory |

\* TargetObjects is required for assignable kinds: ObjectFilling, Report, PrintForm, RelatedObjectCreation.

### Kind Mapping

User may specify kind in free form. Determine the correct one from context:

| User Input | Kind | API Method |
|------------|------|------------|
| additional processor, global | AdditionalDataProcessor | `ВидОбработкиДополнительнаяОбработка()` |
| additional report, global report | AdditionalReport | `ВидОбработкиДополнительныйОтчет()` |
| filling, fill | ObjectFilling | `ВидОбработкиЗаполнениеОбъекта()` |
| report (assignable, for object) | Report | `ВидОбработкиОтчет()` |
| print form, printing | PrintForm | `ВидОбработкиПечатнаяФорма()` |
| related object creation | RelatedObjectCreation | `ВидОбработкиСозданиеСвязанныхОбъектов()` |

### Default Command Type by Kind

| Kind | Default Command Type |
|------|---------------------|
| AdditionalDataProcessor | `ТипКомандыОткрытиеФормы()` |
| AdditionalReport | `ТипКомандыОткрытиеФормы()` |
| ObjectFilling | `ТипКомандыВызовСерверногоМетода()` |
| Report | `ТипКомандыОткрытиеФормы()` |
| PrintForm | `ТипКомандыВызовСерверногоМетода()` |
| RelatedObjectCreation | `ТипКомандыВызовСерверногоМетода()` |

### Template: СведенияОВнешнейОбработке

Base template — same for all kinds, only API method calls and conditional sections differ.

```bsl
Функция СведенияОВнешнейОбработке() Экспорт

	МетаданныеОбработки = Метаданные();

	ПараметрыРегистрации = ДополнительныеОтчетыИОбработки.СведенияОВнешнейОбработке("2.2.2.1");
	ПараметрыРегистрации.Вид     = ДополнительныеОтчетыИОбработкиКлиентСервер.{{ProcessorKind}};
	ПараметрыРегистрации.Версия  = "1.0";

	{{TARGET_SECTION}}

	НоваяКоманда = ПараметрыРегистрации.Команды.Добавить();
	НоваяКоманда.Представление      = МетаданныеОбработки.Представление();
	НоваяКоманда.Идентификатор      = МетаданныеОбработки.Имя;
	НоваяКоманда.Использование      = ДополнительныеОтчетыИОбработкиКлиентСервер.{{CommandType}};
	НоваяКоманда.ПоказыватьОповещение = Ложь;
	{{MODIFIER_SECTION}}

	Возврат ПараметрыРегистрации;

КонецФункции
```

### Substitutions

- `{{ProcessorKind}}` — API method from kind mapping table
- `{{CommandType}}` — API method from default command type table

### Conditional Sections

**`{{TARGET_SECTION}}`** — only for assignable kinds (ObjectFilling, Report, PrintForm, RelatedObjectCreation). One line per object:

```bsl
	ПараметрыРегистрации.Назначение.Добавить("Document.SalesInvoice");
```

Object name format: `MetadataClassName.ObjectName` (e.g., `Document.SalesInvoice`, `Catalog.Contractors`).

For global kinds (AdditionalDataProcessor, AdditionalReport) — remove section with empty line.

**`{{MODIFIER_SECTION}}`** — only for PrintForm:

```bsl
	НоваяКоманда.Модификатор = "PrintMXL";
```

For other kinds — remove with empty line.

### Server Handler Templates

For kinds with `ТипКомандыВызовСерверногоМетода` command type, add the corresponding handler procedure in the same `ПрограммныйИнтерфейс` region, after `СведенияОВнешнейОбработке`.

#### For ObjectFilling / RelatedObjectCreation

```bsl
Процедура ВыполнитьКоманду(ИдентификаторКоманды, ОбъектыНазначения, ПараметрыВыполненияКоманды) Экспорт

	// Прикладная логика команды.

КонецПроцедуры
```

#### For PrintForm

```bsl
Процедура Печать(МассивОбъектов, КоллекцияПечатныхФорм, ОбъектыПечати, ПараметрыВывода) Экспорт

	// Прикладная логика печати.

КонецПроцедуры
```

#### For AdditionalDataProcessor / AdditionalReport (with ServerMethodCall)

If user explicitly chose server method instead of opening form:

```bsl
Процедура ВыполнитьКоманду(ИдентификаторКоманды, ПараметрыВыполненияКоманды) Экспорт

	// Прикладная логика команды.

КонецПроцедуры
```

Note: global processors do not have the `ОбъектыНазначения` parameter.

### Instructions

1. Find `ObjectModule.bsl` via Glob: `src/{{ProcessorName}}/Ext/ObjectModule.bsl`
2. Read the file
3. If `СведенияОВнешнейОбработке` already exists — inform user, do not duplicate
4. If file not found — suggest using `1c-epf-scaffold` skill first
5. Find the region `#Область ПрограммныйИнтерфейс` ... `#КонецОбласти`
6. Insert `СведенияОВнешнейОбработке()` function inside this region
7. If kind requires server handler — insert it too, after the function
8. Use tabs for indentation (match existing file style)

### Example

User: "Register MyProcessor as a print form for Document.SalesInvoice"

Result in `ObjectModule.bsl`:

```bsl
#Область ОписаниеПеременных

#КонецОбласти

#Область ПрограммныйИнтерфейс

Функция СведенияОВнешнейОбработке() Экспорт

	МетаданныеОбработки = Метаданные();

	ПараметрыРегистрации = ДополнительныеОтчетыИОбработки.СведенияОВнешнейОбработке("2.2.2.1");
	ПараметрыРегистрации.Вид     = ДополнительныеОтчетыИОбработкиКлиентСервер.ВидОбработкиПечатнаяФорма();
	ПараметрыРегистрации.Версия  = "1.0";

	ПараметрыРегистрации.Назначение.Добавить("Document.SalesInvoice");

	НоваяКоманда = ПараметрыРегистрации.Команды.Добавить();
	НоваяКоманда.Представление      = МетаданныеОбработки.Представление();
	НоваяКоманда.Идентификатор      = МетаданныеОбработки.Имя;
	НоваяКоманда.Использование      = ДополнительныеОтчетыИОбработкиКлиентСервер.ТипКомандыВызовСерверногоМетода();
	НоваяКоманда.ПоказыватьОповещение = Ложь;
	НоваяКоманда.Модификатор = "PrintMXL";

	Возврат ПараметрыРегистрации;

КонецФункции

Процедура Печать(МассивОбъектов, КоллекцияПечатныхФорм, ОбъектыПечати, ПараметрыВывода) Экспорт

	// Прикладная логика печати.

КонецПроцедуры

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

#КонецОбласти
```

### Next Steps

- Add more commands: `1c-bsp-command` skill
- Add a form: `1c-form-scaffold` skill
- Add a template: `1c-template-manage` skill
- Build EPF: `1c-epf-build` skill

---

## 2. Command — Add Command to Registered Processor

Adds a command to an existing `СведенияОВнешнейОбработке()` function and generates the corresponding handler.

The data processor must be initialized with BSP registration first (see `1c-bsp-registration` skill).

### Usage

```
1c-bsp-command <ProcessorName> <Identifier> [CommandType] [Presentation]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ProcessorName | yes | — | Processor name |
| Identifier | yes | — | Internal command name (Latin characters) |
| CommandType | no | from processor kind | Command launch type (see mapping below) |
| Presentation | no | = Identifier | Display name for the user |
| SrcDir | no | `src` | Source directory |

### Command Type Mapping

User may specify type in free form:

| User Input | Command Type |
|------------|-------------|
| open form, form | `ТипКомандыОткрытиеФормы()` |
| client method, on client | `ТипКомандыВызовКлиентскогоМетода()` |
| server method, on server | `ТипКомандыВызовСерверногоМетода()` |
| form filling, fill form | `ТипКомандыЗаполнениеФормы()` |
| scenario, safe mode | `ТипКомандыСценарийВБезопасномРежиме()` |

If user does not specify — determine from processor kind in existing `СведенияОВнешнейОбработке()` code:

| Processor Kind (from code) | Default Command Type |
|---------------------------|---------------------|
| AdditionalDataProcessor | `ТипКомандыОткрытиеФормы()` |
| AdditionalReport | `ТипКомандыОткрытиеФормы()` |
| ObjectFilling | `ТипКомандыВызовСерверногоМетода()` |
| Report | `ТипКомандыОткрытиеФормы()` |
| PrintForm | `ТипКомандыВызовСерверногоМетода()` |
| RelatedObjectCreation | `ТипКомандыВызовСерверногоМетода()` |

### Command Addition Template

Insert in `СведенияОВнешнейОбработке()` **before** the `Возврат ПараметрыРегистрации` line:

```bsl
	НоваяКоманда = ПараметрыРегистрации.Команды.Добавить();
	НоваяКоманда.Представление      = НСтр("ru = '{{Presentation}}'");
	НоваяКоманда.Идентификатор      = "{{Identifier}}";
	НоваяКоманда.Использование      = ДополнительныеОтчетыИОбработкиКлиентСервер.{{CommandType}};
	НоваяКоманда.ПоказыватьОповещение = Ложь;
```

For print forms (ВидОбработкиПечатнаяФорма) also add:

```bsl
	НоваяКоманда.Модификатор = "PrintMXL";
```

Note: unlike the first command (from `1c-bsp-registration`), additional commands use string literals `НСтр("ru = '...'")` for presentation and a string for ID, not `Метаданные()`.

### Handler Templates

#### ServerMethodCall — handler already exists

If `ВыполнитьКоманду` procedure already exists in the object module, add a branch before `КонецЕсли`:

```bsl
	ИначеЕсли ИдентификаторКоманды = "{{Identifier}}" Тогда
		// Прикладная логика команды {{Identifier}}.
```

#### ServerMethodCall — no handler yet

For global processors (without `ОбъектыНазначения`):

```bsl
Процедура ВыполнитьКоманду(ИдентификаторКоманды, ПараметрыВыполненияКоманды) Экспорт

	Если ИдентификаторКоманды = "{{Identifier}}" Тогда
		// Прикладная логика команды {{Identifier}}.
	КонецЕсли;

КонецПроцедуры
```

For assignable processors (with `ОбъектыНазначения`):

```bsl
Процедура ВыполнитьКоманду(ИдентификаторКоманды, ОбъектыНазначения, ПараметрыВыполненияКоманды) Экспорт

	Если ИдентификаторКоманды = "{{Identifier}}" Тогда
		// Прикладная логика команды {{Identifier}}.
	КонецЕсли;

КонецПроцедуры
```

#### PrintForm — `Печать` procedure already exists

Add block before `КонецПроцедуры`:

```bsl
	ПечатнаяФорма = УправлениеПечатью.СведенияОПечатнойФорме(КоллекцияПечатныхФорм, "{{Identifier}}");
	Если ПечатнаяФорма <> Неопределено Тогда
		ПечатнаяФорма.ТабличныйДокумент = Сформировать{{Identifier}}(МассивОбъектов, ОбъектыПечати);
		ПечатнаяФорма.СинонимМакета = НСтр("ru = '{{Presentation}}'");
	КонецЕсли;
```

#### PrintForm — no `Печать` procedure yet

```bsl
Процедура Печать(МассивОбъектов, КоллекцияПечатныхФорм, ОбъектыПечати, ПараметрыВывода) Экспорт

	ПечатнаяФорма = УправлениеПечатью.СведенияОПечатнойФорме(КоллекцияПечатныхФорм, "{{Identifier}}");
	Если ПечатнаяФорма <> Неопределено Тогда
		ПечатнаяФорма.ТабличныйДокумент = Сформировать{{Identifier}}(МассивОбъектов, ОбъектыПечати);
		ПечатнаяФорма.СинонимМакета = НСтр("ru = '{{Presentation}}'");
	КонецЕсли;

КонецПроцедуры
```

#### ClientMethodCall

Added to **form module** (`Forms/<FormName>/Ext/Form/Module.bsl`):

For global processors:

```bsl
&НаКлиенте
Процедура ВыполнитьКоманду(ИдентификаторКоманды) Экспорт

	Если ИдентификаторКоманды = "{{Identifier}}" Тогда
		// Клиентская логика команды {{Identifier}}.
	КонецЕсли;

КонецПроцедуры
```

For assignable processors:

```bsl
&НаКлиенте
Процедура ВыполнитьКоманду(ИдентификаторКоманды, МассивЦелевыхОбъектов) Экспорт

	Если ИдентификаторКоманды = "{{Identifier}}" Тогда
		// Клиентская логика команды {{Identifier}}.
	КонецЕсли;

КонецПроцедуры
```

If procedure already exists — add `ИначеЕсли` branch.

### Instructions

1. Find and read `ObjectModule.bsl` via Glob: `src/{{ProcessorName}}/Ext/ObjectModule.bsl`
2. Ensure `СведенияОВнешнейОбработке()` exists. If not — suggest using `1c-bsp-registration` skill first
3. Determine processor kind from existing code (find the line with `ВидОбработки...()`)
4. Insert command block **before** `Возврат ПараметрыРегистрации`
5. Add handler:
   - For server handlers — in `ObjectModule.bsl`, `ПрограммныйИнтерфейс` region
   - For client handlers — in form module (find via Glob: `src/{{ProcessorName}}/Forms/*/Ext/Form/Module.bsl`)
6. If handler (`ВыполнитьКоманду` / `Печать`) already exists — add branch, do not duplicate the procedure
7. Use tabs for indentation

---

## Typical Workflow

1. Create processor: `1c-epf-scaffold <Name>`
2. Register with BSP: `1c-bsp-registration <Name> <Kind> [TargetObjects]`
3. Add commands: `1c-bsp-command <Name> <Identifier> [CommandType]`
4. Add form/template as needed
5. Build: `1c-epf-build`

---

## Recent Additions (upstream `w-2026-05-17`)

The upstream `cc-1c-skills` skills `epf-bsp-init` and `epf-bsp-add-command` are no-script (the agent does the work directly via Read / Edit / Glob / Grep). Their content is already covered by Sections 1–2 of this document, in English. Cross-checked against upstream `w-2026-05-17`:

- Kind mapping (six kinds: `ДополнительнаяОбработка`, `ДополнительныйОтчет`, `ЗаполнениеОбъекта`, `Отчет`, `ПечатнаяФорма`, `СозданиеСвязанныхОбъектов`) — aligned.
- Default command type per kind — aligned.
- Free-form command types (open form, client method, server method, form filling, safe-mode script) — aligned.
- `СведенияОВнешнейОбработке` skeleton, `Назначение` section for assignable kinds, `Модификатор` for `ПечатнаяФорма` — aligned.
- Server handlers (`ВыполнитьКоманду` for `ЗаполнениеОбъекта` / `СозданиеСвязанныхОбъектов` / global processors, `Печать` for `ПечатнаяФорма`) — aligned.

No script files were brought into `tools/` — the operations are pure module-text edits performed by the agent, which is how upstream ships them as well.

## MCP Integration

- **ssl_search** — Find SSL module methods for BSP registration and verify correct API method names.
- **metadatasearch** — Verify target metadata object names.
- **get_metadata_details** — Get full structure of target objects for registration.
- **codesearch** — Find existing handler patterns in the codebase.

## SDD Integration

When registering processors with BSP as part of a feature, update SDD artifacts if present (see `content/rules/sdd-integrations.md` for detection):

- **OpenSpec**: Document BSP registration details and command placement in spec deltas under `openspec/changes/<change-id>/specs/`.
