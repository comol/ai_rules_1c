---
name: prompt-enhancer
description: "Improve and structure short, unstructured prompts and task statements, turning them into detailed imperative specifications with numbered analysis steps, explicit edge cases, and a clearly described expected output format. Preserves all terms and conditions from the source, does not add new requirements. Use when the user asks to: improve a prompt, refine a task statement, expand a task description, structure a spec, turn a note into a detailed instruction, make a prompt more precise or detailed, prepare a spec from a draft, polish a task, convert a short note into a clear specification. Accepts text as a command argument or a path to a .md file."
---

# prompt-enhancer — improving prompts and task statements

Turns a short note or unstructured task into a detailed imperative specification. Suitable for 1C developers who need to formalize a quickly written thought into a clear task statement.

## When to use

Trigger this skill on user phrases like:

- "improve the prompt", "make the prompt better / more precise / more detailed"
- "refine the task statement", "formalize this task", "polish the task"
- "structure the spec", "prepare a spec from a note"
- "expand the task description", "turn this into a detailed instruction"

The skill works with any subject area, but specifically accounts for 1C task specifics (terminology, attribute names, object names, form names).

## Modes

| Mode | Trigger | What it does |
|------|---------|--------------|
| Inline | argument is arbitrary text | Improved prompt is printed in chat |
| File | argument is a path to an existing file | Result is saved next to the source with `-enhanced.md` suffix |
| Interactive | argument is empty | Ask the user for the prompt text or a file path |

## Mode detection algorithm

The mode is selected deterministically, without heuristic on the argument text:

1. If the argument is empty — Interactive mode. Ask the user for the prompt text or a file path with a regular message.
2. Otherwise try reading the argument via the Read tool.
   - If Read returns file content — File mode.
   - If Read returns a "file does not exist / not found" error — that is the normal path, not a failure. Switch to Inline: use the entire argument as the prompt text.
3. Do not detect mode by the presence of `.md` in the text. A phrase like "prepare a spec about .md generation" must not be interpreted as a path. File existence is checked by Read, not by string parsing.

## Transformation principles

The core of the skill. Re-check this list on every generation:

1. **Source as the single source of truth.** All terms, attribute names, tab names, object names, form names, subsystem names, numbers, enumerations are carried over verbatim. Do not replace `Айс_КодИсточника77` with "service attribute".
2. **Imperative instead of description.** "needs to be displayed" becomes "Display"; "we should analyze" becomes "Analyze". The result is a plan of actions, not a story.
3. **Explicit edge cases.** Exception conditions are extracted into a separate sentence in the form "if ..., then ...", not hidden inside parentheses. An edge case must stand out.
4. **Fixed expected output.** Add a "For each item, specify" section with a numbered list of fields. State the result format (table, structured list, JSON) explicitly.
5. **No new requirements.** Do not add requirements that were not in the source: tests, documentation, roles, rollback, logging. Improvement is form, not content.
6. **Numbering of analysis steps.** Split user wishes into discrete verifiable operations 1..N. Each step — one operation.
7. **Preserve intent, not literal text.** If the source says "prepare a list" but then lists analytical tasks, analysis comes first, list compilation second. Restore the correct order.
8. **Neutral business register.** Remove conversational and emotional elements ("would be nice", "somehow", "we'd like"), keep neutral phrasing.
9. **Short essence in the first line.** Before the step-by-step plan — one sentence stating the task goal.
10. **Formatting per repo rules.** No long or short dashes (only the regular hyphen), no letter "ё" with dots, no time or ROI estimates.

## Improved prompt template

Mandatory result blocks:

1. **Goal** — one sentence, what to do.
2. **Analysis steps** — numbered list of imperatives (Analyze, Study, Determine, Output).
3. **Edge cases** — explicit "if ..., then ..." conditions with concrete names and values from the source.
4. **Output format** — name of the format (table / structured list / JSON) and the list of fields the result must contain.
5. **Additional clarifications** (optional) — details, if the source mentioned deadlines, owners, dependencies.

## Before / after example

**Source prompt (short, unstructured):**

> The task — display all non-typical attributes of typical objects on the "Доп. реквизиты Айс" tab. Place the tab last. If only one attribute is added, Айс_КодИсточника77, do nothing. Prepare a list of objects, analyze element forms, determine where and how to add the tab.

**Improved prompt (structured, detailed):**

> Analyze all typical configuration objects and prepare a list of those that contain non-typical attributes. Study the element forms of these objects. Add a new "Доп. реквизиты Айс" tab last in order to each form. Move all non-typical attributes onto the tab, except when the only non-typical attribute is Айс_КодИсточника77 (then no changes are made). For each object, specify:
>
> 1. Object name.
> 2. List of non-typical attributes.
> 3. Name of the element form used and current tab structure.
> 4. Recommended changes to tab placement and attribute movement, taking interface logic into account.
>
> Format the output as a convenient table or structured list ready for implementation.

Additional cases — see `examples/`.

## DO / DON'T

**DO:**
- Preserve names of objects, attributes, tabs, constants, enumerations verbatim.
- Turn requests into imperatives, add structure and numbering.
- Extract exceptions and edge cases into separate sentences.
- Specify the expected result format explicitly.
- Add a short essence on the first line before the step-by-step plan.

**DON'T:**
- Invent new requirements that were not in the source (roles, tests, rollback, printing, logging).
- Replace concrete terms with generalizations.
- Add technical solutions ("use БСП", "do this via HTTP service") unless mentioned in the source.
- Use long dash, en dash, double hyphen, or letter "ё" with dots.
- Estimate effort in hours, days, weeks, or money.

## Saving the file (file mode)

- Result name: `<source filename without extension>-enhanced.md`. If the original is `postanovka.md`, the result is `postanovka-enhanced.md` in the same folder.
- Encoding: UTF-8.
- Do not overwrite, delete, or rename the original.
- If the result file already exists — overwrite without asking (this is a rerun of the skill).

## Encoding handling

Source files are read as UTF-8. If Read returns obvious mojibake (unreadable Cyrillic like "ж©", "­", squares), inform the user that the file is likely in cp1251 or another encoding and ask to save it as UTF-8. Auto-detection of encoding is intentionally not implemented in the skill — a deliberate simplification of the first version.

## Trigger phrases (for reliable detection)

The skill should recognize these user phrasings as triggers, even when the `/prompt-enhancer` command is not specified explicitly:

- improve / make the prompt better
- expand / refine / formalize the task statement (task, spec)
- structure the spec / task
- make the prompt more detailed / more precise / better
- prepare a detailed spec from a note / draft
- polish the task / statement
- turn this into a clear spec / detailed instruction

## Limitations

- The skill rewrites form, not content. If the source prompt is logically contradictory or incomplete, the result will also be incomplete (see principle 5 — no new requirements).
- For very long source texts (2000+ words), processing may miss details. In that case, split the text into logical blocks and process them in parts.
- The skill assumes no domain knowledge beyond the source. If 1C-specifics need clarification, additionally use related skills like `composing-1c-queries` and the relevant rules in this repo.
