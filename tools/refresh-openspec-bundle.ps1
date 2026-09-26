#Requires -Version 5.1
<#
.SYNOPSIS
    Refreshes content/openspec-bundle/ from a locally installed OpenSpec CLI.

.DESCRIPTION
    Maintainer-only utility. Runs `openspec init` in a temporary directory
    against the five tools supported by 1c-rules, then mirrors the resulting
    files into content/openspec-bundle/<tool>/ and refreshes
    content/openspec-bundle/version.txt with the CLI's reported version.

    Bumps the static snapshot that the installer ships, so end-users continue
    to get OpenSpec slash commands and SKILLs without needing npm at install
    time. Re-run after upgrading the OpenSpec CLI.

    Requirements (maintainer machine only):
      - Node.js + npm
      - The official OpenSpec CLI installed globally:
          npm install -g @fission-ai/openspec@latest

.PARAMETER RepoRoot
    Path to the 1c-rules source repository. Defaults to the parent directory
    of the script (i.e. running from the repo works without arguments).

.PARAMETER DryRun
    Show planned actions and the diff summary; do not modify the repository.

.EXAMPLE
    .\tools\refresh-openspec-bundle.ps1

.EXAMPLE
    .\tools\refresh-openspec-bundle.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [string]$RepoRoot,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$script:Tools = @('cursor', 'claude-code', 'codex', 'opencode', 'kilocode')
$script:OpenSpecToolsArg = 'cursor,claude,codex,opencode,kilocode'
$script:DotMap = @{
    'cursor'      = '.cursor'
    'claude-code' = '.claude'
    # OpenSpec >= 1.13 writes Codex skills to the vendor-neutral .agents/skills/;
    # the installer maps them onto the Codex adapter's .codex/skills/.
    'codex'       = '.agents'
    'opencode'    = '.opencode'
    'kilocode'    = '.kilocode'
}

function Resolve-RepoRoot {
    param([string]$Requested)
    if ($Requested) {
        if (-not (Test-Path $Requested)) { throw "RepoRoot does not exist: $Requested" }
        return (Resolve-Path $Requested).Path
    }
    $scriptDir = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptDir '..')).Path
}

function Test-OpenSpecAvailable {
    $cmd = Get-Command openspec -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "OpenSpec CLI not found on PATH. Install it first: npm install -g @fission-ai/openspec@latest"
    }
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $version = (& openspec --version 2>&1 | Out-String).Trim()
    }
    finally {
        $ErrorActionPreference = $prevPref
    }
    if (-not $version) { throw "openspec --version returned empty output" }
    return $version
}

function Invoke-OpenSpecInit {
    param([string]$WorkDir)
    Push-Location $WorkDir
    # OpenSpec writes progress to stderr; with $ErrorActionPreference='Stop'
    # PowerShell would treat that as a fatal native-command error. Relax the
    # preference for the duration of this call and rely on $LASTEXITCODE.
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & openspec init --tools $script:OpenSpecToolsArg 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            Write-Host $output
            throw "openspec init failed (exit $LASTEXITCODE)"
        }
        return $output
    }
    finally {
        $ErrorActionPreference = $prevPref
        Pop-Location
    }
}

# CLI bookkeeping files that must not ship (e.g. .agents/skills/.openspec-target).
$script:SkipNames = @('.openspec-target')

