---
description: 1C anti-patterns, performance guidelines, and code review scoring
alwaysApply: false
category: quality
---
# 1C Anti-Patterns and Performance Guidelines

> **Ownership.** This file owns the anti-pattern **catalog**: severity, detection hints, before/after fix templates. The normative query rules themselves (no queries in loops, parameterization, `КАК` aliases, virtual-table filters via parameters, intermediate result variable, `ВТ_*` naming, `ПЕРВЫЕ N`) are owned by `dev-standards-architecture.md §3 → "Queries"`; the dot-notation ban — by `dev-standards-architecture.md §4`. On conflict, the owner file wins — update rules there, update examples here.

## Critical Anti-Patterns (Must Fix)

### 1. Query in Loop

**Impact:** O(n) database calls → O(1)
**Severity:** CRITICAL

```bsl
// ❌ CRITICAL: N database calls
Для Каждого Строка Из Данные Цикл
    Запрос = Новый Запрос("ВЫБРАТЬ ... ГДЕ Ссылка = &Ссылка");
    Запрос.УстановитьПараметр("Ссылка", Строка.Ссылка);
    РезультатЗапроса = Запрос.Выполнить();
КонецЦикла;

// ✅ OPTIMIZED: 1 database call
Запрос = Новый Запрос;
Запрос.Текст =
"ВЫБРАТЬ ...
|ГДЕ
|   Ссылка В (&СписокСсылок)";
Запрос.УстановитьПараметр("СписокСсылок", 
    Данные.ВыгрузитьКолонку("Ссылка"));
РезультатЗапроса = Запрос.Выполнить();
```

### 2. Direct Attribute Access (Dot Notation)

**Impact:** Loads entire object from database
**Severity:** CRITICAL
**Note:** Project default is a hard ban outside trivial single-call handlers. **[Project rule — stricter than ITS standard]** — ITS allows occasional dot-notation in non-hot code; the project default is to use dedicated БСП methods regardless. See `dev-standards-architecture.md §4 → "Data Access — Reference Attribute Access"`.

```bsl
// ❌ CRITICAL: Full object load for each attribute
ИНН = Контрагент.ИНН;
КПП = Контрагент.КПП;
Наименование = Контрагент.Наименование;

// ✅ OPTIMIZED: Single targeted query via SSL
Реквизиты = ОбщегоНазначения.ЗначенияРеквизитовОбъекта(
    Контрагент, "ИНН, КПП, Наименование");
ИНН = Реквизиты.ИНН;
КПП = Реквизиты.КПП;
Наименование = Реквизиты.Наименование;
```

**SSL Methods Reference:** See `dev-standards-architecture.md §4 → "Data Access — Reference Attribute Access"`.

### 3. Subquery in SELECT

**Impact:** N+1 query execution
**Severity:** CRITICAL

```bsl
// ❌ CRITICAL: Subquery executed per row
"ВЫБРАТЬ
|   Заказы.Ссылка,
|   (ВЫБРАТЬ СУММА(Оплаты.Сумма) 
|    ИЗ Документ.Оплата КАК Оплаты 
|    ГДЕ Оплаты.Заказ = Заказы.Ссылка) КАК СуммаОплат
|ИЗ
|   Документ.Заказ КАК Заказы"

// ✅ OPTIMIZED: Single join with aggregation
"ВЫБРАТЬ
|   Заказы.Ссылка КАК Ссылка,
|   ЕСТЬNULL(Оплаты.СуммаОплат, 0) КАК СуммаОплат
|ИЗ
|   Документ.Заказ КАК Заказы
|       ЛЕВОЕ СОЕДИНЕНИЕ (
|           ВЫБРАТЬ
|               Оплаты.Заказ КАК Заказ,
|               СУММА(Оплаты.Сумма) КАК СуммаОплат
|           ИЗ
|               Документ.Оплата КАК Оплаты
|           СГРУППИРОВАТЬ ПО
|               Оплаты.Заказ) КАК Оплаты
|       ПО Заказы.Ссылка = Оплаты.Заказ"
```

