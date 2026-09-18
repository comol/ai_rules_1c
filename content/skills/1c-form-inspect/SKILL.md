---
name: 1c-form-inspect
description: "Read managed and ordinary 1C forms — find similar forms, inspect element trees, bindings, commands and handlers, read form / role / report artifacts, fetch the XSD or format spec of a form — through the code-metadata, graph and docs MCP servers. Use before generating or changing a form; the mutation itself goes through 1c-metadata-manage."
argument-hint: "<Kind.Name> [form name]"
allowed-tools: mcp__1c-code-metadata-mcp__search_forms, mcp__1c-code-metadata-mcp__inspect_form_layout, mcp__1c-code-metadata-mcp__get_form_artifact, mcp__1c-code-metadata-mcp__get_xsd_schema, mcp__1c-graph-metadata-mcp__get_form_structure, mcp__1c-graph-metadata-mcp__find_form_links, mcp__1C-docs-mcp__formatspec
---

# 1c-form-inspect — read forms before touching them

Read-only. Creating or editing `Form.xml` is the `1c-metadata-manage` skill (`docs/form-manage.md`, form-compile DSL); design rules — `content/rules/forms.md`. Hand-writing a form while the skill is available is a defect.

## Tools and exact arguments

| Need | Call | Arguments |
|---|---|---|
| Similar existing forms as examples | `search_forms` (code) | `query`, `limit=10`, `grep=false` |
| Element tree, bindings, commands, handlers | `inspect_form_layout` (code) | `object_name`, `form_name=""` (empty = default form) |
| Form artifact with provenance | `get_form_artifact` (code) | `object_name`, `form_name` or `artifact_id`, `include_ranges=true` |
| Graph view of a form | `get_form_structure` / `find_form_links` (graph) | `form_ref` from `resolve_graph_entity`, `include`, `max_depth`; `direction="both"`, `link_kinds` |
| XML rules of the target | `get_xsd_schema` (code) | `object_type="Форма"` (also `Справочник`, `Документ`, `Роль`, `СКД`, `Макет`; English aliases accepted) |
| On-disk format specification | `formatspec` (docs) | `name="1c-form-spec"` or `query="реквизиты формы"` |

## Calls

```json
{"tool": "search_forms", "args": {"query": "ФормаДокумента Реализация", "limit": 10}}
{"tool": "inspect_form_layout", "args": {"object_name": "Документ.РеализацияТоваровУслуг", "form_name": "ФормаДокумента"}}
{"tool": "get_xsd_schema", "args": {"object_type": "Форма"}}
{"tool": "formatspec", "args": {"name": "1c-form-spec"}}
```

## Ordinary forms

`Forms/<Имя>/Ext/Form.bin` is a binary container: none of the XML routes see it. Read it with `unpack_ordinary_form(form_path, workspace_path)` and write it back with `build_ordinary_form(workspace_path, output_path, verify=true)` — the contract, workspace layout and the `verification.status == "match"` criterion are in `content/skills/v8unpack-cf/SKILL.md → Ordinary forms`. Never edit `Form.bin` directly.

## After the change

`verify_xml(xml_content, object_type="Форма")` plus the skill's `form-validate`; `syntaxcheck_file` on the regenerated form module — `1c-validate`. Typed answers map to actions by code — `content/rules/mcp-policy.md → C. Server answers → actions`.

Details: `content/skills/mcp-1c-tools/docs/1c-code-metadata-mcp.md → Forms`, `content/skills/mcp-1c-tools/docs/1c-graph-metadata-mcp.md → Forms`.
