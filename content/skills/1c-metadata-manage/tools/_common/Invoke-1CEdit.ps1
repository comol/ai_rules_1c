#Requires -Version 5.1
<#
.SYNOPSIS
    Preview / apply wrapper for the mutating tools of the 1c-metadata-manage
    skill: logical object addressing, a unified diff of what a run changed, and
    a rollback when the run was only a preview.

.DESCRIPTION
    The tool scripts under `tools/` are vendored from upstream cc-1c-skills and
    each writes its own files; there is no shared write layer to patch, and
    patching thirty scripts would be lost on the next sync. This wrapper sits in
    front of them instead, so preview, dry-run and logical addressing are one
    local file that survives an upstream refresh.

    Three things it adds:

    1. **Logical addressing.** `-Object Справочник.Контрагенты` resolves to the
       physical XML path the tool expects. Nested forms, templates, rights and
       modules resolve too (`Отчет.Продажи.Макет.ОсновнаяСхема`). The resolved
       path is passed as `-Path`, which every path-taking tool aliases.

    2. **Unified diff.** Whatever the run changed is printed as a diff, so an
       agent can show the change instead of claiming it.

    3. **Preview (optional).** `-Preview` runs the real tool and then puts the
       tree back. Default is apply immediately; `METADATA_PREVIEW=auto` limits
       it to the risky cases (see docs/edit-preview.md). When
       the tool ships its own `-DryRun` (meta-remove, remove-form,
       remove-template, web-unpublish, db-load-git) that native flag is used
       instead: it is a plan the tool itself vouches for, and nothing is written
       that would need rolling back.

    Two rollback backends, chosen automatically:

    - **git** (preferred) — the configuration dump lives in a repository. The
      whole dump is watched, so a write outside the edited object is still
      caught, and the rollback is `git checkout` + `git clean` of that path.
      Requires the watched path to be clean before the run: rolling back over
      someone's uncommitted work is the one failure this must never cause.
    - **copy** (fallback) — no repository, or the dump is not tracked. The
      object folder, its parent kind folder and the root `Configuration.xml` are
      copied to a temp folder first. This scope is stated in the output, and a
      write outside it is reported as unwatched rather than silently missed.

    Exit code is the tool's own exit code, except when a preview rollback fails,
    which exits 2 and says what is left on disk.

.PARAMETER Tool
    Short name of the tool script, e.g. `meta-edit`, `form-edit`, `skd-edit`,
    `role-compile`. Resolved by file name under the skill's `tools/` directory,
    so a tool added by a later upstream sync works without editing this file.

.PARAMETER Object
    Logical address of the target, e.g. `Справочник.Контрагенты`,
    `Документ.Реализация.Форма.ФормаДокумента`, `Роль.ПолныеПрава`. Russian and
    English kind names are both accepted. Omit it and pass the tool's own path
    parameter instead when the address is unusual.

.PARAMETER Root
    Configuration dump root. Default: `EXPORT_PATH` from `.dev.env`, else the
    nearest folder with a `Configuration.xml`.

.PARAMETER Preview
    Run the tool, show the diff, then restore the tree. Alias: `-DryRun`.

.PARAMETER Scope
    Extra paths to watch and restore, on top of the ones derived from `-Object`.
    Only meaningful for the copy backend; git watches the whole dump anyway.

.PARAMETER NoDiff
    Apply without printing the diff. For batch callers that diff themselves.

.EXAMPLE
    # apply an attribute addition (default)
    Invoke-1CEdit.ps1 -Tool meta-edit -Object Справочник.Контрагенты `
        -Operation add-attribute -Value '{"name":"ИНН","type":"String","length":12}'

    # optional preview: show the diff and restore the tree
    Invoke-1CEdit.ps1 -Tool meta-edit -Object Справочник.Контрагенты -Preview `
        -Operation add-attribute -Value '{"name":"ИНН","type":"String","length":12}'

