---
description: Per-task MCP tool playbooks (writing code, review, refactoring — including the safe-refactoring method and mandatory pre-refactor impact analysis, error fixing, performance, forms, integrations, documentation)
alwaysApply: false
category: tooling
---

# Tool Usage by Task — Playbooks

The MCP server catalog, fallback order (`graph → code-metadata → grep=true retry → Grep` for project-source search), and per-server tool descriptors live in the `mcp-1c-tools` skill (`content/skills/mcp-1c-tools/SKILL.md`, `docs/<server>.md`). `AGENTS.md` only defines the short obligation rules and points here.

## Minimum Evidence Matrix

Use the smallest set that closes the real context gaps. Do not promote a task to a heavier path just to satisfy a generic checklist.

| Task shape | Required before edit | Required after edit |
|---|---|---|
| **Quick-fix BSL** (one logical change in one module, no metadata / transaction / public-contract impact) | Read the target module / procedure and any directly referenced helper needed to understand the bug | `syntaxcheck` → `check_1c_code` → `review_1c_code` on the touched module; quick-fix reduces process overhead, not verification depth |
| **Full-cycle BSL** | `templatesearch` when a reusable pattern may exist; `search_code` / `codesearch` for local patterns; `get_object_dossier` / `metadatasearch` when metadata shape affects the code; platform / БСП / ITS docs only when versioned API or standard behaviour matters | `syntaxcheck` → `check_1c_code` → `review_1c_code`; impact analysis when public surface or metadata usage changed |
| **Metadata XML / forms** | Similar object/form examples, metadata lookup, `get_xsd_schema`; prefer `1c-metadata-manage` over hand edits | `verify_xml`; metadata validation / form compilation where applicable |
| **Integrations / platform APIs** | Existing integrations, templates, relevant БСП APIs, platform docs for exact API names / version availability, security requirements | `syntaxcheck` → `check_1c_code` → `review_1c_code`; ITS check when relying on an ITS standard |
| **Markdown / rules / docs** | Read affected docs and referenced files needed for consistency | Structural checks only: paths, links, anchors, duplicate / conflicting wording |

## Writing New Code

Load `content/rules/coding-standards.md` first; for forms use `forms.md`, for non-trivial queries use `query-design.md`.

1. **recall** (`1c-templates-mcp`) — project-memory lookup with the task's key terms (object name, subsystem, error text) at the start of any non-trivial task, per `AGENTS.md → Project memory`. Skip for genuinely greenfield topics the project has never touched.
2. **templatesearch** — find similar implementations.
3. **get_object_dossier** — full passport of the target metadata object (structure, forms, dependencies, code, roles) in a single call.
4. **search_code** → **codesearch** — review existing patterns in the configuration.
5. **search_function** — find an existing procedure/function by name for reuse.
6. **get_module_structure** — overview of the module you intend to edit.
7. **metadatasearch** / **get_metadata_details** — verify metadata structure and attribute types.
8. **bsl_scope_members** — discover available methods/properties of a context.
9. **docinfo** — verify built-in functions by exact name; **docsearch** — search by description.
10. **ssl_search** — find reusable БСП functions.
11. **syntaxcheck** — verify syntax after writing.
12. **check_1c_code** — find logic and performance defects.
13. **review_1c_code** — verify style and ITS standards compliance.
14. **validatequery** (`1c-data-mcp`, if available) — when the change introduces a new / non-trivial query string (module code, DCS data set, dynamic list), parse-check it against the live IB before delivery. Especially important after non-deterministic AI generation (`rewrite_1c_code` / `modify_1c_code` / `ask_1c_ai`).

## Code Review

1. **search_code** → **codesearch** — verify pattern compliance.
2. **trace_impact** → **graph_dependencies** — object-level impact analysis of the change.
3. **trace_call_chain** → **get_method_call_hierarchy** — routine-level BSL call chains, callers/callees.
4. **metadatasearch** / **get_metadata_details** — correct metadata usage.
5. **docinfo** — verify method/property existence; **docsearch** — search by description.
6. **syntaxcheck** — reject syntax-broken input before AI review.
7. **check_1c_code** — bugs and performance issues.
8. **review_1c_code** — style and ITS compliance.
9. **its_help** → **fetch_its** — cross-check against ITS standards.

