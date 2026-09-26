# Rules rationale — evidence behind specific rules

Maintainer-only notes. The installer does not ship `tools/`, so nothing here reaches an agent's
context. Rules state the obligation and, where it helps compliance, a one-clause consequence;
the measurements and incidents that motivated a rule live here instead of being re-read on every
load. When a rule changes, update or drop its entry.

| Rule (owner) | Observation that motivated it |
|---|---|
| Argument names come from the operation skill; schema fetch at most once per tool per session (`content/rules/mcp-policy.md → C. Call discipline and server answers`, item 4) | In the analysed sessions 20 of 60 MCP calls were schema lookups that changed nothing. |
| Schema and project lookups are not repeated per call (`content/skills/mcp-1c-tools/docs/1c-graph-metadata-mcp.md`, *Schema lookups are not free*) | The analysed sessions spent a third of all calls on schema and project lookups that returned nothing new. |
| A lane closed by the server stays closed (`content/rules/mcp-first-search.md → Hard rule`, item 3) | The analysed sessions spent ten graph calls each proving one `tabular_part_columns_not_indexed` / missing-index warning through sibling tools. |
| Memory queries are one topic per query (`content/rules/project-memory.md → Provider routing`) | The merged query `working conditions benchmark conventions НачислениеЗарплаты Премия …` returned vacation-calendar notes in every analysed session. |
