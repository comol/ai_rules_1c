---
description: Send a problem report about a 1C MCP server or about the 1c-rules ruleset to the support service (Yandex Cloud Function -> Yandex Database)
argumentHint: "[mcp|rules] <краткое описание проблемы>"
---

# /support — report a problem with MCP or with the rules

The command sends a ticket to the support service: **Yandex Cloud Function → Yandex Database**. A new ticket is created with status **`новый`**; the operator handles it and moves it to **`закрыт`**, attaching an answer when needed. The status of your own tickets — `/supportstatus`.

The full contract of the channel (preconditions, what may and may not be sent, the rules for model-initiated tickets) — `content/rules/support-feedback.md`. This file is the procedure.

## Preconditions (hard)

Read `.dev.env` at the project root. A ticket is sent **only** when **both** parameters are filled:

| Parameter | Meaning |
|---|---|
| `SUPPORT_KEY` | shared support key; ships with the MCP distribution (`config.env` from `MCP_Distr`) |
| `SUPPORT_EMAIL` | working e-mail of the ticket author; the operator answers to it |
| `SUPPORT_API_URL` | service endpoint (Defaulted) |

Parameters, classes and defaults — `content/rules/dev-standards-env-process.md`; Defaulted keys are never asked for.

If `SUPPORT_KEY` **or** `SUPPORT_EMAIL` is empty — **send nothing**. Answer with one message saying what is missing and where to get it:

> Обращение не отправлено: в `.dev.env` не заполнен `<SUPPORT_KEY|SUPPORT_EMAIL|оба>`.
> `SUPPORT_KEY` и `SUPPORT_API_URL` лежат в `config.env` дистрибутива MCP (по умолчанию
> `C:\Work\MCP_Distr\config.env`, раздел 6), перенос описан в `INSTALL.md` → ШАГ 6.
> `SUPPORT_EMAIL` — ваш рабочий e-mail, укажите его сами. Свежий дистрибутив с ключом —
> личный кабинет https://vibecoding1c.ru/.

Do not invent a key, do not take one from another project, and do not offer to send the ticket "directly to the developer" without a key.

## Step 1. Determine the ticket type

The command argument or the nature of the problem gives `kind`:

- `mcp` — an MCP server: does not start, does not respond, returns garbage, a tool is missing, a search result is plainly wrong, a licence error;
- `rules` — the `1c-rules` ruleset: a rule contradicts the platform or another rule, a command describes a non-existent step, an instruction leads to non-working code;
- `other` — everything else (distribution, documentation, personal cabinet).

The type is not guessed from a single word — ask with one question.

## Step 2. Collect the environment facts

Without the environment a ticket is nearly useless, so collect it yourself instead of asking the user.

### For `kind = mcp` — the tag is mandatory

Since 27.09.2026 images are published in one channel under the variant tags `latest` / `light` / `arm64`. A bug on `light` and the same bug on `latest` may differ, so the tag is taken from the **actually running container**, not from `config.env`:

```powershell
docker ps --format '{{.Names}}' | ForEach-Object {
    [pscustomobject]@{
        Container = $_
        Image     = (docker inspect $_ --format '{{.Config.Image}}')
    }
} | Format-Table -AutoSize
```

From an `Image` like `comol/1c_help_mcp:light` derive:

- `component` — the server id per the `/checkmcp` catalog (`1c-help-mcp`, `1c-code-metadata-mcp`, …);
- `image_tag` — `light`;
- `channel` — always `stable`.

A container on a `*-beta` tag (any spelling, also `latestbeta`) or on an image created before 27.09.2026 is outdated. Suggest `/updatemcp` and a re-check on the current image first; if the person still files the ticket, `image_tag` carries the actual tag and the text says the image is outdated.

Add a digital fingerprint to `context`: the local image digest (`docker image inspect <image> --format '{{index .RepoDigests 0}}'`), the exact error text from the logs (`docker logs --tail 50 <container>`), and the name of the MCP tool on which the problem reproduced.

### For `kind = rules`

- `component` — the file name of the rule or command (`mcp-first-search.md`, `updatemcp.md`);
- `channel` / `image_tag` — left empty;
- in `context` — `version` and `updatedAt` from `.ai-rules.json`, the active tool (cursor / claude-code / opencode / …), `AGENT_MODEL` from `.dev.env`.

## Step 3. Compose the ticket text

`title` — one line, the essence of the problem. `text` — in this structure (the operator reads Russian; keep the labels as data):