## High Priority Anti-Patterns

### 4. Virtual Table Filter in WHERE

**Impact:** Full table scan instead of index usage
**Severity:** HIGH

```bsl
// ❌ HIGH: Filter after virtual table calculation
"ВЫБРАТЬ
|   Остатки.Номенклатура КАК Номенклатура,
|   Остатки.КоличествоОстаток КАК Остаток
|ИЗ
|   РегистрНакопления.ТоварыНаСкладах.Остатки() КАК Остатки
|ГДЕ
|   Остатки.Склад = &Склад"

// ✅ OPTIMIZED: Filter in virtual table parameters
"ВЫБРАТЬ
|   Остатки.Номенклатура КАК Номенклатура,
|   Остатки.КоличествоОстаток КАК Остаток
|ИЗ
|   РегистрНакопления.ТоварыНаСкладах.Остатки(, Склад = &Склад) КАК Остатки"
```

### 5. Missing ПЕРВЫЕ N

**Impact:** Loads all records when only subset needed
**Severity:** HIGH

```bsl
// ❌ HIGH: Loads all records
"ВЫБРАТЬ
|   Контрагенты.Ссылка КАК Ссылка
|ИЗ
|   Справочник.Контрагенты КАК Контрагенты"

// ✅ OPTIMIZED: Limit at query level
"ВЫБРАТЬ ПЕРВЫЕ 10
|   Контрагенты.Ссылка КАК Ссылка
|ИЗ
|   Справочник.Контрагенты КАК Контрагенты
|
|УПОРЯДОЧИТЬ ПО
|   Контрагенты.Наименование"
```

Always pair `ПЕРВЫЕ N` with `УПОРЯДОЧИТЬ ПО` — without an explicit ordering the returned subset is non-deterministic and may differ between runs and DBMS engines.

### 6. Excessive Client-Server Calls

**Impact:** Network overhead, context serialization
**Severity:** HIGH

```bsl
// ❌ HIGH: Multiple server calls
&НаКлиенте
Процедура Обработать(Команда)
    Данные1 = ПолучитьДанные1НаСервере();
    Данные2 = ПолучитьДанные2НаСервере();
    Данные3 = ПолучитьДанные3НаСервере();
КонецПроцедуры

// ✅ OPTIMIZED: Single server call
&НаКлиенте
Процедура Обработать(Команда)
    ВсеДанные = ПолучитьВсеДанныеНаСервере();
КонецПроцедуры

&НаСервереБезКонтекста
Функция ПолучитьВсеДанныеНаСервере()
    Результат = Новый Структура;
    Результат.Вставить("Данные1", ПолучитьДанные1());
    Результат.Вставить("Данные2", ПолучитьДанные2());
    Результат.Вставить("Данные3", ПолучитьДанные3());
    Возврат Результат;
КонецФункции
```

### 7. Using &НаСервере Instead of &НаСервереБезКонтекста

**Impact:** Unnecessary form context transfer
**Severity:** HIGH

```bsl
// ❌ HIGH: Transfers full form context
&НаСервере
Функция ПолучитьДанныеНаСервере()
    Возврат ВыполнитьЗапрос();
КонецФункции

// ✅ OPTIMIZED: No context transfer
&НаСервереБезКонтекста
Функция ПолучитьДанныеНаСервере(Параметры)
    Возврат ВыполнитьЗапрос(Параметры);
КонецФункции
```

### 7a. Using `Сообщить()` for User Notifications

**Impact:** Bypasses the platform's user-message subsystem; messages are not bound to form fields, are not collected by long-running operations, and behave inconsistently between thin / web / mobile clients.
**Severity:** HIGH
**Source rule:** `dev-standards-code-style.md → "Forbidden Calls and Constructs"` ("`Сообщить()` for user notifications is **PROHIBITED**").

