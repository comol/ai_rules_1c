# OpenSpec

> **AI agents:** if you need to install or update project rules, go to [`AGENT-INSTALL.md`](../AGENT-INSTALL.md). This file is a human-oriented overview of the OpenSpec workspace.

Spec-driven development workspace for this project, structured per the
[Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) v1.0+ workflow
(OPSX, artifact-guided).

This folder is bundled by the `1c-rules` installer (see `AGENT-INSTALL.md`,
phase **Place / Shared OpenSpec scaffold**) so every project that installs
`1c-rules` starts with a ready-to-use OpenSpec layout. The installer copies
files in **skip-if-exists** mode — your existing specs and change proposals
are never overwritten.

## Directory layout

```
openspec/
├── README.md           # this file
├── config.yaml         # optional project-level OpenSpec config
├── project.md          # auto-generated 1C project context (see below)
├── specs/              # source of truth: how the system currently behaves
│   └── <domain>/
│       └── spec.md
└── changes/            # active proposals (one folder per change)
    ├── archive/        # completed changes (created by `openspec archive`)
    └── <change-name>/
        ├── proposal.md # why & what is changing
        ├── design.md   # how (technical decisions, optional)
        ├── tasks.md    # implementation checklist
        └── specs/      # delta specs (ADDED / MODIFIED / REMOVED)
            └── <domain>/
                └── spec.md
```

## Auto-generated `project.md` (1C context)

The installer inspects the project root on every `init` and `update` and
regenerates `openspec/project.md` from real 1C metadata signals:

- `Configuration.xml` / `ConfigurationExtension.xml` — name, synonym, vendor,
  edition, `CompatibilityMode` (→ platform version), `DefaultRunMode` +
  `Use*FormIn*Application` (→ form mode: managed / ordinary / mixed),
  `NamePrefix` (→ extension marker)
- `CommonModules/СтандартныеПодсистемыСервер/Ext/Module.bsl` (or English
  `StandardSubsystemsServer`) — БСП presence and version (parsed from
  `Функция ВерсияБиблиотеки()` / `Function LibraryVersion()`)
- `Subsystems/*.xml` — top-level subsystems
- `Catalogs/`, `Documents/`, `*Registers/`, `CommonModules/`, … — metadata
  counts

The file is tracked in `.ai-rules.json` like any other managed content. If
you edit it manually, the installer marks it `userModified` and stops
overwriting it. To pick up changes after editing `Configuration.xml`,
delete `openspec/project.md` and re-run `install.ps1 update`.

If the project is not a 1C source dump (no `Configuration.xml`), the bundled
fallback `project.md` remains with `unknown` values until real metadata is
available.

## Activating slash commands

OpenSpec slash commands (`/opsx:propose`, `/opsx:apply`, `/opsx:archive`,
`/opsx:explore`, `/opsx:sync`, `/opsx:update`) and the matching SKILLs are placed automatically by the
`1c-rules` installer for every active tool — **no `npm` and no OpenSpec CLI
required at install time**. The installer ships a snapshot of `openspec init`
output under `content/openspec-bundle/<tool>/` and copies the per-tool files
during phases 6c (`init` / `add`) and *OpenSpec artefacts (update)* (`update`).
The OpenSpec CLI version of the bundled snapshot is recorded in
`.ai-rules.json` under `integrations.openspec.artifactsBundleVersion`.

After installation you should already see, depending on which tools are active:

- Cursor — `.cursor/commands/opsx-{apply,archive,explore,propose,sync,update}.md`
- Claude Code — `.claude/commands/opsx/{apply,archive,explore,propose,sync,update}.md`
- Codex — only SKILLs under `.codex/skills/openspec-*/SKILL.md` (Codex has no project slash commands; the upstream `.agents/skills/` output is remapped there)
- OpenCode — `.opencode/command/opsx-{apply,archive,explore,propose,sync,update}.md` (upstream `.opencode/commands/`, remapped to the adapter's folder)
- Kilo Code — `.kilo/commands/opsx-{apply,archive,explore,propose,sync,update}.md` (the upstream `.kilocode/workflows/` layout is remapped by the installer — see `adapters/kilocode.yaml`)

…plus matching `openspec-{propose,apply-change,archive-change,explore,sync-specs,update-change}/SKILL.md`
folders under each tool's `skills/` directory. Restart your IDE for the
slash commands to take effect.

### Refreshing to a newer OpenSpec version (optional)

The bundled snapshot is updated together with `1c-rules` releases. If you
want to jump ahead to a newer OpenSpec CLI version without waiting for the
next `1c-rules` release, install the official CLI once and run it inside
the project — it will overwrite the bundled files in place:

```bash
npm install -g @fission-ai/openspec@latest
openspec update      # refresh slash commands and SKILLs to the current CLI version
```

This is purely optional. After a subsequent `1c-rules` update, the bundled
snapshot's version takes over again (unless you've marked the affected files
as user-modified, in which case `1c-rules` preserves your edits).

## Workflow (default core profile)

```
/opsx:propose <idea>   →  /opsx:apply   →  /opsx:archive
```

1. **propose** — AI creates `proposal.md`, delta `specs/`, `design.md`, and
   `tasks.md`. Full-cycle artifacts define an observable Definition of Done
   (DoD), with acceptance criteria and tasks for testing and review.
2. **apply** — AI implements, runs tests, reviews the final change, fixes
   blocking findings and reconciles DoD with evidence. Testing and review
   are required for full-cycle unless explicitly waived by the user; waivers
   are recorded separately from passes. CLI `all_done` / checked tasks alone
   do not establish completion. Missing verification keeps DoD incomplete.
3. **archive** — after checking DoD evidence, completed changes merge into `specs/` and the change folder
   is moved to `changes/archive/<date>-<change-name>/`.

Browser testing retains its `UI_TESTING` policy; disabling it does not cancel
all testing. Separate reviewer agents retain their launch conditions; the
parent performs full-cycle review by default. The completion contract lives
in [`sdd-integrations.md`](../content/rules/sdd-integrations.md).

For deeper guidance see:

- Getting started — <https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md>
- Workflows — <https://github.com/Fission-AI/OpenSpec/blob/main/docs/workflows.md>
- Commands — <https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md>

## Integration with `1c-rules`

The detailed agent-side rules for how to read and update this folder live in:

- source repository: [`content/rules/sdd-integrations.md`](../content/rules/sdd-integrations.md)
- installed project: the canonical rules directory referenced from `AGENTS.md`

That file is loaded on demand whenever an SDD framework is detected in the project.

The installer also records the presence of this folder in
`.ai-rules.json` under `integrations.openspec` so other agents can detect it
without scanning the filesystem.
