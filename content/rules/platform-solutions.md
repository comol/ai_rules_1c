---
description: Case book of common 1C platform pitfalls and proven fix templates
alwaysApply: false
category: quality
---

# Platform Cases & Fix Templates

Each case follows the schema: **problem → symptom → correct template → reference to ITS standard or short rationale**.

---

## 1. Checking values for emptiness

**Problem.** Wrong predicate causes false positives on empty references, uninitialized variables, and attributes with default values.

**Symptom.** Conditions like `Если Контрагент <> Неопределено` skip empty refs `Справочники.Контрагенты.ПустаяСсылка()`; `Если ЗначениеЗаполнено(Реквизит)` on a form may return `Истина` for a freshly initialized composite reference.

**Template.**

```bsl
// Universal "non-empty" check for any value type.
Если ЗначениеЗаполнено(Контрагент) Тогда
    // ...
КонецЕсли;
```

For form attributes with reference or composite types — first copy the value to a local variable and check that, to avoid repeated platform property access:

```bsl
ТекущийКонтрагент = Объект.Контрагент;

Если ЗначениеЗаполнено(ТекущийКонтрагент) Тогда
    // ...
КонецЕсли;
```

**Standard.** ITS: "Использование функции ЗначениеЗаполнено".

---

## 2. Long-running operations

**Problem.** Direct background-job calls bypassing the БСП "Long-running operations" subsystem leave the UI without progress, no cancel handling, and no result serialization.

**Symptom.** Hanging client, no progress indication, "Cancel" button does nothing, result is lost on network drops.

**Template.** Use `ДлительныеОперации.ВыполнитьФункцию` with the correct method-name format:

```bsl
// On the server.
Параметры = Новый Структура;
Параметры.Вставить("ДатаНачала", ДатаНачала);
Параметры.Вставить("ДатаОкончания", ДатаОкончания);

ДлительнаяОперация = ДлительныеОперации.ВыполнитьФункцию(
    ПараметрыВыполнения,
    "Отчеты.ПродажиПоПериоду.СформироватьДанныеНаСервере",
    Параметры);
```

- `ИмяВыполняемогоМетода` format: `ИмяОбщегоМодуля.ИмяФункции` or `Тип.ИмяОбъекта.ИмяМетода` (no `ОбщийМодуль.` prefix).
- On the client, hook `ДлительныеОперацииКлиент.ОжидатьЗавершение` to poll status.
- Do NOT pass into a background job a temporary-storage address bound to the form session — pass serializable parameters; if needed, place the result into temporary storage from inside the job.

**Standard.** БСП: "Long-running operations" subsystem.

---

## 3. Temporary storage: correct functions

**Problem.** Using `ВременноеХранилище` as if it were an object instead of platform-level global functions.

**Symptom.** Error: «Метод объекта не обнаружен (Поместить)».

**Template.**

```bsl
// Wrong
Адрес = ВременноеХранилище.Поместить(Данные, УникальныйИдентификатор);
Данные = ВременноеХранилище.Получить(Адрес);

// Correct - platform global functions
Адрес = ПоместитьВоВременноеХранилище(Данные, УникальныйИдентификатор);
Данные = ПолучитьИзВременногоХранилища(Адрес);
```

**Standard.** Platform syntax assistant.

---

## 4. Transactions in event handlers

**Problem.** Nested transactions in `ПередЗаписью` / `ПриЗаписи` of an object lead to a double `НачалоТранзакции` and unexpected rollback behavior.

**Symptom.** "Транзакция не активна" on rollback, partially saved data on inner errors, cross-session locks.

**Template.** In object-write event handlers **do not open your own transaction** — the platform has already opened one. If an outer transaction is required, open it in the calling code; inside the handler, use `ТранзакцияАктивна()` only for diagnostic checks if needed.

```bsl
// In the calling code that invokes Записать().
НачалоТранзакции();

Попытка
    Документ.Записать(РежимЗаписиДокумента.Проведение);
    ЗафиксироватьТранзакцию();
Исключение
    ОтменитьТранзакцию();
    ВызватьИсключение;
КонецПопытки;
```

**Standard.** ITS: "Использование транзакций".

---

## 5. Copying objects and tabular sections

**Problem.** Calling a non-existent or wrong method `Копия()` instead of `Скопировать()`.

**Symptom.** "Метод объекта не обнаружен", lost rows of tabular sections when manually copying via a loop.

**Template.**

```bsl
// Value table.
КопияТаблицы = ИсходнаяТаблица.Скопировать();

// Structure.
КопияСтруктуры = Новый Структура;
Для Каждого КлючИЗначение Из ИсходнаяСтруктура Цикл
    КопияСтруктуры.Вставить(КлючИЗначение.Ключ, КлючИЗначение.Значение);
КонецЦикла;

// Document as a brand new object.
НовыйДокумент = Документы.РеализацияТоваровУслуг.СоздатьДокумент();
ЗаполнитьЗначенияСвойств(НовыйДокумент, ИсходныйДокумент, , "Номер,Дата,ПометкаУдаления,Проведен");
НовыйДокумент.Товары.Загрузить(ИсходныйДокумент.Товары.Выгрузить());
```

