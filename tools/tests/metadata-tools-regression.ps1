#Requires -Version 5.1
<#
.SYNOPSIS
    Focused regression tests for the meta-edit / meta-compile tools of the
    1c-metadata-manage skill.

.DESCRIPTION
    Two defects are pinned here, both reported against rules_version 81cc1d5:

      A. meta-edit re-serialized the whole document through System.Xml.XmlWriter
         and wrote it back unconditionally. On a UTF-8 BOM + LF Configurator dump
         a one-attribute edit therefore produced unrelated formatting churn:
         `<Tag />` instead of Configurator's `<Tag/>`, CRLF mixed into an LF file
         (the script inserts "`r`n" whitespace nodes), and - on the rename /
         retype / synonym paths - two logically separate child elements glued
         onto one line, because InsertAfter + Remove-NodeWithWhitespace drops the
         *leading* whitespace of the replaced position.

      B. meta-compile always appended a newly registered object after the last
         element of its own type in Configuration.xml, and saved the file through
         the DOM - rewriting declaration case, self-closing form and EOL of a
         file it was only supposed to add one line to. There was no way to ask
         for the by-name order the platform standard (APK:1108) expects.

    Every case materializes a fixture into a temp directory with exact bytes
    (BOM + chosen EOL), runs the real tool script, and asserts on the raw bytes
    of the result. The fixtures under fixtures/ are stored LF-only; the runner
    applies the target EOL itself, so the tests are immune to the checkout EOL
    policy (core.autocrlf) of the machine they run on.

    NOTE: this file is deliberately pure ASCII, like tools/validate-rules.ps1 -
    Windows PowerShell 5.1 reads a BOM-less .ps1 as ANSI, which would mangle
    non-ASCII source characters. Every Cyrillic identifier the tests need is read
    from a fixture file instead of being written here.

.PARAMETER Filter
    Run only cases whose name matches this wildcard pattern.

.PARAMETER KeepWorkDir
    Do not delete the temp working directory - useful when a case fails.

.EXAMPLE
    powershell -NoProfile -File tools\tests\metadata-tools-regression.ps1
    powershell -NoProfile -File tools\tests\metadata-tools-regression.ps1 -Filter 'meta-edit*'
#>
[CmdletBinding()]
param(
    [string]$Filter = '*',
    [switch]$KeepWorkDir
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot    = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$FixturesDir = Join-Path $PSScriptRoot 'fixtures'
$ToolsDir    = Join-Path $RepoRoot 'content\skills\1c-metadata-manage\tools'
$MetaEdit    = Join-Path $ToolsDir '1c-meta-edit\scripts\meta-edit.ps1'
$MetaCompile = Join-Path $ToolsDir '1c-meta-compile\scripts\meta-compile.ps1'
$MetaValidate = Join-Path $ToolsDir '1c-meta-validate\scripts\meta-validate.ps1'
$FormAdd      = Join-Path $ToolsDir '1c-form-scaffold\scripts\form-add.ps1'
$RemoveForm   = Join-Path $ToolsDir '1c-form-scaffold\scripts\remove-form.ps1'
$FormCompile  = Join-Path $ToolsDir '1c-form-compile\scripts\form-compile.ps1'

foreach ($required in @($MetaEdit, $MetaCompile, $RemoveForm,
        (Join-Path $FixturesDir 'config-dump'), (Join-Path $FixturesDir 'epf-with-form'))) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing prerequisite: $required" }
}

# ---------------------------------------------------------------- infrastructure

$script:Cases    = @()
$script:Failures = @()

function Register-Case([string]$Name, [scriptblock]$Body) {
    $script:Cases += [pscustomobject]@{ Name = $Name; Body = $Body }
}

function Fail([string]$Message) { throw [System.Exception]::new($Message) }

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { Fail $Message }
}

function Assert-Equal($Expected, $Actual, [string]$What) {
    if ("$Expected" -ne "$Actual") { Fail "$What : expected [$Expected], got [$Actual]" }
}

# Reads a file as raw bytes and reports the byte-level properties the two defects
# are about. Deliberately byte-based: a String round-trip would hide BOM and EOL.
function Get-FileFacts([string]$Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $offset = if ($hasBom) { 3 } else { 0 }
    $text   = [System.Text.Encoding]::UTF8.GetString($bytes, $offset, $bytes.Length - $offset)
    $crlf   = ([regex]::Matches($text, "`r`n")).Count
    $allLf  = ([regex]::Matches($text, "`n")).Count
    return [pscustomobject]@{
        Path       = $Path
        Bom        = $hasBom
        Text       = $text
        Crlf       = $crlf
        Lf         = $allLf
        LoneLf     = $allLf - $crlf
        LooseClose = ([regex]::Matches($text, ' />')).Count
        Lines      = $text -split "`r`n|`n"
    }
}

# Materializes a fixture tree into $Dest with the requested EOL. Fixture sources are
# stored LF-only with a UTF-8 BOM; text files are rewritten here so the test controls
# the exact bytes the tool sees regardless of how git checked the fixture out.
function Copy-Fixture([string]$Name, [string]$Dest, [string]$Eol = "`n") {
    $src = Join-Path $FixturesDir $Name
    if (-not (Test-Path -LiteralPath $src)) { throw "Fixture not found: $src" }
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    $bom = New-Object System.Text.UTF8Encoding($true)
    foreach ($file in (Get-ChildItem -LiteralPath $src -Recurse -File)) {
        $rel = $file.FullName.Substring($src.Length).TrimStart('\', '/')
        $out = Join-Path $Dest $rel
        New-Item -ItemType Directory -Path (Split-Path $out -Parent) -Force | Out-Null
        if ($file.Extension -eq '.bin') {
            # Support-state blob: copy byte-for-byte, it is not ours to restyle.
            Copy-Item -LiteralPath $file.FullName -Destination $out -Force
            continue
        }
        $facts = Get-FileFacts $file.FullName
        $text  = ($facts.Text -replace "`r`n", "`n")
        if ($Eol -ne "`n") { $text = $text -replace "`n", $Eol }
        [System.IO.File]::WriteAllText($out, $text, $bom)
    }
}

function Invoke-Tool([string]$Script, [string[]]$ToolArgs, [string]$WorkDir) {
    $stdout = [System.IO.Path]::GetTempFileName()
    $stderr = [System.IO.Path]::GetTempFileName()
    try {
        # Start-Process joins -ArgumentList with plain spaces, so quote here: an unquoted
        # `-Value "Baza: synonym=X"` would reach the script as two tokens and the second
        # one would bind positionally to -DefinitionFile.
        $psArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$Script`"")
        foreach ($a in $ToolArgs) {
            if ($a -match '\s') { $psArgs += "`"$a`"" } else { $psArgs += $a }
        }
        $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $psArgs `
            -WorkingDirectory $WorkDir -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        return [pscustomobject]@{
            ExitCode = $proc.ExitCode
            StdOut   = (Get-Content -LiteralPath $stdout -Raw -Encoding UTF8)
            StdErr   = (Get-Content -LiteralPath $stderr -Raw -Encoding UTF8)
        }
    } finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

# A Configurator-written line carries exactly one tag construct: an open tag, a close
# tag, an empty element, or an open/text/close triple. Anything else means two
# logically separate elements ended up glued onto one line - defect A's third symptom.
$script:WellFormedLine = [regex]'^[ \t]*(<\?[^<>]*\?>|<[^<>]+>[^<>]*</[^<>]+>|<[^<>]+/>|<[^<>]+>|</[^<>]+>)[ \t]*$'

function Assert-NoGluedTags($Facts, [string]$What) {
    $bad = @()
    for ($i = 0; $i -lt $Facts.Lines.Count; $i++) {
        $line = $Facts.Lines[$i]
        if ($line -eq '') { continue }
        if (-not $script:WellFormedLine.IsMatch($line)) { $bad += "line $($i + 1): $line" }
    }
    if ($bad.Count -gt 0) {
        Fail "$What : $($bad.Count) glued / malformed line(s):`n  " + ($bad -join "`n  ")
    }
}

function Assert-StyleKept($Before, $After, [string]$What, [string]$Eol = "`n") {
    Assert-True $After.Bom "$What : BOM lost"
    if ($Eol -eq "`n") {
        Assert-Equal 0 $After.Crlf "$What : CRLF introduced into an LF file"
    } else {
        Assert-Equal 0 $After.LoneLf "$What : lone LF introduced into a CRLF file"
        Assert-True ($After.Crlf -gt 0) "$What : CRLF file lost its CRLF"
    }
    Assert-Equal 0 $After.LooseClose "$What : Configurator writes <Tag/>, found <Tag />"
    Assert-NoGluedTags $After $What
}

# Line-level delta between two states of the same file. Returns added / removed line
# lists, so a case can assert "the diff is exactly the semantic change and nothing else".
function Get-LineDelta($Before, $After) {
    $beforeLines = @($Before.Lines)
    $afterLines  = @($After.Lines)
    $bag = @{}
    foreach ($l in $beforeLines) { if ($bag.ContainsKey($l)) { $bag[$l]++ } else { $bag[$l] = 1 } }
    $added = New-Object System.Collections.ArrayList
    foreach ($l in $afterLines) {
        if ($bag.ContainsKey($l) -and $bag[$l] -gt 0) { $bag[$l]-- } else { [void]$added.Add($l) }
    }
    $removed = New-Object System.Collections.ArrayList
    foreach ($key in $bag.Keys) { for ($i = 0; $i -lt $bag[$key]; $i++) { [void]$removed.Add($key) } }
    return [pscustomobject]@{ Added = $added.ToArray(); Removed = $removed.ToArray() }
}

# <ChildObjects> entries of a Configuration.xml in document order.
function Get-ChildObjectEntries([string]$Path) {
    $facts = Get-FileFacts $Path
    $block = [regex]::Match($facts.Text, '(?s)<ChildObjects\s*>(.*?)</ChildObjects>')
    if (-not $block.Success) { return @() }
    $entries = New-Object System.Collections.ArrayList
    foreach ($m in [regex]::Matches($block.Groups[1].Value, '<(\w+)>([^<]*)</\1>')) {
        [void]$entries.Add([pscustomobject]@{ Tag = $m.Groups[1].Value; Name = $m.Groups[2].Value })
    }
    return $entries.ToArray()
}

function Read-JsonFixture([string]$RelPath) {
    $path = Join-Path $FixturesDir $RelPath
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $offset = if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { 3 } else { 0 }
    return ([System.Text.Encoding]::UTF8.GetString($bytes, $offset, $bytes.Length - $offset) | ConvertFrom-Json)
}

# --- helpers for the add-form / validator / event cases -------------------------

function Get-TreeSnapshot([string]$Root) {
    # Relative path -> content hash for every file under $Root. Used to assert
    # that a refusal really happened before any mutation.
    $map = @{}
    foreach ($file in (Get-ChildItem -LiteralPath $Root -Recurse -File -Force)) {
        $rel = $file.FullName.Substring($Root.Length).TrimStart('')
        $map[$rel] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    }
    return $map
}

function Assert-TreeIdentical($Before, $After, [string]$What) {
    $beforeKeys = @($Before.Keys | Sort-Object)
    $afterKeys  = @($After.Keys | Sort-Object)
    Assert-Equal ($beforeKeys -join '|') ($afterKeys -join '|') "$What : the file list changed"
    foreach ($key in $beforeKeys) {
        Assert-Equal $Before[$key] $After[$key] "$What : $key changed"
    }
}

function New-BrokenToolTree([string]$Work, [string]$Name, [scriptblock]$Mutate) {
    # A private copy of the tool tree, damaged by $Mutate, so a case can run the
    # real entry point with a missing or failing validator next to it.
    $root = Join-Path $Work $Name
    Copy-Item -LiteralPath $ToolsDir -Destination $root -Recurse -Force
    & $Mutate $root
    return $root
}

function Add-ChildObjectsEntry([string]$Path, [string[]]$Lines) {
    # Append raw ChildObjects entries, byte-preserving: the shapes under test are
    # exactly the ones a generic child builder emits.
    $bytes  = [System.IO.File]::ReadAllBytes($Path)
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $offset = if ($hasBom) { 3 } else { 0 }
    $text   = [System.Text.Encoding]::UTF8.GetString($bytes, $offset, $bytes.Length - $offset)
    $eol    = if ($text -match "`r`n") { "`r`n" } else { "`n" }
    $block  = ($Lines -join $eol) + $eol
    $index  = $text.IndexOf('</ChildObjects>')
    if ($index -lt 0) { Fail "no </ChildObjects> in $Path" }
    $text = $text.Substring(0, $index) + $block + "`t`t" + $text.Substring($index)
    $encoding = New-Object System.Text.UTF8Encoding($hasBom)
    [System.IO.File]::WriteAllText($Path, $text, $encoding)
}

function Invoke-FormCompileCase([string]$Work, [string]$Tag, [string]$ElementKeysJson) {
    # Compile a one-table form whose single element carries $ElementKeysJson, then
    # read back the emitted Table/Events/Event pairs semantically - a substring
    # match would pass on a handler that landed on the wrong element.
    $dir = Join-Path $Work "fc-$Tag"
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $source = Join-Path $dir 'input.json'
    $out    = Join-Path $dir 'Form.xml'
    # Substring, not Trim: TrimEnd('}') would also eat the closing brace of a
    # nested object such as "handlers":{...}.
    $raw    = $ElementKeysJson.Trim()
    $keys   = $raw.Substring(1, $raw.Length - 2)
    $json   = '{"title":"Test","elements":[{"table":"T","columns":[],' + $keys + '}],"attributes":[],"commands":[]}'
    [System.IO.File]::WriteAllText($source, $json, (New-Object System.Text.UTF8Encoding($false)))
    $run = Invoke-Tool $FormCompile @('-JsonPath', $source, '-OutputPath', $out) $dir
    $events = @()
    if (Test-Path -LiteralPath $out) {
        $xml = New-Object System.Xml.XmlDocument
        $xml.Load($out)
        foreach ($node in $xml.SelectNodes("//*[local-name()='Table']/*[local-name()='Events']/*[local-name()='Event']")) {
            $events += [pscustomobject]@{ Name = $node.GetAttribute('name'); Handler = $node.InnerText.Trim() }
        }
    }
    return [pscustomobject]@{ Run = $run; OutPath = $out; Events = @($events) }
}

function Write-DevEnv([string]$Dir, [string]$Body) {
    [System.IO.File]::WriteAllText((Join-Path $Dir '.dev.env'), $Body, (New-Object System.Text.UTF8Encoding($false)))
}

# ---------------------------------------------------------------- A. meta-edit

Register-Case 'meta-edit: add-attribute keeps BOM, LF and tight self-closing tags' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $before = Get-FileFacts $target

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-Operation', 'add-attribute', '-Value', 'RegrFlag: Boolean', '-NoValidate') $Work
    Assert-Equal 0 $run.ExitCode "meta-edit exit code (stderr: $($run.StdErr))"

    $after = Get-FileFacts $target
    Assert-StyleKept $before $after 'add-attribute'

    $delta = Get-LineDelta $before $after
    Assert-Equal 0 $delta.Removed.Count "add-attribute removed lines: $($delta.Removed -join ' | ')"
    Assert-True (($delta.Added | Where-Object { $_ -match '<Name>RegrFlag</Name>' }).Count -eq 1) 'added block does not carry the new attribute name'
    Assert-True (($delta.Added | Where-Object { $_ -notmatch '^\s*$' }).Count -eq $delta.Added.Count) 'blank lines added'
}

