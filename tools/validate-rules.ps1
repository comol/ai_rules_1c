#Requires -Version 5.1
<#
.SYNOPSIS
    Structural validator for the 1c-rules ruleset. Intended for CI and for a
    pre-commit run by maintainers.

.DESCRIPTION
    The ruleset is ~1.4 MB of interlinked Markdown whose consistency is otherwise
    only checked by a human running /doctor. This script makes the mechanical part
    of that check automatic and fast:

      1. Frontmatter - every rule / agent / command / skill file carries the keys
         the adapters in adapters/*.yaml expect, with allowed values only.
         Unknown keys are reported: an adapter that does not list a key in
         keep/drop silently loses it on install.
      2. Cross-references - every `content/...` path mentioned anywhere in the
         ruleset resolves to a file that exists, and every relative Markdown link
         resolves from the file that contains it. A broken reference turns a hard
         gate into a dangling pointer without any visible error.
      3. Section anchors - "<file>.md -> Section" references point at a heading
         that exists in the target file. Reported as warnings: the ruleset also
         uses non-heading anchors (section signs, "A.7"), which cannot be
         resolved mechanically.
      4. Routed standards - every rule in content/rules that carries the
         help-mcp-router marker has its body in the standards directory (the
         1C-docs-mcp corpus, see -StandardsDir), every body there has a
         router, and the two heading trees agree. A router keeps
         its headings and drops its text, so a heading on one side only is
         either a reference resolving to an empty section or a section no
         reference can reach - and neither shows up otherwise, because the
         router parses fine alone. The first retrieval target must match the
         router name; repository URLs must not become body-retrieval fallbacks.
      5. Always-on budget - AGENTS.md stays under a byte ceiling. This is the one
         file loaded into every request; unbounded growth there is a silent,
         permanent cost on every task.
      6. Load-set budgets - a single rule stays under -RuleMaxBytes; the rules a
         typical full-cycle BSL change loads ($hotPathFiles) stay under
         -HotPathMaxBytes; what a subagent reads at start (AGENTS.md +
         subagent-core.md + its own prompt) stays under -SubagentStartMaxBytes.
         Growth of any of them is a per-task token cost, so it has to be a
         visible decision, not drift.

    Generated trees (content/openspec-bundle/) are excluded: they are produced by
    tools/refresh-openspec-bundle.ps1 from the OpenSpec CLI and are not authored
    here. Installed dependencies (node_modules/) are excluded likewise.

    NOTE: this file is deliberately pure ASCII. Windows PowerShell 5.1 reads a
    BOM-less .ps1 as ANSI, which mangles non-ASCII source characters and breaks
    parsing. Unicode characters used in patterns are built with [char] instead.

.PARAMETER Root
    Repository root. Defaults to the parent directory of this script.

.PARAMETER StandardsDir
    Directory holding the bodies of the routed standards (one <stem>.md per
    router). They live outside this repository - in the 1C-docs-mcp corpus,
    data/corpora/1c-standards/content/standards. Resolution order: this
    parameter, the ONEC_STANDARDS_DIR environment variable, a sibling
    MCP_Docs_new checkout next to the rules repository. When none is found the
    router self-checks still run and the body / heading checks are skipped
    with a notice (this is the CI case).

.PARAMETER AgentsMaxBytes
    Byte ceiling for AGENTS.md. Ratchet it downward as the file shrinks; never
    raise it without a deliberate decision.

.PARAMETER RuleMaxBytes
    Byte ceiling for one file under content/rules. Above it, split detail into
    a companion rule loaded on its own trigger.

.PARAMETER HotPathMaxBytes
    Byte ceiling for the combined files a typical full-cycle BSL change loads.
    Ratchet it downward as the set shrinks.

.PARAMETER SubagentStartMaxBytes
    Byte ceiling for AGENTS.md + content/rules/subagent-core.md + the largest
    agent prompt - the context every subagent pays before its first action.

.PARAMETER SkillDescriptionMaxBytes
    Byte ceiling for one skill description. Hosts list every skill description
    in every session, so it is always-on context like AGENTS.md.

.PARAMETER AgentDescriptionMaxBytes
    Byte ceiling for one agent description (listed in every session).

.PARAMETER RuleDescriptionMaxBytes
    Byte ceiling for one rule description (Cursor lists agent-requested rule
    descriptions in every session).

.PARAMETER Strict
    Treat warnings as errors (exit code 1).

.EXAMPLE
    powershell -NoProfile -File tools\validate-rules.ps1
    powershell -NoProfile -File tools\validate-rules.ps1 -Strict
#>
[CmdletBinding()]
param(
    [string]$Root,
    [string]$StandardsDir,
    [int]$AgentsMaxBytes = 11264,
    [int]$RuleMaxBytes = 40960,
    [int]$HotPathMaxBytes = 126976,
    [int]$SubagentStartMaxBytes = 28672,
    [int]$SkillDescriptionMaxBytes = 300,
    [int]$AgentDescriptionMaxBytes = 250,
    [int]$RuleDescriptionMaxBytes = 250,
    [switch]$Strict
)

$ErrorActionPreference = 'Stop'

if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$Root = (Resolve-Path -LiteralPath $Root).Path

# Bodies of the routed standards live outside this repository (the 1C-docs-mcp
# corpus). Resolve the directory once: parameter -> ONEC_STANDARDS_DIR -> a
# sibling MCP_Docs_new checkout -> none (body and heading checks are skipped).
if (-not $StandardsDir) { $StandardsDir = $env:ONEC_STANDARDS_DIR }
if (-not $StandardsDir) {
    $sibling = Join-Path $Root '..\..\MCP_Docs_new\data\corpora\1c-standards\content\standards'
    if (Test-Path -LiteralPath $sibling) { $StandardsDir = (Resolve-Path -LiteralPath $sibling).Path }
}
if ($StandardsDir -and -not (Test-Path -LiteralPath $StandardsDir)) {
    Write-Host ('Standards directory not found, body checks skipped: ' + $StandardsDir) -ForegroundColor Yellow
    $StandardsDir = ''
}
$standardsDir = $StandardsDir
$routerMarker = '<!-- help-mcp-router -->'

$BT    = [string][char]0x60    # backtick
$ARROW = [string][char]0x2192  # right arrow used by the ruleset for anchors

$script:Errors = New-Object System.Collections.ArrayList
$script:Warnings = New-Object System.Collections.ArrayList

function Add-Problem {
    param(
        [ValidateSet('error', 'warning')][string]$Level,
        [string]$File,
        [int]$Line = 0,
        [string]$Message
    )
    $rel = $File
    if ($rel.StartsWith($Root)) { $rel = $rel.Substring($Root.Length).TrimStart('\', '/') }
    $rel = $rel -replace '\\', '/'
    $where = $rel
    if ($Line -gt 0) { $where = $rel + ':' + $Line }
    $entry = $where + ' - ' + $Message
    if ($Level -eq 'error') { [void]$script:Errors.Add($entry) } else { [void]$script:Warnings.Add($entry) }
}

# --------------------------------------------------------------------------
# Frontmatter
# --------------------------------------------------------------------------

function Get-Frontmatter {
    # Minimal top-level YAML reader: "key: value" pairs between the opening and
    # closing "---". Enough for the flat frontmatter this ruleset uses; nested
    # structures are not expected and surface as unknown keys.
    param([string]$Path)

    $lines = [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8)
    if ($lines.Count -eq 0 -or $lines[0].Trim() -ne '---') { return $null }

    $map = [ordered]@{}
    for ($i = 1; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        if ($line.Trim() -eq '---') { return [pscustomobject]@{ Keys = $map; EndLine = $i + 1 } }
        if ($line -match '^\s*#') { continue }
        if ($line -match '^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$') {
            $map[$Matches[1]] = $Matches[2].Trim()
        }
    }
    return $null
}

function Test-Frontmatter {
    param(
        [string]$Path,
        [string[]]$Required,
        [string[]]$Optional,
        [hashtable]$AllowedValues = @{}
    )

    $fm = Get-Frontmatter -Path $Path
    if ($null -eq $fm) {
        Add-Problem -Level error -File $Path -Line 1 -Message 'no closing YAML frontmatter block'
        return
    }

    foreach ($key in $Required) {
        if (-not $fm.Keys.Contains($key)) {
            Add-Problem -Level error -File $Path -Line 1 -Message ("frontmatter: required key '" + $key + "' is missing")
        }
        elseif ([string]::IsNullOrWhiteSpace([string]$fm.Keys[$key])) {
            Add-Problem -Level error -File $Path -Line 1 -Message ("frontmatter: key '" + $key + "' is empty")
        }
    }

    $known = @($Required) + @($Optional)
    foreach ($key in $fm.Keys.Keys) {
        if ($known -notcontains $key) {
            Add-Problem -Level warning -File $Path -Line 1 -Message ("frontmatter: unknown key '" + $key + "' - no adapter lists it in keep/drop, so it is dropped silently on install")
        }
    }

    foreach ($key in $AllowedValues.Keys) {
        if ($fm.Keys.Contains($key)) {
            $value = ([string]$fm.Keys[$key]).Trim('"', "'")
            if ($AllowedValues[$key] -notcontains $value) {
                $allowed = ($AllowedValues[$key] -join ' | ')
                Add-Problem -Level error -File $Path -Line 1 -Message ("frontmatter: '" + $key + "' = '" + $value + "' is not one of: " + $allowed)
            }
        }
    }
}

# --------------------------------------------------------------------------
# File inventory
# --------------------------------------------------------------------------

$excludedDirs = @('openspec-bundle', 'node_modules')

function Get-RulesetFiles {
    param([string]$Subpath, [string]$Filter = '*.md')
    $dir = Join-Path $Root $Subpath
    if (-not (Test-Path -LiteralPath $dir)) { return @() }
    Get-ChildItem -LiteralPath $dir -Filter $Filter -File -Recurse |
        Where-Object {
            $relative = $_.FullName.Substring($Root.Length).TrimStart('\', '/') -replace '\\', '/'
            $hit = $false
            foreach ($skip in $excludedDirs) { if ($relative -like ('*/' + $skip + '/*')) { $hit = $true } }
            -not $hit
        }
}

Write-Host ('1c-rules validator - root: ' + $Root) -ForegroundColor Cyan
Write-Host ''

# --- rules ---------------------------------------------------------------
$ruleFiles = @(Get-RulesetFiles -Subpath 'content/rules')
foreach ($file in $ruleFiles) {
    Test-Frontmatter -Path $file.FullName `
        -Required @('description', 'alwaysApply', 'category') `
        -Optional @('globs') `
        -AllowedValues @{ alwaysApply = @('true', 'false') }
}

# --- agents --------------------------------------------------------------
# Source files declare the abstract "modelTier"; the installer resolves it into
# "modelHint" before the adapters' keep/rename ops run (AGENT-INSTALL.md, Lean
# placement, step 4). A source file carrying "modelHint" or "model" directly has
# skipped that resolution and pins a model name inside the ruleset.
$agentFiles = @(Get-RulesetFiles -Subpath 'content/agents')
foreach ($file in $agentFiles) {
    Test-Frontmatter -Path $file.FullName `
        -Required @('name', 'description', 'modelTier', 'tools', 'isSubagent', 'allowParallel') `
        -Optional @('reasoningEffort') `
        -AllowedValues @{
            modelTier     = @('coding', 'analysis', 'light')
            isSubagent    = @('true', 'false')
            allowParallel = @('true', 'false')
        }

    $fm = Get-Frontmatter -Path $file.FullName
    if ($fm -and ($fm.Keys.Contains('modelHint') -or $fm.Keys.Contains('model'))) {
        Add-Problem -Level error -File $file.FullName -Line 1 -Message 'frontmatter pins a concrete model - source agents declare modelTier only; the installer resolves it from .dev.env'
    }

    if ($fm -and $fm.Keys.Contains('name')) {
        $expected = $file.BaseName
        $declared = ([string]$fm.Keys['name']).Trim('"', "'")
        if ($declared -ne ('1c-' + $expected) -and $declared -ne $expected) {
            Add-Problem -Level warning -File $file.FullName -Line 1 -Message ("frontmatter: name '" + $declared + "' does not match the file name ('" + $expected + "' / '1c-" + $expected + "') - subagents.md maps ids to file names")
        }
    }
}

# --- commands ------------------------------------------------------------
$commandFiles = @(Get-RulesetFiles -Subpath 'content/commands')
foreach ($file in $commandFiles) {
    Test-Frontmatter -Path $file.FullName `
        -Required @('description') `
        -Optional @('argumentHint', 'allowedTools', 'userOnly') `
        -AllowedValues @{ userOnly = @('true', 'false') }
}

# --- skills --------------------------------------------------------------
$skillFiles = @(Get-RulesetFiles -Subpath 'content/skills' -Filter 'SKILL.md')
foreach ($file in $skillFiles) {
    Test-Frontmatter -Path $file.FullName `
        -Required @('name', 'description') `
        -Optional @('license', 'allowed-tools', 'argument-hint', 'metadata')
}

# --------------------------------------------------------------------------
# Cross-references
# --------------------------------------------------------------------------

# Index of every Markdown basename that exists in the repo. A bare "<name>.md"
# reference is accepted when the file exists anywhere - the ruleset legitimately
# points at skill docs, command files and root documents from a rule file.
$mdIndex = New-Object System.Collections.Generic.HashSet[string]
foreach ($f in (Get-ChildItem -LiteralPath $Root -Filter '*.md' -File -Recurse |
        Where-Object {
            $rel = $_.FullName.Substring($Root.Length).TrimStart('\', '/') -replace '\\', '/'
            $rel -notlike '.git/*' -and $rel -notlike 'content/openspec-bundle/*' -and $rel -notlike '*/node_modules/*'
        })) {
    [void]$mdIndex.Add($f.Name.ToLowerInvariant())
}

# Names that are referenced by design and are NOT expected to exist in this repo.
$bareRefWhitelist = @(
    # OpenSpec artifacts - created per change under openspec/changes/<id>/.
    'proposal.md', 'design.md', 'tasks.md', 'spec.md', 'conflict.md', 'project.md',
    # Entry points the installer generates in the TARGET project, per adapter.
    'CLAUDE.md', 'AGENTS.md', 'QWEN.md', 'INSTALL.md',
    # Generic form used when talking about "a skill's SKILL.md".
    'SKILL.md',
    # Legacy file the migration rules deliberately still name so that projects
    # carrying it get migrated. Removing the mention would drop the migration.
    'infobasesettings.md',
    # Created by /build-release in the TARGET project (release changelog).
    'CHANGELOG.md'
) | ForEach-Object { $_.ToLowerInvariant() }

$scanned = @()
$scanned += $ruleFiles
$scanned += $agentFiles
$scanned += $commandFiles
$scanned += @(Get-RulesetFiles -Subpath 'content/skills')
foreach ($name in @('AGENTS.md', 'README.md', 'AGENT-INSTALL.md', 'memory.md', 'LLM-RULES.md')) {
    $path = Join-Path $Root $name
    if (Test-Path -LiteralPath $path) { $scanned += Get-Item -LiteralPath $path }
}

# "content/..." paths mentioned anywhere in the text.
$contentRefPattern = '(content/[A-Za-z0-9._\-]+(?:/[A-Za-z0-9._\-]+)*\.(?:md|ps1|py|json|txt))'
# Windows-style "content\..." references: the ruleset convention is forward
# slashes (portable across tools), so these are flagged; their targets are
# still resolved so a broken one surfaces as an error, not just a style nit.
$contentRefBackslashPattern = '(content\\[A-Za-z0-9._\-]+(?:\\[A-Za-z0-9._\-]+)*\.(?:md|ps1|py|json|txt))'
# Bare "<name>.md" inside backticks - resolved against the file's own directory,
# then against content/rules/ (the ruleset's shorthand for sibling rules).
$bareRefPattern = $BT + '([A-Za-z0-9._\-]+\.md)' + $BT
# "<file>.md -> Section" anchors.
$anchorPattern = $BT + '([A-Za-z0-9._\-/]+\.md)\s*' + $ARROW + '\s*([^' + $BT + ']+)' + $BT
# Relative Markdown links [text](target.md).
$mdLinkPattern = '\]\((?!https?:)([^)#]+\.md)(?:#[^)]*)?\)'
# Routed-standard references: `standards(name="<stem>") [sectionN] [-> "Title"]` - the MCP-call form.
# The stem must be a router in content/rules; the section is checked against the body
# in the standards directory when one is available.
$stdRefPattern = $BT + 'standards\(name="([A-Za-z0-9._\-]+)"\)([^' + $BT + ']*)' + $BT
# Characters stripped before comparing heading text.
$decorationPattern = '[' + $BT + '*_"]'

$headingCache = @{}
function Get-Headings {
    param([string]$Path)
    if ($headingCache.ContainsKey($Path)) { return $headingCache[$Path] }
    $found = New-Object System.Collections.ArrayList
    foreach ($line in [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8)) {
        if ($line -match '^#{1,6}\s+(.+?)\s*$') {
            [void]$found.Add((($Matches[1] -replace $decorationPattern, '').Trim().ToLowerInvariant()))
        }
    }
    $headingCache[$Path] = $found
    return $found
}

foreach ($file in $scanned) {
    $lines = [System.IO.File]::ReadAllLines($file.FullName, [System.Text.Encoding]::UTF8)
    $ownDir = Split-Path -Parent $file.FullName
    $relPath = $file.FullName.Substring($Root.Length).TrimStart('\', '/') -replace '\\', '/'

    # The bare "<name>.md" shorthand is the ruleset's own way of pointing at a
    # sibling rule, so it is only checked inside the ruleset's own prose. Skill
    # docs and installer docs use Markdown filenames as examples and generated
    # names ("input.md", "postanovka-enhanced.md", "AGENTS.md.bak.md"), which are
    # indistinguishable from rule names and would be pure noise here. Fully
    # qualified "content/..." paths and Markdown links stay checked everywhere.
    $checkBareRefs = $relPath -match '^(content/(rules|agents|commands)/|AGENTS\.md$)'

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        $lineNo = $i + 1

        foreach ($m in [regex]::Matches($line, $contentRefPattern)) {
            $target = Join-Path $Root ($m.Groups[1].Value -replace '/', '\')
            if (-not (Test-Path -LiteralPath $target)) {
                Add-Problem -Level error -File $file.FullName -Line $lineNo -Message ('broken reference: ' + $m.Groups[1].Value)
            }
        }

        foreach ($m in [regex]::Matches($line, $contentRefBackslashPattern)) {
            $raw = $m.Groups[1].Value
            $target = Join-Path $Root $raw
            if (-not (Test-Path -LiteralPath $target)) {
                Add-Problem -Level error -File $file.FullName -Line $lineNo -Message ('broken reference (backslash form): ' + $raw)
            }
            else {
                Add-Problem -Level warning -File $file.FullName -Line $lineNo -Message ('backslash path reference: ' + $raw + ' - use forward slashes (ruleset convention, portable across tools)')
            }
        }

        if ($checkBareRefs) {
            foreach ($m in [regex]::Matches($line, $bareRefPattern)) {
                $name = $m.Groups[1].Value
                $key = $name.ToLowerInvariant()
                if ($bareRefWhitelist -contains $key) { continue }
                if (-not $mdIndex.Contains($key)) {
                    Add-Problem -Level error -File $file.FullName -Line $lineNo -Message ('dangling reference: ' + $name + ' - no file with this name exists in the repo')
                    continue
                }
                # Guard against basename false-pass: a bare reference must resolve
                # from the canonical shorthand locations (own directory, sibling
                # rules/commands/agents, repo root) - not merely share a basename
                # with an unrelated file somewhere else in the repo.
                $resolved = $false
                foreach ($dir in @($ownDir, (Join-Path $Root 'content\rules'), (Join-Path $Root 'content\commands'), (Join-Path $Root 'content\agents'), $Root)) {
                    if (Test-Path -LiteralPath (Join-Path $dir $name)) { $resolved = $true; break }
                }
                if (-not $resolved) {
                    Add-Problem -Level warning -File $file.FullName -Line $lineNo -Message ('bare reference resolves only by repo-wide basename: ' + $name + ' - qualify the path (content/...)')
                }
            }
        }

        foreach ($m in [regex]::Matches($line, $mdLinkPattern)) {
            $target = Join-Path $ownDir ($m.Groups[1].Value -replace '/', '\')
            if (-not (Test-Path -LiteralPath $target)) {
                Add-Problem -Level error -File $file.FullName -Line $lineNo -Message ('broken Markdown link: ' + $m.Groups[1].Value)
            }
        }

        foreach ($m in [regex]::Matches($line, $stdRefPattern)) {
            $stem = $m.Groups[1].Value
            $stemRouter = Join-Path $Root ('content\rules\' + $stem + '.md')
            $isRoutedStem = (Test-Path -LiteralPath $stemRouter) -and
                [System.IO.File]::ReadAllText($stemRouter, [System.Text.Encoding]::UTF8).Contains($routerMarker)
            if (-not $isRoutedStem) {
                Add-Problem -Level error -File $file.FullName -Line $lineNo -Message ('standards(name="' + $stem + '") names no routed standard - no router content/rules/' + $stem + '.md carries the help-mcp-router marker')
                continue
            }
            if (-not $standardsDir) { continue }   # bodies unavailable - heading check skipped
            $bodyPath = Join-Path $standardsDir ($stem + '.md')
            if (-not (Test-Path -LiteralPath $bodyPath)) {
                Add-Problem -Level error -File $file.FullName -Line $lineNo -Message ('standards(name="' + $stem + '") has no body ' + $stem + '.md in the standards directory ' + $standardsDir)
                continue
            }
            $rest = $m.Groups[2].Value
            if ($rest -match ($ARROW + '\s*(.+)$')) {
                $section = ($Matches[1] -split $ARROW)[0]
                $section = ($section -replace $decorationPattern, '').Trim().TrimEnd('.', ',', ';').ToLowerInvariant()
                if ($section -and -not ($section -match '[<>]')) {
                    $hit = $false
                    foreach ($heading in (Get-Headings -Path $bodyPath)) {
                        if ($heading -eq $section -or $heading.Contains($section) -or $section.Contains($heading)) { $hit = $true; break }
                    }
                    if (-not $hit) {
                        Add-Problem -Level warning -File $file.FullName -Line $lineNo -Message ("anchor '" + $section + "' not found as a heading in the standards body " + $stem + '.md')
                    }
                }
            }
        }

        foreach ($m in [regex]::Matches($line, $anchorPattern)) {
            $refFile = $m.Groups[1].Value
            $section = $m.Groups[2].Value
            # Nested anchors ("A -> B -> C"): only the first segment is reliably a
            # heading; deeper ones are often list items (A.7, Gate 3a, section 8).
            $section = ($section -split $ARROW)[0]
            $section = ($section -replace $decorationPattern, '').Trim().TrimEnd('.', ',', ';').ToLowerInvariant()
            if (-not $section) { continue }

            # Anchors that are correct but cannot resolve to a heading:
            #   "A.7" / "C.1"  - numbered list items inside AGENTS.md sections
            #   section sign   - numbered sections of a rule file
            #   "<...>"        - placeholders in command / template text
            if ($section -match '^[a-z]\.\d+$') { continue }
            if ($section.StartsWith([string][char]0xA7)) { continue }
            if ($section -match '[<>]') { continue }
            # memory.md and LLM-RULES.md gain their sections at runtime.
            if ($refFile -match '(?i)(memory|LLM-RULES)\.md$') { continue }

            $candidates = @(
                (Join-Path $ownDir ($refFile -replace '/', '\')),
                (Join-Path $Root ($refFile -replace '/', '\')),
                (Join-Path $Root ('content\rules\' + $refFile))
            )
            $targetPath = $null
            foreach ($candidate in $candidates) {
                if (Test-Path -LiteralPath $candidate) { $targetPath = $candidate; break }
            }
            if (-not $targetPath) { continue }  # the path itself is reported above

            $headings = Get-Headings -Path $targetPath
            $hit = $false
            foreach ($heading in $headings) {
                if ($heading -eq $section -or $heading.Contains($section) -or $section.Contains($heading)) { $hit = $true; break }
            }
            if (-not $hit) {
                Add-Problem -Level warning -File $file.FullName -Line $lineNo -Message ("anchor '" + $section + "' not found as a heading in " + $refFile)
            }
        }
    }
}

# --------------------------------------------------------------------------
# Routed standards - router in content/rules <-> body in content/standards
# --------------------------------------------------------------------------
# A routed rule keeps its heading tree and drops its text; the text lives in
# content/standards and is what the 1c-standards collection indexes. The pair
# only works while the two heading trees agree: a heading present in one and
# not the other is either a "<file>.md -> Section" reference that resolves to
# nothing, or a section of the standard no reference can reach. Neither shows
# up anywhere else, because the router parses fine on its own.

function Get-HeadingSet {
    param([string]$Path, [string[]]$Ignore = @())
    $set = New-Object System.Collections.ArrayList
    foreach ($line in [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8)) {
        if ($line -match '^#{2,4}\s+(.+?)\s*$') {
            $title = $Matches[1]
            if ($Ignore -notcontains $title) { [void]$set.Add($title) }
        }
    }
    return $set
}

$scaffold     = @('Where this standard lives', 'Sections')
$routedCount  = 0
if ($standardsDir) {
    Write-Host ('Standards bodies: ' + $standardsDir)
}
else {
    Write-Host 'Standards bodies: not available - body and heading checks skipped (pass -StandardsDir or set ONEC_STANDARDS_DIR)' -ForegroundColor Yellow
}

$routers = @($ruleFiles | Where-Object {
    [System.IO.File]::ReadAllText($_.FullName, [System.Text.Encoding]::UTF8).Contains($routerMarker)
})

foreach ($router in $routers) {
    $routedCount++
    $routerText = [System.IO.File]::ReadAllText($router.FullName, [System.Text.Encoding]::UTF8)
    $retrievalText = $routerText.Substring($routerText.IndexOf($routerMarker) + $routerMarker.Length)
    $retrievalTarget = [regex]::Match($retrievalText, 'standards\(name="([A-Za-z0-9._\-]+)"\)')
    if (-not $retrievalTarget.Success -or $retrievalTarget.Groups[1].Value -ne $router.BaseName) {
        Add-Problem -Level error -File $router.FullName -Message (
            'routed rule must retrieve its own standard by short name: standards(name="' + $router.BaseName + '")')
    }
    if ($routerText -match 'https?://[^\s)<>]*/content/(?:rules|standards)/[^\s)<>]+') {
        Add-Problem -Level error -File $router.FullName -Message (
            'routed standard contains a repository body URL - runtime retrieval must use MCP standards only')
    }
    if (-not $standardsDir) { continue }   # bodies unavailable - heading sync skipped
    $bodyPath = Join-Path $standardsDir $router.Name
    if (-not (Test-Path -LiteralPath $bodyPath)) {
        Add-Problem -Level error -File $router.FullName -Line 1 -Message (
            'routed rule has no body ' + $router.Name + ' in the standards directory ' + $standardsDir +
            ' - the router points at text that is not in the corpus')
        continue
    }

    $routerHeadings = Get-HeadingSet -Path $router.FullName -Ignore $scaffold
    $bodyHeadings   = Get-HeadingSet -Path $bodyPath

    foreach ($h in $routerHeadings) {
        if ($bodyHeadings -notcontains $h) {
            Add-Problem -Level error -File $router.FullName -Message (
                'heading "' + $h + '" has no counterpart in the standards body ' + $router.Name +
                ' - references to it resolve to an empty section')
        }
    }
    foreach ($h in $bodyHeadings) {
        if ($routerHeadings -notcontains $h) {
            Add-Problem -Level error -File $bodyPath -Message (
                'heading "' + $h + '" is missing from the router content/rules/' + $router.Name +
                ' - no reference in the ruleset can reach it')
        }
    }
}

