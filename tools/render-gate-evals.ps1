#Requires -Version 5.1
<#
.SYNOPSIS
    Renders tools/tests/gate-scenarios.json into Claude Code plugin eval cases.

.DESCRIPTION
    Every scenario of the corpus becomes one eval case directory:

        <OutDir>/<scenario id>-<gate id>/
            prompt.md              frontmatter (name, tags, runs, max_turns, allowed_tools) + the task
            graders/<name>.md      tool_used / tool_order / regex / llm graders derived from the wire

    A scenario may set "max_turns" (default 15) to cap the turn budget, and a wire
    step may set "max" to cap how often that call may happen.

    The corpus is the single source of truth; this script never edits it. Run the
    rendered suite with the Claude Code eval runner against a project that has
    1c-rules installed and the MCP servers exposed, for example:

        claude plugin eval <path to plugins/1c-rules> --eval-dir tools/tests/evals --json

    The graders are structural: tool_used asserts a wire call happened (or, for
    forbidden tools, did not), tool_order asserts the MCP call preceded a native
    tool, regex asserts the delivery contains the required line, llm judges the
    scenario criteria. They cannot see server answers, so a scenario whose
    expected class is "refused" is graded on the reply text.

.PARAMETER CorpusPath
    Path to gate-scenarios.json. Default: tools/tests/gate-scenarios.json next to this script.

.PARAMETER OutDir
    Output directory. Default: tools/tests/evals. Existing case directories with
    the same name are replaced; other directories are left alone.
