---
description: "Performant BSP RLS (ТаблицыЗначенийДоступа) — connecting custom or extension objects to access-group restrictions and diagnosing list/update failures."
alwaysApply: false
category: development
---

# Performant BSP RLS (Access Value Tables)

Load when connecting a new catalog, document, register, or **extension object** to BSP's performant record-level security (`ОграничениеДоступаНаУровнеЗаписей`, `ТаблицыЗначенийДоступа`), or when diagnosing dynamic-list / access-update failures under RLS. For programmatic profile creation and role assignment, see `standards(name="bsp-access-rights")`.

## Core Mechanics (Verify Exact Signatures via `ssl_search` / Project Code)

Performant BSP RLS precomputes effective access sets in information registers (`ЗначенияГруппДоступа*` / `ТаблицыГруппДоступа` / `КлючиДоступа*`) instead of evaluating heavy joins on every row read.

Before writing code, inspect how an already-connected object of the same kind in the project is wired (use `search_code` / `get_object_dossier`) and confirm BSP version handlers via `ssl_search`:

1. **Overridable / subscription registration:** register the object in the project's BSP access-control overridable module (typically `УправлениеДоступомПереопределяемый` → `ПриЗаполненииСписковОграниченийДоступа` / `ПриЗаполненииСписковНезависимыхОграниченийДоступа`, and access-kind mapping for its restricting fields such as `Организация`, `Подразделение`, `Партнер`, `Склад`).
2. **Role & restriction templates:** assign the role's read/write rights and attach the matching BSP RLS restriction template (`#ПоЗначениям(...)` / `#ДляОбъекта(...)` — exact template names from the project's `БазовыеПраваБСП` or sibling role) on every restricted right (`Чтение`, `Добавление`, `Изменение`, `Удаление`, `Проведение`).
3. **Registering access-key updates:** ensure `ПриЗаписи` / event subscriptions trigger access-key recalculation (`УправлениеДоступом.ЗаписатьКлючиДоступа*` or the project's subscription `ОбновитьКлючиДоступаОбъектов`) whenever a restricting attribute changes.
4. **Extension objects (`CFE`):**
   - Remember that BSP stores extension roles separately from base-configuration metadata IDs (`standards(name="bsp-access-rights")`).
   - Adopted roles or new extension roles must not drop existing base restrictions; verify whether the project's BSP version supports RLS templates on extension objects and check `УправлениеДоступом` hooks via `search_code`.

## Common Failures and Diagnostics

- **Dynamic list fails with RLS query error or missing field:** the list's custom query omits a field referenced by the RLS template (or uses a subquery/alias that breaks RLS injection), or the role lacks read access to the restricting reference catalog.
- **User sees zero rows (or all rows) after connecting an object:** access-key registers were not populated after metadata deployment — run the BSP access-rights update procedure / scheduled job (`ОбновлениеВспомогательныхДанных` / `ЗаполнитьТаблицыДоступа`) on the dev/test base, and verify the user's access group includes the required values.
- **Performance cliff on list open:** verify the object is using the performant key-table template (not a legacy unindexed subquery template) and that restricting fields are indexed.
- **Verification boundary:** a query or UI check under a full-rights / technical user (`ПолныеПрава`) **never** proves RLS works — test under a restricted user profile or record RLS runtime verification as unverified under **Risks**.