Register-Case 'meta-edit: add-attribute on a CRLF dump keeps CRLF' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`r`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $before = Get-FileFacts $target
    Assert-Equal 0 $before.LoneLf 'fixture was not materialized as CRLF'

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-Operation', 'add-attribute', '-Value', 'RegrFlag: Boolean', '-NoValidate') $Work
    Assert-Equal 0 $run.ExitCode "meta-edit exit code (stderr: $($run.StdErr))"

    Assert-StyleKept $before (Get-FileFacts $target) 'add-attribute (CRLF)' "`r`n"
}

Register-Case 'meta-edit: remove-attribute leaves no glued or blank lines' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $before = Get-FileFacts $target

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-Operation', 'remove-attribute', '-Value', 'Baza', '-NoValidate') $Work
    Assert-Equal 0 $run.ExitCode "meta-edit exit code (stderr: $($run.StdErr))"

    $after = Get-FileFacts $target
    Assert-StyleKept $before $after 'remove-attribute'
    $delta = Get-LineDelta $before $after
    # Removing the first of two attributes must not pull its leading whitespace into the
    # sibling: the surviving <Attribute> has to keep starting a line of its own.
    Assert-Equal 0 $delta.Added.Count "remove-attribute added lines: $($delta.Added -join ' | ')"
    Assert-True (($delta.Removed | Where-Object { $_ -match '<Name>Baza</Name>' }).Count -eq 1) 'removed block does not contain the removed attribute'
    Assert-True ($after.Text -match '(?m)^\s*<Attribute uuid="[^"]+">\s*$') 'surviving <Attribute> no longer starts its own line'
    Assert-True ($after.Text -match '<Name>Vtoroy</Name>') 'the sibling attribute was removed too'
}

Register-Case 'meta-edit: modify-attribute synonym does not glue the replaced element' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $before = Get-FileFacts $target

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-Operation', 'modify-attribute', '-Value', 'Baza: synonym=Regr synonym', '-NoValidate') $Work
    Assert-Equal 0 $run.ExitCode "meta-edit exit code (stderr: $($run.StdErr))"

    $after = Get-FileFacts $target
    Assert-StyleKept $before $after 'modify-attribute synonym'
    # The element right before <Synonym> in the fixture is <Name>; gluing showed up as
    # `<Name>Baza</Name><Synonym>` on one line and one fewer line in the file.
    Assert-Equal $before.Lines.Count $after.Lines.Count 'synonym replacement changed the line count'
    Assert-True ($after.Text -match '(?m)^\s*<Synonym>\s*$') '<Synonym> no longer starts its own line'
}

Register-Case 'meta-edit: modify-attribute type does not glue the replaced element' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $before = Get-FileFacts $target

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-Operation', 'modify-attribute', '-Value', 'Baza: type=Boolean', '-NoValidate') $Work
    Assert-Equal 0 $run.ExitCode "meta-edit exit code (stderr: $($run.StdErr))"

    $after = Get-FileFacts $target
    Assert-StyleKept $before $after 'modify-attribute type'
    Assert-True ($after.Text -match '(?m)^\s*<Comment/>\s*$') '<Comment/> no longer stands on its own line'
    Assert-True ($after.Text -match '<v8:Type>xs:boolean</v8:Type>') 'type was not changed'
}

Register-Case 'meta-edit: rename keeps the auto-synonym block on its own lines' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $before = Get-FileFacts $target

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-Operation', 'modify-attribute', '-Value', 'Baza: name=BazaNew', '-NoValidate') $Work
    Assert-Equal 0 $run.ExitCode "meta-edit exit code (stderr: $($run.StdErr))"

    $after = Get-FileFacts $target
    Assert-StyleKept $before $after 'rename'
    Assert-Equal $before.Lines.Count $after.Lines.Count 'rename changed the line count'
    Assert-True ($after.Text -match '<Name>BazaNew</Name>') 'attribute was not renamed'
}

Register-Case 'meta-edit: the mandatory meta-validate really runs and never degrades to [SKIP]' {
    param($Work)
    # Defect C: the validator lives under the downstream directory name
    # 1c-meta-validate, the upstream-relative path resolved to nothing, and the
    # run printed [SKIP] on an otherwise successful edit. The previous version of
    # this case matched the substring 'meta-validate' - which the string '[SKIP]
    # meta-validate not found' also satisfies - and compared the result file with
    # itself. Both halves are pinned properly here: a real banner, no [SKIP], and
    # a baseline captured before the edit.
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $before = Get-FileFacts $target

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-Operation', 'add-attribute', '-Value', 'RegrFlag: Boolean') $Work
    Assert-Equal 0 $run.ExitCode "meta-edit exit code (stderr: $($run.StdErr))"

    $combined = "$($run.StdOut)$($run.StdErr)"
    Assert-True ($combined -match '--- Running meta-validate ---') "the validator banner never appeared: $combined"
    Assert-True ($combined -notmatch '\[SKIP\]') "validation was skipped instead of run: $combined"
    Assert-True ($combined -match '=== Validation: Catalog\.TestCatalog ===') "the validator printed no banner for the edited object: $combined"
    Assert-True ($combined -match '=== Result: 0 errors') "the validator produced no clean result line: $combined"

    $after = Get-FileFacts $target
    Assert-True ($before.Text -ne $after.Text) 'baseline and result are the same bytes - the case asserts nothing'
    Assert-True ($after.Text -match '<Name>RegrFlag</Name>') 'the attribute was not added'
    Assert-StyleKept $before $after 'validated edit'
}

