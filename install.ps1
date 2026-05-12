#Requires -Version 5.1
<#
.SYNOPSIS
    1c-rules installer (PowerShell channel)

.DESCRIPTION
    Implements the same installation protocol as AGENT-INSTALL.md but
    deterministically through a CLI. Reads content/ and adapters/*.yaml,
    writes per-tool files and a shared .ai-rules.json manifest.

    Commands:
      init     First install (no manifest yet, or force re-init).
      update   Update installed rules to the current repo version.
      add      Add rules for an additional tool.
      remove   Remove rules (optionally only for one tool).
      doctor   Read-only diagnostic.
      eject    Delete manifest; leave files in place.

.PARAMETER Command
    Command to run. One of: init, update, add, remove, doctor, eject.

.PARAMETER Tool
    For `add` / `remove`: the tool id to operate on.

.PARAMETER Tools
    For `init` / `update`: explicit list of active tool ids. If omitted,
    the script auto-detects and prompts the user.

.PARAMETER Source
    Source repository URL or local path. Defaults to the directory where
    install.ps1 lives (supports running from a cloned repo directly).
    A URL value (https://..., git@host:..., or path ending with .git) is
    shallow-cloned into a deterministic cache directory under $env:TEMP
    (key derived from the URL hash) and reused on subsequent runs. Requires
    'git' on PATH when a URL is supplied.

.PARAMETER NonInteractive
    Do not prompt. Use defaults: accept detected tools, skip collisions,
    keep user-modified files on conflict.

.PARAMETER AssumeYes
    Answer "yes" to confirmation prompts (but still pause on destructive
    conflicts — those require -NonInteractive to auto-resolve).

.PARAMETER ProjectRoot
    Project root directory to install into. Defaults to the current working
    directory. Use this when invoking install.ps1 from a different location
    (e.g. running a cached copy from $env:TEMP) and you want the rules
    written into a specific project folder.

.EXAMPLE
    .\install.ps1 init -Tools cursor,claude-code -NonInteractive

.EXAMPLE
    .\install.ps1 update -AssumeYes

.EXAMPLE
    & "$env:TEMP\install.ps1" init -ProjectRoot "C:\Work\MyProject" -Source "$env:TEMP\1c-rules" -AssumeYes

.EXAMPLE
    .\install.ps1 init -Source https://github.com/comol/ai_rules_1c -AssumeYes

.NOTES
    Target: Windows PowerShell 5.1+ (compatible with PowerShell 7+).
    Protocol version: 1.0. See AGENT-INSTALL.md for the specification.
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('init', 'update', 'add', 'remove', 'doctor', 'eject')]
    [string]$Command = 'init',

    [Parameter(Position = 1)]
    [string]$Tool,

    [string[]]$Tools,
    [string]$Source,
    [string]$ProjectRoot,
    [switch]$NonInteractive,
    [switch]$AssumeYes
)

# ============================================================================
# CONSTANTS
# ============================================================================

$script:ProtocolVersion = '1.0'
$script:ManifestFileName = '.ai-rules.json'
$script:AgentsMdFileName = 'AGENTS.md'
$script:UserRulesFileName = 'USER-RULES.md'
$script:MemoryFileName = 'memory.md'
$script:DevEnvFileName = '.dev.env'
$script:DevEnvExampleName = '.dev.env.example'
$script:SupportedTools = @('cursor', 'claude-code', 'codex', 'opencode', 'kilocode', 'other')
$script:ManagedBlocks = @('core', 'user-defined', 'openspec')
$script:LastChannel = 'powershell'
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding $false

# ============================================================================
# SECTION 1: LOGGING AND USER INPUT
# ============================================================================

function Write-Info {
    param([string]$Message)
    Write-Host $Message
}

function Write-Warn {
    param([string]$Message)
    Write-Host "WARN: $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

function Write-Section {
    param([string]$Title)
    Write-Host ''
    Write-Host "== $Title ==" -ForegroundColor Cyan
}

function Read-YesNo {
    param(
        [string]$Prompt,
        [bool]$Default = $true
    )
    if ($NonInteractive -or $AssumeYes) { return $true }
    $suffix = if ($Default) { '[Y/n]' } else { '[y/N]' }
    $ans = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($ans)) { return $Default }
    return ($ans -match '^[Yy]')
}

function Read-Choice {
    param(
        [string]$Prompt,
        [string[]]$Options,
        [string]$Default
    )
    if ($NonInteractive) { return $Default }
    $optsText = ($Options | ForEach-Object { if ($_ -eq $Default) { "[$_]" } else { $_ } }) -join '/'
    $ans = Read-Host "$Prompt ($optsText)"
    if ([string]::IsNullOrWhiteSpace($ans)) { return $Default }
    $match = $Options | Where-Object { $_ -like "${ans}*" } | Select-Object -First 1
    if ($match) { return $match }
    return $Default
}

# ============================================================================
# SECTION 2: FILE IO WITH ENCODING CONTROL
# ============================================================================

function Read-TextFile {
    param([string]$Path)
    return [System.IO.File]::ReadAllText((Resolve-Path $Path).Path)
}

function Write-TextFile {
    param(
        [string]$Path,
        [string]$Content
    )
    $full = [System.IO.Path]::GetFullPath($Path)
    $dir = [System.IO.Path]::GetDirectoryName($full)
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    [System.IO.File]::WriteAllText($full, $Content, $script:Utf8NoBom)
}

function Get-FileSha256 {
    param([string]$Path)
    return (Get-FileHash -Path $Path -Algorithm SHA256).Hash.ToLower()
}

function Get-StringSha256 {
    param([string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $hash = $sha.ComputeHash($bytes)
    $sha.Dispose()
    return (($hash | ForEach-Object { $_.ToString('x2') }) -join '')
}

# ============================================================================
# SECTION 3: YAML PARSING (frontmatter + adapter subset)
# ============================================================================

# Parse a flat YAML frontmatter block. Supports scalars, quoted strings,
# booleans, flow arrays [a, b]. No nesting.
function ConvertFrom-FrontmatterYaml {
    param([string]$Text)

    $result = [ordered]@{}
    foreach ($rawLine in ($Text -split "`r?`n")) {
        $line = $rawLine -replace '\s+$', ''
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -match '^\s*#') { continue }
        if ($line -notmatch '^([\w-]+)\s*:\s*(.*)$') { continue }
        $key = $Matches[1]
        $val = $Matches[2]
        $result[$key] = ConvertFrom-ScalarOrArray $val
    }
    return $result
}

function ConvertFrom-ScalarOrArray {
    param([string]$Raw)
    $trim = $Raw.Trim()
    if ($trim -eq '') { return '' }
    if ($trim -match '^\[(.*)\]$') {
        $inside = $Matches[1]
        if ($inside.Trim() -eq '') { return @() }
        $items = $inside -split ','
        return @($items | ForEach-Object { ConvertFrom-Scalar ($_.Trim()) })
    }
    return (ConvertFrom-Scalar $trim)
}

function ConvertFrom-Scalar {
    param([string]$Raw)
    if ($Raw.Length -eq 0) { return '' }
    $c = $Raw[0]
    if ($c -eq '"' -and $Raw.EndsWith('"')) {
        $inner = $Raw.Substring(1, $Raw.Length - 2)
        return $inner -replace '\\"', '"'
    }
    if ($c -eq "'" -and $Raw.EndsWith("'")) {
        return $Raw.Substring(1, $Raw.Length - 2)
    }
    if ($Raw -eq 'true') { return $true }
    if ($Raw -eq 'false') { return $false }
    if ($Raw -eq 'null' -or $Raw -eq '~') { return $null }
    if ($Raw -match '^-?\d+$') { return [int]$Raw }
    return $Raw
}

# Parse an adapter YAML file. Supports:
#   - Scalars (string, int, bool)
#   - Flow arrays [a, b]
#   - Flow dicts { k: v, k2: v2 }
#   - Block-style nested dicts via indentation
#   - Block literal (|) for multi-line strings
#   - Comments (# to end of line, but not inside quoted strings)
function ConvertFrom-AdapterYaml {
    param([string]$Path)

    $text = Read-TextFile $Path
    $allLines = $text -split "`r?`n"
    # Strip end-of-line comments but preserve content lines.
    $lines = @()
    foreach ($ln in $allLines) {
        $stripped = $ln
        # Remove comments only if the # is not inside quotes
        $inS = $false; $inD = $false; $cutAt = -1
        for ($i = 0; $i -lt $stripped.Length; $i++) {
            $ch = $stripped[$i]
            if (-not $inD -and $ch -eq "'") { $inS = -not $inS }
            elseif (-not $inS -and $ch -eq '"') { $inD = -not $inD }
            elseif (-not $inS -and -not $inD -and $ch -eq '#') { $cutAt = $i; break }
        }
        if ($cutAt -ge 0) { $stripped = $stripped.Substring(0, $cutAt) }
        $lines += $stripped.TrimEnd()
    }

    $parser = [PSCustomObject]@{ Lines = $lines; Index = 0 }
    return Invoke-YamlBlock -Parser $parser -BaseIndent 0
}

function Get-YamlIndent {
    param([string]$Line)
    if ($Line -match '^(\s*)') { return $Matches[1].Length }
    return 0
}

function Test-YamlBlank {
    param([string]$Line)
    return [string]::IsNullOrWhiteSpace($Line)
}

# Parse a YAML block (dict) starting at Parser.Index with BaseIndent.
# Returns an ordered hashtable.
function Invoke-YamlBlock {
    param(
        [Parameter(Mandatory)][PSCustomObject]$Parser,
        [Parameter(Mandatory)][int]$BaseIndent
    )
    $result = [ordered]@{}
    while ($Parser.Index -lt $Parser.Lines.Count) {
        $line = $Parser.Lines[$Parser.Index]
        if (Test-YamlBlank $line) { $Parser.Index++; continue }
        $indent = Get-YamlIndent $line
        if ($indent -lt $BaseIndent) { break }
        if ($indent -gt $BaseIndent) {
            throw "YAML parse error at line $($Parser.Index + 1): unexpected indent (expected $BaseIndent, got $indent)"
        }
        $trim = $line.Trim()
        # Dict entries look like "key:" or "key: value"
        if ($trim -notmatch '^("([^"]+)"|[\w!-][\w-]*)\s*:\s*(.*)$') {
            throw "YAML parse error at line $($Parser.Index + 1): expected key-value, got '$trim'"
        }
        $rawKey = $Matches[1]
        $quotedKey = $Matches[2]
        $rawVal = $Matches[3]
        $key = if ($quotedKey) { $quotedKey } else { $rawKey }
        $Parser.Index++

        if ($rawVal -eq '|') {
            # Block literal: collect indented lines
            $blockLines = @()
            $blockIndent = -1
            while ($Parser.Index -lt $Parser.Lines.Count) {
                $l = $Parser.Lines[$Parser.Index]
                if (Test-YamlBlank $l) { $blockLines += ''; $Parser.Index++; continue }
                $li = Get-YamlIndent $l
                if ($li -le $BaseIndent) { break }
                if ($blockIndent -lt 0) { $blockIndent = $li }
                if ($li -lt $blockIndent) { break }
                $blockLines += $l.Substring($blockIndent)
                $Parser.Index++
            }
            # Trim trailing empty lines
            while ($blockLines.Count -gt 0 -and $blockLines[-1] -eq '') {
                $blockLines = $blockLines[0..($blockLines.Count - 2)]
            }
            $result[$key] = ($blockLines -join "`n") + "`n"
        }
        elseif ($rawVal -eq '') {
            # Nested block — could be dict or array
            if ($Parser.Index -lt $Parser.Lines.Count) {
                $next = $Parser.Lines[$Parser.Index]
                $nextIndent = Get-YamlIndent $next
                $nextTrim = $next.Trim()
                if ($nextTrim.StartsWith('- ') -or $nextTrim -eq '-') {
                    $result[$key] = Invoke-YamlBlockArray -Parser $Parser -BaseIndent $nextIndent
                }
                elseif ($nextIndent -gt $BaseIndent) {
                    $result[$key] = Invoke-YamlBlock -Parser $Parser -BaseIndent $nextIndent
                }
                else {
                    $result[$key] = $null
                }
            }
            else {
                $result[$key] = $null
            }
        }
        else {
            $result[$key] = ConvertFrom-YamlInlineValue $rawVal
        }
    }
    return $result
}

# Parse a block-style array at BaseIndent (each line starts with "- ").
function Invoke-YamlBlockArray {
    param(
        [Parameter(Mandatory)][PSCustomObject]$Parser,
        [Parameter(Mandatory)][int]$BaseIndent
    )
    $items = @()
    while ($Parser.Index -lt $Parser.Lines.Count) {
        $line = $Parser.Lines[$Parser.Index]
        if (Test-YamlBlank $line) { $Parser.Index++; continue }
        $indent = Get-YamlIndent $line
        if ($indent -lt $BaseIndent) { break }
        if ($indent -gt $BaseIndent) {
            throw "YAML parse error at line $($Parser.Index + 1): unexpected indent in array"
        }
        $trim = $line.Trim()
        if ($trim -notmatch '^-\s*(.*)$') { break }
        $rest = $Matches[1]
        $Parser.Index++
        if ([string]::IsNullOrWhiteSpace($rest)) {
            # Nested dict item
            if ($Parser.Index -lt $Parser.Lines.Count) {
                $next = $Parser.Lines[$Parser.Index]
                $nextIndent = Get-YamlIndent $next
                $items += (Invoke-YamlBlock -Parser $Parser -BaseIndent $nextIndent)
            }
        }
        elseif ($rest -match '^([\w-]+)\s*:\s*(.*)$') {
            # Inline dict with single key on the - line; possibly followed by more keys
            # We support single-line flow for simplicity:
            #   - exists: ".cursor/"
            $dict = [ordered]@{}
            $dict[$Matches[1]] = ConvertFrom-YamlInlineValue $Matches[2]
            $items += $dict
        }
        else {
            $items += (ConvertFrom-YamlInlineValue $rest)
        }
    }
    return , $items
}

# Parse an inline YAML value: scalar, flow array, flow dict.
function ConvertFrom-YamlInlineValue {
    param([string]$Raw)
    $trim = $Raw.Trim()
    if ($trim -eq '') { return '' }
    if ($trim -match '^\{(.*)\}$') {
        $inside = $Matches[1].Trim()
        if ($inside -eq '') { return [ordered]@{} }
        $dict = [ordered]@{}
        $parts = Split-YamlFlow $inside
        foreach ($p in $parts) {
            if ($p -match '^("([^"]+)"|[\w!-][\w-]*)\s*:\s*(.*)$') {
                $k = if ($Matches[2]) { $Matches[2] } else { $Matches[1] }
                $dict[$k] = ConvertFrom-YamlInlineValue $Matches[3]
            }
        }
        return $dict
    }
    if ($trim -match '^\[(.*)\]$') {
        $inside = $Matches[1].Trim()
        if ($inside -eq '') { return , @() }
        $items = Split-YamlFlow $inside
        return , ($items | ForEach-Object { ConvertFrom-YamlInlineValue $_ })
    }
    return (ConvertFrom-Scalar $trim)
}

# Split a flow-style inner (e.g. "a, b, { k: v }, [x, y]") on commas that
# are not inside brackets, braces, or quotes.
function Split-YamlFlow {
    param([string]$Raw)
    $parts = @()
    $buf = ''
    $depthB = 0; $depthC = 0; $inD = $false; $inS = $false
    for ($i = 0; $i -lt $Raw.Length; $i++) {
        $ch = $Raw[$i]
        if (-not $inD -and $ch -eq "'") { $inS = -not $inS; $buf += $ch; continue }
        if (-not $inS -and $ch -eq '"') { $inD = -not $inD; $buf += $ch; continue }
        if ($inS -or $inD) { $buf += $ch; continue }
        switch ($ch) {
            '[' { $depthB++; $buf += $ch; continue }
            ']' { $depthB--; $buf += $ch; continue }
            '{' { $depthC++; $buf += $ch; continue }
            '}' { $depthC--; $buf += $ch; continue }
            ',' {
                if ($depthB -eq 0 -and $depthC -eq 0) {
                    $parts += $buf.Trim(); $buf = ''; continue
                }
                else { $buf += $ch; continue }
            }
            default { $buf += $ch }
        }
    }
    if ($buf.Trim() -ne '') { $parts += $buf.Trim() }
    return $parts
}

# ============================================================================
# SECTION 4: FRONTMATTER EXTRACTION AND SERIALIZATION
# ============================================================================

function Split-FrontmatterAndBody {
    param([string]$Text)
    $lines = $Text -split "`r?`n"
    if ($lines.Count -lt 2 -or $lines[0] -ne '---') {
        return @{ Frontmatter = $null; Body = $Text }
    }
    $closer = -1
    for ($i = 1; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -eq '---') { $closer = $i; break }
    }
    if ($closer -lt 0) {
        return @{ Frontmatter = $null; Body = $Text }
    }
    $fmText = ($lines[1..($closer - 1)] -join "`n")
    $bodyText = ($lines[($closer + 1)..($lines.Count - 1)] -join "`n")
    $fm = ConvertFrom-FrontmatterYaml $fmText
    return @{ Frontmatter = $fm; Body = $bodyText }
}

function Format-Frontmatter {
    param([System.Collections.IDictionary]$Fm)
    if ($null -eq $Fm -or $Fm.Keys.Count -eq 0) { return '' }
    $lines = @('---')
    foreach ($k in $Fm.Keys) {
        $v = $Fm[$k]
        $lines += (Format-FrontmatterEntry $k $v)
    }
    $lines += '---'
    return ($lines -join "`n")
}

function Format-FrontmatterEntry {
    param(
        [string]$Key,
        $Value
    )
    if ($null -eq $Value) { return "${Key}:" }
    if ($Value -is [bool]) {
        $s = if ($Value) { 'true' } else { 'false' }
        return "${Key}: $s"
    }
    if ($Value -is [int]) { return "${Key}: $Value" }
    if ($Value -is [array]) {
        $items = @($Value | ForEach-Object { Format-FrontmatterInlineString $_ })
        return "${Key}: [$(($items -join ', '))]"
    }
    if ($Value -is [string]) {
        return "${Key}: " + (Format-FrontmatterStringValue $Value)
    }
    return "${Key}: " + $Value.ToString()
}

function Format-FrontmatterInlineString {
    param([string]$S)
    if ($S -match '[,\[\]"'':]') {
        return '"' + ($S -replace '"', '\"') + '"'
    }
    return '"' + $S + '"'
}

function Format-FrontmatterStringValue {
    param([string]$S)
    if ($S -match '^[\w./\-]+$' -and -not ($S -match '^(true|false|null|~)$')) {
        return $S
    }
    return '"' + ($S -replace '"', '\"') + '"'
}

# ============================================================================
# SECTION 5: FRONTMATTER OPERATIONS
# ============================================================================

function Invoke-FrontmatterOps {
    param(
        [System.Collections.IDictionary]$Source,
        $Ops
    )
    $src = [ordered]@{}
    if ($Source) { foreach ($k in $Source.Keys) { $src[$k] = $Source[$k] } }

    if ($null -eq $Ops) { return $src }

    $keep = if ($Ops.keep) { @($Ops.keep) } else { @() }
    $drop = if ($Ops.drop) { @($Ops.drop) } else { @() }
    $rename = if ($Ops.rename) { $Ops.rename } else { @{} }
    $addIf = if ($Ops.addIf) { $Ops.addIf } else { @{} }

    # Phase 1: keep/drop filtering
    if ($keep.Count -gt 0) {
        $filtered = [ordered]@{}
        foreach ($k in $src.Keys) {
            if ($keep -contains $k) { $filtered[$k] = $src[$k] }
        }
        $src = $filtered
    }
    elseif ($drop.Count -gt 0) {
        $filtered = [ordered]@{}
        foreach ($k in $src.Keys) {
            if (-not ($drop -contains $k)) { $filtered[$k] = $src[$k] }
        }
        $src = $filtered
    }

    # Phase 2: rename
    if ($rename -and $rename.Keys.Count -gt 0) {
        $renamed = [ordered]@{}
        foreach ($k in $src.Keys) {
            $newName = if ($rename.Contains($k)) { $rename[$k] } else { $k }
            $renamed[$newName] = $src[$k]
        }
        $src = $renamed
    }

    # Phase 3: addIf — add fields conditionally
    if ($addIf -and $addIf.Keys.Count -gt 0) {
        foreach ($cond in $addIf.Keys) {
            $negated = $cond.StartsWith('!')
            $field = if ($negated) { $cond.Substring(1) } else { $cond }
            $hasField = $Source.Contains($field)
            $truthy = $hasField -and $Source[$field]
            $shouldAdd = if ($negated) { -not $truthy } else { $truthy }
            if ($shouldAdd) {
                $toAdd = $addIf[$cond]
                if ($toAdd -is [System.Collections.IDictionary]) {
                    foreach ($k in $toAdd.Keys) { $src[$k] = $toAdd[$k] }
                }
            }
        }
    }
    return $src
}

# ============================================================================
# SECTION 6: TOML RENDERING (for Codex rebuild-toml and MCP config)
# ============================================================================

function Format-TomlString {
    param([string]$Value)
    # Simple TOML string escape: quotes and backslashes
    $s = $Value -replace '\\', '\\\\' -replace '"', '\"'
    return '"' + $s + '"'
}

function Format-TomlArray {
    param([array]$Values)
    $items = @($Values | ForEach-Object { Format-TomlString $_ })
    return '[' + ($items -join ', ') + ']'
}

function Invoke-CodexAgentTemplate {
    param(
        [string]$Template,
        [System.Collections.IDictionary]$Fm,
        [string]$Body
    )
    $outLines = @()
    foreach ($line in ($Template -split "`n")) {
        # Find placeholders {field}
        $placeholders = [regex]::Matches($line, '\{([\w-]+)\}')
        $hasMissing = $false
        $rendered = $line
        $placeholderKeys = @()
        foreach ($m in $placeholders) {
            $k = $m.Groups[1].Value
            if ($k -eq 'body') { continue }
            $placeholderKeys += $k
            if (-not $Fm.Contains($k) -or [string]::IsNullOrEmpty([string]$Fm[$k])) {
                $hasMissing = $true
                break
            }
        }
        if ($hasMissing) { continue }

        foreach ($k in $placeholderKeys) {
            $v = $Fm[$k]
            $rendered = $rendered -replace ('\{' + [regex]::Escape($k) + '\}'), ($v -replace '\$', '$$$$')
        }
        if ($rendered -match '\{body\}') {
            $rendered = $rendered -replace '\{body\}', ($Body -replace '\$', '$$$$')
        }
        $outLines += $rendered
    }
    return ($outLines -join "`n")
}

# ============================================================================
# SECTION 7: MCP CONFIG RENDERERS
# ============================================================================

function Read-McpServers {
    param([string]$Root)
    $path = Join-Path $Root 'content/mcp-servers.json'
    if (-not (Test-Path $path)) {
        throw "MCP servers list not found: $path"
    }
    $json = Read-TextFile $path
    $obj = $json | ConvertFrom-Json
    return $obj.servers
}

function ConvertTo-McpServersJsonDict {
    param([array]$Servers)
    $dict = [ordered]@{}
    foreach ($s in $Servers) {
        $entry = [ordered]@{}
        if ($s.url) { $entry['url'] = $s.url }
        if ($s.connectionId) { $entry['connection_id'] = $s.connectionId }
        if ($s.description) { $entry['description'] = $s.description }
        if ($s.command) { $entry['command'] = $s.command }
        if ($s.args) { $entry['args'] = $s.args }
        if ($s.env) { $entry['env'] = $s.env }
        $dict[$s.id] = $entry
    }
    return $dict
}

function New-McpConfig-Cursor {
    param([array]$Servers)
    $root = [ordered]@{ mcpServers = (ConvertTo-McpServersJsonDict $Servers) }
    return (ConvertTo-Json $root -Depth 10)
}

function New-McpConfig-ClaudeCode {
    param([array]$Servers)
    return New-McpConfig-Cursor $Servers
}

function New-McpConfig-Kilocode {
    param([array]$Servers)
    return New-McpConfig-Cursor $Servers
}

function New-McpConfig-OpenCode {
    param([array]$Servers)
    $mcp = [ordered]@{}
    foreach ($s in $Servers) {
        $entry = [ordered]@{}
        if ($s.url) {
            $entry['type'] = 'remote'
            $entry['url'] = $s.url
        }
        elseif ($s.command) {
            $entry['type'] = 'local'
            $cmd = @($s.command) + @($s.args)
            $entry['command'] = $cmd
        }
        if ($s.description) { $entry['description'] = $s.description }
        $mcp[$s.id] = $entry
    }
    $root = [ordered]@{ mcp = $mcp }
    return (ConvertTo-Json $root -Depth 10)
}

function New-McpConfig-Codex {
    param([array]$Servers)
    $lines = @('# MCP server configuration for Codex CLI')
    $lines += '# Generated by 1c-rules installer'
    $lines += ''
    foreach ($s in $Servers) {
        $lines += "[mcp_servers.`"$($s.id)`"]"
        if ($s.url) { $lines += 'url = ' + (Format-TomlString $s.url) }
        if ($s.connectionId) { $lines += 'connection_id = ' + (Format-TomlString $s.connectionId) }
        if ($s.description) { $lines += 'description = ' + (Format-TomlString $s.description) }
        if ($s.command) {
            $lines += 'command = ' + (Format-TomlString $s.command)
            if ($s.args) { $lines += 'args = ' + (Format-TomlArray $s.args) }
        }
        $lines += ''
    }
    return ($lines -join "`n")
}

function New-McpConfig {
    param(
        [string]$ToolId,
        [array]$Servers
    )
    switch ($ToolId) {
        'cursor' { return (New-McpConfig-Cursor $Servers) }
        'claude-code' { return (New-McpConfig-ClaudeCode $Servers) }
        'codex' { return (New-McpConfig-Codex $Servers) }
        'opencode' { return (New-McpConfig-OpenCode $Servers) }
        'kilocode' { return (New-McpConfig-Kilocode $Servers) }
        default { throw "Unknown tool id: $ToolId" }
    }
}

# ============================================================================
# SECTION 8: MANIFEST
# ============================================================================

function New-Manifest {
    param(
        [string]$Source,
        [string]$Version
    )
    $ts = [datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $m = [ordered]@{
        protocol      = $script:ProtocolVersion
        source        = $Source
        version       = $Version
        installedAt   = $ts
        updatedAt     = $ts
        lastChannel   = $script:LastChannel
        tools         = @()
        language      = 'en'
        mcpServers    = @()
        files         = [ordered]@{}
        foreignFiles  = [ordered]@{}
        integrations  = [ordered]@{}
    }
    return $m
}

function Read-Manifest {
    param([string]$Root)
    $path = Join-Path $Root $script:ManifestFileName
    if (-not (Test-Path $path)) { return $null }
    $json = Read-TextFile $path
    $obj = $json | ConvertFrom-Json
    return (ConvertTo-OrderedHashtable $obj)
}

function Write-Manifest {
    param(
        [string]$Root,
        [System.Collections.IDictionary]$Manifest
    )
    $path = Join-Path $Root $script:ManifestFileName
    $json = ConvertTo-Json $Manifest -Depth 15
    Write-TextFile -Path $path -Content ($json + "`n")
}

function ConvertTo-OrderedHashtable {
    param($Obj)
    if ($null -eq $Obj) { return $null }
    # Primitives: return as-is. Check BEFORE IEnumerable because strings are IEnumerable in .NET.
    if ($Obj -is [string] -or $Obj -is [bool] -or $Obj -is [int] -or $Obj -is [long] -or $Obj -is [double] -or $Obj -is [datetime]) {
        return $Obj
    }
    if ($Obj -is [System.Collections.IDictionary]) {
        $h = [ordered]@{}
        foreach ($k in $Obj.Keys) { $h[$k] = ConvertTo-OrderedHashtable $Obj[$k] }
        return $h
    }
    if ($Obj -is [PSCustomObject]) {
        $h = [ordered]@{}
        foreach ($p in $Obj.PSObject.Properties) { $h[$p.Name] = ConvertTo-OrderedHashtable $p.Value }
        return $h
    }
    if ($Obj -is [array] -or $Obj -is [System.Collections.IList]) {
        $list = New-Object System.Collections.ArrayList
        foreach ($item in $Obj) { [void]$list.Add((ConvertTo-OrderedHashtable $item)) }
        return , ($list.ToArray())
    }
    return $Obj
}

# ============================================================================
# SECTION 9: DETECTION AND SCANNING
# ============================================================================

function Get-ToolDetectionSignals {
    param([string]$Root)
    $signals = @{
        'cursor'      = @((Test-Path (Join-Path $Root '.cursor')))
        'claude-code' = @((Test-Path (Join-Path $Root '.claude')), (Test-Path (Join-Path $Root 'CLAUDE.md')))
        'codex'       = @((Test-Path (Join-Path $Root '.codex')))
        'opencode'    = @((Test-Path (Join-Path $Root '.opencode')), (Test-Path (Join-Path $Root 'opencode.json')))
        'kilocode'    = @((Test-Path (Join-Path $Root '.kilo')), (Test-Path (Join-Path $Root '.kilocode')))
        # 'other' is a manual-only fallback — never auto-detected.
        'other'       = @()
    }
    $detected = @()
    foreach ($t in $script:SupportedTools) {
        if ($signals[$t] -contains $true) { $detected += $t }
    }
    return $detected
}

function Invoke-Detection {
    param(
        [string]$Root,
        [string[]]$RequestedTools
    )
    $detected = Get-ToolDetectionSignals $Root
    if ($RequestedTools -and $RequestedTools.Count -gt 0) {
        $invalid = $RequestedTools | Where-Object { $_ -notin $script:SupportedTools }
        if ($invalid) {
            throw "Unknown tool id(s): $($invalid -join ', '). Supported: $($script:SupportedTools -join ', ')"
        }
        return $RequestedTools
    }
    # Auto-silent semantics:
    #   - exactly 1 detected -> proceed without prompting (single common case)
    #   - 0 detected         -> ask once (or throw in NonInteractive)
    #   - 2+ detected        -> ask once to confirm/edit (or accept all in NonInteractive)
    $detectedArr = @($detected)
    if ($detectedArr.Count -eq 1) {
        Write-Info ("Detected tool: " + $detectedArr[0] + " (auto-selected)")
        return $detectedArr
    }
    if ($detectedArr.Count -eq 0) {
        if ($NonInteractive) {
            throw 'No tools detected and no -Tools provided. Refusing to guess in non-interactive mode.'
        }
        Write-Info 'No AI tool directories detected in this project.'
        Write-Info "Supported tools: $($script:SupportedTools -join ', ')"
        $ans = Read-Host 'Enter comma-separated tool ids to install for'
        $list = @($ans -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        if ($list.Count -eq 0) { throw 'No tools selected; aborting.' }
        return $list
    }
    Write-Info ("Detected tools: " + ($detectedArr -join ', '))
    if ($NonInteractive -or $AssumeYes) { return $detectedArr }
    $ans = Read-Host "Press Enter to accept all, or enter comma-separated subset"
    if ([string]::IsNullOrWhiteSpace($ans)) { return $detectedArr }
    $list = @($ans -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($list.Count -eq 0) { return $detectedArr }
    return $list
}

function Get-AdapterTargetDirs {
    param([System.Collections.IDictionary]$Adapter)
    $dirs = @()
    foreach ($section in @('rules', 'agents', 'commands', 'skills')) {
        if (-not $Adapter.Contains($section)) { continue }
        $s = $Adapter[$section]
        if ($s.copyTo) {
            $tpl = [string]$s.copyTo
            $tpl = $tpl -replace '\{name\}.*$', ''
            $tpl = $tpl.TrimEnd('/', '\')
            if ($tpl) { $dirs += $tpl }
        }
    }
    return ($dirs | Sort-Object -Unique)
}

function Invoke-ScanForeign {
    param(
        [string]$Root,
        [string[]]$ActiveTools,
        [System.Collections.IDictionary]$Manifest,
        [hashtable]$Adapters
    )
    $result = [ordered]@{}
    $managedFiles = @{}
    if ($Manifest -and $Manifest.files) {
        foreach ($k in $Manifest.files.Keys) { $managedFiles[$k] = $true }
    }
    $rootFull = (Resolve-Path $Root).Path.TrimEnd('\', '/')
    foreach ($tool in $ActiveTools) {
        $adapter = $Adapters[$tool]
        if (-not $adapter) { continue }
        $dirs = Get-AdapterTargetDirs $adapter
        $foreign = @()
        foreach ($d in $dirs) {
            $abs = Join-Path $Root $d
            if (-not (Test-Path $abs)) { continue }
            $files = Get-ChildItem -Recurse -File -Path $abs -ErrorAction SilentlyContinue
            foreach ($f in $files) {
                $rel = $f.FullName.Substring($rootFull.Length + 1).Replace('\', '/')
                if (-not $managedFiles.ContainsKey($rel)) { $foreign += $rel }
            }
        }
        $result[$tool] = @($foreign | Sort-Object -Unique)
    }
    return $result
}

function Invoke-ScanIntegrations {
    param([string]$Root)
    $result = [ordered]@{}
    $rootFull = (Resolve-Path $Root).Path.TrimEnd('\', '/')
    $specsDir = Join-Path $Root 'openspec/specs'
    $changesDir = Join-Path $Root 'openspec/changes'
    if ((Test-Path $specsDir) -or (Test-Path $changesDir)) {
        $files = @()
        foreach ($d in @($specsDir, $changesDir)) {
            if (Test-Path $d) {
                Get-ChildItem -Recurse -File -Path $d -Filter *.md -ErrorAction SilentlyContinue | ForEach-Object {
                    $files += $_.FullName.Substring($rootFull.Length + 1).Replace('\', '/')
                }
            }
        }
        $result['openspec'] = [ordered]@{
            detected = $true
            files    = @($files | Sort-Object -Unique)
        }
    }
    return $result
}

# Scaffold the OpenSpec workspace (`openspec/`) into the project root from the
# source repository. Always runs as part of installation regardless of active
# tools — OpenSpec lives at the project root and is tool-agnostic. The copy is
# strict skip-if-exists per file: existing user content (specs, change
# proposals, customised README/config) is never overwritten. Scaffolded files
# are NOT added to `manifest.files` so future updates do not try to refresh
# them after the user has filled them with content; the installer only flips
# `manifest.integrations.openspec.scaffolded = true`.
function Invoke-OpenSpecScaffold {
    param(
        [string]$Root,
        [string]$SourceRoot,
        [System.Collections.IDictionary]$Manifest
    )
    $sourceOpenSpec = Join-Path $SourceRoot 'openspec'
    if (-not (Test-Path $sourceOpenSpec)) {
        Write-Warn "OpenSpec scaffold: source folder not found at $sourceOpenSpec — skipped."
        return
    }

    $sourceFull = (Resolve-Path $sourceOpenSpec).Path.TrimEnd('\', '/')
    $copied = 0
    $skipped = 0
    Get-ChildItem -Recurse -File -Path $sourceOpenSpec -ErrorAction SilentlyContinue | ForEach-Object {
        $rel = $_.FullName.Substring($sourceFull.Length + 1).Replace('\', '/')
        $targetRel = "openspec/$rel"
        $targetAbs = Join-Path $Root $targetRel
        if (Test-Path $targetAbs) {
            $skipped++
            return
        }
        $targetDir = Split-Path -Parent $targetAbs
        if ($targetDir -and -not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
        }
        Copy-Item -Path $_.FullName -Destination $targetAbs -Force
        $copied++
    }

    if (-not $Manifest.integrations) { $Manifest.integrations = [ordered]@{} }
    if (-not $Manifest.integrations.Contains('openspec')) {
        $Manifest.integrations['openspec'] = [ordered]@{ detected = $true; files = @() }
    }
    $Manifest.integrations['openspec']['scaffolded'] = $true
    $Manifest.integrations['openspec']['detected'] = $true

    Write-Info "  OpenSpec scaffold: $copied file(s) copied, $skipped preserved"
}

# Place OpenSpec artefacts (slash commands / workflows + SKILLs) bundled under
# `content/openspec-bundle/<tool>/...`. Each file under a tool's bundle is
# copied verbatim to the same relative path in the project root, so the
# resulting layout exactly matches what `openspec init` would produce — but
# without requiring npm or the OpenSpec CLI at install time.
#
# Files are tracked in `manifest.files` like any other managed content, so
# `update` refreshes them, `remove` deletes them, and `userModified` is
# honoured. The OpenSpec CLI version of the snapshot is recorded in
# `manifest.integrations.openspec.artifactsBundleVersion` for diagnostics.
function Invoke-OpenSpecArtifacts {
    param(
        [string]$Root,
        [string]$SourceRoot,
        [string[]]$ActiveTools,
        [System.Collections.IDictionary]$Manifest
    )
    $bundleRoot = Join-Path $SourceRoot 'content/openspec-bundle'
    if (-not (Test-Path $bundleRoot)) {
        Write-Warn "OpenSpec artefacts: bundle not found at $bundleRoot — skipped."
        return
    }

    $bundleVersion = ''
    $verFile = Join-Path $bundleRoot 'version.txt'
    if (Test-Path $verFile) {
        $bundleVersion = ((Get-Content -Raw -Path $verFile) -replace '\s+$', '').Trim()
    }

    $totalCopied = 0
    $totalKept = 0
    foreach ($tool in $ActiveTools) {
        $toolBundle = Join-Path $bundleRoot $tool
        if (-not (Test-Path $toolBundle)) { continue }
        $toolBundleFull = (Resolve-Path $toolBundle).Path.TrimEnd('\', '/')
        $toolCopied = 0
        $toolKept = 0
        Get-ChildItem -Recurse -File -Path $toolBundle -ErrorAction SilentlyContinue | ForEach-Object {
            $rel = $_.FullName.Substring($toolBundleFull.Length + 1).Replace('\', '/')
            if ($Manifest.files.Contains($rel)) {
                $existing = $Manifest.files[$rel]
                if ($existing -and $existing.userModified) {
                    $toolKept++
                    return
                }
            }
            $absTarget = Join-Path $Root $rel
            $parentDir = Split-Path -Parent $absTarget
            if ($parentDir -and -not (Test-Path $parentDir)) {
                New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
            }
            Copy-Item -Path $_.FullName -Destination $absTarget -Force
            $Manifest.files[$rel] = [ordered]@{
                source        = "content/openspec-bundle/$tool/$rel"
                installedHash = (Get-FileSha256 $absTarget)
            }
            $toolCopied++
        }
        if ($toolCopied -gt 0 -or $toolKept -gt 0) {
            $msg = "  [$tool] OpenSpec artefacts: $toolCopied placed"
            if ($toolKept -gt 0) { $msg += ", $toolKept kept (userModified)" }
            Write-Info $msg
        }
        $totalCopied += $toolCopied
        $totalKept += $toolKept
    }

    if (-not $Manifest.integrations) { $Manifest.integrations = [ordered]@{} }
    if (-not $Manifest.integrations.Contains('openspec')) {
        $Manifest.integrations['openspec'] = [ordered]@{ detected = $false; files = @() }
    }
    if ($bundleVersion) {
        $Manifest.integrations['openspec']['artifactsBundleVersion'] = $bundleVersion
    }
    Write-Info "  OpenSpec artefacts: $totalCopied placed, $totalKept kept (bundle v$bundleVersion)"
}

# ============================================================================
# SECTION 9b: 1C PROJECT DETECTION + openspec/project.md GENERATOR
# ============================================================================
#
# Inspects the project root for 1C metadata signals (Configuration.xml,
# CommonModules/СтандартныеПодсистемыСервер, top-level subsystems, kind
# subdirectories) and renders a Russian-language openspec/project.md.
#
# The file is tracked in manifest.files like any other managed content,
# so update refreshes it when the source 1C metadata changes, but a
# user-edited project.md is preserved (userModified flag, identical to
# the rest of the place phase).

function Get-1cFieldValue {
    # Single-line tag extractor for the simple, regular 1C XML format.
    # Handles `<Tag>value</Tag>` and `<Tag />` (empty); ignores attributes.
    param(
        [string]$Xml,
        [string]$Tag
    )
    if (-not $Xml) { return '' }
    $pattern = '<' + [regex]::Escape($Tag) + '\s*(?:/>|>([^<]*)</' + [regex]::Escape($Tag) + '>)'
    $m = [regex]::Match($Xml, $pattern)
    if ($m.Success) {
        $val = $m.Groups[1].Value
        return $val.Trim()
    }
    return ''
}

function Get-1cSynonymRu {
    # Pulls the Russian synonym (v8:item with v8:lang=ru) from a Synonym block.
    param([string]$Xml)
    if (-not $Xml) { return '' }
    $synBlock = [regex]::Match($Xml, '(?s)<Synonym>(.*?)</Synonym>')
    if (-not $synBlock.Success) { return '' }
    $items = [regex]::Matches($synBlock.Groups[1].Value,
        '(?s)<v8:item>\s*<v8:lang>([^<]+)</v8:lang>\s*<v8:content>([^<]*)</v8:content>\s*</v8:item>')
    foreach ($it in $items) {
        if ($it.Groups[1].Value.Trim() -eq 'ru') { return $it.Groups[2].Value.Trim() }
    }
    if ($items.Count -gt 0) { return $items[0].Groups[2].Value.Trim() }
    return ''
}

function Get-1cProjectInfo {
    param([string]$Root)

    $info = [ordered]@{
        Detected        = $false
        ConfigPath      = ''
        IsExtension     = $false
        Name            = ''
        Synonym         = ''
        Description     = ''
        Vendor          = ''
        Version         = ''
        PlatformVersion = ''
        DefaultRunMode  = ''
        FormMode        = ''
        ScriptVariant   = ''
        NamePrefix      = ''
        BspDetected     = $false
        BspVersion      = ''
        Subsystems      = @()
        Counts          = [ordered]@{}
    }

    $configXml = Join-Path $Root 'Configuration.xml'
    $extXml = Join-Path $Root 'ConfigurationExtension.xml'
    $xmlPath = $null
    if (Test-Path $configXml) { $xmlPath = $configXml }
    elseif (Test-Path $extXml) { $xmlPath = $extXml; $info.IsExtension = $true }
    if (-not $xmlPath) { return $info }

    $info.Detected = $true
    $info.ConfigPath = (Split-Path -Leaf $xmlPath)

    $xml = ''
    try { $xml = Get-Content -Raw -Path $xmlPath -ErrorAction Stop }
    catch { return $info }

    # Narrow the search to the Properties block of the top-level Configuration
    # (or ConfigurationExtension) element so that nested objects (when present)
    # do not bleed into single-tag matches.
    $propsMatch = [regex]::Match($xml, '(?s)<Properties>(.*?)</Properties>')
    $props = if ($propsMatch.Success) { $propsMatch.Groups[1].Value } else { $xml }

    $info.Name = Get-1cFieldValue -Xml $props -Tag 'Name'
    $info.Description = Get-1cFieldValue -Xml $props -Tag 'Comment'
    $info.Vendor = Get-1cFieldValue -Xml $props -Tag 'Vendor'
    $info.Version = Get-1cFieldValue -Xml $props -Tag 'Version'
    $info.NamePrefix = Get-1cFieldValue -Xml $props -Tag 'NamePrefix'
    $info.ScriptVariant = Get-1cFieldValue -Xml $props -Tag 'ScriptVariant'
    $info.DefaultRunMode = Get-1cFieldValue -Xml $props -Tag 'DefaultRunMode'

    $compat = Get-1cFieldValue -Xml $props -Tag 'CompatibilityMode'
    if (-not $compat) { $compat = Get-1cFieldValue -Xml $props -Tag 'ConfigurationExtensionCompatibilityMode' }
    if ($compat -and $compat -match 'Version(\d+)_(\d+)_(\d+)') {
        $info.PlatformVersion = "$($matches[1]).$($matches[2]).$($matches[3])"
    }
    elseif ($compat) {
        $info.PlatformVersion = $compat
    }

    $useManagedInOrdinary = (Get-1cFieldValue -Xml $props -Tag 'UseManagedFormInOrdinaryApplication') -eq 'true'
    $useOrdinaryInManaged = (Get-1cFieldValue -Xml $props -Tag 'UseOrdinaryFormInManagedApplication') -eq 'true'
    switch ($info.DefaultRunMode) {
        'ManagedApplication'  { $info.FormMode = if ($useOrdinaryInManaged) { 'mixed' } else { 'managed' } }
        'OrdinaryApplication' { $info.FormMode = if ($useManagedInOrdinary) { 'mixed' } else { 'ordinary' } }
        default               { $info.FormMode = '' }
    }

    $info.Synonym = Get-1cSynonymRu -Xml $props

    if ($info.NamePrefix -and -not $info.IsExtension) { $info.IsExtension = $true }

    # БСП detection — common module path is the canonical signal; fall back to
    # the matching subsystem .xml. Version is parsed from the body of the
    # `Функция ВерсияБиблиотеки()` (or English `LibraryVersion()`) function.
    $bspCandidates = @(
        'CommonModules\СтандартныеПодсистемыСервер\Ext\Module.bsl',
        'CommonModules\StandardSubsystemsServer\Ext\Module.bsl'
    )
    $bspFile = $null
    foreach ($c in $bspCandidates) {
        $p = Join-Path $Root $c
        if (Test-Path $p) { $bspFile = $p; break }
    }
    if (-not $bspFile) {
        foreach ($n in @('СтандартныеПодсистемы.xml', 'StandardSubsystems.xml')) {
            if (Test-Path (Join-Path $Root "Subsystems\$n")) { $info.BspDetected = $true; break }
        }
    }
    if ($bspFile) {
        $info.BspDetected = $true
        try {
            $bspContent = Get-Content -Raw -Path $bspFile -ErrorAction Stop
            $rxRu = [regex]'(?ms)Функция\s+ВерсияБиблиотеки\s*\(\s*\)\s+Экспорт.*?Возврат\s+"([0-9.]+)"'
            $rxEn = [regex]'(?ms)Function\s+LibraryVersion\s*\(\s*\)\s+Export.*?Return\s+"([0-9.]+)"'
            $vm = $rxRu.Match($bspContent)
            if (-not $vm.Success) { $vm = $rxEn.Match($bspContent) }
            if ($vm.Success) { $info.BspVersion = $vm.Groups[1].Value }
        }
        catch {}
    }

    $subsDir = Join-Path $Root 'Subsystems'
    if (Test-Path $subsDir) {
        $info.Subsystems = @(
            Get-ChildItem -File $subsDir -Filter *.xml -ErrorAction SilentlyContinue |
                ForEach-Object { [System.IO.Path]::GetFileNameWithoutExtension($_.Name) } |
                Sort-Object
        )
    }

    $kinds = [ordered]@{
        'Catalogs'                    = 'Справочники'
        'Documents'                   = 'Документы'
        'InformationRegisters'        = 'Регистры сведений'
        'AccumulationRegisters'       = 'Регистры накопления'
        'AccountingRegisters'         = 'Регистры бухгалтерии'
        'CalculationRegisters'        = 'Регистры расчёта'
        'CommonModules'               = 'Общие модули'
        'Reports'                     = 'Отчёты'
        'DataProcessors'              = 'Обработки'
        'Enums'                       = 'Перечисления'
        'ChartsOfCharacteristicTypes' = 'Планы видов характеристик'
        'BusinessProcesses'           = 'Бизнес-процессы'
        'Tasks'                       = 'Задачи'
    }
    foreach ($k in $kinds.Keys) {
        $d = Join-Path $Root $k
        if (Test-Path $d) {
            $count = @(Get-ChildItem -File $d -Filter *.xml -ErrorAction SilentlyContinue).Count
            if ($count -gt 0) { $info.Counts[$kinds[$k]] = $count }
        }
    }

    return $info
}

function Format-1cProjectMd {
    param([System.Collections.IDictionary]$Info)

    $lines = New-Object System.Collections.ArrayList
    $title = if ($Info.Synonym) { $Info.Synonym } elseif ($Info.Name) { $Info.Name } else { 'Проект 1С' }
    [void]$lines.Add("# Проект: $title")
    [void]$lines.Add('')
    [void]$lines.Add('> Этот файл сгенерирован автоматически установщиком `1c-rules` на основе')
    [void]$lines.Add('> данных репозитория (`Configuration.xml`, БСП-модуль, состав каталогов')
    [void]$lines.Add('> метаданных). Обновляется при `update` параллельно с остальными правилами.')
    [void]$lines.Add('> Если вы редактируете файл вручную, ваши правки сохраняются — установщик')
    [void]$lines.Add('> отметит его как `userModified` в `.ai-rules.json` и больше не будет')
    [void]$lines.Add('> перезаписывать. Чтобы пересобрать с нуля, удалите файл и запустите `update`.')
    [void]$lines.Add('')
    [void]$lines.Add('## Конфигурация')
    [void]$lines.Add('')
    if ($Info.Name) { [void]$lines.Add("- Имя метаданных: ``$($Info.Name)``") }
    if ($Info.Synonym) { [void]$lines.Add("- Синоним: $($Info.Synonym)") }
    if ($Info.Vendor) { [void]$lines.Add("- Поставщик: $($Info.Vendor)") }
    if ($Info.Version) { [void]$lines.Add("- Редакция / версия: $($Info.Version)") }
    $type = if ($Info.IsExtension) { 'расширение конфигурации (CFE)' } else { 'основная конфигурация (CF)' }
    [void]$lines.Add("- Тип: $type")
    if ($Info.NamePrefix) { [void]$lines.Add("- Префикс расширения (NamePrefix): ``$($Info.NamePrefix)``") }
    if ($Info.Description) {
        [void]$lines.Add('')
        [void]$lines.Add($Info.Description)
    }
    [void]$lines.Add('')

    [void]$lines.Add('## Платформа')
    [void]$lines.Add('')
    if ($Info.PlatformVersion) { [void]$lines.Add("- Совместимость: 1С:Предприятие $($Info.PlatformVersion)") }
    else { [void]$lines.Add('- Совместимость: не определена в `Configuration.xml`') }
    if ($Info.DefaultRunMode) { [void]$lines.Add("- Режим запуска по умолчанию: ``$($Info.DefaultRunMode)``") }
    if ($Info.FormMode) {
        $formText = switch ($Info.FormMode) {
            'managed'  { 'управляемые' }
            'ordinary' { 'обычные' }
            'mixed'    { 'смешанный (управляемые и обычные)' }
            default    { $Info.FormMode }
        }
        [void]$lines.Add("- Режим форм: $formText")
    }
    if ($Info.ScriptVariant) { [void]$lines.Add("- Вариант встроенного языка: $($Info.ScriptVariant)") }
    [void]$lines.Add('')

    [void]$lines.Add('## Стандартная библиотека (БСП)')
    [void]$lines.Add('')
    if ($Info.BspDetected) {
        $ver = if ($Info.BspVersion) { $Info.BspVersion } else { 'версия не определена' }
        [void]$lines.Add('- Используется: да')
        [void]$lines.Add("- Версия: $ver")
    }
    else {
        [void]$lines.Add('- Используется: нет (общий модуль `СтандартныеПодсистемыСервер` не обнаружен)')
    }
    [void]$lines.Add('')

    if ($Info.Subsystems.Count -gt 0) {
        [void]$lines.Add("## Подсистемы верхнего уровня ($($Info.Subsystems.Count))")
        [void]$lines.Add('')
        foreach ($s in $Info.Subsystems) { [void]$lines.Add("- $s") }
        [void]$lines.Add('')
    }

    if ($Info.Counts.Count -gt 0) {
        [void]$lines.Add('## Состав метаданных')
        [void]$lines.Add('')
        foreach ($k in $Info.Counts.Keys) { [void]$lines.Add("- ${k}: $($Info.Counts[$k])") }
        [void]$lines.Add('')
    }

    [void]$lines.Add('## Соглашения и ограничения')
    [void]$lines.Add('')
    [void]$lines.Add('- Язык платформы: 1С (BSL); комментарии и UI-строки — на русском')
    [void]$lines.Add('- Стандарты ИТС, расширенные правилами проекта (см. `AGENTS.md` и каталог on-demand правил активного инструмента)')
    [void]$lines.Add('- Запрет на тернарный оператор `?(...)`, `Сообщить()`, обращение к реквизитам через точку')
    [void]$lines.Add('- Перед написанием кода — поиск по `templatesearch` / `codesearch` / `search_code`')
    [void]$lines.Add('- После написания кода — `syntaxcheck` → `check_1c_code` → `review_1c_code` (≤ 3 раза за цикл)')
    [void]$lines.Add('- Полный список запретов и стандартов — `AGENTS.md`, раздел *Forbidden Calls and Constructs*')
    return ($lines -join "`n") + "`n"
}

function Invoke-OpenSpecProjectMd {
    param(
        [string]$Root,
        [System.Collections.IDictionary]$Manifest
    )
    $rel = 'openspec/project.md'
    $info = Get-1cProjectInfo -Root $Root

    if (-not $info.Detected) {
        Write-Info '  OpenSpec project.md: 1С-сигналов не найдено (нет Configuration.xml) — пропуск'
        return
    }

    if ($Manifest.files.Contains($rel)) {
        $existing = $Manifest.files[$rel]
        if ($existing -and $existing.userModified) {
            Write-Info '  OpenSpec project.md: оставлен без изменений (userModified)'
            return
        }
    }

    $abs = Join-Path $Root $rel
    $parent = Split-Path -Parent $abs
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    $content = Format-1cProjectMd -Info $info
    Write-TextFile -Path $abs -Content $content
    $hash = Get-FileSha256 $abs
    $Manifest.files[$rel] = [ordered]@{
        source        = '<auto-generated:1c-rules>'
        installedHash = $hash
    }

    if (-not $Manifest.integrations) { $Manifest.integrations = [ordered]@{} }
    if (-not $Manifest.integrations.Contains('openspec')) {
        $Manifest.integrations['openspec'] = [ordered]@{ detected = $false; files = @() }
    }
    $Manifest.integrations['openspec']['projectMdGenerated'] = $true

    $summaryParts = @()
    if ($info.Synonym) { $summaryParts += $info.Synonym }
    elseif ($info.Name) { $summaryParts += $info.Name }
    if ($info.PlatformVersion) { $summaryParts += "8.3.x: $($info.PlatformVersion)" }
    if ($info.BspDetected) {
        $bspTag = 'БСП'
        if ($info.BspVersion) { $bspTag += " $($info.BspVersion)" }
        $summaryParts += $bspTag
    }
    if ($info.FormMode) { $summaryParts += "формы: $($info.FormMode)" }
    if ($info.IsExtension) { $summaryParts += 'CFE' }
    Write-Info ('  OpenSpec project.md: ' + ($summaryParts -join ' | '))
}

# ============================================================================
# SECTION 10: PLACE PHASE
# ============================================================================

function Get-AdapterForTool {
    param(
        [string]$Root,
        [string]$Tool
    )
    $path = Join-Path $Root "adapters/$Tool.yaml"
    if (-not (Test-Path $path)) {
        throw "Adapter not found: $path"
    }
    return (ConvertFrom-AdapterYaml $path)
}

function Resolve-CopyToPath {
    param(
        [string]$Template,
        [string]$Name
    )
    $p = $Template -replace '\{name\}', $Name
    if ($p.StartsWith('~/')) {
        $userHome = [Environment]::GetFolderPath('UserProfile')
        $tail = $p.Substring(2).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
        $p = [System.IO.Path]::Combine($userHome, $tail)
    }
    return $p
}

function Invoke-PlaceArtifactFile {
    param(
        [string]$Root,
        [string]$SourcePath,
        [string]$TargetRel,
        [System.Collections.IDictionary]$SourceFm,
        [string]$SourceBody,
        [System.Collections.IDictionary]$FrontmatterOps,
        [string]$Mode,
        [string]$Template,
        [System.Collections.IDictionary]$Manifest,
        [string]$ContentSource
    )
    # Respect user modifications: if manifest marks this path as userModified,
    # keep the user's edits and leave the manifest entry unchanged.
    if ($Manifest -and $Manifest.files -and $Manifest.files.Contains($TargetRel)) {
        $existing = $Manifest.files[$TargetRel]
        if ($existing -and $existing.userModified) {
            return
        }
    }
    if ([System.IO.Path]::IsPathRooted($TargetRel)) {
        $absTarget = $TargetRel
    }
    else {
        $absTarget = Join-Path $Root $TargetRel
    }
    if ($Mode -eq 'rebuild-toml') {
        $rendered = Invoke-CodexAgentTemplate -Template $Template -Fm $SourceFm -Body $SourceBody
        Write-TextFile -Path $absTarget -Content $rendered
    }
    elseif ($Mode -eq 'verbatim') {
        $parentDir = Split-Path -Parent $absTarget
        if ($parentDir -and -not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        Copy-Item -Path $SourcePath -Destination $absTarget -Force
    }
    else {
        $newFm = Invoke-FrontmatterOps -Source $SourceFm -Ops $FrontmatterOps
        $fmText = Format-Frontmatter $newFm
        if ($fmText) {
            $full = $fmText + "`n" + $SourceBody
        }
        else {
            $full = $SourceBody
        }
        Write-TextFile -Path $absTarget -Content $full
    }
    $hash = Get-FileSha256 $absTarget
    $Manifest.files[$TargetRel] = [ordered]@{
        source        = $ContentSource
        installedHash = $hash
    }
}

function Invoke-PlaceSkill {
    param(
        [string]$Root,
        [string]$SourceDir,
        [string]$TargetDir,
        [System.Collections.IDictionary]$Manifest,
        [string]$ContentSource
    )
    $absTarget = Join-Path $Root $TargetDir
    if (Test-Path $absTarget) { Remove-Item -Recurse -Force $absTarget }
    Copy-Item -Path $SourceDir -Destination $absTarget -Recurse -Force
    $rootFull = (Resolve-Path $Root).Path.TrimEnd('\', '/')
    Get-ChildItem -Recurse -File -Path $absTarget | ForEach-Object {
        $rel = $_.FullName.Substring($rootFull.Length + 1).Replace('\', '/')
        $Manifest.files[$rel] = [ordered]@{
            source        = $ContentSource
            installedHash = (Get-FileSha256 $_.FullName)
        }
    }
}

function Invoke-PlacePhase {
    param(
        [string]$Root,
        [string]$SourceRoot,
        [string[]]$ActiveTools,
        [hashtable]$Adapters,
        [System.Collections.IDictionary]$Manifest
    )
    foreach ($tool in $ActiveTools) {
        $adapter = $Adapters[$tool]
        Write-Info "  [$tool] placing files"

        # rules
        if ($adapter.rules -and $adapter.rules.copyTo) {
            $copyTpl = $adapter.rules.copyTo
            $fmOps = $adapter.rules.frontmatter
            $mode = if ($adapter.rules.mode) { $adapter.rules.mode } else { 'transform' }
            foreach ($f in Get-ChildItem -File (Join-Path $SourceRoot 'content/rules') -Filter *.md) {
                $parts = Split-FrontmatterAndBody (Read-TextFile $f.FullName)
                $name = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
                $target = Resolve-CopyToPath $copyTpl $name
                Invoke-PlaceArtifactFile -Root $Root -SourcePath $f.FullName `
                    -TargetRel $target -SourceFm $parts.Frontmatter -SourceBody $parts.Body `
                    -FrontmatterOps $fmOps -Mode $mode `
                    -Manifest $Manifest -ContentSource ("content/rules/" + $f.Name)
            }
        }

        # agents
        if ($adapter.agents -and $adapter.agents.copyTo) {
            $copyTpl = $adapter.agents.copyTo
            $fmOps = $adapter.agents.frontmatter
            $mode = if ($adapter.agents.mode) { $adapter.agents.mode } else { 'transform' }
            $template = $adapter.agents.template
            foreach ($f in Get-ChildItem -File (Join-Path $SourceRoot 'content/agents') -Filter *.md) {
                $parts = Split-FrontmatterAndBody (Read-TextFile $f.FullName)
                $name = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
                $target = Resolve-CopyToPath $copyTpl $name
                Invoke-PlaceArtifactFile -Root $Root -SourcePath $f.FullName `
                    -TargetRel $target -SourceFm $parts.Frontmatter -SourceBody $parts.Body `
                    -FrontmatterOps $fmOps -Mode $mode -Template $template `
                    -Manifest $Manifest -ContentSource ("content/agents/" + $f.Name)
            }
        }

        # commands
        if ($adapter.commands -and $adapter.commands.copyTo) {
            $copyTpl = $adapter.commands.copyTo
            $fmOps = $adapter.commands.frontmatter
            $mode = if ($adapter.commands.mode) { $adapter.commands.mode } else { 'transform' }
            foreach ($f in Get-ChildItem -File (Join-Path $SourceRoot 'content/commands') -Filter *.md) {
                $parts = Split-FrontmatterAndBody (Read-TextFile $f.FullName)
                $name = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
                $targetRaw = Resolve-CopyToPath $copyTpl $name
                # If target starts with ~/ (absolute home path), we need to write outside root
                if ($copyTpl.StartsWith('~/')) {
                    Invoke-PlaceArtifactFile -Root $Root -SourcePath $f.FullName `
                        -TargetRel $targetRaw -SourceFm $parts.Frontmatter -SourceBody $parts.Body `
                        -FrontmatterOps $fmOps -Mode $mode `
                        -Manifest $Manifest -ContentSource ("content/commands/" + $f.Name)
                    Write-Warn "  command written to user scope: $targetRaw (shared across projects)"
                }
                else {
                    Invoke-PlaceArtifactFile -Root $Root -SourcePath $f.FullName `
                        -TargetRel $targetRaw -SourceFm $parts.Frontmatter -SourceBody $parts.Body `
                        -FrontmatterOps $fmOps -Mode $mode `
                        -Manifest $Manifest -ContentSource ("content/commands/" + $f.Name)
                }
            }
        }

        # skills
        if ($adapter.skills -and $adapter.skills.copyTo) {
            $dirTpl = $adapter.skills.copyTo.TrimEnd('/', '\')
            foreach ($sd in Get-ChildItem -Directory (Join-Path $SourceRoot 'content/skills')) {
                $skillMd = Join-Path $sd.FullName 'SKILL.md'
                if (-not (Test-Path $skillMd)) { continue }
                $name = $sd.Name
                $targetDir = Resolve-CopyToPath $dirTpl $name
                Invoke-PlaceSkill -Root $Root -SourceDir $sd.FullName -TargetDir $targetDir `
                    -Manifest $Manifest -ContentSource ("content/skills/" + $name)
            }
        }

        # entry (Claude Code CLAUDE.md and similar)
        if ($adapter.entry) {
            $etarget = $adapter.entry.target
            $etpl = $adapter.entry.template
            if ($etarget) {
                Write-TextFile -Path (Join-Path $Root $etarget) -Content $etpl
                $Manifest.files[$etarget] = [ordered]@{
                    source        = 'adapters/' + $tool + '.yaml#entry'
                    installedHash = (Get-FileSha256 (Join-Path $Root $etarget))
                }
            }
        }
    }

    # On-demand rules go to each active tool's rules directory only. The shared
    # `.ai-rules/rules/` mirror is no longer created — `AGENTS.md` references
    # the canonical tool's directory, resolved by `Resolve-CanonicalRulesDir`.
}

# Priority order for choosing the "canonical" rules directory referenced by
# AGENTS.md. Lower index = higher priority. The first active tool in this
# order whose adapter defines a `rules.copyTo` wins. The universal fallback
# `other` is intentionally last: when combined with any "real" tool the real
# tool's rules dir wins; `.ai-agent/rules/` becomes canonical only when
# `other` is the only active tool.
$script:RulesDirPriority = @('cursor', 'claude-code', 'kilocode', 'opencode', 'codex', 'other')

function Resolve-CanonicalRulesLayout {
    # Returns @{ Dir = <path>; Ext = <ext-without-dot> } for the highest-priority
    # active tool whose adapter declares `rules.copyTo`. Returns $null if none.
    param(
        [string[]]$ActiveTools,
        [hashtable]$Adapters
    )
    foreach ($tool in $script:RulesDirPriority) {
        if ($ActiveTools -notcontains $tool) { continue }
        $adapter = $Adapters[$tool]
        if (-not $adapter -or -not $adapter.Contains('rules')) { continue }
        $copyTo = [string]$adapter.rules.copyTo
        if (-not $copyTo) { continue }
        $dir = $copyTo -replace '\{name\}.*$', ''
        $dir = $dir.TrimEnd('/', '\')
        $ext = ''
        if ($copyTo -match '\{name\}\.([A-Za-z0-9]+)$') { $ext = $Matches[1] }
        if ($dir) { return @{ Dir = $dir; Ext = $ext } }
    }
    return $null
}

# ============================================================================
# SECTION 11: MCP PHASE
# ============================================================================

function Invoke-McpPhase {
    param(
        [string]$Root,
        [string]$SourceRoot,
        [string[]]$ActiveTools,
        [hashtable]$Adapters,
        [System.Collections.IDictionary]$Manifest
    )
    $servers = Read-McpServers -Root $SourceRoot
    $installedIds = @($servers | ForEach-Object { $_.id })
    $Manifest.mcpServers = @($installedIds)

    foreach ($tool in $ActiveTools) {
        $adapter = $Adapters[$tool]
        if (-not $adapter.mcp) { continue }
        $target = $adapter.mcp.target
        if (-not $target) { continue }
        $content = New-McpConfig -ToolId $tool -Servers $servers
        $absTarget = Join-Path $Root $target
        Write-TextFile -Path $absTarget -Content ($content + "`n")
        $Manifest.files[$target] = [ordered]@{
            source        = 'content/mcp-servers.json'
            installedHash = (Get-FileSha256 $absTarget)
        }
        Write-Info "  [$tool] MCP config: $target"
    }
}

# ============================================================================
# SECTION 12: AGENTS.MD (STATIC COPY)
# ============================================================================
#
# AGENTS.md is shipped as a fully static file in the source repository. The
# installer only copies it into the project root and refreshes it on update
# when the user has not modified it. No dynamic blocks, no @-imports injected
# for foreign files or SDD integrations - the installer records those in the
# manifest (`foreignFiles`, `integrations`) for bookkeeping only, and the
# shipped `AGENTS.md` documents how the user can link them manually.

function Update-AgentsMd {
    param(
        [string]$Root,
        [string]$SourceRoot,
        [string[]]$ActiveTools,
        [hashtable]$Adapters,
        [System.Collections.IDictionary]$Manifest
    )
    $agentsPath = Join-Path $Root $script:AgentsMdFileName
    $sourceAgentsPath = Join-Path $SourceRoot $script:AgentsMdFileName

    if (-not (Test-Path $sourceAgentsPath)) { return }

    # Render: read source template and substitute the {{ rulesDir }} and
    # {{ rulesExt }} placeholders with the canonical rules directory and file
    # extension of the highest-priority active tool. Substitution is always
    # done from the source template (idempotent on repeated updates even if
    # active tools change).
    $layout = Resolve-CanonicalRulesLayout -ActiveTools $ActiveTools -Adapters $Adapters
    if (-not $layout) {
        Write-Warn 'No active tool defines a rules directory; AGENTS.md placeholders will be left as-is.'
        $rulesDir = '{{ rulesDir }}'
        $rulesExt = '{{ rulesExt }}'
    }
    else {
        $rulesDir = [string]$layout.Dir
        $rulesExt = [string]$layout.Ext
        if (-not $rulesExt) { $rulesExt = 'md' }
    }
    $sourceText = Read-TextFile $sourceAgentsPath
    $rendered = $sourceText.Replace('{{ rulesDir }}', $rulesDir).Replace('{{ rulesExt }}', $rulesExt)

    # Copy or refresh only when safe: the file does not exist locally, or it
    # was installed by us previously and has not been user-modified since.
    $shouldRefresh = $false
    if (-not (Test-Path $agentsPath)) {
        $shouldRefresh = $true
    }
    elseif ($Manifest.files.Contains($script:AgentsMdFileName)) {
        $entry = $Manifest.files[$script:AgentsMdFileName]
        if (-not $entry.userModified) {
            $currentHash = Get-FileSha256 $agentsPath
            if ($currentHash -eq $entry.installedHash) {
                $shouldRefresh = $true
            }
        }
    }
    if ($shouldRefresh) {
        Write-TextFile -Path $agentsPath -Content $rendered
    }

    if (Test-Path $agentsPath) {
        $Manifest.files[$script:AgentsMdFileName] = [ordered]@{
            source        = 'AGENTS.md'
            rulesDir      = $rulesDir
            rulesExt      = $rulesExt
            installedHash = (Get-FileSha256 $agentsPath)
        }
    }
}

# Place USER-RULES.md and memory.md from source templates into the project
# root, but ONLY if they do not already exist. The installer never overwrites
# these files — they belong to the user/project. Manifest records them with
# `template = $true` so update flows know these are placed-once templates and
# their hashes are not re-validated.
function Place-RootTemplates {
    param(
        [string]$Root,
        [string]$SourceRoot,
        [System.Collections.IDictionary]$Manifest
    )
    $names = @($script:UserRulesFileName, $script:MemoryFileName)
    foreach ($name in $names) {
        $target = Join-Path $Root $name
        $source = Join-Path $SourceRoot $name
        if (Test-Path $target) {
            # Keep manifest entry consistent if the file was created earlier
            # but is missing from the current manifest (e.g. legacy install).
            if (-not $Manifest.files.Contains($name)) {
                $Manifest.files[$name] = [ordered]@{
                    source        = $name
                    template      = $true
                    installedHash = (Get-FileSha256 $target)
                }
            }
            continue
        }
        if (-not (Test-Path $source)) {
            Write-Warn "Template not found in source: $name"
            continue
        }
        $content = Read-TextFile $source
        Write-TextFile -Path $target -Content $content
        $Manifest.files[$name] = [ordered]@{
            source        = $name
            template      = $true
            installedHash = (Get-FileSha256 $target)
        }
        Write-Info "  placed (template, will not be overwritten on update): $name"
    }
}

# ============================================================================
# SECTION 12b: .dev.env BOOTSTRAP
# ============================================================================
#
# .dev.env is the single source of truth for project parameters used by
# all rules / commands / subagents (code-generation params + infobase
# connection params + web-publish URL for tests).
#
# Behaviour:
#   - If the file already exists in the project root — DO NOT overwrite.
#     Just register it in the manifest so future updates know it is present.
#   - If missing — render from the source `.dev.env.example` template,
#     auto-fill what we can detect (PLATFORM_VERSION from Configuration.xml,
#     PLATFORM_PATH from C:\Program Files\1cv8\, PREFIX from extension's
#     NamePrefix), and either prompt the user for the rest (interactive
#     mode) or leave them empty with a console WARNING (non-interactive).
#
# Critical fields (treated as blocking for IB-related commands when empty):
#   PREFIX, COMPANY, DEVELOPER, PLATFORM_VERSION, PLATFORM_PATH,
#   INFOBASE_PATH.
# Recommended fields (warned about, but not blocking):
#   IB_USER, INFOBASE_PUBLISH_URL, LOG_PATH.

function Find-PlatformPath {
    # Returns the path to the most recent installed 1C platform under
    # `C:\Program Files\1cv8\<version>\bin\1cv8.exe` or its (x86) sibling,
    # or empty string when nothing is found.
    param([string]$PreferredVersion)

    $roots = @()
    foreach ($pf in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not $pf) { continue }
        $r = Join-Path $pf '1cv8'
        if (Test-Path $r) { $roots += $r }
    }
    if ($roots.Count -eq 0) { return '' }

    $candidates = @()
    foreach ($r in $roots) {
        $dirs = Get-ChildItem -Directory -Path $r -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d+(\.\d+){2,3}$' -and (Test-Path (Join-Path $_.FullName 'bin\1cv8.exe')) }
        foreach ($d in $dirs) {
            $verParts = ($d.Name -split '\.') | ForEach-Object { [int]$_ }
            while ($verParts.Count -lt 4) { $verParts += 0 }
            $candidates += [PSCustomObject]@{
                Path     = $d.FullName
                Version  = $d.Name
                SortKey  = ($verParts[0] * 1000000000L) + ($verParts[1] * 1000000L) + ($verParts[2] * 1000L) + $verParts[3]
            }
        }
    }
    if ($candidates.Count -eq 0) { return '' }

    if ($PreferredVersion -and $PreferredVersion -match '^\d+(\.\d+){1,3}$') {
        $prefMatch = $candidates | Where-Object { $_.Version.StartsWith($PreferredVersion + '.') -or $_.Version -eq $PreferredVersion } |
            Sort-Object SortKey -Descending | Select-Object -First 1
        if ($prefMatch) { return $prefMatch.Path }
    }
    return ($candidates | Sort-Object SortKey -Descending | Select-Object -First 1).Path
}

function Read-DevEnvKeys {
    # Parses a .dev.env file and returns an ordered hashtable of keys → values
    # for the lines that look like KEY=VALUE (no comments, no blanks).
    param([string]$Path)

    $result = [ordered]@{}
    if (-not (Test-Path $Path)) { return $result }
    foreach ($line in (Get-Content -Path $Path -Encoding UTF8 -ErrorAction SilentlyContinue)) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $trim = $line.TrimStart()
        if ($trim.StartsWith('#')) { continue }
        if ($trim -match '^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$') {
            $result[$Matches[1]] = $Matches[2]
        }
    }
    return $result
}

function Set-DevEnvValue {
    # In-place rewrite of a single KEY= line in the rendered template text.
    # Idempotent: only the first occurrence of `<Key>=...` at line start is
    # touched. If the key is not present, the text is returned unchanged.
    param(
        [string]$Text,
        [string]$Key,
        [string]$Value
    )
    if (-not $Text) { return $Text }
    $pattern = '(?m)^' + [regex]::Escape($Key) + '=.*$'
    $escVal = $Value -replace '\$', '$$$$'
    return [regex]::Replace($Text, $pattern, ($Key + '=' + $escVal), 1)
}

function Read-Required {
    # Asks the user for a value. Empty input returns empty string and lets the
    # caller decide whether to leave the field blank.
    param(
        [string]$Prompt,
        [string]$DefaultValue
    )
    if ($NonInteractive) { return $DefaultValue }
    $hint = if ($DefaultValue) { " [$DefaultValue]" } else { '' }
    $ans = Read-Host "$Prompt$hint"
    if ([string]::IsNullOrWhiteSpace($ans)) { return $DefaultValue }
    return $ans.Trim()
}

function Place-DevEnv {
    param(
        [string]$Root,
        [string]$SourceRoot,
        [System.Collections.IDictionary]$Manifest
    )
    $target = Join-Path $Root $script:DevEnvFileName
    $source = Join-Path $SourceRoot $script:DevEnvExampleName

    if (-not (Test-Path $source)) {
        Write-Warn "Template not found in source: $script:DevEnvExampleName"
        return
    }

    if (Test-Path $target) {
        if (-not $Manifest.files.Contains($script:DevEnvFileName)) {
            $Manifest.files[$script:DevEnvFileName] = [ordered]@{
                source        = $script:DevEnvExampleName
                template      = $true
                installedHash = (Get-FileSha256 $target)
            }
        }
        Write-Info "  .dev.env: already exists, leaving user values untouched"
        return
    }

    # Detect what we can without asking
    $info = Get-1cProjectInfo -Root $Root
    $detectedVersion = if ($info.PlatformVersion) { $info.PlatformVersion } else { '' }
    $detectedPath    = Find-PlatformPath -PreferredVersion $detectedVersion
    $detectedPrefix  = if ($info.NamePrefix) { $info.NamePrefix } else { '' }

    $text = Read-TextFile $source

    # Prefill auto-detected values
    if ($detectedVersion) { $text = Set-DevEnvValue -Text $text -Key 'PLATFORM_VERSION' -Value $detectedVersion }
    if ($detectedPath)    { $text = Set-DevEnvValue -Text $text -Key 'PLATFORM_PATH'    -Value $detectedPath }
    if ($detectedPrefix)  { $text = Set-DevEnvValue -Text $text -Key 'PREFIX'           -Value $detectedPrefix }

    # Interactive prompts for the human-only fields
    if (-not $NonInteractive) {
        Write-Info ''
        Write-Info '  Заполнение .dev.env (Enter — оставить поле пустым/значением по умолчанию):'
        if (-not $detectedPrefix)  { $val = Read-Required 'PREFIX (префикс новых объектов, напр. рлф)' '';                                     if ($val) { $text = Set-DevEnvValue -Text $text -Key 'PREFIX'              -Value $val } }
        $val = Read-Required 'COMPANY (название компании/проекта для комментариев)' '';                                                       if ($val) { $text = Set-DevEnvValue -Text $text -Key 'COMPANY'             -Value $val }
        $val = Read-Required 'DEVELOPER (идентификатор разработчика)'                ''; if (-not $val) { $val = $env:USERNAME };             if ($val) { $text = Set-DevEnvValue -Text $text -Key 'DEVELOPER'           -Value $val }
        if (-not $detectedVersion) { $val = Read-Required 'PLATFORM_VERSION (мин. совместимость, напр. 8.3.23)' '';                            if ($val) { $text = Set-DevEnvValue -Text $text -Key 'PLATFORM_VERSION'    -Value $val } }
        if (-not $detectedPath)    { $val = Read-Required 'PLATFORM_PATH (каталог установки 1С, содержит bin\1cv8.exe)' '';                    if ($val) { $text = Set-DevEnvValue -Text $text -Key 'PLATFORM_PATH'       -Value $val } }
        $kindAns = Read-Choice 'INFOBASE_KIND' @('file', 'server') 'file';                                                                     $text = Set-DevEnvValue -Text $text -Key 'INFOBASE_KIND' -Value $kindAns
        $val = Read-Required 'INFOBASE_PATH (путь к файловой ИБ или строка подключения)'  '';                                                  if ($val) { $text = Set-DevEnvValue -Text $text -Key 'INFOBASE_PATH'       -Value $val }
        $val = Read-Required 'IB_USER (пусто — без аутентификации)'                       '';                                                  if ($val) { $text = Set-DevEnvValue -Text $text -Key 'IB_USER'             -Value $val }
        $val = Read-Required 'IB_PASSWORD (пусто — без пароля; не храните прод-пароли)'   '';                                                  if ($val) { $text = Set-DevEnvValue -Text $text -Key 'IB_PASSWORD'         -Value $val }
        $val = Read-Required 'LOG_PATH (файл лога Designer''а, напр. E:\Temp\1cv8.log)' '';                                                   if ($val) { $text = Set-DevEnvValue -Text $text -Key 'LOG_PATH'            -Value $val }
        $val = Read-Required 'INFOBASE_PUBLISH_URL (URL веб-публикации для UI-тестов; пусто — UI-тесты пропускаются)' '';                      if ($val) { $text = Set-DevEnvValue -Text $text -Key 'INFOBASE_PUBLISH_URL' -Value $val }
    }

    Write-TextFile -Path $target -Content $text
    $Manifest.files[$script:DevEnvFileName] = [ordered]@{
        source        = $script:DevEnvExampleName
        template      = $true
        installedHash = (Get-FileSha256 $target)
    }

    Write-Info "  placed: .dev.env (single source of truth for project parameters)"
    if ($detectedVersion) { Write-Info "    autodetected PLATFORM_VERSION = $detectedVersion" }
    if ($detectedPath)    { Write-Info "    autodetected PLATFORM_PATH    = $detectedPath" }
    if ($detectedPrefix)  { Write-Info "    autodetected PREFIX           = $detectedPrefix" }

    # Final sanity check: warn loudly about empty critical fields so the user
    # knows the file still needs hand-editing before code-gen / IB commands run.
    $values = Read-DevEnvKeys -Path $target
    $criticalEmpty = @()
    foreach ($k in @('PREFIX', 'COMPANY', 'DEVELOPER', 'PLATFORM_VERSION', 'PLATFORM_PATH', 'INFOBASE_PATH')) {
        if (-not $values.Contains($k) -or [string]::IsNullOrWhiteSpace($values[$k])) { $criticalEmpty += $k }
    }
    $recommendedEmpty = @()
    foreach ($k in @('LOG_PATH', 'INFOBASE_PUBLISH_URL')) {
        if (-not $values.Contains($k) -or [string]::IsNullOrWhiteSpace($values[$k])) { $recommendedEmpty += $k }
    }
    if ($criticalEmpty.Count -gt 0) {
        Write-Warn ("  .dev.env: незаполнены критичные поля: " + ($criticalEmpty -join ', '))
        Write-Warn '  Заполните их вручную перед запуском задач генерации кода / работы с ИБ.'
    }
    if ($recommendedEmpty.Count -gt 0) {
        Write-Info ("  .dev.env: рекомендуется также заполнить: " + ($recommendedEmpty -join ', '))
    }
}

# ============================================================================
# SECTION 13: COMMANDS
# ============================================================================

function Test-SourceIsUrl {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $false }
    if ($Value -match '^(https?|git|ssh)://') { return $true }
    if ($Value -match '^git@[^:]+:.+') { return $true }
    if ($Value -match '\.git/?$') { return $true }
    return $false
}

# Shallow-clone a remote repository to a deterministic cache directory under
# $env:TEMP and return its path. The cache key is derived from the URL so
# repeated runs reuse the same checkout (refreshed via fetch + reset).
function Get-SourceFromUrl {
    param([string]$Url)

    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        throw "Source is a URL ($Url) but 'git' was not found in PATH. Install git or pass a local path via -Source."
    }

    $hash = (Get-StringSha256 $Url).Substring(0, 12)
    $cacheRoot = if ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }
    $cacheDir = Join-Path $cacheRoot "1c-rules-source-$hash"

    if (Test-Path (Join-Path $cacheDir '.git')) {
        Write-Info "Refreshing cached source: $cacheDir"
        & git -C $cacheDir fetch --depth 1 origin HEAD 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            & git -C $cacheDir reset --hard FETCH_HEAD 2>&1 | Out-Null
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Fetch failed; reusing existing cached checkout."
        }
    }
    else {
        if (Test-Path $cacheDir) {
            Remove-Item -Recurse -Force $cacheDir
        }
        Write-Info "Cloning source: $Url -> $cacheDir"
        & git clone --depth 1 $Url $cacheDir 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $cacheDir '.git'))) {
            throw "git clone failed for $Url (exit code $LASTEXITCODE)."
        }
    }

    return (Resolve-Path $cacheDir).Path
}

function Resolve-SourceRoot {
    param([string]$Requested)
    if ($Requested) {
        if (Test-SourceIsUrl $Requested) {
            return (Get-SourceFromUrl -Url $Requested)
        }
        if (Test-Path $Requested) { return (Resolve-Path $Requested).Path }
        throw "Source path does not exist: $Requested"
    }
    # Default: directory where install.ps1 lives
    $scriptPath = $MyInvocation.ScriptName
    if (-not $scriptPath) { $scriptPath = $PSCommandPath }
    if (-not $scriptPath) { $scriptPath = $script:MyInvocation.MyCommand.Path }
    if (-not $scriptPath) {
        # Fallback — cwd
        return (Get-Location).Path
    }
    return (Split-Path -Parent $scriptPath)
}

function Load-Adapters {
    param([string]$SourceRoot, [string[]]$Tools)
    $result = @{}
    foreach ($t in $Tools) {
        $result[$t] = Get-AdapterForTool -Root $SourceRoot -Tool $t
    }
    return $result
}

function Get-SourceVersion {
    param([string]$SourceRoot)
    $gitDir = Join-Path $SourceRoot '.git'
    if (Test-Path $gitDir) {
        try {
            $ver = & git -C $SourceRoot describe --tags --always 2>$null
            if ($LASTEXITCODE -eq 0 -and $ver) { return $ver.Trim() }
        }
        catch {}
    }
    return 'local'
}

function Invoke-Init {
    param(
        [string]$Root,
        [string]$SourceRootRequested,
        [string[]]$RequestedTools
    )
    Write-Section 'Phase 1: Detection'
    $sourceRoot = Resolve-SourceRoot -Requested $SourceRootRequested
    Write-Info "Source: $sourceRoot"
    Write-Info "Project: $Root"

    $existing = Read-Manifest -Root $Root
    if ($existing -and -not $AssumeYes -and -not $NonInteractive) {
        Write-Warn 'Manifest already exists. init will overwrite it.'
        if (-not (Read-YesNo 'Proceed with re-init?' $false)) { return }
    }

    $activeTools = Invoke-Detection -Root $Root -RequestedTools $RequestedTools
    Write-Info ("Active tools: " + ($activeTools -join ', '))

    $adapters = Load-Adapters -SourceRoot $sourceRoot -Tools $activeTools

    Write-Section 'Phase 2-3: Scan foreign files + integrations'
    $foreign = Invoke-ScanForeign -Root $Root -ActiveTools $activeTools -Manifest $null -Adapters $adapters
    $integrations = Invoke-ScanIntegrations -Root $Root
    foreach ($t in $foreign.Keys) {
        if ($foreign[$t].Count -gt 0) { Write-Info "  foreign[$t]: $($foreign[$t].Count) file(s)" }
    }
    if ($integrations.Contains('openspec')) { Write-Info "  integration: openspec ($($integrations.openspec.files.Count) files)" }

    Write-Section 'Phase 4: Plan'
    Write-Info "Will write per-tool files into: .$($activeTools -join ', .')"
    Write-Info "MCP servers will be added to each tool's MCP config."
    if (-not $AssumeYes -and -not $NonInteractive) {
        if (-not (Read-YesNo 'Proceed with installation?' $true)) { return }
    }

    $version = Get-SourceVersion -SourceRoot $sourceRoot
    $manifest = New-Manifest -Source $sourceRoot -Version $version
    $manifest.tools = @($activeTools)
    $manifest.foreignFiles = $foreign
    $manifest.integrations = $integrations

    Write-Section 'Phase 6: Place (copy + transform)'
    Invoke-PlacePhase -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest

    Write-Section 'Phase 6b: OpenSpec scaffold'
    Invoke-OpenSpecScaffold -Root $Root -SourceRoot $sourceRoot -Manifest $manifest
    # Re-scan integrations now that openspec/ may have been created/extended
    # by scaffold; preserve the `scaffolded` flag set by the scaffold step.
    $rescanned = Invoke-ScanIntegrations -Root $Root
    if ($rescanned.Contains('openspec')) {
        $wasScaffolded = $false
        if ($manifest.integrations.Contains('openspec') -and $manifest.integrations['openspec'].Contains('scaffolded')) {
            $wasScaffolded = [bool]$manifest.integrations['openspec']['scaffolded']
        }
        $rescanned['openspec']['scaffolded'] = $wasScaffolded
    }
    $manifest.integrations = $rescanned

    Write-Section 'Phase 6c: OpenSpec artefacts (slash commands + skills)'
    Invoke-OpenSpecArtifacts -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Manifest $manifest

    Write-Section 'Phase 6d: OpenSpec project.md (1C autodetect)'
    Invoke-OpenSpecProjectMd -Root $Root -Manifest $manifest

    Write-Section 'Phase 7: MCP'
    Invoke-McpPhase -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest

    Write-Section 'Phase 8: AGENTS.md'
    Update-AgentsMd -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest

    Write-Section 'Phase 8b: Root templates (USER-RULES.md, memory.md)'
    Place-RootTemplates -Root $Root -SourceRoot $sourceRoot -Manifest $manifest

    Write-Section 'Phase 8c: .dev.env (project parameters, single source of truth)'
    Place-DevEnv -Root $Root -SourceRoot $sourceRoot -Manifest $manifest

    Write-Section 'Phase 9: Manifest'
    Write-Manifest -Root $Root -Manifest $manifest
    Write-Info ".ai-rules.json written"

    Write-Section 'Phase 10: Verify'
    $verify = Invoke-Verify -Root $Root -Manifest $manifest
    if ($verify.Ok) { Write-Info "Verification OK: $($verify.Count) files checked" }
    else { Write-Warn "Verification found $($verify.Mismatches.Count) mismatch(es)"; $verify.Mismatches | ForEach-Object { Write-Warn "  $_" } }

    Write-Section 'Phase 11: Report'
    Write-Info "Installation complete."
    Write-Info "  Version: $version (via $($script:LastChannel) channel)"
    Write-Info "  Tools: $($activeTools -join ', ')"
    Write-Info "  Files written: $($manifest.files.Count)"
    Write-Info "  MCP servers: $($manifest.mcpServers.Count)"
    if ($manifest.integrations -and $manifest.integrations.Contains('openspec')) {
        $os = $manifest.integrations['openspec']
        $scaffoldedTag = if ($os.Contains('scaffolded') -and $os['scaffolded']) { ' (scaffolded)' } else { '' }
        $bundleTag = if ($os.Contains('artifactsBundleVersion') -and $os['artifactsBundleVersion']) { " [artefacts v$($os['artifactsBundleVersion'])]" } else { '' }
        Write-Info "  OpenSpec$scaffoldedTag$bundleTag : $($os.files.Count) user file(s) in specs/changes"
    }
}

function Invoke-Verify {
    param(
        [string]$Root,
        [System.Collections.IDictionary]$Manifest
    )
    $mismatches = @()
    $count = 0
    foreach ($rel in $Manifest.files.Keys) {
        $abs = Join-Path $Root $rel
        if (-not (Test-Path $abs)) { $mismatches += "missing: $rel"; continue }
        $count++
        $actual = Get-FileSha256 $abs
        $expected = $Manifest.files[$rel].installedHash
        if ($actual -ne $expected) { $mismatches += "hash diff: $rel" }
    }
    return @{ Ok = ($mismatches.Count -eq 0); Count = $count; Mismatches = $mismatches }
}

function Invoke-Update {
    param(
        [string]$Root,
        [string]$SourceRootRequested
    )
    $manifest = Read-Manifest -Root $Root
    if (-not $manifest) { throw 'No manifest found. Run init first.' }
    if ($manifest.protocol -and [version]$manifest.protocol -gt [version]$script:ProtocolVersion) {
        throw "Manifest protocol $($manifest.protocol) is newer than installer $($script:ProtocolVersion). Update installer first."
    }

    $sourceRoot = Resolve-SourceRoot -Requested $SourceRootRequested
    Write-Info "Source: $sourceRoot"

    $activeTools = @($manifest.tools)
    $adapters = Load-Adapters -SourceRoot $sourceRoot -Tools $activeTools

    Write-Section 'Migration: legacy .ai-rules/rules/ mirror'
    $legacyKeys = @($manifest.files.Keys | Where-Object { $_ -like '.ai-rules/rules/*' })
    $legacyDirty = @()
    foreach ($k in $legacyKeys) {
        $abs = Join-Path $Root $k
        if (Test-Path $abs) {
            $entry = $manifest.files[$k]
            $expected = if ($entry -and $entry.installedHash) { $entry.installedHash } else { '' }
            $actual = Get-FileSha256 $abs
            if ($expected -and ($actual -ne $expected)) { $legacyDirty += $k }
        }
    }
    $proceedLegacy = $true
    if ($legacyDirty.Count -gt 0) {
        Write-Warn "Legacy .ai-rules/rules/ contains user-modified files: $($legacyDirty.Count)"
        $legacyDirty | ForEach-Object { Write-Warn "  $_" }
        if (-not $NonInteractive -and -not $AssumeYes) {
            $proceedLegacy = Read-YesNo 'Delete legacy .ai-rules/rules/ anyway? (your edits will be lost)' $false
        }
    }
    if ($proceedLegacy -and $legacyKeys.Count -gt 0) {
        foreach ($k in $legacyKeys) {
            $abs = Join-Path $Root $k
            if (Test-Path $abs) { Remove-Item -Force $abs -ErrorAction SilentlyContinue }
            $manifest.files.Remove($k)
        }
        $legacyDir = Join-Path $Root '.ai-rules/rules'
        if (Test-Path $legacyDir) {
            $remaining = Get-ChildItem -File -Recurse $legacyDir -ErrorAction SilentlyContinue
            if (-not $remaining -or $remaining.Count -eq 0) {
                Remove-Item -Recurse -Force $legacyDir -ErrorAction SilentlyContinue
                $parent = Join-Path $Root '.ai-rules'
                if (Test-Path $parent) {
                    $parentItems = Get-ChildItem $parent -ErrorAction SilentlyContinue
                    if (-not $parentItems -or $parentItems.Count -eq 0) {
                        Remove-Item -Recurse -Force $parent -ErrorAction SilentlyContinue
                    }
                }
            }
        }
        Write-Info "Migrated: removed $($legacyKeys.Count) legacy .ai-rules/rules/ entries"
    }

    Write-Section 'Detecting user-modified files'
    $dirty = @()
    foreach ($rel in @($manifest.files.Keys)) {
        $abs = Join-Path $Root $rel
        if (-not (Test-Path $abs)) { continue }
        $actual = Get-FileSha256 $abs
        $expected = $manifest.files[$rel].installedHash
        if ($actual -ne $expected) { $dirty += $rel }
    }
    if ($dirty.Count -gt 0) {
        Write-Warn "User-modified files detected: $($dirty.Count)"
        $dirty | ForEach-Object { Write-Warn "  $_" }
        if (-not $NonInteractive -and -not $AssumeYes) {
            $choice = Read-Choice 'Resolution' @('keep', 'take', 'skip') 'keep'
            if ($choice -eq 'keep') {
                # Keep mine: mark these as userModified so future updates skip them
                foreach ($d in $dirty) { $manifest.files[$d]['userModified'] = $true }
            }
            elseif ($choice -eq 'skip') {
                # Skip update for these paths — keep them in manifest as-is but do not re-write
                Write-Info 'Will keep user edits; they will be re-overwritten only if you pass take.'
                foreach ($d in $dirty) { $manifest.files[$d]['userModified'] = $true }
            }
            # take — proceed with overwrite (default behavior of place)
        }
        else {
            # Non-interactive default: keep
            foreach ($d in $dirty) { $manifest.files[$d]['userModified'] = $true }
        }
    }

    # Rescan
    $foreign = Invoke-ScanForeign -Root $Root -ActiveTools $activeTools -Manifest $manifest -Adapters $adapters
    $integrations = Invoke-ScanIntegrations -Root $Root
    $manifest.foreignFiles = $foreign
    $manifest.integrations = $integrations

    # Re-place for all files (skipping userModified)
    # Approach: put places into manifest; for userModified, preserve entry but do not overwrite
    $newFiles = [ordered]@{}
    foreach ($k in $manifest.files.Keys) {
        if ($manifest.files[$k].userModified) { $newFiles[$k] = $manifest.files[$k] }
    }
    $manifest.files = $newFiles

    Write-Section 'Place (update)'
    Invoke-PlacePhase -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest
    # Merge userModified preservations (they may have been overwritten by Place if source names collide; guard at place time is not implemented in v1)

    Write-Section 'OpenSpec scaffold (update)'
    Invoke-OpenSpecScaffold -Root $Root -SourceRoot $sourceRoot -Manifest $manifest
    $rescanned = Invoke-ScanIntegrations -Root $Root
    if ($rescanned.Contains('openspec')) {
        $wasScaffolded = $false
        if ($manifest.integrations.Contains('openspec') -and $manifest.integrations['openspec'].Contains('scaffolded')) {
            $wasScaffolded = [bool]$manifest.integrations['openspec']['scaffolded']
        }
        $rescanned['openspec']['scaffolded'] = $wasScaffolded
    }
    $manifest.integrations = $rescanned

    Write-Section 'OpenSpec artefacts (update)'
    Invoke-OpenSpecArtifacts -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Manifest $manifest

    Write-Section 'OpenSpec project.md (update / 1C autodetect)'
    Invoke-OpenSpecProjectMd -Root $Root -Manifest $manifest

    Write-Section 'MCP (update)'
    Invoke-McpPhase -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest

    Write-Section 'AGENTS.md (update)'
    Update-AgentsMd -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest

    Write-Section 'Root templates (update)'
    Place-RootTemplates -Root $Root -SourceRoot $sourceRoot -Manifest $manifest

    Write-Section '.dev.env (update — placed only if missing)'
    Place-DevEnv -Root $Root -SourceRoot $sourceRoot -Manifest $manifest

    $manifest.updatedAt = [datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $manifest.lastChannel = $script:LastChannel
    $manifest.version = Get-SourceVersion -SourceRoot $sourceRoot

    Write-Manifest -Root $Root -Manifest $manifest
    Write-Info 'Update complete.'
}

function Invoke-Add {
    param(
        [string]$Root,
        [string]$SourceRootRequested,
        [string]$NewTool
    )
    if (-not $NewTool) { throw '-Tool is required for add command' }
    if ($NewTool -notin $script:SupportedTools) { throw "Unknown tool: $NewTool" }

    $manifest = Read-Manifest -Root $Root
    if (-not $manifest) { throw 'No manifest found. Run init first.' }
    if ($manifest.tools -contains $NewTool) {
        Write-Warn "$NewTool already installed. Use 'update' to refresh."
        return
    }

    $sourceRoot = Resolve-SourceRoot -Requested $SourceRootRequested
    $activeTools = @($NewTool)
    $adapters = Load-Adapters -SourceRoot $sourceRoot -Tools $activeTools

    $foreign = Invoke-ScanForeign -Root $Root -ActiveTools $activeTools -Manifest $manifest -Adapters $adapters
    $integrations = $manifest.integrations
    if (-not $integrations) { $integrations = [ordered]@{} }

    Write-Section "Placing files for tool: $NewTool"
    Invoke-PlacePhase -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest
    Invoke-OpenSpecArtifacts -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Manifest $manifest
    Invoke-McpPhase -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest

    # Merge foreign files for this tool into manifest
    foreach ($k in $foreign.Keys) { $manifest.foreignFiles[$k] = $foreign[$k] }

    # Update tools list
    $manifest.tools = @($manifest.tools) + $NewTool

    # Refresh AGENTS.md against the FULL active tool set so that the
    # canonical rules dir resolution sees existing tools too, not only the
    # newly added one.
    $allActive = @($manifest.tools)
    $allAdapters = Load-Adapters -SourceRoot $sourceRoot -Tools $allActive
    Update-AgentsMd -Root $Root -SourceRoot $sourceRoot -ActiveTools $allActive -Adapters $allAdapters -Manifest $manifest

    Place-RootTemplates -Root $Root -SourceRoot $sourceRoot -Manifest $manifest
    Place-DevEnv -Root $Root -SourceRoot $sourceRoot -Manifest $manifest

    $manifest.updatedAt = [datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    Write-Manifest -Root $Root -Manifest $manifest
    Write-Info "Added rules for $NewTool."
}

function Invoke-Remove {
    param(
        [string]$Root,
        [string]$ScopeTool
    )
    $manifest = Read-Manifest -Root $Root
    if (-not $manifest) { Write-Info 'No manifest; nothing to remove.'; return }

    if ($ScopeTool) {
        if ($ScopeTool -notin $manifest.tools) { Write-Warn "$ScopeTool is not installed."; return }
        Write-Info "Removing rules for $ScopeTool only."
        $toolPrefixes = @(".$ScopeTool/")
        # Claude uses `.claude/` but also generates `CLAUDE.md` entry; Codex uses `.codex/` + `AGENTS.md` edits; handle per-tool cleanup:
        switch ($ScopeTool) {
            'claude-code' { $toolPrefixes = @('.claude/', 'CLAUDE.md', '.mcp.json') }
            'codex'       { $toolPrefixes = @('.codex/') }
            'opencode'    { $toolPrefixes = @('.opencode/', 'opencode.json') }
            'kilocode'    { $toolPrefixes = @('.kilo/', '.kilocode/') }
            'cursor'      { $toolPrefixes = @('.cursor/') }
            'other'       { $toolPrefixes = @('.ai-agent/') }
        }
        $toRemove = @()
        foreach ($rel in @($manifest.files.Keys)) {
            foreach ($p in $toolPrefixes) {
                if ($rel -eq $p -or $rel.StartsWith($p.TrimEnd('/') + '/')) {
                    $toRemove += $rel; break
                }
            }
        }
        foreach ($rel in $toRemove) {
            $abs = Join-Path $Root $rel
            if (Test-Path $abs) { Remove-Item -Force $abs -ErrorAction SilentlyContinue }
            $manifest.files.Remove($rel)
        }
        $manifest.tools = @($manifest.tools | Where-Object { $_ -ne $ScopeTool })
        if ($manifest.foreignFiles.Contains($ScopeTool)) { $manifest.foreignFiles.Remove($ScopeTool) }
        # Rebuild AGENTS.md without this tool's contributions (we just strip block if no tools left)
        if ($manifest.tools.Count -eq 0) {
            # Delete AGENTS.md if no non-managed content
            $ap = Join-Path $Root $script:AgentsMdFileName
            if (Test-Path $ap) { Remove-Item -Force $ap; $manifest.files.Remove($script:AgentsMdFileName) }
            Remove-Item -Force (Join-Path $Root $script:ManifestFileName) -ErrorAction SilentlyContinue
            Write-Info "All tools removed; manifest deleted."
            return
        }
        $manifest.updatedAt = [datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
        Write-Manifest -Root $Root -Manifest $manifest
        Write-Info "Removed $ScopeTool ($($toRemove.Count) files)."
    }
    else {
        Write-Info 'Removing all installed files.'
        foreach ($rel in @($manifest.files.Keys)) {
            $abs = Join-Path $Root $rel
            if (Test-Path $abs) { Remove-Item -Force $abs -ErrorAction SilentlyContinue }
        }
        Remove-Item -Force (Join-Path $Root $script:ManifestFileName) -ErrorAction SilentlyContinue
        # Clean up empty per-tool directories
        $cleanupDirs = @('.ai-rules')
        foreach ($t in $manifest.tools) {
            if ($t -eq 'other') { $cleanupDirs += '.ai-agent' }
            else { $cleanupDirs += ".$t" }
        }
        foreach ($rel in $cleanupDirs) {
            $dir = Join-Path $Root $rel
            if (Test-Path $dir) {
                $remaining = Get-ChildItem -Recurse -Force $dir -ErrorAction SilentlyContinue |
                    Where-Object { -not $_.PSIsContainer }
                if (-not $remaining -or $remaining.Count -eq 0) {
                    Remove-Item -Force -Recurse $dir
                }
            }
        }
        Write-Info 'Removal complete.'
    }
}

function Invoke-Doctor {
    param([string]$Root)
    $manifest = Read-Manifest -Root $Root
    if (-not $manifest) { Write-Info 'No manifest found. Nothing installed.'; return }

    Write-Section 'Installed'
    Write-Info "Protocol: $($manifest.protocol)"
    Write-Info "Version: $($manifest.version) (installed $($manifest.installedAt), updated $($manifest.updatedAt))"
    Write-Info "Tools: $(($manifest.tools) -join ', ')"
    Write-Info "Files: $($manifest.files.Count)"
    Write-Info "MCP servers: $(($manifest.mcpServers) -join ', ')"

    Write-Section 'File integrity'
    $verify = Invoke-Verify -Root $Root -Manifest $manifest
    if ($verify.Ok) { Write-Info "All $($verify.Count) files match manifest." }
    else {
        Write-Warn "Mismatches: $($verify.Mismatches.Count)"
        $verify.Mismatches | ForEach-Object { Write-Warn "  $_" }
    }

    Write-Section 'User-modified files'
    $userMod = @()
    foreach ($k in $manifest.files.Keys) {
        if ($manifest.files[$k].userModified) { $userMod += $k }
    }
    if ($userMod.Count -eq 0) { Write-Info 'None.' }
    else { $userMod | ForEach-Object { Write-Info "  $_" } }

    Write-Section 'Foreign files'
    foreach ($t in $manifest.foreignFiles.Keys) {
        $cnt = $manifest.foreignFiles[$t].Count
        if ($cnt -gt 0) { Write-Info "  ${t}: $cnt file(s)" }
    }

    Write-Section 'Integrations'
    if ($manifest.integrations -and $manifest.integrations.Count -gt 0) {
        foreach ($k in $manifest.integrations.Keys) {
            $i = $manifest.integrations[$k]
            if ($i.detected) {
                $tag = if ($i.Contains('scaffolded') -and $i['scaffolded']) { ' [scaffolded]' } else { '' }
                $bundleTag = if ($i.Contains('artifactsBundleVersion') -and $i['artifactsBundleVersion']) { " [artefacts v$($i['artifactsBundleVersion'])]" } else { '' }
                Write-Info "  ${k}: detected ($($i.files.Count) files)$tag$bundleTag"
            }
        }
    }
    else {
        Write-Info '  (none)'
    }
}

function Invoke-Eject {
    param([string]$Root)
    $path = Join-Path $Root $script:ManifestFileName
    if (-not (Test-Path $path)) { Write-Info 'No manifest to eject.'; return }
    Remove-Item -Force $path
    Write-Info 'Manifest removed. Installed files are preserved; future installers will treat them as foreign.'
}

# ============================================================================
# SECTION 14: MAIN DISPATCH
# ============================================================================

$ErrorActionPreference = 'Stop'

if ($ProjectRoot) {
    if (-not (Test-Path $ProjectRoot)) {
        Write-Err "ProjectRoot does not exist: $ProjectRoot"
        exit 1
    }
    $projectRoot = (Resolve-Path $ProjectRoot).Path
}
else {
    $projectRoot = (Get-Location).Path
}

# Normalise -Tools argument: accept comma-separated single string (CLI convenience)
if ($Tools -and $Tools.Count -eq 1 -and $Tools[0].Contains(',')) {
    $Tools = @($Tools[0] -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

try {
    switch ($Command) {
        'init'   { Invoke-Init   -Root $projectRoot -SourceRootRequested $Source -RequestedTools $Tools }
        'update' { Invoke-Update -Root $projectRoot -SourceRootRequested $Source }
        'add'    { Invoke-Add    -Root $projectRoot -SourceRootRequested $Source -NewTool $Tool }
        'remove' { Invoke-Remove -Root $projectRoot -ScopeTool $Tool }
        'doctor' { Invoke-Doctor -Root $projectRoot }
        'eject'  { Invoke-Eject  -Root $projectRoot }
        default  { throw "Unknown command: $Command" }
    }
}
catch {
    Write-Err $_.Exception.Message
    if ($_.ScriptStackTrace) { Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray }
    exit 1
}
