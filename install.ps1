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

.PARAMETER Force
    For `update`: overwrite user-modified files with the current shipped
    version ("take theirs") instead of keeping the user's edits. Without
    -ForcePaths this applies to every drifted file; combine with -ForcePaths
    to force only specific files. Applies uniformly to artefact files, the
    MCP config, the `entry` file (CLAUDE.md), and skill files.

.PARAMETER ForcePaths
    For `update`: restrict -Force to the listed project-relative paths
    (exact match or `*` wildcard, e.g. `.claude/rules/tooling-playbooks.md`
    or `.claude/skills/*`). Implies -Force for the matching paths only; all
    other drifted files keep the user's edits. Multiple paths are passed
    COMMA-separated (PowerShell array syntax):
    `-ForcePaths .claude/skills/*,.claude/rules/forms.md` — a space-separated
    list would bind only the first path.

.PARAMETER McpMode
    How to handle the MCP phase. `auto` (default) — detect an external MCP
    installation (INSTALL.md mode 3 of the MCP distribution) via the
    BASESAI_MCP_GLOBAL_ROOT user environment variable (fallback:
    MCP_GLOBAL_ROOT in the project .dev.env) plus `install.manifest.json`
    in that folder; when found, the installer does NOT touch any tool MCP
    config and instead syncs the `mcp:install_forme` section of
    USER-RULES.md from the actual install artifacts. `managed` — always
    render MCP configs from `content/mcp-servers.json` (legacy behaviour),
    even when an external installation is detected. `external` — require
    the external installation (fail if the env signal or manifest is
    missing) and skip MCP config rendering.

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
    [switch]$AssumeYes,
    [switch]$Force,
    [string[]]$ForcePaths,

    [ValidateSet('auto', 'managed', 'external')]
    [string]$McpMode = 'auto'
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
# Set by Invoke-Update (empty during init): the full set of project-relative
# paths the manifest tracked before the per-update prune. Used by skill
# pruning to tell "a file we shipped and later dropped" (safe to delete) from
# "a file the user dropped into the skill dir themselves" (must be kept).
$script:PreviousFiles = @{}
$script:ForcedThisRun = @()
$script:KeptThisRun = @()

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
            # Nested block — could be dict or array. Skip blank lines first
            # (comment-only lines are blanked by the comment stripper above);
            # otherwise a comment between `key:` and its first child would be
            # mistaken for an empty value and break the nesting detection.
            while ($Parser.Index -lt $Parser.Lines.Count -and (Test-YamlBlank $Parser.Lines[$Parser.Index])) {
                $Parser.Index++
            }
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
    if ($Value -is [System.Collections.IDictionary]) {
        # Nested block-style dict (e.g. OpenCode `permission:` object).
        $lines = @("${Key}:")
        foreach ($subKey in $Value.Keys) {
            $subVal = $Value[$subKey]
            $rendered =
                if ($null -eq $subVal) { '' }
                elseif ($subVal -is [bool]) { if ($subVal) { 'true' } else { 'false' } }
                elseif ($subVal -is [int]) { "$subVal" }
                elseif ($subVal -is [string]) { Format-FrontmatterStringValue $subVal }
                else { [string]$subVal }
            $lines += "  ${subKey}: $rendered"
        }
        return ($lines -join "`n")
    }
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
    $toolsToPermission = if ($Ops.toolsToPermission) { $Ops.toolsToPermission } else { $null }

    # Phase 0: tools array -> permission object (OpenCode).
    # Runs BEFORE keep/drop so it can still read the source `tools` list.
    # Each mapped source tool present in the list -> `grant` (allow);
    # every mapped permission key NOT granted -> `deny`, so a read-only agent
    # (no Write/Edit/Shell in its `tools`) is actually denied edit/bash instead
    # of falling back to OpenCode's permissive default tool set.
    if ($toolsToPermission) {
        $srcKey = if ($toolsToPermission.source) { $toolsToPermission.source } else { 'tools' }
        $grantVal = if ($toolsToPermission.grant) { $toolsToPermission.grant } else { 'allow' }
        $denyVal = if ($toolsToPermission.deny) { $toolsToPermission.deny } else { 'deny' }
        $map = $toolsToPermission.map
        if ($map -and $src.Contains($srcKey)) {
            $granted = @($src[$srcKey])
            $permission = [ordered]@{}
            foreach ($srcTool in $map.Keys) {
                $permKey = $map[$srcTool]
                if ([string]::IsNullOrEmpty([string]$permKey)) { continue }
                $isGranted = $granted -contains $srcTool
                if (-not $permission.Contains($permKey)) {
                    $permission[$permKey] = if ($isGranted) { $grantVal } else { $denyVal }
                }
                elseif ($isGranted) {
                    # Multiple source tools can map to one key (Write/Edit -> edit):
                    # any granting tool wins.
                    $permission[$permKey] = $grantVal
                }
            }
            if ($permission.Keys.Count -gt 0) { $src['permission'] = $permission }
        }
    }

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

# Known UI locale codes that may appear as the trailing path segment of
# INFOBASE_PUBLISH_URL (the web-publication URL is typically
# `http://host/<infobase>/<locale>/`). The HTTP-service endpoint is served
# under `<host>/<infobase>/hs/<service>` — without the locale subpath — so the
# locale must be stripped before substituting into MCP server URL templates.
$script:KnownInfobaseLocales = @(
    'ru', 'en', 'uk', 'kk', 'be', 'de', 'fr', 'es', 'it', 'pl', 'tr',
    'vi', 'zh', 'ja', 'ka', 'lt', 'lv', 'hu', 'bg', 'ro', 'sk', 'cs',
    'sl', 'hr', 'sr', 'et', 'fi', 'sv', 'no', 'da', 'nl', 'pt', 'el',
    'az', 'hy', 'mn', 'mk', 'th', 'ko', 'ar', 'he'
)

function Get-InfobasePublishUrlBase {
    # Reads INFOBASE_PUBLISH_URL from `.dev.env` in the project root and
    # normalizes it for use as the base URL of HTTP services published on the
    # infobase:
    #   1) trim whitespace, strip the trailing slash;
    #   2) strip the trailing `/<locale>` segment when it matches a known
    #      1C UI locale code from $script:KnownInfobaseLocales — HTTP services
    #      live at `<base>/hs/<service>`, not under the locale subpath.
    # Returns an empty string when `.dev.env` is missing, the key is absent,
    # or the value is empty.
    param([string]$Root)

    $envPath = Join-Path $Root $script:DevEnvFileName
    if (-not (Test-Path $envPath)) { return '' }

    $keys = Read-DevEnvKeys -Path $envPath
    if (-not $keys.Contains('INFOBASE_PUBLISH_URL')) { return '' }

    $raw = [string]$keys['INFOBASE_PUBLISH_URL']
    if ([string]::IsNullOrWhiteSpace($raw)) { return '' }

    $url = $raw.Trim().TrimEnd('/')
    if ($url -match '/([a-z]{2,3})$') {
        if ($script:KnownInfobaseLocales -contains $Matches[1]) {
            $url = $url.Substring(0, $url.LastIndexOf('/'))
        }
    }
    return $url
}

function Resolve-McpServerPlaceholders {
    # Substitutes {INFOBASE_PUBLISH_URL} in the `url` field of every server
    # entry that contains it. Mutates the input collection. Returns the list
    # of server ids whose placeholder could not be resolved because
    # INFOBASE_PUBLISH_URL was empty / `.dev.env` was missing — the caller
    # uses this to warn the user.
    param(
        [array]$Servers,
        [string]$InfobaseBase
    )
    $unresolved = @()
    foreach ($s in $Servers) {
        if (-not $s.url) { continue }
        if ($s.url -notmatch '\{INFOBASE_PUBLISH_URL\}') { continue }
        if ($InfobaseBase) {
            $s.url = $s.url.Replace('{INFOBASE_PUBLISH_URL}', $InfobaseBase)
        }
        else {
            $unresolved += $s.id
        }
    }
    return , $unresolved
}

function Test-McpHttpEndpoint {
    # Probes an HTTP endpoint with a short timeout. Used to detect whether a
    # 1C HTTP-service-based MCP server (`1c-data-mcp`) is reachable AND
    # whether the publication allows anonymous access (no Basic auth) — the
    # MCP client does not pass credentials, so HTTP 401 / 403 means the user
    # must reconfigure the publication.
    #
    # Returns a hashtable:
    #   Code      — HTTP status code (int) when the server responded with one,
    #               or the string 'down' when the connection was refused /
    #               timed out, or 'error' on any other client-side failure.
    #   Reachable — $true if any HTTP response was received (even 4xx / 5xx).
    param(
        [string]$Url,
        [int]$TimeoutSec = 3
    )
    try {
        $r = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
        return @{ Code = [int]$r.StatusCode; Reachable = $true }
    }
    catch {
        if ($_.Exception -and $_.Exception.Response) {
            try { return @{ Code = [int]$_.Exception.Response.StatusCode; Reachable = $true } } catch { }
        }
        # No HTTP response was received — the server is not listening, the
        # name does not resolve, or the request timed out. From the
        # installer's point of view all three are equivalent ("endpoint not
        # reachable, not blocking install"), so report a single 'down' code.
        return @{ Code = 'down'; Reachable = $false }
    }
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
    # Claude Code `.mcp.json` schema (https://code.claude.com/docs/en/mcp).
    # Remote servers MUST carry an explicit `"type": "http"` — without it the
    # current Claude Code (VS Code extension and CLI) does not load the server
    # and it silently never appears in the tool list. The documented keys for
    # an HTTP entry are `type`, `url`, `headers`; for a local (stdio) entry
    # `command`, `args`, `env`. The Cursor-only `connection_id` / `description`
    # keys are NOT part of the Claude Code schema, so they are omitted here.
    param([array]$Servers)
    $dict = [ordered]@{}
    foreach ($s in $Servers) {
        $entry = [ordered]@{}
        if ($s.url) {
            $entry['type'] = 'http'
            $entry['url'] = $s.url
            if ($s.headers) { $entry['headers'] = $s.headers }
        }
        elseif ($s.command) {
            $entry['command'] = $s.command
            if ($s.args) { $entry['args'] = $s.args }
            if ($s.env) { $entry['env'] = $s.env }
        }
        $dict[$s.id] = $entry
    }
    $root = [ordered]@{ mcpServers = $dict }
    return (ConvertTo-Json $root -Depth 10)
}

function New-McpConfig-Kilocode {
    # Current Kilo CLI / Kilo Code extension MCP schema (v7.x+, see
    # https://kilo.ai/docs/automate/mcp/using-in-cli):
    #
    #   {
    #     "mcp": {
    #       "<server-id>": {
    #         "type": "remote" | "local",
    #         "url": "...",            # remote only
    #         "command": ["..."],      # local only
    #         "environment": {...},    # local, optional
    #         "headers": {...},        # remote, optional
    #         "enabled": true,
    #         "timeout": 5000          # optional
    #       }
    #     }
    #   }
    #
    # The legacy `.kilocode/mcp.json` with the `mcpServers` dictionary is no
    # longer read by the current Kilo CLI nor by the current Kilo Code VS
    # Code extension — both look up MCP under the top-level `mcp` key of
    # `kilo.json` / `kilo.jsonc` / `.kilo/kilo.json` / `.kilo/kilo.jsonc`
    # (see `adapters/kilocode.yaml > mcp.target`). Writing the legacy
    # `mcpServers` shape into `.kilocode/mcp.json` results in silently empty
    # MCP listings in `/mcps` and during agent tool discovery.
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
            if ($s.env) { $entry['environment'] = $s.env }
        }
        $entry['enabled'] = $true
        $mcp[$s.id] = $entry
    }
    $root = [ordered]@{ mcp = $mcp }
    return (ConvertTo-Json $root -Depth 10)
}