if ($standardsDir) {
    foreach ($body in Get-ChildItem -LiteralPath $standardsDir -Filter *.md -File) {
        if ($body.Name -eq 'README.md') { continue }
        $routerPath = Join-Path (Join-Path $Root 'content/rules') $body.Name
        $isRouter = (Test-Path -LiteralPath $routerPath) -and
            [System.IO.File]::ReadAllText($routerPath, [System.Text.Encoding]::UTF8).Contains($routerMarker)
        if (-not $isRouter) {
            Add-Problem -Level error -File $body.FullName -Line 1 -Message (
                'no routed rule in content/rules refers to this body - an inlined rule must not ' +
                'also live here (one rule, one body), and an unreferenced body is indexed but unreachable')
        }
    }
}

# --------------------------------------------------------------------------
# Script encoding
# --------------------------------------------------------------------------

# Windows PowerShell 5.1 reads a BOM-less .ps1 as ANSI, so a script carrying
# Cyrillic identifiers or literals is mangled before it runs - and the failure
# surfaces as a parse error far from the cause. Every shipped .ps1 with a
# non-ASCII byte must therefore start with a UTF-8 BOM. Pure-ASCII scripts are
# left alone: they read identically either way, and the two test harnesses are
# deliberately ASCII-only.

$psFiles = @(Get-ChildItem -LiteralPath $Root -Recurse -File -Filter '*.ps1' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '\\\.git\\' })
$bomChecked = 0
foreach ($ps in $psFiles) {
    $bytes = [System.IO.File]::ReadAllBytes($ps.FullName)
    $nonAscii = $false
    foreach ($b in $bytes) { if ($b -gt 127) { $nonAscii = $true; break } }
    if (-not $nonAscii) { continue }
    $bomChecked++
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    if (-not $hasBom) {
        Add-Problem -Level error -File $ps.FullName -Message 'non-ASCII .ps1 without a UTF-8 BOM: Windows PowerShell 5.1 reads it as ANSI and mangles the text before parsing. Save it as UTF-8 with BOM, or keep the file pure ASCII.'
    }
}

