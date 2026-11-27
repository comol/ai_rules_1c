# References

Curated list of projects with rules / skills for AI assistants targeting 1C development.

## Rules and skills for 1C

- [1c-agent-based-dev-framework](https://github.com/SteelMorgan/1c-agent-based-dev-framework) — SteelMorgan
- [1c-ai-development-kit](https://github.com/Arman-Kudaibergenov/1c-ai-development-kit) — Arman-Kudaibergenov
- [1c-ai-feature-dev-workflow](https://github.com/AndreevED/1c-ai-feature-dev-workflow) — AndreevED
- [1c-ai-rules](https://github.com/unchnm/1c-ai-rules) — unchnm
- [1c-batch](https://github.com/vladimir-kharin/1c-batch) — vladimir-kharin
- [1C-Enterprise-Agent-Toolkit](https://github.com/Muredsa/1C-Enterprise-Agent-Toolkit) — Muredsa (MIT): a Python CLI wrapping Designer batch mode behind an isolated, auditable session. Source for `content/rules/designer-batch-checks.md` — the three-signal verdict (`/DumpResult` alongside exit code and `/Out`), the success-phrase-before-error-stem log classification, the `/CheckModules` → `/CheckCanApplyConfigurationExtensions` → `/CheckConfig` ladder, the dual extension backup + `/RollbackCfg` rollback model, and the never-run switch list; also the minimal-closure procedure in `getconfigfiles.md`. Its session sandbox (copied file infobase, `onec-dev-*` markers, manifest-driven cleanup) is **not** ported: this ruleset works against a `.dev.env` dev/test base under the existing dev/test confirmation rules.
- [1c-edt-skills-ai](https://github.com/NixLavr/1c-edt-skills-ai) — NixLavr
- [1c-enhanced-codemetadata](https://github.com/Arman-Kudaibergenov/1c-enhanced-codemetadata) — Arman-Kudaibergenov
- [1c-feature-dev](https://github.com/Diversus23/1c-feature-dev) — Diversus23
- [1c-platform-actions](https://github.com/svhov/1c-platform-actions) — svhov
- [1c-quality-gate](https://github.com/Romandredan/1c-quality-gate) — Romandredan (MIT): Claude Code / OpenCode quality gate plugin. Source of ideas for `content/agents/cold-reader.md` (blind diff-only behavioral review with verbatim quote rule) and the silent-clean sentinel / isolated CFE base-config guard in `content/rules/verification-gates.md`. Its blocking Stop/shell hooks are intentionally not ported to preserve agent flexibility.
- [1c-ssl-skills](https://github.com/brake71/1c-ssl-skills) — brake71 (MIT): BSP 3.1.11 skills and RED/GREEN behavioral evaluation harness (also source for PowerShell UTF-8 stdout encoding pitfalls in `content/skills/powershell-windows/SKILL.md`).
- [1c-standards-claude-skill](https://github.com/SolovievHub/1c-standards-claude-skill) — SolovievHub
- [cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) — Nikolay-Shirokov (MIT): source of the vendored `1c-metadata-manage` tools, synced at `29a3a9e` (2026-11-26; notice: `content/skills/1c-metadata-manage/NOTICE.md`; the support-guard hook stays at `2e75b0f`), of the configuration-repository log handling in `1c-repository-manage` (learnings from its `db-repo`, not vendored) and of the opt-in support-guard hook `plugins/1c-rules/hooks/support-guard.mjs` (notice beside it). Its `web-test` skill and `regress-example/` are not vendored; their platform findings are in `content/rules/web-client-driving.md` and `content/skills/1c-ui-regression/docs/regression-stand.md`.
- [claude-code-bsl-lsp](https://github.com/1c-syntax/claude-code-bsl-lsp) — 1c-syntax: official BSL Language Server LSP plugin for Claude Code.
- [claude-code-skills-1c](https://github.com/Desko77/claude-code-skills-1c) — Desko77 (MIT): source of ideas for `content/rules/git-safety.md`, `content/rules/edt-pitfalls.md`, `content/rules/rls-performant-bsp.md`, Cyrillic Windows rules in `content/skills/powershell-windows/SKILL.md`, and the optional domain pack catalog.
- [claude_rules_1c](https://github.com/Dach-Coin/claude_rules_1c) — Dach-Coin
- [cursor-1c-skills](https://github.com/Desko77/cursor-1c-skills) — Desko77
- [form-ordinary](https://github.com/dreamadv81/form-ordinary) — dreamadv81 (MIT): vendored as `content/skills/form-ordinary/` at `a0f5294` (2026-11-16; notice: `content/skills/form-ordinary/NOTICE.md`), the primary route for ordinary forms (`Form.bin`, `form.frm`). Its platform pictures belong to 1C and are not under MIT.
- [opencode_1c_rules](https://github.com/colVEEEN/opencode_1c_rules) — colVEEEN
- [partial-load-config](https://github.com/Nikolay-Shirokov/partial-load-config) — Nikolay-Shirokov
- [Pauk_1C](https://github.com/Mempemp/Pauk_1C) — Mempemp
- [unica](https://github.com/IngvarConsulting/unica) — Ingvar Consulting (LGPL-3.0-or-later): 1C agent plugin supporting 8.3.27 and 8.5 (formats 2.21/2.22). Ideas adapted (no code copied) for `content/rules/platform-versions.md`, `content/rules/data-separation.md`, `content/rules/log-analysis.md`, `content/rules/localization.md`, `content/rules/mcp-policy.md → A.2`, and `content/skills/1c-metadata-manage/SKILL.md → Plan unit`.
- [universal_1c_rules](https://github.com/fairballer-rgb/universal_1c_rules) — fairballer-rgb
- [va-ai](https://github.com/Nikolay-Shirokov/va-ai) — Nikolay-Shirokov (MIT): Vanessa Automation BDD step library and validator.

## Generic rules for AI agents

- [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) — Karpathy's rules (forrestchang): four AI-coding principles (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution).
- [superpowers](https://github.com/obra/superpowers) — Jesse Vincent / obra: skill framework for coding agents (brainstorming, writing-plans, executing-plans, subagent-driven-development, systematic-debugging, verification-before-completion, requesting/receiving-code-review, using-git-worktrees, finishing-a-development-branch, writing-skills). Source, adapted to 1C, for `subagent-pipeline.md` (two-stage review), `systematic-debugging.md` and the evidence rule of `verification-gates.md` / `verification-delivery.md`; since 2026-11-17 also for acting on review findings (`verification-delivery.md → Soft gate C`, from receiving-code-review), intent before design (`sdd-propose.md`, from brainstorming), the failing-scenario-first rule for rule edits with the `Check` line of `/evolve`, and trigger-only descriptions (both from writing-skills). Not ported: the TDD iron law and git worktrees (they assume cheap unit tests and isolated checkouts, which a shared infobase and repository locks do not give), a fresh subagent per small task (metadata work runs sequentially) and the session-start bootstrap with its mandatory-invocation wording.
- [caveman](https://github.com/JuliusBrussee/caveman) — Julius Brussee (MIT): the terse "caveman" answer style. Source for `content/skills/caveman/SKILL.md`, tracked against upstream **v2.2.0** (adapted to 1C: Russian output, `.dev.env` `CAVEMAN` gating, task-type scope, BSL / metadata boundaries; wenyan levels and the v2 engine / proxy / CLI surface not ported — see the skill's *Upstream deviations*).
- [mattpocock/skills](https://github.com/mattpocock/skills) — Matt Pocock: a set of Claude Code skills from his `.claude` (engineering: `diagnose`, `grill-with-docs`, `improve-codebase-architecture`, `to-prd`, `to-issues`, `triage`, `zoom-out`, `prototype`; productivity: `caveman`, `grill-me`, `handoff`, `write-a-skill`). Source for `content/skills/handoff/SKILL.md` (adapted to 1C: default path `handoffs/`, references to `openspec/`, `memory.md`, `1c-templates-mcp`, gates from `verification-checklist.md`).
