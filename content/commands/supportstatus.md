---
description: Show the status of your support tickets about MCP servers and the 1c-rules ruleset, and close a ticket you no longer need
userOnly: true
argumentHint: "[новый|закрыт|<id тикета>|close <id тикета>]"
---

# /supportstatus — status of support tickets

Shows the tickets sent by `/support` from this `SUPPORT_EMAIL`. There are only two statuses: **`новый`** (accepted, not yet handled) and **`закрыт`** (handled; the `answer` field may hold the operator's reply).

## Preconditions

The same as for `/support`: `SUPPORT_KEY` and `SUPPORT_EMAIL` are filled in `.dev.env` (`SUPPORT_API_URL` is Defaulted). Parameters, classes and defaults — `content/rules/dev-standards-env.md §1`; Defaulted keys are never asked for. Empty — do not go to the network; say what is missing and where to get it (`/support` → *Preconditions*).

A client key sees **only its own** tickets: the service filters them by `SUPPORT_EMAIL`. Other people's tickets are not returned for this key — that is not a failure.

## Arguments

| Argument | Action |
|---|---|
| empty | the last 50 tickets, newest first |
| `новый` / `new` | only unhandled ones |
| `закрыт` / `closed` | only closed ones, with the operator's answers |
| `<id>` | one ticket in full: text, `context`, answer |
| `close <id>` | close your own ticket (the problem went away / resolved itself) |

The status may be written in Latin letters — the service accepts `new` / `closed` alongside the Cyrillic values. That is more reliable: Cyrillic in a query string from PowerShell regularly arrives in the wrong encoding.

## Execution

Keep the script in **pure ASCII**: Windows PowerShell 5.1 reads a BOM-less `.ps1` as ANSI and mangles any Cyrillic in literals — hence the English output labels. If you need Cyrillic inside the script, save the file as UTF-8 **with BOM**. Switch the output to UTF-8, otherwise Cyrillic coming from the server turns into garbage in the console.

### List

```powershell
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$devEnv = @{}
Get-Content '.dev.env' | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=(.*)$') { $devEnv[$Matches[1]] = $Matches[2].Trim() }
}
$key   = $devEnv['SUPPORT_KEY']
$email = $devEnv['SUPPORT_EMAIL']
$api   = $devEnv['SUPPORT_API_URL']
if (-not $api) { $api = 'https://d5ds85pood7ob80g5fd9.nnekmrav.apigw.yandexcloud.net' }
if (-not $key -or -not $email) { throw 'SUPPORT_KEY / SUPPORT_EMAIL are empty in .dev.env' }

# $status: '' | 'new' | 'closed'
$status = ''
$url = "$api/api/tickets?email=$([Uri]::EscapeDataString($email))&limit=50"
if ($status) { $url += "&status=$status" }

$resp = Invoke-RestMethod -Uri $url -Headers @{ 'X-Support-Key' = $key }
"Total: $($resp.total), new: $($resp.total_new)"
$resp.tickets | Select-Object @{n='id';e={$_.id.Substring(0,8)}}, status, kind, component, title, created_at |
    Format-Table -AutoSize
```

### One ticket

```powershell
$resp = Invoke-RestMethod -Uri "$api/api/tickets/$id`?email=$([Uri]::EscapeDataString($email))" `
    -Headers @{ 'X-Support-Key' = $key }
$resp.ticket | Format-List id, status, kind, component, channel, image_tag, title, text, context, answer, created_at, closed_at
```

### Close your own ticket

Closing is the user's action, not your initiative. Ask for confirmation («Закрываю обращение `<id>` — `<заголовок>`?») and only then send. The body here is short and has no Cyrillic, so `-Body` is enough:

```powershell
$body = "{""status"":""closed"",""email"":""$email""}"
$resp = Invoke-RestMethod -Uri "$api/api/tickets/$id/status" -Method Post `
    -Headers @{ 'X-Support-Key' = $key } `
    -ContentType 'application/json; charset=utf-8' -Body $body
$resp.ticket | Select-Object id, status, closed_at | Format-List
```

A closed ticket cannot be returned to `новый` with the client key — that is the operator's right (`403 admin_key_required`). If the problem came back, send a new ticket via `/support` and refer to the previous `id` in the text.

## Report

- There are closed tickets with a non-empty `answer` — show the operator's answer as a separate block; it is the main thing in the command's output.
- Nothing — say so: «обращений с этого e-mail нет». Do not invent tickets and do not show other people's.
- Errors — the table in `/support` → *Step 6*. `401 invalid_support_key` most often means the key went stale after a distribution update.

Never print `SUPPORT_KEY` into chat or into logs.
