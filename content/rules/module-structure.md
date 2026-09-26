---
description: Canonical region templates for common, object / manager and form modules — `#Область` names, preprocessor directives, mandatory regions. Load before creating a new module or restructuring an existing one.
alwaysApply: false
category: development
---

# Module Structure Templates

Canonical region names are **Russian, БСП-style**. English names (`Public` / `Internal` / `Private`) MUST NOT be used — except when the whole configuration is already maintained in English locale with regions defined uniformly across the codebase.

Index row for module-region policy — `coding-standards.md` (reached from `AGENTS.md → Coding Standards`).

## Common Module

```bsl
#Область ПрограммныйИнтерфейс

#КонецОбласти

#Область СлужебныйПрограммныйИнтерфейс

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

#КонецОбласти
```

- `ПрограммныйИнтерфейс` — public exported procedures and functions; what other modules of the configuration may call.
- `СлужебныйПрограммныйИнтерфейс` — exported procedures and functions intended only for the project's own modules (БСП convention: do not call from third-party code).
- `СлужебныеПроцедурыИФункции` — internal helpers, never `Экспорт`.

## Object / Manager Module

```bsl
#Если Сервер Или ТолстыйКлиентОбычноеПриложение Или ВнешнееСоединение Тогда

#Область ПрограммныйИнтерфейс

#КонецОбласти

#Область ОбработчикиСобытий

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

#КонецОбласти

#КонецЕсли
```

The outer `#Если Сервер Или ТолстыйКлиентОбычноеПриложение Или ВнешнееСоединение Тогда` preprocessor block is **mandatory** for object and manager modules.

## Form Module

```bsl
#Область ОбработчикиСобытийФормы

#КонецОбласти

#Область ОбработчикиСобытийЭлементовШапкиФормы

#КонецОбласти

#Область ОбработчикиСобытийЭлементовТаблицыФормыИмяТаблицы

#КонецОбласти

#Область ОбработчикиКомандФормы

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

#КонецОбласти
```

All 5 form-module regions are **mandatory**, even when empty. For every form tabular section create a separate region `ОбработчикиСобытийЭлементовТаблицыФормы<ИмяТаблицы>` (replace `<ИмяТаблицы>` with the actual tabular-section name).

## Global Rules

- Regions inside procedures / functions are **forbidden**.
- Pseudo-regions via comments are **forbidden** — use only `#Область` / `#КонецОбласти`.
- Do not rename, drop, or reorder the canonical regions; if a section is empty, leave it empty.
