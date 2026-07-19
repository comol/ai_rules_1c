---
description: 1C configuration extension (CFE) patterns — interceptor types (`&Перед` / `&После` / `&ИзменениеИКонтроль`), `ПродолжитьВызов` rules, change markers, adopted-object constraints. Load when writing or reviewing extension code.
alwaysApply: false
category: architecture
---

# 1C Extension Patterns (CFE)

BSL patterns for working with 1C configuration extensions.

Applies to: extension code (`**/Extensions/**/*.bsl` and similar).

Background reference: `dev-standards-architecture.md §2` (Extensions) — modification priority, directives, placement rules. This file is the **practical** companion: interceptor types, `ПродолжитьВызов` semantics, markers, and adopted-object constraints.

> **Naming convention used in examples.** Below, `Расш1_` / `МоеРасш_` denotes the **extension's own short alias** (set in the extension's properties — typically the `Имя` of the extension or an explicit alias), **not** `{PREFIX}` from `.dev.env`. `{PREFIX}` applies to new metadata objects and attributes; the extension alias applies to procedure / function names introduced by the extension and prevents name collisions between extensions. The two are independent: an extension can both add a new attribute `{PREFIX}Признак` to a typical object and define an interceptor procedure `Расш1_ПриЗаписи` in the same module.
>
> The alias itself MUST NOT contain the letter «ё» — see `dev-standards-code-style.md → Typography`. Use `МоеРасш_`, `Расш1_`, `MyExt_` or any «ё»-free form.

---

## Interceptor types

| Directive | Type | When to use |
|-----------|------|-------------|
| `&Перед("ИмяМетода")` | Before | Code before the original method |
| `&После("ИмяМетода")` | After | Code after the original method |
| `&ИзменениеИКонтроль("ИмяМетода")` | ModificationAndControl | Full replacement of the method body |

### Before / After — simple interceptors

```bsl
&НаСервере
&Перед("ПриЗаписи")
Процедура Расш1_ПриЗаписи()
    // Runs BEFORE the original ПриЗаписи
КонецПроцедуры

&НаСервере
&После("ПриЗаписи")
Процедура Расш1_ПослеЗаписи()
    // Runs AFTER the original ПриЗаписи
КонецПроцедуры
```

### ИзменениеИКонтроль — full replacement

```bsl
&НаСервере
&ИзменениеИКонтроль("ОбработкаЗаполнения")
Процедура Расш1_ОбработкаЗаполнения(ДанныеЗаполнения, СтандартнаяОбработка)
    #Удаление
    // Original code (deleted)
    #КонецУдаления

    #Вставка
    // New code (inserted)
    #КонецВставки

    ПродолжитьВызов();
КонецПроцедуры
```

---

## ПродолжитьВызов() rules

- `&Перед` — `ПродолжитьВызов()` is invoked automatically afterwards. **Do not call manually.**
- `&После` — the original has already executed; `ПродолжитьВызов()` is not used.
- `&ИзменениеИКонтроль` — `ПродолжитьВызов()` is **mandatory** for the original to run. Without it, the original method does **not** execute.

---

## Change markers

Markers are **required** inside `&ИзменениеИКонтроль` to track changes:

| Marker | Purpose |
|--------|---------|
| `#Вставка` / `#КонецВставки` | New code added by the extension |
| `#Удаление` / `#КонецУдаления` | Original code that was replaced |

Markers preserve diff/merge semantics when the base configuration is updated and the extension needs to be re-borrowed.

---

## Constraints on adopted (borrowed) objects

- An adopted object (`ObjectBelonging=Adopted`) is **not a copy** — it is a reference to a base-configuration object brought into the extension's scope so that the extension can attach interceptors and add its own attributes / tabular sections / form elements. The original definition still lives in the base configuration; on a base-configuration update the adopted object is automatically re-read, and the extension is re-applied on top of it.
- You **cannot** delete existing attributes / tabular sections of an adopted object — they belong to the base configuration.
- You **can** add your own attributes / tabular sections (with `{PREFIX}` from `.dev.env`).
- Modules of adopted objects — interceptors only (`&Перед` / `&После` / `&ИзменениеИКонтроль`), no direct edits to the original procedure body.
- Forms of adopted objects — you can add elements, you cannot delete existing ones.

---

## Anti-patterns

### Direct edit of an adopted module

```bsl
// WRONG: editing original code in place
Процедура ПриЗаписи()
    // changed code...
КонецПроцедуры

// RIGHT: interceptor
&Перед("ПриЗаписи")
Процедура Расш1_ПриЗаписи()
    // additional code
КонецПроцедуры
```

### Forgotten ПродолжитьВызов

```bsl
// DANGEROUS: original method will not execute!
&ИзменениеИКонтроль("ОбработкаПроведения")
Процедура Расш1_ОбработкаПроведения(Отказ)
    // own code...
    // FORGOT: ПродолжитьВызов();
КонецПроцедуры
```

### No prefix in extension method names

```bsl
// Bad: name conflict with other extensions
Процедура ДополнительнаяПроверка()

// Good: extension prefix
Процедура МоеРасш_ДополнительнаяПроверка()
```

---

## Extension purpose tag

Set the `Purpose` (Назначение) of the extension in its properties:

| Type | Purpose | When to use |
|------|---------|-------------|
| Patch | `Patch` | Minimal changes, interceptors only |
| Customization | `Customization` | Attributes, forms, modules |
| AddOn | `AddOn` | Full new functionality |

The `Purpose` value affects update behaviour and the way the platform reapplies the extension after a base-configuration update.