# --------------------------------------------------------------------------
# Gate scenarios - a rule claims only what it checks
# --------------------------------------------------------------------------
# tools/tests/gate-scenarios.json registers the hard gates of AGENTS.md and the
# acceptance scenarios that exercise them. A gate without a scenario is an
# unchecked claim; a scenario naming an unknown gate or a tool no skill
# documents is dead weight. Both are reported here, so the registry and the
# always-on file cannot drift apart silently.

$scenarioPath = Join-Path $Root 'tools/tests/gate-scenarios.json'
# Arguments the rules explicitly say do not exist (mcp-first-search.md -> Hard rule:
# current Code tools have no grep input). A scenario wiring one grades a defect as a pass.
$retiredArgs = @('grep')
$gateCount = 0
$scenarioCount = 0
if (Test-Path -LiteralPath $scenarioPath) {
    $agentsText = ''
    if (Test-Path -LiteralPath (Join-Path $Root 'AGENTS.md')) {
        $agentsText = [System.IO.File]::ReadAllText((Join-Path $Root 'AGENTS.md'), [System.Text.Encoding]::UTF8)
    }
    $agentsHeadings = New-Object System.Collections.Generic.HashSet[string]
    foreach ($line in ($agentsText -split "`r?`n")) {
        if ($line -match '^#{1,4}\s') { [void]$agentsHeadings.Add($line.TrimEnd()) }
    }
    $skillsText = ''
    foreach ($f in (Get-RulesetFiles -Subpath 'content/skills')) {
        $skillsText += [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8) + "`n"
    }
    $corpus = $null
    try {
        $corpus = [System.IO.File]::ReadAllText($scenarioPath, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    } catch {
        Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: invalid JSON - ' + $_.Exception.Message)
    }
    if ($corpus) {
        $servers = @{}
        foreach ($prop in $corpus.servers.PSObject.Properties) { $servers[$prop.Name] = [string]$prop.Value }
        $gateIds = New-Object System.Collections.Generic.HashSet[string]
        $gateUse = @{}
        if ($corpus.PSObject.Properties['opt_in_servers']) {
            foreach ($alias in @($corpus.opt_in_servers)) {
                if (-not $servers.ContainsKey([string]$alias)) { Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: opt_in_servers names unknown server key ' + $alias) }
            }
        }
        foreach ($gate in @($corpus.gates)) {
            $gateCount++
            $id = [string]$gate.id
            if (-not $gateIds.Add($id)) { Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: duplicate gate id ' + $id) }
            $gateUse[$id] = 0
            $heading = [string]$gate.heading
            if (-not $agentsHeadings.Contains($heading)) {
                Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: gate ' + $id + ' points at a heading AGENTS.md does not have: "' + $heading + '"')
            }
            if (-not [string]$gate.claim) { Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: gate ' + $id + ' has no claim') }
        }
        $scenarioIds = New-Object System.Collections.Generic.HashSet[string]
        foreach ($sc in @($corpus.scenarios)) {
            $scenarioCount++
            $sid = [string]$sc.id
            if (-not $scenarioIds.Add($sid)) { Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: duplicate scenario id ' + $sid) }
            $g = [string]$sc.gate
            if ($gateIds.Contains($g)) { $gateUse[$g]++ } else { Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' names unknown gate ' + $g) }
            if (-not [string]$sc.task) { Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' has no task') }
            if (-not [string]$sc.criteria) { Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' has no criteria') }
            foreach ($step in @($sc.wire)) {
                $srv = [string]$step.server
                $tool = [string]$step.tool
                if (-not $servers.ContainsKey($srv)) { Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' uses unknown server key ' + $srv) }
                if ($step.PSObject.Properties['args'] -and $step.args) {
                    foreach ($argName in @($step.args.PSObject.Properties | ForEach-Object { $_.Name })) {
                        if ($retiredArgs -contains $argName) {
                            Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' sends ' + $tool + '(' + $argName + '=...), an argument the ruleset declares non-existent - the scenario would reward a forbidden call')
                        }
                    }
                }
                if ($skillsText -notmatch ('(?<![A-Za-z0-9_])' + [regex]::Escape($tool) + '(?![A-Za-z0-9_])')) {
                    Add-Problem -Level warning -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' calls ' + $tool + ', which no skill under content/skills documents')
                }
            }
            foreach ($entry in @($sc.forbid)) {
                $parts = ([string]$entry) -split ':', 2
                if ($parts.Count -eq 2 -and $servers.ContainsKey($parts[0]) -and $skillsText -notmatch ('(?<![A-Za-z0-9_])' + [regex]::Escape($parts[1]) + '(?![A-Za-z0-9_])')) {
                    Add-Problem -Level warning -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' forbids ' + $entry + ', which no skill under content/skills documents')
                }
            }
            # "mocks" exposes opt-in servers to the rendered eval case; every
            # server needs a mock under tools/tests/eval-mocks and every tool it
            # narrows to or turns into an error must be a tool of that mock.
            if ($sc.PSObject.Properties['mocks'] -and $sc.mocks) {
                foreach ($prop in @($sc.mocks.PSObject.Properties)) {
                    if (-not $servers.ContainsKey($prop.Name)) {
                        Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' mocks unknown server key ' + $prop.Name)
                        continue
                    }
                    $serverMd = Join-Path $Root ('tools/tests/eval-mocks/' + $servers[$prop.Name] + '/_server.md')
                    if (-not (Test-Path -LiteralPath $serverMd)) {
                        Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' mocks ' + $prop.Name + ', which has no tools/tests/eval-mocks/' + $servers[$prop.Name] + '/_server.md')
                        continue
                    }
                    $toolsLine = [regex]::Match([System.IO.File]::ReadAllText($serverMd, [System.Text.Encoding]::UTF8), '(?m)^tools: \[(.*)\]')
                    $mockTools = @()
                    if ($toolsLine.Success) { $mockTools = @($toolsLine.Groups[1].Value -split ',\s*') }
                    $named = @()
                    if ($prop.Value -and $prop.Value.PSObject.Properties['tools']) { $named += @($prop.Value.tools) }
                    if ($prop.Value -and $prop.Value.PSObject.Properties['errors']) { $named += @($prop.Value.errors.PSObject.Properties | ForEach-Object { $_.Name }) }
                    if ($prop.Value -and $prop.Value.PSObject.Properties['answers']) { $named += @($prop.Value.answers.PSObject.Properties | ForEach-Object { $_.Name }) }
                    foreach ($mockTool in $named) {
                        if ($mockTools -notcontains [string]$mockTool) {
                            Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' mocks ' + $prop.Name + ':' + $mockTool + ', which its mock does not answer')
                        }
                    }
                }
            }
            # "fixtures" names sets under tools/tests/eval-fixtures/sets; "env"
            # holds the .dev.env values the task states, as plain strings.
            if ($sc.PSObject.Properties['fixtures']) {
                foreach ($set in @($sc.fixtures)) {
                    if (-not (Test-Path -LiteralPath (Join-Path $Root ('tools/tests/eval-fixtures/sets/' + [string]$set)))) {
                        Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' names fixture set ' + $set + ', which tools/tests/eval-fixtures/sets does not have')
                    }
                }
            }
            if ($sc.PSObject.Properties['env']) {
                foreach ($prop in @($sc.env.PSObject.Properties)) {
                    if ($prop.Name -notmatch '^[A-Z][A-Z0-9_]*$' -or $prop.Value -isnot [string]) {
                        Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: scenario ' + $sid + ' env ' + $prop.Name + ' must be an upper-case .dev.env key with a string value')
                    }
                }
            }
        }
        foreach ($id in $gateUse.Keys) {
            if ($gateUse[$id] -eq 0) { Add-Problem -Level error -File $scenarioPath -Message ('gate scenarios: gate ' + $id + ' has no scenario - a rule claims only what it checks; add a scenario or drop the gate') }
        }
    }
} else {
    Add-Problem -Level warning -File $scenarioPath -Message 'gate scenarios: corpus missing - the hard gates of AGENTS.md are unchecked claims'
}

