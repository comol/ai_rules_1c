# Memory

This file is the working project memory for AI agents.

Eligibility, routing between this file and `1c-templates-mcp` (`remember` / `recall`),
fallback when the MCP server is unavailable — see `AGENTS.md → Project memory`.
There are no permanent entries yet.

Entry format (one entry = one self-contained rule). Use English for narrative,
preserve original 1C identifiers (objects, modules, attributes) as-is:

<!--
## YYYY-MM-DD — <short rule title>

- **Scope:** module / subsystem / object where the rule applies (e.g. `Документ.РеализацияТоваровУслуг`).
- **Rule:** what must / must not be done.
- **Why:** consequence of violation (production breakage / data loss / regulatory / data leak).
- **Source:** user request, incident, or external document that established the rule.
-->

## Captured during work (no remember available)

- 2026-07-23 — rule-friction: with the ruleset installed, the agent hand-edited forms/layouts and did not use the `1c-metadata-manage` skill or form/metadata MCP tools; it admitted this only when the user asked ("skills и mcp для макетов использовал?"). User states skill/MCP usage for forms and metadata generation is very important. Ruleset hardened same day: the skill is now a hard gate (defect on hand-edit) in `AGENTS.md → Skills and Subagents`, `SKILL.md → Hard rule`, `tooling-playbooks.md` (skill as Step 0), `forms.md`/`forms-add.md`, `verification-gates.md → Gate 5`, `subagents.md → Common obligations` + agent footers. Watch whether the gate holds in future sessions; second episode → recommend `/evolve`.
- 2026-07-23 — rule-friction (second episode, same behavior class — skills/commands bypassed): during a DB update the agent used neither the `1c-metadata-manage` `db-ops` scripts nor the `/update1cbase` command (ad-hoc command lines instead), and had no iterative failure handling. User requires: read the update log for errors after each attempt, terminate the Configurator on failure, fix causes, retry from scratch. Ruleset hardened same day: infobase-operations hard gate added (`AGENTS.md → Skills and Subagents`, `SKILL.md → Hard rule`); canonical "Update retry loop" written in `update1cbase.md` (log-first, PID-scoped kill, fix-before-retry, 3-attempt budget) and mirrored in `deploy-and-test.md`, `db-manage.md → Update retry discipline`, `tester.md`. Two episodes accumulated → `/evolve` recommended to the user.