.EXAMPLE
    # form edit addressed logically
    Invoke-1CEdit.ps1 -Tool form-edit -Object Документ.Реализация.Форма.ФормаДокумента `
        -Preview -JsonPath .\add-field.json
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Tool,

    [string]$Object,

    [string]$Root,

    [Alias('DryRun')]
    [switch]$Preview,

    [string[]]$Scope,

    [switch]$NoDiff,

    [Parameter(ValueFromRemainingArguments = $true)]
    [object[]]$ToolArgs
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot 'DevEnv.ps1')
. (Join-Path $PSScriptRoot 'MetadataAddress.ps1')

function Write-Section([string]$Text) { Write-Host "" ; Write-Host "== $Text" -ForegroundColor Cyan }

function Resolve-ToolScript {
    # Find <Tool>.ps1 under the skill's tools/ directory. Resolved by name, not
    # by a hard-coded table, so an upstream sync that adds a tool needs no edit
    # here. An ambiguous name is an error, never a guess.
    param([string]$Name)

    $toolsRoot = Split-Path $PSScriptRoot -Parent
    $leaf = if ($Name.EndsWith('.ps1')) { $Name } else { "$Name.ps1" }
    $hits = @(Get-ChildItem -LiteralPath $toolsRoot -Recurse -File -Filter $leaf -ErrorAction SilentlyContinue)
    if ($hits.Count -eq 0) {
        $known = (Get-ChildItem -LiteralPath $toolsRoot -Recurse -File -Filter '*.ps1' |
            ForEach-Object { $_.BaseName } | Sort-Object -Unique) -join ', '
        throw "Unknown tool '$Name'. Known scripts: $known"
    }
    if ($hits.Count -gt 1) {
        throw ("Ambiguous tool '{0}' - {1} matches: {2}" -f $Name, $hits.Count, (($hits | ForEach-Object { $_.FullName }) -join '; '))
    }
    return $hits[0].FullName
}

function Get-ScriptParameters {
    # Parameter names and aliases of the target script, read from its own param
    # block. Used to decide where the resolved path goes and whether the tool
    # has a native -DryRun worth preferring over a rollback.
    param([string]$ScriptPath)

    $tokens = $null; $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($ScriptPath, [ref]$tokens, [ref]$errors)
    $result = @{}
    if (-not $ast.ParamBlock) { return $result }
    foreach ($p in $ast.ParamBlock.Parameters) {
        $name = $p.Name.VariablePath.UserPath
        $aliases = @()
        foreach ($attr in $p.Attributes) {
            if ($attr -is [System.Management.Automation.Language.AttributeAst] -and $attr.TypeName.Name -eq 'Alias') {
                foreach ($arg in $attr.PositionalArguments) {
                    if ($arg -is [System.Management.Automation.Language.StringConstantExpressionAst]) { $aliases += $arg.Value }
                }
            }
        }
        $result[$name] = [pscustomobject]@{
            Name    = $name
            Aliases = $aliases
            IsSwitch = ($p.StaticType -and $p.StaticType.Name -eq 'SwitchParameter')
        }
    }
    return $result
}

function Find-PathParameter {
    # The parameter that takes the target path: the one aliased 'Path' when
    # there is one, otherwise the single mandatory *Path parameter.
    param($Parameters)

    foreach ($p in $Parameters.Values) {
        if ($p.Aliases -contains 'Path') { return $p.Name }
    }
    $candidates = @($Parameters.Values | Where-Object { $_.Name -match 'Path$' -and -not $_.IsSwitch })
    if ($candidates.Count -eq 1) { return $candidates[0].Name }
    return $null
}

function ConvertTo-ParameterTable {
    # Remaining arguments come in flat: -Operation add-attribute -Value {...}.
    # Array splatting would re-parse them positionally and bind "-Operation" as
    # a *value*, so they are turned into a hashtable and splatted by name.
    # A switch of the target script takes no value; anything else consumes the
    # next token unless that token is itself a parameter name.
    param([object[]]$Arguments, $Parameters)

    $table = @{}
    $isSwitch = {
        param([string]$name)
        foreach ($p in $Parameters.Values) {
            if ($p.Name -eq $name -or $p.Aliases -contains $name) { return $p.IsSwitch }
        }
        return $false
    }

    $i = 0
    while ($i -lt $Arguments.Count) {
        $token = [string]$Arguments[$i]
        # A launcher that joins an empty argument list can hand us a blank token;
        # it carries no instruction, so skip it rather than fail the run.
        if ([string]::IsNullOrWhiteSpace($token)) { $i++; continue }
        if (-not $token.StartsWith('-')) {
            throw "Cannot pass '$token' through: expected a -ParameterName before it."
        }
        $name = $token.TrimStart('-')
        if (& $isSwitch $name) {
            $table[$name] = [switch]$true
            $i++
            continue
        }
        if ($i + 1 -ge $Arguments.Count) {
            # Trailing bare token: treat as a switch the target may still accept.
            $table[$name] = [switch]$true
            $i++
            continue
        }
        $next = [string]$Arguments[$i + 1]
        if ($next.StartsWith('-') -and $next.Length -gt 1 -and -not ($next -match '^-\d')) {
            $table[$name] = [switch]$true
            $i++
            continue
        }
        $value = $Arguments[$i + 1]
        # PowerShell 5.1 splits a remaining argument that contains commas into an
        # array, which shreds a JSON value like {"name":"X","type":"String"}.
        # Join it back; a target parameter that really wants a list is typed
        # String[] and re-splits the comma form itself.
        if ($value -is [System.Array]) { $value = ($value -join ',') }
        $table[$name] = $value
        $i += 2
    }
    return $table
}

function Invoke-Git {
    # git writes advice to stderr on perfectly successful runs - the CRLF
    # warning is the common one - and under $ErrorActionPreference = 'Stop' a
    # native command's stderr is turned into a terminating error. Every git call
    # goes through here so a warning cannot abort a diff or, worse, a rollback.
    # Line-ending translation is switched off for the same reason: this code
    # compares bytes, and a filter that rewrites them would invent differences.
    param([string[]]$GitArgs)

    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $full = @('-c', 'core.autocrlf=false', '-c', 'core.safecrlf=false') + $GitArgs
        $out = & git @full 2>$null
        return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = @($out) }
    } catch {
        return [pscustomobject]@{ ExitCode = 1; Output = @() }
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Test-GitTracked {
    param([string]$Path)
    $dir = if (Test-Path -LiteralPath $Path -PathType Container) { $Path } else { Split-Path $Path -Parent }
    if (-not $dir) { return $false }
    return ((Invoke-Git @('-C', $dir, 'rev-parse', '--is-inside-work-tree')).ExitCode -eq 0)
}

function Get-GitStatus {
    param([string]$RepoDir, [string]$WatchPath)
    $run = Invoke-Git @('-C', $RepoDir, 'status', '--porcelain', '--untracked-files=all', '--', $WatchPath)
    if ($run.ExitCode -ne 0) { return @() }
    return @($run.Output | Where-Object { $_ })
}

function New-CopySnapshot {
    # Copy the watched paths into a temp folder. Returns a map original -> copy
    # plus the list of watched roots, so both the diff and the rollback know
    # exactly what was observed.
    param([string[]]$Paths)

    $stamp = [Guid]::NewGuid().ToString('N').Substring(0, 12)
    $store = Join-Path ([System.IO.Path]::GetTempPath()) "1c-edit-$stamp"
    $null = New-Item -ItemType Directory -Path $store -Force
    $files = @{}
    $i = 0
    foreach ($p in $Paths) {
        if (-not (Test-Path -LiteralPath $p)) { continue }
        $items = if (Test-Path -LiteralPath $p -PathType Container) {
            Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue
        } else {
            Get-Item -LiteralPath $p
        }
        foreach ($f in $items) {
            if ($files.ContainsKey($f.FullName)) { continue }
            $i++
            $copy = Join-Path $store ("{0:D5}.bin" -f $i)
            Copy-Item -LiteralPath $f.FullName -Destination $copy -Force
            $files[$f.FullName] = $copy
        }
    }
    return [pscustomobject]@{ Store = $store; Files = $files; Watched = $Paths }
}

function Get-CopyChanges {
    param($Snapshot)

    $changed = New-Object System.Collections.ArrayList
    foreach ($orig in $Snapshot.Files.Keys) {
        if (-not (Test-Path -LiteralPath $orig)) {
            $null = $changed.Add([pscustomobject]@{ Path = $orig; Kind = 'deleted' })
            continue
        }
        $a = (Get-FileHash -LiteralPath $Snapshot.Files[$orig] -Algorithm SHA256).Hash
        $b = (Get-FileHash -LiteralPath $orig -Algorithm SHA256).Hash
        if ($a -ne $b) { $null = $changed.Add([pscustomobject]@{ Path = $orig; Kind = 'modified' }) }
    }
    foreach ($p in $Snapshot.Watched) {
        if (-not (Test-Path -LiteralPath $p)) { continue }
        $items = if (Test-Path -LiteralPath $p -PathType Container) {
            Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue
        } else { Get-Item -LiteralPath $p }
        foreach ($f in $items) {
            if (-not $Snapshot.Files.ContainsKey($f.FullName)) {
                $null = $changed.Add([pscustomobject]@{ Path = $f.FullName; Kind = 'added' })
            }
        }
    }
    return $changed
}

function Show-UnifiedDiff {
    # git diff --no-index gives a real unified diff for any two files, including
    # /dev/null for an addition or a deletion. git is already a hard requirement
    # of the surrounding workflow, so there is no second diff implementation
    # here to keep in sync.
    param([string]$Before, [string]$After, [string]$Label)

    $nul = if ($IsLinux -or $IsMacOS) { '/dev/null' } else { 'NUL' }
    $a = if ($Before) { $Before } else { $nul }
    $b = if ($After) { $After } else { $nul }
    $out = (Invoke-Git @('diff', '--no-index', '--no-color', '--', $a, $b)).Output
    if (-not $out) { return }
    # git labels the two temp paths it was handed; rewrite the header so the
    # reader sees the file that actually changed.
    Write-Host "--- a/$Label"
    Write-Host "+++ b/$Label"
    $out | Select-Object -Skip 4 | ForEach-Object { Write-Host $_ }
}

# ---------------------------------------------------------------- resolve tool
$scriptPath = Resolve-ToolScript -Name $Tool
$parameters = Get-ScriptParameters -ScriptPath $scriptPath
$nativeDryRun = $parameters.ContainsKey('DryRun')

# ------------------------------------------------------------- resolve address
$targetPath = $null
if ($Object) {
    $dumpRoot = Resolve-1CDumpRoot -Root $Root
    if (-not $dumpRoot) {
        throw "Cannot locate the configuration dump root. Pass -Root, or set EXPORT_PATH in .dev.env."
    }
    $targetPath = Resolve-1CObjectPath -Address $Object -Root $dumpRoot
    $pathParam = Find-PathParameter -Parameters $parameters
    if (-not $pathParam) {
        throw ("{0} takes no single path parameter - drop -Object and pass its own parameters instead." -f $Tool)
    }
    $ToolArgs = @("-$pathParam", $targetPath) + @($ToolArgs)
}

$callArgs = ConvertTo-ParameterTable -Arguments @($ToolArgs) -Parameters $parameters

# --------------------------------------------------------------- native dry-run
if ($Preview -and $nativeDryRun) {
    Write-Section "preview via the tool's own -DryRun ($Tool)"
    $callArgs['DryRun'] = [switch]$true
    # Reset for the same reason as before the main run below.
    $global:LASTEXITCODE = 0
    & $scriptPath @callArgs
    exit $LASTEXITCODE
}

# --------------------------------------------------------------- watch and run
$watchPaths = @()
if ($targetPath) { $watchPaths += Get-1CWatchPaths -TargetPath $targetPath }
if ($Scope) { $watchPaths += $Scope }
$watchPaths = @($watchPaths | Where-Object { $_ } | Sort-Object -Unique)

$backend = 'none'
$repoDir = $null
$snapshot = $null
$gitWatch = $null

if ($Preview) {
    if ($watchPaths.Count -eq 0) {
        throw "-Preview needs something to watch: pass -Object, or -Scope <path> when the tool is addressed directly."
    }
    $anchor = $watchPaths[0]
    if (Test-GitTracked -Path $anchor) {
        $backend = 'git'
        $repoDir = if (Test-Path -LiteralPath $anchor -PathType Container) { $anchor } else { Split-Path $anchor -Parent }
        $gitWatch = if ($Object) { (Resolve-1CDumpRoot -Root $Root) } else { $anchor }
        $dirty = Get-GitStatus -RepoDir $repoDir -WatchPath $gitWatch
        if ($dirty.Count -gt 0) {
            Write-Host "Refusing to preview: the watched path already has uncommitted changes." -ForegroundColor Red
            Write-Host "A rollback would take them with it. Commit or stash first, or run without -Preview." -ForegroundColor Red
            $dirty | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
            exit 2
        }
    } else {
        $backend = 'copy'
        $snapshot = New-CopySnapshot -Paths $watchPaths
        Write-Host "Preview scope (copy backend): $($watchPaths -join '; ')" -ForegroundColor DarkGray
        Write-Host "Writes outside this scope are not watched and not rolled back." -ForegroundColor DarkGray
    }
}

Write-Section "run: $Tool"
# A PowerShell tool that succeeds by falling off its end does not touch
# $LASTEXITCODE, so it would still hold the last native code seen here - git's
# 128 from Test-GitTracked outside a repository - and a clean run would exit
# 128. Reset it so only the tool's own exit (or native call) can set it.
$global:LASTEXITCODE = 0
& $scriptPath @callArgs
$toolExit = $LASTEXITCODE

# ------------------------------------------------------------------- show diff
if (-not $NoDiff -and $Preview) {
    Write-Section 'diff'
    if ($backend -eq 'git') {
        $null = Invoke-Git @('-C', $repoDir, 'add', '--intent-to-add', '--all', '--', $gitWatch)
        $diff = (Invoke-Git @('-C', $repoDir, 'diff', '--no-color', '--', $gitWatch)).Output
        if ($diff) { $diff | ForEach-Object { Write-Host $_ } } else { Write-Host '(no changes)' }
        $null = Invoke-Git @('-C', $repoDir, 'reset', '--quiet', '--', $gitWatch)
    } else {
        $changes = Get-CopyChanges -Snapshot $snapshot
        if ($changes.Count -eq 0) { Write-Host '(no changes)' }
        $labelRoot = if ($Object) { Resolve-1CDumpRoot -Root $Root } else { $null }
        foreach ($c in $changes) {
            $label = if ($labelRoot -and $c.Path.StartsWith($labelRoot, [StringComparison]::OrdinalIgnoreCase)) {
                $c.Path.Substring($labelRoot.Length).TrimStart('\', '/')
            } else { $c.Path }
            switch ($c.Kind) {
                'added'    { Show-UnifiedDiff -Before $null -After $c.Path -Label $label }
                'deleted'  { Show-UnifiedDiff -Before $snapshot.Files[$c.Path] -After $null -Label $label }
                'modified' { Show-UnifiedDiff -Before $snapshot.Files[$c.Path] -After $c.Path -Label $label }
            }
        }
    }
}

# -------------------------------------------------------------------- rollback
if ($Preview) {
    Write-Section 'rollback (preview)'
    $failed = $false
    if ($backend -eq 'git') {
        if ((Invoke-Git @('-C', $repoDir, 'checkout', '--quiet', '--', $gitWatch)).ExitCode -ne 0) { $failed = $true }
        if ((Invoke-Git @('-C', $repoDir, 'clean', '--quiet', '-fd', '--', $gitWatch)).ExitCode -ne 0) { $failed = $true }
        $left = Get-GitStatus -RepoDir $repoDir -WatchPath $gitWatch
        if ($left.Count -gt 0) { $failed = $true; $left | ForEach-Object { Write-Host "  still dirty: $_" -ForegroundColor Red } }
    } else {
        $changes = Get-CopyChanges -Snapshot $snapshot
        foreach ($c in $changes) {
            try {
                switch ($c.Kind) {
                    'added'    { Remove-Item -LiteralPath $c.Path -Force }
                    default    { Copy-Item -LiteralPath $snapshot.Files[$c.Path] -Destination $c.Path -Force }
                }
            } catch { $failed = $true; Write-Host "  restore failed: $($c.Path) - $($_.Exception.Message)" -ForegroundColor Red }
        }
        Remove-Item -LiteralPath $snapshot.Store -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($failed) {
        Write-Host "Rollback incomplete - the tree still holds part of the preview. Inspect before continuing." -ForegroundColor Red
        exit 2
    }
    Write-Host 'tree restored; nothing was applied' -ForegroundColor DarkGray
}

exit $toolExit
