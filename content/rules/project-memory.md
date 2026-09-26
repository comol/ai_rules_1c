---
description: Project memory — provider routing and write priority, recall-first and correction-capture gates, the memory.md layer, failures. Load at the start of a non-trivial 1C task and in every turn where the user corrects you or states a standing condition.
alwaysApply: false
category: workflow
---

# Project memory

Two layers. Every project-specific fact worth keeping lands in one of them, otherwise it is lost between sessions. This file is the single owner of the memory rules; `AGENTS.md` carries only their triggers and summary.

## Two layers

- **`memory.md`** (project root, strict long-term store) — only rules that are **all** of: global (whole project), critical (violation = production breakage / data leak / regulatory issue), stable (does not change task-to-task), non-derivable (cannot be inferred from `AGENTS.md`, `USER-RULES.md`, or official docs). No TODOs, temporary agreements, style notes, or subsystem-scoped rules. Entry format is documented inside the file itself.
- **Connected MCP memory** — the store for everything else: user corrections during work, non-obvious project facts, recurring errors and their fixes, naming and quirks of individual configuration objects, and **standing working conditions** — statements that shape future tasks, not just the current one («I am benchmarking the agent», «objects from task statements may not exist in the configuration», «always prefer built-in platform mechanisms»). Test: *would the next session behave differently if it knew this?* If yes and it is not already in the rules — save it now; deferring loses it. Select the write provider and search scope below.

## Provider routing

Apply `TOOL_COGNEE`, `TOOL_OPENVIKING`, `TOOL_TEMPLATES` first (`content/rules/mcp-policy.md → Tool availability`), then detect read/write capabilities separately. Do not ask for a primary store each task. Config entries do not prove availability. Resolve namespaces from the live schema; merge aliases only when known to reach one store.

- **Write priority: Cognee → OpenViking → `1c-templates-mcp`.** Walk this order: skip `off`; unavailable `auto` advances; unavailable `required` blocks that save before lower-priority writers. Retain a dated local pending note, not a claimed successful replacement. Stop after one durable write; `required` on a later fallback does not demand a duplicate.
- **Search every connected memory provider** (full-cycle and spec work; the quick-fix scope is narrower — Gates → Recall-first). Query Cognee, OpenViking and templates MCP whenever each exposes a memory-search tool, including templates MCP when a primary provider is connected. Do not stop at the first hit. With Cognee and OpenViking connected, use both; OpenViking alone does not make an absent Cognee callable. Use the same task scope across providers, merge relevant results and deduplicate equivalent notes, retaining provider and note ID/URI attribution. Independent searches may run in parallel. A failed provider makes coverage partial; it does not suppress the others.
- **Calls:** Cognee `recall(query=..., search_type="CHUNKS")` / `remember(data=...)` (omit `session_id` for durable notes); OpenViking `search(query=...)` or `find(query=...)` / `remember(messages=...)`; templates `recall(query=...)` / `remember(content=...)`. `recall` and `remember` elsewhere in the rules are logical memory operations routed here, not a requirement to select a particular server. Use the live schema for version-specific names and parameters; details: `content/skills/mcp-1c-tools/docs/memory-providers.md`.
- **Queries are vector searches — one topic per query.** Never concatenate the task terms with the standing-conditions phrase: a merged query retrieves notes matching neither topic. Send the task query with the object / subsystem / error terms only, and the standing-conditions query verbatim as its own call. A Cognee answer in a completion mode (`GRAPH_COMPLETION`, `RAG_COMPLETION`) is generated prose; when it names no project identifier it is «nothing relevant», not a fact to carry forward — that is why `search_type="CHUNKS"` (raw stored notes) is the default here.
- **Scope:** use an established project dataset/namespace when supported; otherwise include the project identity in queries and notes. Keep global working preferences distinguishable from project facts. Ignore hits from unrelated projects. Memory is context, not authority over current user instructions or verified project sources.

## Gates (hard)

