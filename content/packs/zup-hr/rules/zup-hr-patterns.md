---
description: "1C:ZUP 3.1 domain patterns — HR history, average earnings, SFR benefits, payroll registers and API verification rules. Load on ZUP 3.1 HR/payroll tasks."
alwaysApply: false
category: development
---

# 1C:ZUP 3.1 — HR and Payroll Patterns (Optional Pack)

Load when modifying or auditing **1С:Зарплата и управление персоналом 3.1** (or the HR/payroll subsystem of ERP / КА): personnel events, schedules, average earnings, SFR benefits, contributions, or regulated reporting.

## Verification First (No Guessed APIs)

ZUP 3.1 module signatures evolve across minor releases (`3.1.27` → `3.1.30+`). **Always verify exact export signatures in the target project via MCP (`search_function` / `search_code` / `get_object_dossier`) before calling any ZUP common module.** Never invent parameter lists from memory.

## Core Architectural Boundaries

1. **Personnel data (`КадровыйУчет`):**
   - Never query raw HR documents (`ПриемНаРаботу`, `КадровыйПеревод`, `Увольнение`) directly for current employee state — use the project's `КадровыйУчет` API (`КадровыеДанныеСотрудников`, `СостоянияСотрудников`, `ТекущиеКадровыеДанныеСотрудников`) or slice registers (`КадроваяИсторияСотрудников`, `ТекущиеКадровыеДанныеСотрудников`), which correctly resolve dates, combinations, and cancellations.
   - Distinguish `ФизическоеЛицо` (person) vs `Сотрудник` (employment contract / position) vs `ГоловнаяОрганизация` / обособленное подразделение.
2. **Working time and schedules (`УчетРабочегоВремени*`):**
   - Resolve planned vs actual hours through the ZUP time-tracking API (respecting `Табель`, `ИндивидуальныеГрафики`, absences, and `ВидыИспользованияРабочегоВремени`), not by scanning raw `ГрафикиРаботы` alone.
3. **Average earnings and accruals (`РасчетСреднегоЗаработка`, `Начисления`):**
   - Average-earnings calculations depend on indexation coefficients, excluded periods, calculation base registers (`ДанныеОНачисленияхДляРасчетаСреднегоЗаработка*`), and the specific benefit type (vacation vs business trip vs sick leave / SFR). Reuse the configuration's existing calculation modules instead of reimplementing formulas.
4. **Benefits, SFR (СФР / СЭДО) and regulated reporting:**
   - Check the exact exchange format version and schema active in the configuration before modifying СЭДО / 6-НДФЛ / РСВ / ЕФС-1 handlers; never hardcode tax/contribution limits or rates that belong in periodic registers (`СведенияОСтавках*`, `ПредельнаяВеличинаБазыСтраховыхВзносов`).
5. **High-stakes review:** payroll, tax, and SFR changes are always **full-cycle** (`AGENTS.md → Triage`); verify calculations on a dev/test base with known reference cases and check rounding, negative adjustments (`Сторно`), and recalculation periods (`ПериодРегистрации` vs `ПериодДействия`).