**Note.** For documents, you must clear `Номер`, `Дата`, `ПометкаУдаления`, `Проведен` — otherwise the platform may try to overwrite the source.

---

## 6. Time on the server

**Problem.** Using `ТекущаяДата()` on the server gives different values across cluster nodes and ignores the session time zone.

**Symptom.** Documents with "future" or "past" dates when users work in different time zones; mismatched logs and postings.

**Template.**

```bsl
// On the server - do NOT use
Текущая = ТекущаяДата();

// On the server
Текущая = ТекущаяДатаСеанса();

// On the client - ТекущаяДата() is acceptable, but obtaining it from the server is preferred
```

**Standard.** ITS: "Использование функций для работы с датой и временем".

---

## 7. Searching in collections: choosing by complexity

**Problem.** Linear `Найти()` / `НайтиПоЗначению()` in large collections is O(n) per call; inside a loop you get O(n²).

**Template.**

- Up to ~100 elements — `Найти()` / `НайтиПоЗначению()` is acceptable.
- From ~1000 elements upwards or inside a loop — build an index on `Соответствие` (Map), lookup becomes O(1):

```bsl
ИндексПоИНН = Новый Соответствие;

Для Каждого Строка Из ТаблицаКонтрагентов Цикл
    ИндексПоИНН.Вставить(Строка.ИНН, Строка.Контрагент);
КонецЦикла;

// O(1) lookup in subsequent loops.
Контрагент = ИндексПоИНН.Получить(ИНН);
```

- For frequent multi-key lookups — use `ТаблицаЗначений.Индексы.Добавить("Поле1, Поле2")` + `НайтиСтроки(Структура)` for indexed linear search.

---

## 8. External components on the thin client

**Problem.** Synchronous attach of an external component blocks the UI and does not work in the web client.

**Template.** Use the asynchronous form via `НачатьПодключениеВнешнейКомпоненты` + `ОписаниеОповещения`:

```bsl
&НаКлиенте
Процедура ПодключитьСканер()
    Оповещение = Новый ОписаниеОповещения("ПослеПодключенияСканера", ЭтотОбъект);
    НачатьПодключениеВнешнейКомпоненты(Оповещение, "ОбщийМакет.СканерКомпонента", "Сканер", ТипВнешнейКомпоненты.Native);
КонецПроцедуры

&НаКлиенте
Процедура ПослеПодключенияСканера(Подключено, ДополнительныеПараметры) Экспорт

    Если Не Подключено Тогда
        ОбщегоНазначенияКлиент.СообщитьПользователю("Не удалось подключить сканер.");
        Возврат;
    КонецЕсли;

    // ...
КонецПроцедуры
```

**Standard.** ITS: "Внешние компоненты, асинхронный интерфейс".

---

## 9. Managed locks and deadlock prevention

**Problem.** Missing or incorrect managed locks cause read-write conflicts during posting; inconsistent lock ordering across documents leads to deadlocks.

**Symptom.** Sporadic «Конфликт блокировок при выполнении транзакции», deadlocks under load (especially in document posting), reading uncommitted data, balance inconsistencies after parallel posting.

**Template — set a managed lock before reading register balances during posting:**

```bsl
Процедура ОбработкаПроведения(Отказ, РежимПроведения)

    Блокировка = Новый БлокировкаДанных;

    ЭлементБлокировки = Блокировка.Добавить("РегистрНакопления.ТоварыНаСкладах");
    ЭлементБлокировки.Режим = РежимБлокировкиДанных.Исключительный;
    ЭлементБлокировки.ИсточникДанных = Товары;
    ЭлементБлокировки.ИспользоватьИзИсточникаДанных("Номенклатура", "Номенклатура");
    ЭлементБлокировки.ИспользоватьИзИсточникаДанных("Склад",       "Склад");

    Блокировка.Заблокировать();

    // ... read balances and write movements within the same transaction ...

КонецПроцедуры
```

**Rules.**