#>
[CmdletBinding()]
param(
    [string]$CorpusPath,
    [string]$OutDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
if (-not $CorpusPath) { $CorpusPath = Join-Path $root 'tools/tests/gate-scenarios.json' }
if (-not $OutDir) { $OutDir = Join-Path $root 'tools/tests/evals' }

$utf8 = New-Object System.Text.UTF8Encoding($false)
$corpus = [System.IO.File]::ReadAllText($CorpusPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json

$servers = @{}
foreach ($prop in $corpus.servers.PSObject.Properties) { $servers[$prop.Name] = [string]$prop.Value }

function Resolve-ToolName {
    # "graph:search_code" -> mcp__1c-graph-metadata-mcp__search_code; "Grep" -> Grep
    param([string]$Ref)
    $parts = $Ref -split ':', 2
    if ($parts.Count -eq 2 -and $servers.ContainsKey($parts[0])) {
        return 'mcp__' + $servers[$parts[0]] + '__' + $parts[1]
    }
    return $Ref
}

function Write-Utf8 {
    param([string]$Path, [string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, $utf8)
}

function Escape-Regex {
    param([string]$Text)
    return [regex]::Escape($Text)
}

function Get-Field {
    # Optional corpus fields are absent, not null, on most scenarios; StrictMode
    # would throw on a direct property access.
    param($Object, [string]$Name, $Default = @())
    if ($Object.PSObject.Properties[$Name]) { return $Object.$Name }
    return $Default
}

if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

$rendered = 0
foreach ($sc in @($corpus.scenarios)) {
    $caseName = ([string]$sc.id + '-' + [string]$sc.gate).ToLowerInvariant()
    $caseDir = Join-Path $OutDir $caseName
    if (Test-Path -LiteralPath $caseDir) { Remove-Item -LiteralPath $caseDir -Recurse -Force }
    $gradersDir = Join-Path $caseDir 'graders'
    New-Item -ItemType Directory -Path $gradersDir | Out-Null

    # allowed tools: every wire tool plus the native set the ruleset expects
    $allowed = New-Object System.Collections.Generic.List[string]
    foreach ($t in @('Read', 'Grep', 'Glob', 'Edit', 'Write', 'Bash', 'PowerShell', 'Agent')) { $allowed.Add($t) }
    foreach ($step in @(Get-Field $sc 'wire')) { $allowed.Add((Resolve-ToolName ([string]$step.server + ':' + [string]$step.tool))) }
    foreach ($srv in $servers.Values) { $allowed.Add('mcp__' + $srv + '__*') }
    $allowedYaml = ($allowed | Select-Object -Unique | ForEach-Object { '  - ' + $_ }) -join "`n"

    $prompt = @(
        '---',
        ('name: ' + [string]$sc.id + ' ' + [string]$sc.area),
        ('tags: [' + [string]$sc.gate + ', gates]'),
        'runs: 1',
        ('max_turns: ' + (Get-Field $sc 'max_turns' 15)),
        'timeout_seconds: 600',
        'allowed_tools:',
        $allowedYaml,
        '---',
        [string]$sc.task,
        '',
        ('<!-- gate ' + [string]$sc.gate + ': ' + (($corpus.gates | Where-Object { $_.id -eq $sc.gate } | Select-Object -First 1).claim) + ' -->')
    ) -join "`n"
    Write-Utf8 (Join-Path $caseDir 'prompt.md') ($prompt + "`n")

    $n = 0
    foreach ($step in @(Get-Field $sc 'wire')) {
        $n++
        $tool = Resolve-ToolName ([string]$step.server + ':' + [string]$step.tool)
        $lines = New-Object System.Collections.Generic.List[string]
        $lines.Add('---')
        $lines.Add('name: wire-' + $n + '-' + [string]$step.tool)
        $lines.Add('type: tool_used')
        $lines.Add('tool: ' + $tool)
        $lines.Add('target: trace')
        $lines.Add('min: 1')
        $max = $null
        if ($step.PSObject.Properties['max']) { $max = $step.max }
        if ($null -ne $max) { $lines.Add('max: ' + $max) }
        $inputMatch = $null
        if ($step.PSObject.Properties['input_match']) { $inputMatch = [string]$step.input_match }
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
            if ($parts.Count -eq 2) { $lines.Add("input_match: '" + (Escape-Regex $parts[1]) + "'") }
        }
        $lines.Add('target: trace')
        $lines.Add('min: 0')
        $lines.Add('max: 0')
        $lines.Add('---')
        $lines.Add('Scenario ' + [string]$sc.id + ' must not call ' + [string]$entry + '.')
        Write-Utf8 (Join-Path $gradersDir ('forbid-' + $n + '.md')) (($lines -join "`n") + "`n")
    }

    $n = 0
    foreach ($pair in @(Get-Field $sc 'order')) {
        $n++
        $lines = @(
            '---',
            ('name: order-' + $n),
            'type: tool_order',
            ('before: ' + (Resolve-ToolName ([string]$pair.before))),
            ('after: ' + (Resolve-ToolName ([string]$pair.after))),
            'target: trace',
            '---',
            ('Scenario ' + [string]$sc.id + ': ' + [string]$pair.before + ' is called before ' + [string]$pair.after + ' (a native tool may follow the MCP attempt, never precede it).')
        )
        Write-Utf8 (Join-Path $gradersDir ('order-' + $n + '.md')) (($lines -join "`n") + "`n")
    }

    $pattern = $null
    if ($sc.PSObject.Properties['pattern']) { $pattern = [string]$sc.pattern }
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

    $llm = @(
        '---',
        'name: criteria',
        'type: llm',
        'target: trace',
        '---',
        ('Gate ' + [string]$sc.gate + ': ' + (($corpus.gates | Where-Object { $_.id -eq $sc.gate } | Select-Object -First 1).claim)),
        '',
        ('Pass criteria: ' + [string]$sc.criteria),
        '',
        ('Expected response class: ' + [string]$sc.response + '. A silently skipped gate, an invented tool result, or a reply that claims a check it did not run fails this grader.'),
        '',
        'Efficiency: also fail when the trace repeats a call against unchanged state, probes sibling tools after a typed server answer closed the lane, or re-runs a validator for style noise - those are defects of the ruleset even when the final answer is right.'
    )
    Write-Utf8 (Join-Path $gradersDir 'criteria.md') (($llm -join "`n") + "`n")
    $rendered++
}

Write-Host ('Rendered ' + $rendered + ' eval cases into ' + $OutDir)
