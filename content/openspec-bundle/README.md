# OpenSpec bundle — snapshot of `openspec init` output

This folder ships a per-tool snapshot of the artifacts that the official OpenSpec CLI (`@fission-ai/openspec`) generates on `openspec init`: slash commands / workflows and SKILL packages for `/opsx:propose`, `/opsx:apply`, `/opsx:archive`, `/opsx:explore`.

- One subfolder per supported tool (`cursor/`, `claude-code/`, `codex/`, `opencode/`, `kilocode/`); each mirrors the exact relative paths the CLI writes into a project (e.g. `cursor/.cursor/commands/opsx-apply.md`). The installer copies a tool's subtree during `init` / `add` / `update` — see `AGENT-INSTALL.md → Place / Shared OpenSpec scaffold`. Note: the Kilo Code subtree is stored in the upstream `.kilocode/` layout (`workflows/` + `skills/`), but the installer remaps it to `.kilo/` on placement (`workflows/` → `.kilo/commands/`, `skills/` → `.kilo/skills/`) so Kilo Code gets a single project folder that matches `adapters/kilocode.yaml`; an earlier `.kilocode/` install is cleaned up on `update`.
- `version.txt` — the OpenSpec CLI version the snapshot was generated from; recorded in `.ai-rules.json` under `integrations.openspec.artifactsBundleVersion` on install.
- Codex ships SKILLs only (no project slash commands); the `other` adapter has no bundle — see `README.md → OpenSpec`.

To refresh the snapshot to a newer OpenSpec CLI version, run `tools/refresh-openspec-bundle.ps1` (maintainer machine; requires Node.js + the globally installed OpenSpec CLI) and review the diff — the script re-runs `openspec init` per tool and refreshes `version.txt` itself. Do not hand-edit the generated files — they are overwritten on the next refresh.