function Get-RelativeFiles {
    param([string]$BaseDir)
    if (-not (Test-Path $BaseDir)) { return @() }
    $base = (Resolve-Path $BaseDir).Path.TrimEnd('\', '/')
    return @(Get-ChildItem -Recurse -File -Force $BaseDir -ErrorAction SilentlyContinue |
        Where-Object { $script:SkipNames -notcontains $_.Name } | ForEach-Object {
        $_.FullName.Substring($base.Length + 1).Replace('\', '/')
    } | Sort-Object)
}

function Sync-ToolBundle {
    param(
        [string]$Tool,
        [string]$ProbeRoot,
        [string]$BundleRoot,
        [bool]$DryRun
    )
    $dot = $script:DotMap[$Tool]
    $sourceDir = Join-Path $ProbeRoot $dot
    # The whole per-tool folder is compared and replaced, so a dot directory the
    # CLI stopped writing (e.g. codex/.codex after the move to .agents) is removed.
    $toolDir = Join-Path $BundleRoot $Tool

    if (-not (Test-Path $sourceDir)) {
        Write-Warning "  [$Tool] no $dot in probe output - skipped"
        return [pscustomobject]@{ Tool = $Tool; Added = 0; Updated = 0; Removed = 0 }
    }

    $sourceFiles = @(Get-RelativeFiles $sourceDir | ForEach-Object { "$dot/$_" })
    $targetFiles = Get-RelativeFiles $toolDir
    $sourceSet = [System.Collections.Generic.HashSet[string]]::new([string[]]$sourceFiles)
    $targetSet = [System.Collections.Generic.HashSet[string]]::new([string[]]$targetFiles)

    $added = @($sourceFiles | Where-Object { -not $targetSet.Contains($_) })
    $removed = @($targetFiles | Where-Object { -not $sourceSet.Contains($_) })
    $shared = @($sourceFiles | Where-Object { $targetSet.Contains($_) })
    $updated = @()
    foreach ($rel in $shared) {
        $a = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $ProbeRoot $rel)).Hash
        $b = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $toolDir $rel)).Hash
        if ($a -ne $b) { $updated += $rel }
    }

    if (-not $DryRun) {
        if (Test-Path $toolDir) { Remove-Item -Recurse -Force $toolDir }
        foreach ($rel in $sourceFiles) {
            $dest = Join-Path $toolDir $rel
            $parent = Split-Path -Parent $dest
            if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
            Copy-Item -Force -Path (Join-Path $ProbeRoot $rel) -Destination $dest
        }
    }

    return [pscustomobject]@{
        Tool    = $Tool
        Added   = $added.Count
        Updated = $updated.Count
        Removed = $removed.Count
    }
}

$repo = Resolve-RepoRoot -Requested $RepoRoot
$bundleRoot = Join-Path $repo 'content\openspec-bundle'
if (-not (Test-Path $bundleRoot)) { New-Item -ItemType Directory -Path $bundleRoot | Out-Null }

Write-Host "Repo:    $repo"
Write-Host "Bundle:  $bundleRoot"
Write-Host "DryRun:  $DryRun"

$cliVersion = Test-OpenSpecAvailable
Write-Host "OpenSpec CLI version: $cliVersion"

$probe = Join-Path $env:TEMP ("opsx-refresh-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $probe | Out-Null
try {
    Write-Host ''
    Write-Host "Running openspec init in $probe ..."
    $initOut = Invoke-OpenSpecInit -WorkDir $probe
    Write-Verbose $initOut

    Write-Host ''
    Write-Host 'Per-tool diff:'
    $stats = @()
    foreach ($t in $script:Tools) {
        $stats += Sync-ToolBundle -Tool $t -ProbeRoot $probe -BundleRoot $bundleRoot -DryRun:$DryRun
    }
    foreach ($s in $stats) {
        Write-Host ("  {0,-12} added={1,-3} updated={2,-3} removed={3,-3}" -f $s.Tool, $s.Added, $s.Updated, $s.Removed)
    }

    $verFile = Join-Path $bundleRoot 'version.txt'
    $existingVersion = ''
    if (Test-Path $verFile) { $existingVersion = ((Get-Content -Raw -Path $verFile) -replace '\s+$', '').Trim() }
    if (-not $DryRun) {
        Set-Content -Path $verFile -Value $cliVersion -NoNewline -Encoding UTF8
    }

    Write-Host ''
    if ($existingVersion -and $existingVersion -ne $cliVersion) {
        Write-Host "version.txt: $existingVersion -> $cliVersion"
    }
    elseif (-not $existingVersion) {
        Write-Host "version.txt: <new> -> $cliVersion"
    }
    else {
        Write-Host "version.txt: $cliVersion (unchanged)"
    }

    if ($DryRun) {
        Write-Host ''
        Write-Host 'Dry run - no files modified. Re-run without -DryRun to apply.'
    }
    else {
        Write-Host ''
        Write-Host 'Bundle refresh complete. Review `git status` and commit.'
    }
}
finally {
    if (Test-Path $probe) { Remove-Item -Recurse -Force $probe }
}
