---
description: "Structured 1C review defect cards with triggers and Legitimate Form counter-signals. Load during code review before reporting defects."
alwaysApply: false
category: quality
---

# 1C Review Defect Catalog (Trigger & Legitimate Form)

<!-- help-mcp-router -->

> **Retrieve through MCP only.** Call `standards(name="review-defect-catalog")` (or `standards(query="...")` for a targeted card) on `1C-docs-mcp` during code review before reporting findings. Retrieval, paging, and unavailable-server policy: `content/rules/help-corpus-retrieval.md`. Headings below are retrieval targets, not summaries.

## How to Apply During Review

## PERF — Performance Defects

### PERF-01. Query Inside Loop (Запрос в цикле)

### PERF-02. Reference Attribute Dot-Notation (Обращение через точку к ссылке)

### PERF-03. Unindexed Temp Table in Join or Union (Временная таблица без индекса)

## QUERY — Query Language Defects

### QUERY-01. Virtual Table Filter in WHERE Instead of Parameters (Отбор виртуальной таблицы в ГДЕ)

### QUERY-02. Unbounded Query or Non-Deterministic TOP N (Запрос без ПЕРВЫЕ N или без сортировки)

### QUERY-03. Correlated Subquery in SELECT or WHERE (Коррелированный подзапрос)

## TXN — Transactions and Locks Defects

### TXN-01. Missing Managed Lock Before Read-Modify-Write (Нет управляемой блокировки)

### TXN-02. External I/O or Heavy Work Inside Open Transaction (Внешний вызов или долгая работа в транзакции)

### TXN-03. Silent Exception Swallowing in DB Write / Transaction (Подавление исключения в транзакции)

## FORM & CLIENT — Managed Forms and Client-Server Defects

### FORM-01. Unnecessary `&НаСервере` Instead of `&НаСервереБезКонтекста` (Избыточный контекст формы)

### FORM-02. Form Data Conversion Outside Server Context (РеквизитФормыВЗначение вне &НаСервере)

### FORM-03. Chained Client-to-Server Round-Trips (Серия серверных вызовов с клиента)

### CLIENT-01. Direct `Сообщить()` Instead of `СообщениеПользователю` / БСП (Запрещённый Сообщить)

### CLIENT-02. Modal Calls in Async / Web-Client Environment (Модальный вызов)

## SEC — Security and Access Rights Defects

### SEC-01. Unbounded Privileged Mode (Бесконтрольный привилегированный режим)

### SEC-02. Dynamic Query Concatenation or `Выполнить()` Injection (Конкатенация в запрос или Выполнить)

## EXT — Configuration Extension Defects

### EXT-01. `&Вместо` Dropping `ПродолжитьВызов` Silently (Потеря ПродолжитьВызов в &Вместо)

### EXT-02. Direct Edit of Locked Vendor Object (Правка объекта на замке)

## MODEL — Typical AI-Generated Code Defects

### MODEL-01. Hallucinated Platform or БСП API (Выдуманный метод платформы или БСП)

### MODEL-02. Silent Null / Empty-Ref Masking (Молчаливое обнуление Неопределено / ПустаяСсылка)
