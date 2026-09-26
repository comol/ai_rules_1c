#Requires -Version 5.1
<#
.SYNOPSIS
    Offline installer regressions for ZCode, MiMo Code, Kimi, Cline and Command Code.
.DESCRIPTION
    Runs the real installer and adapters against a small source fixture. Checks
    discovery, permissions, MCP shape, update ownership and scoped removal.
    No client executable, network service or global configuration is touched.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Installer = Join-Path $RepoRoot 'install.ps1'
$Work = Join-Path ([IO.Path]::GetTempPath()) ('1c-agent-adapters-' + [guid]::NewGuid().ToString('N'))
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

function Read-Json([string]$Path) {
    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
}

function Invoke-Installer([string]$Project, [string[]]$Arguments, [switch]$ExpectFailure) {
    $log = Join-Path $Work ('run-' + [guid]::NewGuid().ToString('N') + '.log')
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Installer @Arguments `
        -ProjectRoot $Project -Source $SourceRoot -NonInteractive -McpMode managed *> $log
    $code = $LASTEXITCODE
    if (($code -ne 0) -ne [bool]$ExpectFailure) {
        throw "Installer exit $code for $($Arguments -join ' '):`n$(Get-Content -LiteralPath $log -Raw)"
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
    Write-Fixture (Join-Path $SourceRoot 'AGENTS.md') '# Read content/rules/probe.md and content/skills/probe/SKILL.md on demand.'
    foreach ($file in @('USER-RULES.md', 'memory.md', 'LLM-RULES.md')) {
        Write-Fixture (Join-Path $SourceRoot $file) "# $file"
    }
    Write-Fixture (Join-Path $SourceRoot 'content/rules/probe.md') "---`ndescription: Fixture`nalwaysApply: false`ncategory: workflow`n---`n# Probe"
    Write-Fixture (Join-Path $SourceRoot 'content/commands/probe.md') "---`ndescription: Fixture command`nargumentHint: input`n---`n# Probe"
    Write-Fixture (Join-Path $SourceRoot 'content/skills/probe/SKILL.md') "---`nname: probe`ndescription: Fixture skill`n---`n# Probe"
    foreach ($name in @('explorer', 'developer')) {
        $path = Join-Path $SourceRoot "content/agents/$name.md"
        [void][IO.Directory]::CreateDirectory((Split-Path $path -Parent))
        Copy-Item -LiteralPath (Join-Path $RepoRoot "content/agents/$name.md") -Destination $path
    }
    $catalog = '{"servers":[{"id":"fixture-http","url":"http://127.0.0.1:1/mcp","headers":{"X-Test":"fixture"},"connectionId":"omit-in-strict-clients","description":"fixture"},{"id":"fixture-stdio","command":"node","args":["server.js"],"env":{"FIXTURE":"yes"}},{"id":"user-collision","url":"http://127.0.0.1:2/mcp"}]}'
    Write-Fixture (Join-Path $SourceRoot 'content/mcp-servers.json') $catalog

    $clients = @(
        @{ Id = 'zcode'; Dir = '.zcode'; Mcp = '.zcode/config.json' },
        @{ Id = 'mimocode'; Dir = '.mimocode'; Mcp = 'mimocode.json' },
        @{ Id = 'kimi'; Dir = '.kimi-code'; Mcp = '.kimi-code/mcp.json' },
        @{ Id = 'cline'; Dir = '.cline'; Mcp = '' },
        @{ Id = 'command-code'; Dir = '.commandcode'; Mcp = '.mcp.json' }
    )
    foreach ($client in $clients) {
        $project = Join-Path $Work $client.Id
        [void][IO.Directory]::CreateDirectory((Join-Path $project $client.Dir))
        Write-Fixture (Join-Path $project '.dev.env') "SUBAGENT_MODEL_LIGHT=fixture-light`nSUBAGENT_MODEL_CODING=fixture-coding`n"
        $protectServers = $client.Id -in @('zcode', 'mimocode')
        if ($protectServers) {
            $servers = '{"user-only":{"url":"http://localhost:99/mcp"},"user-collision":{"url":"http://localhost:98/mcp"}}'
            $mcp = if ($client.Id -eq 'zcode') { '{"servers":' + $servers + '}' } else { $servers }
            Write-Fixture (Join-Path $project $client.Mcp) ('{"model":"user-model","mcp":' + $mcp + '}')
        }
        $null = Invoke-Installer $project @('init')
        $manifest = Read-Json (Join-Path $project '.ai-rules.json')
        Assert-True (@($manifest.tools).Count -eq 1 -and $manifest.tools[0] -eq $client.Id) "$($client.Id): detection"
        foreach ($rel in @('rules-1c/probe.md', 'agents/explorer.md', 'agents/developer.md', 'skills/probe/SKILL.md')) {
            Assert-True (Test-Path -LiteralPath (Join-Path $project ($client.Dir + '/' + $rel))) "$($client.Id): missing $rel"
        }
        $entry = Get-Content -LiteralPath (Join-Path $project 'AGENTS.md') -Raw
        Assert-True ($entry.Contains($client.Dir + '/rules-1c/probe.md')) "$($client.Id): canonical links"
        $reader = Get-Content -LiteralPath (Join-Path $project ($client.Dir + '/agents/explorer.md')) -Raw
        $writer = Get-Content -LiteralPath (Join-Path $project ($client.Dir + '/agents/developer.md')) -Raw
        if ($client.Id -eq 'mimocode') {
            Assert-True ($reader -match 'edit: deny' -and $reader -match 'bash: deny' -and $reader -match 'mode: subagent') 'MiMo reader permissions'
            Assert-True ($writer -match 'edit: allow' -and $writer -match 'bash: allow') 'MiMo writer permissions'
        }
        elseif ($client.Id -ne 'cline') {
            Assert-True ($reader -match '(?m)^disallowedTools:') "$($client.Id): no reader denylist"
            Assert-True ($writer -notmatch '(?m)^disallowedTools:') "$($client.Id): writer unexpectedly restricted"
        }
        if ($client.Id -eq 'command-code') {
            Assert-True ($reader -match '(?m)^tools: "\*"' -and $writer -match '(?m)^tools: "\*"') 'Command Code must explicitly inherit tools'
            Assert-True ($reader -match 'write_file' -and $reader -match 'edit_file' -and $reader -match 'shell_command') 'Command Code native denylist'
        }
        if ($client.Id -eq 'kimi') {
            Assert-True ($reader -notmatch '(?m)^(model|isSubagent):') 'Kimi ignored fields must not imply per-agent model support'
        }
        else {
            Assert-True ($reader -match '(?m)^model: fixture-light' -and $writer -match '(?m)^model: fixture-coding') "$($client.Id): configured model tiers lost"
        }
        $hasCommands = $client.Id -in @('zcode', 'mimocode', 'command-code')
        Assert-True ((Test-Path -LiteralPath (Join-Path $project ($client.Dir + '/commands/probe.md'))) -eq $hasCommands) "$($client.Id): commands placement"
        if ($client.Mcp) {
            $config = Read-Json (Join-Path $project $client.Mcp)
            $servers = switch ($client.Id) {
                'zcode' { $config.mcp.servers }
                'mimocode' { $config.mcp }
                default { $config.mcpServers }
            }
            Assert-True ($servers.'fixture-http'.url -eq 'http://127.0.0.1:1/mcp') "$($client.Id): HTTP URL"
            Assert-True ($servers.'fixture-http'.headers.'X-Test' -eq 'fixture') "$($client.Id): headers"
            if ($client.Id -eq 'zcode') {
                Assert-True ($servers.'fixture-http'.type -eq 'http' -and $servers.'fixture-stdio'.type -eq 'stdio') 'ZCode transports'
                Assert-True (@($servers.'fixture-http'.PSObject.Properties.Name).Count -eq 3) 'ZCode strict remote schema'
            }
            if ($client.Id -eq 'mimocode') {
                Assert-True ($servers.'fixture-http'.type -eq 'remote' -and $servers.'fixture-stdio'.type -eq 'local') 'MiMo transports'
                Assert-True ($servers.'fixture-stdio'.command[0] -eq 'node' -and $servers.'fixture-stdio'.environment.FIXTURE -eq 'yes') 'MiMo stdio shape'
            }
            if ($protectServers) {
                Assert-True ($config.model -eq 'user-model' -and $servers.'user-only' -and $servers.'user-collision'.url -eq 'http://localhost:98/mcp') "$($client.Id): user config preserved"
            }
        }
        else {
            Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.cline/mcp.json'))) 'Cline must not get project MCP'
            Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.mcp.json'))) 'Cline must not get root MCP'
            Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.clinerules'))) 'Cline must not eagerly load rules'
        }
        if ($protectServers) {
            Write-Fixture (Join-Path $SourceRoot 'content/mcp-servers.json') ($catalog.Replace('127.0.0.1:1/mcp', '127.0.0.1:3/mcp'))
        }
        $null = Invoke-Installer $project @('update')
        if ($protectServers) {
            $manifest = Read-Json (Join-Path $project '.ai-rules.json')
            $owned = @($manifest.files.($client.Mcp).managedServers)
            Assert-True ($owned.Count -eq 2 -and 'user-collision' -notin $owned) "$($client.Id): update lost MCP ownership"
            $config = Read-Json (Join-Path $project $client.Mcp)
            $servers = if ($client.Id -eq 'zcode') { $config.mcp.servers } else { $config.mcp }
            Assert-True ($servers.'fixture-http'.url -eq 'http://127.0.0.1:3/mcp') "$($client.Id): managed server did not update"
            $null = Invoke-Installer $project @('update', '-ForcePaths', $client.Mcp)
            $config = Read-Json (Join-Path $project $client.Mcp)
            $servers = if ($client.Id -eq 'zcode') { $config.mcp.servers } else { $config.mcp }
            Assert-True ($servers.'user-collision'.url -eq 'http://localhost:98/mcp') "$($client.Id): force update overwrote user-owned server"
            Write-Fixture (Join-Path $SourceRoot 'content/mcp-servers.json') $catalog
        }
        $log = Invoke-Installer $project @('doctor')
        Assert-True ($log -match 'All \d+ files match manifest') "$($client.Id): doctor integrity"
        Write-Fixture (Join-Path $project ($client.Dir + '/user-note.txt')) 'keep me'
        $null = Invoke-Installer $project @('remove', '-Tool', $client.Id)
        Assert-True (Test-Path -LiteralPath (Join-Path $project ($client.Dir + '/user-note.txt'))) "$($client.Id): foreign file removed"
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $project ($client.Dir + '/agents/explorer.md')))) "$($client.Id): agent not removed"
        if ($protectServers) {
            $config = Read-Json (Join-Path $project $client.Mcp)
            $servers = if ($client.Id -eq 'zcode') { $config.mcp.servers } else { $config.mcp }
            Assert-True ($config.model -eq 'user-model' -and $servers.'user-only' -and $servers.'user-collision' -and -not $servers.'fixture-http') "$($client.Id): removal damaged user config"
        }
        Pass "$($client.Id): init, update, doctor, remove"
    }

    $project = Join-Path $Work 'combined'
    [void][IO.Directory]::CreateDirectory($project)
    $null = Invoke-Installer $project @('init', '-Tools', 'zcode,mimocode,kimi,cline,command-code,claude-code')
    $manifest = Read-Json (Join-Path $project '.ai-rules.json')
    Assert-True (@($manifest.files.'.mcp.json'.owners).Count -eq 2) 'Shared MCP ownership'
    $null = Invoke-Installer $project @('remove', '-Tool', 'command-code')
    Assert-True (Test-Path -LiteralPath (Join-Path $project '.mcp.json')) 'Removing Command Code removed Claude MCP'
    $null = Invoke-Installer $project @('add', '-Tool', 'command-code')
    $null = Invoke-Installer $project @('remove')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.ai-rules.json'))) 'Full remove left manifest'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $project 'mimocode.json'))) 'Full remove left MiMo config'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.zcode/config.json'))) 'Full remove left ZCode config'
    Pass 'multi-client ownership, add and full removal'

    foreach ($client in $clients | Where-Object { $_.Id -in @('zcode', 'mimocode') }) {
        $project = Join-Path $Work ($client.Id + '-invalid')
        $path = Join-Path $project $client.Mcp
        Write-Fixture $path '{invalid json'
        $null = Invoke-Installer $project @('init', '-Tools', $client.Id) -ExpectFailure
        Assert-True ((Get-Content -LiteralPath $path -Raw) -eq '{invalid json') "$($client.Id): invalid config overwritten"
        Pass "$($client.Id): malformed user config preserved"
    }
    $project = Join-Path $Work 'mimo-jsonc'
    $jsonc = '// user override' + "`n" + '{"model":"user-model"}'
    Write-Fixture (Join-Path $project 'mimocode.jsonc') $jsonc
    $null = Invoke-Installer $project @('init')
    $manifest = Read-Json (Join-Path $project '.ai-rules.json')
    Assert-True ($manifest.tools[0] -eq 'mimocode') 'MiMo JSONC detection'
    Assert-True ((Get-Content -LiteralPath (Join-Path $project 'mimocode.jsonc') -Raw) -eq $jsonc) 'MiMo JSONC overwritten'
    Pass 'MiMo JSONC discovery and preservation'
    Write-Host "Passed: $script:Passed"
}
finally {
    # Resolve and verify the exact temporary root before recursive cleanup.
    if (Test-Path -LiteralPath $Work) {
        $resolved = (Resolve-Path -LiteralPath $Work).Path
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
            (Split-Path $resolved -Leaf) -notlike '1c-agent-adapters-*') {
            throw "Refusing cleanup outside test workspace: $resolved"
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
