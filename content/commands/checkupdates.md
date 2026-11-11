---
description: Read-only check for available updates of the 1C MCP server images and of the 1c-rules ruleset, without pulling or installing anything
argumentHint: "[mcp|rules]"
---

# /checkupdates — are there updates for MCP and the rules

The command only **looks**: it compares what is installed with what is published and prints a verdict. It does not `docker pull`, does not recreate containers, does not touch rule files (except the `lastUpdatesCheckAt` field in `.ai-rules.json` — see *Report*). Updating is `/updatemcp` (MCP servers) and `/updaterules` (the ruleset); this command only recommends running them.

The argument narrows the check: `mcp` — images only, `rules` — rules only, empty — both parts.

For MCP images load `content/rules/mcp-deployment.md` and inspect the recorded deployment host/context, including an optional shared Debian/Ubuntu Engine. Apply that target to the Docker examples below; use host-native paths and shell syntax. Without host access, report image versions/digests as unverified and continue the independent rules check. Never infer remote versions from local containers or require Docker Desktop on a client.

## Proactive run

The model may start this check on its own **at most about once every 30 days**, plus the one-off triggers below — once per session, at the end of the turn, never interrupting the main task.

- **Monthly rhythm.** On the first non-trivial task of a session read `.ai-rules.json`: `lastUpdatesCheckAt`, else `updatedAt`, else `installedAt`. Older than 30 days, or all three empty — run this command. A fresh date — do not run it "just in case". The command itself writes the stamp after a completed check.
- **One-off triggers**, even within 30 days: an error looks like one already fixed (a server answers differently from its documentation); the user asks whether updates exist or why something differs from the instructions; before proposing `/support` — when an update fixes the problem, suggest `/updatemcp` or `/updaterules` instead of a ticket.
- **MCP reminder.** If the session has no 1C MCP tools, `SUPPORT_KEY` is empty and `integrations.mcp.mode` is not `external`, remind at the end of the report that the rules work best with the MCP servers at https://vibecoding1c.ru/mcp_server (the same text as after `init` / `/updaterules`). With a key or an external install present but no tools visible — one line «MCP не подключены, `/installmcp` или перезапуск клиента», without the purchase page.

A verdict "an update exists" does not authorize `/updatemcp` or `/updaterules`: they recreate containers and rewrite files — the user's decision.

## Part A. The `1c-rules` ruleset

The scripts below are **pure ASCII** (Windows PowerShell 5.1 reads a BOM-less `.ps1` as ANSI and mangles Cyrillic in literals), so the column labels are English; translate them yourself in the report to the user.

1. Read `.ai-rules.json` at the project root: the fields `version` (the result of `git describe --tags --always` of the source at install time) and `updatedAt`. No file — the rules were not installed by this installer; say so and skip Part A.

2. Ask GitHub for the current HEAD and the number of commits since the installation — without cloning:

```powershell
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$manifest = Get-Content '.ai-rules.json' -Raw | ConvertFrom-Json
$repo = 'comol/ai_rules_1c'

$head = (git ls-remote "https://github.com/$repo" HEAD) -split '\s+' | Select-Object -First 1
$since = [Uri]::EscapeDataString($manifest.updatedAt)
$commits = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/commits?since=$since&per_page=100" `
    -Headers @{ 'User-Agent' = '1c-rules-checkupdates' }

