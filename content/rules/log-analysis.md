---
description: "1C Event Log (ЖР) and Tech Log (ТЖ) diagnostics — timeline correlation for exceptions, locks, deadlocks, slow SQL, background jobs and HTTP errors."
alwaysApply: false
category: quality
---

# Event Log (ЖР) and Tech Log (ТЖ) Analysis

Load when diagnosing production or test incidents from Event Log (`ЖурналРегистрации`), Tech Log (`ТехнологическийЖурнал`: `EXCP`, `TLOCK`, `TDEADLOCK`, `TTIMEOUT`, `DBMSSQL`, `CALL`, `SCALL`, `SDBL`), lock/deadlock traces, long server calls, background job failures, or HTTP service errors. For *writing* log entries, see `standards(name="logging-strategy")`.

## Investigation Workflow

1. **Classify the artifact:** identify whether the input is ЖР export, ТЖ fragment, DBMS/SQL trace, platform exception text, HTTP/web-client error, or a live `1c-data-mcp` log slice. Preserve exact timestamps, timezones, process IDs (`p:processName`), session IDs (`SessionID` / `t:connectID`), user, infobase, event kind, transaction ID, and correlation IDs.
2. **Build one ordered timeline:** align clocks/timezones across files before drawing causal conclusions.
3. **Separate root cause from cascade:** the **first** exception, lock wait, or timeout in a transaction usually triggers subsequent rollback / "Транзакция не активна" / retry noise. Trace backward to the first failure, not the last visible error.
4. **Extract code anchors:** pull module name, procedure name, line number, metadata object, HTTP path, or query text from the event (`Context=` in ТЖ, metadata/comment in ЖР).
5. **Map back to source via MCP:** locate the exact routine and metadata via `search_code`, `get_module_structure`, `get_object_dossier`, or `trace_call_chain`. Never diagnose from an event message alone without reading the corresponding code.
6. **Verify platform message semantics:** if the exact meaning of a platform error or lock event matters, confirm via `1C-docs-mcp` (`docsearch` / `its_help` → `fetch_its`).

## Event-Specific Evidence Checklist

- **Managed locks / deadlocks (`TLOCK`, `TDEADLOCK`, `TTIMEOUT`):** capture *both* waiter and holder (`WaitConnections`, lock space `Regions`, locked values, mode `Shared`/`Exclusive`, `Context` call stack, and elapsed wait time). Cross-check lock acquisition order against `standards(name="locks-and-transactions")`.
- **Slow queries (`DBMSSQL`, `DBPOSTGRS`, `SDBL`):** keep `Duration`, `Rows` / `RowsAffected`, normalized SQL/SDBL text, and `Context` together. Check missing indexes, virtual-table filters outside parameters, and unindexed temp tables (`query-design.md`).
- **Background jobs / HTTP services:** trace start → execution → exception → retry; check session user, separator context (`data-separation.md`), and `rphost` signature cache if the error is "Метод задания не найден" after refactoring.

## Output Shape

Report concisely:
1. **Timeline** of key causal events (with timestamps and session/process IDs).
2. **Root-cause hypothesis** backed by verbatim log lines and matched source paths (`Module.bsl:line`).
3. **Recommended fix or next targeted measurement** (e.g. exact `logcfg.xml` event filter if current logs lack `Context` or `TLOCK`).
4. **Missing evidence** — state explicitly when the provided log slice cannot prove the root cause.
