---
description: "1C data exchange patterns — Data Conversion 2.0/3.1 (КД), EnterpriseData XDTO extensions, exchange plans and ОбменДанными.Загрузка traps. Load on exchange tasks."
alwaysApply: false
category: development
---

# 1C Data Exchange — КД 2.0 / КД 3.1 / EnterpriseData (Optional Pack)

Load when authoring, extending, or debugging 1C data exchanges: Exchange Plans (`ПланыОбмена`), Data Conversion 2.0 / 3.1 (`КД 2.0`, `КД 3.1`), `EnterpriseData` / Universal Format (`ОбменДаннымиXDTO`), or cross-base synchronization.

## Core Exchange Invariants

1. **`ОбменДанными.Загрузка = Истина` discipline:**
   - Never use `ОбменДанными.Загрузка = Истина` as a shortcut to bypass validation, fill-checks, or locks in ordinary business logic — reserve it strictly for genuine data-exchange / migration loads.
   - Inside `ПередЗаписью` / `ПриЗаписи` / `ОбработкаПроведения`, check `Если ОбменДанными.Загрузка Тогда Возврат; КонецЕсли;` deliberately: know which side effects *must* be skipped (e.g., auto-numbering, interactive checks) and which *must* still run (e.g., critical register consistency when required by the configuration's exchange contract).
   - Guard against infinite ping-pong loops: register changes on exchange nodes only when the change did not originate from that same node (`ОбменДанными.Отправитель`).
2. **КД 2.0 (XML rules, `ПКО`/`ПКС`/`ПВД`):**
   - Keep `ПКО` search fields (`ПоляПоиска`) deterministic and aligned with indexed fields (prefer GUID when syncing same-family configs, or canonical business keys like `ИНН`+`КПП` for counterparties).
   - Verify handler variable contracts (`Источник`, `Приемник`, `ВходящиеДанные`, `Отказ`, `Значение`) against the project's actual `ОбработкаОбменаДанными` / BSP exchange manager via MCP.
3. **КД 3.1 and `EnterpriseData` (Universal Format / XDTO):**
   - Extend `EnterpriseData` cleanly via extension XDTO packages and BSP exchange manager hooks (`МенеджерОбменаЧерезУниверсальныйФормат*` — verify exact overridable module names via `search_code` / `ssl_search`), never by editing locked base XDTO packages directly (`content/skills/1c-metadata-manage/docs/xdto-manage.md`).
   - Preserve namespace URIs and version compatibility (`EnterpriseData` 1.x): adding optional properties must not break deserialization on peer nodes running an older release.
   - Map `ДополнительныеСвойства` / `КонтактнаяИнформация` / tabular sections explicitly and guard against missing or `Неопределено` XDTO properties.
4. **Testing & rollback:**
   - Always test both directions (export → inspect XML/XDTO payload → import into target dev/test base → re-export idempotency) and check for duplicate creation on repeated sync.
   - For separated databases, ensure exchange payloads carry and validate tenant scope (`content/rules/data-separation.md`).
