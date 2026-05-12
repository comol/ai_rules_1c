---
description: "1C asynchronous methods (Асинх / Ждать / Обещание) — patterns and pitfalls for platform 8.3.18+"
globs: ["**/*.bsl", "**/*.os"]
alwaysApply: false
category: forms
---

# Asynchronous Methods in 1C (Асинх / Ждать / Обещание)

Rules for using the asynchronous mechanism introduced in platform 8.3.18+.

Applies to: client-side code with asynchronous calls (`&НаКлиенте`).

Authoritative reference: dev-standards-architecture.md §3 — Async and Modality. This file gives the practical patterns and the pitfalls.

---

## Core principles

1. Every new async function (suffix `Асинх`) returns an `Обещание` (Promise) object.
2. `Ждать` is the wait operator. Code after `Ждать` does not execute until the promise resolves.
3. `*Асинх` methods can be called **only inside** procedures / functions declared with the `Асинх` keyword.
4. `Обещание` has three states: **Ожидание**, **Успех**, **Провал**.
5. The mechanism works **only on the client** (`&НаКлиенте`).

---

## Old vs new method correspondence

Prefer the new `*Асинх` syntax over `Показать*` with `ОписаниеОповещения`:

| Modal (forbidden) | Callback-based | New Асинх |
|---|---|---|
| `Предупреждение()` | `ПоказатьПредупреждение()` | `ПредупреждениеАсинх()` |
| `Вопрос()` | `ПоказатьВопрос()` | `ВопросАсинх()` |
| `ОткрытьЗначение()` | `ПоказатьЗначение()` | `ОткрытьЗначениеАсинх()` |
| `ВвестиЧисло()` | `ПоказатьВводЧисла()` | `ВвестиЧислоАсинх()` |
| `НайтиФайлы()` | `НачатьПоискФайлов()` | `НайтиФайлыАсинх()` |
| `ПоместитьФайлы()` | `НачатьПомещениеФайлов()` | `ПоместитьФайлыНаСерверАсинх()` |

---

## Return values (result of `Ждать`)

| Method | Result of `Ждать Обещание` |
|---|---|
| `ПредупреждениеАсинх` | `Неопределено` |
| `ВопросАсинх` | `КодВозвратаДиалога` |
| `ОткрытьЗначениеАсинх` | `Неопределено` |
| `ВвестиЧислоАсинх` | `Число` |
| `НайтиФайлыАсинх` | `Массив` of `Файл` objects |
| `ПоместитьФайлыНаСерверАсинх` | `Массив` of `ОписаниеПомещенногоФайла` (success) / `Неопределено` (failure) |

---

## Basic template

```bsl
&НаКлиенте
Асинх Процедура МояПроцедура()

    Обещание = ВопросАсинх("Продолжить?", РежимДиалогаВопрос.ДаНет);
    Результат = Ждать Обещание;

    Если Результат = КодВозвратаДиалога.Да Тогда
        // Action
    КонецЕсли;

КонецПроцедуры
```

---

## Critical rules

### 1. Without `Ждать`, exceptions are silently lost

If you call an async function without `Ждать` and an exception occurs inside, it is **swallowed without trace**. Code continues as if nothing happened.

```bsl
// DANGEROUS: the exception inside ВызватьОшибку() is lost!
Процедура МояПроцедура(Команда)
    ВызватьОшибку(); // Async function called without Ждать
КонецПроцедуры

Асинх Функция ВызватьОшибку()
    ВызватьИсключение "ошибка!"; // nobody will see this
КонецФункции
```

**Rule.** Always use `Ждать` when calling `Асинх` functions if the result or error handling matters. Skip `Ждать` only for fire-and-forget scenarios where the result and any errors are intentionally ignored.

### 2. `Асинх` in form event handlers does NOT block

Form event handlers (`ПриОткрытии`, `ПередЗакрытием`) declared with `Асинх` **do not behave as expected** — the platform does not wait for them to finish.

