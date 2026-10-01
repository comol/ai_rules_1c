#Requires -Version 5.1
<#
.SYNOPSIS
    Targeted tests for the marketplace wrapper around install.ps1.

.DESCRIPTION
    Pure-ASCII. Calls invoke-install.ps1 -DryRun only - it must not write
    into the repo or clone GitHub.
#>
[CmdletBinding()]
param(
    [string]$Filter = '*'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Script = Join-Path $RepoRoot 'plugins\1c-rules\scripts\invoke-install.ps1'
$PowerShellCommand = if (Get-Command powershell.exe -ErrorAction SilentlyContinue) { 'powershell.exe' } else { 'pwsh' }

if (-not (Test-Path -LiteralPath $Script)) { throw "Missing $Script" }

$script:Failures = @()
$script:Passed = 0

function Read-Plan {
    param(
        [string]$Command,
        [string]$Tool = 'cursor',
        [string]$ProjectRoot,
        [string]$Source
    )
    $argList = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $Script,
        '-Action', $Command,
        '-Tool', $Tool,
        '-ProjectRoot', $ProjectRoot,
        '-DryRun'
    )
    if ($Source) { $argList += @('-Source', $Source) }
    $raw = & $PowerShellCommand @argList
    if ($LASTEXITCODE -ne 0) { throw "DryRun failed: $raw" }
    $json = ($raw | Out-String).Trim()
    if (-not $json) { throw "DryRun produced no JSON" }
    return ($json | ConvertFrom-Json)
}

function Assert-Eq($Actual, $Expected, $Message) {
    if ($Actual -ne $Expected) {
        throw "$Message (expected='$Expected' actual='$Actual')"
    }
}

function Run-Case([string]$Name, [scriptblock]$Body) {
    if ($Name -notlike $Filter) { return }
    try {
        & $Body
        $script:Passed++
        Write-Host "OK  $Name"
    }
    catch {
        $script:Failures += "$Name : $($_.Exception.Message)"
        Write-Host "FAIL  $Name : $($_.Exception.Message)" -ForegroundColor Red
    }
}

