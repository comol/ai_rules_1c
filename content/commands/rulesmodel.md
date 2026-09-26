---
description: Adapt the ruleset to the model that is actually running — normalize a free-form model name to a profile slug and write AGENT_MODEL (opus5|sonnet5|fable5|gpt56|gpt6) into .dev.env
userOnly: true
argumentHint: "[opus5|sonnet5|fable5|gpt56|gpt6|<any model name>|auto|status|off]"
---

# /rulesmodel — adapt the rules to the active model

Bind the ruleset to the model that executes it by writing the `AGENT_MODEL` key in `.dev.env`. Canonical behaviour of the layer — `content/rules/model-adaptation.md` and the profile files `content/rules/model-<slug>.md` (installed copies; match by file name per the path convention in `AGENTS.md`). **Load `model-adaptation.md` before acting.**

Supported profiles: `opus5` (Claude Opus 5), `sonnet5` (Claude Sonnet 5), `fable5` (Claude Fable 5 / Mythos 5), `gpt56` (GPT-5.6), `gpt6` (GPT-6 Astra). Any other model runs the base ruleset, which is model-neutral by design — that is a valid state, not a degraded one.

Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for.

The command edits **only** the `AGENT_MODEL` line in `.dev.env` — never other keys, never other files. Rewrite the `AGENT_MODEL=` line in place, or append `AGENT_MODEL=<slug>` at the end; if `.dev.env` is missing, run the installer (`install.ps1 init`) instead of creating a partial file — until then apply the profile for the current session only.

> **`AGENT_MODEL` ≠ `SUBAGENT_MODEL_*`.** This command sets which model **you** run on, so the ruleset can adapt to its documented behaviour. The models that **subagents** run on are `SUBAGENT_MODEL_CODING` / `_ANALYSIS` / `_LIGHT`, configured by `/economymode models` and consumed by the installer. If the user asks to "change the model" meaning subagent tiers, route them there instead and say so in one line.

## Argument parsing (normalization is your job, not a script's)

The user may write the model name any way they like. Resolve free-form input to a canonical slug **yourself** — no script has to be fed an exact string:

1. **Empty or `auto`** — identify the model you are actually running from your own self-knowledge and map it to a slug. If you are not one of the supported models, treat it as `off` (see below) and say which model you identified.
2. **A model name in any spelling** — normalize by family + major version: lowercase; strip spaces, dashes, dots, underscores; strip vendor prefixes (`anthropic/`, `openai/`, `claude-`, `gpt-`) and client-side suffixes (`-thinking`, `-high`, `#xhigh`, `-max`, `-fast`, date stamps); accept Russian spellings (`клод опус 5`, `сонет 5`, `фейбл 5`, `гпт 5.6`, `гпт 6`, `астра`). Use the alias table below, and judgement for spellings it does not list. The value written is always the dot-free slug (`gpt56`, not `gpt5.6`; `gpt6`, not `gpt-6`) — rule file names and the `AGENTS.md` path rewriting require it.
3. **`status`** — report without editing anything.
4. **`off` / `none` / `generic` / `сброс`** — clear the value (base ruleset).

**Unsupported or ambiguous input is never silently coerced.** `gpt-5.5`, `opus 4.8`, `sonnet 4.6`, `haiku`, a bare `claude`, `gemini`, `glm`, `qwen`, a bare version number: report the supported slugs, explain that the base ruleset applies unchanged for other models, and ask which the user wants. Offer the nearest same-family profile only as an explicit choice they confirm — never map one family onto another. `gpt-5.6` is `gpt56`; `gpt-6` / `gpt-6-astra` is `gpt6` — do not coerce one into the other.

**Requested slug ≠ the model you are running** is allowed (the user may be configuring the project for a teammate or for another client): write the requested value, and state in one line that the active session is a different model, so the profile you apply right now is the one matching your own identity per `model-adaptation.md §2`.

### Accepted spellings