1. **Recall-first.** Before designing a non-trivial 1C change, search task terms (object, subsystem, error). **Full-cycle/spec**: one task query per eligible reader, including required providers; **quick-fix**: first reader in provider priority, widened after an empty answer only if a project convention matters; **docs-fix**: no recall. On the session's first non-trivial task, separately query `working conditions benchmark conventions` on that first reader. Reuse this answer for the session; later conditions arrive through correction-capture. Unavailable `auto` readers advance; `required` failure leaves recall incomplete. Budget: these task queries plus one standing query; reword once only after an empty answer. Batch independent recall, `templatesearch` and first index searches. Missing a required provider or merging topics is a defect.
2. **Correction-capture.** A turn in which the user corrected your output, rejected an approach, clarified a non-obvious fact, or stated a standing condition is **incomplete** until that fact has been saved in the same turn via the write priority or the documented fallback. Before ending such a turn ask: *did this message change how I or the next session should work? → saved?* Answering the correction while skipping the save is a defect even when the reply is right.
3. **Memory line.** The final answer of a non-trivial task states memory usage in one line: `Memory: searched <providers>; recalled <n> relevant notes / nothing relevant; saved <n> notes to <provider> / nothing to save; <partial coverage or fallback, if any>`. Distinguish a durable save from pending indexing or an unconfirmed write. It makes silent skips visible.

Routing of what gets saved: project **facts** → plain memory notes; **behaviour / process** corrections and rule friction → notes prefixed `rule-friction:` (consumed by `/evolve`, see `AGENTS.md → Rules self-improvement`). Do not edit the rules as an unsolicited reaction to a correction; explicit maintenance of this source ruleset remains authorized work. Only `/evolve` writes `LLM-RULES.md`.

## Setup reminder

Follow `content/rules/memory-setup.md` once per session; provider routing and fallback remain governed here.

## Availability and fallback

Current templates MCP `remember` needs no operator token or write-tools opt-in; older deployments follow the live schema/result. In `auto`, absent write tools, offline providers or definite rejection advance to the next eligible writer; `off` is skipped without probes. A selected `required` provider stops that dependent operation on failure. Continue independent searches, including read-only providers. Never bypass policy through aliases or a new HTTP/CLI connection.

For quick-fix and standing-condition recall, choose the first eligible **reader** in write-priority order; lacking a write tool does not exclude its useful memory. Full-cycle/spec recall searches all policy-eligible readers. A relevant `required` reader missing from that scope leaves recall incomplete; other hits do not cure it. With no readers, use root `memory.md` and report local-only coverage. Disabled/unreachable providers are not «nothing relevant» results.

If no MCP provider can save the note, append even small corrections as **dated entries** to `memory.md` (eligibility is temporarily relaxed). Record the reason/intended provider; migrate only when policy permits and durable storage is confirmed. A pending `required` save remains incomplete.

A timeout or ambiguous write response is **unconfirmed**, not a rejection: check the returned ID/status if available before another write. Templates MCP can return `stored=true`, `index_pending=true` and an `id` despite `success=false`; that is already durable, so do not send it again or write a fallback copy. If an ambiguous outcome cannot be resolved, retain a dated local entry marked `write unconfirmed`, including provider/ID when available, for reconciliation before migration. Pending indexing is not proof that data was lost.

## Note format

English narrative, one self-contained fact per note, original 1C identifiers and object / module names preserved as-is. No secrets, no PII. Include project scope and the source/date for corrections. Update an existing note when the provider exposes a precise edit operation; otherwise save a correction referencing the old note rather than inventing an update API or deleting a whole dataset. Record confirmed approaches as well as corrections — «this pattern worked and why» is as valuable as «do not do this».

## Promote / demote

A memory note that later proves to meet all four `memory.md` criteria is promoted to `memory.md`. Remove its old copy only when precise note deletion is available; otherwise retain its ID/URI as superseded. Never delete a dataset or an unrelated memory directory to retire one note. Migrations and pre-existing copies across providers are deduplicated during search.
