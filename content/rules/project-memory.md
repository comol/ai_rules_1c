---
description: Project memory — Cognee-first writes, OpenViking and templates fallback, search across all connected memory providers, recall-first and correction-capture gates, the strict memory.md layer and failure handling. Load at the start of any non-trivial 1C task and in every turn where the user corrects you or states a standing condition.
alwaysApply: false
category: workflow
---

# Project memory

Two layers. Every project-specific fact worth keeping lands in one of them, otherwise it is lost between sessions. This file is the single owner of the memory rules; `AGENTS.md` carries only the two gates in one line each.

## Two layers

- **`memory.md`** (project root, strict long-term store) — only rules that are **all** of: global (whole project), critical (violation = production breakage / data leak / regulatory issue), stable (does not change task-to-task), non-derivable (cannot be inferred from `AGENTS.md`, `USER-RULES.md`, or official docs). No TODOs, temporary agreements, style notes, or subsystem-scoped rules. Entry format is documented inside the file itself.
- **Connected MCP memory** — the store for everything else: user corrections during work, non-obvious project facts, recurring errors and their fixes, naming and quirks of individual configuration objects, and **standing working conditions** — statements that shape future tasks, not just the current one («I am benchmarking the agent», «objects from task statements may not exist in the configuration», «always prefer built-in platform mechanisms»). Test: *would the next session behave differently if it knew this?* If yes and it is not already in the rules — save it now; deferring loses it. Select the write provider and search scope below.

## Provider routing

These rules are automatic from the tools exposed in the current session; do not ask the user to pick a primary store on each task. A configured MCP entry alone is not a connection. Detect read and write capabilities separately, by server namespace and live tool schema, not by an unqualified tool name. Cognee may be named `cognee` or `cognee-memory`; OpenViking may have its own client-specific alias. Treat aliases as one provider only when they are known to reach the same store.

- **Write priority: Cognee → OpenViking → `1c-templates-mcp`.** When Cognee is connected and writable, save there first as the primary memory. Without Cognee, use connected OpenViking. If neither is connected, use templates MCP memory. One successful durable write is sufficient; routine notes do not need to be copied to every store.
- **Search every connected memory provider.** Query Cognee, OpenViking and templates MCP whenever each exposes a memory-search tool, including templates MCP when a primary provider is connected. Do not stop at the first hit. With Cognee and OpenViking connected, use both; OpenViking alone does not make an absent Cognee callable. Use the same task scope across providers, merge relevant results and deduplicate equivalent notes, retaining provider and note ID/URI attribution. Independent searches may run in parallel. A failed provider makes coverage partial; it does not suppress the others.
- **Calls:** Cognee `recall(query=..., search_type="CHUNKS")` / `remember(data=...)` (omit `session_id` for durable notes); OpenViking `search(query=...)` or `find(query=...)` / `remember(messages=...)`; templates `recall(query=...)` / `remember(content=...)`. `recall` and `remember` elsewhere in the rules are logical memory operations routed here, not a requirement to select a particular server. Use the live schema for version-specific names and parameters; details: `content/skills/mcp-1c-tools/docs/memory-providers.md`.
- **Queries are vector searches — one topic per query.** Never concatenate the task terms with the standing-conditions phrase (`working conditions benchmark conventions НачислениеЗарплаты Премия …` returned vacation-calendar notes in every analysed session). Send the task query with the object / subsystem / error terms only, and the standing-conditions query verbatim as its own call. A Cognee answer in a completion mode (`GRAPH_COMPLETION`, `RAG_COMPLETION`) is generated prose; when it names no project identifier it is «nothing relevant», not a fact to carry forward — that is why `search_type="CHUNKS"` (raw stored notes) is the default here.
- **Scope:** use an established project dataset/namespace when supported; otherwise include the project identity in queries and notes. Keep global working preferences distinguishable from project facts. Ignore hits from unrelated projects. Memory is context, not authority over current user instructions or verified project sources.

## Gates (hard)

1. **Recall-first.** For any non-trivial 1C task, search all connected memory providers with the task's key terms (object name, subsystem, error text) **before** solution design — same standing as `templatesearch`. On the session's first non-trivial task also query the standing conditions — a **separate** call with the fixed phrase `working conditions benchmark conventions`, sent to the primary write provider only (Cognee when connected, otherwise OpenViking, otherwise templates memory): standing conditions are saved there first, so the other providers add nothing on that query. Budget: one task query per connected provider plus that one standing-conditions call; a repeat with different wording is allowed only when the first answer was empty. Skipping an exposed memory-search provider on the task query is a defect; so is a merged query.
2. **Correction-capture.** A turn in which the user corrected your output, rejected an approach, clarified a non-obvious fact, or stated a standing condition is **incomplete** until that fact has been saved in the same turn via the write priority or the documented fallback. Before ending such a turn ask: *did this message change how I or the next session should work? → saved?* Answering the correction while skipping the save is a defect even when the reply is right.
3. **Memory line.** The final answer of a non-trivial task states memory usage in one line: `Memory: searched <providers>; recalled <n> relevant notes / nothing relevant; saved <n> notes to <provider> / nothing to save; <partial coverage or fallback, if any>`. Distinguish a durable save from pending indexing or an unconfirmed write. It makes silent skips visible.

Routing of what gets saved: project **facts** → plain memory notes; **behaviour / process** corrections and rule friction → notes prefixed `rule-friction:` (consumed by `/evolve`, see `AGENTS.md → Rules self-improvement`). Do not edit the rules as an unsolicited reaction to a correction; explicit maintenance of this source ruleset remains authorized work. Only `/evolve` writes `LLM-RULES.md`.

## Availability and fallback

Current templates MCP `remember` is always registered and requires no operator bearer token or write-tools opt-in; do not preflight it as an administrative mutation. On older deployments follow the exposed schema and an actual call result. When the selected provider has no write tool, is offline or definitively rejects the write (including an observed `mutation_auth_required` from an older deployment), try the next connected writable provider in priority order and report the fallback. Continue searching any provider whose read tool still works. Do not loop on a failing call, expose credentials or silently bypass missing MCP tools with a new HTTP/CLI connection.

If no MCP provider can save the note, append even small particular-case corrections as **dated entries** directly to `memory.md` (eligibility is temporarily relaxed). Record the intended provider and migrate to the highest-priority available memory once it returns; remove the fallback entry only after durable storage is confirmed.

A timeout or ambiguous write response is **unconfirmed**, not a rejection: check the returned ID/status if available before another write. Templates MCP can return `stored=true`, `index_pending=true` and an `id` despite `success=false`; that is already durable, so do not send it again or write a fallback copy. If an ambiguous outcome cannot be resolved, retain a dated local entry marked `write unconfirmed`, including provider/ID when available, for reconciliation before migration. Pending indexing is not proof that data was lost.

## Note format

English narrative, one self-contained fact per note, original 1C identifiers and object / module names preserved as-is. No secrets, no PII. Include project scope and the source/date for corrections. Update an existing note when the provider exposes a precise edit operation; otherwise save a correction referencing the old note rather than inventing an update API or deleting a whole dataset. Record confirmed approaches as well as corrections — «this pattern worked and why» is as valuable as «do not do this».

## Promote / demote

A memory note that later proves to meet all four `memory.md` criteria is promoted to `memory.md`. Remove its old copy only when precise note deletion is available; otherwise retain its ID/URI as superseded. Never delete a dataset or an unrelated memory directory to retire one note. Migrations and pre-existing copies across providers are deduplicated during search.