$tempRoot = if ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }
$work = Join-Path $tempRoot ("1c-rules-mp-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
try {
    Run-Case 'source walks up to this checkout' {
        $oneC = Join-Path $work 'cf-project'
        New-Item -ItemType Directory -Path $oneC | Out-Null
        Set-Content -LiteralPath (Join-Path $oneC 'Configuration.xml') -Value '<MetaDataObject/>' -Encoding ASCII
        $plan = Read-Plan -Command ensure -Tool cursor -ProjectRoot $oneC
        Assert-Eq $plan.action 'init' 'expected first-install init'
        Assert-Eq $plan.reason 'first-install' 'reason'
        $sourceNorm = [System.IO.Path]::GetFullPath($plan.source).TrimEnd('\', '/').ToLowerInvariant()
        $repoNorm = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\', '/').ToLowerInvariant()
        Assert-Eq $sourceNorm $repoNorm 'source should be the repo root'
        if (-not $plan.installer) { throw 'installer path missing for a local checkout' }
    }

    Run-Case 'forbidden home is skipped' {
        $homeDir = [Environment]::GetFolderPath('UserProfile')
        $plan = Read-Plan -Command ensure -Tool cursor -ProjectRoot $homeDir
        Assert-Eq $plan.action 'skip' 'home must skip'
        Assert-Eq $plan.reason 'forbidden-root' 'home reason'
    }

    Run-Case 'random folder is not a 1C project' {
        $other = Join-Path $work 'go-app'
        New-Item -ItemType Directory -Path $other | Out-Null
        Set-Content -LiteralPath (Join-Path $other 'main.go') -Value 'package main' -Encoding ASCII
        $plan = Read-Plan -Command ensure -Tool cursor -ProjectRoot $other
        Assert-Eq $plan.action 'skip' 'non-1C must skip'
        Assert-Eq $plan.reason 'not-1c-project' 'non-1C reason'
    }

    Run-Case 'existing tool is a no-op' {
        $proj = Join-Path $work 'installed'
        New-Item -ItemType Directory -Path $proj | Out-Null
        Set-Content -LiteralPath (Join-Path $proj 'Configuration.xml') -Value '<MetaDataObject/>' -Encoding ASCII
        Set-Content -LiteralPath (Join-Path $proj '.ai-rules.json') -Value '{"tools":["cursor"]}' -Encoding ASCII
        $plan = Read-Plan -Command ensure -Tool cursor -ProjectRoot $proj
        Assert-Eq $plan.action 'skip' 'already installed'
        Assert-Eq $plan.reason 'already-installed' 'already installed reason'
    }

    Run-Case 'missing host tool becomes add' {
        $proj = Join-Path $work 'add-tool'
        New-Item -ItemType Directory -Path $proj | Out-Null
        Set-Content -LiteralPath (Join-Path $proj 'Configuration.xml') -Value '<MetaDataObject/>' -Encoding ASCII
        Set-Content -LiteralPath (Join-Path $proj '.ai-rules.json') -Value '{"tools":["claude-code"]}' -Encoding ASCII
        $plan = Read-Plan -Command ensure -Tool cursor -ProjectRoot $proj
        Assert-Eq $plan.action 'add' 'should add cursor'
        Assert-Eq $plan.reason 'missing-tool' 'add reason'
        Assert-Eq $plan.tool 'cursor' 'tool id'
    }

    Run-Case 'ensure never chooses update' {
        $proj = Join-Path $work 'no-update'
        New-Item -ItemType Directory -Path $proj | Out-Null
        Set-Content -LiteralPath (Join-Path $proj 'Configuration.xml') -Value '<MetaDataObject/>' -Encoding ASCII
        Set-Content -LiteralPath (Join-Path $proj '.ai-rules.json') -Value '{"tools":["cursor"],"version":"old"}' -Encoding ASCII
        $plan = Read-Plan -Command ensure -Tool cursor -ProjectRoot $proj
        Assert-Eq $plan.action 'skip' 'ensure must not update'
    }

    Run-Case 'catalogs and plugin manifests parse' {
        $files = @(
            '.cursor-plugin\marketplace.json',
            '.claude-plugin\marketplace.json',
            '.agents\plugins\marketplace.json',
            'plugins\1c-rules\.cursor-plugin\plugin.json',
            'plugins\1c-rules\.claude-plugin\plugin.json',
            'plugins\1c-rules\.codex-plugin\plugin.json',
            'plugins\1c-rules\package.json'
        )
        foreach ($rel in $files) {
            $path = Join-Path $RepoRoot $rel
            if (-not (Test-Path -LiteralPath $path)) { throw "missing $rel" }
            $null = (Get-Content -LiteralPath $path -Raw) | ConvertFrom-Json
        }
        $cursorMarket = (Get-Content -LiteralPath (Join-Path $RepoRoot '.cursor-plugin\marketplace.json') -Raw) | ConvertFrom-Json
        $pluginDir = Join-Path $RepoRoot ($cursorMarket.plugins[0].source -replace '/', '\')
        if (-not (Test-Path -LiteralPath (Join-Path $pluginDir '.cursor-plugin\plugin.json'))) {
            throw 'Cursor marketplace source does not contain plugin.json'
        }
        $codexMarket = (Get-Content -LiteralPath (Join-Path $RepoRoot '.agents\plugins\marketplace.json') -Raw) | ConvertFrom-Json
        $codexPath = [string]$codexMarket.plugins[0].source.path
        if (-not $codexPath) { throw 'Codex marketplace entry has no source.path' }
        $codexPlugin = Join-Path $RepoRoot ($codexPath.TrimStart('.', '/', '\') -replace '/', '\')
        if (-not (Test-Path -LiteralPath (Join-Path $codexPlugin '.codex-plugin\plugin.json'))) {
            throw 'Codex marketplace source does not contain .codex-plugin/plugin.json'
        }
        $codexManifest = (Get-Content -LiteralPath (Join-Path $codexPlugin '.codex-plugin\plugin.json') -Raw) | ConvertFrom-Json
        if ($codexManifest.PSObject.Properties.Name -notcontains 'hooks' -or @($codexManifest.hooks).Count -ne 0) {
            throw 'Codex must explicitly disable the Claude Code SessionStart hook'
        }
    }

    Run-Case 'plugin does not ship content rules' {
        $rules = Join-Path $RepoRoot 'plugins\1c-rules\rules'
        if (Test-Path -LiteralPath $rules) { throw 'plugin must not contain a rules/ dump' }
        $content = Join-Path $RepoRoot 'plugins\1c-rules\content'
        if (Test-Path -LiteralPath $content) { throw 'plugin must not vendor content/' }
    }
}
finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host ("Passed {0}, failed {1}" -f $script:Passed, $script:Failures.Count)
if ($script:Failures.Count -gt 0) {
    foreach ($item in $script:Failures) { Write-Host $item -ForegroundColor Red }
    exit 1
}
exit 0
