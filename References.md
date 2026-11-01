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
- [1c-standards-claude-skill](https://github.com/SolovievHub/1c-standards-claude-skill) — SolovievHub
- [cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) — Nikolay-Shirokov (MIT): source of the vendored `1c-metadata-manage` tools, synced at `2e75b0f` (2026-10-31; notice: `content/skills/1c-metadata-manage/NOTICE.md`), of the configuration-repository log handling in `1c-repository-manage` (learnings from its `db-repo`, not vendored) and of the opt-in support-guard hook `plugins/1c-rules/hooks/support-guard.mjs` (notice beside it). Its `web-test` skill and `regress-example/` are not vendored; their platform findings are in `content/rules/web-client-driving.md` and `content/skills/1c-ui-regression/docs/regression-stand.md`.
- [claude-code-skills-1c](https://github.com/Desko77/claude-code-skills-1c) — Desko77
- [claude_rules_1c](https://github.com/Dach-Coin/claude_rules_1c) — Dach-Coin
- [cursor-1c-skills](https://github.com/Desko77/cursor-1c-skills) — Desko77
- [opencode_1c_rules](https://github.com/colVEEEN/opencode_1c_rules) — colVEEEN
- [partial-load-config](https://github.com/Nikolay-Shirokov/partial-load-config) — Nikolay-Shirokov
- [Pauk_1C](https://github.com/Mempemp/Pauk_1C) — Mempemp
- [universal_1c_rules](https://github.com/fairballer-rgb/universal_1c_rules) — fairballer-rgb

## Generic rules for AI agents

- [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) — Karpathy's rules (forrestchang): four AI-coding principles (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution).
- [superpowers](https://github.com/obra/superpowers) — Jesse Vincent / obra: skill framework for coding agents (brainstorming, writing-plans, executing-plans, subagent-driven-development, systematic-debugging, verification-before-completion, requesting/receiving-code-review, using-git-worktrees, finishing-a-development-branch, writing-skills). Source for the on-demand rules `subagent-pipeline.md`, `systematic-debugging.md`, `verification-checklist.md` (adapted to 1C specifics — see `AGENTS.md → Additional rules (load on demand)`).
- [caveman](https://github.com/JuliusBrussee/caveman) — Julius Brussee (MIT): the terse "caveman" answer style. Source for `content/skills/caveman/SKILL.md`, tracked against upstream **v2.2.0** (adapted to 1C: Russian output, `.dev.env` `CAVEMAN` gating, task-type scope, BSL / metadata boundaries; wenyan levels and the v2 engine / proxy / CLI surface not ported — see the skill's *Upstream deviations*).
- [mattpocock/skills](https://github.com/mattpocock/skills) — Matt Pocock: a set of Claude Code skills from his `.claude` (engineering: `diagnose`, `grill-with-docs`, `improve-codebase-architecture`, `to-prd`, `to-issues`, `triage`, `zoom-out`, `prototype`; productivity: `caveman`, `grill-me`, `handoff`, `write-a-skill`). Source for `content/skills/handoff/SKILL.md` (adapted to 1C: default path `handoffs/`, references to `openspec/`, `memory.md`, `1c-templates-mcp`, gates from `verification-checklist.md`).
