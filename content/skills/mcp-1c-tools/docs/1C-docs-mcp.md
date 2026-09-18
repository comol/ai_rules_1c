# 1C-docs-mcp — tool catalog

Four kinds of content behind **four** tools. They are not interchangeable, and two of them are not reachable from the other two.

> Load this file only if the `1C-docs-mcp` server is actually available in the current session.

| Tool | Content | When to use |
|---|---|---|
| **docsearch** | Platform **syntax reference** + platform **prose** (guides, glossary, query-language book), hybrid vector + BM25 | Find built-in functions by description, look up platform features when the exact name is unknown |
| **docinfo** | The same two, by exact name | Documentation for a known name (`"ТаблицаЗначений"`, `"Массив.Найти"`, `"Запрос"`) |
| **standards** | The project's **development standards** (`1c-standards` collection) — the routed rules of `content/rules/` | Retrieve a routed standard before writing or reviewing code — canon: `content/rules/help-corpus-retrieval.md` |
| **formatspec** | 1C **file-format specifications** — on-disk XML of forms, roles, DCS schemas, spreadsheet documents, extensions | Authoring or debugging metadata XML by hand; next to `metadata-xml-workarounds.md` and the `1c-metadata-manage` skill |

## Parameters

`docsearch(query)` and `docinfo(name)` take the same optional set: `top_k`, `doc_type` (`method` \| `property` \| `constructor` \| `event` \| `object` \| `type` \| `structure` \| `other`), `scope` (`syntax` \| `docs` \| `all`), `max_chars`, `max_items`, `detail_level` (`detailed` \| `compact`), `cursor`, `diagnostics=false`.

`standards` and `formatspec` are **collection tools** with three call forms each — no args = the catalogue, `name=` = one document entire, `query=` = search inside that collection only — plus `max_chars`, `max_items`, `detail_level`, `cursor`, `diagnostics=false`.

```
standards()                          # catalogue of standards with their declared descriptions
standards(name="anti-patterns")     # that standard, entire (short name, returned doc_id, or title)
standards(query="именование ролей")  # search inside the standards only

formatspec()                         # catalogue of format specifications
formatspec(name="1c-form-spec")      # that specification, entire
formatspec(query="реквизиты формы")  # search inside the specifications only
```

- **There is no `corpus` argument on any tool of this server.** Passing one is an unknown-argument error and the guessed-parameter defect of `AGENTS.md → MCP Tool Calling → C.2`.
- **`scope` does not reach the collections.** `standards` and `formatspec` are the only routes to them; `docsearch(scope="all")` still searches only the syntax reference and the prose.
- **Documents are paged, not cut.** A document over `max_chars` returns `collection.parts` and `next_cursor`; continue until you have what you need. A first page is not the whole standard.
- **Returned identifiers are opaque.** Copy `doc_id` and cursors exactly; do not manufacture them from names, paths, or call expressions.
- **Routed standards are retrieved through MCP only.** No repository URL or local-body fallback; if unavailable, continue independent work and leave dependent requirements unverified under `content/rules/help-corpus-retrieval.md → When the server is not exposed`.

## Response contract 4.0

- Read `outcome` first: `ok`, `not_found`, `unavailable`, or `error`. `not_found` is a successful absence of an answer; do not loop on it.
- `top_k` limits the result set counted by `total`; `max_items` limits one page of that set. Continue with the opaque `next_cursor` and the same arguments.
- `detail_level="detailed"` returns a document prefix. `compact` returns up to **four** query-relevant snippets in document order.
- A result owns the only `score`. `snippet_count` is omitted for a complete hit; on a partial hit it is the total available snippet count and is therefore greater than `len(snippets)`. The removed per-result `truncated` flag must not be expected.
- Citation fields are conditional: `source`, `doc_type`, `name`/`object_name` and similar fields are omitted when another field already determines them. A single-corpus response carries `corpus` at envelope level; mixed results carry it in each citation.
- Leave `diagnostics=false` for normal retrieval. The slim response omits lanes, fusion, relevance, detail-level machinery and per-result lane scores; common `filter` remains, and `status` appears whenever the index is not ready. `diagnostics=true` adds retrieval details. Threshold entries name their measured `field`, and relevance reports distinguish `admitted`, `rejected`, `cleared`, `best` and `closest`.
- The current source contract is `schema_version: "4.0"`, but the published beta image is still `2.1`. Follow the actual tool schema and response of the connected image rather than assuming source-only 4.0 fields.

## Notes

- **Prefer `docinfo` for known names** — exact lookup is faster and more precise than semantic search.
- **`docsearch` is for fuzzy / semantic search** when the exact name is unknown.
- **Prefer `standards(name=…)` over `standards(query=…)`** when you know which rule governs — these rules are written to be read whole, and one call gets the whole rule.
- When verifying a platform method / type during writing or review — always cross-check against the documentation; functions and signatures change between platform versions.
- `outcome: "not_found"` is a finished answer, not an error: the call succeeded and the documentation has no entry. Do not retry it as if it failed.

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