Register-Case 'meta-edit: add-form is refused before any mutation and names form-add' {
    param($Work)
    # Defect C, writer half: add-form registered the form as a nested ChildObjects
    # descriptor with FormType=Ordinary and wrote no form file at all - a dump the
    # Configurator refuses to load. The operation is now refused outright.
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $before = Get-TreeSnapshot $Work

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-Operation', 'add-form', '-Value', 'TestForm') $Work
    Assert-Equal 2 $run.ExitCode "add-form must exit 2 (stderr: $($run.StdErr))"
    Assert-TreeIdentical $before (Get-TreeSnapshot $Work) 'refused add-form'
    Assert-True ($run.StdErr -match 'form-add') "the refusal does not point at form-add: $($run.StdErr)"
    Assert-True ($run.StdErr -match 'form-add\.ps1') 'the refusal names no PowerShell entry point to use instead'
}

Register-Case 'meta-edit: a missing validator is refused before the edit is written' {
    param($Work)
    $broken = New-BrokenToolTree $Work 'no-validator' { param($Root)
        Remove-Item -LiteralPath (Join-Path $Root '1c-meta-validate\scripts\meta-validate.ps1') -Force
    }
    $dump = Join-Path $Work 'dump'
    Copy-Fixture 'config-dump' $dump "`n"
    $target = Join-Path $dump 'Catalogs\TestCatalog.xml'
    $before = Get-TreeSnapshot $dump

    $run = Invoke-Tool (Join-Path $broken '1c-meta-edit\scripts\meta-edit.ps1') @('-ObjectPath', $target, '-Operation', 'add-attribute', '-Value', 'RegrFlag: Boolean') $dump
    Assert-True ($run.ExitCode -ne 0) "a missing validator exited 0 (stdout: $($run.StdOut))"
    Assert-TreeIdentical $before (Get-TreeSnapshot $dump) 'edit with no validator available'
    Assert-True ($run.StdErr -match 'meta-validate') "the refusal does not name the missing validator: $($run.StdErr)"
    Assert-True ("$($run.StdOut)$($run.StdErr)" -notmatch '\[SKIP\]') 'a missing validator is still degraded to a [SKIP]'
}

Register-Case 'meta-edit: -NoValidate is the explicit opt-out and the only one' {
    param($Work)
    $broken = New-BrokenToolTree $Work 'no-validator-optout' { param($Root)
        Remove-Item -LiteralPath (Join-Path $Root '1c-meta-validate\scripts\meta-validate.ps1') -Force
    }
    $dump = Join-Path $Work 'dump'
    Copy-Fixture 'config-dump' $dump "`n"
    $target = Join-Path $dump 'Catalogs\TestCatalog.xml'
    $before = Get-FileFacts $target

    $run = Invoke-Tool (Join-Path $broken '1c-meta-edit\scripts\meta-edit.ps1') @('-ObjectPath', $target, '-Operation', 'add-attribute', '-Value', 'RegrFlag: Boolean', '-NoValidate') $dump
    Assert-Equal 0 $run.ExitCode "-NoValidate exit code (stderr: $($run.StdErr))"
    $after = Get-FileFacts $target
    Assert-True ($after.Text -match '<Name>RegrFlag</Name>') '-NoValidate did not apply the edit'
    Assert-StyleKept $before $after '-NoValidate edit'
}

Register-Case 'meta-edit: a validator that reports errors propagates its non-zero exit' {
    param($Work)
    $broken = New-BrokenToolTree $Work 'failing-validator' { param($Root)
        $stub = Join-Path $Root '1c-meta-validate\scripts\meta-validate.ps1'
        Set-Content -LiteralPath $stub -Encoding ASCII -Value @(
            'param([string]$ObjectPath)',
            'Write-Host "stub validator: refusing"',
            'exit 3')
    }
    $dump = Join-Path $Work 'dump'
    Copy-Fixture 'config-dump' $dump "`n"
    $target = Join-Path $dump 'Catalogs\TestCatalog.xml'

    $run = Invoke-Tool (Join-Path $broken '1c-meta-edit\scripts\meta-edit.ps1') @('-ObjectPath', $target, '-Operation', 'add-attribute', '-Value', 'RegrFlag: Boolean') $dump
    Assert-True ($run.ExitCode -ne 0) "a failing validator was summarized as success (stdout: $($run.StdOut))"
    Assert-True ("$($run.StdOut)$($run.StdErr)" -match '--- Running meta-validate ---') 'the validator banner never appeared'
    Assert-True ($run.StdErr -match '3') "the child exit code is not reported: $($run.StdErr)"
}

# ---------------------------------------------------------------- C. meta-validate form checks

Register-Case 'meta-validate: an inline ChildObjects/Form descriptor is rejected (6a)' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    Add-ChildObjectsEntry $target @(
        "`t`t`t<Form uuid=`"11111111-1111-1111-1111-111111111111`">",
        "`t`t`t`t<Properties>",
        "`t`t`t`t`t<Name>BadForm</Name>",
        "`t`t`t`t`t<FormType>Ordinary</FormType>",
        "`t`t`t`t</Properties>",
        "`t`t`t</Form>")

    $run = Invoke-Tool $MetaValidate @('-ObjectPath', $target) $Work
    $combined = "$($run.StdOut)$($run.StdErr)"
    Assert-True ($run.ExitCode -ne 0) "the validator accepted an inline form descriptor: $combined"
    Assert-True ($combined -match '6a\.') "no 6a diagnostic: $combined"
}

Register-Case 'meta-validate: a form registered without its descriptor file is rejected (6b)' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    Add-ChildObjectsEntry $target @("`t`t`t<Form>GhostForm</Form>")

    $run = Invoke-Tool $MetaValidate @('-ObjectPath', $target) $Work
    $combined = "$($run.StdOut)$($run.StdErr)"
    Assert-True ($run.ExitCode -ne 0) "the validator accepted a dangling form reference: $combined"
    Assert-True ($combined -match '6b\.') "no 6b diagnostic: $combined"
}

# ---------------------------------------------------------------- D. form-add / form-compile

Register-Case 'form-add: the managed scaffold it writes is accepted by meta-validate' {
    param($Work)
    # The remediation add-form points at. Three layers are checked, because the
    # defect was invisible at each single one: registration shape, files on disk,
    # and the validator's own verdict.
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'

    $run = Invoke-Tool $FormAdd @('-ObjectPath', $target, '-FormName', 'SmokeForm', '-Purpose', 'Object', '-SetDefault') $Work
    Assert-Equal 0 $run.ExitCode "form-add exit code (stderr: $($run.StdErr))"

    $entries = @(Get-ChildObjectEntries $target | Where-Object { $_.Tag -eq 'Form' })
    Assert-Equal 1 $entries.Count 'the form is not registered exactly once'
    Assert-Equal 'SmokeForm' $entries[0].Name 'the registration is not a scalar <Form>Name</Form> reference'

    $formsDir = Join-Path $Work 'Catalogs\TestCatalog\Forms'
    Assert-True (Test-Path -LiteralPath (Join-Path $formsDir 'SmokeForm.xml')) 'no Forms/SmokeForm.xml descriptor'
    Assert-True (Test-Path -LiteralPath (Join-Path $formsDir 'SmokeForm\Ext\Form.xml')) 'no Ext/Form.xml'
    Assert-True (Test-Path -LiteralPath (Join-Path $formsDir 'SmokeForm\Ext\Form\Module.bsl')) 'no Ext/Form/Module.bsl'
    $facts = Get-FileFacts $target
    Assert-True ($facts.Text -match '<DefaultObjectForm>Catalog\.TestCatalog\.Form\.SmokeForm</DefaultObjectForm>') '-SetDefault did not set DefaultObjectForm'

    $check = Invoke-Tool $MetaValidate @('-ObjectPath', $target) $Work
    Assert-Equal 0 $check.ExitCode "meta-validate rejected the form-add scaffold: $($check.StdOut)$($check.StdErr)"
}

Register-Case 'form-compile: a standalone handlers map produces the event, conflicts are refused' {
    param($Work)
    # Defect B: `handlers` without `on` compiled successfully and emitted no event
    # at all, and OnEditEnd auto-names fell through to a literal fallback because
    # the suffix map spells the key OnEndEdit. This file is pure ASCII, so the
    # Cyrillic auto-name is asserted negatively - it must not be the literal
    # English event name, which is exactly what the fallback produced. The full
    # Cyrillic comparison lives in tools/tests/python-ports-regression.py.
    $standalone = Invoke-FormCompileCase $Work 'standalone' '{"handlers":{"OnActivateRow":"TActivate"}}'
    Assert-Equal 0 $standalone.Run.ExitCode "standalone handlers exit code (stderr: $($standalone.Run.StdErr))"
    Assert-Equal 1 $standalone.Events.Count "standalone handlers emitted no event: $($standalone.Events.Count)"
    Assert-Equal 'OnActivateRow' $standalone.Events[0].Name 'wrong event name'
    Assert-Equal 'TActivate' $standalone.Events[0].Handler 'wrong handler name'

    $editEnd = Invoke-FormCompileCase $Work 'editend' '{"events":{"OnEditEnd":null}}'
    Assert-Equal 0 $editEnd.Run.ExitCode "OnEditEnd exit code (stderr: $($editEnd.Run.StdErr))"
    Assert-Equal 1 $editEnd.Events.Count 'OnEditEnd emitted no event'
    Assert-Equal 'OnEditEnd' $editEnd.Events[0].Name 'wrong event name'
    Assert-True ($editEnd.Events[0].Handler -notmatch 'OnEditEnd') "the auto-name is still the literal fallback: $($editEnd.Events[0].Handler)"
    Assert-True ($editEnd.Events[0].Handler.Length -gt 0) 'the auto-name is empty'

    foreach ($pair in @(
        @{ Tag = 'conflict'; Keys = '{"events":{"OnActivateRow":"A"},"on":["OnActivateRow"]}' },
        @{ Tag = 'unknown';  Keys = '{"events":{"OnEndEdit":null}}' },
        @{ Tag = 'orphan';   Keys = '{"on":["OnActivateRow"],"handlers":{"OnEditEnd":"X"}}' })) {
        $case = Invoke-FormCompileCase $Work $pair.Tag $pair.Keys
        Assert-True ($case.Run.ExitCode -ne 0) "$($pair.Tag): expected a non-zero exit, got 0"
        Assert-True (-not (Test-Path -LiteralPath $case.OutPath)) "$($pair.Tag): refused but still wrote Form.xml"
    }
}