- Set the lock **before** reading the data you intend to modify; the lock lives until the end of the current transaction.
- Use `РежимБлокировкиДанных.Исключительный` for write paths, `Разделяемый` only for reads that must stay consistent.
- Always use `ИсточникДанных` (e.g. the document's tabular section) instead of iterating rows manually.
- **Lock ordering.** Establish a **canonical order of locked tables** across all postings (e.g. always lock `ТоварыНаСкладах` before `ТоварыКПередаче`). Violating the order across two documents that touch the same registers causes deadlocks.
- Lock the **register**, not the document — locking the document does not protect register reads.
- Do not call user dialogs, long-running operations, or external services while holding a transaction.
- Set the configuration property **«Режим управления блокировкой данных»** to `Управляемый` for the whole configuration; mixed mode hides bugs.
- For diagnosing — `ТранзакцияАктивна()` and reading the technological log section `TLOCK` / `TDEADLOCK`.

**Standard.** ITS: "Управление блокировкой данных в транзакции", "Особенности проведения документов".

---

## 10. Background jobs from an external data processor (БСП)

**Problem.** `ДлительныеОперации` runs server-side. If a data processor is opened via "File → Open" (i.e. as an external `*.epf`, not from the `ДополнительныеОтчетыИОбработки` catalog), БСП cannot find the processor on the server and `ВыполнитьВФоне` fails.

**Symptom.** "Метаданные не найдены" / "Не удалось получить обработку на сервере" when calling `ДлительныеОперации.ВыполнитьВФоне` from an external processor's form.

**Template — copy the processor binary to the server via temporary storage:**

```bsl
&НаКлиенте
Процедура ПриОткрытии(Отказ)
    Если ЭтоВнешняяОбработка() Тогда
        ОписаниеОповещения = Новый ОписаниеОповещения(
            "ОбработатьРезультатПомещенияФайлаОбработки", ЭтотОбъект);
        НачатьПомещениеФайлов(ОписаниеОповещения,
            ИмяФайлаОбработки(), Ложь, УникальныйИдентификатор);
    КонецЕсли;
КонецПроцедуры

&НаКлиенте
Процедура ОбработатьРезультатПомещенияФайлаОбработки(ПомещенныеФайлы, ОбработчикЗавершения) Экспорт
    Если ПомещенныеФайлы <> Неопределено Тогда
        ХранениеФайлаОбработки = КопияОбработкиНаСервере(ПомещенныеФайлы[0].Хранение);
    КонецЕсли;
КонецПроцедуры

&НаСервере
Функция КопияОбработкиНаСервере(Хранение)
    Результат = ПолучитьИмяВременногоФайла();
    ДвоичныеДанные = ПолучитьИзВременногоХранилища(Хранение);
    ДвоичныеДанные.Записать(Результат);
    Возврат Результат;
КонецФункции
```

**Template — start the background job:**

```bsl
&НаСервере
Функция НачатьВыполнениеФоновогоЗаданияНаСервере()
    ЭтоВнешняяОбработка = ЭтоВнешняяОбработка();
    Если ЭтоВнешняяОбработка Тогда
        ИмяОбработки = ХранениеФайлаОбработки;
    Иначе
        ИмяОбработки = РеквизитФормыВЗначение("Объект").Метаданные().ПолноеИмя();
    КонецЕсли;

    ПараметрыЗадания = Новый Структура;
    ПараметрыЗадания.Вставить("ИмяОбработки", ИмяОбработки);
    ПараметрыЗадания.Вставить("ИмяМетода", "<procedure name in the object module>");
    ПараметрыЗадания.Вставить("ПараметрыВыполнения", ПараметрыВыполненияОбработки);
    ПараметрыЗадания.Вставить("ЭтоВнешняяОбработка", ЭтоВнешняяОбработка);

    ПараметрыВыполнения = ДлительныеОперации.ПараметрыВыполненияВФоне(УникальныйИдентификатор);
    ПараметрыВыполнения.НаименованиеФоновогоЗадания = "<job description>";
    ПараметрыВыполнения.ЗапуститьВФоне = Истина;

    Возврат ДлительныеОперации.ВыполнитьВФоне(
        "ДлительныеОперации.ВыполнитьПроцедуруМодуляОбъектаОбработки",
        ПараметрыЗадания, ПараметрыВыполнения);
КонецФункции
```

**Bypassing safe mode in the background.** To disable the safe-mode permission check inside the background job, create a fresh instance of the processor without safe mode:

```bsl
Процедура ОбработкаДанныхВФоне(Параметры, АдресРезультата) Экспорт
    ЧастиИмени = СтрРазделить(ЭтотОбъект.Метаданные().ПолноеИмя(), ".");
    ЭтоВнешняяОбработка = (ВРег(ЧастиИмени[0]) = "ВНЕШНЯЯОБРАБОТКА");
    Если ЭтоВнешняяОбработка Тогда
        ОбработкаОбъект = ВнешниеОбработки.Создать(
            ЭтотОбъект.ИспользуемоеИмяФайла, Ложь,
            ОбщегоНазначения.ОписаниеЗащитыБезПредупреждений());
        Результат = ОбработкаОбъект.ОбработкаДанных(...);
    Иначе
        Результат = ОбработкаДанных(...);
    КонецЕсли;
    ПоместитьВоВременноеХранилище(Результат, АдресРезультата);
КонецПроцедуры
```

**Constraints.**

- The background procedure cannot use form attributes or processor tabular sections — pass everything via parameters.
- The server-side copy lives in a temp file — keep its path in a form attribute (`ХранениеФайлаОбработки`) until the long-running operation completes.

**Standard.** БСП "Длительные операции" subsystem; `ДлительныеОперации.ВыполнитьПроцедуруМодуляОбъектаОбработки` reference. Requires БСП 3.0+ and platform 8.3.13+.

---

## Extending the case book

When you discover a new typical pitfall:

1. Add a new section using the "Problem → Symptom → Template → Standard" schema.
2. If the solution depends on the platform or БСП version — state the version explicitly.
3. If a minimal reproducible example exists — include it.
4. When possible, link to ITS, the platform documentation, or a specific БСП module.
