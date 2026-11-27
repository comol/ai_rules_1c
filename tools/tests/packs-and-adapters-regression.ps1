#Requires -Version 5.1
<#
.SYNOPSIS
    Offline installer regressions for extended IDE adapters (copilot, windsurf,
    roocode, gemini, kiro, yandex) and optional 1C domain packs (`-Packs`, `packs`).
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Installer = Join-Path $RepoRoot 'install.ps1'
$Work = Join-Path ([IO.Path]::GetTempPath()) ('1c-packs-adapters-' + [guid]::NewGuid().ToString('N'))
$SourceRoot = Join-Path $Work 'source'
$Utf8 = New-Object Text.UTF8Encoding $false
$script:Passed = 0

function Write-Fixture([string]$Path, [string]$Text) {
    [void][IO.Directory]::CreateDirectory((Split-Path $Path -Parent))
    [IO.File]::WriteAllText($Path, $Text, $Utf8)
}

function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Invoke-Installer([string]$Project, [string[]]$Arguments) {
    $log = Join-Path $Work ('run-' + [guid]::NewGuid().ToString('N') + '.log')
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Installer @Arguments `
        -ProjectRoot $Project -Source $SourceRoot -NonInteractive -McpMode managed *> $log
    if ($LASTEXITCODE -ne 0) {
        throw "Installer exit $LASTEXITCODE for $($Arguments -join ' '):`n$(Get-Content -LiteralPath $log -Raw)"
    }
    return (Get-Content -LiteralPath $log -Raw)
}

function Pass([string]$Name) {
    $script:Passed++
    Write-Host "OK  $Name"
}

