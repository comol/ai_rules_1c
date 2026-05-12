---
description: Check availability of 1C MCP servers and install/start the missing ones
---

# Проверка и установка MCP-серверов для 1С

Команда проверяет, что все MCP-серверы из каталога проекта (`content/mcp-servers.json`; после установки 1c-rules — рендер в конфиг активного инструмента, например `.cursor/mcp.json` / `.mcp.json` / `.opencode/opencode.json` / `.codex/config.toml`) реально доступны в текущей сессии, и помогает запустить/установить то, чего не хватает.

Источник правды по образам, портам и переменным окружения — [docs.onerpa.ru/mcp-servery-1c](https://docs.onerpa.ru/mcp-servery-1c) и [vibecoding1c.ru/mcp_server](https://vibecoding1c.ru/mcp_server).

## Целевой каталог серверов

| id | Порт | Docker-образ | Назначение | Требует данных |
|---|---|---|---|---|
| `1c-syntax-checker-mcp` | 8002 | `comol/1c_syntaxcheck_mcp:latest` | Синтаксис BSL (BSL Language Server) | Нет |
| `1c-templates-mcp` | 8004 | `comol/1c_templates_mcp:latest` | Шаблоны и проектная память (`remember`/`recall`) | Нет |
| `1c-ssl-mcp` | 8008 | `comol/mcp_ssl_server:latest` | Поиск по БСП | Нет (`SSL_VERSION`) |
| `1C-docs-mcp` | 8003 | `comol/1c_help_mcp:latest` | Справка платформы 1С (RAG) | Да — папка `bin` платформы |
| `1c-code-metadata-mcp` | 8000 | `comol/1c_code_metadata_mcp:latest` | Метаданные/код/формы/XSD | Да — выгрузка конфигурации |
| `1c-graph-metadata-mcp` | 8006 | `comol/1c_graph_metadata_mcp:latest` | Графовый поиск (Neo4j) | Да — выгрузка + Neo4j |
| `1c-code-check-mcp` | 8007 | `comol/1c_code_checker_mcp:latest` | 1С:Напарник, ИТС | Нет (токен Напарника) |

> Точные имена образов могут отличаться от версии к версии — если `docker pull` падает с `manifest unknown`, свериться с актуальным списком на [docs.onerpa.ru/mcp-servery-1c/servery.md](https://docs.onerpa.ru/mcp-servery-1c/servery.md).

## Алгоритм

### Шаг 1. Определить набор серверов

1. Если в проекте есть `.ai-rules.json` — взять каталог из конфига активного инструмента, который указан в манифесте (`.cursor/mcp.json` / `.mcp.json` / `.opencode/opencode.json` / `.codex/config.toml`).
2. Иначе — взять `content/mcp-servers.json` из репозитория правил.
3. Если ничего из этого нет — использовать таблицу выше как набор по умолчанию.

### Шаг 2. Проверить доступность в текущей сессии агента

Для каждого `id` определить статус **TOOLS_OK** / **TOOLS_MISSING**:

- **TOOLS_OK** — инструменты этого сервера видны в схеме инструментов текущей сессии (например, `syntaxcheck` для `1c-syntax-checker-mcp`, `templatesearch`/`recall` для `1c-templates-mcp`, `ssl_search` для `1c-ssl-mcp`, `docinfo`/`docsearch` для `1C-docs-mcp`, `metadatasearch`/`codesearch` для `1c-code-metadata-mcp`, `search_metadata`/`get_object_dossier` для `1c-graph-metadata-mcp`, `check_1c_code`/`its_help` для `1c-code-check-mcp`).
- **TOOLS_MISSING** — инструментов в схеме нет.

Если статус **TOOLS_OK** — сервер считается рабочим, дальше не проверять.

### Шаг 3. Проверить HTTP-эндпоинт

Для серверов со статусом **TOOLS_MISSING** дёрнуть HTTP-эндпоинт. PowerShell (Windows):

```powershell
$servers = @(
    @{ Id = '1c-code-metadata-mcp';   Port = 8000 },
    @{ Id = '1c-syntax-checker-mcp';  Port = 8002 },
    @{ Id = '1C-docs-mcp';            Port = 8003 },
    @{ Id = '1c-templates-mcp';       Port = 8004 },
    @{ Id = '1c-graph-metadata-mcp';  Port = 8006 },
    @{ Id = '1c-code-check-mcp';      Port = 8007 },
    @{ Id = '1c-ssl-mcp';             Port = 8008 }
)
foreach ($s in $servers) {
    $url = "http://localhost:$($s.Port)/mcp"
    try {
        $r = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        Write-Host ("{0,-26} {1,-5} HTTP {2}" -f $s.Id, $s.Port, $r.StatusCode)
    } catch {
        $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 'down' }
        Write-Host ("{0,-26} {1,-5} {2}" -f $s.Id, $s.Port, $code)
    }
}
```

Любой HTTP-ответ (даже `405`/`400`/`406`) означает, что порт слушает контейнер — статус **HTTP_OK**. Полный таймаут / `Connection refused` — статус **HTTP_DOWN**.

### Шаг 4. Проверить состояние Docker

Если есть хотя бы один **HTTP_DOWN**:

```powershell
docker version --format '{{.Server.Version}}'
docker ps --all --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

Возможные исходы:

- `docker version` падает с ошибкой подключения к движку → **DOCKER_DOWN** (Docker Desktop не запущен) — попросить пользователя запустить Docker Desktop и повторить `/checkmcp`.
- Контейнер виден в `docker ps -a`, но в состоянии `Exited` → **CONTAINER_STOPPED** — запустить:

  ```powershell
  docker start <container_name>
  ```

  Имена по умолчанию: `1c_syntaxcheck_mcp`, `1c_templates_mcp`, `mcp_ssl_server`, `1c_help_mcp`, `1c_code_metadata_mcp`, `1c_graph_metadata_mcp`, `1c_code_checker_mcp` (фактическое имя смотреть в выводе `docker ps -a`).

- Контейнера нет в `docker ps -a` → **CONTAINER_MISSING**. Образ может уже лежать в кэше (`docker images`), но контейнер не создан. Создать и запустить — см. шаг 5.

### Шаг 5. Установить недостающий сервер

**Не запускать `docker run` молча.** Сначала запросить у пользователя:

- `LICENSE_KEY` — лицензионный ключ MCP-серверов (общий для всех).
- Пути к локальным данным для серверов, которые этого требуют:
  - `1C-docs-mcp` — путь к папке `bin` платформы (например, `C:\Program Files\1cv8\8.3.23.1997\bin`).
  - `1c-code-metadata-mcp`, `1c-graph-metadata-mcp` — путь к каталогу выгрузки конфигурации (`DumpConfigToFiles`).
  - `1c-ssl-mcp` — версия БСП (`SSL_VERSION`, например `3.1.11`).
  - `1c-code-check-mcp` — токен 1С:Напарника, если планируется использовать.
- Каталог для томов индексов (`-v ...:/app/chroma_db`) — общая папка вроде `E:\bases\mcp_<id>`.

Шаблоны команд запуска (минимальный набор без подготовки данных):

```powershell
# 1c-syntax-checker-mcp
docker run -d -p 8002:8002 --name 1c_syntaxcheck_mcp `
  -e LICENSE_KEY={LICENSE_KEY} `
  comol/1c_syntaxcheck_mcp:latest

# 1c-templates-mcp
docker run -d -p 8004:8004 --name 1c_templates_mcp `
  -e LICENSE_KEY={LICENSE_KEY} `
  -v "{DATA_ROOT}\mcp_templates:/app/chroma_db" `
  comol/1c_templates_mcp:latest

# 1c-ssl-mcp
docker run -d -p 8008:8008 --name mcp_ssl_server `
  -e LICENSE_KEY={LICENSE_KEY} `
  -e SSL_VERSION={SSL_VERSION} `
  -v "{DATA_ROOT}\mcp_ssl:/app/chroma_db" `
  comol/mcp_ssl_server:latest

# 1C-docs-mcp
docker run -d -p 8003:8003 --name 1c_help_mcp `
  -e LICENSE_KEY={LICENSE_KEY} `
  -v "{PLATFORM_BIN}:/1c_docs" `
  -v "{DATA_ROOT}\mcp_docs:/app/chroma_db" `
  comol/1c_help_mcp:latest

# 1c-code-metadata-mcp
docker run -d -p 8000:8000 --name 1c_code_metadata_mcp `
  -e LICENSE_KEY={LICENSE_KEY} `
  -v "{EXPORT_PATH}:/app/configuration" `
  -v "{DATA_ROOT}\mcp_code_metadata:/app/chroma_db" `
  comol/1c_code_metadata_mcp:latest

# 1c-graph-metadata-mcp — отдельная установка Neo4j, см. документацию
# https://docs.onerpa.ru/mcp-servery-1c/servery/graph-metadata-search.md

# 1c-code-check-mcp
docker run -d -p 8007:8007 --name 1c_code_checker_mcp `
  -e NAPARNIK_TOKEN={NAPARNIK_TOKEN} `
  comol/1c_code_checker_mcp:latest
```

Точные актуальные команды для каждого сервера — на странице конкретного сервера в документации:

- [HelpSearchServer](https://docs.onerpa.ru/mcp-servery-1c/servery/help-search-server.md)
- [CodeMetadataSearchServer](https://docs.onerpa.ru/mcp-servery-1c/servery/code-metadata-search.md)
- [Graph Metadata Search](https://docs.onerpa.ru/mcp-servery-1c/servery/graph-metadata-search.md)
- [SSLSearchServer](https://docs.onerpa.ru/mcp-servery-1c/servery/ssl-search-server.md)
- [SyntaxCheckServer](https://docs.onerpa.ru/mcp-servery-1c/servery/syntax-check-server.md)
- [TemplatesSearchServer](https://docs.onerpa.ru/mcp-servery-1c/servery/templates-search-server.md)
- [1CCodeChecker](https://docs.onerpa.ru/mcp-servery-1c/servery/code-checker.md)

### Шаг 6. После установки/запуска

1. Подождать 5–15 секунд (контейнеру нужно прогреться; для серверов с RAG-индексацией — десятки минут до часов на первом запуске, следить через `docker logs -f <name>`).
2. Повторить шаг 3 (HTTP-проверка) — все статусы должны стать **HTTP_OK**.
3. Если в MCP-конфиге активного инструмента сервер отсутствует — добавить запись (соответствующий рендер уже сделан установщиком 1c-rules; если установка не запускалась — внести вручную, см. `adapters/<tool>.yaml → mcp.schema`).
4. Перезапустить клиент (Cursor / Claude Code / Codex / OpenCode / Kilo Code), чтобы он переинициализировал MCP-сессию.
5. Запустить `/checkmcp` ещё раз — статусы шага 2 должны стать **TOOLS_OK**.

## Финальный отчёт

Сводная таблица для пользователя:

| Сервер | Tools в сессии | HTTP | Контейнер | Действие |
|---|---|---|---|---|
| `…` | OK / нет | OK / down | running / stopped / missing | ничего / `docker start` / `docker run` / переподключить клиент |

Под таблицей — список явных следующих шагов (с командами под копирование), без перечисления того, что уже работает.

## Ограничения

- Команда не запускает `docker run` без подтверждения пользователя — нужны `LICENSE_KEY`, пути к данным и согласие на скачивание образов (несколько ГБ).
- Графовый MCP (`1c-graph-metadata-mcp`) требует отдельной установки Neo4j и индексации — это многошаговый процесс, его выполнять по документации на странице сервера, а не из этой команды.
- Серверы с RAG-индексацией (`1C-docs-mcp`, `1c-code-metadata-mcp`, `1c-graph-metadata-mcp`, `1c-ssl-mcp`) могут отвечать на HTTP, но ещё не быть полезными — пока идёт первичная индексация. Это нормально, проверять прогресс через `docker logs -f <name>`.
