---
name: mcp-1c-tools
description: "Router for the 1C MCP ecosystem — which server answers which need, which operation skill holds the exact calls and parameter names, and the fallback chain. Load before selecting any 1c-*-mcp / 1C-*-mcp tool."
---

# MCP tools for 1C — router

Apply `content/rules/mcp-policy.md → Tool availability` before routing: `.dev.env` `TOOL_*` policy plus callable tools and verified scope. Config entries alone prove nothing. The same policy owns obligations, budgets and typed-error recovery. Search: `content/rules/mcp-first-search.md`; task sequences: `content/rules/tooling-playbooks.md`.

**Project scope is part of the call.** For extensions or a multi-project graph, first match the current source roots to a returned base `project_id` through `list_graph_projects` (`content/rules/multi-contour-search.md`). Supply it explicitly on every graph project-data call that exposes it, including paging and evidence. Resolve extension-layer coverage separately. Use each other server's actual selector (`configurationId` or another field only if exposed); its identifiers are not interchangeable with graph IDs. If a tool has no explicit selector, require a verified fixed/session/entity scope or use a suitable scoped tool/fallback. Never invent unsupported parameters or accept a default/foreign project as the current one. Reuse a valid mapping until the workspace/server context changes.

## Need → operation skill

Load the skill for the operation, not this whole catalogue. Each skill lists the exact argument names of its tools and example calls; no schema fetch is needed for a tool it names.

| Need | Skill | Servers |
|---|---|---|
| Locate or read BSL code, module layout, members of a context | `content/skills/1c-code-search/SKILL.md` | graph, code |
| Facts about a metadata object: passport, attributes, tabular-part columns, objects by category or description | `content/skills/1c-meta-info/SKILL.md` | graph, code |
| Usages, call chains, downstream impact, register writers, extension layers | `content/skills/1c-impact/SKILL.md` | graph, code |
| Read forms, form artifacts, XSD / format specs before a form change | `content/skills/1c-form-inspect/SKILL.md` | code, graph, docs |
| Validate changed BSL and metadata XML (Gates 1–3, 5) | `content/skills/1c-validate/SKILL.md` | syntax, checker, code |
| Platform reference, capability check, БСП API, routed standards, ITS, configuration docs | `content/skills/1c-platform-help/SKILL.md` | docs, ssl, checker, code |
| Templates as the base, project memory recall / save | `content/skills/1c-templates-memory/SKILL.md` | templates, cognee, openviking |
| Run a query or fragment in the live infobase, last event-log error | `content/skills/1c-live-ib/SKILL.md` | data |
| Create / edit / remove metadata, forms, roles, DCS, MXL, infobases | `content/skills/1c-metadata-manage/SKILL.md` | scripts, not MCP |
| Live 1C:EDT workspace (`USE_EDT=true` only) | `docs/edt-mcp.md`, `content/rules/edt-workflow.md` | edt |

## Server catalog

| Server id | Purpose | Details |
|---|---|---|
| `1c-graph-metadata-mcp` | Neo4j graph: dossier, impact, call graph, usages, business search, extension layers | `docs/1c-graph-metadata-mcp.md` |
| `1c-code-metadata-mcp` | Metadata and BSL search, navigation, forms, XSD, `verify_xml` | `docs/1c-code-metadata-mcp.md` |
| `1c-syntax-checker-mcp` | BSL Language Server: `syntaxcheck_file` (default), `syntaxcheck` (text fallback) | `docs/1c-syntax-checker-mcp.md` |
| `1c-code-check-mcp` | 1С:Напарник: `check_1c_code`, `review_1c_code`, AI drafts, ITS, version docs | `docs/1c-code-check-mcp.md` |
| `1C-docs-mcp` | Platform reference (`docsearch`, `docinfo`), `standards`, `formatspec` | `docs/1C-docs-mcp.md` |
| `1c-ssl-mcp` | БСП / SSL API search | `docs/1c-ssl-mcp.md` |
| `1c-templates-mcp` | Code templates, memory fallback | `docs/1c-templates-mcp.md` |
| `cognee`, `openviking` *(optional)* | Memory providers | `docs/memory-providers.md` |
| `1c-data-mcp` | Live-IB execution over `hs/mcp` | `docs/1c-data-mcp.md` |
| `edt-mcp` *(conditional)* | Live EDT workspace | `docs/edt-mcp.md` |

### Optional pre-alpha servers

These are experimental projects, separate from the seven main servers above and not required by normal development gates. Client aliases vary; use the tools actually exposed in this session. Read their catalog only for a task that needs them; do not install, start a client, replay UI actions or write conversion files merely to check availability.

| Project / runtime server name | Purpose | Details |
|---|---|---|
| `MCP_Test` / `1C Visual UI Test` | Testing knowledge base, scenario preparation, test-client processes and UI replay | `docs/mcp-test.md` |
| `MCP_ConversionData20` / `1C Конвертация данных 2.0 — разработка правил обмена` | Metadata mapping and conversion-rule authoring/validation/export | `docs/mcp-conversion-data20.md` |

## Fallback chain

**Project source** (code, metadata, usages, forms, file locations): within verified contour coverage, graph → mapped code-metadata → scoped native `Grep` / `Glob` / `Read` after a bounded miss, with a one-line fallback note. Code chooses its file-scan fallback internally; current tools have no `grep` input. Skip uncovered lanes; no eligible exposed index means native search in that contour immediately. Owner: `content/rules/mcp-first-search.md`; multiple roots, catalog/scope selectors and acceptance: `content/rules/multi-contour-search.md`.

**External knowledge** has no interchangeable fallback chain. Select only the relevant eligible provider. Missing templates: disclose no template check; memory: `project-memory.md`; routed standards: `help-corpus-retrieval.md`; validators/live IB: `verification-gates.md`. An unavailable source never proves API absence or a passed check; block dependent design when authoritative facts are missing.

Open `docs/<server>.md` once per server per session and only for a mode or response shape the operation skill does not cover; the environment descriptor wins over any document here.
