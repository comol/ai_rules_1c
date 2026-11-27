---
description: List, install, update or remove optional 1C domain packs (ZUP 3.1, Data Exchange KD/EnterpriseData, 1C:Compatible audit, meeting-to-tasks)
argumentHint: "[status | list | add <pack,...|all> | remove <pack,...|all>]"
userOnly: true
---

# /install-packs — optional 1C domain packs

Manages optional domain packs shipped under `content/packs/` in the `1c-rules` source repository. Packs are **not** installed by default so core context stays lean; users may opt in during initial setup (`install.ps1 init -Packs ...`) or add/remove them at any time with this command.

## Catalog (`content/packs/packs.json`)

| Pack ID | Title | Contents |
|---|---|---|
| `zup-hr` | 1С:ЗУП 3.1 (кадровый учёт и расчёт зарплаты) | `rules/zup-hr-patterns.md` |
| `data-exchange` | Обмены 1С (КД 2.0, КД 3.1, EnterpriseData) | `rules/exchange-kd-patterns.md` |
| `1c-compatible` | Аудит «1С:Совместимо» и словарь терминов 1С | `rules/1c-compatible-audit.md` |
| `meeting-to-tasks` | Разбор встреч в задачи и OpenSpec | `skills/meeting-to-tasks/SKILL.md` |

## Steps

### 1. Inspect current state (`status` / `list` / no arguments)

1. Read `.ai-rules.json` at the project root:
   - `source` — local source clone path (or fallback `https://github.com/comol/ai_rules_1c`);
   - `tools` — active installed tools;
   - `packs` — currently installed pack IDs (empty array if absent).
2. Read `<source>/content/packs/packs.json` (if the cached clone is missing, run `install.ps1 packs list -Source https://github.com/comol/ai_rules_1c` or clone to a temporary cache per `AGENT-INSTALL.md`).
3. Print a compact Russian table of all available packs with `installed` / `not installed` status and one-line purpose.
   - For `/install-packs status` or `/install-packs list`: stop here without modifying files.
   - For bare `/install-packs`: ask once which pack IDs to install (`add`) or remove (`remove`), or `none`.

### 2. Install (`add <pack,...|all>`) or remove (`remove <pack,...|all>`)

Prefer the deterministic PowerShell channel when PowerShell and `install.ps1` are available:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<source>\install.ps1" packs add -Packs "<id1,id2>" -ProjectRoot "<projectRoot>" -NonInteractive
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<source>\install.ps1" packs remove -Packs "<id1>" -ProjectRoot "<projectRoot>" -NonInteractive
```

If running purely through the agent channel (without PowerShell):

- **Add:** for each selected pack in `packs.json`, place each rule into every active tool's `rules.copyTo` (applying its adapter frontmatter transform and canonical path rewriting) and each skill into every active tool's `skills.copyTo` (`mode: verbatim`, rewriting `content/...` references). Record every placed file in `.ai-rules.json` (`files` with `source: "content/packs/<id>/..."` and `owners`) and add `<id>` to `manifest.packs`.
- **Remove:** delete only manifest-tracked files whose `source` starts with `content/packs/<id>/` (preserving any file with `userModified: true` unless forced) and remove `<id>` from `manifest.packs`.

Do **not** modify `AGENTS.md` or `.dev.env` when adding or removing packs — installed packs live in the tool's on-demand rules / skills directories and update automatically on `/updaterules` (`install.ps1 update`).

### 3. Report

Report concisely in Russian: installed / removed pack IDs, placed or removed files, and currently active packs.
