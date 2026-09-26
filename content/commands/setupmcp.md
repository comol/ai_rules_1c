---
description: Connect already installed MCP servers and available memory providers to the current repository by asking for their endpoints and project scope
userOnly: true
---

# /setupmcp — connect existing MCP servers to this project

Use when MCP servers are already installed locally or remotely and a new repository needs its own client connections and memory scope. Ask for missing addresses, merge the selected connections into the current project's active client config, and verify them. Reuse confirmed answers from the current request.

This command configures connections only. It does not download distributions, install packages, start or recreate servers, change Docker mounts, register/reindex server-side projects, or migrate memory. Fresh installation belongs to `content/commands/installmcp.md`, `content/commands/install-cognee.md` and `content/commands/install-openviking.md`; updates belong to `content/commands/updatemcp.md`.

## 1. Inspect the current repository

Resolve the repository root and active AI client from the session and `.ai-rules.json` when present. A global command file still operates on the current repository, not on its own directory or on a previously configured project. If several clients are installed, use the current one unless the user selected more; ask only if the active client cannot be determined.

Read the current project MCP config, relevant user-level MCP entries (read-only), `.dev.env`, `USER-RULES.md` and the existing contour catalog when declared. Never print credentials. Resolve the target and schema from `adapters/<tool>.yaml` in the rules source; installed copies can use `content/commands/installmcp.md` → Step 7. Per-client MCP config. Do not invent a second vendor directory or use a global CLI add command that silently writes outside the repository.

Apply `TOOL_*` policy from `content/rules/mcp-policy.md`. Preserve existing values, including `off` and `required`. Explicit setup permits inspecting a disabled provider; only explicit selection permits configuring it, and neither action silently changes its ordinary-use policy. Missing `.dev.env` keys use the documented defaults; do not copy the entire example over existing settings.

**External installation:** detect `.ai-rules.json` `integrations.mcp.mode = "external"`, `BASESAI_MCP_GLOBAL_ROOT`, or `.dev.env` `MCP_GLOBAL_ROOT`. Resolve the installation manifest and its global/project consumers using the external-installation contract in `AGENT-INSTALL.md` (or the matching section of the installed `/checkmcp` procedure). Use actual server IDs and URLs, not the default catalog ports. A missing or stale external manifest is an unresolved ownership issue, not permission to reset the connection to catalog defaults.

## 2. Collect endpoints in one question

Show the discovered connections with their purpose, scope (global/project), and whether their addresses are confirmed for this repository. Use `content/mcp-servers.json` only as a server-purpose catalog when available. An installer-generated localhost URL is a candidate, not evidence that this server is installed or serves the new project.

Ask only for missing or ambiguous choices, in one compact question in the user's language. For a new project without confirmed connections, use this shape:

> Укажите полные MCP-адреса уже установленных серверов для этого репозитория: справка 1С, БСП, шаблоны, проверка синтаксиса, проверка кода, поиск по коду/метаданным и граф. Можно написать «оставить найденные» или «пропустить» для отдельных серверов. Есть ли уже установленная память Cognee или OpenViking? Если да, укажите MCP-адрес и существующий dataset/область проекта, если она задана; если нет — напишите «нет».

Keep confirmed entries out of the question. Accept full URLs with their actual scheme, host, port and path, including remote hosts, reverse-proxy prefixes, `/mcp`, `/mcp/` or an existing SSE endpoint. Ask for clarification on a bare host or missing transport/path; do not derive all addresses from one hostname, assume default ports, or replace SSE with HTTP without evidence. Reuse an existing stdio connection only when its command, arguments and durable paths are known; prefer an existing shared HTTP memory endpoint over spawning another process against the same store.

For optional live-infobase MCP, ask for its existing endpoint only when selected or already configured. Read any existing `INFOBASE_PUBLISH_URL` without changing the publication or credentials. EDT and browser MCP are not implicit members of the 1C bundle.

Ask for authentication requirements only when the selected connection needs them. Request the client's supported environment/secret reference, not a token pasted into tracked files. Preserve existing auth settings and keep secrets out of reports, `USER-RULES.md`, memory notes and version control. Never forward credentials from an old endpoint to a changed host without confirming that they belong to the new service.

If no memory provider exists, skip that branch and continue MCP setup. Do not install memory or treat its absence as an installation request. An explicitly skipped server is left untouched, not deleted or disabled.

## 3. Resolve project and memory scope

**Search indexes.** A successful connection does not prove that Graph or Code Metadata contains this repository. Load `content/rules/multi-contour-search.md` and, for a base with extensions, `content/rules/extension-workspace.md`. Before using 1C tools, load `content/skills/mcp-1c-tools/SKILL.md` and the operation skill it selects. Discover actual project IDs, layers, indexed roots and freshness through the exposed read-only tools; match them to the project's configured source roots. Do not derive a project ID from the repository folder name or reuse another project's index merely because its URL responds.

Persist only verified mappings using the existing contour-catalog contract; reference its path from `USER-RULES.md`. If the new project is absent from an index, complete independent connections and report indexing/registration as pending operator work. Do not change a shared server's source path, overwrite registry rows, or mark unverified contours as covered.

**Memory.** Follow `content/rules/project-memory.md` and `content/skills/mcp-1c-tools/docs/memory-providers.md`. Configure the existing permitted providers selected by the user, preserving other memory connections. Read the live schema rather than assuming every provider has Cognee's parameters.