Register-Case 'form-validate: version, owner type, folder type, handlers and conversion context' {
    param($Work)
    # form-validate v1.10 checks 1, 12, 12b, 13 and 14 on a form-add scaffold. BSL
    # is written in English keywords so this file stays pure ASCII.
    $FormValidate = Join-Path $ToolsDir '1c-form-validate\scripts\form-validate.ps1'
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $bom = New-Object System.Text.UTF8Encoding($true)
    $formsDir = Join-Path $Work 'Catalogs\TestCatalog\Forms'
    foreach ($name in @('Main', 'Other')) {
        $run = Invoke-Tool $FormAdd @('-ObjectPath', $target, '-FormName', $name, '-Purpose', 'Object') $Work
        Assert-Equal 0 $run.ExitCode "form-add $name (stderr: $($run.StdErr))"
    }
    $formXml = Join-Path $formsDir 'Main\Ext\Form.xml'
    $modulePath = Join-Path $formsDir 'Main\Ext\Form\Module.bsl'
    $pristineForm = (Get-FileFacts $formXml).Text
    $validate = {
        param([string]$FormText, [string]$ModuleText)
        [System.IO.File]::WriteAllText($formXml, $FormText, $bom)
        [System.IO.File]::WriteAllText($modulePath, $ModuleText, $bom)
        $run = Invoke-Tool $FormValidate @('-FormPath', $formXml) $Work
        return [pscustomobject]@{ ExitCode = $run.ExitCode; Text = "$($run.StdOut)$($run.StdErr)" }
    }
    $withEvent = $pristineForm -replace '<ChildItems/>', "<Events>`n`t`t<Event name=`"OnOpen`">OnOpenHandler</Event>`n`t</Events>`n`t<ChildItems/>"
    $clientHandler = "&AtClient`nProcedure OnOpenHandler(Cancel)`nEndProcedure`n"

    $ok = & $validate $withEvent $clientHandler
    Assert-Equal 0 $ok.ExitCode "a matching handler was rejected: $($ok.Text)"
    Assert-True ($ok.Text -notmatch '\[WARN\]') "a matching handler was warned about: $($ok.Text)"

    $missing = & $validate $withEvent "&AtClient`nProcedure Unrelated()`nEndProcedure`n"
    Assert-Equal 0 $missing.ExitCode "a missing handler must stay a warning: $($missing.Text)"
    Assert-True ($missing.Text -match '\[WARN\]\s+13\..*not found') "no warning for a missing handler: $($missing.Text)"

    $duplicate = & $validate $withEvent ($clientHandler + "`n" + $clientHandler)
    Assert-True ($duplicate.ExitCode -ne 0) "a duplicate handler was accepted: $($duplicate.Text)"
    Assert-True ($duplicate.Text -match '\[ERROR\] 13\..*declared 2 times') "no error for a duplicate handler: $($duplicate.Text)"

    $conversion = & $validate $withEvent ($clientHandler + "`n&AtClient`nProcedure Convert()`n`tValue = FormAttributeToValue(`"Object`");`nEndProcedure`n")
    Assert-True ($conversion.ExitCode -ne 0) "a client-side FormAttributeToValue was accepted: $($conversion.Text)"
    Assert-True ($conversion.Text -match '\[ERROR\] 14\.') "no error for a client-side conversion: $($conversion.Text)"
    $serverConversion = & $validate $withEvent ($clientHandler + "`n&AtServer`nProcedure Convert()`n`tValue = FormAttributeToValue(`"Object`");`nEndProcedure`n")
    Assert-Equal 0 $serverConversion.ExitCode "a server-side FormAttributeToValue was rejected: $($serverConversion.Text)"

    $version = & $validate ($pristineForm -replace 'version="2\.17"', 'version="2.20"') ''
    Assert-True ($version.ExitCode -ne 0) "a Form.xml version different from Configuration.xml was accepted: $($version.Text)"
    Assert-True ($version.Text -match 'differs from Configuration\.xml') "no version diagnostic: $($version.Text)"

    $owner = & $validate ($pristineForm -replace 'cfg:CatalogObject\.TestCatalog', 'cfg:CatalogObject.OtherCatalog') ''
    Assert-True ($owner.ExitCode -ne 0) "the default object form with a foreign main attribute was accepted: $($owner.Text)"
    Assert-True ($owner.Text -match '\[ERROR\] 12b\.') "no 12b diagnostic: $($owner.Text)"

    $folder = & $validate ($pristineForm -replace '</Attributes>', "`t<Attribute name=`"Extra`" id=`"2`">`n`t`t`t<Type>`n`t`t`t`t<v8:Type>cfg:Catalogs.TestCatalog</v8:Type>`n`t`t`t</Type>`n`t`t</Attribute>`n`t</Attributes>") ''
    Assert-True ($folder.ExitCode -ne 0) "cfg:Catalogs.TestCatalog was accepted: $($folder.Text)"
    Assert-True ($folder.Text -match 'export folder name') "no export-folder diagnostic: $($folder.Text)"

    # The second form is not a default form: a foreign main attribute is legitimate there.
    $otherXml = Join-Path $formsDir 'Other\Ext\Form.xml'
    [System.IO.File]::WriteAllText($otherXml, ((Get-FileFacts $otherXml).Text -replace 'cfg:CatalogObject\.TestCatalog', 'cfg:CatalogObject.OtherCatalog'), $bom)
    $nonDefault = Invoke-Tool $FormValidate @('-FormPath', $otherXml) $Work
    Assert-Equal 0 $nonDefault.ExitCode "a non-default form with another main attribute was rejected: $($nonDefault.StdOut)"
}

# ---------------------------------------------------------------- B. meta-compile

Register-Case 'meta-compile: default position appends after the last object of the type' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    $configPath = Join-Path $Work 'Configuration.xml'
    $before  = Get-FileFacts $configPath
    $newEnum = (Read-JsonFixture 'meta-compile\new-enum.json').name

    Copy-Item (Join-Path $FixturesDir 'meta-compile\new-enum.json') (Join-Path $Work 'new-enum.json')
    $run = Invoke-Tool $MetaCompile @('-JsonPath', (Join-Path $Work 'new-enum.json'), '-OutputDir', $Work) $Work
    Assert-Equal 0 $run.ExitCode "meta-compile exit code (stderr: $($run.StdErr))"

    $enums = @(Get-ChildObjectEntries $configPath | Where-Object { $_.Tag -eq 'Enum' })
    Assert-Equal 3 $enums.Count 'enum entry count'
    Assert-Equal $newEnum $enums[2].Name 'default position must append after the last Enum'

    $after = Get-FileFacts $configPath
    Assert-StyleKept $before $after 'meta-compile default'
    Assert-True ($after.Text -match 'encoding="utf-8"') 'XML declaration was rewritten'
    $delta = Get-LineDelta $before $after
    Assert-Equal 0 $delta.Removed.Count "registration removed lines: $($delta.Removed -join ' | ')"
    Assert-Equal 1 $delta.Added.Count "registration must add exactly one line, added: $($delta.Added -join ' | ')"
}

Register-Case 'meta-compile: NEW_OBJECT_POSITION=byName inserts inside the type group' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    Write-DevEnv $Work "NEW_OBJECT_POSITION=byName`r`n"
    $configPath = Join-Path $Work 'Configuration.xml'
    $before  = Get-FileFacts $configPath
    $newEnum = (Read-JsonFixture 'meta-compile\new-enum.json').name
    $baseEnums = @(Get-ChildObjectEntries $configPath | Where-Object { $_.Tag -eq 'Enum' })

    Copy-Item (Join-Path $FixturesDir 'meta-compile\new-enum.json') (Join-Path $Work 'new-enum.json')
    $run = Invoke-Tool $MetaCompile @('-JsonPath', (Join-Path $Work 'new-enum.json'), '-OutputDir', $Work) $Work
    Assert-Equal 0 $run.ExitCode "meta-compile exit code (stderr: $($run.StdErr))"

    $enums = @(Get-ChildObjectEntries $configPath | Where-Object { $_.Tag -eq 'Enum' })
    Assert-Equal 3 $enums.Count 'enum entry count'
    Assert-Equal $baseEnums[0].Name $enums[0].Name 'first enum moved'
    Assert-Equal $newEnum          $enums[1].Name 'byName must place the new enum between the two existing ones'
    Assert-Equal $baseEnums[1].Name $enums[2].Name 'last enum moved'

    $after = Get-FileFacts $configPath
    Assert-StyleKept $before $after 'meta-compile byName'
    $delta = Get-LineDelta $before $after
    Assert-Equal 0 $delta.Removed.Count "registration removed lines: $($delta.Removed -join ' | ')"
    Assert-Equal 1 $delta.Added.Count "registration must add exactly one line, added: $($delta.Added -join ' | ')"
}

Register-Case 'meta-compile: NEW_OBJECT_POSITION=end is the backward-compatible default' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    Write-DevEnv $Work "NEW_OBJECT_POSITION=end`r`n"
    $configPath = Join-Path $Work 'Configuration.xml'
    $newEnum = (Read-JsonFixture 'meta-compile\new-enum.json').name

    Copy-Item (Join-Path $FixturesDir 'meta-compile\new-enum.json') (Join-Path $Work 'new-enum.json')
    $run = Invoke-Tool $MetaCompile @('-JsonPath', (Join-Path $Work 'new-enum.json'), '-OutputDir', $Work) $Work
    Assert-Equal 0 $run.ExitCode "meta-compile exit code (stderr: $($run.StdErr))"

    $enums = @(Get-ChildObjectEntries $configPath | Where-Object { $_.Tag -eq 'Enum' })
    Assert-Equal $newEnum $enums[2].Name 'explicit end must behave like the default'
}

