#Requires -Version 5.1
<#
.SYNOPSIS
    Offline regressions for what `install.ps1 update` does to user files and settings.
.DESCRIPTION
    Runs the real installer against a small source fixture through a child
    PowerShell with -File, the way agents call it:
      - the .claude/rules/ and .ai-rules/rules/ migrations keep user edits in
        -AssumeYes and -NonInteractive runs;
      - -ForcePaths as a comma-separated string, with ./, backslashes and an
        absolute path; unmatched patterns are reported; the report tells
        overwritten files from kept ones;
      - USE_EDT follows the working tree;
      - the user's own MCP config survives init, update and remove;
      - an unchanged adapter entry file stays managed across updates.
    No network, client executable or infobase is touched.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Installer = Join-Path $RepoRoot 'install.ps1'
$PsExe = if ($PSVersionTable.PSEdition -eq 'Core' -and -not $IsWindows) { Join-Path $PSHOME 'pwsh' } else { 'powershell.exe' }
$Work = Join-Path ([IO.Path]::GetTempPath()) ('installer-update-' + [guid]::NewGuid().ToString('N'))
$SourceRoot = Join-Path $Work 'source'
$Utf8 = New-Object Text.UTF8Encoding $false
$script:Passed = 0

function Write-Fixture([string]$Path, [string]$Text) {
    [void][IO.Directory]::CreateDirectory((Split-Path $Path -Parent))
    [IO.File]::WriteAllText($Path, $Text, $Utf8)
}
function Assert-True($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Read-Text([string]$Path) { return [IO.File]::ReadAllText($Path) }
function Pass([string]$Name) { $script:Passed++; Write-Host "OK  $Name" }

function Invoke-Installer([string]$Project, [string[]]$Arguments, [string]$Mode = '-NonInteractive', [switch]$ExpectFailure) {
    $log = Join-Path $Work ('run-' + [guid]::NewGuid().ToString('N') + '.log')
    # The empty pipeline redirects stdin, so a run without -NonInteractive cannot block on a prompt.
    $null | & $PsExe -NoProfile -ExecutionPolicy Bypass -File $Installer @Arguments `
        -ProjectRoot $Project -Source $SourceRoot $Mode -McpMode managed *> $log
    $code = $LASTEXITCODE
    $text = Get-Content -LiteralPath $log -Raw
    if (($code -ne 0) -ne [bool]$ExpectFailure) { throw "Installer exit $code for $($Arguments -join ' '):`n$text" }
    return $text
}

function Read-Manifest([string]$Project) {
    return (Read-Text (Join-Path $Project '.ai-rules.json') | ConvertFrom-Json)
}

function Save-Manifest([string]$Project, $Manifest) {
    Write-Fixture (Join-Path $Project '.ai-rules.json') ($Manifest | ConvertTo-Json -Depth 20)
}

function New-Project([string]$Name, [string[]]$InitArgs = @('-Tools', 'claude-code')) {
    $project = Join-Path $Work $Name
    Write-Fixture (Join-Path $project '.dev.env') "EXPORT_PATH=`nINFOBASE_PATH=`nUSE_EDT=false`nCODE_OWNER=user`n"
    $null = Invoke-Installer $project (@('init') + $InitArgs)
    return $project
}

function Move-ToLegacyRule([string]$Project, [string]$Rule, [string]$Edit, [string]$LegacyDir = '.claude/rules') {
    # Rewrites the manifest and the tree the way an install before 1b6e2ed left them.
    $manifest = Read-Manifest $Project
    $newKey = ".claude/rules-1c/$Rule.md"
    $entry = $manifest.files.$newKey
    $manifest.files.PSObject.Properties.Remove($newKey)
    if ($Edit) { $entry | Add-Member -NotePropertyName userModified -NotePropertyValue $true -Force }
    $manifest.files | Add-Member -NotePropertyName "$LegacyDir/$Rule.md" -NotePropertyValue $entry -Force
    Save-Manifest $Project $manifest
    $newAbs = Join-Path $Project $newKey
    $legacyAbs = Join-Path $Project "$LegacyDir/$Rule.md"
    [void][IO.Directory]::CreateDirectory((Split-Path $legacyAbs -Parent))
    Move-Item -LiteralPath $newAbs -Destination $legacyAbs -Force
    if ($Edit) { Write-Fixture $legacyAbs $Edit }
}

try {
    [void][IO.Directory]::CreateDirectory($SourceRoot)
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'adapters') -Destination $SourceRoot -Recurse
    Write-Fixture (Join-Path $SourceRoot 'AGENTS.md') '# Rules: content/rules/probe.md'
    foreach ($file in @('USER-RULES.md', 'memory.md', 'LLM-RULES.md')) { Write-Fixture (Join-Path $SourceRoot $file) "# $file" }
    Write-Fixture (Join-Path $SourceRoot '.dev.env.example') "EXPORT_PATH=`nINFOBASE_PATH=`nUSE_EDT=false`nCODE_OWNER=user`nPLATFORM_VERSION=`nPREFIX=`n"
    Write-Fixture (Join-Path $SourceRoot 'content/mcp-servers.json') '{"servers":[]}'
    foreach ($rule in @('probe', 'clean', 'both', 'same')) {
        Write-Fixture (Join-Path $SourceRoot "content/rules/$rule.md") "---`ndescription: Fixture $rule`nalwaysApply: false`ncategory: workflow`n---`n# Shipped $rule"
    }
    foreach ($agent in @('probe', 'other')) {
        Write-Fixture (Join-Path $SourceRoot "content/agents/$agent.md") "---`nname: $agent`ndescription: Fixture`ntools: [Read, Grep, Glob, MCP]`nisSubagent: true`n---`n# Shipped agent $agent"
    }
    Write-Fixture (Join-Path $SourceRoot 'content/commands/probe.md') "---`ndescription: Fixture`n---`n# Command"
    Write-Fixture (Join-Path $SourceRoot 'content/skills/probe/SKILL.md') "---`nname: probe`ndescription: Fixture`n---`n# Skill"

    # ------------------------------------------------------------ legacy rules migration
    foreach ($mode in @('-AssumeYes', '-NonInteractive')) {
        $project = New-Project "migrate$mode"
        Move-ToLegacyRule $project 'probe' 'USER EDIT probe'
        Move-ToLegacyRule $project 'clean' ''
        Move-ToLegacyRule $project 'both' 'USER EDIT both (legacy)'
        Write-Fixture (Join-Path $project '.claude/rules-1c/both.md') 'USER EDIT both (new path)'
        Write-Fixture (Join-Path $project '.claude/rules/mine.md') 'personal rule'
        $shippedHash = (Read-Manifest $project).files.'.claude/rules/probe.md'.installedHash
        $log = Invoke-Installer $project @('update') $mode
        $manifest = Read-Manifest $project
        Assert-True ((Read-Text (Join-Path $project '.claude/rules-1c/probe.md')) -eq 'USER EDIT probe') "${mode}: the edit was not moved"
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.claude/rules/probe.md'))) "${mode}: the edited legacy copy stayed auto-loaded"
        $entry = $manifest.files.'.claude/rules-1c/probe.md'
        Assert-True ($entry.userModified -and $entry.installedHash -eq $shippedHash) "${mode}: the moved entry lost userModified or its hash"
        Assert-True ($log -match 'LEFT AT THEIR PREVIOUS VERSION' -and $log -match 'rules-1c/probe\.md') "${mode}: the kept file is not in the report"
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.claude/rules/clean.md'))) "${mode}: an unchanged legacy copy stayed"
        Assert-True ((Read-Text (Join-Path $project '.claude/rules-1c/clean.md')) -match '# Shipped clean') "${mode}: the shipped copy is missing"
        Assert-True (-not $manifest.files.'.claude/rules-1c/clean.md'.userModified) "${mode}: an unchanged rule is flagged"
        Assert-True ((Read-Text (Join-Path $project '.claude/rules-1c/both.md.legacy')) -eq 'USER EDIT both (legacy)') "${mode}: the legacy edit is lost"
        Assert-True ((Read-Text (Join-Path $project '.claude/rules/mine.md')) -eq 'personal rule') "${mode}: an untracked rule was touched"
        Assert-True (@($manifest.files.PSObject.Properties.Name | Where-Object { $_ -like '.claude/rules/*' }).Count -eq 0) "${mode}: legacy manifest keys stayed"
        # A second run changes nothing.
        $null = Invoke-Installer $project @('update') $mode
        Assert-True ((Read-Text (Join-Path $project '.claude/rules-1c/probe.md')) -eq 'USER EDIT probe') "${mode}: the second update lost the edit"
        Assert-True ((Read-Text (Join-Path $project '.claude/rules-1c/both.md.legacy')) -eq 'USER EDIT both (legacy)') "${mode}: the second update lost the saved copy"
        Pass "legacy .claude/rules/ migration keeps user edits ($mode)"
    }

    $project = New-Project 'migrate-untracked-new'
    Move-ToLegacyRule $project 'both' 'USER EDIT both (legacy)'
    Write-Fixture (Join-Path $project '.claude/rules-1c/both.md') 'untracked different file'
    $log = Invoke-Installer $project @('update', '-ForcePaths', '.claude/rules/both.md')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.claude/rules/both.md'))) 'a forced legacy copy stayed'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.claude/rules-1c/both.md.legacy'))) 'a forced legacy copy was saved'
    Assert-True ($log -notmatch 'matched no managed path') 'a pattern that matched a legacy path is reported as unmatched'
    Pass 'legacy migration: -ForcePaths on the legacy path takes the shipped version'

    $project = New-Project 'migrate-mirror'
    Move-ToLegacyRule $project 'probe' 'USER EDIT mirror' '.ai-rules/rules'
    Move-ToLegacyRule $project 'clean' '' '.ai-rules/rules'
    $null = Invoke-Installer $project @('update') '-AssumeYes'
    Assert-True ((Read-Text (Join-Path $project '.ai-rules/rules/probe.md')) -eq 'USER EDIT mirror') 'the .ai-rules mirror edit is lost'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.ai-rules/rules/clean.md'))) 'an unchanged mirror copy stayed'
    Assert-True (@((Read-Manifest $project).files.PSObject.Properties.Name | Where-Object { $_ -like '.ai-rules/rules/*' }).Count -eq 0) 'mirror manifest keys stayed'
    Pass 'legacy .ai-rules/rules/ migration keeps user edits'

    # ------------------------------------------------------------ -ForcePaths
    $project = New-Project 'force'
    $agent = Join-Path $project '.claude/agents/probe.md'
    $rule = Join-Path $project '.claude/rules-1c/probe.md'
    $patterns = @(
        @{ Name = 'comma list as one string'; Value = '.claude/agents/*,.claude/rules-1c/probe.md'; Both = $true },
        @{ Name = 'comma list with spaces and ./'; Value = './.claude/agents/probe.md, ./.claude/rules-1c/*'; Both = $true },
        @{ Name = 'backslashes'; Value = '.claude\agents\*'; Both = $false },
        @{ Name = 'leading ./'; Value = './.claude/agents/*'; Both = $false },
        @{ Name = 'absolute path'; Value = $agent; Both = $false }
    )
    foreach ($p in $patterns) {
        Write-Fixture $agent 'USER EDIT agent'
        Write-Fixture $rule 'USER EDIT rule'
        # The first update records userModified, as in a real project.
        $null = Invoke-Installer $project @('update')
        $log = Invoke-Installer $project @('update', '-ForcePaths', $p.Value) '-AssumeYes'
        Assert-True ((Read-Text $agent) -match '# Shipped agent probe') "$($p.Name): the agent was not overwritten"
        Assert-True (((Read-Text $rule) -match '# Shipped probe') -eq $p.Both) "$($p.Name): the rule overwrite is wrong"
        Assert-True ($log -notmatch 'matched no managed path') "$($p.Name): reported as unmatched"
        $expected = if ($p.Both) { 2 } else { 1 }
        Assert-True ($log -match "Overwritten with shipped version \(-Force\): $expected file") "$($p.Name): overwritten count"
        $keptText = if ($log -match '(?s)LEFT AT THEIR PREVIOUS VERSION.*') { $Matches[0] } else { '' }
        Assert-True ($keptText -notmatch 'agents/probe\.md') "$($p.Name): an overwritten file is listed as kept"
        Assert-True (-not (Read-Manifest $project).files.'.claude/agents/probe.md'.userModified) "$($p.Name): userModified stayed"
    }
    Pass '-ForcePaths: comma list, ./, backslashes and absolute path'

    Write-Fixture $agent 'USER EDIT agent'
    $null = Invoke-Installer $project @('update')
    $log = Invoke-Installer $project @('update', '-ForcePaths', '.claude/agent/*,.claude/rules-1c/probe.md') '-AssumeYes'
    Assert-True ((Read-Text $agent) -eq 'USER EDIT agent') 'a misspelled pattern overwrote the file'
    $tail = if ($log -match '(?s)matched no managed path.*') { $Matches[0] } else { '' }
    Assert-True ($tail -match '\.claude/agent/\*') 'an unmatched pattern is not reported'
    Assert-True ($log -match '-ForcePaths: 1 pattern\(s\)') 'a matched pattern is counted as unmatched'
    $log = Invoke-Installer $project @('update', '-Force', '-ForcePaths', ',') '-AssumeYes' -ExpectFailure
    Assert-True ((Read-Text $agent) -eq 'USER EDIT agent') 'an empty -ForcePaths list forced every file'
    Pass '-ForcePaths: unmatched patterns are reported, an empty list is refused'

    # ------------------------------------------------------------ USE_EDT
    function Set-EdtProject([string]$Dir) {
        Write-Fixture (Join-Path $Dir '.project') '<projectDescription/>'
        Write-Fixture (Join-Path $Dir 'DT-INF/PROJECT.PMF') 'Manifest-Version: 1.0'
        Write-Fixture (Join-Path $Dir 'src/Configuration/Configuration.mdo') '<mdclass:Configuration/>'
    }
    $cases = @(
        @{ Name = 'edt-root'; Edt = '.'; Dump = ''; Export = ''; Value = 'true' },
        @{ Name = 'edt-nested'; Edt = 'ws/Proj'; Dump = ''; Export = ''; Value = 'true' },
        @{ Name = 'edt-hybrid'; Edt = 'ws/Proj'; Dump = 'src/cf'; Export = ''; Value = 'false' },
        @{ Name = 'edt-root-hybrid'; Edt = '.'; Dump = 'xml'; Export = ''; Value = 'false' },
        @{ Name = 'edt-export-path'; Edt = 'ws/Proj'; Dump = 'a/b/c/d/dump'; Export = 'a/b/c/d/dump'; Value = 'false' },
        @{ Name = 'designer'; Edt = ''; Dump = 'src'; Export = ''; Value = 'false' },
        @{ Name = 'empty'; Edt = ''; Dump = ''; Export = ''; Value = 'false' }
    )
    foreach ($c in $cases) {
        $project = New-Project $c.Name
        if ($c.Edt) { Set-EdtProject (Join-Path $project $c.Edt) }
        if ($c.Dump) { Write-Fixture (Join-Path $project "$($c.Dump)/Configuration.xml") '<MetaDataObject/>' }
        Write-Fixture (Join-Path $project '.dev.env') "EXPORT_PATH=$($c.Export)`nINFOBASE_PATH=`nCODE_OWNER=user`n"
        $log = Invoke-Installer $project @('update') '-AssumeYes'
        Assert-True ((Read-Text (Join-Path $project '.dev.env')) -match "(?m)^USE_EDT=$($c.Value)\s*$") "update $($c.Name): expected USE_EDT=$($c.Value)"
        if ($c.Edt -and $c.Edt -ne '.') { Assert-True ($log -match [regex]::Escape($c.Edt)) "update $($c.Name): the EDT project path is not named" }
        # A value the user set is never changed.
        $opposite = if ($c.Value -eq 'true') { 'false' } else { 'true' }
        Write-Fixture (Join-Path $project '.dev.env') "USE_EDT=$opposite`nCODE_OWNER=user`n"
        $null = Invoke-Installer $project @('update') '-AssumeYes'
        Assert-True ((Read-Text (Join-Path $project '.dev.env')) -match "(?m)^USE_EDT=$opposite\s*$") "update $($c.Name): a user value was changed"
    }
    foreach ($c in @($cases | Where-Object { -not $_.Export })) {
        $project = Join-Path $Work ('init-' + $c.Name)
        [void][IO.Directory]::CreateDirectory($project)
        if ($c.Edt) { Set-EdtProject (Join-Path $project $c.Edt) }
        if ($c.Dump) { Write-Fixture (Join-Path $project "$($c.Dump)/Configuration.xml") '<MetaDataObject><Configuration><Properties><Name>X</Name></Properties></Configuration></MetaDataObject>' }
        $null = Invoke-Installer $project @('init', '-Tools', 'claude-code')
        Assert-True ((Read-Text (Join-Path $project '.dev.env')) -match "(?m)^USE_EDT=$($c.Value)\s*$") "init $($c.Name): expected USE_EDT=$($c.Value)"
    }
    Pass 'USE_EDT follows the tree on init and update, a user value is kept'

    # ------------------------------------------------------------ the user's own MCP config
    $catalogPath = Join-Path $SourceRoot 'content/mcp-servers.json'
    Write-Fixture $catalogPath '{"servers":[{"id":"1c-one","url":"http://127.0.0.1:1/mcp"},{"id":"1c-two","url":"http://127.0.0.1:2/mcp"}]}'
    $userJson = '{"mcpServers":{"user-server":{"url":"http://127.0.0.1:9999/mcp"},"1c-two":{"url":"http://10.0.0.5:8002/mcp","headers":{"Authorization":"fixture"}}},"userSetting":"' + [string][char]0x041F + '"}'
    $clients = @(
        @{ Tool = 'claude-code'; Path = '.mcp.json'; Key = 'mcpServers' },
        @{ Tool = 'cursor'; Path = '.cursor/mcp.json'; Key = 'mcpServers' },
        @{ Tool = 'kimi'; Path = '.kimi-code/mcp.json'; Key = 'mcpServers' },
        @{ Tool = 'qwen'; Path = '.qwen/settings.json'; Key = 'mcpServers' },
        @{ Tool = 'kilocode'; Path = '.kilo/kilo.json'; Key = 'mcp' }
    )
    foreach ($c in $clients) {
        $project = Join-Path $Work ('mcp-' + $c.Tool)
        $config = Join-Path $project $c.Path
        Write-Fixture (Join-Path $project '.dev.env') "INFOBASE_PATH=`nUSE_EDT=false`nCODE_OWNER=user`n"
        Write-Fixture $config ($userJson.Replace('mcpServers', $c.Key))
        foreach ($run in @(@('init', '-Tools', $c.Tool), @('update'))) {
            $null = Invoke-Installer $project $run
            $json = [IO.File]::ReadAllText($config, $Utf8) | ConvertFrom-Json
            $servers = $json.($c.Key)
            Assert-True ($servers.'user-server'.url -eq 'http://127.0.0.1:9999/mcp') "$($c.Tool) $($run[0]): the user server is lost"
            Assert-True ($servers.'1c-two'.url -eq 'http://10.0.0.5:8002/mcp' -and $servers.'1c-two'.headers.Authorization -eq 'fixture') "$($c.Tool) $($run[0]): the user URL or headers are replaced"
            Assert-True ($json.userSetting -eq [string][char]0x041F) "$($c.Tool) $($run[0]): a user setting is lost or re-encoded"
            Assert-True ([bool]$servers.'1c-one') "$($c.Tool) $($run[0]): the missing catalog server was not added"
        }
        # A server the installer added follows the catalog; the user's do not.
        Write-Fixture $catalogPath '{"servers":[{"id":"1c-one","url":"http://127.0.0.1:11/mcp"},{"id":"1c-two","url":"http://127.0.0.1:2/mcp"}]}'
        $null = Invoke-Installer $project @('update')
        $servers = ([IO.File]::ReadAllText($config, $Utf8) | ConvertFrom-Json).($c.Key)
        $oneText = $servers.'1c-one' | ConvertTo-Json -Depth 5 -Compress
        Assert-True ($oneText -match '127\.0\.0\.1:11/mcp') "$($c.Tool): the managed server was not refreshed: $oneText"
        Assert-True ($servers.'1c-two'.url -eq 'http://10.0.0.5:8002/mcp') "$($c.Tool): the user server was refreshed"
        $null = Invoke-Installer $project @('remove')
        $json = [IO.File]::ReadAllText($config, $Utf8) | ConvertFrom-Json
        $servers = $json.($c.Key)
        Assert-True ($servers.'user-server' -and $servers.'1c-two' -and -not $servers.'1c-one' -and $json.userSetting) "$($c.Tool): remove did not leave exactly the user's config"
        Write-Fixture $catalogPath '{"servers":[{"id":"1c-one","url":"http://127.0.0.1:1/mcp"},{"id":"1c-two","url":"http://127.0.0.1:2/mcp"}]}'
    }
    Pass 'user MCP config (JSON): servers, URLs, headers and settings survive init, update and remove'

    foreach ($c in $clients) {
        $project = Join-Path $Work ('mcp-bad-' + $c.Tool)
        $config = Join-Path $project $c.Path
        Write-Fixture (Join-Path $project '.dev.env') "INFOBASE_PATH=`nUSE_EDT=false`nCODE_OWNER=user`n"
        foreach ($bad in @('{invalid json', '{"' + $c.Key + '":[]}')) {
            Write-Fixture $config $bad
            $null = Invoke-Installer $project @('init', '-Tools', $c.Tool)
            Assert-True ((Read-Text $config) -eq $bad) "$($c.Tool): an unreadable user config was overwritten"
            $null = Invoke-Installer $project @('update', '-Force')
            Assert-True ((Read-Text $config) -eq $bad) "$($c.Tool): -Force overwrote an unreadable user config"
            Remove-Item -LiteralPath (Join-Path $project '.ai-rules.json') -Force
        }
    }
    $project = Join-Path $Work 'mcp-codex'
    $toml = "[mcp_servers.custom]`nurl = `"http://127.0.0.1:9099/mcp`"`n`n[features]`nmulti_agent = false`n"
    Write-Fixture (Join-Path $project '.dev.env') "INFOBASE_PATH=`nUSE_EDT=false`nCODE_OWNER=user`n"
    Write-Fixture (Join-Path $project '.codex/config.toml') $toml
    foreach ($run in @(@('init', '-Tools', 'codex'), @('update'), @('update', '-Force'), @('remove'))) {
        $null = Invoke-Installer $project $run
        Assert-True ((Read-Text (Join-Path $project '.codex/config.toml')) -eq $toml) "codex $($run[0]): the user's config.toml changed"
    }
    Pass 'user MCP config: unreadable JSON and Codex TOML are never overwritten'

    # A config the installer created stays managed as a whole.
    $project = New-Project 'mcp-own'
    $config = Join-Path $project '.mcp.json'
    Assert-True ([bool](Read-Text $config | ConvertFrom-Json).mcpServers.'1c-one') 'a fresh config was not created'
    Write-Fixture $catalogPath '{"servers":[{"id":"1c-one","url":"http://127.0.0.1:21/mcp"}]}'
    $null = Invoke-Installer $project @('update')
    $servers = (Read-Text $config | ConvertFrom-Json).mcpServers
    Assert-True (($servers.'1c-one' | ConvertTo-Json -Compress) -match ':21/mcp' -and -not $servers.'1c-two') 'a managed config did not follow the catalog'
    $null = Invoke-Installer $project @('remove')
    Assert-True (-not (Test-Path -LiteralPath $config)) 'remove left a managed config'
    Write-Fixture $catalogPath '{"servers":[]}'
    Pass 'a config created by the installer still follows the catalog'

    # ------------------------------------------------------------ adapter entry file
    $project = New-Project 'entry'
    $claudeMd = Join-Path $project 'CLAUDE.md'
    $stub = Read-Text $claudeMd
    foreach ($run in 1..2) {
        $null = Invoke-Installer $project @('update')
        Assert-True (-not (Read-Manifest $project).files.'CLAUDE.md'.userModified) "update ${run}: an unchanged CLAUDE.md is flagged userModified"
    }
    $adapterPath = Join-Path $SourceRoot 'adapters/claude-code.yaml'
    $adapterText = Read-Text $adapterPath
    Assert-True ($adapterText.Contains('@AGENTS.md')) 'precondition: the entry template imports AGENTS.md'
    Write-Fixture $adapterPath ($adapterText.Replace('See @AGENTS.md', 'Refreshed entry template: see @AGENTS.md'))
    $null = Invoke-Installer $project @('update')
    Assert-True ((Read-Text $claudeMd) -match 'Refreshed entry template' -and (Read-Text $claudeMd) -ne $stub) 'an unchanged CLAUDE.md did not receive the new template'
    Write-Fixture $claudeMd 'USER CLAUDE.md'
    $null = Invoke-Installer $project @('update')
    Assert-True ((Read-Text $claudeMd) -eq 'USER CLAUDE.md' -and (Read-Manifest $project).files.'CLAUDE.md'.userModified) 'an edited CLAUDE.md was overwritten'
    Write-Fixture $adapterPath $adapterText
    Pass 'adapter entry file: unchanged stays managed, edited is kept'

    Write-Host "Passed: $script:Passed"
}
finally {
    $resolved = [IO.Path]::GetFullPath($Work)
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if ($resolved.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolved -Leaf) -match '^installer-update-[a-f0-9]{32}$') {
        if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
    }
    else { throw "Unsafe fixture cleanup refused: $resolved" }
}
