#Requires -Version 5.1
<#
.SYNOPSIS
    Drift guard for the vendored cc-1c-skills PowerShell tools: identical
    copies of shared functions, and functions declared before top-level use.

.DESCRIPTION
    Upstream cc-1c-skills has no shared runtime modules: a helper such as
    Find-ProjectV8Path or Assert-EditAllowed is copied into every script that
    needs it, and upstream keeps the copies in step with a registry of
    "families" (tests/skills/check-inline-drift.mjs). Our local patches
    (.dev.env first, batch verdict, ...) are written into each copy, so a
    re-sync that misses one copy leaves a script that silently behaves like
    upstream again. This script is that guard for our tree.

    Mode 'drift' - every family in the registry:
      * finds every definition of the function in the vendored tree by AST
        ([System.Management.Automation.Language.Parser]::ParseFile,
        FunctionDefinitionAst; nested definitions included), never by
        counting braces;
      * normalizes each copy: Extent.Text with comment tokens removed and
        whitespace collapsed, so comments, indentation and line endings are
        not divergence;
      * groups the copies into variants and compares every copy with the base
        variant - the copy in 'authority' when the family names one, else the
        largest group;
      * a copy outside the base variant is an error unless the registry
        declares that file a deliberate local variant with a reason; a family
        with 'maxVariants' is a ratchet instead (error only when the number of
        variants grows past it);
      * a copy that calls a function the base copy's file defines, but its own
        file does not, is an error (an unresolvable copy fails at run time).
      Output per family: copies, variants, and which files differ.

    Mode 'order' - declared before use: PowerShell binds a function when it
    is called, and sees only definitions that already ran. A function called
    from top-level script code - directly or through the functions that call
    it - whose `function` statement comes later in the file is a runtime
    CommandNotFoundException; inside a try/catch or with a $null fallback it
    is a silent no-op (upstream issue 93). Calls inside trap blocks are not
    checked (they run later, at an unknown point).

    Exit code 1 on any error, 0 otherwise. Warnings (stale declarations,
    families absent from the tree) fail only with -Strict.

    NOTE: this file is deliberately pure ASCII (Windows PowerShell 5.1 reads a
    BOM-less .ps1 as ANSI).

.PARAMETER Mode
    all (default) | drift | order.

.PARAMETER Registry
    Registry JSON. Default: vendored-drift.registry.json next to this script.

.PARAMETER Family
    Only families whose function name matches this wildcard (drift mode).

.PARAMETER Detailed
    Also list the files of the base variant.

.PARAMETER Discover
    List functions defined in two or more files that the registry does not
    cover yet, with their variant counts, then exit 0. Calibration aid.

.PARAMETER Strict
    Treat warnings as errors.

.PARAMETER SelfTest
    Run the guard against small synthetic trees (a whitespace-only difference,
    an undeclared and a declared variant, an unresolvable copy, a direct and a
    transitive use before declaration) and check its verdicts. Independent of
    the real tree; exit 0 when the guard behaves.

.EXAMPLE
    powershell -NoProfile -File tools\tests\vendored-drift.ps1
    powershell -NoProfile -File tools\tests\vendored-drift.ps1 -Mode drift -Family 'Get-EditMode' -Detailed
    powershell -NoProfile -File tools\tests\vendored-drift.ps1 -Discover
    powershell -NoProfile -File tools\tests\vendored-drift.ps1 -SelfTest