Register-Case 'meta-compile: an invalid .dev.env value resolves to end, not to the fallback' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    # A typo in .dev.env must not hand the decision to .v8-project.json: the documented
    # contract is that .dev.env is authoritative and an unrecognized value means `end`.
    Write-DevEnv $Work "NEW_OBJECT_POSITION=by-name`r`n"
    [System.IO.File]::WriteAllText((Join-Path $Work '.v8-project.json'), '{ "newObjectPosition": "byName" }', (New-Object System.Text.UTF8Encoding($false)))
    $configPath = Join-Path $Work 'Configuration.xml'
    $newEnum = (Read-JsonFixture 'meta-compile\new-enum.json').name

    Copy-Item (Join-Path $FixturesDir 'meta-compile\new-enum.json') (Join-Path $Work 'new-enum.json')
    $run = Invoke-Tool $MetaCompile @('-JsonPath', (Join-Path $Work 'new-enum.json'), '-OutputDir', $Work) $Work
    Assert-Equal 0 $run.ExitCode "meta-compile exit code (stderr: $($run.StdErr))"

    $enums = @(Get-ChildObjectEntries $configPath | Where-Object { $_.Tag -eq 'Enum' })
    Assert-Equal 3 $enums.Count 'enum entry count'
    Assert-Equal $newEnum $enums[2].Name 'invalid .dev.env value must fall back to end, not to .v8-project.json byName'
}

Register-Case 'meta-compile: a missing .dev.env key still honours the .v8-project.json fallback' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    # Key absent entirely (not merely invalid): the vendored upstream registry stays in force.
    Write-DevEnv $Work "SUPPORT_GUARD=`r`n"
    [System.IO.File]::WriteAllText((Join-Path $Work '.v8-project.json'), '{ "newObjectPosition": "byName" }', (New-Object System.Text.UTF8Encoding($false)))
    $configPath = Join-Path $Work 'Configuration.xml'
    $newEnum = (Read-JsonFixture 'meta-compile\new-enum.json').name

    Copy-Item (Join-Path $FixturesDir 'meta-compile\new-enum.json') (Join-Path $Work 'new-enum.json')
    $run = Invoke-Tool $MetaCompile @('-JsonPath', (Join-Path $Work 'new-enum.json'), '-OutputDir', $Work) $Work
    Assert-Equal 0 $run.ExitCode "meta-compile exit code (stderr: $($run.StdErr))"

    $enums = @(Get-ChildObjectEntries $configPath | Where-Object { $_.Tag -eq 'Enum' })
    Assert-Equal $newEnum $enums[1].Name 'missing .dev.env key must leave the .v8-project.json fallback in charge'
}

Register-Case 'meta-compile: a brand-new type group lands in canonical type order' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    $configPath = Join-Path $Work 'Configuration.xml'
    $before = Get-FileFacts $configPath

    Copy-Item (Join-Path $FixturesDir 'meta-compile\new-report.json') (Join-Path $Work 'new-report.json')
    $run = Invoke-Tool $MetaCompile @('-JsonPath', (Join-Path $Work 'new-report.json'), '-OutputDir', $Work) $Work
    Assert-Equal 0 $run.ExitCode "meta-compile exit code (stderr: $($run.StdErr))"

    # Canonical order of kinds: ... Catalog, ... Enum, Report, ... AccumulationRegister.
    # Appending to the end of the block would have put Report after AccumulationRegister.
    $tags = @(Get-ChildObjectEntries $configPath | ForEach-Object { $_.Tag })
    Assert-Equal 'Language Catalog Enum Enum Report AccumulationRegister' ($tags -join ' ') 'kind order in ChildObjects'

    $after = Get-FileFacts $configPath
    Assert-StyleKept $before $after 'meta-compile new type group'
    $delta = Get-LineDelta $before $after
    Assert-Equal 0 $delta.Removed.Count "registration removed lines: $($delta.Removed -join ' | ')"
    Assert-Equal 1 $delta.Added.Count "registration must add exactly one line, added: $($delta.Added -join ' | ')"
}

Register-Case 'meta-compile: re-registering the same object is a no-op' {
    param($Work)
    Copy-Fixture 'config-dump' $Work "`n"
    Write-DevEnv $Work "NEW_OBJECT_POSITION=byName`r`n"
    $configPath = Join-Path $Work 'Configuration.xml'
    $newEnum = (Read-JsonFixture 'meta-compile\new-enum.json').name
    Copy-Item (Join-Path $FixturesDir 'meta-compile\new-enum.json') (Join-Path $Work 'new-enum.json')

    $first = Invoke-Tool $MetaCompile @('-JsonPath', (Join-Path $Work 'new-enum.json'), '-OutputDir', $Work) $Work
    Assert-Equal 0 $first.ExitCode "first meta-compile exit code (stderr: $($first.StdErr))"
    $afterFirst = Get-FileFacts $configPath

    $second = Invoke-Tool $MetaCompile @('-JsonPath', (Join-Path $Work 'new-enum.json'), '-OutputDir', $Work) $Work
    Assert-Equal 0 $second.ExitCode "second meta-compile exit code (stderr: $($second.StdErr))"
    $afterSecond = Get-FileFacts $configPath

    $hits = @(Get-ChildObjectEntries $configPath | Where-Object { $_.Name -eq $newEnum })
    Assert-Equal 1 $hits.Count 'object registered twice'
    Assert-Equal $afterFirst.Text $afterSecond.Text 'second run rewrote Configuration.xml'
}

# ------------------------------------------------- downstream support guard

Register-Case 'support guard: meta-edit still refuses a locked vendor object' {
    param($Work)
    Copy-Fixture 'on-support' $Work "`n"
    $target = Join-Path $Work 'Catalogs\Locked.xml'
    $before = [System.IO.File]::ReadAllBytes($target)

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-Operation', 'add-attribute', '-Value', 'RegrFlag: Boolean', '-NoValidate') $Work
    Assert-True ($run.ExitCode -ne 0) 'guard let a locked object through'
    Assert-True ($run.StdErr -match 'support-guard') "stderr does not name the guard: $($run.StdErr)"
    Assert-Equal ([System.Convert]::ToBase64String($before)) ([System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes($target))) 'refused edit still touched the file'
}

Register-Case 'support guard: .dev.env SUPPORT_GUARD=off still wins over the default' {
    param($Work)
    Copy-Fixture 'on-support' $Work "`n"
    Write-DevEnv $Work "SUPPORT_GUARD=off`r`n"
    $target = Join-Path $Work 'Catalogs\Locked.xml'

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-Operation', 'add-attribute', '-Value', 'RegrFlag: Boolean', '-NoValidate') $Work
    Assert-Equal 0 $run.ExitCode "guard did not honour SUPPORT_GUARD=off (stderr: $($run.StdErr))"
    Assert-True ((Get-FileFacts $target).Text -match '<Name>RegrFlag</Name>') 'edit was not applied with the guard off'
}

Register-Case 'support guard: meta-compile still refuses to write into a locked dump' {
    param($Work)
    Copy-Fixture 'on-support' $Work "`n"
    Copy-Item (Join-Path $FixturesDir 'meta-compile\new-enum.json') (Join-Path $Work 'new-enum.json')
    $configPath = Join-Path $Work 'Configuration.xml'
    $before = Get-FileFacts $configPath

    $run = Invoke-Tool $MetaCompile @('-JsonPath', (Join-Path $Work 'new-enum.json'), '-OutputDir', $Work) $Work
    Assert-True ($run.ExitCode -ne 0) 'guard let a compile into a locked dump through'
    Assert-True ($run.StdErr -match 'support-guard') "stderr does not name the guard: $($run.StdErr)"
    Assert-Equal $before.Text (Get-FileFacts $configPath).Text 'refused compile still edited Configuration.xml'
}


# ---------------------------------------------------------------- E. remove-form / add-form / descriptor safety

Register-Case 'meta-edit: every accepted spelling of add-form is refused before any mutation' {
    param($Work)
    # The gate matched the literal key 'add' while the dispatcher under it goes
    # through Resolve-OperationKey, so a definition written with the Cyrillic alias
    # walked past it and wrote the inline FormType=Ordinary descriptor the gate
    # exists to prevent. This file is pure ASCII, so the alias is built from code
    # points - it is not exotic input, it is what meta-edit documents.
    $dobavit = -join @(0x0434, 0x043E, 0x0431, 0x0430, 0x0432, 0x0438, 0x0442, 0x044C | ForEach-Object { [char]$_ })
    $formy   = -join @(0x0444, 0x043E, 0x0440, 0x043C, 0x044B | ForEach-Object { [char]$_ })
    $spellings = @(
        @{ Op = 'add';    Child = 'forms' },
        @{ Op = 'Add';    Child = 'forms' },
        @{ Op = 'ADD';    Child = 'Forms' },
        @{ Op = $dobavit; Child = 'forms' },
        @{ Op = $dobavit; Child = $formy }
    )
    $index = 0
    foreach ($spelling in $spellings) {
        $index++
        $dump = Join-Path $Work "alias$index"
        Copy-Fixture 'config-dump' $dump "`n"
        $target = Join-Path $dump 'Catalogs\TestCatalog.xml'
        $definition = Join-Path $dump 'definition.json'
        $json = '{"' + $spelling.Op + '":{"' + $spelling.Child + '":["ReviewForm"]}}'
        [System.IO.File]::WriteAllText($definition, $json, (New-Object System.Text.UTF8Encoding($false)))
        $before = Get-TreeSnapshot $dump

        $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-DefinitionFile', $definition) $dump
        Assert-Equal 2 $run.ExitCode "spelling #$index was not refused (stdout: $($run.StdOut) stderr: $($run.StdErr))"
        Assert-TreeIdentical $before (Get-TreeSnapshot $dump) "refused spelling #$index"
        Assert-True ($run.StdErr -match 'form-add') "spelling #$index : the refusal does not point at form-add"
    }

    # A mixed definition is refused as a whole: the unrelated half must not be
    # applied on the way to discovering the add-form half.
    $dump = Join-Path $Work 'alias-mixed'
    Copy-Fixture 'config-dump' $dump "`n"
    $target = Join-Path $dump 'Catalogs\TestCatalog.xml'
    $definition = Join-Path $dump 'definition.json'
    $json = '{"modify":{"properties":{"Comment":"regression"}},"' + $dobavit + '":{"forms":["ReviewForm"]}}'
    [System.IO.File]::WriteAllText($definition, $json, (New-Object System.Text.UTF8Encoding($false)))
    $before = Get-TreeSnapshot $dump

    $run = Invoke-Tool $MetaEdit @('-ObjectPath', $target, '-DefinitionFile', $definition) $dump
    Assert-Equal 2 $run.ExitCode "a mixed definition was not refused (stdout: $($run.StdOut))"
    Assert-TreeIdentical $before (Get-TreeSnapshot $dump) 'mixed definition applied its other half'
}

