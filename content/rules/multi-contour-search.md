---
description: Source contour catalog, verified index coverage, request-specific search scope and routing acceptance for a base configuration with extensions or separate source indexes
alwaysApply: false
category: tooling
---

# Multi-contour source search

**When to load:** a source question spans a base configuration and extensions, uses separate source indexes, the graph serves multiple projects, or the project declares a contour catalog. Read once per task and reuse until mappings or sources change. This rule selects scope and eligible servers; `content/rules/mcp-first-search.md` owns the bounded retrieval chain, retries and native fallback. Source/build layout and write targets — `content/rules/extension-workspace.md`.

## Catalog and ownership

A contour is a source root with its own origin: a base configuration or a named extension. Keep the source folder, metadata configuration name, search index and target infobase distinct. A method prefix or folder name does not establish ownership; attribute a hit by its actual source path and descriptor.

Reuse the catalog declared by the project's entry instructions. When setup is requested and no catalog exists, use a project-root `project-contours.json` and explicitly reference it from `USER-RULES.md`. Keep one project-owned catalog across clients, using the active client's installed rule path. Preserve an existing location; do not copy vendor-specific forwarding trees from another project or overwrite project mappings during rules updates.

The catalog is optional. Its absence never blocks an ordinary single-contour lookup or triggers automatic setup. In a multi-contour task without one, use supplied roots and verified existing mappings for that task, disclose unresolved coverage, and create a persistent catalog only within requested setup. Discover unknown sources through the applicable search chain; catalog preparation is not permission for an unrestricted source scan.

Catalog fields:

- `schema_version`: `1` for the format below.
- `contours`: ordered records with project-relative `folder`, exact `configuration_name`, `kind` (`base` or `extension`), `role` (`baseline`, `primary`, `secondary`, `infrastructure`) and `code_metadata_server` (actual client server ID, or `null` when no dedicated code index is configured).
- `graph`: `server` and `folders`, listing only verified source roots covered by that graph. With no graph, use `server: null` and `folders: []`. This search catalog does not configure the graph server's extension ingestion catalog.
- `excluded_folders`: project-relative roots omitted from automatic searches. Name relevant exclusions when they limit a broad answer; an explicit request to inspect one sets the task scope but does not silently change the catalog.
- Optional `graph.scope` and contour `code_metadata_scope`: per-tool maps of verified scope arguments, keyed by the tool name exposed by the selected server. Record only parameter names and values supported by that tool's live contract; project IDs must come from server discovery. These fields are routing instructions, not new MCP arguments: never pass the enclosing map to a tool. Empty/omitted maps are sufficient only when the server has a verified fixed scope or the required scope was already resolved for this session. For a shared server, resolve the selected contour's scope before retrieval; a missing/unsupported selector makes that route unusable for a contour-specific claim.

Example for a graph covering only the base, separate code indexes and an unindexed extension. Names and server IDs are illustrative; replace them from project evidence before activating the catalog. A unified graph may instead list all its verified layers in `graph.folders`.

```json
{
  "schema_version": 1,
  "graph": {
    "server": "1c-graph-metadata-mcp",
    "folders": ["Main"],
    "scope": {}
  },
  "excluded_folders": ["Archive"],
  "contours": [
    {
      "folder": "Trade",
      "configuration_name": "Продажи",
      "kind": "extension",
      "role": "primary",
      "code_metadata_server": "trade-code-metadata",
      "code_metadata_scope": {}
    },
    {
      "folder": "Purchasing",
      "configuration_name": "Закупки",
      "kind": "extension",
      "role": "primary",
      "code_metadata_server": null
    },
    {
      "folder": "Main",
      "configuration_name": "ОсновнаяКонфигурация",
      "kind": "base",
      "role": "baseline",
      "code_metadata_server": "1c-code-metadata-mcp"
    },
    {
      "folder": "Exchange",
      "configuration_name": "Интеграция",
      "kind": "extension",
      "role": "secondary",
      "code_metadata_server": "exchange-code-metadata"
    },
    {
      "folder": "OneMCP",
      "configuration_name": "OneMCP",
      "kind": "extension",
      "role": "infrastructure",
      "code_metadata_server": null
    }
  ]
}
```

