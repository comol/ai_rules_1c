---
name: meeting-to-tasks
description: "Turn a 1C project meeting recording or transcript into structured requirements, open questions, and draft OpenSpec change proposals."
---

# Meeting to Tasks & OpenSpec Proposals (Optional Pack)

Use this skill when the user provides a meeting recording (audio/video), transcript, or call notes and wants a structured task breakdown and draft `openspec/changes/` proposals for a 1C project.

## Workflow

1. **Obtain clean text:**
   - If the input is audio or video (`.mp3`, `.wav`, `.m4a`, `.mp4`, `.mkv`, `.webm`), run `content/skills/transcribe/SKILL.md` first to get a timestamped transcript.
   - If the input is already text / Markdown / `.docx` (use `officecli` for `.docx`), read it directly.
2. **Extract structured facts (separate facts from assumptions):**
   - **Decisions agreed** (who / what / constraint, with timestamp or quote).
   - **Actionable 1C tasks** (grouped by subsystem/object, priority, and estimated mode: `quick-fix` vs `full-cycle`).
   - **Open questions / ambiguities** (candidate `CONFUSION` items that must be clarified before coding — never invent business rules to fill gaps).
   - **Out of scope / deferred items** mentioned on the call.
3. **Confirm concrete 1C objects via MCP (when connected):**
   - Before drafting technical scope, look up mentioned catalogs, documents, registers, and reports in the project (`get_object_dossier` / `search_metadata_by_description`) so task names use real metadata identifiers rather than colloquial call nicknames.
4. **Present the task list for user approval BEFORE creating OpenSpec files:**
   - Show a concise table: `# | Task | Affected 1C objects | Open questions | Create OpenSpec change?`.
   - Ask which tasks should be turned into `openspec/changes/<slug>/` drafts.
5. **Draft approved OpenSpec proposals:**
   - For each approved task, load `content/rules/sdd-integrations.md` and `content/rules/sdd-propose.md` and generate clean `proposal.md` / `tasks.md` drafts with explicit DoD criteria and open questions preserved.
   - Never start `apply` (implementation) from this skill automatically.
