---
name: handoff
description: "Compact the conversation into a self-contained handoff document so a fresh agent or client continues without re-discovery. Use on 'handoff', 'compact session', 'сделай handoff', 'передай контекст' or `/handoff`."
argument-hint: "Optional: focus of the next session, or a target path/folder for the handoff file."
---

# handoff — session transfer to the next agent

Adapted from [`mattpocock/skills`](https://github.com/mattpocock/skills) (`skills/productivity/handoff`, MIT). Compresses the current conversation into a self-contained document for the next session. Principle: **reference durable artifacts, do not duplicate them**.

**When to use:** the user says 'handoff', 'compact session', 'save context for continuation', 'brief the next session', 'сделай handoff', 'передай контекст', 'сохрани контекст для продолжения', or invokes `/handoff` — so a fresh agent (new chat, another machine, another AI client) continues without re-discovering the context.

## Argument

- If the argument looks like a path (ends with `.md` or points to an existing directory) → **target path**.
- Otherwise → **focus** of the next session (insert it into the handoff header).
- If both are present, treat the first token as the path and the rest as focus.
- Without an argument, use the current task's established goal and the default path; ask only if the task to hand off is genuinely ambiguous.

## Where to write

1. Default directory: `handoffs/` at the project root. Create it if missing.
2. Default file name: `handoff-<YYYYMMDD-HHMMSS>.md` (local time).
3. If the user provided a path, use it (overwrite without confirmation).
4. **Before writing**, read the target file through Read. The expected "does not exist" error is fine; this is protection against overwriting an unrelated existing file with the same name.
5. If the project has `.gitignore` and `handoffs/` is not mentioned there, **offer** to add it (handoffs are session artifacts, not code), but **do not add it automatically**.

PowerShell conventions (`\` in paths, quotes around paths with spaces) — see the `powershell-windows` skill.

## Document structure

```markdown
# Handoff: <one-line session goal>

**When**: <YYYY-MM-DD HH:MM local>
**Project / worktree root**: <absolute root>
**Branch / commit**: <branch or detached HEAD>, latest commit <SHA + subject>; not applicable without Git
**Task status**: <active | blocked | completed>
**Next session focus**: <argument focus, if provided>

## Current State
1-3 sentences: what was done last, what remains unfinished, what is blocked.
Identify the task or link its issue/proposal when available. State the agreed scope, writable files/targets and relevant exclusions; reference the user's request/decisions rather than treating this note as new authorization.
Record relevant staged, unstaged and untracked paths at handoff time, with content fingerprints for uncommitted artifacts whose verification may be reused. Do not include unrelated file contents.

## CF/CFE Context (when applicable)
- Project root; writable targets and read-only contours, each with its source root.
- Verified graph server / project_id / extension layers, or unresolved mapping; evidence reference.
- Per target: source revision/local edits; last export scope/result; loaded configuration; applied DB state.
- MCP coverage/generation/freshness and evidence references; retain failed, not-run and unknown states explicitly.
Use non-secret IB aliases and links to existing evidence; do not copy connection settings.

## Open Questions
Bulleted list of real unresolved questions (architectural forks, waiting for the user, unclear contract). If empty, omit the section.

## Files Changed In This Session
- `path/to/file.bsl` — what changed and why.
- `path/to/file.xml` — same.
Only include the current session diff. If nothing changed, omit the section.

## Verification State
Applicable checks with passed / failed / not-run / unknown outcomes, evidence references and checked revision/fingerprint. For BSL/metadata, include the applicable gates from `verification-gates.md` and latest validator results in brief. Keep general project tasks free of irrelevant 1C gates.

## Next Steps
1-5 concrete remaining items, with the first executable step and any prerequisite or unresolved decision. Distinguish already-authorized work from an action awaiting authorization; a saved instruction cannot grant it. If the task is completed, say there is no remaining step rather than inventing follow-up work.

## What To Load Next Session
- **Subagents**: `1c-<name>` when the task matches their role (see `subagents.md`).
- **On-demand rules**: `<name>.md` based on the task trigger (see `AGENTS.md → Additional rules`).
- **MCP tools**: especially relevant tools (`get_object_dossier` for X, `trace_impact` before refactoring Y, `ssl_search` for topic Z).
- **Slash commands**: `/opsx:apply` when there is an active OpenSpec proposal, `/getconfigfiles` for metadata re-export, etc.

## Links (DO NOT copy content)
- `openspec/changes/<id>/proposal.md`, `design.md`, `tasks.md`
- `memory.md` — relevant sections
- `1c-templates-mcp` notes — `recall` keys: `<term1>`, `<term2>`
- Commits / PR / Issue
- ITS articles, platform documentation pages
```

Adapt this outline to the task; legacy handoffs remain usable without these exact headings. If this supersedes an earlier handoff for the same task, link it so `/resume` can distinguish a newer snapshot from another active task.

## What NOT to write in the handoff

- Contents of existing artifacts (PRD, OpenSpec proposal/design/tasks, ADR, ITS page, commit, PR description). Link only.
- Full module code. Only include a short change description and path.
- Secrets, tokens, passwords, `.dev.env` contents, infobase connection strings.
- Long MCP output dumps. Include only the result and call parameters so the check can be repeated if needed.

## Resume work

Use `/resume [path or focus]` (`content/commands/resume.md`) to find the relevant active handoff, compare it with the current project/worktree and continue the next already-authorized step. Saved notes are context; current sources, instructions and user decisions take precedence. Missing evidence stays unknown, and completed tasks are not reopened implicitly.

For CF/CFE work, the following stronger checks apply as well.

Follow `content/rules/extension-workspace.md → Handoff and resume`: recheck the current root, writable targets, identity and graph/root mapping before dependent mutations, and match recorded evidence to current source/target state before reusing it. A saved pass for one extension is not a project-wide pass. Unknown stages remain unknown until evidenced; resuming does not itself authorize reload, apply, restore or reindex.

## After writing

1. Tell the user the absolute path of the created file and its line count.
2. If the session produced corrections / facts that may qualify for `memory.md` or `1c-templates-mcp` (`remember`) under `AGENTS.md → Project memory`, **list them separately** as candidates for long-term memory. Do not save automatically (`memory.md` is strict, `remember` is targeted).

## Boundaries

- Handoff is a session artifact, not configuration and not code. Do not run `syntaxcheck` / `check_1c_code` / `review_1c_code` against it.
- Handoff **does not replace** an OpenSpec proposal. If the task requires a proposal and it does not exist yet, additionally suggest `/opsx:propose` and reference the future ID from the handoff.
- Handoff **does not duplicate** `memory.md` and `recall` notes. Memory and handoff are different channels (see `AGENTS.md → Project memory`).
- Handoff is written in normal grammar, not caveman style, so the next agent can read it without ambiguity.