- Cognee: reuse its actual MCP endpoint and existing `cognee-memory`/`cognee` entry; do not duplicate aliases known to share one store. Distinguish the MCP URL from a backend API URL — neither a health page nor a REST API base is automatically an MCP endpoint. Reuse an established dataset; when several datasets could belong to this repository, ask which to use. Pass dataset scope through supported memory-tool arguments, not invented MCP config keys. Durable `remember` calls omit `session_id`.
- OpenViking: reuse its actual endpoint and authenticated identity. Scope retrieval to the established project URI when supported by the live schema. Do not fabricate a workspace URI or change the service's shared storage directory. Its `remember` payload follows the provider contract, not Cognee's signature.
- Templates MCP: an existing selected connection may also expose project memory. Preserve that connection and its established scope. When the server cannot isolate a project through supported arguments, include the repository identity in queries and notes and explicitly report that this is a shared store, not access isolation.

Do not create a new server-side dataset or memory root merely to run setup. With no established dedicated scope, use the confirmed existing store and an explicit repository identity in notes/searches; ask if the user requires a separate dataset instead. Never claim that a naming convention prevents cross-project access.

Write the confirmed memory routing context into a small project-owned block in `USER-RULES.md`, between `<!-- setupmcp:memory -->` and `<!-- /setupmcp:memory -->`. Record repository identity, selected provider IDs and confirmed dataset/URI or shared-store scoping. Preserve text outside the block and unrelated entries inside it; conflicting existing instructions require clarification. Keep this separate from the external installer's `mcp:install_forme` block. Add no secret values or unsupported `.dev.env` keys. If memory was skipped, leave the memory block unchanged.

## 4. Merge project connections

Before writing, state the target files and selected connection changes with secrets redacted. The `/setupmcp` request authorizes this repository-scoped setup; do not ask for a second generic approval of already supplied endpoints. Read each edit target immediately before modifying it and keep a recoverable pre-edit copy outside tracked files. Abort a malformed or concurrently changed config instead of rebuilding it from defaults.

Merge only the selected server entries using the active adapter's native JSON/JSONC/TOML format, preserving unrelated keys, entries, auth references, disabled state and supported per-server options. For an existing ID, change only the requested fields. Do not replace the whole MCP map, regenerate the static catalog, or run `install.ps1 init|update` / `/updaterules` to apply custom endpoints. Preserve JSONC comments and TOML tables through a format-aware or surgical edit; never parse JSONC as plain JSON and silently discard content.

Use project paths: for example `.cursor/mcp.json`, `.mcp.json`, root `opencode.json`, `.kilo/kilo.json`, `.codex/config.toml` — exactly as the adapter declares. Preserve client-specific shapes and OpenCode's `onec-` ID mapping from `/installmcp` Step 7. If the client has no project MCP support, explain that limitation and leave its global config unchanged; do not invent a project file or silently broaden setup to all repositories.

Reuse inherited global entries that already work for this project; do not copy them into project config just to make a local list complete. A project-specific endpoint may override an inherited ID only where the client's documented precedence supports it. If an existing local entry conflicts with the selected inherited endpoint, resolve that entry explicitly so it cannot continue shadowing the intended server.

**External ownership exception:** automatic rules installation/update still leaves all external MCP configs untouched. An explicit `/setupmcp` run may merge selected connections into the current repository's client config only. Preserve the external global config, manifest, project registry, assigned server IDs/ports and the `mcp:install_forme` cache. For registry-owned connections, reuse the current project's resolved endpoints; a conflict with those endpoints requires resolving the owner mapping before editing that entry. A client file outside the repository remains read-only. Missing project registration remains pending; do not copy another registry row or flip `integrations.mcp.mode` to bypass ownership.

Treat these connection edits as user customization for future rules updates. Preserve `.ai-rules.json` installation hashes so a later update detects the modified config; do not rewrite hashes to make custom endpoints appear to be the shipped defaults. Re-running `/setupmcp` with the same inputs should produce no config or memory-context diff.

## 5. Verify and report

Parse the saved files with the corresponding format parser and check the final diff: only the selected connections and project context should change, with no duplicate tables/IDs or unresolved placeholders in newly configured entries. Confirm auth references resolve without displaying their values.

Check the selected endpoints with bounded, read-only probes and the client's MCP connection status. A normal HTTP response, 405 from an MCP URL, or a health response alone is not proof of an initialized MCP session; 401/403 means authentication remains unresolved. Do not change authentication or install/restart services to turn a failed probe green. Use `/checkmcp`'s read-only checks for selected 1C servers, without its install/start branches; test memory providers separately.

For memory, verify read availability in the confirmed scope and write-tool exposure independently. When live tools are callable, store one harmless, uniquely identifiable setup note in the intended project scope and retrieve it, following the provider's indexing/status contract. The note may remain as the setup record; never delete a shared dataset or memory root as test cleanup. Do not repeat this write on an unchanged successful rerun. Respect `TOOL_*=off`: report ordinary memory use as disabled unless explicitly overridden for this setup check. A missing write tool or unconfirmed write is not a successful memory setup.

If the client needs a reload/restart before new tools appear, report the files as configured and runtime verification as pending, with one restart instruction at the end. Do not claim completion of the MCP or memory smoke check from old session tools belonging to a different endpoint or scope.

Report concisely in Russian: current repository and client, every changed file, connected/reused/skipped servers, memory provider and project scope, actual connection/read/write checks, and unresolved indexing/auth/reload work. HTTP reachability, session tools and verified project coverage are separate results. Include the `Memory:` evidence line when applicable.