function New-McpConfig-Other {
    # Universal fallback adapter — uses the standard `mcpServers` JSON
    # dictionary schema (same shape as Cursor / Claude Code / Kilo Code), so
    # reuse the same renderer. The output is written to `.ai-agent/mcp.json`
    # per `adapters/other.yaml` and is consumable by any AI client that
    # supports the de-facto `mcpServers` JSON convention.
    param([array]$Servers)
    return New-McpConfig-Cursor $Servers
}

function ConvertTo-OpenCodeMcpKey {
    # OpenCode exposes MCP tools to the model as `<server-key>_<tool>`, taking
    # the key verbatim from the `mcp` object (it only replaces characters
    # outside [a-zA-Z0-9_-] with `_`, it does NOT force a leading letter). Some
    # providers — Moonshot/Kimi in particular — reject any function name that
    # does not start with a letter (`^[a-zA-Z_][a-zA-Z0-9-_]{2,63}$`), so a key
    # like `1c-syntax-checker-mcp` produces `1c-syntax-checker-mcp_syntaxcheck`
    # and the whole request fails with "function name is invalid, must start
    # with a letter". Normalize the well-known `1c`/`1C` prefix to the readable
    # `onec`; guarantee any other non-letter-leading id also starts with a
    # letter. Canonical ids in content/mcp-servers.json stay `1c-...`; only the
    # OpenCode-rendered key changes (tool detection in /checkmcp keys off the
    # bare tool names, not the server prefix, so it is unaffected).
    param([string]$Id)
    $key = $Id
    if ($key -match '^1c(.*)$') { $key = 'onec' + $Matches[1] }
    if ($key -notmatch '^[A-Za-z]') { $key = 'mcp-' + $key }
    return $key
}

function New-McpConfig-OpenCode {
    # OpenCode MCP schema (https://opencode.ai/docs/mcp-servers/). The config
    # goes into `opencode.json` at the PROJECT ROOT (see adapters/opencode.yaml
    # > mcp.target) — NOT `.opencode/opencode.json`, which OpenCode never reads.
    # Each entry is validated with Zod `.strict()`: ONLY the documented keys are
    # allowed, and any unknown key (e.g. `description`, `connection_id`) makes
    # OpenCode reject the whole config so the servers silently never load.
    # Emit only:
    #   remote -> { type: "remote", url, enabled }
    #   local  -> { type: "local",  command: [...], enabled, environment? }
    # `enabled: true` is written explicitly (matches OpenCode's documented
    # examples). `$schema` is added for editor validation; on merge an existing
    # `$schema` is preserved.
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
            if ($s.env) { $entry['environment'] = $s.env }
        }
        $entry['enabled'] = $true
        $mcp[(ConvertTo-OpenCodeMcpKey $s.id)] = $entry
    }
    $root = [ordered]@{ '$schema' = 'https://opencode.ai/config.json'; mcp = $mcp }
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
        'other' { return (New-McpConfig-Other $Servers) }
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

