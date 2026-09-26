---
description: Per-task MCP tool playbooks — code writing, review, architecture, error fixing, performance, safe refactoring with impact analysis, metadata XML, forms, integrations. Load for code / review / debug / refactor / performance / metadata work.
alwaysApply: false
category: tooling
---

# Tool Usage by Task — Playbooks

Server catalog and routing — `content/skills/mcp-1c-tools/SKILL.md`; exact argument names and example calls — the operation skill it names (`1c-code-search`, `1c-meta-info`, `1c-impact`, `1c-form-inspect`, `1c-validate`, `1c-platform-help`, `1c-templates-memory`, `1c-live-ib`); search discipline — `content/rules/mcp-first-search.md`. In EDT projects (`.dev.env` `USE_EDT=true`) the playbooks apply unchanged and `content/rules/edt-workflow.md` adds the source-format check, EDT validation markers, EDT-side DB update and form snapshots.

## Minimum Evidence Matrix

Use the smallest set that closes the real context gaps; do not promote a task to a heavier path to satisfy a checklist.

| Task shape | Required before edit | Required after edit |
|---|---|---|
| **Quick-fix BSL** | The target module / procedure and any directly referenced helper needed to understand the change | The validator chain of the active `VERIFICATION_DEPTH` on the touched module (default `standard`: `syntaxcheck` → `check_1c_code`; `verification-policy.md → Verification depth levels`) |
| **Full-cycle BSL** | Common preamble below; `search_code` / `codesearch` for local patterns; `get_object_dossier` / `metadatasearch` when metadata shape affects the code; platform / БСП / ITS docs only when a versioned API or standard matters | The validator chain; impact analysis when public surface or metadata usage changed (`verification-gates.md → Gate 4`) |
| **Metadata XML / forms** | Similar object / form examples, metadata lookup, `get_xsd_schema`; **the mutation goes through the `1c-metadata-manage` skill** (hard gate, `AGENTS.md → Skills and Subagents`) | `verify_xml`; the skill's validation / form compilation |
| **Integrations / platform APIs** | Existing integrations, templates, relevant БСП APIs, platform docs for exact API names and version availability, security requirements | The validator chain; ITS check when relying on an ITS standard |
| **Markdown / rules / docs** | Affected docs and the files they reference | Structural checks only: paths, links, anchors, duplicate / conflicting wording |

## Common preamble — every playbook that writes or changes BSL

0. **Platform-capability check** when the task enters a specialized domain (cryptography, СЛАУ / numerical methods, data analysis, collaboration system / bots, integration bus / queues, full-text search, regex, …) — `AGENTS.md → MCP Tool Calling → A.7`.
1. **`recall`** with the task's key terms — `content/rules/project-memory.md`.
2. **`templatesearch`** — task text verbatim; a hit is the base — `AGENTS.md → MCP Tool Calling → A.8–A.9`.

The steps below assume the preamble is done. Validator steps are `syntaxcheck` (by path — `syntaxcheck_file`) → `check_1c_code` → `review_1c_code` within `verification-policy.md → Validator budget`.

## Writing New Code

Load `content/rules/coding-standards.md` first; forms — `forms.md`; non-trivial queries — `query-design.md`.

1. `get_object_dossier` — passport of the target object (structure, forms, dependencies, code, roles).
2. `search_code` → `codesearch` — existing patterns in the configuration; `search_function` — an existing routine to reuse; `get_module_structure` — the module you will edit.
3. `metadatasearch` / `get_metadata_details` — attribute names and types; `bsl_scope_members` — members of a context.
4. `docinfo` (exact name) / `docsearch` (by description) — built-in functions; `ssl_search` — reusable БСП functions.
5. Validator chain; then `validatequery` (`1c-data-mcp`, if exposed) for every new / non-trivial query string, especially after AI generation.

## Code Review

1. `search_code` → `codesearch` — pattern compliance.
2. `trace_impact` → `graph_dependencies` — object-level impact; `trace_call_chain` → `get_method_call_hierarchy` — callers / callees.
3. `metadatasearch` / `get_metadata_details` — metadata usage; `docinfo` / `docsearch` — method existence.
4. Validator chain (`syntaxcheck` first — never feed syntax-broken code to the AI reviewers).
5. `its_help` → `fetch_its` — ITS standards cross-check.

## Architecture Design

1. `get_object_dossier` — key objects; `metadatasearch` / `get_metadata_details` — existing structure.
2. `trace_impact` → `graph_dependencies` — dependency map (USED_IN, DO_MOVEMENTS_IN, CALLS); `find_objects_using_object` — every referrer.
3. `search_code` → `codesearch` — existing architectural patterns; `trace_call_chain` → `get_method_call_hierarchy` — coupling.
4. `templatesearch` — architectural templates; `ask_1c_ai` — a hint, not authority; `config_help` — pattern realization in specific configurations.

## Error Fixing

Method — `standards(name="systematic-debugging")` (`DEBUG_FAST_PATH` for directly evidenced root causes).

1. `recall` — recurring errors and their fixes are stored there.
2. `vcloggetlasterror` (`1c-data-mcp`, if exposed) — exact text, timestamp and affected metadata of the last error; skip when the scenario is not reproduced in the connected IB.
3. `syntaxcheck` (by path) → `check_1c_code` — syntax and logic defects.
4. `search_function`, `search_code` (`detail_level="L0"` for a full routine body) → `codesearch`, `get_module_structure` — locate and understand the failing routine; `trace_call_chain` → `get_method_call_hierarchy` — propagation.
5. `docinfo` / `docsearch`, `metadatasearch` / `get_metadata_details` — verify names the code relies on.
6. `validatequery` → `vcexecutequery` (read-only) → `vcexecutecode` (read-only fragment; never a mutation without explicit consent — `docs/1c-data-mcp.md → Safety`) — confirm a data-state or platform-behaviour hypothesis in the live IB.
7. `modify_1c_code` — targeted AI fix (a draft: re-validate).

