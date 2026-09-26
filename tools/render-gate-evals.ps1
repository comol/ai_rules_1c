#Requires -Version 5.1
<#
.SYNOPSIS
    Renders tools/tests/gate-scenarios.json into a Claude Code eval plugin.

.DESCRIPTION
    `claude plugin eval` runs every case in an empty sandbox workspace with its
    own configuration: project CLAUDE.md / AGENTS.md, project settings and the
    project's .mcp.json never load, and only the MCP servers of the plugin under
    test exist (named mcp__plugin_<plugin>_<server>__<tool>). The output is
    therefore a self-contained plugin:

        <OutDir>/
            .claude-plugin/plugin.json   plugin "gates"
            .mcp.json                    every corpus server; real URL or a dead placeholder
            workspace/                   1c-rules installed for Claude Code (install.ps1)
                                         plus the sources of tools/tests/eval-fixtures/common
            cases/
                mocks/<server>/          suite-wide agent mocks from tools/tests/eval-mocks,
                                         each extended with eval-mocks/_world.md
                <scenario id>-<gate id>/
                    prompt.md            task; AGENTS.md as append_system_prompt
                    case.yaml            context.scaffold_script
                    scaffold.sh          copies workspace/ into the run's workspace, then
                                         tools/tests/eval-fixtures/<scenario id>/ if present
                    mocks/<server>/      opt-in servers named by the scenario
                    graders/<name>.md    tool_used / tool_order / regex / llm

    Servers that any scenario lists under "mocks" (the memory providers) are
    opt-in: a case exposes them only when its wire or "mocks" names them, and
    "mocks" can narrow their tools ("tools") or turn a tool into an error
    ("errors"). Every other server with a directory in tools/tests/eval-mocks is
    mocked suite-wide; the rest (platform docs, SSL) run for real.

    The corpus is the single source of truth; this script never edits it. Run the
    rendered suite from any directory (native Windows cannot sandbox shell tools,
    so the suite grants none):

        claude plugin eval <OutDir> --eval-dir cases --scaffold --allow-real-servers
            --trust-plugin --allow-tools Write Edit <real server grants printed below>

    The graders are structural plus one judge: tool_used asserts a wire call
    happened (or, for forbidden tools, did not), tool_order asserts the MCP call
    preceded a native tool, regex asserts the reply contains the required line,
    llm judges the scenario criteria against the trace.

.PARAMETER CorpusPath
    Path to gate-scenarios.json. Default: tools/tests/gate-scenarios.json.

.PARAMETER OutDir
    Output plugin directory. Default: tools/tests/evals. Generated case
    directories, cases/mocks and workspace are replaced; cases/results is kept.

.PARAMETER Workspace
    An existing project with 1c-rules installed for Claude Code to copy instead
    of running install.ps1.