## Architecture Design

1. **get_object_dossier** — passport of key metadata objects.
2. **metadatasearch** / **get_metadata_details** — existing metadata structure.
3. **trace_impact** → **graph_dependencies** — dependency map across USED_IN, DO_MOVEMENTS_IN, CALLS.
4. **find_objects_using_object** — find all objects referencing the given one.
5. **search_code** → **codesearch** — existing architectural patterns.
6. **trace_call_chain** → **get_method_call_hierarchy** — code coupling and call chains.
7. **templatesearch** — architectural templates.
8. **ask_1c_ai** — architectural questions to 1С:Напарник (treat as a hint, not authority).
9. **config_help** — pattern realization in specific configurations.

## Error Fixing

1. **recall** (`1c-templates-mcp`) — check project memory for the error text / object name first: recurring errors and their fixes are stored there per `AGENTS.md → Project memory`.
2. **vcloggetlasterror** (`1c-data-mcp`, if available) — fetch the exact text, timestamp and affected metadata of the last error from the live IB before forming hypotheses. Avoids guessing what the user "probably saw". Skip when the failing scenario is not yet reproduced in the connected IB.
3. **syntaxcheck** — syntax errors.
4. **check_1c_code** — logic and performance issues.
5. **search_function** — locate the failing procedure/function.
6. **search_code** → **codesearch** — related patterns (`detail_level="L0"` for the full body of a specific routine).
7. **get_module_structure** — module context around the error.
8. **trace_call_chain** → **get_method_call_hierarchy** — how the error propagates through the call chain.
9. **docinfo** — verify function/method names; **docsearch** — fallback by description.
10. **metadatasearch** / **get_metadata_details** — verify metadata names and attributes.
11. **validatequery** (`1c-data-mcp`, if available) — when the suspect path is a query string, parse-check it before deeper investigation.
12. **vcexecutequery** (`1c-data-mcp`, if available) — read-only query against the live IB to confirm a data-state hypothesis without changing production code.
13. **vcexecutecode** (`1c-data-mcp`, if available) — run a small read-only BSL fragment in the live IB to verify a platform-version-specific behaviour. Default to read-only; **never** wrap a mutation without explicit user consent (see `docs/1c-data-mcp.md → Safety`).
14. **modify_1c_code** — targeted AI fix (treat output as a draft, re-validate).

## Performance Optimization

1. **search_code** → **codesearch** — locate slow patterns (`semantic` mode: "медленный запрос", "цикл по выборке").
2. **trace_call_chain** → **get_method_call_hierarchy** — identify hot call chains.
3. **trace_impact** → **graph_dependencies** — objects that cause cascading issues (`relationship_types=["CALLS"]` for pure code paths).
4. **metadatasearch** / **get_metadata_details** — verify indexes and metadata structure.
5. **check_1c_code** — bottleneck analysis.
6. **rewrite_1c_code** — AI optimization (`goal: optimize`); re-validate with
   `syntaxcheck` → `check_1c_code` → `review_1c_code`.
7. **templatesearch** — optimized templates.
8. **its_help** → **fetch_its** — ITS performance standards.
9. **validatequery** → **vcexecutequery** (`1c-data-mcp`, if available) — parse-check the rewritten query, then run it read-only against the live IB to compare row counts / spot Cartesian explosions / confirm a virtual-table state. Use only on a test or copy IB when production data volumes matter.

## Refactoring

**Method — sequencing before tools.** Refactoring is high-risk because the user-visible behaviour must stay identical while the code shape changes:

1. **Top-down analysis first.** Map the entire chain of calls and data flow for the area you intend to change. Do not start editing until you can answer: what are the entry points, who calls what, what registers / metadata are touched, what is the observable behaviour.
2. **Bottom-up edits.** Start with the lowest-level utility functions and work upward. Higher-level callers integrate the refactored helpers only after the helpers themselves are clean and verified.
3. **No "while we're here" edits.** Out-of-scope cleanup belongs to a separate, explicit task — see `AGENTS.md → Surgical Changes`.