```bsl
// ❌ HIGH: legacy global call, not bound to form fields, lost in long-running ops
Сообщить("Контрагент не указан");

// ✅ OPTIMIZED (server): proper user-message subsystem, can target a form field
Сообщение = Новый СообщениеПользователю;
Сообщение.Текст = НСтр("ru = 'Контрагент не указан'");
Сообщение.Поле = "Объект.Контрагент";
Сообщение.УстановитьДанные(ОбъектДляФормы);
Сообщение.Сообщить();

// ✅ OPTIMIZED (БСП wrappers — preferred when БСП is available)
ОбщегоНазначения.СообщитьПользователю(
    НСтр("ru = 'Контрагент не указан'"), , "Объект.Контрагент");
// On the client:
ОбщегоНазначенияКлиент.СообщитьПользователю(
    НСтр("ru = 'Контрагент не указан'"), , "Объект.Контрагент");
```

## Medium Priority Anti-Patterns

### 8. Missing Caching

**Impact:** Repeated expensive operations
**Severity:** MEDIUM

```bsl
// ❌ MEDIUM: Same calculation repeated
Для Каждого Строка Из ТаблицаДанных Цикл
    Курс = ПолучитьКурсВалюты(Строка.Валюта, Строка.Дата);
КонецЦикла;

// ✅ OPTIMIZED: Cache results
КэшКурсов = Новый Соответствие;

Для Каждого Строка Из ТаблицаДанных Цикл
    
    Ключ = Строка.Валюта + "|" + Формат(Строка.Дата, "ДФ=yyyyMMdd");
    Курс = КэшКурсов.Получить(Ключ);
    
    Если Курс = Неопределено Тогда
        Курс = ПолучитьКурсВалюты(Строка.Валюта, Строка.Дата);
        КэшКурсов.Вставить(Ключ, Курс);
    КонецЕсли;
    
КонецЦикла;
```

### 9. O(n²) Algorithm

**Impact:** Quadratic growth in comparisons and execution time as both collections grow
**Severity:** MEDIUM

```bsl
// ❌ MEDIUM: O(n²) nested loop search
Для Каждого Строка1 Из Таблица1 Цикл
    Для Каждого Строка2 Из Таблица2 Цикл
        Если Строка1.Ключ = Строка2.Ключ Тогда
            // Process match
        КонецЕсли;
    КонецЦикла;
КонецЦикла;

// ✅ OPTIMIZED: O(n) with Map lookup
ИндексТаблицы2 = Новый Соответствие;
Для Каждого Строка2 Из Таблица2 Цикл
    ИндексТаблицы2.Вставить(Строка2.Ключ, Строка2);
КонецЦикла;

Для Каждого Строка1 Из Таблица1 Цикл
    Строка2 = ИндексТаблицы2.Получить(Строка1.Ключ);
    Если Строка2 <> Неопределено Тогда
        // Process match
    КонецЕсли;
КонецЦикла;
```

### 10. Deep Nesting

**Impact:** Poor readability, hard to maintain
**Severity:** MEDIUM

```bsl
// ❌ MEDIUM: Deep nesting (>4 levels)
Если Условие1 Тогда
    Если Условие2 Тогда
        Если Условие3 Тогда
            Если Условие4 Тогда
                // Logic
            КонецЕсли;
        КонецЕсли;
    КонецЕсли;
КонецЕсли;

// ✅ OPTIMIZED: Early returns
Если НЕ Условие1 Тогда
    Возврат;
КонецЕсли;

Если НЕ Условие2 Тогда
    Возврат;
КонецЕсли;

Если НЕ Условие3 Тогда
    Возврат;
КонецЕсли;

Если НЕ Условие4 Тогда
    Возврат;
КонецЕсли;

// Logic
```

## Architectural Anti-Patterns

### Big Ball of Mud
- No clear structure
- Everything depends on everything
- **Impact**: Unmaintainable, high change risk

### God Module
- One module does everything
- Hundreds of procedures in single module
- **Impact**: Hard to understand, test, modify

### Tight Coupling
- Modules directly dependent on implementation details
- Changes cascade across modules
- **Impact**: High modification cost

### Copy-Paste Architecture
- Same code in multiple places
- No shared modules
- **Impact**: Inconsistency, maintenance burden

