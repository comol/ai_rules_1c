---
description: "Support channel contract: when a ticket may be proposed or sent (/support, /supportstatus), the evidence threshold, the approval gate. Load on a suspected defect in MCP or the rules and before /support."
alwaysApply: false
category: workflow
---

# Support channel: MCP and rules

A ticket goes to the support service (`SUPPORT_API_URL`). A new ticket has status **`новый`**; the operator handles it and moves it to **`закрыт`**, with an answer when needed. The answer arrives at `SUPPORT_EMAIL`.

| Command | What it does | Who starts it |
|---|---|---|
| `/support` | sends a ticket about a problem in MCP or in the rules | the user, or the model — **always** with explicit approval |
| `/supportstatus` | status of own tickets, operator answers, closing an own ticket | the user; the model on request |
| `/checkupdates` | whether MCP images and the ruleset have updates (read-only) | the user; the model about every 30 days (`content/commands/checkupdates.md → Proactive run`) |

Procedures, ticket fields, image tags and data scrubbing — `content/commands/support.md`, `content/commands/supportstatus.md`, `content/commands/checkupdates.md`. This file is the contract: when a ticket is allowed, when it is not, and what counts as enough evidence.

## 1. Preconditions — hard

The channel works **only** when the project `.dev.env` has **both** values:

- `SUPPORT_KEY` — the shared support key from the MCP distribution (`config.env`, section 6);
- `SUPPORT_EMAIL` — the working e-mail of the ticket author.

`SUPPORT_API_URL` is Defaulted (`dev-standards-env-process.md → Support-channel parameters`).

If either is empty, nothing is sent and no workaround is taken. Say what is missing and where to get it (the distribution's `INSTALL.md` → step 6; a fresh key — the personal cabinet https://vibecoding1c.ru/). Never borrow a key from another project, never ask the user to send the problem "somewhere else", never defer silently.

The key is a secret: it never appears in chat, logs, the ticket text or `context`.

## 2. When the model proposes `/support` itself

**Propose** a ticket when you have a well-founded, confident suspicion of a defect in the shipped product — a rule of the `1c-rules` set or an MCP server. "Confident" is a met threshold, not a feeling.

### Evidence threshold (all four)

1. **A defect in the product, not in the project.** The problem is in the text of a rule / command of the set or in an MCP server's behaviour — not in the user's code, configuration or `.dev.env`.
2. **Checked against facts.** The rule contradicts platform documentation or another rule of the set; a command step names a file / key / tool that does not exist; an MCP tool returns a result a direct check refutes (for example `standards` does not find a section that is in the corpus, confirmed by a second request). One failed attempt is not evidence.
3. **Reproducible.** You repeated the scenario with the same result, or the error is deterministic by construction (a broken link in a rule always reproduces).
4. **Not fixable in place.** It is not something a project code change or a reworded request repairs.

Threshold not met — do not propose. A "just in case" ticket is worse than none: it clutters the operator's queue.

### Not a defect

- An error in the user's code or metadata, even if a rule did not catch it.
- Missing data: `PATH_METADATA` / `PATH_CODE` not set, the index not built, an HTTP service not published — setup, not a defect.
- An empty licence key, the key of another server, or a key issued before 27.09.2026 — a known situation, solved by `/updatemcp` and the personal cabinet.
- Disagreement with a rule's style or strictness. A rule can be inconvenient and still correct.
- A single network failure, a timeout, "the container did not come up after a reboot".
- Anything already covered by `/doctor`, `/checkmcp` or the troubleshooting section of the documentation.
- Something an update fixes: before proposing a ticket, run `/checkupdates`; if the problem is fixed by an update, suggest `/updatemcp` or `/updaterules` instead.

### Approval gate

The model's initiative ends with a **proposal**, never a send. Show it as one block, in Russian:

> Похоже на дефект `<в правиле X | в сервере Y>`. Что видел: `<факт>`. Чем подтверждается: `<проверка>`. Предлагаю отправить обращение в поддержку — вот текст: `<полное тело>`. Отправляем? (да / нет / поправить)

Without an explicit "да" from the person, `/support` does not run — not automatically, not "since the text is ready", not on a repeat of the same error. A ticket sent on the model's initiative carries `source: "model"`, which the operator uses to tell model findings from human ones.

### Frequency

At most **one** proposal per defect per session and at most two proposals per session overall. A declined proposal closes the topic for the session; do not reword it. The proposal never interrupts the user's task: finish the work, then add the proposal at the end of the answer.

## 3. `/support` versus `/evolve`

| Sign | `/evolve` | `/support` |
|---|---|---|
| Writes to | this project's local `LLM-RULES.md` | the external support service |
| Records | agent behaviour to change **in this project** | a defect of a shipped rule or MCP server |
| Addressed to | yourself in later sessions | the product maintainers |
| Example | "в нашем проекте не ставить маркеры доработки" | "правило ссылается на несуществующий файл" |

A rule that is inconvenient, excessive or in conflict with the project's agreements is friction: a `rule-friction:` memory note and, when `AGENTS.md → Rules self-improvement` allows, a recommendation of `/evolve`. A rule that is wrong as such, or a tool that returns false results, is `/support`. In doubt — treat it as friction, not a ticket: a local correction is reversible, a ticket is not.