**Pre-refactor impact analysis (steps 1–4 below) is mandatory** — run it before touching the first line. If the impact-analysis MCPs are not exposed in the session, follow the graceful-degradation procedure from `verification-gates.md → Gate 4`; do not refactor blind.

1. **get_object_dossier** — passport of the object being refactored.
2. **trace_impact** → **graph_dependencies** (`direction="downstream"`) — what breaks on change.
3. **trace_call_chain** → **get_method_call_hierarchy** (`direction="callers"`) — all callers.
4. **find_objects_using_object** / **find_usages_of_object** — every type reference before renaming/removing. For registers additionally **find_register_movement_docs** — every document that posts movements there.
5. **search_code** → **codesearch** — every code pattern related to the object.
6. **search_code** (`detail_level="L3"`, high `top_k`) → **codesearch** — post-refactor verification that no old references remain.
7. Run the full closing gate from `verification-checklist.md` once. It applies
   `syntaxcheck` → `check_1c_code` → `review_1c_code` in order and reuses fresh Stage 3
   evidence instead of repeating validators on unchanged code.

If the refactor is large enough to enter the subagent pipeline — delegate per
`subagent-pipeline.md → Stage 3` (`1c-refactoring`).

## Generating / Modifying Metadata XML

1. **metadatasearch** (`names_only=true`) — similar objects as examples.
2. **get_xsd_schema** — XSD schema for the target metadata type.
3. Write/modify XML against the schema and examples.
4. **verify_xml** — validate against XSD; fix errors.
5. Use the **1c-metadata-manage** skill for compilation and deployment.

## Form Analysis and Generation

1. **search_forms** — similar existing forms in the configuration.
2. **inspect_form_layout** — structure of the found form (elements, bindings, commands, events).
3. **metadatasearch** (`names_only=true`) — metadata objects for XML references.
4. **get_xsd_schema** (`"Форма"`) — XSD schema of `Form.xml`.
5. Generate `Form.xml` based on examples and schema.
6. **verify_xml** — validate `Form.xml` against XSD.
7. **1c-metadata-manage** skill (form-manage) — compilation and validation.

## Integrations

Use this playbook when writing HTTP services / clients, REST integrations, file or message-queue exchanges, webhooks. Domain rules — `integrations-add.md`.

1. **ssl_search** — check for ready-made БСП subsystems ("Интернет-поддержка пользователей", "Обмен данными", "Получение файлов из Интернета", "Цифровая подпись").
2. **templatesearch** — integration templates (HTTP request, JSON parsing, signed payloads, retry policy).
3. **search_code** → **codesearch** (`semantic` mode) — existing integrations in the configuration ("HTTP запрос", "отправка JSON", "парсинг ответа").
4. **docinfo** — verify platform types by exact name (`HTTPСоединение`, `HTTPЗапрос`, `ЧтениеJSON`, `ЗаписьJSON`, `ЗаписьXML`, `ЧтениеXML`).
5. **docsearch** — fallback when the exact platform-API name is unknown.
6. **get_xsd_schema** + **verify_xml** — when the contract is XML with a known XSD.
7. **its_help** → **fetch_its** — ITS articles on long-running operations, secure password storage, asynchronous external components.
8. **search_function** + **get_module_structure** — locate or extend the integration common module (typically `*HTTPClient`, `*Integration`, `*Exchange`).
9. After implementation: **syntaxcheck** → **check_1c_code** → **review_1c_code**.

## Documentation

1. **codesearch** — find code to document.
2. **metadatasearch** / **get_metadata_details** — metadata structure.
3. **get_module_structure** — list of procedures/functions.
4. **docinfo** — documentation by exact name; **docsearch** — search by description.
5. **helpsearch** — existing help articles.
6. **its_help** → **fetch_its** — methodological ITS articles.
7. **search_1c_documentation** — version-specific platform documentation.

## Comparing Platform Versions

1. **diff_1c_documentation_versions** — what changed between versions.
2. **search_1c_documentation** — documentation for a specific version.