### Premature Optimization
- Complex caching before proving need
- Over-engineered for current scale
- **Impact**: Unnecessary complexity

## Optimized Patterns

### Batch Query with Temp Table

```bsl
МенеджерВТ = Новый МенеджерВременныхТаблиц;

Запрос = Новый Запрос;
Запрос.МенеджерВременныхТаблиц = МенеджерВТ;

// Step 1: Create temp table with input data
Запрос.Текст =
"ВЫБРАТЬ
|   Данные.Номенклатура КАК Номенклатура,
|   Данные.Склад КАК Склад
|ПОМЕСТИТЬ ВТ_Входные
|ИЗ
|   &ТаблицаДанных КАК Данные";
Запрос.УстановитьПараметр("ТаблицаДанных", ТаблицаДанных);
Запрос.Выполнить();

// Step 2: Join with register for batch result
Запрос.Текст =
"ВЫБРАТЬ
|   ВТ_Входные.Номенклатура КАК Номенклатура,
|   ВТ_Входные.Склад КАК Склад,
|   ЕСТЬNULL(Остатки.КоличествоОстаток, 0) КАК Остаток
|ИЗ
|   ВТ_Входные КАК ВТ_Входные
|       ЛЕВОЕ СОЕДИНЕНИЕ РегистрНакопления.ТоварыНаСкладах.Остатки(
|           ,
|           (Номенклатура, Склад) В
|               (ВЫБРАТЬ ВТ.Номенклатура, ВТ.Склад ИЗ ВТ_Входные КАК ВТ)
|       ) КАК Остатки
|       ПО ВТ_Входные.Номенклатура = Остатки.Номенклатура
|           И ВТ_Входные.Склад = Остатки.Склад";
РезультатЗапроса = Запрос.Выполнить();
```

### Bulk SSL Attribute Access

```bsl
// Instead of individual calls in loop
СписокКонтрагентов = ТаблицаДанных.ВыгрузитьКолонку("Контрагент");

// Get all attributes in single call
ТаблицаРеквизитов = ОбщегоНазначения.ЗначенияРеквизитовОбъектов(
    СписокКонтрагентов, "ИНН, КПП, Наименование");

// Build lookup map
СоответствиеРеквизитов = Новый Соответствие;
Для Каждого СтрокаРеквизитов Из ТаблицаРеквизитов Цикл
    СоответствиеРеквизитов.Вставить(
        СтрокаРеквизитов.Ссылка, СтрокаРеквизитов);
КонецЦикла;
```

## Confidence Scoring (for Reviews)

Rate findings on a scale from 0 to 100:

| Score | Description |
|-------|-------------|
| **0-25** | Low confidence — might be false positive |
| **26-50** | Moderate — worth discussing |
| **51-75** | High — likely real issue |
| **76-100** | Very high — confirmed issue with evidence |

**Report only findings with confidence ≥ 75 for code review, ≥ 50 for architecture review.**

## Quick Reference Checklist

| Anti-Pattern | Severity | Check For |
|--------------|----------|-----------|
| Query in loop | CRITICAL | `Для Каждого` followed by `Новый Запрос` |
| Dot notation | CRITICAL | `.Реквизит` on references |
| Subquery in SELECT | CRITICAL | Nested `ВЫБРАТЬ` in field list |
| Virtual table WHERE | HIGH | Conditions on virtual table results |
| Missing TOP N | HIGH | Large queries without `ПЕРВЫЕ` |
| Multiple server calls | HIGH | Sequential `НаСервере` calls from client |
| &НаСервере misuse | HIGH | Server call not needing form context |
| `Сообщить()` for notifications | HIGH | Direct `Сообщить("...")` instead of `СообщениеПользователю` / `ОбщегоНазначения.СообщитьПользователю` |
| Missing cache | MEDIUM | Repeated expensive calls with same params |
| O(n²) loops | MEDIUM | Nested loops searching for matches |
| Deep nesting | MEDIUM | >4 levels of conditionals/loops |
