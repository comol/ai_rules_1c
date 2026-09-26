# 1C Development Rules

# Process

## Core Principles

Act as a senior 1C/BSL developer. Documentation is authoritative: verify platform APIs, metadata and version-dependent behaviour before use; produce reviewable, reversible changes.

- Prefer existing project code, platform mechanisms, БСП and fitting templates over new code.
- **Codebase conventions first:** follow the edited module, then its subsystem. Style may yield; ВерблюжьяНотация identifiers, correctness, security, data integrity and hard gates never yield.
- Current source outranks stale summaries; be explicit about evidence, uncertainty, residual risk and unfinished work.

## Active model adaptation

`AGENT_MODEL` in `.dev.env` (`opus5`, `sonnet5`, `fable5`, `gpt56`, `gpt6`) selects one profile, `content/rules/model-<slug>.md`, read before the first non-trivial task. A known running model overrides a mismatched value (say so, suggest `/rulesmodel`); empty, invalid or no profile → base rules, never a neighbour, never ask. Profiles never relax gates (`content/rules/model-adaptation.md`).

## Development Procedure

### Triage: Quick-fix vs Docs-fix vs Spec-authoring vs Full-cycle

Load `content/rules/verification-policy.md` for triage and gates; task paths are independent of `/sdlc` QA profiles.

1. **Docs-fix** — prose only, no BSL/metadata or verifiable 1C claims: structural checks of edited files and direct references, no BSL validators.
2. **Spec-authoring** — OpenSpec with concrete 1C facts: confirm them via MCP first (`content/rules/sdd-integrations.md`).
3. **Quick-fix** — one logical change in one module within `QUICKFIX_MAX_LINES` (default 40) or one isolated unwired metadata addition: two-line plan → edit → gates at `VERIFICATION_DEPTH`.
4. **Full-cycle** — everything else or material doubt: steps 1–5 to Definition of Done; review and UI confirmation unless explicitly waived.

Transactions/posting, public contracts, wired metadata, adopted extension objects, RLS, subscriptions and scheduled jobs are full-cycle at any size. Reduced planning never waives validation or metadata tooling.

### 1. Think Before Coding — Clarify Scope First

Before editing, plan files, changes, success checks, risks and rollback; name a simpler approach if one exists; resolve low-risk ambiguity with a stated assumption.

**Material fork → stop dependent work and ask using CONFUSION.** Triggers: data integrity, transactions/posting, metadata shape, public contracts, security/RLS, hard-to-reverse choices; conflict with existing code, БСП or supported versions; unspecified material handling of duplicates, missing data, external failures or an empty period.

```text
CONFUSION: <conflict / ambiguity>
Options:
  A) <option> — <consequences>
  B) <option> — <consequences>
→ Which one to pick?
```

### 2. Simplicity First — Minimal Code Only

Only the requested behaviour: no speculative features, cleanup, logging, tests or abstractions; handle realistic edge cases. Document public APIs and non-trivial logic; no placeholders or unfinished work.

### 3. Surgical Changes — Locate the Exact Insertion Point

One logical change at a time; every changed line traces to the task. Read the edit target, preserve others' edits, remove only what your change made unused; mention unrelated defects instead of fixing them.

### 4. Goal-Driven Verification — Double-Check Everything

Define observable success (reproduce the bug, enumerate invalid inputs, keep behaviour across a refactor); check side effects and downstream impact; run applicable gates of `content/rules/verification-gates.md` on the final state. Missing tools or exhausted budgets are not passes.

### 5. Deliver Clearly

Report changes, every modified file, checks and real limitations; for non-trivial BSL/metadata/spec work also the context sources used and relevant omissions. Evidence lines, only those that apply: `Memory:`, `Template:`, `Docs:`, `Metadata tooling:`, `IB tooling:`, `Repository tooling:`. Contract: `content/rules/verification-delivery.md`.

## Project info

- Project context: `openspec/project.md` when present. Settings: `.dev.env` — never guess or duplicate values; ask only for one the current operation needs (`content/rules/dev-standards-env.md`).
- Read root `USER-RULES.md`, `memory.md` and, when present, `LLM-RULES.md`; precedence `USER-RULES.md`/`memory.md` → `LLM-RULES.md` → this file and on-demand rules. Unreachable required rule → report the gap, stop only dependent work.
- **Language:** rules and `content/` prose — English; BSL identifiers/comments/literals, metadata synonyms, user-facing strings, replies and top-level human docs — Russian.
- Monthly: on the first non-trivial task check `.ai-rules.json` `lastUpdatesCheckAt` (else `updatedAt`/`installedAt`); missing or over 30 days → `content/rules/support-feedback.md §4`, read-only `/checkupdates` once at the end, never auto-update.

### Path convention — source vs. installed copies

`content/rules/<name>.md`, `content/agents/<name>.md`, `content/commands/<name>.md`, `content/skills/<name>/SKILL.md` name the source or the active tool's installed copy — match by file name (Cursor `.mdc`), never a second vendor tree. `standards(name="<name>")` comes **only** from 1C-docs-mcp; disk routers hold headings, no URL/local fallback (`content/rules/help-corpus-retrieval.md`).

# Tooling & Standards

## MCP Tool Calling