# --------------------------------------------------------------------------
# Always-on budget
# --------------------------------------------------------------------------

$agentsPath = Join-Path $Root 'AGENTS.md'
if (Test-Path -LiteralPath $agentsPath) {
    $size = (Get-Item -LiteralPath $agentsPath).Length
    $approxTokens = [math]::Round($size / 3.7)
    Write-Host ('AGENTS.md: {0:N0} bytes (~{1:N0} tokens), ceiling {2:N0}' -f $size, $approxTokens, $AgentsMaxBytes)
    if ($size -gt $AgentsMaxBytes) {
        Add-Problem -Level error -File $agentsPath -Message ('always-on budget exceeded: ' + $size + ' bytes > ' + $AgentsMaxBytes + '. This file is loaded into every request - move detail into an on-demand rule instead of raising the ceiling.')
    }
}

# --------------------------------------------------------------------------
# Load-set budgets
# --------------------------------------------------------------------------

foreach ($file in $ruleFiles) {
    if ($file.Length -gt $RuleMaxBytes) {
        Add-Problem -Level error -File $file.FullName -Message ('rule budget exceeded: ' + $file.Length + ' bytes > ' + $RuleMaxBytes + '. Split detail into a companion rule loaded on its own trigger.')
    }
}

# What a typical full-cycle BSL change loads: triage, MCP policy and router, search,
# standards index, playbooks, memory, gates, delivery and the operation skills of the
# write -> validate path. Keep in sync with the AGENTS.md triggers.
$hotPathFiles = @(
    'AGENTS.md',
    'content/rules/verification-policy.md', 'content/rules/verification-gates.md', 'content/rules/verification-delivery.md',
    'content/rules/mcp-policy.md', 'content/rules/mcp-first-search.md', 'content/rules/coding-standards.md',
    'content/rules/tooling-playbooks.md', 'content/rules/project-memory.md',
    'content/skills/mcp-1c-tools/SKILL.md', 'content/skills/1c-code-search/SKILL.md',
    'content/skills/1c-validate/SKILL.md', 'content/skills/1c-templates-memory/SKILL.md'
)
$hotBytes = 0
foreach ($rel in $hotPathFiles) {
    $path = Join-Path $Root $rel
    if (Test-Path -LiteralPath $path) { $hotBytes += (Get-Item -LiteralPath $path).Length }
    else { Add-Problem -Level error -File $path -Message 'hot-path budget: listed file is missing - update $hotPathFiles' }
}
Write-Host ('Full-cycle load set: {0:N0} bytes (~{1:N0} tokens), ceiling {2:N0}' -f $hotBytes, [math]::Round($hotBytes / 3.7), $HotPathMaxBytes)
if ($hotBytes -gt $HotPathMaxBytes) {
    Add-Problem -Level error -File (Join-Path $Root 'AGENTS.md') -Message ('full-cycle load set exceeded: ' + $hotBytes + ' bytes > ' + $HotPathMaxBytes + '. Deduplicate against the owning rule or move trigger-only detail out of the set.')
}