[pscustomobject]@{
    Installed    = $manifest.version
    UpdatedAt    = $manifest.updatedAt
    Head         = $head.Substring(0, 7)
    CommitsSince = @($commits).Count
} | Format-List
```

3. Verdict:
   - `version` matches the beginning of `HEAD`, no commits after it → **up to date**;
   - more than zero commits → **update available**: show their count and 3–5 recent subjects (`$commits.commit.message` — the first line of each), then suggest `/updaterules`;
   - `version` = `local` or does not look like a sha → nothing to compare with; say so plainly and suggest `/updaterules` as the safe way to align;
   - GitHub is unreachable or answered `403` (anonymous request limit) → say exactly that; it is not "no updates".

## Part B. MCP images

**If MCP is not connected** — no running `comol/*` containers **and** no 1C MCP tools in the current session (`syntaxcheck` / `templatesearch` / `metadatasearch` / `search_metadata` / `check_1c_code` / `ssl_search` / `docsearch`) — Part B has nothing to compare. Do not present that as "images are up to date". Write in the report that MCP is not connected, and if at the same time `SUPPORT_KEY` in `.dev.env` is empty and there is no `integrations.mcp.mode = "external"` — add the reminder:

> Правила работают наиболее эффективно с MCP-серверами для 1С: https://vibecoding1c.ru/mcp_server
> Комплект уже куплен — `/installtools` или `/installmcp`. Нет комплекта — страница покупки по ссылке. Установщик правил ключ MCP не выдаёт.

If the key or an external install is present but there are no tools in the session — briefly: MCP is not connected, `/installmcp` or a client restart; do not repeat the purchase link. Do not go further in Part B.

Since 27.09.2026 every server is published in one channel under the variant tags `latest` / `light` / `arm64` (canon — `/installmcp` → `## Image variant`). Compare **the container's tag with the same tag on Docker Hub**; a newer `latest` says nothing about a `light` container. A container on a `*-beta` tag (also the joined form `latestbeta`) is **outdated**: those tags are no longer published, so there is nothing to compare — report it with the fix `/updatemcp`.

1. Collect what actually runs — the tag is taken from the container, not from `config.env` (the user may have changed it by hand):

```powershell
$containers = docker ps --format '{{.Names}}' | ForEach-Object {
    $image = docker inspect $_ --format '{{.Config.Image}}'
    if ($image -notmatch '^([^:]+):(.+)$') { return }
    $repo, $tag = $Matches[1], $Matches[2]
    [pscustomobject]@{
        Container = $_
        Repo      = $repo
        Tag       = $tag
        Outdated  = $tag -match 'beta'
        Digest    = (docker image inspect "$repo`:$tag" --format '{{index .RepoDigests 0}}' 2>$null)
    }
} | Where-Object { $_ -and $_.Repo -like 'comol/*' }
$containers | Format-Table -AutoSize
```

2. For each image ask Docker Hub for the published digest **of the same tag** (public repositories, no authorization needed):

```powershell
foreach ($c in $containers) {
    $url = "https://hub.docker.com/v2/repositories/$($c.Repo)/tags/$($c.Tag)"
    try {
        $remote = Invoke-RestMethod -Uri $url
    } catch {
        "$($c.Repo):$($c.Tag) - tag not found in Docker Hub (404) or registry unreachable"
        continue
    }
    $local = ($c.Digest -split '@')[-1]
    [pscustomobject]@{
        Server    = $c.Container
        Tag       = $c.Tag
        Outdated  = $c.Outdated
        Published = $remote.last_updated
        Update    = if ($local -and $local -eq $remote.digest) { 'no' } else { 'YES' }
    }
}
```

3. Verdict per server:
   - the local image digest matches the published one → **up to date**;
   - they differ → **update available**; show `last_updated` of the published tag;
   - there is no local digest (the image was built locally, not pulled from the registry) → nothing to compare; note it separately, do not present it as "update available";
   - the tag was not found (404) → say that this tag is not published; a `*-beta` tag is outdated (fix: `/updatemcp`), and SyntaxCheck has no `light` (it is published as `latest` / `arm64`).

4. Additionally compare the declared variant with the actual one: `IMAGE_VARIANT` / `IMAGE_TAG` in the distribution's `config.env` (default `C:\Work\MCP_Distr\config.env`; contract — `/installmcp` → `## Image variant`) against the `Tag` column. A mismatch is not an error, but it must be mentioned. An image created before 27.09.2026 needs the new per-server `LICENSE_KEY_<SERVER>` keys; `/updatemcp` brings both.

## Report

One table for the rules, one for the servers (when MCP is connected; otherwise, instead of the servers table — the verdict «MCP не подключены» and the reminder from Part B), then a short conclusion:

- everything is up to date → one line «обновлений нет», without suggesting to run anything;
- there are updates → list exactly what is outdated and suggest exactly what is needed: `/updatemcp` (keeps the variant, migrates `*-beta` tags), `/updaterules`;
- some checks did not complete (no network, no Docker, GitHub answered `403`) → list exactly what was not checked. Unchecked is not presented as checked.

The command installs nothing itself and does not change image tags. Even when an update is clearly available, running `/updatemcp` or `/updaterules` is a separate decision of the user.

After any completed check (including a partial run and the verdict «MCP не подключены») write the field `lastUpdatesCheckAt` into `.ai-rules.json` with the current UTC in the same format as `updatedAt` (`yyyy-MM-ddTHH:mm:ssZ`). Do not touch the other fields of the manifest. If the network failed before any verdict — do not update the field, so that the next session retries.
