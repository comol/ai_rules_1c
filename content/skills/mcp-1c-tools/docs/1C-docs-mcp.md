# 1C-docs-mcp — tool catalog

1C platform documentation: search by description (vector + BM25) and exact lookup by name.

> Load this file only if the `1C-docs-mcp` server is actually available in the current session.

| Tool | Purpose | When to use |
|---|---|---|
| **docsearch** | Search the platform documentation by description (hybrid: vector + BM25). Single argument: `query` (string) | Find built-in functions by description, look up platform features when the exact name is unknown |
| **docinfo** | Look up platform documentation by exact object / method name | Get documentation for a known name (`"ТаблицаЗначений"`, `"Массив.Найти"`, `"Запрос"`) |

## Notes

- **Prefer `docinfo` for known names** — exact lookup is faster and more precise than semantic search.
- **`docsearch` is for fuzzy / semantic search** when the exact name is unknown.
- When verifying a platform method / type during writing or review — always cross-check against the documentation; functions and signatures change between platform versions.

## Platform capability discovery

Canonical procedure for `AGENTS.md → MCP Tool Calling → A.7`: before implementing a specialized capability by hand, check whether the platform already ships it. The platform has many niche built-in mechanisms that model training data routinely misses — this server indexes the real documentation and is the authority.

**Trigger domains** (non-exhaustive — apply to any capability that feels like "a platform could have this built in"):

| Domain | Example query terms for `docsearch` |
|---|---|
| Cryptography, digital signatures, hashing | «криптография», «электронная подпись», «хеширование» |
| Math / numerical methods (СЛАУ, statistics) | «решение системы линейных уравнений», «математические функции» |
| Data analysis, forecasting, ML | «анализ данных», «прогнозирование», «кластеризация» |
| Collaboration system, bots, notifications | «система взаимодействия», «обсуждения», «бот» |
| Integration bus, message queues, brokers | «шина», «очередь сообщений», «брокер» |
| Full-text search | «полнотекстовый поиск» |
| Regular expressions, string processing | «регулярные выражения» |
| Files, archives, pictures, printing | «работа с архивами», «графическая схема», «печать» |
| Geo / maps, planners, calendars | «геосхема», «планировщик», «календарь» |
| Background / long-running work | «фоновые задания», «длительные операции» |

**Procedure:**

1. `docsearch` with a Russian description of the *capability* (not the assumed class name) — 1–2 reformulations if the first query misses.
2. `docinfo` for every exact type / method name the search returned, to confirm availability and signatures in the target platform version.
3. Where a library-level (not platform-level) solution is plausible — also `ssl_search` on `1c-ssl-mcp`.
4. **Found and usable → build on the platform / БСП mechanism** — use the documented types, methods, virtual tables, and subsystems; custom code only for glue and project-specific wiring. **Found but unusable** (platform version / `РежимСовместимости` / functional mismatch) → implement custom **and state the reason** in the final answer. **Not found** after honest reformulated queries → custom implementation is legitimate; note what was searched.

Skipping this check and hand-rolling a capability from a trigger domain is a defect, even if the resulting code is correct. **Hand-rolling when a usable mechanism was found is also a defect** — see *Using a found platform mechanism* below.

## Using a found platform mechanism

> Canon for `AGENTS.md → MCP Tool Calling → A.7` (reuse half). Applies to **`docsearch` / `docinfo`** (and БСП via `ssl_search`) — **not** to **`templatesearch`** (code templates — `1c-templates-mcp.md → Using a found template`).

When platform documentation (or БСП) confirms a built-in mechanism fits the task:

1. **Use it as the foundation** — call the platform API, virtual table, subsystem, or standard pattern the docs describe. Do not substitute a home-grown class, loop, or data structure that reimplements the same capability.
2. **Custom code = integration layer** — parameters, mapping to project metadata, error messages, placement in modules. Not a parallel reimplementation «because you remember another way».
3. **State the reason** only when you **decline** a found mechanism (version, compatibility, functional gap). Silence when hand-rolling despite a doc hit is a defect.

### Near-fit mechanisms — escalate, do not silently hand-roll

A found mechanism that is *slightly* inconvenient is still a match. «Slightly inconvenient» = awkward API shape, an extra data-conversion step, needs thin glue code, covers 90% of the requirement. None of these authorize a custom reimplementation.

- **Full fit** → use the mechanism, no question needed.
- **Partial fit** (covers the core but a real gap remains) → raise `CONFUSION`: option A — platform mechanism + glue for the gap (state what the glue does), option B — custom implementation (state the cost: more code, no platform support, re-verification burden). Let the operator choose.
- **Cannot ask** (autonomous / batch / benchmark run, no operator reply possible) → **default to the platform mechanism**, close the gap with glue code, and record the residual limitation in the final answer.
- **Hard mismatch only** (doc-confirmed absence in the target platform version, `РежимСовместимости` conflict, functional contradiction with the core requirement) → custom implementation is allowed; cite the evidence in the final answer.

Aesthetic preference, unfamiliarity with the mechanism's API, or «it would take a different data structure» are **not** valid grounds for rejection.

**Good:** docs describe `РегExp` / `МенеджерОбработкиОшибок` / a virtual table — solution uses them directly.

**Good:** platform ships `РешениеСистемЛинейныхУравнений`-class math but the task needs a small preprocessing step → mechanism used, preprocessing written as glue, noted in the answer.

**Defect:** `docinfo` confirms the platform ships the mechanism → agent writes a custom equivalent from training-data habit.

**Defect:** mechanism found, «не совсем удобно» → agent silently hand-rolls instead of raising `CONFUSION` (or defaulting to the mechanism when asking is impossible).
