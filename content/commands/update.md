---
description: Обновить набор правил 1c-rules с GitHub (https://github.com/comol/ai_rules_1c)
---

# /update — обновить правила 1c-rules

Источник: `https://github.com/comol/ai_rules_1c`.

Действие: обновить managed-файлы текущей установки до актуальной версии репозитория (on-demand правила, описания субагентов, слэш-команды, SKILL-пакеты, MCP-конфиг, бандл OpenSpec, рендер `AGENTS.md`). Сохраняются:

- `USER-RULES.md` и `memory.md` — одноразовые шаблоны, не перезаписываются;
- содержимое `openspec/specs/` и `openspec/changes/` — копируется в режиме skip-if-exists;
- любой managed-файл, помеченный `userModified: true` в `.ai-rules.json`.

## Шаги

1. Убедиться, что в корне проекта есть `.ai-rules.json`. Если файла нет — это первая установка: выполнить `init` по `AGENT-INSTALL.md`, а не `update`.

2. Запустить PowerShell-канал из корня проекта. `install.ps1` ожидает в `-Source` локальный путь, поэтому сначала клонируем (или обновляем) исходник в кэш под `$env:TEMP`:

```powershell
$src = Join-Path $env:TEMP '1c-rules'
if (Test-Path (Join-Path $src '.git')) {
    git -C $src fetch --depth 1 origin HEAD
    git -C $src reset --hard FETCH_HEAD
} else {
    git clone --depth 1 https://github.com/comol/ai_rules_1c.git $src
}
& "$src\install.ps1" update -Source $src -AssumeYes
```

3. Проверить вывод установщика:
   - `Update complete.` — успех;
   - сообщения `User-modified files detected: N` — список файлов, в которых найдены локальные правки; они помечаются `userModified` и сохраняются;
   - сообщения `Verification OK` / `Verification found N mismatch(es)` — состояние свежеразложенных файлов.

4. Если PowerShell недоступен (ограниченная среда, нет `git`/`pwsh`) — выполнить раздел *Update / add / remove* из `AGENT-INSTALL.md` агентским каналом: переразложить managed-файлы из обновлённого клона, перерендерить `AGENTS.md` (плейсхолдеры `{{ rulesDir }}` / `{{ rulesExt }}`), обновить `version` и `updatedAt` в `.ai-rules.json`. `USER-RULES.md` и `memory.md` не трогать.

## Параметры

- `-AssumeYes` — отвечает «да» на подтверждения и оставляет пользовательские правки (`keep`) на конфликтных файлах. Для полностью автоматического запуска (CI) добавить `-NonInteractive`.
- `-Tools cursor,claude-code` — не нужно: список активных инструментов берётся из `.ai-rules.json`.