## Performance Optimization

0. If the slow artifact is or contains a query — `query-design.md` and `content/skills/1c-metadata-manage/docs/query-optimization.md → Mandatory Optimization Checklist`, item by item, even when no MCP server is exposed.
1. `search_code` (`semantic`: «медленный запрос», «цикл по выборке») → `codesearch` — slow patterns; `trace_call_chain` → `get_method_call_hierarchy` — hot chains; `trace_impact` (`relationship_types=["CALLS"]`) → `graph_dependencies` — cascades.
2. `metadatasearch` / `get_metadata_details` — indexes and structure; establish the baseline result and measured bottleneck. If diagnosis needs `check_1c_code`, first obtain syntax evidence for that same state.
3. Reuse the common preamble's `templatesearch` result as the base when it fits; search again only for a newly identified gap. `its_help` → `fetch_its` — applicable ITS performance standards **before** choosing the rewrite. Confirm the candidate preserves row multiplicity, values and other required behaviour.
4. Adapt the matching template, or use `rewrite_1c_code` (`goal: optimize`) when no fitting template exists — a draft. Run the validator chain after the edit.
5. `validatequery` → bounded read-only `vcexecutequery` (`1c-data-mcp`, test or copy IB) — compare results with the baseline, including duplicates and overlapping conditions, then compare performance. Parsing alone proves neither metadata resolution nor result equivalence (`verification-gates.md → Gate 3a`).

## Refactoring

**Method.** Top-down analysis first: map entry points, callers, touched registers / metadata and the observable behaviour — no edit before you can state them. Bottom-up edits: lowest-level helpers first, callers integrate only after the helpers are clean and verified. No "while we're here" edits (`AGENTS.md → Surgical Changes`).

**Pre-refactor impact analysis is mandatory** — steps 1–3 before touching the first line; when the impact MCPs are not exposed follow `verification-gates.md → Gate 4` graceful degradation, never refactor blind.

1. `get_object_dossier` — passport of the object.
2. `trace_impact` (`direction="downstream"`) → `graph_dependencies` — what breaks; `trace_call_chain` (`direction="callers"`) → `get_method_call_hierarchy` — all callers.
3. `find_objects_using_object` / `find_usages_of_object` — every type reference before renaming / removing; registers additionally `find_register_movement_docs`.
4. `search_code` → `codesearch` — every related code pattern; after the refactor `search_code` (`detail_level="L3"`, high `top_k`) → `codesearch` — no old references remain.
5. The closing gate from `verification-gates.md` once, reusing fresh Stage 3 evidence. A refactor large enough for the subagent pipeline — `subagent-pipeline.md → Stage 3` (`1c-refactoring`).

## Generating / Modifying Metadata XML

Step 0 is the execution decision: load the **`1c-metadata-manage`** skill (`SKILL.md` → domain doc) **before** writing or modifying any XML — the mutation is driven by the skill's tools (hard gate, `AGENTS.md → Skills and Subagents`; exceptions in `SKILL.md → Hard rule`); MCP calls gather evidence around the run, they do not replace it.

1. `metadatasearch` (`names_only=true`) — similar objects as examples; `get_xsd_schema` — the target type's schema.
2. The skill's scaffold / edit / compile tools against the schema and examples; direct execution vs. the `1c-metadata-manager` subagent per the skill's Dispatch Strategy.
3. `verify_xml` + the skill's validation scripts; fix and re-validate.

## Form Analysis and Generation

Same gate: `Form.xml` / layouts are created or changed through the skill (`docs/form-manage.md`, form-compile DSL) or the `1c-metadata-manager` subagent; design rules — `forms.md` (router). Hand-writing `Form.xml` while the skill is available is a defect.

1. `search_forms` — similar existing forms; `inspect_form_layout` — their structure (elements, bindings, commands, events).
2. `metadatasearch` (`names_only=true`) — objects for XML references; `get_xsd_schema("Форма")`.
3. The skill's form-scaffold / form-edit / form-compile tools; `verify_xml` + `form-validate`; fix and re-validate.

## Integrations

Domain rules — `integrations-add.md`.

1. `ssl_search` — ready-made БСП subsystems («Интернет-поддержка пользователей», «Обмен данными», «Получение файлов из Интернета», «Цифровая подпись»); `templatesearch` — integration templates.
2. `search_code` (`semantic`: «HTTP запрос», «отправка JSON», «парсинг ответа») → `codesearch` — existing integrations; `search_function` + `get_module_structure` — the integration common module (`*HTTPClient`, `*Integration`, `*Exchange`).
3. `docinfo` — platform types by exact name (`HTTPСоединение`, `HTTPЗапрос`, `ЧтениеJSON`, `ЗаписьJSON`, `ЗаписьXML`, `ЧтениеXML`); `docsearch` when the name is unknown; `get_xsd_schema` + `verify_xml` for an XML contract with a known XSD.
4. `its_help` → `fetch_its` — long-running operations, secure password storage, asynchronous external components.
5. Validator chain.

## Documentation

`codesearch` — code to document; `metadatasearch` / `get_metadata_details` — structure; `get_module_structure` — routine list; `docinfo` / `docsearch` — platform documentation; `helpsearch` — existing help articles; `its_help` → `fetch_its` — methodological articles; `search_1c_documentation` — version-specific platform docs.

## Comparing Platform Versions

`diff_1c_documentation_versions` — what changed between versions; `search_1c_documentation` — documentation for a specific version.