Register-Case 'form-add: an ampersand in -Synonym produces a parseable descriptor' {
    param($Work)
    # An ordinary user-facing synonym, not an attack. It was interpolated into the
    # descriptor here-string verbatim, so form-add exited 0 having written a file no
    # XML parser accepts - and meta-validate passed the object, because it only
    # checked that the descriptor path existed.
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $synonym = 'A & B'

    $run = Invoke-Tool $FormAdd @('-ObjectPath', $target, '-FormName', 'ReviewForm', '-Synonym', $synonym) $Work
    Assert-Equal 0 $run.ExitCode "form-add refused an ordinary synonym (stderr: $($run.StdErr))"

    $descriptor = Join-Path $Work 'Catalogs\TestCatalog\Forms\ReviewForm.xml'
    $doc = New-Object System.Xml.XmlDocument
    try { $doc.Load($descriptor) } catch { Fail "the descriptor does not parse as XML: $($_.Exception.Message)" }
    $nameNode = $doc.SelectSingleNode("//*[local-name()='Form']/*[local-name()='Properties']/*[local-name()='Name']")
    Assert-True ($null -ne $nameNode) 'the descriptor has no Form/Properties/Name'
    Assert-Equal 'ReviewForm' $nameNode.InnerText 'descriptor Name'
    $contentNode = $doc.SelectSingleNode("//*[local-name()='Synonym']//*[local-name()='content']")
    Assert-True ($null -ne $contentNode) 'the descriptor has no Synonym content'
    Assert-Equal $synonym $contentNode.InnerText 'the synonym did not survive escaping intact'

    $check = Invoke-Tool $MetaValidate @('-ObjectPath', $target) $Work
    Assert-Equal 0 $check.ExitCode "meta-validate rejected a correctly escaped scaffold: $($check.StdOut)$($check.StdErr)"
}

Register-Case 'meta-validate: a malformed or mismatched form descriptor is rejected' {
    param($Work)
    # Three layers, because a validator that rejected everything would satisfy the
    # negative half on its own: an untouched scaffold still passes, an unparseable
    # descriptor is 6c, and one that parses but describes another form is 6d.
    Copy-Fixture 'config-dump' $Work "`n"
    $target = Join-Path $Work 'Catalogs\TestCatalog.xml'
    $run = Invoke-Tool $FormAdd @('-ObjectPath', $target, '-FormName', 'ReviewForm') $Work
    Assert-Equal 0 $run.ExitCode "form-add exit code (stderr: $($run.StdErr))"

    $ok = Invoke-Tool $MetaValidate @('-ObjectPath', $target) $Work
    Assert-Equal 0 $ok.ExitCode "a valid scaffold was rejected: $($ok.StdOut)$($ok.StdErr)"

    $descriptor = Join-Path $Work 'Catalogs\TestCatalog\Forms\ReviewForm.xml'
    $original = (Get-FileFacts $descriptor).Text
    $bom = New-Object System.Text.UTF8Encoding($true)

    $malformed = $original -replace '<Name>ReviewForm</Name>', "<Name>ReviewForm</Name>`n`t`t`t<Raw>A & B</Raw>"
    [System.IO.File]::WriteAllText($descriptor, $malformed, $bom)
    $broken = Invoke-Tool $MetaValidate @('-ObjectPath', $target) $Work
    $combined = "$($broken.StdOut)$($broken.StdErr)"
    Assert-True ($broken.ExitCode -ne 0) "an unparseable descriptor was accepted: $combined"
    Assert-True ($combined -match '6c\.') "no 6c diagnostic: $combined"

    $mismatched = $original -replace '<Name>ReviewForm</Name>', '<Name>OtherForm</Name>'
    [System.IO.File]::WriteAllText($descriptor, $mismatched, $bom)
    $wrong = Invoke-Tool $MetaValidate @('-ObjectPath', $target) $Work
    $combined = "$($wrong.StdOut)$($wrong.StdErr)"
    Assert-True ($wrong.ExitCode -ne 0) "a descriptor for another form was accepted: $combined"
    Assert-True ($combined -match '6d\.') "no 6d diagnostic: $combined"
}