# Return the canonical primary directory for a tool — the leading top-level
# segment of the first defined `<section>.copyTo` (rules → agents → commands
# → skills). Used purely for human-readable progress messages so the user
# sees the real install location (e.g. `.kilo` for Kilo Code, `.ai-agent`
# for the universal `other` fallback) instead of a heuristic `.<tool-id>`
# guess that is wrong for those two adapters.
function Get-AdapterPrimaryDir {
    param([System.Collections.IDictionary]$Adapter)
    if (-not $Adapter) { return '' }
    foreach ($section in @('rules', 'agents', 'commands', 'skills')) {
        if (-not $Adapter.Contains($section)) { continue }
        $copyTo = [string]$Adapter[$section].copyTo
        if (-not $copyTo) { continue }
        # Skip user-scope paths like `~/.codex/prompts/...` — they are not
        # representative of the project-local install location.
        if ($copyTo.StartsWith('~/') -or $copyTo.StartsWith('~\')) { continue }
        $normalized = $copyTo.Replace('\', '/').TrimStart('/')
        $firstSeg = ($normalized -split '/', 2)[0]
        if ($firstSeg) { return $firstSeg }
    }
    return ''
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

# Resolve a manifest key (relative or already-absolute) to an absolute filesystem
# path. Manifest keys for adapters whose `copyTo` starts with `~/` (currently
# codex `commands`) are stored as absolute paths by `Invoke-PlaceArtifactFile`;
# every other key is project-relative. Iteration over `$manifest.files.Keys`
# must go through this helper instead of `Join-Path $Root $rel`, otherwise
# absolute keys turn into garbage like `C:\Project\C:\Users\...` and Test-Path
# falsely reports the files as missing.
function Resolve-ManifestPath {
    param(
        [string]$Root,
        [string]$Rel
    )
    if ([System.IO.Path]::IsPathRooted($Rel)) { return $Rel }
    return (Join-Path $Root $Rel)
}

# Decide whether a drifted (user-modified) target should be overwritten with
# the shipped version on `update`. Driven by the global -Force / -ForcePaths
# switches. -Force with no -ForcePaths forces every path; -ForcePaths narrows
# the force to paths matching one of the patterns (exact match or `*`/`?`
# wildcard via -like). Used uniformly by the artefact, MCP, entry, and skill
# placement paths so the overwrite contract is identical everywhere.
function Test-ForcePath {
    param([string]$Rel)
    # -ForcePaths implies -Force for the listed paths (per the documented
    # contract), so a bare `update -ForcePaths <path>` works without -Force.
    $hasPaths = ($script:ForcePaths -and $script:ForcePaths.Count -gt 0)
    if (-not $script:Force -and -not $hasPaths) { return $false }
    if (-not $hasPaths) { return $true }
    $norm = ([string]$Rel).Replace('\', '/')
    foreach ($pat in $script:ForcePaths) {
        if (-not $pat) { continue }
        $p = ([string]$pat).Replace('\', '/')
        if ($norm -like $p) { return $true }
    }
    return $false
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
    # keep the user's edits and leave the manifest entry unchanged — unless the
    # user asked to force this path (-Force / -ForcePaths), in which case fall
    # through and overwrite with the shipped version.
    if ($Manifest -and $Manifest.files -and $Manifest.files.Contains($TargetRel)) {
        $existing = $Manifest.files[$TargetRel]
        if ($existing -and $existing.userModified -and -not (Test-ForcePath $TargetRel)) {
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
    # Per-file sync of a skill directory. Earlier versions wiped the whole
    # target dir (`Remove-Item -Recurse`) and re-copied, which silently
    # destroyed any user edit inside `<skills>/<name>/` on every update. Now
    # each file follows the same userModified contract as other artefacts:
    #   - a file flagged userModified by a prior `update` is preserved
    #     (unless -Force / -ForcePaths targets it);
    #   - files removed from the source are pruned from disk and manifest,
    #     except user-modified ones, so stale shipped files do not linger.
    param(
        [string]$Root,
        [string]$SourceDir,
        [string]$TargetDir,
        [System.Collections.IDictionary]$Manifest,
        [string]$ContentSource
    )
    $absTarget = Join-Path $Root $TargetDir
    $srcFull = (Resolve-Path $SourceDir).Path.TrimEnd('\', '/')
    $targetRelBase = ($TargetDir -replace '[\\/]+$', '').Replace('\', '/')
    if (-not (Test-Path $absTarget)) {
        New-Item -ItemType Directory -Force -Path $absTarget | Out-Null
    }

    # 1) Copy / refresh every source file unless the user owns it.
    $sourceRels = @{}
    foreach ($sf in Get-ChildItem -Recurse -File -Path $srcFull) {
        $relWithin = $sf.FullName.Substring($srcFull.Length + 1).Replace('\', '/')
        $sourceRels[$relWithin] = $true
        $key = "$targetRelBase/$relWithin"
        if ($Manifest.files.Contains($key)) {
            $skEntry = $Manifest.files[$key]
            if ($skEntry -and $skEntry.userModified -and -not (Test-ForcePath $key)) {
                continue
            }
        }
        $destFull = Join-Path $absTarget $relWithin
        $destDir = Split-Path -Parent $destFull
        if ($destDir -and -not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        }
        Copy-Item -Path $sf.FullName -Destination $destFull -Force
        $Manifest.files[$key] = [ordered]@{
            source        = $ContentSource
            installedHash = (Get-FileSha256 $destFull)
        }
    }

    # 2) Prune files that are no longer shipped, keeping user-modified ones.
    $absTargetFull = (Resolve-Path $absTarget).Path.TrimEnd('\', '/')
    foreach ($ef in Get-ChildItem -Recurse -File -Path $absTargetFull) {
        $relWithin = $ef.FullName.Substring($absTargetFull.Length + 1).Replace('\', '/')
        if ($sourceRels.Contains($relWithin)) { continue }
        $key = "$targetRelBase/$relWithin"
        if ($Manifest.files.Contains($key)) {
            $skEntry = $Manifest.files[$key]
            if ($skEntry -and $skEntry.userModified -and -not (Test-ForcePath $key)) { continue }
            [void]$Manifest.files.Remove($key)
            Remove-Item -Path $ef.FullName -Force -ErrorAction SilentlyContinue
            continue
        }
        # Not currently tracked. Only delete it if WE shipped it in a previous
        # version (recorded in PreviousFiles before the prune); a file the user
        # placed into the skill dir themselves is never tracked and is kept.
        if ($script:PreviousFiles.Contains($key)) {
            Remove-Item -Path $ef.FullName -Force -ErrorAction SilentlyContinue
        }
    }
}

# ============================================================================
# SECTION 7b: SUBAGENT MODEL TIERS
# ============================================================================
#
# Source agent files in content/agents/*.md declare an abstract `modelTier`
# (coding | light) instead of a concrete model name. The concrete model per
# tier is a project setting in .dev.env:
#   SUBAGENT_MODEL_CODING — coding / analysis / review subagents;
#   SUBAGENT_MODEL_LIGHT  — small bounded tasks (e.g. 1c-error-fixer).
# Both are DEFAULTED parameters: an empty value means the model field is
# omitted from the installed agent file and the AI client uses its default
# model. The install never blocks on them.
# On first init (no .dev.env yet) the values are asked interactively once
# during agent placement and persisted into the rendered .dev.env by
# Place-DevEnv. On update they are read from the existing .dev.env silently.

$script:ModelTierKeys = [ordered]@{ coding = 'SUBAGENT_MODEL_CODING'; light = 'SUBAGENT_MODEL_LIGHT' }
$script:ModelTierValues = $null

function Resolve-ModelTiers {
    # Returns an ordered hashtable tier -> concrete model name ('' = client
    # default). Cached for the whole run so the interactive prompt fires once.
    param([string]$Root)
    if ($null -ne $script:ModelTierValues) { return $script:ModelTierValues }
    $vals = [ordered]@{ coding = ''; light = '' }
    $envPath = Join-Path $Root $script:DevEnvFileName
    if (Test-Path $envPath) {
        $keys = Read-DevEnvKeys -Path $envPath
        foreach ($tier in @($script:ModelTierKeys.Keys)) {
            $k = $script:ModelTierKeys[$tier]
            if ($keys.Contains($k)) { $vals[$tier] = ([string]$keys[$k]).Trim() }
        }
    }
    elseif (-not $NonInteractive) {
        Write-Info ''
        Write-Info '  Модели субагентов (Enter — модель AI-клиента по умолчанию):'
        $vals['coding'] = Read-Required 'SUBAGENT_MODEL_CODING (модель для кодинга/анализа/ревью)' ''
        $vals['light']  = Read-Required 'SUBAGENT_MODEL_LIGHT (модель для небольших задач: быстрые исправления, разведка)' ''
    }
    if (-not $vals['coding'] -and -not $vals['light']) {
        Write-Info '  subagent models not set (SUBAGENT_MODEL_CODING / SUBAGENT_MODEL_LIGHT in .dev.env) — agents will use the AI client default model'
    }
    $script:ModelTierValues = $vals
    return $vals
}

function Resolve-AgentModelTier {
    # Replaces the abstract `modelTier` key in an agent's frontmatter with the
    # concrete `modelHint` consumed by the adapters' keep/rename ops (and by
    # the Codex rebuild-toml template). When the tier is unknown or its model
    # is not configured, the key is removed and no model is emitted — the AI
    # client falls back to its default model.
    param(
        [System.Collections.IDictionary]$Frontmatter,
        [string]$Root
    )
    if (-not $Frontmatter -or -not $Frontmatter.Contains('modelTier')) { return $Frontmatter }
    $tiers = Resolve-ModelTiers -Root $Root
    $tier = ([string]$Frontmatter['modelTier']).Trim().ToLowerInvariant()
    $model = if ($tiers.Contains($tier)) { [string]$tiers[$tier] } else { '' }
    $result = [ordered]@{}
    foreach ($k in $Frontmatter.Keys) {
        if ($k -eq 'modelTier') {
            if ($model) { $result['modelHint'] = $model }
            continue
        }
        $result[$k] = $Frontmatter[$k]
    }
    return $result
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
                $agentFm = Resolve-AgentModelTier -Frontmatter $parts.Frontmatter -Root $Root
                $name = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
                $target = Resolve-CopyToPath $copyTpl $name
                Invoke-PlaceArtifactFile -Root $Root -SourcePath $f.FullName `
                    -TargetRel $target -SourceFm $agentFm -SourceBody $parts.Body `
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

        # entry (Claude Code CLAUDE.md and similar). This file frequently holds
        # user project context, so it must NOT be clobbered on update. Same
        # contract as AGENTS.md: write only when the file is missing, or it was
        # installed by us and is byte-identical to what we recorded (lets a
        # changed stub template refresh cleanly); otherwise keep the user's
        # file. -Force / -ForcePaths overrides and rewrites the shipped stub.
        if ($adapter.entry) {
            $etarget = $adapter.entry.target
            $etpl = $adapter.entry.template
            if ($etarget) {
                $eabs = Join-Path $Root $etarget
                $shouldWriteEntry = $false
                if (-not (Test-Path $eabs)) {
                    $shouldWriteEntry = $true
                }
                elseif (Test-ForcePath $etarget) {
                    $shouldWriteEntry = $true
                }
                elseif ($Manifest.files.Contains($etarget)) {
                    $eentry = $Manifest.files[$etarget]
                    if ($eentry -and -not $eentry.userModified -and ((Get-FileSha256 $eabs) -eq $eentry.installedHash)) {
                        $shouldWriteEntry = $true
                    }
                }
                if ($shouldWriteEntry) {
                    Write-TextFile -Path $eabs -Content $etpl
                    $Manifest.files[$etarget] = [ordered]@{
                        source        = 'adapters/' + $tool + '.yaml#entry'
                        installedHash = (Get-FileSha256 $eabs)
                    }
                }
                elseif ((Test-Path $eabs) -and -not $Manifest.files.Contains($etarget)) {
                    # Pre-existing file we did NOT write (user had their own
                    # CLAUDE.md before init). Track it as user-owned so a later
                    # update never mistakes it for our pristine stub and
                    # overwrites it. Recording it as "ours" with its current
                    # hash would do exactly that on the next run.
                    $Manifest.files[$etarget] = [ordered]@{
                        source        = 'adapters/' + $tool + '.yaml#entry'
                        installedHash = (Get-FileSha256 $eabs)
                        userModified  = $true
                    }
                }
                # Skipped but already tracked: leave the manifest entry as-is
                # (preserves userModified and the original installedHash).
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
    $layouts = Resolve-CanonicalArtifactLayouts -ActiveTools $ActiveTools -Adapters $Adapters
    if ($layouts -and $layouts.Contains('rules')) {
        return @{ Dir = [string]$layouts['rules'].Dir; Ext = [string]$layouts['rules'].Ext }
    }
    return $null
}

# Compute the canonical installed location for every artefact section (rules,
# agents, commands, skills) by walking the same priority order as
# Resolve-CanonicalRulesLayout and picking, per section, the highest-priority
# active tool whose adapter declares `<section>.copyTo`. Returns an ordered
# hashtable `{ rules = @{Dir=..; Ext=..}; agents = ...; commands = ...; skills = ... }`.
# Sections without a defined canonical layout are simply omitted.
#
# Used by Update-AgentsMd to rewrite `content/<section>/...` paths in the
# source AGENTS.md to the per-section installed paths so the agent reading
# AGENTS.md from the project root can resolve every link to an existing file.
function Resolve-CanonicalArtifactLayouts {
    param(
        [string[]]$ActiveTools,
        [hashtable]$Adapters
    )
    $layouts = [ordered]@{}
    foreach ($section in @('rules', 'agents', 'commands', 'skills')) {
        foreach ($tool in $script:RulesDirPriority) {
            if ($ActiveTools -notcontains $tool) { continue }
            $adapter = $Adapters[$tool]
            if (-not $adapter -or -not $adapter.Contains($section)) { continue }
            $copyTo = [string]$adapter[$section].copyTo
            if (-not $copyTo) { continue }
            $dir = $copyTo -replace '\{name\}.*$', ''
            $dir = $dir.TrimEnd('/', '\')
            if (-not $dir) { continue }
            $ext = ''
            if ($copyTo -match '\{name\}\.([A-Za-z0-9]+)$') { $ext = $Matches[1] }
            $layouts[$section] = [ordered]@{ Dir = $dir; Ext = $ext; Tool = $tool }
            break
        }
    }
    return $layouts
}

# Rewrite source-repo paths (`content/<section>/<name>.md`,
# `content/skills/<rest>`) to the per-section canonical installed paths. The
# source AGENTS.md is maintained with readable repo-relative paths; the
# installer substitutes them so that the file copied into the project root
# points at files that actually exist on disk for the active tool(s).
#
# Substitutions performed (when the corresponding section layout is known):
#   content/rules/<name>.md     -> <rulesDir>/<name>.<rulesExt>
#   content/agents/<name>.md    -> <agentsDir>/<name>.<agentsExt>
#   content/commands/<name>.md  -> <commandsDir>/<name>.<commandsExt>
#   content/skills/<rest>       -> <skillsDir>/<rest>      (verbatim subpath)
#
# The name regex accepts `<` and `>` so placeholder paths like
# `content/agents/<name>.md` in prose are also rewritten to the installed
# directory but keep the literal `<name>` token.
function Convert-AgentsMdPaths {
    param(
        [string]$Text,
        [System.Collections.IDictionary]$Layouts
    )
    if ([string]::IsNullOrEmpty($Text)) { return $Text }
    if ($null -eq $Layouts -or $Layouts.Count -eq 0) { return $Text }

    $result = $Text
    $sectionRegexes = @(
        @{ Section = 'rules';    Pattern = 'content/rules/([\w\-<>]+)\.md' },
        @{ Section = 'agents';   Pattern = 'content/agents/([\w\-<>]+)\.md' },
        @{ Section = 'commands'; Pattern = 'content/commands/([\w\-<>]+)\.md' }
    )
    foreach ($entry in $sectionRegexes) {
        $section = $entry.Section
        if (-not $Layouts.Contains($section)) { continue }
        $dir = [string]$Layouts[$section].Dir
        if (-not $dir) { continue }
        $ext = [string]$Layouts[$section].Ext
        if (-not $ext) { $ext = 'md' }
        # Closure capture for callback
        $captureDir = $dir
        $captureExt = $ext
        # Pass 1: file references — both directory and extension are rewritten
        # (the extension swap matters for Cursor's `.mdc` rules and Codex's
        # `.toml` agents).
        $result = [regex]::Replace($result, $entry.Pattern, {
            param($m)
            $name = $m.Groups[1].Value
            return "$captureDir/$name.$captureExt"
        })
        # Pass 2: bare directory references like `content/rules/` (used in the
        # source-language policy bullet, etc.). Substring replace is sufficient
        # because pass 1 already consumed all preceding file references.
        $result = $result.Replace("content/$section/", "$captureDir/")
    }

    if ($Layouts.Contains('skills')) {
        $skillsDir = [string]$Layouts['skills'].Dir
        if ($skillsDir) {
            # Skills are copied verbatim — anything after `content/skills/`
            # (SKILL.md, docs/<file>.md, tools/<…>) is preserved by the
            # place phase, so a single prefix swap covers both file
            # references (`content/skills/<name>/SKILL.md`) and bare
            # directory references (`content/skills/`).
            $result = $result.Replace('content/skills/', "$skillsDir/")
        }
    }

    return $result
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

    # Substitute {INFOBASE_PUBLISH_URL} placeholders in server URLs from the
    # project's .dev.env (Place-DevEnv runs earlier in the pipeline so the
    # file is in place by now). Servers whose placeholder cannot be resolved
    # keep the literal placeholder in the rendered config — the user sees a
    # clear TODO marker and a warning telling them what to fill in.
    $infobaseBase = Get-InfobasePublishUrlBase -Root $Root
    $unresolved = Resolve-McpServerPlaceholders -Servers $servers -InfobaseBase $infobaseBase
    if ($unresolved.Count -gt 0) {
        Write-Warn ("  MCP config: следующие серверы используют плейсхолдер {INFOBASE_PUBLISH_URL}, но INFOBASE_PUBLISH_URL в .dev.env пуст: " + ($unresolved -join ', ') + '.')
        Write-Warn '  Заполните INFOBASE_PUBLISH_URL в .dev.env (URL веб-публикации ИБ, напр. http://localhost/<infobase_name>/ru/) и запустите установщик повторно — MCP-конфиг будет перерендерен с подставленным URL.'
    }

    # Probe HTTP-service-based MCP servers (1c-data-mcp). The MCP HTTP client
    # does not pass any Authorization header to /hs/<service>, so the 1C
    # publication MUST allow anonymous access to the endpoint — otherwise the
    # server returns HTTP 401 / 403 and the MCP tools simply do not appear in
    # the agent's session. We probe right after substitution so the user is
    # told at install time, not later when they wonder why `1c-data-mcp` is
    # missing from the tool list.
    foreach ($s in $servers) {
        if (-not $s.url) { continue }
        if ($s.url -match '\{INFOBASE_PUBLISH_URL\}') { continue }  # already warned above
        if ($s.url -notmatch '/hs/') { continue }                   # only HTTP-service URLs
        $probe = Test-McpHttpEndpoint -Url $s.url -TimeoutSec 3
        switch -Regex ([string]$probe.Code) {
            '^401$' {
                Write-Warn ("  MCP config: " + $s.id + " — endpoint " + $s.url + " вернул HTTP 401 (требуется Basic-аутентификация).")
                Write-Warn '  MCP-клиент НЕ передаёт логин/пароль на /hs/<service> — публикация ИБ должна разрешать анонимный доступ к этому HTTP-сервису:'
                Write-Warn '    1. В default.vrd публикации укажите технического пользователя без пароля для HTTP-сервиса:'
                Write-Warn '         <ws publishByDefault="true"/>'
                Write-Warn '         <usr name="МCPПользователь" pwd=""/>   (или <usr name="" pwd=""/> для анонимного доступа, если в ИБ разрешены пустые пароли).'
                Write-Warn '    2. Либо в админке кластера 1С разрешите пустые пароли и заведите пользователя ИБ без пароля с ролью, позволяющей вызов HTTP-сервиса mcp.'
                Write-Warn '    3. После изменения публикации перезапустите веб-сервер (IIS / Apache) и повторите проверку: Invoke-WebRequest "' + $s.url + '" -Method Get -UseBasicParsing.'
            }
            '^403$' {
                Write-Warn ("  MCP config: " + $s.id + " — endpoint " + $s.url + " вернул HTTP 403 (пользователь по умолчанию не имеет прав на HTTP-сервис).")
                Write-Warn '  У пользователя, заданного в публикации (default.vrd → <usr name=...>), должны быть права на роль, разрешающую вызов HTTP-сервиса mcp.'
            }
            '^(200|201|204|405|406|400)$' {
                Write-Info ("  MCP config: " + $s.id + " — endpoint " + $s.url + " отвечает анонимно (HTTP " + $probe.Code + '), OK.')
            }
            '^4\d{2}$' {
                Write-Info ("  MCP config: " + $s.id + " — endpoint " + $s.url + " ответил HTTP " + $probe.Code + '. Проверьте, что HTTP-сервис `mcp` опубликован и не требует аутентификации.')
            }
            '^5\d{2}$' {
                Write-Info ("  MCP config: " + $s.id + " — endpoint " + $s.url + " ответил HTTP " + $probe.Code + ' (ошибка сервера). Проверьте журнал веб-сервера и состояние ИБ.')
            }
            'down' {
                Write-Info ("  MCP config: " + $s.id + " — endpoint " + $s.url + " не отвечает (веб-публикация не запущена или недоступна). Это не блокирует установку: повторите проверку через /checkmcp после старта публикации.")
            }
            default {
                Write-Info ("  MCP config: " + $s.id + " — не удалось проверить endpoint " + $s.url + " (status=" + $probe.Code + '). Это не блокирует установку.')
            }
        }
    }

    $installedIds = @($servers | ForEach-Object { $_.id })
    $Manifest.mcpServers = @($installedIds)

    foreach ($tool in $ActiveTools) {
        $adapter = $Adapters[$tool]
        if (-not $adapter.mcp) { continue }
        $target = $adapter.mcp.target
        if (-not $target) { continue }
        $content = New-McpConfig -ToolId $tool -Servers $servers
        $absTarget = Join-Path $Root $target

        # `mcp.legacyTargets` (set in adapter yaml) — list of relative paths
        # that previous installer versions wrote to and that the current
        # tool no longer reads. Delete them so they do not confuse
        # `/checkmcp` and tool diagnostics, and prune them from the
        # manifest if a prior install recorded them.
        $legacyTargets = @()
        if ($adapter.mcp.PSObject.Properties.Match('legacyTargets').Count -gt 0) {
            $legacyTargets = @($adapter.mcp.legacyTargets)
        }
        elseif ($adapter.mcp -is [System.Collections.IDictionary] -and $adapter.mcp.Contains('legacyTargets')) {
            $legacyTargets = @($adapter.mcp['legacyTargets'])
        }
        foreach ($legacy in $legacyTargets) {
            if (-not $legacy) { continue }
            $absLegacy = Join-Path $Root $legacy
            if (Test-Path $absLegacy) {
                try {
                    Remove-Item -Path $absLegacy -Force -ErrorAction Stop
                    Write-Info "  [$tool] MCP legacy removed: $legacy"
                }
                catch {
                    Write-Info "  [$tool] MCP legacy: не удалось удалить $legacy — $($_.Exception.Message)"
                }
            }
            if ($Manifest.files.Contains($legacy)) { [void]$Manifest.files.Remove($legacy) }
        }

        # Respect user modifications to the MCP config the same way artefact
        # files are respected: if a previous `update` flagged this target as
        # userModified (the user trimmed the server list, switched the format,
        # etc.), DO NOT regenerate it from the full catalog — that would
        # silently bring back servers the user removed. Honour -Force /
        # -ForcePaths as the explicit opt-in to regenerate.
        if ($Manifest.files.Contains($target)) {
            $mcpExisting = $Manifest.files[$target]
            if ($mcpExisting -and $mcpExisting.userModified -and -not (Test-ForcePath $target)) {
                Write-Warn "  [$tool] MCP config: $target помечен как изменённый пользователем — оставляю без изменений (ваш выбор серверов сохранён). Чтобы перегенерировать из полного каталога: update -Force -ForcePaths $target — ваши правки будут заменены."
                continue
            }
        }

        # `mcp.merge: true` (set in adapter yaml) — when the target file is
        # a SHARED tool config (e.g. `.kilo/kilo.json` carries not only MCP
        # but also `instructions`, `skills.paths`, custom permissions),
        # do not overwrite the whole file. Instead read existing JSON,
        # replace the top-level `mcp` key with our rendered value, keep
        # every other key untouched. New file path → write whole rendered
        # JSON as before.
        $mergeRequested = $false
        if ($adapter.mcp.PSObject.Properties.Match('merge').Count -gt 0) {
            $mergeRequested = [bool]$adapter.mcp.merge
        }
        elseif ($adapter.mcp -is [System.Collections.IDictionary] -and $adapter.mcp.Contains('merge')) {
            $mergeRequested = [bool]$adapter.mcp['merge']
        }

        $finalContent = $content
        if ($mergeRequested -and (Test-Path $absTarget)) {
            try {
                $existingRaw = Get-Content -Path $absTarget -Raw -ErrorAction Stop
                $existingObj = $existingRaw | ConvertFrom-Json -ErrorAction Stop
                $renderedObj = $content | ConvertFrom-Json -ErrorAction Stop
                $merged = [ordered]@{}
                # Preserve user keys in their original order, replacing only `mcp`.
                foreach ($prop in $existingObj.PSObject.Properties) {
                    if ($prop.Name -ne 'mcp') { $merged[$prop.Name] = $prop.Value }
                }
                if ($renderedObj.PSObject.Properties.Match('mcp').Count -gt 0) {
                    $merged['mcp'] = $renderedObj.mcp
                }
                # Append any non-`mcp` keys from rendered that the existing file lacks
                # (defensive: future-proofs adapters that emit more than `mcp`).
                foreach ($prop in $renderedObj.PSObject.Properties) {
                    if ($prop.Name -eq 'mcp') { continue }
                    if (-not $merged.Contains($prop.Name)) { $merged[$prop.Name] = $prop.Value }
                }
                $finalContent = (ConvertTo-Json $merged -Depth 20)
            }
            catch {
                Write-Info "  [$tool] MCP merge: existing $target не парсится как JSON — пишу заново. Ошибка: $($_.Exception.Message)"
                $finalContent = $content
            }
        }

        Write-TextFile -Path $absTarget -Content ($finalContent + "`n")
        $mcpEntry = [ordered]@{
            source        = 'content/mcp-servers.json'
            installedHash = (Get-FileSha256 $absTarget)
        }
        # `merged` marks a SHARED config (opencode.json / .kilo/kilo.json) that
        # carries user keys besides `mcp`. On `remove`, such a file must NOT be
        # deleted — only its top-level `mcp` key is stripped (see Invoke-Remove).
        if ($mergeRequested) { $mcpEntry['merged'] = $true }
        $Manifest.files[$target] = $mcpEntry
        Write-Info "  [$tool] MCP config: $target"
    }
}

# ============================================================================
# SECTION 11B: EXTERNAL MCP (INSTALL.md MODE 3 OF THE MCP DISTRIBUTION)
# ============================================================================
#
# When the MCP servers were installed by the MCP distribution's INSTALL.md in
# multi-project mode (mode 3: GLOBAL_ROOT + projects.registry.json + dynamic
# per-project ports + two-level mcp.json), the rules installer must NOT
# overwrite the tool MCP configs with the static catalog from
# `content/mcp-servers.json` — that would break the working per-project port
# layout. Instead it:
#   1. Detects the external installation: user env BASESAI_MCP_GLOBAL_ROOT
#      (fallback: MCP_GLOBAL_ROOT in the project .dev.env) pointing at a
#      folder that contains `install.manifest.json`.
#   2. Resolves every artifact path through the manifest contract
#      (`schema_version` / `artifacts` / `consumers` / `resolution`) — no
#      hardcoded paths, ids, or ports in this consumer. Legacy manifests
#      without `schema_version` fall back to the schema-v1 default contract.
#   3. Skips Invoke-McpPhase entirely (MCP configs untouched) and syncs the
#      `mcp:install_forme` section of USER-RULES.md from the ACTUAL servers
#      found in the resolved global/project mcp.json files.
# No detection signal (or manifest missing) → managed mode, the legacy
# behaviour above. Spec: 1C-RULES-MCP-INTEGRATION-PROPOSAL.md (Comol package).

function Get-EnvFileValue {
    # Reads a single KEY value from a dotenv-style file (.dev.env, config.env)
    # via the shared Read-DevEnvKeys parser. Returns '' when the file or the
    # key is missing. Surrounding quotes are stripped: a path written as
    # MCP_GLOBAL_ROOT="C:\mcp" must still resolve with Test-Path.
    param(
        [string]$FilePath,
        [string]$Key
    )
    $keys = Read-DevEnvKeys -Path $FilePath
    if (-not $keys.Contains($Key)) { return '' }
    $val = ([string]$keys[$Key]).Trim()
    if ($val.Length -ge 2 -and
        (($val.StartsWith('"') -and $val.EndsWith('"')) -or
         ($val.StartsWith("'") -and $val.EndsWith("'")))) {
        $val = $val.Substring(1, $val.Length - 2)
    }
    return $val
}

function Normalize-PathForCompare {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    try {
        return ([System.IO.Path]::GetFullPath($Path)).TrimEnd('\', '/').ToLowerInvariant()
    }
    catch {
        return $Path.Trim().TrimEnd('\', '/').ToLowerInvariant()
    }
}

function Read-JsonFile {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path $Path)) { return $null }
    $raw = Read-TextFile $Path
    try { return ($raw | ConvertFrom-Json) } catch { return $null }
}

# Default manifest contract (schema_version 1). Used as the fallback for
# legacy manifests and as the merge base: a manifest only has to declare the
# keys it overrides.
function Get-DefaultMcpManifestContract {
    return [ordered]@{
        schema_version = 1
        artifacts      = [ordered]@{
            registry      = [ordered]@{
                path        = 'projects.registry.json'
                description = 'Multi-project index: id, label, path_code, mcp_root, ports, containers, mcp_cursor'
            }
            global_config = [ordered]@{
                path        = 'config.env'
                description = 'Shared API keys, IMAGE_TAG'
            }
            help_config   = [ordered]@{
                path_pattern = 'help_*/config.env'
                description  = 'PORT_HELP, PATH_1C_BIN per help_* folder under GLOBAL_ROOT'
            }
            ssl_config    = [ordered]@{
                path_pattern = 'ssl_*/config.env'
                description  = 'PORT_SSL, SSL_VERSION per ssl_* folder under GLOBAL_ROOT'
            }
        }
        consumers      = [ordered]@{
            cursor_global_mcp  = [ordered]@{
                path        = '%USERPROFILE%/.cursor/mcp.json'
                scope       = 'global'
                description = 'Help, SSL, Templates, Syntax, CodeChecker — actual id, url, description'
            }
            cursor_project_mcp = [ordered]@{
                primary_path_pattern  = '{path_code}/.cursor/mcp.json'
                fallback_path_pattern = '{mcp_root}/.cursor/mcp.json'
                scope                 = 'per-project'
                description           = 'Code and Graph metadata MCP for workspace'
            }
            project_dev_env    = [ordered]@{
                path_pattern = '{path_code}/.dev.env'
                keys         = @('MCP_GLOBAL_ROOT')
                description  = 'Fallback env signal for external MCP detection'
            }
            project_mcp_config = [ordered]@{
                path_pattern = '{mcp_root}/config.env'
                description  = 'PATH_METADATA, PATH_CODE, PATH_BASES (reference)'
            }
        }
        resolution     = [ordered]@{
            project_match = [ordered]@{
                source  = 'registry'
                field   = 'path_code'
                compare = 'workspace_root_normalized'
            }
            detection     = [ordered]@{
                entry_env        = 'BASESAI_MCP_GLOBAL_ROOT'
                fallback_env_key = 'MCP_GLOBAL_ROOT'
                manifest_file    = 'install.manifest.json'
            }
        }
    }
}

function Merge-McpManifestContractNode {
    param(
        $Default,
        $Override
    )
    if ($null -eq $Override) { return $Default }
    $result = [ordered]@{}
    foreach ($key in $Default.Keys) {
        $defVal = $Default[$key]
        $ovVal = $null
        if ($Override.PSObject.Properties.Name -contains $key) {
            $ovVal = $Override.$key
        }
        if ($defVal -is [System.Collections.IDictionary] -and $null -ne $ovVal) {
            $result[$key] = Merge-McpManifestContractNode -Default $defVal -Override $ovVal
        }
        elseif ($null -ne $ovVal -and "$ovVal" -ne '') {
            $result[$key] = $ovVal
        }
        else {
            $result[$key] = $defVal
        }
    }
    foreach ($prop in $Override.PSObject.Properties) {
        if (-not $result.Contains($prop.Name)) {
            $result[$prop.Name] = $prop.Value
        }
    }
    return $result
}

# Merge the contract declared inside install.manifest.json over the schema-v1
# defaults. A $null manifest (or one without contract sections) yields the
# pure defaults — that is the legacy-manifest path.
function Get-McpManifestContract {
    param($Manifest)
    $defaults = Get-DefaultMcpManifestContract
    if (-not $Manifest) { return $defaults }
    $schemaVer = 1
    if ($Manifest.PSObject.Properties.Name -contains 'schema_version' -and $Manifest.schema_version) {
        $schemaVer = [int]$Manifest.schema_version
    }
    $contract = [ordered]@{ schema_version = $schemaVer }
    foreach ($section in @('artifacts', 'consumers', 'resolution')) {
        $defSection = $defaults[$section]
        $manSection = $null
        if ($Manifest.PSObject.Properties.Name -contains $section) {
            $manSection = $Manifest.$section
        }
        $merged = [ordered]@{}
        foreach ($key in $defSection.Keys) {
            $ov = $null
            if ($manSection -and $manSection.PSObject.Properties.Name -contains $key) {
                $ov = $manSection.$key
            }
            $merged[$key] = Merge-McpManifestContractNode -Default $defSection[$key] -Override $ov
        }
        if ($manSection) {
            foreach ($prop in $manSection.PSObject.Properties) {
                if (-not $merged.Contains($prop.Name)) {
                    $merged[$prop.Name] = $prop.Value
                }
            }
        }
        $contract[$section] = $merged
    }
    return $contract
}

function Expand-McpManifestPath {
    # Substitutes %USERPROFILE%, {global_root}, {path_code}, {mcp_root} in a
    # contract path pattern. Relative results resolve under GLOBAL_ROOT.
    param(
        [string]$Pattern,
        [string]$GlobalRoot,
        [string]$ProjectRoot,
        $Project
    )
    if ([string]::IsNullOrWhiteSpace($Pattern)) { return '' }
    $pathCode = if ($Project -and $Project.path_code) { [string]$Project.path_code } else { $ProjectRoot }
    $mcpRoot = if ($Project -and $Project.mcp_root) { [string]$Project.mcp_root } else { '' }
    # Plain string replacement on purpose: substituted values are Windows
    # paths that regex replacement would mishandle ($, \ tokens).
    $expanded = $Pattern.
        Replace('%USERPROFILE%', [Environment]::GetFolderPath('UserProfile')).
        Replace('{global_root}', $GlobalRoot).
        Replace('{path_code}', $pathCode).
        Replace('{mcp_root}', $mcpRoot)
    if (-not [System.IO.Path]::IsPathRooted($expanded)) {
        $expanded = Join-Path $GlobalRoot $expanded
    }
    return $expanded
}

function Resolve-McpArtifactPath {
    param(
        $ArtifactDef,
        [string]$GlobalRoot
    )
    if ($ArtifactDef -and $ArtifactDef.path) {
        $rel = [string]$ArtifactDef.path
        if ([System.IO.Path]::IsPathRooted($rel)) { return $rel }
        return Join-Path $GlobalRoot $rel
    }
    return ''
}

function Resolve-McpConsumerPath {
    # Resolves a consumer path from the contract: explicit `path`, then
    # `primary_path_pattern`, then `fallback_path_pattern`. The first
    # candidate that exists on disk wins; otherwise the first candidate is
    # returned so the caller can report a meaningful missing path.
    param(
        $ConsumerDef,
        [string]$GlobalRoot,
        [string]$ProjectRoot,
        $Project
    )
    $candidates = @()
    foreach ($key in @('path', 'primary_path_pattern', 'fallback_path_pattern')) {
        $pattern = $null
        if ($ConsumerDef -is [System.Collections.IDictionary]) {
            if ($ConsumerDef.Contains($key)) { $pattern = $ConsumerDef[$key] }
        }
        elseif ($ConsumerDef.PSObject.Properties.Name -contains $key) {
            $pattern = $ConsumerDef.$key
        }
        if ($pattern) {
            $candidates += Expand-McpManifestPath -Pattern ([string]$pattern) -GlobalRoot $GlobalRoot -ProjectRoot $ProjectRoot -Project $Project
        }
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    if ($candidates.Count -gt 0) { return $candidates[0] }
    return ''
}

function Get-McpGlobalRootFromEnv {
    param([string]$ProjectRoot)
    $globalRoot = [Environment]::GetEnvironmentVariable('BASESAI_MCP_GLOBAL_ROOT', 'User')
    if (-not $globalRoot) { $globalRoot = $env:BASESAI_MCP_GLOBAL_ROOT }
    if (-not $globalRoot) {
        $globalRoot = Get-EnvFileValue -FilePath (Join-Path $ProjectRoot $script:DevEnvFileName) -Key 'MCP_GLOBAL_ROOT'
    }
    return $globalRoot
}

# Detection: external mode requires BOTH the env signal AND
# `install.manifest.json` inside the folder it points at. Anything else is
# managed mode (legacy behaviour). Returns a hashtable; `Warn` carries an
# optional message for the caller to surface.
function Detect-ExternalMcp {
    param([string]$ProjectRoot)

    $globalRoot = Get-McpGlobalRootFromEnv -ProjectRoot $ProjectRoot
    if ([string]::IsNullOrWhiteSpace($globalRoot)) {
        return @{ Mode = 'managed' }
    }

    $manifestPath = Join-Path $globalRoot 'install.manifest.json'
    if (-not (Test-Path $manifestPath)) {
        return @{
            Mode = 'managed'
            Warn = "Сигнал внешней установки MCP задан (BASESAI_MCP_GLOBAL_ROOT либо MCP_GLOBAL_ROOT в .dev.env: $globalRoot), но install.manifest.json там не найден — fallback на managed MCP (конфиг будет отрендерен из content/mcp-servers.json)."
        }
    }

    $mcpManifest = Read-JsonFile -Path $manifestPath
    $contract = Get-McpManifestContract -Manifest $mcpManifest

    $warnEnvMismatch = $null
    $effectiveRoot = $globalRoot
    if ($mcpManifest -and $mcpManifest.PSObject.Properties.Name -contains 'global_root' -and $mcpManifest.global_root) {
        $effectiveRoot = [string]$mcpManifest.global_root
        if ((Normalize-PathForCompare $effectiveRoot) -ne (Normalize-PathForCompare $globalRoot)) {
            $warnEnvMismatch = "BASESAI_MCP_GLOBAL_ROOT ($globalRoot) не совпадает с manifest.global_root ($effectiveRoot); используется значение из манифеста."
        }
    }

    $registryPath = Resolve-McpArtifactPath -ArtifactDef $contract.artifacts.registry -GlobalRoot $effectiveRoot

    $result = @{
        Mode         = 'external'
        GlobalRoot   = $effectiveRoot
        ManifestPath = $manifestPath
        RegistryPath = $registryPath
        Contract     = $contract
    }
    if ($warnEnvMismatch) { $result['Warn'] = $warnEnvMismatch }
    return $result
}

# Applies the -McpMode CLI override on top of detection.
function Resolve-ExternalMcpMode {
    param([string]$ProjectRoot)
    switch ($script:McpMode) {
        'managed' { return @{ Mode = 'managed' } }
        'external' {
            $det = Detect-ExternalMcp -ProjectRoot $ProjectRoot
            if ($det.Mode -ne 'external') {
                $reason = if ($det.Warn) { $det.Warn } else { 'переменная BASESAI_MCP_GLOBAL_ROOT (или MCP_GLOBAL_ROOT в .dev.env) не задана.' }
                throw "-McpMode external: внешняя установка MCP не обнаружена — $reason"
            }
            return $det
        }
        default {
            $det = Detect-ExternalMcp -ProjectRoot $ProjectRoot
            if ($det.Warn) { Write-Warn "  $($det.Warn)" }
            return $det
        }
    }
}

function Get-RegistryProjectForRoot {
    param(
        $Registry,
        [string]$ProjectRoot,
        $Contract
    )
    if (-not $Registry -or -not ($Registry.PSObject.Properties.Name -contains 'projects') -or -not $Registry.projects) { return $null }
    $matchField = 'path_code'
    if ($Contract -and $Contract.resolution -and $Contract.resolution.project_match -and $Contract.resolution.project_match.field) {
        $matchField = [string]$Contract.resolution.project_match.field
    }
    $normRoot = Normalize-PathForCompare $ProjectRoot
    foreach ($p in $Registry.projects) {
        $fieldVal = $null
        if ($p.PSObject.Properties.Name -contains $matchField) {
            $fieldVal = $p.$matchField
        }
        if (-not $fieldVal) { continue }
        if ((Normalize-PathForCompare $fieldVal) -eq $normRoot) { return $p }
    }
    return $null
}

function Parse-McpJsonServers {
    # Reads ACTUAL server entries from an mcp.json: ids as the user/installer
    # named them, ports parsed from the url — never from constants.
    param([string]$McpJsonPath)
    $result = [ordered]@{}
    if (-not $McpJsonPath -or -not (Test-Path $McpJsonPath)) { return $result }
    $obj = Read-JsonFile -Path $McpJsonPath
    if (-not $obj -or -not ($obj.PSObject.Properties.Name -contains 'mcpServers') -or -not $obj.mcpServers) { return $result }
    foreach ($prop in $obj.mcpServers.PSObject.Properties) {
        $entry = $prop.Value
        $url = if ($entry.PSObject.Properties.Name -contains 'url' -and $entry.url) { [string]$entry.url } else { '' }
        $port = ''
        if ($url -match ':(\d+)(/|$)') { $port = $Matches[1] }
        $result[$prop.Name] = [ordered]@{
            Id          = $prop.Name
            Url         = $url
            Port        = $port
            Description = if ($entry.PSObject.Properties.Name -contains 'description' -and $entry.description) { [string]$entry.description } else { '' }
        }
    }
    return $result
}

function Read-McpPatternConfigs {
    # Expands a `prefix_*/suffix` contract pattern under GLOBAL_ROOT into the
    # list of existing config files (e.g. help_8_3_27/config.env).
    param(
        [string]$GlobalRoot,
        [string]$PathPattern
    )
    $items = @()
    if (-not $GlobalRoot -or -not (Test-Path $GlobalRoot)) { return $items }
    if ($PathPattern -match '^([^*]+)\*/(.+)$') {
        $prefix = $Matches[1]
        $suffix = $Matches[2]
        Get-ChildItem -Directory -Path $GlobalRoot -Filter "${prefix}*" -ErrorAction SilentlyContinue | ForEach-Object {
            $cfg = Join-Path $_.FullName $suffix
            if (Test-Path $cfg) {
                $items += [ordered]@{ Folder = $_.Name; Path = $cfg }
            }
        }
    }
    return $items
}

# Single entry point for reading the external installation: manifest →
# contract → registry + global/project mcp.json + optional help_*/ssl_*
# config.env enrichment. Everything downstream (USER-RULES section,
# .ai-rules.json record) renders from this result only.
function Read-McpInstallArtifacts {
    param(
        [string]$ProjectRoot,
        [string]$GlobalRoot,
        [string]$ManifestPath,
        [string]$RegistryPath,
        $Contract
    )

    $mcpManifest = Read-JsonFile -Path $ManifestPath
    if (-not $Contract) {
        $Contract = Get-McpManifestContract -Manifest $mcpManifest
    }
    if (-not $RegistryPath) {
        $RegistryPath = Resolve-McpArtifactPath -ArtifactDef $Contract.artifacts.registry -GlobalRoot $GlobalRoot
    }

    $registry = Read-JsonFile -Path $RegistryPath
    $project = Get-RegistryProjectForRoot -Registry $registry -ProjectRoot $ProjectRoot -Contract $Contract

    $globalMcpPath = Resolve-McpConsumerPath -ConsumerDef $Contract.consumers.cursor_global_mcp -GlobalRoot $GlobalRoot -ProjectRoot $ProjectRoot -Project $project
    $projectMcpPath = Resolve-McpConsumerPath -ConsumerDef $Contract.consumers.cursor_project_mcp -GlobalRoot $GlobalRoot -ProjectRoot $ProjectRoot -Project $project

    $globalServers = Parse-McpJsonServers -McpJsonPath $globalMcpPath
    $projectServers = Parse-McpJsonServers -McpJsonPath $projectMcpPath

    # Optional enrichment: platform/SSL version suffix + HOST ports from the
    # help_*/ssl_* config.env folders, only when those folders exist. No
    # default port is assumed when the key is absent.
    $helpNotes = @()
    foreach ($item in (Read-McpPatternConfigs -GlobalRoot $GlobalRoot -PathPattern ([string]$Contract.artifacts.help_config.path_pattern))) {
        $p = Get-EnvFileValue -FilePath $item.Path -Key 'PORT_HELP'
        $helpNotes += ("{0}{1}" -f $item.Folder, $(if ($p) { " (PORT_HELP=$p)" } else { '' }))
    }
    foreach ($item in (Read-McpPatternConfigs -GlobalRoot $GlobalRoot -PathPattern ([string]$Contract.artifacts.ssl_config.path_pattern))) {
        $p = Get-EnvFileValue -FilePath $item.Path -Key 'PORT_SSL'
        $helpNotes += ("{0}{1}" -f $item.Folder, $(if ($p) { " (PORT_SSL=$p)" } else { '' }))
    }

    return [ordered]@{
        Manifest       = $mcpManifest
        Contract       = $Contract
        Registry       = $registry
        RegistryPath   = $RegistryPath
        Project        = $project
        GlobalMcpPath  = $globalMcpPath
        ProjectMcpPath = $projectMcpPath
        GlobalServers  = $globalServers
        ProjectServers = $projectServers
        ConfigNotes    = $helpNotes
        GlobalRoot     = $GlobalRoot
    }
}

function Format-McpServerTableRows {
    param([System.Collections.IDictionary]$Servers)
    $lines = New-Object System.Collections.ArrayList
    foreach ($id in $Servers.Keys) {
        $s = $Servers[$id]
        $desc = ($s.Description -replace '\|', '/')
        [void]$lines.Add("| ``$id`` | ``$($s.Url)`` | $desc |")
    }
    if ($lines.Count -eq 0) {
        [void]$lines.Add('| *(нет записей в mcp.json)* | | |')
    }
    return ($lines -join "`n")
}

# Generates / refreshes the block between the `mcp:install_forme` markers in
# USER-RULES.md. Only the block is replaced; everything outside the markers
# is preserved. A `userModified: mcp:install_forme` marker anywhere in the
# file opts the section out of regeneration.
function Update-UserRulesMcpSection {
    param(
        [string]$ProjectRoot,
        [System.Collections.IDictionary]$Artifacts
    )

    $userRulesPath = Join-Path $ProjectRoot $script:UserRulesFileName
    $startMarker = '<!-- mcp:install_forme — generated by 1c-rules from install artifacts; manual edits may be overwritten on update -->'
    $endMarker = '<!-- /mcp:install_forme -->'

    $project = $Artifacts.Project
    $label = if ($project -and $project.label) { $project.label } else { '(не найден в registry)' }
    $projId = if ($project -and $project.id) { $project.id } else { '—' }
    $mcpRoot = if ($project -and $project.mcp_root) { $project.mcp_root } else { '—' }

    $globalRows = Format-McpServerTableRows -Servers $Artifacts.GlobalServers
    $projectRows = New-Object System.Collections.ArrayList
    foreach ($id in $Artifacts.ProjectServers.Keys) {
        $s = $Artifacts.ProjectServers[$id]
        $container = '—'
        if ($project -and ($project.PSObject.Properties.Name -contains 'containers') -and $project.containers) {
            if ($id -match 'code' -and $project.containers.PSObject.Properties.Name -contains 'code' -and $project.containers.code) { $container = $project.containers.code }
            if ($id -match 'graph' -and $project.containers.PSObject.Properties.Name -contains 'graph' -and $project.containers.graph) { $container = $project.containers.graph }
        }
        $desc = ($s.Description -replace '\|', '/')
        [void]$projectRows.Add("| ``$id`` | ``$($s.Url)`` | ``$container`` | ``$mcpRoot`` | $desc |")
    }
    if ($projectRows.Count -eq 0) {
        [void]$projectRows.Add('| *(нет записей в project mcp.json)* | | | | |')
    }

    $manifestVer = ''
    if ($Artifacts.Manifest -and $Artifacts.Manifest.PSObject.Properties.Name -contains 'install_for_me_version' -and $Artifacts.Manifest.install_for_me_version) {
        $manifestVer = $Artifacts.Manifest.install_for_me_version
    }
    $schemaVer = if ($Artifacts.Contract) { $Artifacts.Contract.schema_version } else { 1 }
    $registryPath = if ($Artifacts.RegistryPath) { $Artifacts.RegistryPath } else { '—' }
    $configNotesLine = ''
    if ($Artifacts.ConfigNotes -and @($Artifacts.ConfigNotes).Count -gt 0) {
        $configNotesLine = "`nДополнительно из config.env под GLOBAL_ROOT: " + (@($Artifacts.ConfigNotes) -join ', ') + '.'
    }

    $section = @"
$startMarker
## MCP (внешняя установка через INSTALL.md, режим 3)

### Обнаружение
- Сигнал: ``BASESAI_MCP_GLOBAL_ROOT`` (или ``MCP_GLOBAL_ROOT`` в ``.dev.env``)
- ``install.manifest.json``: найден в ``$($Artifacts.GlobalRoot)``
- ``schema_version``: $schemaVer · ``install_for_me_version``: $manifestVer
- Проект в registry: **$label** (``id``: ``$projId``)

### Контракт манифеста (куда смотреть)
Источник структуры — ``install.manifest.json`` (блоки ``artifacts``, ``consumers``, ``resolution``), не хардкод в потребителе.

| потребитель | путь (разрешённый) |
|-------------|-------------------|
| ``cursor_global_mcp`` | ``$($Artifacts.GlobalMcpPath)`` |
| ``cursor_project_mcp`` | ``$($Artifacts.ProjectMcpPath)`` |
| ``registry`` | ``$registryPath`` |

### Глобальные серверы
Источник: ``$($Artifacts.GlobalMcpPath)`` (из ``consumers.cursor_global_mcp``)

| id (фактический ключ) | url | description |
|-----------------------|-----|-------------|
$globalRows
$configNotesLine
### Проектные серверы
Источник: ``$($Artifacts.ProjectMcpPath)`` + ``$registryPath``

| id | url | Docker container | mcp_root | description |
|----|-----|------------------|----------|-------------|
$($projectRows -join "`n")

### Правило для агента
Глобальные серверы **не дублировать** в проектном ``.cursor/mcp.json``. При ``/checkmcp`` читать ``install.manifest.json`` → разрешать пути по контракту → брать **фактические** id, url и порты из таблиц выше, не шаблон ``content/mcp-servers.json``. Установщик 1c-rules в этом режиме MCP-конфиги не трогает.
$endMarker
"@

    if (-not (Test-Path $userRulesPath)) {
        Write-TextFile -Path $userRulesPath -Content ("# User Rules`n`n$section`n")
        return @{ Updated = $true; Created = $true }
    }

    $existing = Read-TextFile $userRulesPath
    if ($existing -match 'userModified:\s*mcp:install_forme') {
        Write-Warn "  USER-RULES.md: секция mcp:install_forme помечена как userModified — пропускаю регенерацию."
        return @{ Updated = $false; Skipped = 'userModified' }
    }
    if ($existing -match '(?s)<!-- mcp:install_forme.*?<!-- /mcp:install_forme -->') {
        $newContent = [regex]::Replace(
            $existing,
            '(?s)<!-- mcp:install_forme.*?<!-- /mcp:install_forme -->',
            $section.Replace('$', '$$')
        )
    }
    else {
        $newContent = $existing.TrimEnd() + "`n`n" + $section + "`n"
    }

    Write-TextFile -Path $userRulesPath -Content $newContent
    return @{ Updated = $true; Created = $false }
}

# External-mode replacement for Invoke-McpPhase: reads the install artifacts,
# syncs USER-RULES.md, records `integrations.mcp` in .ai-rules.json. Tool MCP
# configs are NOT written and `manifest.mcpServers` is cleared — the external
# installation owns the server list.
function Invoke-ExternalMcpPhase {
    param(
        [string]$ProjectRoot,
        [hashtable]$Detection,
        [System.Collections.IDictionary]$Manifest,
        [string[]]$ActiveTools,
        [hashtable]$Adapters
    )

    $artifacts = Read-McpInstallArtifacts `
        -ProjectRoot $ProjectRoot `
        -GlobalRoot $Detection.GlobalRoot `
        -ManifestPath $Detection.ManifestPath `
        -RegistryPath $Detection.RegistryPath `
        -Contract $Detection.Contract

    if (-not $artifacts.Project) {
        Write-Warn "  External MCP: проект не найден в registry ($($artifacts.RegistryPath)) по path_code = $ProjectRoot. Секция USER-RULES будет без проектных контейнеров — проверьте регистрацию проекта в установке MCP."
    }

    $updateResult = Update-UserRulesMcpSection -ProjectRoot $ProjectRoot -Artifacts $artifacts

    # Keep the manifest hash of USER-RULES.md in sync with what we just wrote,
    # so the next `update` does not flag our own write as a user modification.
    if ($updateResult.Updated -and $Manifest.files.Contains($script:UserRulesFileName)) {
        $entry = $Manifest.files[$script:UserRulesFileName]
        if ($entry -and -not $entry.userModified) {
            $entry['installedHash'] = Get-FileSha256 (Join-Path $ProjectRoot $script:UserRulesFileName)
        }
    }

    if (-not $Manifest.integrations) { $Manifest.integrations = [ordered]@{} }
    $globalIds = @($artifacts.GlobalServers.Keys)
    $projectIds = @($artifacts.ProjectServers.Keys)
    $Manifest.integrations['mcp'] = [ordered]@{
        mode              = 'external'
        schemaVersion     = $artifacts.Contract.schema_version
        contractSource    = 'install.manifest.json'
        manifestPath      = $Detection.ManifestPath
        registryPath      = $artifacts.RegistryPath
        registryProjectId = if ($artifacts.Project -and $artifacts.Project.id) { [string]$artifacts.Project.id } else { '' }
        globalMcpConfig   = $artifacts.GlobalMcpPath
        projectMcpConfig  = $artifacts.ProjectMcpPath
        globalServerIds   = $globalIds
        projectServerIds  = $projectIds
        userRulesSection  = 'mcp:install_forme'
        detectedAt        = [datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    }

    # The external installation owns the MCP configs; the rules installer
    # manages zero servers in this mode (also disables the restart nag —
    # nothing was rewritten).
    $Manifest.mcpServers = @()

    # Untrack the tool MCP targets a previous MANAGED install may have
    # recorded. The files themselves are NOT deleted (they now belong to the
    # external installation), but keeping them in `manifest.files` would make
    # every subsequent update flag them as drifted/user-modified noise, and
    # `remove` would wrongly delete a config we no longer own.
    if ($ActiveTools -and $Adapters) {
        foreach ($tool in $ActiveTools) {
            $adapter = $Adapters[$tool]
            if (-not $adapter -or -not $adapter.mcp) { continue }
            $mcpTarget = $adapter.mcp.target
            if ($mcpTarget -and $Manifest.files.Contains($mcpTarget)) {
                [void]$Manifest.files.Remove($mcpTarget)
                Write-Info "  [$tool] MCP config: $mcpTarget снят с учёта манифеста (принадлежит внешней установке MCP)."
            }
        }
    }

    return @{
        Artifacts    = $artifacts
        UserRules    = $updateResult
        GlobalCount  = $globalIds.Count
        ProjectCount = $projectIds.Count
    }
}

# ============================================================================
# SECTION 12: AGENTS.MD (READABLE COPY + PATH REWRITER)
# ============================================================================
#
# AGENTS.md is shipped as a fully readable file in the source repository,
# using repo-relative paths (`content/rules/<name>.md`, `content/agents/...`,
# `content/skills/...`). The installer copies it into the project root and,
# in the same step, rewrites every `content/<section>/...` path to the
# per-section canonical installed path resolved from the active tool set
# (see Resolve-CanonicalArtifactLayouts + Convert-AgentsMdPaths). The result
# is that every path in the project-root AGENTS.md resolves to an existing
# file for the active tool(s) — no broken links.
#
# Refresh on update is gated on `userModified` (manifest hash match), so user
# edits are preserved. There are no dynamic blocks and no @-imports injected
# for foreign files or SDD integrations — the installer records those in the
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

    # Resolve the canonical installed location for every artefact section
    # (rules / agents / commands / skills) so the readable source AGENTS.md
    # can be rewritten into a project-local file with no broken links.
    $layouts = Resolve-CanonicalArtifactLayouts -ActiveTools $ActiveTools -Adapters $Adapters

    if (-not $layouts -or -not $layouts.Contains('rules')) {
        Write-Warn 'No active tool defines a rules directory; AGENTS.md content/<section>/ paths will not be rewritten.'
        $rulesDir = '{{ rulesDir }}'
        $rulesExt = '{{ rulesExt }}'
    }
    else {
        $rulesDir = [string]$layouts['rules'].Dir
        $rulesExt = [string]$layouts['rules'].Ext
        if (-not $rulesExt) { $rulesExt = 'md' }
    }

    $sourceText = Read-TextFile $sourceAgentsPath
    # 1) Rewrite content/<section>/... → <canonical installed dir>/...
    $rendered = Convert-AgentsMdPaths -Text $sourceText -Layouts $layouts
    # 2) Backward-compat: still substitute the legacy {{ rulesDir }} /
    #    {{ rulesExt }} placeholders for source revisions that pre-date the
    #    rewriter (no-op when the source already uses content/<section>/ paths).
    $rendered = $rendered.Replace('{{ rulesDir }}', $rulesDir).Replace('{{ rulesExt }}', $rulesExt)

    # Copy or refresh only when safe: the file does not exist locally, or it
    # was installed by us previously and has not been user-modified since.
    $shouldRefresh = $false
    if (-not (Test-Path $agentsPath)) {
        $shouldRefresh = $true
    }
    elseif (Test-ForcePath $script:AgentsMdFileName) {
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
        $Manifest.files[$script:AgentsMdFileName] = [ordered]@{
            source        = 'AGENTS.md'
            rulesDir      = $rulesDir
            rulesExt      = $rulesExt
            installedHash = (Get-FileSha256 $agentsPath)
        }
    }
    elseif ((Test-Path $agentsPath) -and -not $Manifest.files.Contains($script:AgentsMdFileName)) {
        # Pre-existing AGENTS.md we did NOT write: track as user-owned.
        # Recording it as "ours" with its current hash would make the next
        # update see "installed by us, unchanged" and overwrite the user's
        # file with the rendered template.
        $Manifest.files[$script:AgentsMdFileName] = [ordered]@{
            source        = 'AGENTS.md'
            rulesDir      = $rulesDir
            rulesExt      = $rulesExt
            installedHash = (Get-FileSha256 $agentsPath)
            userModified  = $true
        }
    }
    # Skipped but already tracked: leave the manifest entry as-is (preserves
    # userModified and the installedHash recorded at the time we wrote it).
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
#   IB_USER, INFOBASE_PUBLISH_URL.
# Defaulted fields (empty = silently fall back to a documented default;
# never re-asked at task time):
#   IB_PASSWORD (empty = no password; /P omitted),
#   LOG_PATH    (empty = $env:TEMP\1cv8.log),
#   SUBAGENT_MODEL_CODING / SUBAGENT_MODEL_LIGHT (empty = AI client default
#   model; see SECTION 7b).

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
        $val = Read-Required 'IB_USER (пусто — без аутентификации, /N опускается)'         '';                                                  if ($val) { $text = Set-DevEnvValue -Text $text -Key 'IB_USER'             -Value $val }
        $val = Read-Required 'IB_PASSWORD (пусто — без пароля, /P опускается; не храните прод-пароли)' '';                                       if ($val) { $text = Set-DevEnvValue -Text $text -Key 'IB_PASSWORD'         -Value $val }
        $val = Read-Required 'LOG_PATH (файл лога Designer''а; пусто — $env:TEMP\1cv8.log)' '';                                                if ($val) { $text = Set-DevEnvValue -Text $text -Key 'LOG_PATH'            -Value $val }
        $val = Read-Required 'INFOBASE_PUBLISH_URL (URL веб-публикации для UI-тестов; пусто — UI-тесты пропускаются)' '';                      if ($val) { $text = Set-DevEnvValue -Text $text -Key 'INFOBASE_PUBLISH_URL' -Value $val }
    }

    # Persist subagent model tiers. The values were either asked once during
    # agent placement (Resolve-ModelTiers, init without .dev.env) or are still
    # unset; ask here only if placement never ran (e.g. degenerate tool set).
    if ($null -eq $script:ModelTierValues -and -not $NonInteractive) {
        Resolve-ModelTiers -Root $Root | Out-Null
    }
    if ($script:ModelTierValues) {
        foreach ($tier in @($script:ModelTierKeys.Keys)) {
            $mval = [string]$script:ModelTierValues[$tier]
            if ($mval) { $text = Set-DevEnvValue -Text $text -Key $script:ModelTierKeys[$tier] -Value $mval }
        }
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
    foreach ($k in @('INFOBASE_PUBLISH_URL')) {
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
    $planDirs = @()
    foreach ($t in $activeTools) {
        $primary = Get-AdapterPrimaryDir $adapters[$t]
        if (-not $primary) { $primary = ".$t" }
        $planDirs += "$t -> $primary/"
    }
    Write-Info ("Will write per-tool files into: " + ($planDirs -join ', '))
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

    # .dev.env must be placed BEFORE the MCP phase because some MCP server
    # URLs in `content/mcp-servers.json` reference {INFOBASE_PUBLISH_URL} —
    # the installer substitutes that placeholder from the freshly-written
    # .dev.env when rendering per-tool MCP configs.
    Write-Section 'Phase 7: .dev.env (project parameters, single source of truth)'
    Place-DevEnv -Root $Root -SourceRoot $sourceRoot -Manifest $manifest

    Write-Section 'Phase 8: MCP'
    $extMcp = Resolve-ExternalMcpMode -ProjectRoot $Root
    if ($extMcp.Mode -eq 'external') {
        Write-Info '  Обнаружена внешняя установка MCP (install.manifest.json) — MCP-конфиги инструментов НЕ изменяются.'
    }
    else {
        Invoke-McpPhase -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest
    }

    Write-Section 'Phase 8b: AGENTS.md'
    Update-AgentsMd -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest

    Write-Section 'Phase 8c: Root templates (USER-RULES.md, memory.md)'
    Place-RootTemplates -Root $Root -SourceRoot $sourceRoot -Manifest $manifest

    # Runs AFTER Place-RootTemplates so the USER-RULES.md template is placed
    # first and the generated section is appended to it (not the other way
    # around, which would suppress the template).
    if ($extMcp.Mode -eq 'external') {
        Write-Section 'Phase 8d: External MCP (USER-RULES.md sync)'
        $extResult = Invoke-ExternalMcpPhase -ProjectRoot $Root -Detection $extMcp -Manifest $manifest -ActiveTools $activeTools -Adapters $adapters
        Write-Info "  MCP: external. Конфиги не тронуты. USER-RULES.md синхронизирован ($($extResult.GlobalCount) глобальных + $($extResult.ProjectCount) проектных серверов)."
    }

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

    Write-RestartRecommendation -ActiveTools $activeTools -McpCount $manifest.mcpServers.Count
}

# Tell the user to restart their AI client so it re-reads the freshly written
# MCP config (and agent definitions). Most clients — OpenCode in particular —
# load these only at startup, so MCP servers and new agents do not appear in an
# already-running session until the client / CLI is restarted.
function Write-RestartRecommendation {
    param(
        [string[]]$ActiveTools,
        [int]$McpCount = 0
    )
    if ($McpCount -le 0) { return }
    Write-Info ""
    Write-Info "ВАЖНО: перезапустите AI-клиент (CLI / IDE), чтобы он перечитал MCP-конфигурацию и определения агентов."
    Write-Info "       MCP-серверы и новые субагенты подхватываются только при старте клиента — без перезапуска они не появятся в текущей сессии."
    if ($ActiveTools -contains 'opencode') {
        Write-Info "       OpenCode: полностью завершите и заново запустите сессию OpenCode (config читается при старте)."
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
        $abs = Resolve-ManifestPath -Root $Root -Rel $rel
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

    # Snapshot every path we currently track, before the per-update prune below
    # drops the non-userModified entries. Skill pruning consults this to avoid
    # deleting files the user added to a skill directory themselves.
    $script:PreviousFiles = @{}
    foreach ($k in $manifest.files.Keys) { $script:PreviousFiles[$k] = $true }

    Write-Section 'Detecting user-modified files'
    $dirty = @()
    foreach ($rel in @($manifest.files.Keys)) {
        $abs = Resolve-ManifestPath -Root $Root -Rel $rel
        if (-not (Test-Path $abs)) { continue }
        $actual = Get-FileSha256 $abs
        $expected = $manifest.files[$rel].installedHash
        if ($actual -ne $expected) { $dirty += $rel }
    }
    # Files force-updated this run ("take theirs"): never flagged userModified,
    # so the place/MCP/entry/skill phases overwrite them with the shipped copy.
    $script:ForcedThisRun = @($dirty | Where-Object { Test-ForcePath $_ })
    $script:KeptThisRun = @()
    if ($dirty.Count -gt 0) {
        Write-Warn "User-modified files detected: $($dirty.Count)"
        $dirty | ForEach-Object {
            $tag = if (Test-ForcePath $_) { '  (will be overwritten: -Force)' } else { '' }
            Write-Warn "  $_$tag"
        }
        # -Force / -ForcePaths is a non-interactive, deterministic decision: the
        # listed paths are overwritten regardless of the interactive prompt.
        # Any remaining drifted file falls back to the interactive/keep logic.
        $undecided = @($dirty | Where-Object { -not (Test-ForcePath $_) })
        if ($undecided.Count -gt 0 -and -not $NonInteractive -and -not $AssumeYes) {
            $choice = Read-Choice 'Resolution for remaining drifted files' @('keep', 'take', 'skip') 'keep'
            if ($choice -eq 'keep' -or $choice -eq 'skip') {
                # Keep mine: mark these as userModified so place/MCP/entry/skill skip them.
                foreach ($d in $undecided) { $manifest.files[$d]['userModified'] = $true }
            }
            elseif ($choice -eq 'take') {
                # Take theirs: also CLEAR the userModified flag set by previous
                # runs, otherwise files flagged earlier would silently stay at
                # their old version despite the explicit "take" answer.
                foreach ($d in $undecided) {
                    if ($manifest.files[$d].Contains('userModified')) {
                        [void]$manifest.files[$d].Remove('userModified')
                    }
                }
            }
        }
        elseif ($undecided.Count -gt 0) {
            # Non-interactive default: keep user edits.
            foreach ($d in $undecided) { $manifest.files[$d]['userModified'] = $true }
        }
        $script:KeptThisRun = @($dirty | Where-Object { $manifest.files[$_] -and $manifest.files[$_].userModified })
    }

    # Rescan
    $foreign = Invoke-ScanForeign -Root $Root -ActiveTools $activeTools -Manifest $manifest -Adapters $adapters
    $integrations = Invoke-ScanIntegrations -Root $Root
    $manifest.foreignFiles = $foreign
    $manifest.integrations = $integrations

    # Re-place for all files (skipping userModified)
    # Approach: put places into manifest; for userModified, preserve entry but do not overwrite
    # AGENTS.md is placed by Update-AgentsMd, not by Invoke-PlacePhase, and its
    # refresh decision needs the previous installedHash from the manifest.
    # Dropping the clean entry here made Update-AgentsMd treat the existing
    # file as user-owned: it was never refreshed and got permanently flagged
    # userModified on every update.
    $newFiles = [ordered]@{}
    foreach ($k in $manifest.files.Keys) {
        if ($manifest.files[$k].userModified -or $k -eq $script:AgentsMdFileName) { $newFiles[$k] = $manifest.files[$k] }
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

    # .dev.env runs before MCP so that {INFOBASE_PUBLISH_URL} placeholders in
    # `content/mcp-servers.json` resolve against the actual project value
    # when MCP configs are re-rendered.
    Write-Section '.dev.env (update — placed only if missing)'
    Place-DevEnv -Root $Root -SourceRoot $sourceRoot -Manifest $manifest

    Write-Section 'MCP (update)'
    $extMcp = Resolve-ExternalMcpMode -ProjectRoot $Root
    if ($extMcp.Mode -eq 'external') {
        Write-Info '  Обнаружена внешняя установка MCP (install.manifest.json) — MCP-конфиги инструментов НЕ изменяются.'
    }
    else {
        Invoke-McpPhase -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest
    }

    Write-Section 'AGENTS.md (update)'
    Update-AgentsMd -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest

    Write-Section 'Root templates (update)'
    Place-RootTemplates -Root $Root -SourceRoot $sourceRoot -Manifest $manifest

    if ($extMcp.Mode -eq 'external') {
        Write-Section 'External MCP (USER-RULES.md sync)'
        $extResult = Invoke-ExternalMcpPhase -ProjectRoot $Root -Detection $extMcp -Manifest $manifest -ActiveTools $activeTools -Adapters $adapters
        Write-Info "  MCP: external. Конфиги не тронуты. USER-RULES.md синхронизирован ($($extResult.GlobalCount) глобальных + $($extResult.ProjectCount) проектных серверов)."
    }

    $manifest.updatedAt = [datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $manifest.lastChannel = $script:LastChannel
    $manifest.version = Get-SourceVersion -SourceRoot $sourceRoot

    Write-Manifest -Root $Root -Manifest $manifest

    Write-Section 'Report'
    Write-Info 'Update complete.'
    $forced = @($script:ForcedThisRun)
    $kept = @($script:KeptThisRun)
    if ($forced.Count -gt 0) {
        Write-Info "  Overwritten with shipped version (-Force): $($forced.Count) file(s)."
    }
    if ($kept.Count -gt 0) {
        Write-Warn "  $($kept.Count) file(s) were LEFT AT THEIR PREVIOUS VERSION because they are user-modified — they did NOT receive this update:"
        $kept | ForEach-Object { Write-Warn "    $_" }
        Write-Warn '  To pull the shipped version for these files, re-run `update -Force` (all of them) or `update -ForcePaths <path>[,<path>...]` (specific files, comma-separated). Your current edits to those files will be replaced.'
    }
    Write-RestartRecommendation -ActiveTools $activeTools -McpCount $manifest.mcpServers.Count
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

    # Place .dev.env BEFORE the MCP phase so {INFOBASE_PUBLISH_URL}
    # placeholders in `content/mcp-servers.json` substitute against the
    # actual project value when rendering the newly-added tool's MCP config.
    Place-DevEnv -Root $Root -SourceRoot $sourceRoot -Manifest $manifest
    $extMcp = Resolve-ExternalMcpMode -ProjectRoot $Root
    if ($extMcp.Mode -eq 'external') {
        Write-Info '  Обнаружена внешняя установка MCP (install.manifest.json) — MCP-конфиг для нового инструмента НЕ создаётся.'
    }
    else {
        Invoke-McpPhase -Root $Root -SourceRoot $sourceRoot -ActiveTools $activeTools -Adapters $adapters -Manifest $manifest
    }

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

    if ($extMcp.Mode -eq 'external') {
        $extResult = Invoke-ExternalMcpPhase -ProjectRoot $Root -Detection $extMcp -Manifest $manifest -ActiveTools $activeTools -Adapters $adapters
        Write-Info "  MCP: external. USER-RULES.md синхронизирован ($($extResult.GlobalCount) глобальных + $($extResult.ProjectCount) проектных серверов)."
    }

    $manifest.updatedAt = [datetime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    Write-Manifest -Root $Root -Manifest $manifest
    Write-Info "Added rules for $NewTool."
    Write-RestartRecommendation -ActiveTools $activeTools -McpCount $manifest.mcpServers.Count
}

# Strip ONLY the top-level `mcp` key from a SHARED tool config that the
# installer deep-merged into (opencode.json / .kilo/kilo.json). Deleting the
# whole file on `remove` would destroy the user's own config (model, theme,
# instructions, skills.paths, permissions…). If after removing `mcp` nothing
# meaningful is left (empty, or only a `$schema` marker the installer added),
# delete the now-pointless file.
function Remove-McpKeyFromConfig {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    try {
        $raw = Get-Content -Path $Path -Raw -ErrorAction Stop
        $obj = $raw | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        # Not valid JSON — do not touch a file we cannot safely parse.
        return
    }
    $kept = [ordered]@{}
    foreach ($prop in $obj.PSObject.Properties) {
        if ($prop.Name -eq 'mcp') { continue }
        $kept[$prop.Name] = $prop.Value
    }
    $meaningful = @($kept.Keys | Where-Object { $_ -ne '$schema' })
    if ($meaningful.Count -eq 0) {
        Remove-Item -Force $Path -ErrorAction SilentlyContinue
        return
    }
    Write-TextFile -Path $Path -Content ((ConvertTo-Json $kept -Depth 20) + "`n")
}

# True when a manifest file entry marks a shared, deep-merged MCP config
# (see Invoke-McpPhase). Such files are stripped, not deleted, on removal.
function Test-MergedMcpEntry {
    param($Entry)
    return ($Entry -is [System.Collections.IDictionary] -and $Entry.Contains('merged') -and $Entry['merged'])
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
            if (Test-MergedMcpEntry $manifest.files[$rel]) {
                # Shared config (opencode.json / .kilo/kilo.json): strip the
                # `mcp` key only, never delete the user's whole config.
                Remove-McpKeyFromConfig -Path $abs
            }
            elseif (Test-Path $abs) {
                Remove-Item -Force $abs -ErrorAction SilentlyContinue
            }
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
            if (Test-MergedMcpEntry $manifest.files[$rel]) {
                # Shared config (opencode.json / .kilo/kilo.json): strip the
                # `mcp` key only, never delete the user's whole config.
                Remove-McpKeyFromConfig -Path $abs
            }
            elseif (Test-Path $abs) {
                Remove-Item -Force $abs -ErrorAction SilentlyContinue
            }
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
            if ($k -eq 'mcp' -and $i -and $i.Contains('mode')) {
                Write-Info "  mcp: mode=$($i['mode'])$(if ($i['mode'] -eq 'external') { " (manifest: $($i['manifestPath']); серверы: $(@($i['globalServerIds']).Count) глоб. + $(@($i['projectServerIds']).Count) проектн.)" })"
                continue
            }
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
