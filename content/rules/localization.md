---
description: "1C localization rules — NStr/НСтр, СтрШаблон, multilingual metadata synonyms/titles, DefaultLanguage vs LanguageCode vs LocaleCode, date/number formatting."
alwaysApply: false
category: development
---

# 1C Localization Rules

Load when authoring or reviewing user-facing strings, multilingual configurations, adding/auditing interface languages, or editing multilingual metadata (`Synonym`, `ToolTip`, `Title`, `ListPresentation`).

## Languages vs Script vs Locale

Never conflate these four properties:

- `Language.Name` — metadata object identifier (e.g. `Русский`); does not by itself prove `LanguageCode`.
- `LanguageCode` — ISO/platform code used in `НСтр` and XML `<v8:lang>` (e.g. `ru`, `en`).
- `Configuration.DefaultLanguage` — reference to the configuration's default `Language` object. Extensions have their own language list; external processors/reports inherit the host configuration's languages at runtime.
- `ScriptVariant` — BSL keyword language (`Русский`/`Английский`), independent of UI language.
- `LocaleCode` — regional formatting of dates, numbers, and Booleans, independent of `НСтр` text selection.

## `НСтр` / `NStr` and `СтрШаблон`

- Wrap all user-facing labels, messages, tooltips, command titles, and user-shown exceptions in `НСтр(...)` when the project supports or prepares for multiple languages.
- **Translate whole phrases with positional placeholders (`%1`, `%2`) and `СтрШаблон`:** never concatenate translated fragments (`НСтр("ru='Документ'") + " " + НСтр("ru='не найден'")`) — word order breaks across languages. Named placeholders like `%Name%` are not valid `СтрШаблон` syntax.
- **Multiline literal trap:** inside `НСтр("ru = '...'; |en = '...'" )`, place line breaks `|` *between* language entries, never inside a translated phrase unless a literal newline is intended in the UI.
- **Single quotes inside translations:** double single quotes (`''`) inside an `НСтр` entry.
- **Do not translate technical keys:** internal structure keys, JSON/XML protocol fields, metadata names, and algorithm keys must stay invariant; never branch business logic on a localized presentation string.
- **Event log (`ЖурналРегистрации`):** keep the event name (`ИмяСобытия`) in the configuration's default language so log filtering does not depend on the user's session language; user-facing comment text may be localized.

## Metadata Translations and Formatting

- **Preserve existing languages:** when editing `Synonym`, `ToolTip`, or form `Title` in XML / tools, preserve every existing `<v8:item>` language entry. Never overwrite a multilingual map with a single-language string unless explicitly asked to remove other languages.
- **Dates, numbers, Booleans:** prefer localized format specifiers (`ДЛФ=Д`, `ДЛФ=ДТ`) for UI presentation; avoid hardcoding `Л=`/`L=` unless required by a specific format contract. For data exchanges use standard XML/JSON serialization (`XMLСтрока` / `ЗаписьJSON`), never user-locale `Формат()`.
- **Review check:** adding `en` to one `НСтр` call does not prove full localization — verify placeholders, label length/wrapping, form titles, templates, and report variants, and report unverified areas explicitly.