Register-Case 'remove-form: a failed publish whose restore also fails keeps the quarantine' {
    param($Work)
    # A real, native fault - no injection hook in a script that deletes files. The
    # root XML is held open with FileShare.Read: the backup copy still reads it, both
    # parking renames still succeed, and only the publish and the restore the
    # rollback then attempts hit a sharing violation.
    #
    # Discarding the quarantine used to be the oldest undo entry, so it ran *after*
    # that failed restore: the recovery directory the error message named had already
    # been deleted by the time the operator read about it.
    $src = Join-Path $Work 'src'
    Copy-Fixture 'epf-with-form' $src "`n"
    $rootXml    = Join-Path $src 'Obrabotka.xml'
    $quarantine = Join-Path $src '.remove-form-quarantine'
    $originalRoot = (Get-FileHash -LiteralPath $rootXml -Algorithm SHA256).Hash

    $lock = [System.IO.File]::Open($rootXml, [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try {
        $run = Invoke-Tool $RemoveForm @('-ObjectName', 'Obrabotka', '-FormName', 'MainForm',
            '-SrcDir', $src, '-Force') $src
    } finally {
        $lock.Close()
        $lock.Dispose()
    }

    Assert-True ($run.ExitCode -ne 0) "a failed publish reported success (stdout: $($run.StdOut))"
    Assert-True (Test-Path -LiteralPath $quarantine) "the quarantine was deleted although the root restore had failed: $($run.StdErr)"

    $backup = Join-Path $quarantine 'root-backup.xml'
    Assert-True (Test-Path -LiteralPath $backup) 'the kept quarantine has no root backup in it'
    Assert-Equal $originalRoot (Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash 'the kept backup is not the original root bytes'
    Assert-True ($run.StdErr -match [regex]::Escape($backup)) "the recovery path does not name the kept backup: $($run.StdErr)"
    Assert-True ($run.StdErr -match [regex]::Escape($rootXml)) "the recovery path does not say where the backup belongs: $($run.StdErr)"

    # The two parked payloads were put back, so the form itself is intact.
    Assert-True (Test-Path -LiteralPath (Join-Path $src 'Obrabotka\Forms\MainForm.xml')) 'the descriptor was not put back'
    Assert-True (Test-Path -LiteralPath (Join-Path $src 'Obrabotka\Forms\MainForm\Ext\Form.xml')) 'the form directory was not put back'
    Assert-Equal $originalRoot (Get-FileHash -LiteralPath $rootXml -Algorithm SHA256).Hash 'the root XML changed although the publish failed'
}

Register-Case 'remove-form: an object directory reached through a junction is refused' {
    param($Work)
    # Containment has to start at -SrcDir. Checking Forms\ against the object
    # directory says nothing when the object directory is itself a reparse point:
    # both sides resolve into the same foreign tree, so a -Force run deleted a
    # stranger's files and exited 0. mklink /J needs no privilege, so this is a real
    # Windows reparse point, and the victim lives in this case's own temp dir.
    $src = Join-Path $Work 'src'
    Copy-Fixture 'epf-with-form' $src "`n"
    $outside = Join-Path $Work 'outside-object'
    Move-Item -LiteralPath (Join-Path $src 'Obrabotka') -Destination $outside
    $link = Join-Path $src 'Obrabotka'
    $mk = & cmd.exe /c mklink /J "$link" "$outside" 2>&1
    Assert-True (Test-Path -LiteralPath $link) "could not create a junction for the case: $mk"

    $before = Get-TreeSnapshot $outside
    $run = Invoke-Tool $RemoveForm @('-ObjectName', 'Obrabotka', '-FormName', 'MainForm',
        '-SrcDir', $src, '-Force') $src
    Assert-Equal 2 $run.ExitCode "a junctioned object directory was not refused (stdout: $($run.StdOut) stderr: $($run.StdErr))"
    Assert-TreeIdentical $before (Get-TreeSnapshot $outside) 'files outside SrcDir behind a junction'
}

# ------------------------------------------------- Invoke-1CEdit: preview wrapper
#
# The wrapper adds what the vendored tools do not have: a logical address, a
# diff of what a run changed, and a preview that runs the tool for real and then
# puts the tree back. The preview is only worth having if the restore is exact
# and if it refuses to run when a rollback would destroy uncommitted work, so
# those two are what these cases pin.

$InvokeEdit = Join-Path $ToolsDir '_common\Invoke-1CEdit.ps1'

function Get-DumpFacts([string]$Root) {
    # Path -> SHA256 for every file under the dump. Compared whole, so a write
    # the wrapper failed to notice shows up as a leftover difference.
    $map = @{}
    foreach ($f in (Get-ChildItem -LiteralPath $Root -Recurse -File)) {
        $map[$f.FullName.Substring($Root.Length)] = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
    }
    return $map
}

function Assert-DumpIdentical($Before, $After, [string]$What) {
    $added = @($After.Keys | Where-Object { -not $Before.ContainsKey($_) })
    $gone = @($Before.Keys | Where-Object { -not $After.ContainsKey($_) })
    $changed = @($Before.Keys | Where-Object { $After.ContainsKey($_) -and $Before[$_] -ne $After[$_] })
    if ($added.Count -or $gone.Count -or $changed.Count) {
        Fail ("$What : added=[{0}] removed=[{1}] changed=[{2}]" -f ($added -join ','), ($gone -join ','), ($changed -join ','))
    }
}

function Initialize-GitDump([string]$Dump) {
    & git -C $Dump init --quiet 2>&1 | Out-Null
    & git -C $Dump config user.email 'regr@test.local' 2>&1 | Out-Null
    & git -C $Dump config user.name 'regr' 2>&1 | Out-Null
    & git -C $Dump config core.autocrlf false 2>&1 | Out-Null
    & git -C $Dump add -A 2>&1 | Out-Null
    & git -C $Dump commit --quiet -m base 2>&1 | Out-Null
}

Register-Case 'Invoke-1CEdit: a logical address reaches the same object as the physical path' {
    param($work)
    $dump = Join-Path $work 'dump'
    Copy-Fixture 'config-dump' $dump
    $before = Get-DumpFacts $dump

    $run = Invoke-Tool $InvokeEdit @('-Tool', 'meta-info', '-Object', 'Catalog.TestCatalog',
        '-Root', $dump) $dump
    Assert-Equal 0 $run.ExitCode "logical address was not resolved (stderr: $($run.StdErr))"
    Assert-True ($run.StdOut -match 'TestCatalog') 'the addressed object was not reported'
    Assert-DumpIdentical $before (Get-DumpFacts $dump) 'a read-only tool wrote to the dump'
}

Register-Case 'Invoke-1CEdit: an unknown kind is refused instead of resolving to nothing' {
    param($work)
    $dump = Join-Path $work 'dump'
    Copy-Fixture 'config-dump' $dump

    $run = Invoke-Tool $InvokeEdit @('-Tool', 'meta-info', '-Object', 'Katalog.TestCatalog',
        '-Root', $dump) $dump
    Assert-True ($run.ExitCode -ne 0) 'an unknown metadata kind was accepted'
    Assert-True (($run.StdErr + $run.StdOut) -match 'Unknown metadata kind') 'the refusal did not name the cause'
}

Register-Case 'Invoke-1CEdit: -Preview restores the tree byte-for-byte (copy backend)' {
    param($work)
    $dump = Join-Path $work 'dump'
    Copy-Fixture 'config-dump' $dump
    $before = Get-DumpFacts $dump

    $run = Invoke-Tool $InvokeEdit @('-Tool', 'meta-edit', '-Object', 'Catalog.TestCatalog',
        '-Root', $dump, '-Preview', '-Operation', 'add-attribute',
        '-Value', 'PreviewProbe: String', '-NoValidate') $dump

    Assert-True ($run.StdOut -match 'PreviewProbe') 'the diff did not show the attribute the run added'
    Assert-True ($run.StdOut -match 'rollback') 'the run did not report a rollback'
    Assert-DumpIdentical $before (Get-DumpFacts $dump) 'the preview left changes behind'
}

Register-Case 'Invoke-1CEdit: the same edit without -Preview is really applied' {
    param($work)
    $dump = Join-Path $work 'dump'
    Copy-Fixture 'config-dump' $dump
    $target = Join-Path $dump 'Catalogs\TestCatalog.xml'
    $before = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash

    $run = Invoke-Tool $InvokeEdit @('-Tool', 'meta-edit', '-Object', 'Catalog.TestCatalog',
        '-Root', $dump, '-Operation', 'add-attribute',
        '-Value', 'AppliedProbe: String', '-NoValidate') $dump
    Assert-Equal 0 $run.ExitCode "apply failed (stdout: $($run.StdOut) stderr: $($run.StdErr))"

    $after = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    Assert-True ($before -ne $after) 'the apply path changed nothing'
    $facts = Get-FileFacts $target
    Assert-True ($facts.Text -match 'AppliedProbe') 'the attribute is missing from the applied file'
    Assert-True $facts.Bom 'the applied file lost its BOM'
}

Register-Case 'Invoke-1CEdit: -Preview under git leaves the working tree clean' {
    param($work)
    $dump = Join-Path $work 'dump'
    Copy-Fixture 'config-dump' $dump
    Initialize-GitDump $dump

    $run = Invoke-Tool $InvokeEdit @('-Tool', 'meta-edit', '-Object', 'Catalog.TestCatalog',
        '-Root', $dump, '-Preview', '-Operation', 'add-attribute',
        '-Value', 'GitProbe: String', '-NoValidate') $dump
    Assert-True ($run.StdOut -match 'GitProbe') 'the git-backed diff did not show the change'

    $status = @(& git -C $dump status --porcelain --untracked-files=all)
    Assert-Equal 0 $status.Count "the git rollback left the tree dirty: $($status -join '; ')"
}

Register-Case 'Invoke-1CEdit: -Preview refuses a dirty tree instead of reverting someone else work' {
    param($work)
    $dump = Join-Path $work 'dump'
    Copy-Fixture 'config-dump' $dump
    Initialize-GitDump $dump

    $module = Join-Path $dump 'Catalogs\TestCatalog\Ext\ObjectModule.bsl'
    Add-Content -LiteralPath $module -Value '// uncommitted work'

    $run = Invoke-Tool $InvokeEdit @('-Tool', 'meta-edit', '-Object', 'Catalog.TestCatalog',
        '-Root', $dump, '-Preview', '-Operation', 'add-attribute',
        '-Value', 'ShouldNotRun: String', '-NoValidate') $dump

    Assert-Equal 2 $run.ExitCode "a dirty tree did not stop the preview (stdout: $($run.StdOut))"
    $text = Get-Content -LiteralPath $module -Raw
    Assert-True ($text -match 'uncommitted work') 'the refusal still destroyed the uncommitted change'
    Assert-True ((Get-FileFacts (Join-Path $dump 'Catalogs\TestCatalog.xml')).Text -notmatch 'ShouldNotRun') `
        'the tool ran even though the preview was refused'
}

Register-Case 'Invoke-1CEdit: a tool with its own -DryRun is previewed by that flag, not by rollback' {
    param($work)
    $src = Join-Path $work 'src'
    Copy-Fixture 'epf-with-form' $src
    $before = Get-DumpFacts $src

    $run = Invoke-Tool $InvokeEdit @('-Tool', 'remove-form', '-Scope', $src, '-Preview',
        '-ObjectName', 'Obrabotka', '-FormName', 'MainForm', '-SrcDir', $src) $src

    Assert-True ($run.StdOut -match "own -DryRun") 'the native dry-run path was not taken'
    Assert-DumpIdentical $before (Get-DumpFacts $src) 'the native dry-run wrote to the tree'
}

Register-Case 'support: meta-edit refuses add-template before any mutation' {
    param($work)
    Copy-Fixture 'config-dump' $work
    $target = Join-Path $work 'Catalogs\TestCatalog.xml'
    $definition = Join-Path $work 'template.json'
    [IO.File]::WriteAllText($definition, '{"modify":{"properties":{"Comment":"must not apply"}},"Add":{"Templates":["Print"]}}')
    $before = Get-TreeSnapshot $work
    foreach ($caseArgs in @(@('-Operation', 'add-template', '-Value', 'Print'), @('-DefinitionFile', $definition))) {
        $run = Invoke-Tool $MetaEdit (@('-ObjectPath', $target) + $caseArgs) $work
        Assert-Equal 2 $run.ExitCode "add-template refusal (stdout: $($run.StdOut))"
        Assert-True ($run.StdErr -match 'add-template.ps1' -and $run.StdErr -match 'TemplateType') 'missing actionable template command'
        Assert-TreeIdentical $before (Get-TreeSnapshot $work) 'refused add-template'
    }
}

Register-Case 'support: add-template accepts object XML paths and keeps name lookup' {
    param($work)
    Copy-Fixture 'config-dump' $work
    $target = Join-Path $work 'Catalogs\TestCatalog.xml'
    $addTemplate = Join-Path $ToolsDir '1c-template-manage\scripts\add-template.ps1'
    foreach ($scenario in @(
        @{ Path = $target; Name = 'Absolute' },
        @{ Path = 'Catalogs\TestCatalog.xml'; Name = 'Relative' },
        @{ Path = 'TestCatalog'; Name = 'ByName' }
    )) {
        $run = Invoke-Tool $addTemplate @('-ObjectName', $scenario.Path, '-TemplateName', $scenario.Name, '-TemplateType', 'Text', '-SrcDir', $work) $work
        Assert-Equal 0 $run.ExitCode "template creation (stderr: $($run.StdErr))"
        [xml]$xml = [IO.File]::ReadAllText($target)
        $registration = $xml.SelectNodes("//*[local-name()='Catalog']/*[local-name()='ChildObjects']/*[local-name()='Template'][text()='$($scenario.Name)']")
        Assert-Equal 1 $registration.Count 'scalar template registration'
        $templateDir = Join-Path $work 'Catalogs\TestCatalog\Templates'
        [xml]$descriptor = [IO.File]::ReadAllText((Join-Path $templateDir "$($scenario.Name).xml"))
        Assert-Equal 'TextDocument' $descriptor.SelectSingleNode("//*[local-name()='TemplateType']").InnerText 'template type'
        Assert-True (Test-Path -LiteralPath (Join-Path $templateDir "$($scenario.Name)\Ext\Template.txt")) 'missing template content'
    }
    Copy-Fixture 'epf-with-form' (Join-Path $work 'epf')
    $run = Invoke-Tool $addTemplate @('-ProcessorName', 'Obrabotka', '-TemplateName', 'Legacy', '-TemplateType', 'Text', '-SrcDir', (Join-Path $work 'epf')) $work
    Assert-Equal 0 $run.ExitCode "legacy EPF alias (stderr: $($run.StdErr))"
}

Register-Case 'support: form-edit command keeps compact tags, EOL and literal XML text' {
    param($work)
    $formEdit = Join-Path $ToolsDir '1c-form-edit\scripts\form-edit.ps1'
    $definition = Join-Path $work 'command.json'
    [IO.File]::WriteAllText($definition, '{"commands":[{"name":"X","action":"X"}]}')
    foreach ($eol in @("`n", "`r`n")) {
        $target = Join-Path $work 'Form.xml'
        $before = '<?xml version="1.0" encoding="UTF-8"?>' + $eol +
            '<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" version="2.17">' + $eol +
            "`t<AutoCommandBar name=`"FormCommandBar`" id=`"-1`"/>" + $eol +
            "`t<!-- literal <Comment /> -->" + $eol +
            "`t<?probe literal <PI /> ?>" + $eol +
            "`t<Title><![CDATA[literal <Text />]]></Title>" + $eol +
            "`t<Commands>" + $eol + "`t`t<Command name=`"Existing`" id=`"1`"><Action>Existing</Action></Command>" + $eol +
            "`t</Commands>" + $eol + '</Form>' + $eol
        [IO.File]::WriteAllText($target, $before, (New-Object Text.UTF8Encoding($true)))
        $run = Invoke-Tool $formEdit @('-FormPath', $target, '-JsonPath', $definition) $work
        Assert-Equal 0 $run.ExitCode "form edit (stderr: $($run.StdErr))"
        $after = Get-FileFacts $target
        Assert-True $after.Bom 'UTF-8 BOM lost'
        [xml]$xml = $after.Text
        Assert-Equal 1 $xml.SelectNodes("//*[local-name()='Commands']/*[local-name()='Command'][@name='X']").Count 'added command'
        $withoutAdded = [regex]::Replace($after.Text, '(?s)[\r\n]+\t\t<Command name="X".*?</Command>', '')
        Assert-Equal $before $withoutAdded 'unrelated form text changed'
    }
}

function Assert-CompactXml([string]$Path) {
    $facts = Get-FileFacts $Path
    [xml]$parsed = $facts.Text
    $tags = [regex]::Replace($facts.Text, '(?s)<!\[CDATA\[.*?\]\]>|<!--.*?-->|<\?.*?\?>', '')
    Assert-True ($tags -notmatch ' />') "serializer expanded empty tags in $Path"
    Assert-Equal 0 $facts.Crlf "LF input acquired CRLF in $Path"
    Assert-True $facts.Bom "UTF-8 BOM lost in $Path"
}

Register-Case 'support xml: form-add preserves compact tags in parent' {
    param($work)
    Copy-Fixture 'epf-with-form' $work
    $target = Join-Path $work 'Obrabotka.xml'
    $run = Invoke-Tool $FormAdd @('-ObjectPath', $target, '-FormName', 'Added', '-Purpose', 'Object') $work
    Assert-Equal 0 $run.ExitCode "form-add: $($run.StdErr)"
    Assert-CompactXml $target
}

Register-Case 'support xml: remove-form preserves compact tags in parent' {
    param($work)
    Copy-Fixture 'epf-with-form' $work
    $run = Invoke-Tool $RemoveForm @('-ObjectName', 'Obrabotka', '-FormName', 'AuxForm', '-SrcDir', $work, '-Force') $work
    Assert-Equal 0 $run.ExitCode "remove-form: $($run.StdErr)"
    Assert-CompactXml (Join-Path $work 'Obrabotka.xml')
}

Register-Case 'support xml: form-compile registration preserves compact tags in parent' {
    param($work)
    Copy-Fixture 'epf-with-form' $work
    $definition = Join-Path $work 'form.json'
    [IO.File]::WriteAllText($definition, '{"title":"Test","elements":[]}')
    $target = Join-Path $work 'Obrabotka\Forms\Added\Ext\Form.xml'
    $run = Invoke-Tool $FormCompile @('-JsonPath', $definition, '-OutputPath', $target) $work
    Assert-Equal 0 $run.ExitCode "form-compile: $($run.StdErr)"
    Assert-CompactXml (Join-Path $work 'Obrabotka.xml')
}

Register-Case 'support xml: cf-edit preserves compact tags' {
    param($work)
    Copy-Fixture 'config-dump' $work
    $target = Join-Path $work 'Configuration.xml'
    $run = Invoke-Tool (Join-Path $ToolsDir '1c-cf-manage\scripts\cf-edit.ps1') @('-ConfigPath', $target, '-Operation', 'modify-property', '-Value', 'Comment=Probe', '-NoValidate') $work
    Assert-Equal 0 $run.ExitCode "cf-edit: $($run.StdErr)"
    Assert-CompactXml $target
}

Register-Case 'support xml: subsystem registration and edit preserve compact tags' {
    param($work)
    Copy-Fixture 'config-dump' $work
    $definition = Join-Path $work 'subsystem.json'
    [IO.File]::WriteAllText($definition, '{"name":"Probe"}')
    $run = Invoke-Tool (Join-Path $ToolsDir '1c-subsystem-manage\scripts\subsystem-compile.ps1') @('-DefinitionFile', $definition, '-OutputDir', $work, '-NoValidate') $work
    Assert-Equal 0 $run.ExitCode "subsystem-compile: $($run.StdErr)"
    Assert-CompactXml (Join-Path $work 'Configuration.xml')
    $target = Join-Path $work 'Subsystems\Probe.xml'
    $text = (Get-FileFacts $target).Text -replace "`r`n", "`n"
    [IO.File]::WriteAllText($target, $text, (New-Object Text.UTF8Encoding($true)))
    $run = Invoke-Tool (Join-Path $ToolsDir '1c-subsystem-manage\scripts\subsystem-edit.ps1') @('-SubsystemPath', $target, '-Operation', 'add-content', '-Value', 'Catalog.TestCatalog', '-NoValidate') $work
    Assert-Equal 0 $run.ExitCode "subsystem-edit: $($run.StdErr)"
    Assert-CompactXml $target
}

Register-Case 'support xml: interface-edit preserves compact tags' {
    param($work)
    $target = Join-Path $work 'CommandInterface.xml'
    $text = "<?xml version=`"1.0`" encoding=`"UTF-8`"?>`n<CommandInterface xmlns=`"http://v8.1c.ru/8.3/xcf/extrnprops`" version=`"2.17`">`n`t<CommandsVisibility/>`n`t<CommandsOrder/>`n</CommandInterface>`n"
    [IO.File]::WriteAllText($target, $text, (New-Object Text.UTF8Encoding($true)))
    $run = Invoke-Tool (Join-Path $ToolsDir '1c-interface-manage\scripts\interface-edit.ps1') @('-CIPath', $target, '-Operation', 'hide', '-Value', 'Catalog.TestCatalog.StandardCommand.OpenList', '-NoValidate') $work
    Assert-Equal 0 $run.ExitCode "interface-edit: $($run.StdErr)"
    Assert-CompactXml $target
}

Register-Case 'support xml: add-template preserves compact tags in parent' {
    param($work)
    Copy-Fixture 'epf-with-form' $work
    $run = Invoke-Tool (Join-Path $ToolsDir '1c-template-manage\scripts\add-template.ps1') @('-ObjectName', 'Obrabotka', '-TemplateName', 'Probe', '-TemplateType', 'Text', '-SrcDir', $work) $work
    Assert-Equal 0 $run.ExitCode "add-template: $($run.StdErr)"
    Assert-CompactXml (Join-Path $work 'Obrabotka.xml')
}

Register-Case 'support xml: add-help preserves compact tags in form descriptor' {
    param($work)
    Copy-Fixture 'epf-with-form' $work
    $target = Join-Path $work 'Obrabotka\Forms\MainForm.xml'
    $text = (Get-FileFacts $target).Text -replace '\s*<IncludeHelpInContents>.*?</IncludeHelpInContents>', ''
    [IO.File]::WriteAllText($target, $text, (New-Object Text.UTF8Encoding($true)))
    New-Item -ItemType Directory -Path (Join-Path $work 'Obrabotka\Ext') -Force | Out-Null
    $run = Invoke-Tool (Join-Path $ToolsDir '1c-help-manage\scripts\add-help.ps1') @('-ObjectName', 'Obrabotka', '-SrcDir', $work) $work
    Assert-Equal 0 $run.ExitCode "add-help: $($run.StdErr)"
    Assert-True ((Get-FileFacts $target).Text -match '<IncludeHelpInContents>false</IncludeHelpInContents>') 'help flag was not added'
    Assert-CompactXml $target
}

Register-Case 'support xml: cfe-borrow preserves compact tags in extension' {
    param($work)
    $base = Join-Path $work 'base'
    Copy-Fixture 'config-dump' $base
    $extension = Join-Path $work 'extension'
    New-Item -ItemType Directory -Path $extension -Force | Out-Null
    $target = Join-Path $extension 'Configuration.xml'
    $text = "<?xml version=`"1.0`" encoding=`"UTF-8`"?>`n<MetaDataObject xmlns=`"http://v8.1c.ru/8.3/MDClasses`" version=`"2.17`">`n`t<Configuration uuid=`"11111111-1111-1111-1111-111111111111`">`n`t`t<Properties><Name>Probe</Name><NamePrefix/><Comment/></Properties>`n`t`t<ChildObjects/>`n`t</Configuration>`n</MetaDataObject>`n"
    # The borrowed-tool version probe reads 2000 characters from nontrivial dumps.
    $text = $text.Replace('</MetaDataObject>', ('<!--' + ('x' * 2100) + '-->' + "`n</MetaDataObject>"))
    [IO.File]::WriteAllText($target, $text, (New-Object Text.UTF8Encoding($true)))
    $run = Invoke-Tool (Join-Path $ToolsDir '1c-cfe-manage\scripts\cfe-borrow.ps1') @('-ExtensionPath', $extension, '-ConfigPath', $base, '-Object', 'Catalog.TestCatalog') $work
    Assert-Equal 0 $run.ExitCode "cfe-borrow: $($run.StdErr)"
    Assert-CompactXml $target
}

Register-Case 'support xml: skd-edit keeps compact tags without changing literal XML text' {
    param($work)
    $target = Join-Path $work 'Template.xml'
    $text = "<?xml version=`"1.0`" encoding=`"UTF-8`"?>`n<DataCompositionSchema xmlns=`"http://v8.1c.ru/8.1/data-composition-system/schema`">`n`t<dataSource><name><![CDATA[literal <Text />]]></name><dataSourceType>Local</dataSourceType></dataSource>`n`t<parameter><name>Probe</name><valueType/></parameter>`n`t<!-- literal <Comment /> -->`n`t<?probe literal <PI /> ?>`n</DataCompositionSchema>`n"
    [IO.File]::WriteAllText($target, $text, (New-Object Text.UTF8Encoding($true)))
    $run = Invoke-Tool (Join-Path $ToolsDir '1c-skd-edit\scripts\skd-edit.ps1') @('-TemplatePath', $target, '-Operation', 'remove-parameter', '-Value', 'Probe') $work
    Assert-Equal 0 $run.ExitCode "skd-edit: $($run.StdErr)"
    Assert-CompactXml $target
    $after = (Get-FileFacts $target).Text
    foreach ($literal in @('<![CDATA[literal <Text />]]>', '<!-- literal <Comment /> -->', '<?probe literal <PI /> ?>')) {
        Assert-True $after.Contains($literal) "XML literal changed: $literal"
    }
}

# ---------------------------------------------------------------- run

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("1c-rules-regr-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $root -Force | Out-Null
Write-Host "Work dir: $root" -ForegroundColor DarkGray
Write-Host ''

$index = 0
foreach ($case in $script:Cases) {
    if ($case.Name -notlike $Filter) { continue }
    $index++
    $work = Join-Path $root ("case{0:d2}" -f $index)
    New-Item -ItemType Directory -Path $work -Force | Out-Null
    try {
        & $case.Body $work
        Write-Host "[PASS] $($case.Name)" -ForegroundColor Green
    } catch {
        $script:Failures += "$($case.Name): $($_.Exception.Message)"
        Write-Host "[FAIL] $($case.Name)" -ForegroundColor Red
        Write-Host "       $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ''
if ($index -eq 0) {
    Write-Host "No case matched filter '$Filter'." -ForegroundColor Yellow
    exit 1
}
if ($script:Failures.Count -eq 0) {
    Write-Host "$index/$index passed." -ForegroundColor Green
    if (-not $KeepWorkDir) { Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue }
    exit 0
}
Write-Host "$($index - $script:Failures.Count)/$index passed, $($script:Failures.Count) failed." -ForegroundColor Red
Write-Host "Work dir kept for inspection: $root" -ForegroundColor Yellow
exit 1