#>
[CmdletBinding()]
param(
    [string]$CorpusPath,
    [string]$OutDir,
    [string]$Workspace
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
if (-not $CorpusPath) { $CorpusPath = Join-Path $root 'tools/tests/gate-scenarios.json' }
if (-not $OutDir) { $OutDir = Join-Path $root 'tools/tests/evals' }
$mocksSource = Join-Path $root 'tools/tests/eval-mocks'
$fixturesSource = Join-Path $root 'tools/tests/eval-fixtures'
$pluginName = 'gates'
$deadUrl = 'http://127.0.0.1:9/mcp'
# Tool input that does not touch the installed ruleset or the project settings.
$settingsExclusion = '^(?![\s\S]*(\.claude|\.dev\.env|AGENTS\.md|CLAUDE\.md|RULES\.md|memory\.md|openspec))'

$utf8 = New-Object System.Text.UTF8Encoding($false)
$corpus = [System.IO.File]::ReadAllText($CorpusPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json

$servers = @{}
foreach ($prop in $corpus.servers.PSObject.Properties) { $servers[$prop.Name] = [string]$prop.Value }

function Get-Field {
    # Optional corpus fields are absent, not null, on most scenarios; StrictMode
    # would throw on a direct property access.
    param($Object, [string]$Name, $Default = @())
    if ($null -ne $Object -and $Object.PSObject.Properties[$Name]) { return $Object.$Name }
    return $Default
}

function Resolve-ToolName {
    # "graph:search_code" -> mcp__plugin_gates_1c-graph-metadata-mcp__search_code; "Grep" -> Grep
    param([string]$Ref)
    $parts = $Ref -split ':', 2
    if ($parts.Count -eq 2 -and $servers.ContainsKey($parts[0])) {
        return 'mcp__plugin_' + $pluginName + '_' + $servers[$parts[0]] + '__' + $parts[1]
    }
    return $Ref
}

function Write-Utf8 {
    param([string]$Path, [string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, $utf8)
}

function ConvertTo-PosixPath {
    # The scaffold runs under bash; on Windows that is Git Bash (C:\x -> /c/x).
    param([string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full -match '^([A-Za-z]):\\(.*)$') { return '/' + $Matches[1].ToLowerInvariant() + '/' + ($Matches[2] -replace '\\', '/') }
    return $full
}

function Copy-Directory {
    param([string]$From, [string]$To)
    New-Item -ItemType Directory -Force -Path $To | Out-Null
    Copy-Item -Path (Join-Path $From '*') -Destination $To -Recurse -Force
    foreach ($hidden in @(Get-ChildItem -LiteralPath $From -Force | Where-Object { $_.Name.StartsWith('.') })) {
        Copy-Item -LiteralPath $hidden.FullName -Destination $To -Recurse -Force
    }
}

function Copy-MockServer {
    # Every agent mock answers from the same configuration description
    # (eval-mocks/_world.md), so graph, code index and fixtures agree.
    param([string]$ServerId, [string]$To)
    Copy-Directory -From (Join-Path $mocksSource $ServerId) -To $To
    $serverMd = Join-Path $To '_server.md'
    if (Test-Path -LiteralPath $serverMd) {
        $text = [System.IO.File]::ReadAllText($serverMd, [System.Text.Encoding]::UTF8).TrimEnd() + "`n`n" + $world
        Write-Utf8 $serverMd ($text.TrimEnd() + "`n")
    }
}

# --- plugin skeleton -------------------------------------------------------

if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path
$casesDir = Join-Path $OutDir 'cases'
New-Item -ItemType Directory -Force -Path (Join-Path $OutDir '.claude-plugin') | Out-Null
New-Item -ItemType Directory -Force -Path $casesDir | Out-Null
Write-Utf8 (Join-Path $OutDir '.claude-plugin/plugin.json') ((@{ name = $pluginName; version = '1.0.0'; description = '1c-rules gate scenarios rendered from tools/tests/gate-scenarios.json' } | ConvertTo-Json) + "`n")

$declared = @{}
$catalog = [System.IO.File]::ReadAllText((Join-Path $root 'content/mcp-servers.json'), [System.Text.Encoding]::UTF8) | ConvertFrom-Json
foreach ($srv in @($catalog.servers)) { if ([string]$srv.url -notmatch '\{') { $declared[[string]$srv.id] = [string]$srv.url } }
$mcp = [ordered]@{}
foreach ($sid in ($servers.Values | Sort-Object -Unique)) {
    $url = $deadUrl
    if ($declared.ContainsKey($sid)) { $url = $declared[$sid] }
    $mcp[$sid] = [ordered]@{ type = 'http'; url = $url }
}
Write-Utf8 (Join-Path $OutDir '.mcp.json') ((@{ mcpServers = $mcp } | ConvertTo-Json -Depth 5) + "`n")

# --- workspace: the ruleset as a Claude Code project ------------------------

$workspaceDir = Join-Path $OutDir 'workspace'
if (Test-Path -LiteralPath $workspaceDir) { Remove-Item -LiteralPath $workspaceDir -Recurse -Force }
if ($Workspace) {
    Copy-Directory -From $Workspace -To $workspaceDir
} else {
    New-Item -ItemType Directory -Path $workspaceDir | Out-Null
    $installLog = Join-Path $OutDir 'workspace-install.log'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'install.ps1') init -Tools claude-code `
        -ProjectRoot $workspaceDir -Source $root -NonInteractive -McpMode managed *> $installLog
    if ($LASTEXITCODE -ne 0) { throw ('install.ps1 failed with exit ' + $LASTEXITCODE + '; see ' + $installLog) }
}
# MCP comes from the plugin; a project .mcp.json would never load in a run anyway.
$projectMcp = Join-Path $workspaceDir '.mcp.json'
if (Test-Path -LiteralPath $projectMcp) { Remove-Item -LiteralPath $projectMcp -Force }
# Project sources the edit scenarios work on; a case may overlay its own
# (eval-fixtures/<scenario id>) from its scaffold.
Copy-Directory -From (Join-Path $fixturesSource 'common') -To $workspaceDir
# A run loads no project settings, so the installed agents, skills and
# commands reach the session as components of this plugin instead.
foreach ($component in @('agents', 'skills', 'commands')) {
    $componentDir = Join-Path $OutDir $component
    if (Test-Path -LiteralPath $componentDir) { Remove-Item -LiteralPath $componentDir -Recurse -Force }
    $installed = Join-Path $workspaceDir ('.claude/' + $component)
    if (Test-Path -LiteralPath $installed) { Copy-Directory -From $installed -To $componentDir }
}
$agentsMd = [System.IO.File]::ReadAllText((Join-Path $workspaceDir 'AGENTS.md'), [System.Text.Encoding]::UTF8)
$systemPrompt = "Contents of the project's AGENTS.md (a normal Claude Code session loads it through CLAUDE.md). These are the project instructions:`n`n" + $agentsMd
$systemPromptYaml = (($systemPrompt -replace "`r`n", "`n").TrimEnd("`n") -split "`n" | ForEach-Object { if ($_.Length -gt 0) { '  ' + $_ } else { '' } }) -join "`n"
$scaffold = "#!/usr/bin/env bash`nset -e`ncp -a `"" + (ConvertTo-PosixPath $workspaceDir) + "/.`" .`n"

# --- mocks ------------------------------------------------------------------

$world = [System.IO.File]::ReadAllText((Join-Path $mocksSource '_world.md'), [System.Text.Encoding]::UTF8)

$optIn = @{}
foreach ($alias in @(Get-Field $corpus 'opt_in_servers')) { $optIn[$servers[[string]$alias]] = $true }
$suiteMocks = Join-Path $casesDir 'mocks'
if (Test-Path -LiteralPath $suiteMocks) { Remove-Item -LiteralPath $suiteMocks -Recurse -Force }
$mocked = @{}
foreach ($dir in @(Get-ChildItem -LiteralPath $mocksSource -Directory)) {
    $mocked[$dir.Name] = $true
    if (-not $optIn.ContainsKey($dir.Name)) { Copy-MockServer -ServerId $dir.Name -To (Join-Path $suiteMocks $dir.Name) }
}
$realServers = @($servers.Values | Sort-Object -Unique | Where-Object { -not $mocked.ContainsKey($_) -and $declared.ContainsKey($_) })

# --- cases ------------------------------------------------------------------

foreach ($old in @(Get-ChildItem -LiteralPath $casesDir -Directory | Where-Object { $_.Name -match '^s\d+-g-' })) {
    Remove-Item -LiteralPath $old.FullName -Recurse -Force
}

$rendered = 0
foreach ($sc in @($corpus.scenarios)) {
    $claim = (@($corpus.gates) | Where-Object { $_.id -eq $sc.gate } | Select-Object -First 1).claim
    $caseDir = Join-Path $casesDir (([string]$sc.id + '-' + [string]$sc.gate).ToLowerInvariant())
    $gradersDir = Join-Path $caseDir 'graders'
    New-Item -ItemType Directory -Path $gradersDir | Out-Null

    # Case mocks: an opt-in server named by the wire or "mocks" is copied whole;
    # any other server named by "mocks" gets only the overriding files, which
    # replace the suite's file by file. "tools" narrows what the agent mock
    # answers, "errors" and "answers" pin one tool to a fixed error or result.
    $caseMocks = Get-Field $sc 'mocks' $null
    $specs = @{}
    foreach ($step in @(Get-Field $sc 'wire')) { if ($optIn.ContainsKey($servers[[string]$step.server])) { $specs[[string]$step.server] = $null } }
    if ($caseMocks) { foreach ($prop in $caseMocks.PSObject.Properties) { $specs[$prop.Name] = $prop.Value } }
    foreach ($alias in $specs.Keys) {
        $sid = $servers[$alias]
        $target = Join-Path $caseDir ('mocks/' + $sid)
        $spec = $specs[$alias]
        $subset = @(Get-Field $spec 'tools')
        if ($optIn.ContainsKey($sid)) {
            Copy-MockServer -ServerId $sid -To $target
        } elseif ($subset.Count -gt 0) {
            New-Item -ItemType Directory -Force -Path $target | Out-Null
            Copy-Item -LiteralPath (Join-Path $suiteMocks ($sid + '/_server.md')) -Destination $target
        } else {
            New-Item -ItemType Directory -Force -Path $target | Out-Null
        }
        if ($subset.Count -gt 0) {
            $serverMd = Join-Path $target '_server.md'
            $text = [System.IO.File]::ReadAllText($serverMd, [System.Text.Encoding]::UTF8)
            $text = [regex]::Replace($text, '(?m)^tools: \[.*\]$', ('tools: [' + ($subset -join ', ') + ']'))
            Write-Utf8 $serverMd $text
        }
        $errors = Get-Field $spec 'errors' $null
        if ($errors) {
            foreach ($prop in $errors.PSObject.Properties) {
                Write-Utf8 (Join-Path $target ($prop.Name + '.md')) ("---`nerror: true`n---`n" + [string]$prop.Value + "`n")
            }
        }
        $answers = Get-Field $spec 'answers' $null
        if ($answers) {
            foreach ($prop in $answers.PSObject.Properties) {
                Write-Utf8 (Join-Path $target ($prop.Name + '.md')) ("---`ntype: fixed`n---`n" + [string]$prop.Value + "`n")
            }
        }
    }

    # Read-only tools are granted by listing; Edit / Write and real MCP servers
    # need the operator's --allow-tools as well. Shell tools are never listed.
    $allowed = New-Object System.Collections.Generic.List[string]
    foreach ($t in @('Read', 'Grep', 'Glob', 'Edit', 'Write', 'Agent', 'Skill')) { $allowed.Add($t) }
    foreach ($step in @(Get-Field $sc 'wire')) { $allowed.Add((Resolve-ToolName ([string]$step.server + ':' + [string]$step.tool))) }
    foreach ($sid in ($servers.Values | Sort-Object -Unique)) { $allowed.Add('mcp__plugin_' + $pluginName + '_' + $sid + '__*') }
    $allowedYaml = ($allowed | Select-Object -Unique | ForEach-Object { '  - ' + $_ }) -join "`n"

    $prompt = @(
        '---',
        ('name: ' + [string]$sc.id + ' ' + [string]$sc.area),
        ("description: '" + ([string]$sc.gate + ': ' + [string]$claim -replace "'", "''") + "'"),
        ('tags: [' + [string]$sc.gate + ', gates]'),
        'runs: 1',
        ('max_turns: ' + (Get-Field $sc 'max_turns' 15)),
        'timeout_seconds: 600',
        'allowed_tools:',
        $allowedYaml,
        'append_system_prompt: |',
        $systemPromptYaml,
        '---',
        [string]$sc.task
    ) -join "`n"
    Write-Utf8 (Join-Path $caseDir 'prompt.md') ($prompt + "`n")
    Write-Utf8 (Join-Path $caseDir 'case.yaml') ("schema_version: `"1.1`"`nname: " + [string]$sc.id + ' ' + [string]$sc.area + "`ncontext:`n  scaffold_script: scaffold.sh`n")
    # Scaffold: workspace, named fixture sets, the case's own overlay, then the
    # .dev.env values the task states ("env"), so the premise is on disk.
    $caseScaffold = $scaffold
    foreach ($set in @(Get-Field $sc 'fixtures')) {
        $caseScaffold += 'cp -a "' + (ConvertTo-PosixPath (Join-Path $fixturesSource ('sets/' + [string]$set))) + "/.`" .`n"
    }
    $overlay = Join-Path $fixturesSource ([string]$sc.id)
    if (Test-Path -LiteralPath $overlay) { $caseScaffold += 'cp -a "' + (ConvertTo-PosixPath $overlay) + "/.`" .`n" }
    $envValues = Get-Field $sc 'env' $null
    if ($envValues) {
        foreach ($prop in $envValues.PSObject.Properties) {
            $pair = $prop.Name + '=' + [string]$prop.Value
            $caseScaffold += "if grep -q '^" + $prop.Name + "=' .dev.env; then sed -i 's|^" + $prop.Name + "=.*|" + $pair + "|' .dev.env; else echo '" + $pair + "' >> .dev.env; fi`n"
        }
    }
    Write-Utf8 (Join-Path $caseDir 'scaffold.sh') $caseScaffold

    $n = 0
    foreach ($step in @(Get-Field $sc 'wire')) {
        $n++
        $lines = New-Object System.Collections.Generic.List[string]
        $lines.Add('---')
        $lines.Add('name: wire-' + $n + '-' + [string]$step.tool)
        $lines.Add('type: tool_used')
        $lines.Add('tool: ' + (Resolve-ToolName ([string]$step.server + ':' + [string]$step.tool)))
        $lines.Add('min: 1')
        $max = Get-Field $step 'max' $null
        if ($null -ne $max) { $lines.Add('max: ' + $max) }
        $inputMatch = [string](Get-Field $step 'input_match' '')
        if ($inputMatch) { $lines.Add("input_match: '" + ($inputMatch -replace "'", "''") + "'") }
        $lines.Add('---')
        $lines.Add('The wire of scenario ' + [string]$sc.id + ' calls ' + [string]$step.tool + ' (' + [string]$step.server + ') with arguments shaped like: ' + ($step.args | ConvertTo-Json -Compress -Depth 5))
        Write-Utf8 (Join-Path $gradersDir ('wire-' + $n + '.md')) (($lines -join "`n") + "`n")
    }

    $n = 0
    foreach ($entry in @(Get-Field $sc 'forbid')) {
        $n++
        $parts = ([string]$entry) -split ':', 2
        $lines = New-Object System.Collections.Generic.List[string]
        $lines.Add('---')
        $lines.Add('name: forbid-' + $n)
        $lines.Add('type: tool_used')
        if ($parts.Count -eq 2 -and $servers.ContainsKey($parts[0])) {
            $lines.Add('tool: ' + (Resolve-ToolName ([string]$entry)))
        } else {
            $lines.Add('tool: ' + $parts[0])
            if ($parts.Count -eq 2) { $lines.Add("input_match: '" + ([regex]::Escape($parts[1]) -replace "'", "''") + "'") }
        }
        $lines.Add('min: 0')
        $lines.Add('max: 0')
        $lines.Add('---')
        $lines.Add('Scenario ' + [string]$sc.id + ' must not call ' + [string]$entry + '.')
        Write-Utf8 (Join-Path $gradersDir ('forbid-' + $n + '.md')) (($lines -join "`n") + "`n")
    }

    # A native tool on the "after" side must not match reading the ruleset or
    # the project settings: the mcp-policy gate makes that the first action.
    $n = 0
    foreach ($pair in @(Get-Field $sc 'order')) {
        $n++
        $after = Resolve-ToolName ([string]$pair.after)
        $afterYaml = 'after: ' + $after
        if ($after -notmatch '^mcp__') {
            $afterYaml = "after:`n  tool: " + $after + "`n  input_match: '" + $settingsExclusion + "'"
        }
        $lines = @(
            '---',
            ('name: order-' + $n),
            'type: tool_order',
            ('before: ' + (Resolve-ToolName ([string]$pair.before))),
            $afterYaml,
            '---',
            ('Scenario ' + [string]$sc.id + ': ' + [string]$pair.before + ' is called before ' + [string]$pair.after + ' (a native tool may follow the MCP attempt, never precede it).')
        )
        Write-Utf8 (Join-Path $gradersDir ('order-' + $n + '.md')) (($lines -join "`n") + "`n")
    }

    $pattern = [string](Get-Field $sc 'pattern' '')
    if ($pattern) {
        $lines = @(
            '---',
            'name: reply-pattern',
            'type: regex',
            ("pattern: '" + ($pattern -replace "'", "''") + "'"),
            'flags: i',
            'match: contains',
            'target: last_message',
            '---',
            ('The final reply of scenario ' + [string]$sc.id + ' contains ' + $pattern + ' (response class: ' + [string]$sc.response + ').')
        )
        Write-Utf8 (Join-Path $gradersDir 'reply-pattern.md') (($lines -join "`n") + "`n")
    }

    # The judge reads the final reply: a trace focus shows it only the first and
    # last twelve messages, mostly rule text, so evidence in the middle looked
    # absent. Which tools ran, and in which order, is graded structurally.
    $llm = @(
        '---',
        'name: criteria',
        'type: llm',
        'focus: last_message',
        '---',
        ('You grade the final reply of an agent that follows a 1C development ruleset. Gate ' + [string]$sc.gate + ': ' + $claim),
        '',
        ('Task given to the agent: ' + [string]$sc.task),
        '',
        ('Pass criteria: ' + [string]$sc.criteria),
        '',
        ('Expected response class: ' + [string]$sc.response + '.'),
        '',
        'Which tools ran and in which order is checked by separate structural graders, so do not fail the reply for not showing tool calls. Fail it when what the reply states or delivers contradicts the pass criteria, when it omits something the criteria require the reply itself to contain, or when it presents a check or result as done while saying it was not run.'
    )
    Write-Utf8 (Join-Path $gradersDir 'criteria.md') (($llm -join "`n") + "`n")
    $rendered++
}

$grants = @('Write', 'Edit') + @($realServers | ForEach-Object { '"mcp__plugin_' + $pluginName + '_' + $_ + '__*"' })
Write-Host ('Rendered ' + $rendered + ' eval cases into ' + $OutDir)
Write-Host ('Run: claude plugin eval "' + $OutDir + '" --eval-dir cases --scaffold --allow-real-servers --trust-plugin --allow-tools ' + ($grants -join ' '))