try {
    [void][IO.Directory]::CreateDirectory($SourceRoot)
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'adapters') -Destination $SourceRoot -Recurse
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'content/packs') -Destination (Join-Path $SourceRoot 'content/packs') -Recurse
    Write-Fixture (Join-Path $SourceRoot 'AGENTS.md') '# Read content/rules/probe.md and content/skills/probe/SKILL.md on demand.'
    foreach ($file in @('USER-RULES.md', 'memory.md', 'LLM-RULES.md')) {
        Write-Fixture (Join-Path $SourceRoot $file) "# $file"
    }
    Write-Fixture (Join-Path $SourceRoot 'content/rules/probe.md') "---`ndescription: Fixture`nalwaysApply: false`ncategory: workflow`n---`n# Probe"
    Write-Fixture (Join-Path $SourceRoot 'content/commands/probe.md') "---`ndescription: Fixture command`nargumentHint: input`n---`n# Probe"
    Write-Fixture (Join-Path $SourceRoot 'content/skills/probe/SKILL.md') "---`nname: probe`ndescription: Fixture skill`n---`n# Probe"
    foreach ($name in @('explorer', 'cold-reader')) {
        $path = Join-Path $SourceRoot "content/agents/$name.md"
        [void][IO.Directory]::CreateDirectory((Split-Path $path -Parent))
        Copy-Item -LiteralPath (Join-Path $RepoRoot "content/agents/$name.md") -Destination $path
    }
    $catalog = '{"servers":[{"id":"fixture-http","url":"http://127.0.0.1:1/mcp","description":"fixture"}]}'
    Write-Fixture (Join-Path $SourceRoot 'content/mcp-servers.json') $catalog

    # 1. All 6 new IDE adapters + init with -Packs zup-hr
    $proj = Join-Path $Work 'multi'
    [void][IO.Directory]::CreateDirectory($proj)
    $null = Invoke-Installer $proj @('init', '-Tools', 'copilot,windsurf,roocode,gemini,kiro,yandex', '-Packs', 'zup-hr')

    foreach ($rel in @(
        '.github/copilot-instructions.md',
        '.github/rules-1c/probe.md',
        '.github/rules-1c/zup-hr-patterns.md',
        '.github/agents/cold-reader.agent.md',
        '.github/prompts/probe.prompt.md',
        '.github/skills/probe/SKILL.md',
        '.vscode/mcp.json',
        '.windsurf/rules-1c/probe.md',
        '.windsurf/workflows/probe.md',
        '.windsurf/skills/probe/SKILL.md',
        '.roo/rules-1c/probe.md',
        '.roo/commands/probe.md',
        '.roo/skills/probe/SKILL.md',
        '.roo/mcp.json',
        'GEMINI.md',
        '.gemini/rules-1c/probe.md',
        '.gemini/skills/probe/SKILL.md',
        '.gemini/settings.json',
        '.kiro/rules-1c/probe.md',
        '.kiro/skills/probe/SKILL.md',
        '.kiro/settings/mcp.json',
        '.codeassistant/rules-1c/probe.md',
        '.codeassistant/skills/probe/SKILL.md'
    )) {
        Assert-True (Test-Path -LiteralPath (Join-Path $proj $rel)) "Missing expected file: $rel"
    }

    # Verify VS Code / Copilot MCP schema uses top-level `servers`
    $vscodeMcp = Get-Content -LiteralPath (Join-Path $proj '.vscode/mcp.json') -Raw | ConvertFrom-Json
    Assert-True ($null -ne $vscodeMcp.servers.'fixture-http') 'Copilot .vscode/mcp.json missing servers.fixture-http'
    Assert-True ($vscodeMcp.servers.'fixture-http'.type -eq 'http') 'Copilot MCP entry type must be http'

    # Verify Gemini MCP schema uses `httpUrl`
    $geminiMcp = Get-Content -LiteralPath (Join-Path $proj '.gemini/settings.json') -Raw | ConvertFrom-Json
    Assert-True ($geminiMcp.mcpServers.'fixture-http'.httpUrl -eq 'http://127.0.0.1:1/mcp') 'Gemini MCP entry must use httpUrl'
    Pass '6 extended IDE adapters (copilot, windsurf, roocode, gemini, kiro, yandex) + init -Packs'

    # 2. Standalone packs list / add / update / remove
    $listOut = Invoke-Installer $proj @('packs', 'list')
    Assert-True ($listOut -match 'zup-hr\s+\[installed\s*\]') 'packs list did not show zup-hr as installed'
    Assert-True ($listOut -match 'meeting-to-tasks\s+\[not installed\]') 'packs list did not show meeting-to-tasks as not installed'

    $null = Invoke-Installer $proj @('packs', 'add', '-Packs', 'meeting-to-tasks')
    Assert-True (Test-Path -LiteralPath (Join-Path $proj '.github/skills/meeting-to-tasks/SKILL.md')) 'packs add did not install meeting-to-tasks skill'
    Assert-True (Test-Path -LiteralPath (Join-Path $proj '.codeassistant/skills/meeting-to-tasks/SKILL.md')) 'packs add did not install meeting-to-tasks for yandex'

    # Update preserves installed packs
    $null = Invoke-Installer $proj @('update')
    Assert-True (Test-Path -LiteralPath (Join-Path $proj '.github/rules-1c/zup-hr-patterns.md')) 'update dropped zup-hr pack'
    Assert-True (Test-Path -LiteralPath (Join-Path $proj '.github/skills/meeting-to-tasks/SKILL.md')) 'update dropped meeting-to-tasks pack'

    # Remove deletes pack files and updates manifest
    $null = Invoke-Installer $proj @('packs', 'remove', '-Packs', 'zup-hr')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $proj '.github/rules-1c/zup-hr-patterns.md'))) 'packs remove left zup-hr rule in copilot'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $proj '.roo/rules-1c/zup-hr-patterns.md'))) 'packs remove left zup-hr rule in roocode'
    $manifest = Get-Content -LiteralPath (Join-Path $proj '.ai-rules.json') -Raw | ConvertFrom-Json
    Assert-True ($manifest.packs -notcontains 'zup-hr') 'packs remove left zup-hr in manifest.packs'
    Assert-True ($manifest.packs -contains 'meeting-to-tasks') 'packs remove dropped unrelated pack'
    Pass 'packs list, add, update preservation and remove'

    # 3. Scoped tool removal cleans up new adapter directories
    $null = Invoke-Installer $proj @('remove', 'gemini')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $proj 'GEMINI.md'))) 'remove gemini left GEMINI.md'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $proj '.gemini/rules-1c/probe.md'))) 'remove gemini left rule'
    Pass 'scoped tool remove for new adapter'

    Write-Host "Passed: $script:Passed"
}
finally {
    if (Test-Path -LiteralPath $Work) {
        Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue
    }
}