Confirm names and base/extension classification from the current root descriptors (`Configuration.xml`, or the corresponding EDT descriptor under `content/rules/edt-workflow.md`), not directory spelling. Assign roles from existing project decisions; unresolved primary roles or exclusions require `CONFUSION` before activating new routing, while inventory can continue. Catalog order is search priority only, never extension application or load order. Keep credentials and infobase connection strings out of this file.

## Scope and stopping conditions

Choose the question's scope before selecting a tool:

- **Named location:** start at the supplied path or likely owner, otherwise primary contours in catalog order. Stop at a sufficient exact hit; it proves location, not uniqueness. If primary searches miss, follow relevant evidence into base/secondary sources or report the unresolved owner.
- **Behavior explanation:** inspect the entry point, relevant base implementation and focused checks of the scenario in the other primary contours. Expand to secondary contours on a relevant reference, adoption evidence or explicit request. Stop when the chain and material influences/gaps are explained; do not repeat the entire investigation in every root.
- **Explicit contour restriction:** stay within the named contour. Include a base dependency only when necessary to explain an adopted implementation and clearly label it; if the user explicitly forbids reading outside that contour, report the dependency as unverified instead.
- **Project-wide usages, impact, uniqueness or absence:** account for the base, all primary and secondary contours, relevant infrastructure and exclusions. A missing route or incomplete scope makes the conclusion partial.
- **Infrastructure question:** inspect the relevant infrastructure contour and its scenario callers.

A supplied file is an entry point; an explicit restriction is a boundary. Absence of an adopted object alone does not rule out influence through common modules or other paths. A named-symbol miss does not prove absence of the business behavior. Report what the checked files/contours establish.

## Eligible routes

### Resolve the project before retrieval

1. Identify the current project root and selected source contour. Reuse a verified mapping only while the workspace, MCP server/namespace and source roots are unchanged. Call `list_graph_projects` once for discovery and again only when that context changes or evidence invalidates the mapping; a session may legitimately contain several projects.
2. Match the returned project to the current roots using its source descriptor/status or existing verified project mapping. A sole returned project is not automatically the current project. Names alone and list order are insufficient. If two projects cannot be tied to the current roots, resolve that ambiguity before dependent graph calls; continue local source work where scope is known.
3. Carry the returned base `project_id` as an explicit top-level scope argument on every supported graph project-data call. It is not `project_name`, a server ID, a folder basename or an extension name. For code/EDT servers, use their own live contract and verified mapping; do not add graph-only arguments. Shared-server routing with no usable selector or fixed scope is unavailable for a contour-specific claim.
4. Verify the expected extension layer and attribute returned paths/entities to it. Only pass layer selectors the particular tool supports; otherwise use layer-aware comparison/effective-entity tools or the mapped contour index/files. A broad project search can locate candidates, but cannot certify a restricted layer result by itself.
5. Preserve project, generation and query when paging; keep entity references within their returned scope. A mismatched response is unusable evidence for the task, not a negative result. `compare_base_and_extension` compares a layer with the base of the same project; a cross-project comparison is a separate explicit operation.

An empty `graph.scope` map in the example is a placeholder for session discovery, not permission to omit `project_id`. Record only live supported arguments when persisting mappings; validate a stored project ID against current discovery before reuse. Discovery and source queries do not authorize server lifecycle changes.

### Select the route

Apply the `mcp-first-search` chain **inside verified coverage**. Server IDs are resolved against tools actually exposed in this session; a client registration or suggestive tool name does not establish coverage.

When coverage is unknown, inspect existing mappings and the applicable bounded scope-discovery response before choosing a route; reuse an attributed search result if it already resolves the gap. No catalog does not mean no coverage. If the available evidence still cannot establish a usable scope, report it as unresolved and use the scoped native fallback; do not claim the index lacks the sources.