| Slug | Recognised as |
|---|---|
| `opus5` | `opus5`, `opus 5`, `opus-5`, `claude-opus-5`, `claude opus 5`, `Claude Opus 5.0`, `клод опус 5`, `опус 5` |
| `sonnet5` | `sonnet5`, `sonnet 5`, `claude-sonnet-5`, `Claude Sonnet 5`, `сонет 5`, `соннет 5` |
| `fable5` | `fable5`, `fable 5`, `claude-fable-5`, `Claude Fable 5`, `mythos5`, `claude-mythos-5`, `фейбл 5`, `фабл 5`, `мифос 5` |
| `gpt56` | `gpt56`, `gpt5.6`, `gpt-5.6`, `GPT 5.6`, `openai gpt-5.6`, `гпт 5.6`, `гпт-5.6` |
| `gpt6` | `gpt6`, `gpt-6`, `GPT 6`, `gpt-6-astra`, `gpt6astra`, `astra`, `astra6`, `astra 6`, `openai gpt-6`, `гпт 6`, `гпт-6`, `астра`, `астра6`, `астра 6` |

## Setting the profile (`auto`, a slug, or a free-form name)

1. Read `.dev.env`: the `AGENT_MODEL` key.
2. Set `AGENT_MODEL=<slug>`.
3. **No re-render needed.** `AGENT_MODEL` is read from `.dev.env` at task time and all profile files are already installed as on-demand rules — no `install.ps1 update`, no client restart.
4. Load `content/rules/model-<slug>.md` and apply it immediately — from this message on, in this session.
5. Confirm to the user in 3–5 lines, in Russian:
   - что записано в `.dev.env` (`AGENT_MODEL=<slug>`, модель — `<полное имя>`) и что действует для проекта, включая новые чаты;
   - 2–3 главных изменения поведения из профиля `model-<slug>.md`;
   - что **не** меняется: хард-гейты — профиль их не ослабляет (`model-adaptation.md §4`);
   - рекомендуемая клиентская настройка усилия / verbosity из профиля, если её задаёт пользователь (эти параметры обычно вне доступа агента);
   - как сменить или выключить — `/rulesmodel <модель>` / `/rulesmodel off`.

## status

Read `.dev.env` and report, without editing anything:

- the `AGENT_MODEL` value (or no profile when the file / key is absent or the value is unrecognised) and which profile file it resolves to;
- whether that value matches the model you are actually running — on a mismatch, say which profile you are applying and recommend `/rulesmodel auto`;
- the profile's recommended effort / verbosity settings, and the 2–3 headline behaviour deltas currently in force;
- for orientation only, the subagent tier models (`SUBAGENT_MODEL_CODING` / `_ANALYSIS` / `_LIGHT`) with a pointer to `/economymode models` — do not change them here.

## off

1. Set `AGENT_MODEL=` (empty value; keep the key and its comment when they already exist). If the key is absent, there is nothing to persist.
2. Stop applying the profile immediately in this session and confirm: адаптация под модель выключена, действует базовый (модель-нейтральный) свод правил; включение — `/rulesmodel <модель>` или `/rulesmodel auto`.

## Constraints (always)

- **The profile layer never weakens a hard gate and never overrides the model-agnostic prompting baseline** — precedence and the baseline are `model-adaptation.md §4` and `model-adaptation.md §5`. A profile tunes verbosity, narration, planning depth, delegation eagerness and self-invented extra passes — nothing else.
- The command asks the user only when the input is unsupported or ambiguous; a recognised name is resolved silently. Asking inside this explicit configuration flow is fine — the never-ask policy applies to regular tasks, not to an invoked configuration command.
- Never edit `SUBAGENT_MODEL_*`, `ORCHESTRATION`, `VERIFICATION_DEPTH`, `CAVEMAN` or any other key here, and never rewrite a rule file to "bake in" a profile — the layer is selected by the `.dev.env` value, not by editing rules.
