---
description: Active-model adaptation — how AGENT_MODEL in .dev.env selects a model profile (opus5 | sonnet5 | fable5 | gpt56 | gpt6), what a profile may and may not change, and the model-agnostic prompting baseline that always holds
alwaysApply: false
category: workflow
---

# Active model adaptation

**When to load this file:** when you need the routing / precedence contract of the model layer — the user runs `/rulesmodel`, a profile and a base rule appear to conflict, a profile is being edited, or `AGENT_MODEL` in `.dev.env` names a model other than the one you are running. **Not at session start:** for ordinary work the profile file (`content/rules/model-<slug>.md`) is self-sufficient; this file is the router, not the content.

## 1. What this layer is

The base ruleset (`AGENTS.md` + every on-demand rule) is written **model-neutral**: it states what must be verified, which tools are mandatory, and what the delivery report must contain — none of which depends on which LLM is executing it. Vendors, however, document behaviours that differ **per model**: default verbosity, how eagerly the model narrates, plans, delegates, re-verifies its own work, or takes unrequested action, and which effort / thinking settings that model actually respects.

A **model profile** is a thin delta that tunes those documented behaviours to the running model. It exists so the same ruleset produces the same outcome on Claude Opus 5, Claude Sonnet 5, Claude Fable 5, GPT-5.6 and GPT-6 Astra without the base rules being rewritten for a particular vendor's quirks.

Sources of the deltas: the Anthropic prompting best-practices set (`platform.claude.com/docs/en/build-with-claude/prompt-engineering/…`, including the per-model pages for Opus 5 / Sonnet 5 / Fable 5), the Anthropic context-engineering guide for the Claude 5 generation (`claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models`, July 2026 — lean context, judgement over hard style constraints, described interfaces over worked examples, progressive disclosure, code-form references), the OpenAI latest-model guide (`developers.openai.com/api/docs/guides/latest-model` → *Prompting best practices*) and [Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra). Only the **model-specific** parts of those guides are allowed into profiles; everything a guide states for all models belongs to §5 below and is always in force.

## 2. Selecting the profile

The profile follows **the model you know you are running**. `AGENT_MODEL` in `.dev.env` is the fallback for an agent that cannot tell, and the project's off switch.

| Model you run | Slug | Profile file |
|---|---|---|
| Claude Opus 5 | `opus5` | `content/rules/model-opus5.md` |
| Claude Sonnet 5 | `sonnet5` | `content/rules/model-sonnet5.md` |
| Claude Fable 5 (and Claude Mythos 5) | `fable5` | `content/rules/model-fable5.md` |
| GPT-5.6 | `gpt56` | `content/rules/model-gpt56.md` |
| GPT-6 Astra | `gpt6` | `content/rules/model-gpt6.md` |
| any other model | — | *no profile — the base ruleset applies as written* |

- **Self-knowledge first.** If you know you are running a model that has a profile, apply **that** profile whatever `AGENT_MODEL` holds — empty, missing, unrecognised or the slug of another model. `AGENT_MODEL` is a project setting and may have been written for a different client: when it names another model, state the mismatch in one line and recommend `/rulesmodel` — do not silently rewrite `.dev.env` mid-task.
- **`AGENT_MODEL` decides only when you cannot tell what you are running:** a slug from the table selects that profile; an empty, missing or unrecognised value means no model layer.
- **`AGENT_MODEL=off` switches the layer off for the project** — no profile is applied even when you know your model. `/rulesmodel off` writes it; `/rulesmodel reset` clears the key again.
- **Never ask** for the value at task time, never guess it, never treat its absence as a defect — the base ruleset is complete without a profile. The canonical editor is the `/rulesmodel` command (`content/commands/rulesmodel.md`).
- **Load once per session**, before the first non-trivial task, together with the rest of the always-on layer. A profile is small (≈1–2k tokens); do not re-read it per task and do not load more than one.
- **No family guessing.** A model without its own profile (Claude Opus 4.8 / 4.6, Sonnet 4.6, GPT-5.5 and earlier, and every non-Anthropic / non-OpenAI model) runs the base ruleset. GPT-5.6 (`gpt56`) and GPT-6 Astra (`gpt6`) are different profiles — do not apply one to the other. Applying a neighbouring profile "because it is close" is wrong — profiles encode deltas that are only correct for the named model. The user may still opt in explicitly through `/rulesmodel <slug>`; then honour the choice and say which profile is active.
- **Subagents select their own profile.** `AGENT_MODEL` describes the model the **parent** runs on; `SUBAGENT_MODEL_CODING` / `_ANALYSIS` / `_LIGHT` are the concrete models the **installer** stamps into subagent files per tier (`content/rules/subagents.md → Model-tier routing`, edited by `/economymode models`). Changing one never changes the other. A subagent applies a profile only from its own knowledge of the model it runs and never takes one from `AGENT_MODEL`; the parent does not translate profiles for it (`content/rules/subagent-core.md`).

## 3. Accepted spellings (normalisation)

Free-form input (`/rulesmodel` or a manual `.dev.env` edit) resolves to a slug from §2 by **family + major version**, case-insensitive, ignoring spaces, dashes, dots, underscores, vendor prefixes, client-side effort suffixes and language (`anthropic/claude-opus-5#xhigh` → `opus5`). Ambiguous or unsupported input (`gpt-5.5`, `opus 4.8`, `haiku`, a bare `claude` or `5`, …) resolves to **nothing** — no slug is written, never a silently coerced neighbour. The value written is always the dot-free slug of §2 (`gpt56`, `gpt6`) — rule file names and the `AGENTS.md` path rewriting require it. Alias table — `content/commands/rulesmodel.md → Accepted spellings`.

