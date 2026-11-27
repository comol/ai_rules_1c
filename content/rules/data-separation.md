---
description: "1C multi-tenant Data Separation (РазделениеДанных / SaaS) — separator boundaries, queries, background jobs, temp storage, exchanges and privileged-code audit."
alwaysApply: false
category: development
---

# Data Separation (Multi-Tenant / SaaS)

Load when working in a separated infobase (1C:Fresh / SaaS / configurations using `ОбщиеРеквизиты` with `РазделениеДанных = Разделять`) or when auditing tenant isolation in queries, background jobs, exchanges, reports, or integrations.

## Audit Workflow

1. **Identify the separation model:** inspect common attributes (`ОбщиеРеквизиты`) with `РазделениеДанных`, session parameters holding separator values, shared vs separated metadata objects (`ИспользованиеРазделенныхДанных`), and whether code runs inside a separated session or a non-separated (service) session.
2. **Verify metadata & roles:** inspect affected objects and roles via MCP (`get_object_dossier` / `get_metadata_details`) to see which objects are separated and which remain shared across tenants.
3. **Trace tenant context end-to-end:** follow the separator value across reads, writes, DCS/reports, background/scheduled jobs, exchanges, HTTP/web services, file batches, and temporary storage (`ПоместитьВоВременноеХранилище`).
4. **Verify queries:** confirm that queries in non-separated or privileged contexts apply explicit separator filters where required and do not join separated tables with shared tables across tenant boundaries.

## Critical Red Flags

- **Missing separator on write:** creating or updating separated objects in a non-separated session without setting separator context (`УстановитьИспользованиеРазделителя` / `УстановитьЗначениеРазделителя`) or separator attributes.
- **Unscoped background / scheduled job:** launching a background job from a broad/service session that iterates across all tenants without per-tenant isolation or explicit tenant routing.
- **Unjustified privileged mode:** `УстановитьПривилегированныйРежим(Истина)` inside reports, DCS, HTTP handlers, or common modules that reads separated data without enforcing the caller's tenant boundary.
- **Cross-tenant leakage via temp storage / cache / files:** storing tenant-specific data in shared `ПовторноеИспользование` caches, shared constants, or unisolated filesystem paths without tenant scoping.
- **Exchange / integration payloads missing tenant owner:** incoming HTTP/XDTO/exchange payloads that match objects by external code/GUID without constraining lookup to the active tenant.

## Verification

- A test run under a single tenant (or non-separated admin user) does **not** prove isolation.
- Where runtime verification is possible on a dev/test base, confirm behavior across at least **two distinct tenant contexts** (data written in Tenant A is invisible and unreachable from Tenant B). Otherwise record tenant-isolation verification as an explicit open risk.