```
Что делал:      <минимальный сценарий, по шагам>
Что ожидал:     <ожидаемое поведение и на чём оно основано — пункт правила / документации>
Что получилось: <фактическое поведение, дословный текст ошибки>
Воспроизводимость: <всегда / иногда / один раз>
```

**What must not be sent.** Everything goes to an external service, so scrub from `title`, `text` and `context`:

- licence keys (`LICENSE_KEY_*`), API keys (`EMBEDDING_API_KEY`, `CHAT_API_KEY`, `ONEC_AI_TOKEN`), `SUPPORT_KEY`, passwords, tokens;
- infobase connection strings, logins, paths with user names when they are not needed for the point;
- personal data from the base;
- large listings. A whole module is not needed: a 10–30 line fragment around the problem spot is enough. Field limits: `text` — 60 000 characters, `context` — 40 000.

## Step 4. Show and confirm

The ticket leaves the machine, so sending is **always** confirmed by a human — both when the user invoked the command and when you initiated it yourself. Show the complete body (e-mail, type, component, channel/tag, title, text, context) and ask in one line:

> Отправляю обращение в поддержку с этим текстом? (да / нет / поправить)

On «поправить» — edit the text and show it again. Nothing is sent without an explicit «да».

## Step 5. Send

The body is built as a **separate UTF-8 JSON file**, and the script itself stays pure ASCII: Windows PowerShell 5.1 reads a BOM-less `.ps1` as ANSI and mangles Cyrillic in literals. Write the file with your file-writing tool, not via `Set-Content` with Cyrillic inside.

`<TEMP>\support-ticket.json`:

```json
{
  "email": "dev@example.com",
  "kind": "mcp",
  "component": "1c-help-mcp",
  "channel": "stable",
  "image_tag": "light",
  "title": "standards не находит раздел про блокировки",
  "text": "Что делал: ...\nЧто ожидал: ...\nЧто получилось: ...\nВоспроизводимость: всегда",
  "source": "user",
  "context": "{\"digest\":\"sha256:...\",\"tool\":\"cursor\",\"rules_version\":\"6f5a738\"}"
}
```

- `source` — `user` when a human invoked the command; `model` when the initiative was yours (see `support-feedback.md`). The field is not decorative: the operator uses it to separate what the model found from what a human found.

Sending (ASCII script, values read from `.dev.env`):

```powershell
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$devEnv = @{}
Get-Content '.dev.env' | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=(.*)$') { $devEnv[$Matches[1]] = $Matches[2].Trim() }
}
$key = $devEnv['SUPPORT_KEY']
$api = $devEnv['SUPPORT_API_URL']
if (-not $api) { $api = 'http://104.249.10.238:18082' }
if (-not $key -or -not $devEnv['SUPPORT_EMAIL']) { throw 'SUPPORT_KEY / SUPPORT_EMAIL are empty in .dev.env' }

$file = Join-Path $env:TEMP 'support-ticket.json'
$resp = Invoke-RestMethod -Uri "$api/api/tickets" -Method Post `
    -Headers @{ 'X-Support-Key' = $key } `
    -ContentType 'application/json; charset=utf-8' -InFile $file
Remove-Item $file -ErrorAction SilentlyContinue
$resp.ticket | Select-Object id, status, kind, component, created_at | Format-List
```

`-InFile` instead of `-Body` is mandatory: the body goes as the file's bytes and Cyrillic is not re-encoded on the way.

## Step 6. Report

Success (`201`) — show `id`, `status` (`новый`) and the time. Say that the status is viewed via `/supportstatus` and that the operator's answer arrives at `SUPPORT_EMAIL`.

Errors:

| Response | What happened | What to do |
|---|---|---|
| `401 invalid_support_key` | the key is wrong or revoked | take a fresh `SUPPORT_KEY` from a new distribution (personal cabinet https://vibecoding1c.ru/) and put it into `.dev.env` |
| `400 email_required` | `SUPPORT_EMAIL` is empty or does not look like an address | fix `.dev.env` |
| `400 field_too_long` | a field limit was exceeded | shorten the text / drop the listing |
| `400 invalid_kind` / `invalid_channel` | invalid value | `kind` — `mcp`/`rules`/`other`, `channel` — `stable` |
| network unavailable | no internet or the service is down | keep the ready ticket text in the answer to the user so it is not lost, and offer to retry later |

Never print `SUPPORT_KEY` into chat, into a log, or into the ticket text.