$corePath = Join-Path $Root 'content/rules/subagent-core.md'
if ((Test-Path -LiteralPath $corePath) -and (Test-Path -LiteralPath $agentsPath) -and $agentFiles.Count -gt 0) {
    $largestAgent = $agentFiles | Sort-Object Length -Descending | Select-Object -First 1
    $startBytes = (Get-Item -LiteralPath $agentsPath).Length + (Get-Item -LiteralPath $corePath).Length + $largestAgent.Length
    Write-Host ('Subagent start set: {0:N0} bytes (~{1:N0} tokens, largest prompt {2}), ceiling {3:N0}' -f $startBytes, [math]::Round($startBytes / 3.7), $largestAgent.Name, $SubagentStartMaxBytes)
    if ($startBytes -gt $SubagentStartMaxBytes) {
        Add-Problem -Level error -File $largestAgent.FullName -Message ('subagent start set exceeded: ' + $startBytes + ' bytes > ' + $SubagentStartMaxBytes + '. Keep shared obligations in subagent-core.md and role detail short.')
    }
}

# --------------------------------------------------------------------------
# Description budgets
# --------------------------------------------------------------------------
# Hosts list skill and agent descriptions (Cursor also agent-requested rule
# descriptions) in every session, so their length is always-on cost exactly
# like AGENTS.md. Get-Frontmatter keeps only the first line of a folded scalar,
# hence the dedicated reader.

