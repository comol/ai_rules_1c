---
description: "1C configuration extension (CFE) patterns — interceptor types, ПродолжитьВызов rules, change markers, adopted-object constraints"
globs: ["**/Extensions/**/*.bsl", "**/Ext/**/*.bsl"]
alwaysApply: false
category: architecture
---

# 1C Extension Patterns (CFE)

BSL patterns for working with 1C configuration extensions.

Applies to: extension code (`**/Extensions/**/*.bsl` and similar).

Background reference: `dev-standards-architecture.md §2 "Extensions"` — modification priority, directives, placement rules. This file is the **practical** companion: interceptor types, `ПродолжитьВызов` semantics, markers, and adopted-object constraints.

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

- An adopted object (`ObjectBelonging=Adopted`) is a copy of metadata from the base configuration.
- You **cannot** delete existing attributes / tabular sections of an adopted object.
- You **can** add your own attributes / tabular sections (with `{PREFIX}` from `.dev.env`).
- Modules of adopted objects — interceptors only, no direct edits.
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
Процедура МоёРасш_ДополнительнаяПроверка()
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
