---
description: Shared TOOL_* policy and runtime availability. Load before selecting any governed tool, including memory; operation-specific routing and recovery stay with their owners.
alwaysApply: false
category: tooling
---

# Tool policy and runtime availability

All availability-driven routing checks BOTH policy and runtime. **Exposed** describes the live tool schema; exposure alone never overrides policy. Before selecting tools, read applicable `TOOL_*` keys in `.dev.env` (names — *Keys* below). Commands, skills and subagents inherit this filter, including instructions phrased as «when exposed/connected».

- `auto` (missing / empty default): use eligible tools; on absence or failure follow the operation's documented fallback.
- `off`: do not call, probe, recommend installing, or bypass the provider through aliases, HTTP or CLI. Record `disabled by policy` when it affects required evidence; then use the documented fallback.
- `required`: when task/depth/routing selects this provider, it must supply the needed capability. Missing tools, failed calls or unsuitable scope block that step; alternatives can gather context but cannot satisfy it. Continue independent work. Do not downgrade or auto-install. This does not invoke unrelated providers, inactive workflows or already-unneeded fallbacks.
- An invalid non-empty value leaves that provider's dependent step blocked until corrected; never interpret a typo as permission. Settings are case-insensitive. Installation/status commands may inspect a disabled tool on explicit request; installation does not change policy. A specific user override applies only to its stated scope.

For existing projects, use the value of `TOOL_WINDOWS_MCP` for `TOOL_AGENT_DESKTOP` when the new key is absent. Both installer channels carry the old choice forward. An explicit new value takes precedence.

Runtime evidence is operation-specific: MCP tools must be callable in this session; CLI tools must already exist and run; read and write capabilities are separate. Config entries, healthy endpoints and `required` do not prove capability. Select verified project/layer/IB scope and check freshness before relying on results. Tool failures follow the selected operation's recovery contract; memory uses `project-memory.md`, 1C tools use `mcp-policy.md → C. Server answers → actions`. Re-evaluate after policy, session or target changes; pass policy and evidence to children, which check their own exposed tools.

These switches select execution paths, never waive hard gates. `auto`/`off` fallbacks keep their own limitations: unavailable standards stay unverified/blocked, missing validators require compensating checks, memory falls back locally, metadata/IB/repository tooling gates remain. `USE_EDT` and `UI_TESTING` still decide whether those workflows apply; a tool flag cannot activate them. Report relevant gaps with policy, capability and consequence, distinguishing disabled, absent, failed and wrong/stale scope.

## Keys

Missing / empty = `auto`; the installer appends missing keys as `auto` without overwriting choices. No per-task questionnaire. No key switches off the shipped metadata / IB / repository procedures; `rtk` is a user-global shell proxy (`/install-rtk`), not project tool routing.

| Parameter | Provider / capability |
|---|---|
| `TOOL_COGNEE` | Cognee memory, including `cognee-memory` aliases |
| `TOOL_OPENVIKING` | OpenViking memory/context |
| `TOOL_TEMPLATES` | `1c-templates-mcp`: both code templates and memory |
| `TOOL_GRAPH` | `1c-graph-metadata-mcp`: indexed project discovery and impact |
| `TOOL_CODE` | `1c-code-metadata-mcp`: code/metadata/form search and XML validation |
| `TOOL_DOCS` | `1C-docs-mcp`: platform help, routed standards and formats |
| `TOOL_SSL` | `1c-ssl-mcp`: БСП APIs |
| `TOOL_SYNTAX` | `1c-syntax-checker-mcp`: syntax validation |
| `TOOL_CHECKER` | `1c-code-check-mcp`: code checks, reviews, AI/ITS tools |
| `TOOL_DATA` | `1c-data-mcp`: live-IB checks |
| `TOOL_EDT` | EDT-MCP; workflow still requires `USE_EDT=true` |
| `TOOL_AGENT_BROWSER` | agent-browser, MCP and CLI |
| `TOOL_BROWSER` | Active client's built-in browser tools and saved UI test runners |
| `TOOL_AGENT_DESKTOP` | Vercel Labs agent-desktop for native windows |
| `TOOL_QA` | `1c-qa` (QA MCP): UI checks in the 1C thin client |
| `TOOL_UI_TEST` | Optional `MCP_Test` / `1C Visual UI Test` |
| `TOOL_CONVERSION` | `1c-kd20` (KD20): «Конвертация данных» 2.0 exchange rules and read-only EnterpriseData checks; installed separately |