#>
[CmdletBinding()]
param(
    [ValidateSet('all', 'drift', 'order')]
    [string]$Mode = 'all',
    [string]$Registry,
    [string]$Family = '*',
    [switch]$Detailed,
    [switch]$Discover,
    [switch]$Strict,
    [switch]$SelfTest
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ---------------------------------------------------------------- self-test

if ($SelfTest) {
    $host_ = (Get-Process -Id $PID).Path
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('1c-rules-drift-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    $enc = New-Object System.Text.UTF8Encoding($false)
    function Write-Fixture([string]$Rel, [string]$Text) {
        $p = Join-Path $tmp $Rel
        New-Item -ItemType Directory -Path (Split-Path $p -Parent) -Force | Out-Null
        [System.IO.File]::WriteAllText($p, $Text, $enc)
    }
    function Invoke-Guard([object]$Reg) {
        $regPath = Join-Path $tmp ('registry-' + [guid]::NewGuid().ToString('N').Substring(0, 6) + '.json')
        [System.IO.File]::WriteAllText($regPath, ($Reg | ConvertTo-Json -Depth 8), $enc)
        $out = & $host_ -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -Registry $regPath 2>&1 | Out-String
        return [pscustomobject]@{ Exit = $LASTEXITCODE; Out = $out }
    }
    function Check([bool]$Ok, [string]$What) {
        if ($Ok) { Write-Host "[PASS] $What" -ForegroundColor Green } else { Write-Host "[FAIL] $What" -ForegroundColor Red; $script:failedSelf++ }
    }
    $script:failedSelf = 0
    try {
        Write-Fixture 'tools/a/scripts/a.ps1' "function Get-Same {`n    param(`$x)  # a comment`n    return `$x + 1`n}`nfunction Helper { 1 }`nfunction Uses-Helper { Helper }`nGet-Same 1`n"
        Write-Fixture 'tools/b/scripts/b.ps1' "function Get-Same {`r`n  param(`$x)`r`n`r`n      return `$x + 1   `r`n}`r`nfunction Uses-Helper { Helper }`r`nLate-Fn`r`nfunction Late-Fn { 1 }`r`nfunction Entry { Later }`r`nEntry`r`nfunction Later { 2 }`r`ntrap { Late-Trap; continue }`r`nfunction Late-Trap { 3 }`r`n"
        Write-Fixture 'tools/c/scripts/c.ps1' "function Get-Same {`n    param(`$x)`n    return `$x + 2`n}`n"
        $root = Join-Path $tmp 'tools'
        $first = Invoke-Guard @{ root = $root; families = @(@{ function = 'Get-Same' }, @{ function = 'Uses-Helper'; authority = 'a/scripts/a.ps1' }) }
        Check ($first.Exit -eq 1) 'divergence, unresolvable copy and late definitions fail the run'
        Check ($first.Out -match 'Get-Same: 3 copies in 3 files, 2 variant') 'comments, indentation and line endings are not divergence'
        Check ($first.Out -match 'c/scripts/c\.ps1:1\s+UNDECLARED') 'an undeclared variant is named by file and line'
        Check ($first.Out -match 'b/scripts/b\.ps1:\d+ calls Helper') 'a copy calling a helper its file lacks is unresolvable'
        Check ($first.Out -match 'function Late-Fn is defined at line 8, but top-level code calls it at line 7') 'a direct use before declaration is caught'
        Check ($first.Out -match 'function Later is defined at line 11, but top-level code calls it at line 10 \(reached through Entry\)') 'a transitive use before declaration is caught'
        Check (-not ($first.Out -match 'Late-Trap')) 'calls inside trap blocks are not checked'
        $second = Invoke-Guard @{
            root = $root
            families = @(@{ function = 'Get-Same'; localVariants = @(@{ files = @('c/scripts/c.ps1'); reason = 'self-test' }) })
            declaredBeforeUse = @{ ignore = @(@{ file = 'b/scripts/b.ps1'; function = 'Late-Fn'; reason = 'self-test' }, @{ file = 'b/scripts/b.ps1'; function = 'Later'; reason = 'self-test' }) }
        }
        Check ($second.Exit -eq 0) 'declared variants and ignored order findings pass'
        Check ($second.Out -match 'declared - self-test') 'a declared variant is reported with its reason'
        $third = Invoke-Guard @{ root = $root; families = @(@{ function = 'Get-Same'; maxVariants = 1 }) }
        Check ($third.Exit -eq 1 -and $third.Out -match 'ratchet allows 1') 'a ratchet fails when variants grow past it'
    } finally {
        Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($script:failedSelf) { Write-Host "Self-test: $($script:failedSelf) check(s) failed." -ForegroundColor Red; exit 1 }
    Write-Host 'Self-test: the guard behaves.' -ForegroundColor Green
    exit 0
}

$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $Registry) { $Registry = Join-Path $PSScriptRoot 'vendored-drift.registry.json' }
if (-not (Test-Path -LiteralPath $Registry)) { throw "Registry not found: $Registry" }
$reg = [System.IO.File]::ReadAllText($Registry, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
$ToolsRoot = if ([System.IO.Path]::IsPathRooted([string]$reg.root)) { [string]$reg.root } else { Join-Path $RepoRoot ($reg.root -replace '/', '\') }
$ToolsRoot = [System.IO.Path]::GetFullPath($ToolsRoot).TrimEnd('\', '/')
if (-not (Test-Path -LiteralPath $ToolsRoot)) { throw "Vendored tree not found: $ToolsRoot" }

$script:Errors = New-Object System.Collections.ArrayList
$script:Warnings = New-Object System.Collections.ArrayList
function Add-Error([string]$Message) { [void]$script:Errors.Add($Message); Write-Host "  [ERROR] $Message" -ForegroundColor Red }
function Add-Warning([string]$Message) { [void]$script:Warnings.Add($Message); Write-Host "  [WARN]  $Message" -ForegroundColor Yellow }

function Get-RelPath([string]$Path) {
    return $Path.Substring($ToolsRoot.Length).TrimStart('\', '/') -replace '\\', '/'
}

# ---------------------------------------------------------------- index

$isFunction = { param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }
$isCommand  = { param($n) $n -is [System.Management.Automation.Language.CommandAst] }

function Test-InsideFunction($Node) {
    $p = $Node.Parent
    while ($p) {
        if ($p -is [System.Management.Automation.Language.FunctionDefinitionAst]) { return $true }
        $p = $p.Parent
    }
    return $false
}

function Test-InsideTrap($Node) {
    $p = $Node.Parent
    while ($p) {
        if ($p -is [System.Management.Automation.Language.TrapStatementAst]) { return $true }
        if ($p -is [System.Management.Automation.Language.FunctionDefinitionAst]) { return $false }
        $p = $p.Parent
    }
    return $false
}

# Function text without comments, whitespace collapsed: the comparison key.
function Get-NormalizedText($FunctionAst, [string]$Text, $Comments) {
    $start = $FunctionAst.Extent.StartOffset
    $end = $FunctionAst.Extent.EndOffset
    $sb = New-Object System.Text.StringBuilder
    $pos = $start
    foreach ($c in $Comments) {
        if ($c.Extent.EndOffset -le $start -or $c.Extent.StartOffset -ge $end) { continue }
        if ($c.Extent.StartOffset -gt $pos) { [void]$sb.Append($Text.Substring($pos, $c.Extent.StartOffset - $pos)) }
        [void]$sb.Append(' ')
        $pos = [Math]::Max($pos, $c.Extent.EndOffset)
    }
    if ($end -gt $pos) { [void]$sb.Append($Text.Substring($pos, $end - $pos)) }
    return (($sb.ToString() -replace '\s+', ' ').Trim())
}

$sha = [System.Security.Cryptography.SHA1]::Create()
function Get-ShortHash([string]$Text) {
    $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Text))
    return (($bytes[0..3] | ForEach-Object { $_.ToString('x2') }) -join '')
}

$files = @(Get-ChildItem -LiteralPath $ToolsRoot -Recurse -File -Filter '*.ps1' | Sort-Object FullName)
$script:Copies = @{}      # function name -> list of copy records
$script:FileFns = @{}     # rel file -> set of all function names defined anywhere in it
$script:Parsed = @{}      # rel file -> @{ Ast; Text }
$parseFailures = 0
foreach ($f in $files) {
    $rel = Get-RelPath $f.FullName
    $tokens = $null; $perrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$tokens, [ref]$perrors)
    if ($perrors -and $perrors.Count) {
        $parseFailures++
        Add-Error ("{0}: does not parse ({1} at line {2}) - its copies cannot be checked" -f $rel, $perrors[0].Message, $perrors[0].Extent.StartLineNumber)
    }
    $text = $ast.Extent.Text
    $comments = @($tokens | Where-Object { $_.Kind -eq [System.Management.Automation.Language.TokenKind]::Comment })
    $script:Parsed[$rel] = @{ Ast = $ast; Text = $text }
    $names = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($fn in $ast.FindAll($isFunction, $true)) {
        [void]$names.Add($fn.Name)
        $norm = Get-NormalizedText $fn $text $comments
        $rec = [pscustomobject]@{
            Name = $fn.Name; File = $rel; Line = $fn.Extent.StartLineNumber
            Hash = (Get-ShortHash $norm); Ast = $fn
        }
        $key = $fn.Name.ToLowerInvariant()
        if (-not $script:Copies.ContainsKey($key)) { $script:Copies[$key] = New-Object System.Collections.ArrayList }
        [void]$script:Copies[$key].Add($rec)
    }
    $script:FileFns[$rel] = $names
}

$families = @($reg.families)
Write-Host ("Vendored tree: {0} ({1} scripts), registry: {2} families" -f $reg.root, $files.Count, $families.Count) -ForegroundColor DarkGray
Write-Host ''

# ---------------------------------------------------------------- discover

if ($Discover) {
    $known = @{}
    foreach ($fam in $families) { $known[$fam.function.ToLowerInvariant()] = $true }
    $rows = foreach ($key in $script:Copies.Keys) {
        if ($known.ContainsKey($key)) { continue }
        $list = $script:Copies[$key]
        $fileCount = @($list | Select-Object -ExpandProperty File -Unique).Count
        if ($fileCount -lt 2) { continue }
        [pscustomobject]@{
            Function = $list[0].Name; Files = $fileCount
            Variants = @($list | Select-Object -ExpandProperty Hash -Unique).Count
        }
    }
    $rows = @($rows | Sort-Object @{ Expression = 'Files'; Descending = $true }, Function)
    Write-Host ("Functions in 2+ files not in the registry: {0}" -f $rows.Count)
    foreach ($r in $rows) { Write-Host ("  {0,-40} files {1,3}  variants {2,3}" -f $r.Function, $r.Files, $r.Variants) }
    exit 0
}

# ---------------------------------------------------------------- drift

function Invoke-DriftCheck {
    Write-Host '=== Drift: shared function families ===' -ForegroundColor Cyan
    $summary = New-Object System.Collections.ArrayList
    foreach ($fam in $families) {
        $name = [string]$fam.function
        if ($name -notlike $Family) { continue }
        $key = $name.ToLowerInvariant()
        $copies = if ($script:Copies.ContainsKey($key)) { @($script:Copies[$key]) } else { @() }
        if ($copies.Count -eq 0) {
            Write-Host ("{0}: no copy in the tree" -f $name)
            Add-Warning "$name : registered, but no copy exists in the tree - drop it from the registry or fix the name"
            continue
        }
        $groups = @($copies | Group-Object Hash | Sort-Object @{ Expression = 'Count'; Descending = $true }, @{ Expression = { ($_.Group | Sort-Object File | Select-Object -First 1).File } })
        $base = $null
        if ($fam.authority) {
            $authCopy = @($copies | Where-Object { $_.File -eq $fam.authority }) | Select-Object -First 1
            if (-not $authCopy) {
                Write-Host ("{0}: {1} copies, {2} variants" -f $name, $copies.Count, $groups.Count)
                Add-Error "$name : authority $($fam.authority) has no copy of the function"
                continue
            }
            $base = $groups | Where-Object { $_.Name -eq $authCopy.Hash } | Select-Object -First 1
        } else {
            $base = $groups[0]
        }
        $baseLabel = if ($fam.authority) { "authority $($fam.authority)" } else { 'largest group' }
        Write-Host ("{0}: {1} copies in {2} files, {3} variant(s); base = {4} ({5} copies)" -f $name, $copies.Count,
            @($copies | Select-Object -ExpandProperty File -Unique).Count, $groups.Count, $baseLabel, $base.Count)
        if ($Detailed) { foreach ($c in ($base.Group | Sort-Object File)) { Write-Host ("      = {0}:{1}" -f $c.File, $c.Line) -ForegroundColor DarkGray } }

        $declared = @{}
        foreach ($v in @($fam.localVariants)) {
            if (-not $v) { continue }
            if (-not $v.reason) { Add-Error "$name : a localVariants entry has no reason ($(@($v.files) -join ', '))" }
            foreach ($file in @($v.files)) { $declared[$file] = $v }
        }

        $undeclared = 0
        foreach ($g in $groups) {
            if ($g.Name -eq $base.Name) { continue }
            foreach ($c in ($g.Group | Sort-Object File, Line)) {
                $v = $declared[$c.File]
                if ($v) {
                    Write-Host ("    variant {0}: {1}:{2}  declared - {3}" -f $g.Name, $c.File, $c.Line, $v.reason) -ForegroundColor DarkYellow
                } elseif ($fam.maxVariants) {
                    Write-Host ("    variant {0}: {1}:{2}" -f $g.Name, $c.File, $c.Line) -ForegroundColor DarkYellow
                } else {
                    $undeclared++
                    Write-Host ("    variant {0}: {1}:{2}  UNDECLARED" -f $g.Name, $c.File, $c.Line) -ForegroundColor Red
                }
            }
        }
        if ($fam.maxVariants) {
            if ($groups.Count -gt [int]$fam.maxVariants) {
                Add-Error "$name : $($groups.Count) variants, ratchet allows $($fam.maxVariants) - a copy drifted further"
            } elseif ($groups.Count -lt [int]$fam.maxVariants) {
                Add-Warning "$name : $($groups.Count) variants, ratchet still allows $($fam.maxVariants) - lower maxVariants"
            }
        } elseif ($undeclared) {
            Add-Error "$name : $undeclared copies differ from the base and are not declared local variants"
        }

        # Declared variants: each group internally identical, and still different from the base.
        foreach ($v in @($fam.localVariants)) {
            if (-not $v) { continue }
            $vc = @($copies | Where-Object { @($v.files) -contains $_.File })
            foreach ($file in @($v.files)) {
                if (-not ($vc | Where-Object { $_.File -eq $file })) { Add-Warning "$name : declared variant $file has no copy of the function" }
            }
            if (@($vc | Select-Object -ExpandProperty Hash -Unique).Count -gt 1) {
                Add-Error "$name : declared variant ($(@($v.files) -join ', ')) is not identical within itself"
            }
            foreach ($c in $vc) {
                if ($c.Hash -eq $base.Name) { Add-Warning "$name : $($c.File) is declared a local variant but matches the base - drop the declaration" }
            }
        }

        # Resolvability: what the base copy's file defines and a copy calls must exist in the copy's file.
        $baseFile = ($base.Group | Sort-Object File | Select-Object -First 1).File
        $baseFns = $script:FileFns[$baseFile]
        foreach ($c in $copies) {
            $own = $script:FileFns[$c.File]
            $missing = New-Object System.Collections.Generic.List[string]
            foreach ($cmd in $c.Ast.Body.FindAll($isCommand, $true)) {
                $called = $cmd.GetCommandName()
                if (-not $called -or $called -eq $c.Name) { continue }
                if ($baseFns.Contains($called) -and -not $own.Contains($called) -and -not $missing.Contains($called)) { $missing.Add($called) }
            }
            if ($missing.Count) { Add-Error "$name : $($c.File):$($c.Line) calls $($missing -join ', '), defined in $baseFile but not in its own file" }
        }
        [void]$summary.Add([pscustomobject]@{ Family = $name; Copies = $copies.Count; Variants = $groups.Count })
    }
    Write-Host ''
    Write-Host ("Families checked: {0}; copies: {1}; families with more than one variant: {2}" -f $summary.Count,
        (($summary | Measure-Object Copies -Sum).Sum), @($summary | Where-Object { $_.Variants -gt 1 }).Count)
    Write-Host ''
}

# ---------------------------------------------------------------- declared before use

function Invoke-OrderCheck {
    Write-Host '=== Order: functions declared before top-level use ===' -ForegroundColor Cyan
    $ignore = @{}
    foreach ($i in @($reg.declaredBeforeUse.ignore)) {
        if (-not $i) { continue }
        if (-not $i.reason) { Add-Error "declaredBeforeUse.ignore entry $($i.file) / $($i.function) has no reason" }
        $ignore[("{0}|{1}" -f $i.file, $i.function).ToLowerInvariant()] = $true
    }
    $chains = 0; $violations = 0; $checkedFiles = 0
    foreach ($rel in ($script:Parsed.Keys | Sort-Object)) {
        $ast = $script:Parsed[$rel].Ast
        # Script-level definitions (not nested in another function): name -> first definition.
        $defs = @{}
        foreach ($fn in $ast.FindAll($isFunction, $true)) {
            if (Test-InsideFunction $fn) { continue }
            $k = $fn.Name.ToLowerInvariant()
            if (-not $defs.ContainsKey($k) -or $fn.Extent.StartOffset -lt $defs[$k].Extent.StartOffset) { $defs[$k] = $fn }
        }
        if ($defs.Count -eq 0) { continue }
        $checkedFiles++
        # Call graph between those functions.
        $graph = @{}
        foreach ($k in $defs.Keys) {
            $set = New-Object 'System.Collections.Generic.HashSet[string]'
            foreach ($cmd in $defs[$k].Body.FindAll($isCommand, $true)) {
                $n = $cmd.GetCommandName()
                if ($n -and $defs.ContainsKey($n.ToLowerInvariant())) { [void]$set.Add($n.ToLowerInvariant()) }
            }
            $graph[$k] = $set
        }
        $reported = @{}
        foreach ($cmd in $ast.FindAll($isCommand, $true)) {
            if (Test-InsideFunction $cmd) { continue }
            if (Test-InsideTrap $cmd) { continue }
            $entry = $cmd.GetCommandName()
            if (-not $entry) { continue }
            $entryKey = $entry.ToLowerInvariant()
            if (-not $defs.ContainsKey($entryKey)) { continue }
            $chains++
            $callAt = $cmd.Extent.StartOffset
            $seen = New-Object 'System.Collections.Generic.HashSet[string]'
            $queue = New-Object System.Collections.Generic.Queue[string]
            $queue.Enqueue($entryKey); [void]$seen.Add($entryKey)
            while ($queue.Count) {
                $x = $queue.Dequeue()
                $def = $defs[$x]
                if ($def.Extent.StartOffset -gt $callAt) {
                    $tag = "$rel|$x".ToLowerInvariant()
                    if (-not $reported.ContainsKey($tag) -and -not $ignore.ContainsKey($tag)) {
                        $reported[$tag] = $true
                        $violations++
                        $via = if ($x -eq $entryKey) { '' } else { " (reached through $entry)" }
                        Add-Error ("{0}: function {1} is defined at line {2}, but top-level code calls it at line {3}{4} - PowerShell has not seen the definition yet" -f $rel, $def.Name, $def.Extent.StartLineNumber, $cmd.Extent.StartLineNumber, $via)
                    }
                }
                foreach ($y in $graph[$x]) { if ($seen.Add($y)) { $queue.Enqueue($y) } }
            }
        }
    }
    Write-Host ("Scripts with functions: {0}; top-level call chains checked: {1}; violations: {2}" -f $checkedFiles, $chains, $violations)
    Write-Host ''
}

if ($Mode -in @('all', 'drift')) { Invoke-DriftCheck }
if ($Mode -in @('all', 'order')) { Invoke-OrderCheck }

if ($script:Errors.Count) {
    Write-Host ("FAILED: {0} error(s), {1} warning(s)." -f $script:Errors.Count, $script:Warnings.Count) -ForegroundColor Red
    exit 1
}
if ($Strict -and $script:Warnings.Count) {
    Write-Host ("FAILED (-Strict): {0} warning(s)." -f $script:Warnings.Count) -ForegroundColor Red
    exit 1
}
Write-Host ("OK: no undeclared drift, {0} warning(s)." -f $script:Warnings.Count) -ForegroundColor Green
exit 0