- **Unified layered graph:** retain one discovered base `project_id`; use layer-aware tools when the relevant extension layers are present. Do not register extensions as separate graph projects. Keep returned order warnings. The graph's predicted effective implementation is source/index evidence until matched to the target infobase.
- **Graph covering only some roots:** use it for those roots and their supported relationships. For an uncovered extension, go directly to its mapped code-metadata server and verified scope. Never infer that extension's behavior through the base-only graph or disable a working graph capability globally because one contour is uncovered.
- **No usable index for the selected contour:** use native search in that contour's own folder immediately, explaining the gap once. Do not substitute a neighboring contour's index. A `null` code server does not exclude using a graph that demonstrably covers the contour; temporary unavailability does not erase an existing mapping.

Use the first useful eligible tool from the operation skill, then the bounded reformulation/native fallback of `mcp-first-search.md`. Current Code tools select their file-scan fallback internally and accept no `grep` switch. Reuse located paths and sufficient returned bodies. Coverage is checked when resolving the route; freshness is checked when absence, a source/index mismatch or the task depends on it. Do not add routine health calls or repeat discovery for every query.

## Evidence and operation boundaries

Attribute decisive evidence to its contour and file/line, with server/scope when an index supplied it. Distinguish:

- **Local source:** what the inspected files implement, including relevant base and extension versions.
- **Index:** the roots/layers and generation actually represented. Readiness or a generation ID alone does not establish equality with current files or an infobase; compare current source when the claim depends on that equality.
- **Running infobase:** what is established for the explicitly named target, including active extensions and their applicable order when relevant. Source-only analysis must retain that boundary; do not query a live infobase merely to decorate a source answer or silently switch databases after a failed call.

For ordinary source answers, give the behavior, decisive references, checked contours and material gaps concisely. Use “not found in the checked contours” for partial coverage; “only here” and project-wide absence require the wider scope and relevant implementation paths above. Do not produce a call log or separate report by default.

`.dev.env` remains the source of operation defaults; `content/rules/dev-standards-env.md` owns them. A search role grants no write permission, and the contour catalog neither overrides `EXTENSION_NAMES` load order nor changes dump/load paths. For an authorized export/import, use the dedicated procedure and `content/rules/extension-workspace.md`, resolve the source root and extension together for that pass, and verify the target identity. Never remove a populated extension argument to recover from a missing-extension error. A search-only task leaves sources, deployment settings and infobases unchanged.

## Setup acceptance

Run these checks when configuring or changing an actual project's routing. Authoring this reusable rule alone does not constitute live acceptance.

1. **Structure:** JSON parses; included roots exist; names/kinds match descriptors; roles and server mappings are explicit. Normalize paths and check duplicate/nested roots, included/excluded overlap and graph folders outside the catalog. Resolve accidental overlap before activation; retain intentional shared graph coverage explicitly.
2. **Entry chain:** each active client's entry instructions reach the same project catalog and canonical policy. Check that project-owned mappings survive the applicable rules-update path. Creating JSON or frontmatter alone does not connect a server, build an index or load a rule.
3. **Indexed routes:** query one known symbol per indexed contour and compare its attributed path/body to the current file. For a shared server, exercise each scope selector. A successful response from the wrong contour fails this check.
4. **Question boundaries:** exercise an exact location request, a behavior request with relevant base/other-primary checks, an explicit single-contour restriction and a project-wide usage request. Check the stopping conditions and named exclusions/gaps.
5. **Fallback:** use an intentionally unindexed contour or isolated test mapping to exercise native search in that root; do not disable shared services. When the graph covers only the base, confirm it is not used as evidence about an uncovered extension.
6. **No side effects:** confirm the search runs left source files, operation defaults and infobases unchanged. Keep structural checks separate from observed MCP routing and runtime checks; list unrun cases as unverified. Setup never implicitly authorizes dumping, loading, reindexing or deployment.
