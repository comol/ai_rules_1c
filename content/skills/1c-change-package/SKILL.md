---
name: 1c-change-package
description: "Deliver a 1C change as a package a human applies or reviews instead of writing it to the sources: a manual-implementation package for the Configurator («Найти» / «Заменить целиком на» pairs, attribute and form-element tables, post-apply checks, rollback) or a review diff (unified diff with context plus a «Сейчас / Предлагается» table for metadata and form properties). Use when the change cannot or must not be written by the agent — vendor-locked object, ordinary / binary form, object locked in the configuration repository by someone else, MCP-only access to the code — or when the user asks for it: «подготовь инструкцию для ручного внесения», «подготовь пакет ручного внесения», «что найти и на что заменить», «код для копирования в Конфигуратор», «покажи дифф», «покажи изменения», «сделай ревью изменения», «сравни текущий и новый код». Not a licence to change the configuration, the infobase or the repository."
argument-hint: "[manual | review] [target path for the result file]"
---

# 1c-change-package — manual implementation and review packages

The deliverable is a document, not an edit: the agent reads the current code, designs the change and hands over a package that a human applies in the Configurator (**manual** mode) or reviews (**review** mode). Nothing is written to the sources, the infobase or the repository. The idea is adapted from the `bsl-change-review` skill of [AzeevAN/mcp-1c](https://github.com/AzeevAN/mcp-1c) (Apache-2.0); the text and the evidence vocabulary are this ruleset's own.

## When this is the deliverable

- **Manual** — the agent must not or cannot write the change itself: a vendor object «на замке» the user chose not to take off support or borrow into an extension (`content/skills/1c-metadata-manage/docs/support-manage.md`); an ordinary / binary form (`content/rules/forms.md` — ordinary forms are not edited as `Form.xml`); an object locked in the configuration repository by another user (`content/skills/1c-repository-manage/SKILL.md` — never bypass the lock); the code is reachable only through MCP; or the user asked for instructions / code to copy.
- **Review** — the user wants to see the change before it is applied: «покажи дифф», «покажи изменения», «сравни текущий и новый код», «сделай ревью изменения».
- The user named a mode — keep it. Both fit and the goal is unclear — ask one short question before reading a reference.

Read exactly one reference for the chosen mode: [references/manual-implementation.md](references/manual-implementation.md) or [references/review.md](references/review.md).

## Common procedure

1. **Current source, verbatim.** Read the exact current text of every procedure, block, form and property the change touches — a local file first, MCP (`1c-code-search`, `1c-meta-info`, `1c-form-inspect`) when the sources are not local. Never reconstruct current code from memory or a summary. No exact text → that change is `blocked — <reason>`.
2. **Fix the snapshot.** Record for each source: configuration / extension (or `unverified`), full address (object, module, procedure / form, element), where it was read (file path or MCP tool), platform version, and a fingerprint — the file hash or a hash of the exact text read (the same artifact fingerprint `content/rules/verification-gates.md → Gate execution and evidence reuse` uses).
3. **Minimal change.** Only what the task requires (`AGENTS.md → Development Procedure`, step 3); an unfinished part is listed as unfinished, never presented as done.
4. **Prove the API.** Before writing `Переменная.Метод()`, establish the variable's type from its creation, assignment or the returning function; then confirm `<Тип>.<Метод>` and its signature with `docinfo` / `bsl_scope_members` (`content/skills/1c-platform-help/SKILL.md`). A method whose return value or failure matters is confirmed the same way. What cannot be confirmed is `unverified`, and code that depends on it is `blocked` — never a placeholder.
5. **Gates on the proposed code.** The new blocks have no file yet, so Gate 1 runs on the text (`syntaxcheck`), followed by the rest of the chain at the active depth — `content/rules/verification-gates.md`, budget `content/rules/verification-policy.md`. Generated XML goes through `verify_xml`. A gate that could not run is `not run — <reason>`.
6. **Staleness check.** Re-read every source right before delivery and compare the fingerprint: same → current; changed → the package is stale, redo it or mark it `blocked — source changed since <time>`; cannot re-read → `unverified`.
7. **Deliver.** By default the whole package goes into the reply. Write a file only to a path the user gave: an explicit file path is used as is; for an explicit directory the file is `IMPLEMENTATION.md` (manual) or `change-review.md` (review). Never write to the project root, the current directory, the skill directory or a scratch folder on your own. If the write fails, return the package in the reply and say so.
8. **Self-review.** Re-read the package against the source as an independent reviewer: every «Найти» block is verbatim, every line order is real, no check is claimed that did not run.

## Evidence vocabulary

The package reuses the ruleset's delivery vocabulary (`content/rules/verification-delivery.md`, `content/rules/verification-gates.md`); no second set of states:

| State | Meaning |
|---|---|
| `passed` | the gate or check ran on the current state; name the tool and its result |
| `not run — <reason>` | the check applies but did not run (tool not exposed, no dev / test base, out of budget) |
| `unverified` | a fact the package relies on was not established — a property value not read, a type not proven, a match count not counted, a scenario not confirmed |
| `blocked — <reason>` | a correct block cannot be written (missing code, missing contract, stale source); nothing is invented in its place |

Behaviour is confirmed only by the gates, by UI confirmation under `.dev.env` `UI_TESTING` (`1c-tester`, `/deploy-and-test` — `content/rules/verification-delivery.md → Soft gates — run when applicable`) and by review. A scenario nobody confirmed is `unverified`, never «done». The usual evidence lines (`Memory:`, `Template:`, `Docs:`, …) follow the package when they apply; `Metadata tooling:` / `Repository tooling:` do not, because the package changes nothing.

## Boundaries

- Reading files and calling read-only MCP tools gives no permission to change the configuration, the infobase, the repository or a container. Applying the package, compiling in the Configurator, updating an infobase and capturing / committing repository objects are separate actions with their own authorization.
- No secrets and no customer code in shared places.
- A package is never a way around a gate: a vendor lock, a repository lock or a refused tool stays in force, and the package says who applies the change and where.