```bsl
// DOES NOT WORK! The form opens anyway, Отказ = Истина is ignored.
&НаКлиенте
Асинх Процедура ПриОткрытии(Отказ)
    Отказ = Истина;                    // platform has already moved on
    ВызватьИсключение "ошибка!";       // user sees an error, but the form is already open
КонецПроцедуры
```

**Rule.** Do **not** make form event handlers (`ПриОткрытии`, `ПередЗакрытием`, `ПриЗаписиНаСервере`, etc.) async. The `Отказ` parameter and any influence on the form's execution flow will be ignored. Instead — call a separate `Асинх` procedure from a regular handler.

### 3. Command handlers — async is allowed

Unlike form event handlers, command handlers **can** safely be declared `Асинх`:

```bsl
&НаКлиенте
Асинх Процедура МояКоманда(Команда)
    Обещание = ВвестиЧислоАсинх(1, "Укажите число");
    Результат = Ждать Обещание;
КонецПроцедуры
```

---

## Pattern: question on form open

`ПриОткрытии` is a regular procedure that calls a separate `Асинх` procedure:

```bsl
&НаКлиенте
Процедура ПриОткрытии(Отказ)
    ЗадатьВопросПриОткрытии();
КонецПроцедуры

&НаКлиенте
Асинх Процедура ЗадатьВопросПриОткрытии()

    Обещание = ВопросАсинх("Продолжить работу?",
        РежимДиалогаВопрос.ДаНет, , КодВозвратаДиалога.Да);
    Результат = Ждать Обещание;

    Если Результат <> КодВозвратаДиалога.Да Тогда
        ЭтаФорма.Закрыть();
    КонецЕсли;

КонецПроцедуры
```

---

## Pattern: question on form close

A flag variable prevents recursion:

```bsl
&НаКлиенте
Перем ВопросПриЗакрытииЗадан;

&НаКлиенте
Процедура ПередЗакрытием(Отказ, ЗавершениеРаботы,
        ТекстПредупреждения, СтандартнаяОбработка)

    Если НЕ ВопросПриЗакрытииЗадан Тогда
        ЗадатьВопросПриЗакрытии();
        Отказ = Истина;
    КонецЕсли;

КонецПроцедуры

&НаКлиенте
Асинх Процедура ЗадатьВопросПриЗакрытии()

    Обещание = ВопросАсинх("Закрыть форму?",
        РежимДиалогаВопрос.ДаНет, , КодВозвратаДиалога.Да);
    Результат = Ждать Обещание;

    Если Результат = КодВозвратаДиалога.Да Тогда
        ВопросПриЗакрытииЗадан = Истина;
        ЭтаФорма.Закрыть();
    КонецЕсли;

КонецПроцедуры

ВопросПриЗакрытииЗадан = Ложь;
```

---

## Pattern: file workflow

```bsl
&НаКлиенте
Асинх Процедура ЗагрузитьФайлыНаСервер()

    Обещание = НайтиФайлыАсинх(ПутьКПапке, "*.*", Ложь);
    НайденныеФайлы = Ждать Обещание;

    ДобавляемыеФайлы = Новый Массив;
    Для Каждого НайденныйФайл Из НайденныеФайлы Цикл
        Описание = Новый ОписаниеПередаваемогоФайла;
        Описание.Имя = НайденныйФайл.ПолноеИмя;
        ДобавляемыеФайлы.Добавить(Описание);
    КонецЦикла;

    Обещание = ПоместитьФайлыНаСерверАсинх(
        , , ДобавляемыеФайлы, ЭтаФорма.УникальныйИдентификатор);
    Результат = Ждать Обещание;

КонецПроцедуры
```

---

## HTTP methods (platform 8.3.21+)

`HTTPСоединение` exposes async analogs (suffix `Асинх`): `ВызватьHTTPМетодАсинх`, `ЗаписатьАсинх`, `ПолучитьАсинх`, etc. Same rules apply: caller must be `Асинх`, use `Ждать` to consume the result and surface exceptions.