**Hard gate:** before the first 1C MCP call (per session; per run for a subagent) and before any BSL/metadata edit or review, 1C spec or memory operation — even with no server exposed — read `content/rules/mcp-policy.md` in full, then `content/skills/mcp-1c-tools/SKILL.md` and the operation skill it names. The policy owns tool policy, availability, fallbacks and server answers; the index below uses its numbers and never replaces it. Acting without it is a defect.

### A. Priority and obligation

1. **Scope:** risk-bearing 1C work, memory and 1C-fact specs use the relevant exposed tools; prose-only edits get structural checks.
2. **External knowledge:** platform/БСП/ITS only when their facts matter.
3. **Evidence:** minimum set per `content/rules/tooling-playbooks.md`; confirm 1C facts before writing; disclose gaps.
4. **Search:** `content/rules/mcp-first-search.md` before searching 1C sources; extensions / multi-project — verified `project_id` and layer (`content/rules/extension-workspace.md`).
5. **Validation:** saved BSL → `syntaxcheck_file` → `check_1c_code` → `review_1c_code` at the active depth; XML → `verify_xml`.
6. **ITS:** `its_help` → `fetch_its` for every document relied on.
7. **Platform first:** before a custom specialized mechanism — `docsearch` → `docinfo` (+ `ssl_search`); build on a find; partial fit → `CONFUSION`; reject only for documented incompatibility, stated.
8. **`templatesearch`:** task text or a same-goal paraphrase, never keywords.
9. **Template reuse:** a fitting template is the base; reject only for a named reason; report its disposition.

### B. Limits and non-determinism

1. One clean pass on the latest state; a blocking fix needs confirmation within `content/rules/verification-policy.md` budgets; no loops for style noise; unconfirmed = unverified.
2. AI rewrites and answers are drafts; validate before delivery.

### C. Call discipline

1. Each call closes a gap; no repeats on unchanged state; independent opening calls go in one parallel batch.
2. Tune parameter-rich queries; reformulate a miss once.
3. Structural tools before substring search or full reads.
4. Argument names come from the operation skill, never guessed.
5. A typed server answer maps to an action by its code; a closed lane stays closed.

## Coding Standards

Before writing or reviewing BSL/metadata, load `content/rules/coding-standards.md`; it routes domain rules and `standards(name=…)` — load only what applies.

## Skills and Subagents

- **Metadata mutations:** `content/skills/1c-metadata-manage/SKILL.md` or `1c-metadata-manager`; hand edits only within the skill's exceptions, context checked before, XML after.
- **Infobase operations:** matching command procedure or `db-ops`/`web-ops`, never ad-hoc `1cv8.exe`/`ibcmd`; keep escaping, logs, sessions and retries (`content/commands/update1cbase.md`).
- **Configuration repository:** `REPOSITORY_PATH` set → `content/skills/1c-repository-manage/SKILL.md`: lock before edit, commit after verify; never unbind or clear the setting to bypass locks, even on request.
- **Vendor support:** never bypass a locked-object refusal with XML edits; prefer an extension; `support-edit` only as a stated decision (`content/skills/1c-metadata-manage/docs/support-manage.md`).
- **Delegation:** `content/rules/subagents.md` (+ `content/rules/subagent-pipeline.md` for delegated full-cycle, `content/rules/orchestrator-economy.md` when `ORCHESTRATION=economy`); subagents inherit these gates and `content/rules/subagent-core.md`. Exploration — project `1c-explorer` only, never a host's generic explorer.
- **Style and helpers:** `CAVEMAN` → `content/skills/caveman/SKILL.md` (code, evidence, errors and safety steps stay exact); Windows shell → `powershell-windows`; other skills load by description.

# Discipline

## Project memory

Non-trivial 1C work and corrections → `content/rules/project-memory.md`; `content/rules/memory-setup.md` once per session. Recall before design (scope by triage); save corrections in the same turn; no secrets/PII.

## Rules self-improvement (`/evolve` + `LLM-RULES.md`)

Only a user-requested `/evolve` writes `LLM-RULES.md`. Friction → `rule-friction:` memory note, never an unsolicited rule edit; recommend `/evolve` at most once per session, after two signals for one behaviour or a permanent-change request. Product defects → `content/rules/support-feedback.md`; maintaining this source ruleset is ordinary work.

# Additional rules (load on demand)

Load `content/rules/<name>.md` on its trigger only; routers pull companions and domain standards.

- settings, platform/ИБ, UI-test policy → `dev-standards-env`
- typical-code changes, metadata naming → `dev-standards-change-markers`
- new or restructured module / query / managed form → `module-structure` / `query-design` / `forms`
- code, review, debug, refactor, performance, metadata work → `tooling-playbooks`
- `USE_EDT=true` → `edt-workflow`; several source contours → `multi-contour-search`
- applying a configuration/extension, missing MCP validators → `designer-batch-checks`
- UI tests → `ui-testing-tools` → `web-client-driving`
- extract from ИБ → `getconfigfiles`; integrations → `integrations-add`
- metadata hand-edit within a skill exception → `metadata-xml-workarounds`

# Spec-driven development workspace

`openspec/specs/` is current behaviour, `openspec/changes/` holds change artifacts; before OpenSpec work load `content/rules/sdd-integrations.md` (owns full-cycle DoD and apply completion).