## 4. Precedence — what a profile may and may not change

A profile tunes **how much the agent does on its own initiative** and **how it communicates**. It never lowers the floor.

**A profile MAY:**

- shape response length, narration cadence, and the wording (not the presence) of the delivery report of `AGENTS.md → Development Procedure → 5`;
- shape how much upfront exploration and planning is proportionate before acting;
- shape the context the agent authors for others — subagent briefs, memory notes, handoffs, OpenSpec artefacts, `/evolve` entries: their structure, described interfaces vs. worked examples, the form of references;
- tune delegation eagerness within the bounds of `content/rules/subagents.md` (and `orchestrator-economy.md` when the mode is on);
- forbid **self-invented extra** verification — additional self-review passes, a verifier subagent, or repeated re-reading of your own diff that no rule asked for;
- recommend client-side settings (effort / reasoning effort, verbosity, thinking on/off) and give a prompt-level equivalent for clients where those settings are not exposed to you;
- recommend a level of an existing presentation switch (e.g. the `caveman` skill's level) with a one-line reason;
- emphasise a mechanism the base rules already own (project memory, `recall` / `remember`, handoff) when the model is documented to benefit from it.

**A profile MUST NOT** touch any of these, and any reading of a profile that seems to do so is a misreading:

- the hard gates **and the reads they mandate** — the load gate of `AGENTS.md → MCP Tool Calling` (`mcp-policy.md`, the router, the operation skill), `coding-standards.md` and `project-memory.md` before 1C work, `1c-metadata-manage` for metadata mutations and infobase-operation tooling (`AGENTS.md → Skills and Subagents`), MCP-first search (`content/rules/mcp-first-search.md`), the platform-capability check and `templatesearch` / `recall` obligations (`AGENTS.md → MCP Tool Calling → A`), and the memory gates (`AGENTS.md → Project memory`). "Lean context" in a profile trims optional reading, never a mandated one;
- the validator chain and its budget (`syntaxcheck → check_1c_code → review_1c_code`, `mcp-policy.md → B.1`) or the gates in `content/rules/verification-gates.md`. **Mandated validator calls are tool evidence, not self-verification** — a profile that damps "over-verification" damps only the extra passes the agent invents for itself;
- triage (`content/rules/verification-policy.md`), the `CONFUSION` obligation on material forks, the completeness / no-placeholders principle, the source-language policy, or the evidence one-liners (`Template:`, `Memory:`, `Metadata tooling:`, `IB tooling:`);
- the requirement to confirm destructive or hard-to-reverse actions.

**Precedence on conflict:** `USER-RULES.md` and `memory.md` → `LLM-RULES.md` → the active model profile → `AGENTS.md` and the other on-demand rules, for the behaviours the profile explicitly covers. Everything in the MUST NOT list is outside what a profile can cover, so it wins regardless of the order. If a profile and a base rule genuinely collide on a behaviour that is not in the MUST NOT list, follow the profile and note it in one line; if the collision touches the MUST NOT list, follow the base rule and report the profile text as a defect worth fixing upstream.

## 5. Model-agnostic prompting baseline (always in force)

These are the parts of both vendor guides that apply to **every** model. They are not repeated in profiles, are never overridden by a profile, and are already implemented by the base ruleset — the pointers show where:

- **Be explicit and specific; sequence steps when order matters.** State the desired output and its constraints (`AGENTS.md → Development Procedure → 1`, `4`).
- **Give the reason with the instruction.** A rule that carries its "why" is followed more accurately — this is why rules in this set state the consequence of violation, and why task briefs to subagents must carry intent, not only steps (`content/rules/subagents.md → Bounded sidecar task templates`).
- **Structure mixed content with tags.** Wrap distinct kinds of content (instructions vs. input vs. examples) in named tags in long briefs. Worked examples are a **per-model** lever, not part of this baseline: the latest guides of both vendors report that examples narrow the newest models' exploration and cost tokens, so each profile decides their place; an example remains the right tool to pin an exact output format.
- **Long context: data first, question last.** Put long inputs (module listings, XML dumps, logs) above the instruction, and ground answers in quoted fragments of what you read.
- **Say what to do, not what not to do.** Positive examples of the wanted shape beat prohibitions.
- **Parallel independent tool calls; never guess parameters.** Batch independent MCP / file calls, keep dependent calls sequential, and never invent an argument name or value (`mcp-policy.md → C.1`, `C.4`).
- **Investigate before answering.** Never speculate about code you have not opened; read the file the user named (`mcp-policy.md → A.3`, `content/rules/mcp-first-search.md`).
- **Define success criteria and verify against them.** Turn imperative tasks into verifiable goals (`AGENTS.md → Development Procedure → 4`).
- **Keep instructions non-contradictory.** Conflicting instructions degrade every model; resolve a conflict explicitly (`CONFUSION`, or the precedence chain above) instead of averaging the two readings.
- **User task vs on-demand skill process.** The user's current-task instruction outranks an on-demand skill's process guidance, except hard gates and the MUST NOT list. A skill must not turn an already authorized task into an approval loop.
- **Author skills with precise triggers and progressive disclosure.** When asked to create or maintain a skill, keep its description short and specific to the workflow that requires it. A multi-workflow root should route to supporting docs and scripts by task; avoid broad keyword triggers, competing activation demands and unrelated required reading. Existing mandatory tool routes remain explicit.
- **Describe outcomes and decision boundaries.** In task prompts and workflow guidance, state the result, constraints, completion checks and where to stop. Prescribe exact steps when correctness, tool contracts or safety depend on their order. Keep shared instructions usable by different models; put model-specific changes to initiative in the matching profile. Apply this during authorized rules maintenance, not as permission for unsolicited rewrites.