function Get-DescriptionText {
    param([string]$Path)
    $lines = [System.IO.File]::ReadAllLines($Path, [System.Text.Encoding]::UTF8)
    if ($lines.Count -eq 0 -or $lines[0].Trim() -ne '---') { return '' }
    $parts = New-Object System.Collections.ArrayList
    $inDescription = $false
    for ($i = 1; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        if ($line.Trim() -eq '---') { break }
        if ($line -match '^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$') {
            if ($inDescription) { break }
            if ($Matches[1] -eq 'description') {
                $inDescription = $true
                $value = $Matches[2].Trim()
                if ($value -notmatch '^[>|][+-]?$') { [void]$parts.Add($value) }
            }
            continue
        }
        if ($inDescription) { [void]$parts.Add($line.Trim()) }
    }
    return (($parts -join ' ').Trim().Trim('"', "'"))
}

$descriptionBudgets = @(
    @{ Kind = 'Skill'; Files = $skillFiles; Max = $SkillDescriptionMaxBytes },
    @{ Kind = 'Agent'; Files = $agentFiles; Max = $AgentDescriptionMaxBytes },
    @{ Kind = 'Rule';  Files = $ruleFiles;  Max = $RuleDescriptionMaxBytes }
)
foreach ($budget in $descriptionBudgets) {
    $total = 0
    foreach ($file in @($budget.Files)) {
        $bytes = [System.Text.Encoding]::UTF8.GetByteCount((Get-DescriptionText -Path $file.FullName))
        $total += $bytes
        if ($bytes -gt $budget.Max) {
            Add-Problem -Level error -File $file.FullName -Line 1 -Message ($budget.Kind.ToLower() + ' description budget exceeded: ' + $bytes + ' bytes > ' + $budget.Max + '. Hosts list it in every session - keep the trigger, move detail into the body.')
        }
    }
    Write-Host ('{0} descriptions: {1:N0} bytes in {2} files, per-file ceiling {3:N0}' -f $budget.Kind, $total, @($budget.Files).Count, $budget.Max)
}

# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

Write-Host ('Checked: {0} rules ({1} routed to the standards corpus), {2} agents, {3} commands, {4} skills, {5} non-ASCII scripts, {6} gates / {7} scenarios.' -f `
    $ruleFiles.Count, $routedCount, $agentFiles.Count, $commandFiles.Count, $skillFiles.Count, $bomChecked, $gateCount, $scenarioCount)
Write-Host ''

if ($script:Warnings.Count -gt 0) {
    Write-Host ('WARNINGS (' + $script:Warnings.Count + '):') -ForegroundColor Yellow
    foreach ($entry in $script:Warnings) { Write-Host ('  ' + $entry) -ForegroundColor Yellow }
    Write-Host ''
}

if ($script:Errors.Count -gt 0) {
    Write-Host ('ERRORS (' + $script:Errors.Count + '):') -ForegroundColor Red
    foreach ($entry in $script:Errors) { Write-Host ('  ' + $entry) -ForegroundColor Red }
    Write-Host ''
    Write-Host 'FAILED' -ForegroundColor Red
    exit 1
}

if ($Strict -and $script:Warnings.Count -gt 0) {
    Write-Host 'FAILED (-Strict: warnings are errors)' -ForegroundColor Red
    exit 1
}

Write-Host 'OK' -ForegroundColor Green
exit 0
