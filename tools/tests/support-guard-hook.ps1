#Requires -Version 5.1
<#
.SYNOPSIS
    Regression tests for the experimental support-guard PreToolUse hook of the
    Claude Code plugin (plugins/1c-rules/hooks/).

.DESCRIPTION
    The hook re-implements in Node the support guard that the vendored
    1c-metadata-manage tools run in PowerShell (Assert-EditAllowed), for raw
    Edit / Write / MultiEdit of a configuration dump. The two must agree, so
    most cases run twice on the same synthetic dump:

      - the hook end to end: `node support-guard.mjs` with a PreToolUse JSON on
        stdin, asserting on the JSON it prints;
      - the PowerShell guard itself: Get-RootUuid, Test-ExternalObjectRoot,
        Find-V8Project, Get-EditMode and Assert-EditAllowed are lifted out of
        the authority script (cf-edit.ps1, as upstream's drift registry names
        it) by AST into a probe script, which exits 1 when the guard refuses.

    Hook-only cases pin what the PowerShell guard has no counterpart for: the
    .dev.env opt-in (SUPPORT_GUARD_HOOK), the dump scope (notes beside a dump
    are not checked), warn as a visible systemMessage, the sh wrapper that
    must not need Node unless the project opted in, and the plugin wiring.

    Needs Node 18+. Without node the run prints SKIP and exits 0, unless
    -RequireNode is given (CI). No 1C platform is needed.

    NOTE: this file is deliberately pure ASCII (Windows PowerShell 5.1 reads a
    BOM-less .ps1 as ANSI).

.PARAMETER Filter
    Run only cases whose name matches this wildcard pattern.

.PARAMETER RequireNode
    Fail instead of skipping when node is not on PATH.

.PARAMETER GuardAuthority
    Script the PowerShell guard functions are lifted from, relative to the
    repository root.

.PARAMETER KeepWorkDir
    Do not delete the temp working directory.

.EXAMPLE
    powershell -NoProfile -File tools\tests\support-guard-hook.ps1
    powershell -NoProfile -File tools\tests\support-guard-hook.ps1 -RequireNode
#>
[CmdletBinding()]
param(
    [string]$Filter = '*',
    [switch]$RequireNode,
    [string]$GuardAuthority = 'content/skills/1c-metadata-manage/tools/1c-cf-manage/scripts/cf-edit.ps1',
    [switch]$KeepWorkDir
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot  = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$HookDir   = Join-Path $RepoRoot 'plugins\1c-rules\hooks'
$HookMjs   = Join-Path $HookDir 'support-guard.mjs'
$HookSh    = Join-Path $HookDir 'support-guard.sh'
$HooksJson = Join-Path $HookDir 'hooks.json'
$DevEnvPs1 = Join-Path $RepoRoot 'content\skills\1c-metadata-manage\tools\_common\DevEnv.ps1'
$Authority = Join-Path $RepoRoot ($GuardAuthority -replace '/', '\')

foreach ($required in @($HookMjs, $HookSh, $HooksJson, $DevEnvPs1, $Authority)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing prerequisite: $required" }
}

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    if ($RequireNode) { Write-Host 'FAIL: node is not on PATH (-RequireNode).' -ForegroundColor Red; exit 1 }
    Write-Host 'SKIP: node is not on PATH - the support-guard hook needs Node 18+.' -ForegroundColor Yellow
    exit 0
}
$NodeExe = $node.Source

# ---------------------------------------------------------------- infrastructure

$script:Cases    = @()
$script:Failures = @()
$script:Skipped  = @()

function Register-Case([string]$Name, [scriptblock]$Body) {
    $script:Cases += [pscustomobject]@{ Name = $Name; Body = $Body }
}
function Fail([string]$Message) { throw [System.Exception]::new($Message) }
function Skip([string]$Message) { throw [System.Management.Automation.PSArgumentException]::new("SKIP: $Message") }
function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { Fail $Message } }
function Assert-Equal($Expected, $Actual, [string]$What) {
    if ("$Expected" -ne "$Actual") { Fail "$What : expected [$Expected], got [$Actual]" }
}

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Utf8Bom   = New-Object System.Text.UTF8Encoding($true)

function Write-File([string]$Path, [string]$Text, [switch]$Bom) {
    New-Item -ItemType Directory -Path (Split-Path $Path -Parent) -Force | Out-Null
    $enc = if ($Bom) { $Utf8Bom } else { $Utf8NoBom }
    [System.IO.File]::WriteAllText($Path, $Text, $enc)
}

# Runs a process with UTF-8 stdin bytes, returns exit code and both streams.
function Invoke-Process([string]$Exe, [string[]]$Arguments, [string]$StdIn, [string]$WorkDir, [hashtable]$Env = @{}) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Exe
    $psi.Arguments = (($Arguments | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' ')
    $psi.WorkingDirectory = $WorkDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    foreach ($k in $Env.Keys) { $psi.EnvironmentVariables[$k] = $Env[$k] }
    $proc = [System.Diagnostics.Process]::Start($psi)
    $outTask = $proc.StandardOutput.ReadToEndAsync()
    $errTask = $proc.StandardError.ReadToEndAsync()
    if ($StdIn) {
        $bytes = $Utf8NoBom.GetBytes($StdIn)
        $proc.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
    }
    # Close the raw stream, not the StreamWriter: the writer would append its own
    # UTF-8 preamble on close, after the bytes written above.
    $proc.StandardInput.BaseStream.Flush()
    $proc.StandardInput.BaseStream.Close()
    if (-not $proc.WaitForExit(60000)) { try { $proc.Kill() } catch {}; Fail "$Exe did not exit within 60 s" }
    return [pscustomobject]@{ ExitCode = $proc.ExitCode; StdOut = $outTask.Result; StdErr = $errTask.Result }
}

# PreToolUse input for one target; the hook decides from tool_input and cwd.
function New-HookInput([string]$Cwd, [object]$ToolInput, [string]$Tool = 'Edit') {
    return (@{ hook_event_name = 'PreToolUse'; tool_name = $Tool; tool_input = $ToolInput; cwd = $Cwd; session_id = 'test' } | ConvertTo-Json -Depth 6 -Compress)
}

# Runs the hook for an Edit of $Target from project $Project; returns the decision.
function Invoke-Hook([string]$Project, [string]$Target, [string]$Raw) {
    $stdin = if ($PSBoundParameters.ContainsKey('Raw')) { $Raw } else { New-HookInput $Project @{ file_path = $Target; old_string = 'a'; new_string = 'b' } }
    $run = Invoke-Process $NodeExe @($HookMjs) $stdin $Project
    Assert-Equal 0 $run.ExitCode "hook exit code (stderr: $($run.StdErr))"
    $text = $run.StdOut.Trim()
    $json = if ($text) { $text | ConvertFrom-Json } else { $null }
    $decision = 'allow'
    if ($json -and $json.hookSpecificOutput -and $json.hookSpecificOutput.permissionDecision) { $decision = $json.hookSpecificOutput.permissionDecision }
    elseif ($json -and $json.systemMessage) { $decision = 'message' }
    return [pscustomobject]@{ Decision = $decision; Json = $json; Raw = $text; StdErr = $run.StdErr }
}

# ---------------------------------------------------------------- PowerShell guard probe

# Lifts the guard functions out of the authority script by AST, so the probe runs
# exactly the code the vendored tools run. The probe sits two levels below a
# tools/ folder holding a copy of DevEnv.ps1, which Get-EditMode dot-sources
# through $PSScriptRoot/../../_common/DevEnv.ps1.
function New-GuardProbe([string]$Root) {
    $tokens = $null; $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($Authority, [ref]$tokens, [ref]$errors)
    if ($errors -and $errors.Count) { Fail "authority does not parse: $($errors[0].Message)" }
    $names = @('Get-RootUuid', 'Test-ExternalObjectRoot', 'Find-V8Project', 'Get-EditMode', 'Assert-EditAllowed')
    $defs = @{}
    foreach ($f in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)) {
        if ($names -contains $f.Name -and -not $defs.ContainsKey($f.Name)) { $defs[$f.Name] = $f.Extent.Text }
    }
    foreach ($n in $names) { if (-not $defs.ContainsKey($n)) { Fail "authority $GuardAuthority has no function $n" } }
    $body = "param([string]`$Target, [string]`$Require = 'editable')`n`$ErrorActionPreference = 'Stop'`n"
    foreach ($n in $names) { $body += $defs[$n] + "`n" }
    $body += "Assert-EditAllowed `$Target `$Require`nexit 0`n"
    $probe = Join-Path $Root 'tools\1c-probe\scripts\guard-probe.ps1'
    Write-File $probe $body -Bom
    Write-File (Join-Path $Root 'tools\_common\DevEnv.ps1') ([System.IO.File]::ReadAllText($DevEnvPs1, [System.Text.Encoding]::UTF8)) -Bom
    return $probe
}

function Invoke-PsGuard([string]$Project, [string]$Target) {
    $run = Invoke-Process 'powershell.exe' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script:Probe, '-Target', $Target) '' $Project
    $decision = switch ($run.ExitCode) { 0 { 'allow' } 1 { 'deny' } default { "exit $($run.ExitCode)" } }
    return [pscustomobject]@{ Decision = $decision; StdErr = $run.StdErr }
}

# ---------------------------------------------------------------- fixtures

$U = @{
    Root     = '11111111-1111-1111-1111-111111111111'
    Locked   = '22222222-2222-2222-2222-222222222222'
    Editable = '33333333-3333-3333-3333-333333333333'
    Removed  = '44444444-4444-4444-4444-444444444444'
    Free     = '55555555-5555-5555-5555-555555555555'
    Form     = '66666666-6666-6666-6666-666666666666'
    Epf      = '77777777-7777-7777-7777-777777777777'
}

function Get-ObjectXml([string]$Kind, [string]$Uuid, [string]$Name) {
    return "<?xml version=`"1.0`" encoding=`"UTF-8`"?>`n<MetaDataObject xmlns=`"http://v8.1c.ru/8.3/MDClasses`" xmlns:xr=`"http://v8.1c.ru/8.3/xcf/readable`" version=`"2.17`">`n`t<$Kind uuid=`"$Uuid`">`n`t`t<Properties>`n`t`t`t<Name>$Name</Name>`n`t`t</Properties>`n`t</$Kind>`n</MetaDataObject>`n"
}

# Support-state text: header {6,G,K, then one vendor block with per-object records f1,0,uuid,uuid.
function Get-BinText([int]$G, [int]$K, [System.Collections.IDictionary]$Records) {
    $text = "{6,$G,$K,aaaaaaaa-0000-0000-0000-000000000000,0,bbbbbbbb-0000-0000-0000-000000000000,`"1.0.0.1`",`"Vendor`",`"Typical`",$($Records.Count),"
    foreach ($uuid in $Records.Keys) { $text += "$($Records[$uuid]),0,$uuid,$uuid," }
    return $text.TrimEnd(',') + '}'
}

# A project with a .dev.env and a configuration dump in src/cf.
# $Bin: support-state text, a byte array, or $null for no Ext/ParentConfigurations.bin.
function New-Project([string]$Work, [object]$Bin, [string]$DevEnv = "SUPPORT_GUARD_HOOK=on`nSUPPORT_GUARD=`n") {
    $project = Join-Path $Work 'project'
    $cf = Join-Path $project 'src\cf'
    if ($null -ne $DevEnv) { Write-File (Join-Path $project '.dev.env') $DevEnv }
    Write-File (Join-Path $cf 'Configuration.xml') (Get-ObjectXml 'Configuration' $U.Root 'Typical') -Bom
    Write-File (Join-Path $cf 'NOTES.md') "notes beside the dump`n"
    foreach ($o in @(@('Locked', $U.Locked), @('Editable', $U.Editable), @('Removed', $U.Removed), @('Free', $U.Free))) {
        Write-File (Join-Path $cf "Catalogs\$($o[0]).xml") (Get-ObjectXml 'Catalog' $o[1] $o[0]) -Bom
        Write-File (Join-Path $cf "Catalogs\$($o[0])\Ext\ObjectModule.bsl") "Procedure A()`nEndProcedure`n" -Bom
    }
    Write-File (Join-Path $cf 'Catalogs\Locked\Forms\ItemForm.xml') (Get-ObjectXml 'Form' $U.Form 'ItemForm') -Bom
    Write-File (Join-Path $cf 'Catalogs\Locked\Forms\ItemForm\Ext\Form.xml') "<?xml version=`"1.0`" encoding=`"UTF-8`"?>`n<Form xmlns=`"http://v8.1c.ru/8.3/xcf/logform`" version=`"2.17`">`n`t<AutoCommandBar name=`"FormCommandBar`" id=`"-1`"/>`n</Form>`n" -Bom
    # An autonomous external data processor dumped inside the configuration tree.
    Write-File (Join-Path $cf 'DataProcessors\Outside.xml') (Get-ObjectXml 'ExternalDataProcessor' $U.Epf 'Outside') -Bom
    Write-File (Join-Path $cf 'DataProcessors\Outside\Ext\ObjectModule.bsl') "Procedure B()`nEndProcedure`n" -Bom
    # An extension dump nested in the tree borrows the locked catalog (same uuid).
    $cfe = Join-Path $cf 'cfe\Patch'
    Write-File (Join-Path $cfe 'Configuration.xml') ("<?xml version=`"1.0`" encoding=`"UTF-8`"?>`n<MetaDataObject xmlns=`"http://v8.1c.ru/8.3/MDClasses`" version=`"2.17`">`n`t<Configuration uuid=`"88888888-8888-8888-8888-888888888888`">`n`t`t<Properties>`n`t`t`t<ConfigurationExtensionPurpose>Customization</ConfigurationExtensionPurpose>`n`t`t</Properties>`n`t</Configuration>`n</MetaDataObject>`n") -Bom
    Write-File (Join-Path $cfe 'Catalogs\Locked.xml') (Get-ObjectXml 'Catalog' $U.Locked 'Locked') -Bom
    if ($Bin -is [byte[]]) {
        New-Item -ItemType Directory -Path (Join-Path $cf 'Ext') -Force | Out-Null
        [System.IO.File]::WriteAllBytes((Join-Path $cf 'Ext\ParentConfigurations.bin'), $Bin)
    } elseif ($null -ne $Bin) {
        Write-File (Join-Path $cf 'Ext\ParentConfigurations.bin') ([string]$Bin) -Bom
    }
    return [pscustomobject]@{ Root = $project; Cf = $cf }
}

function Get-StandardBin([int]$RootF1 = 1) {
    return Get-BinText 0 1 ([ordered]@{ $U.Root = $RootF1; $U.Locked = 0; $U.Editable = 1; $U.Removed = 2; $U.Form = 0 })
}

# One target through both guards; both must reach $Expected ('allow' | 'deny').
function Assert-Parity($P, [string]$Rel, [string]$Expected) {
    $target = Join-Path $P.Cf $Rel
    $hook = Invoke-Hook $P.Root $target
    $ps = Invoke-PsGuard $P.Root $target
    Assert-Equal $Expected $hook.Decision "hook decision for $Rel ($($hook.Raw))"
    Assert-Equal $Expected $ps.Decision "PowerShell guard decision for $Rel ($($ps.StdErr))"
    return $hook
}

# ---------------------------------------------------------------- parity with Assert-EditAllowed

Register-Case 'parity: locked object, its module and its form are refused; editable, off-support and free objects pass' {
    param($Work)
    $p = New-Project $Work (Get-StandardBin)
    $hook = Assert-Parity $p 'Catalogs\Locked.xml' 'deny'
    $reason = $hook.Json.hookSpecificOutput.permissionDecisionReason
    Assert-True ($reason -match 'support-edit -Path') 'the refusal does not name the support-edit command'
    Assert-True ($reason.Contains((Join-Path $p.Cf 'Catalogs\Locked.xml'))) 'the refusal does not name the target'
    Assert-True ($reason -match 'SUPPORT_GUARD_HOOK') 'the refusal does not say how to switch the hook off'
    [void](Assert-Parity $p 'Catalogs\Locked\Ext\ObjectModule.bsl' 'deny')
    [void](Assert-Parity $p 'Catalogs\Locked\Forms\ItemForm\Ext\Form.xml' 'deny')
    [void](Assert-Parity $p 'Catalogs\Editable.xml' 'allow')
    [void](Assert-Parity $p 'Catalogs\Editable\Ext\ObjectModule.bsl' 'allow')
    [void](Assert-Parity $p 'Catalogs\Removed.xml' 'allow')
    [void](Assert-Parity $p 'Catalogs\Free.xml' 'allow')
}

Register-Case 'parity: a new object file follows the configuration root record' {
    param($Work)
    $open = New-Project (Join-Path $Work 'open') (Get-StandardBin 1)
    [void](Assert-Parity $open 'Catalogs\Brand.xml' 'allow')
    $locked = New-Project (Join-Path $Work 'locked') (Get-StandardBin 0)
    [void](Assert-Parity $locked 'Catalogs\Brand.xml' 'deny')
}

Register-Case 'parity: capability off refuses every object; support removed (K=0) allows' {
    param($Work)
    $ro = New-Project (Join-Path $Work 'ro') (Get-BinText 1 1 ([ordered]@{ $U.Root = 1; $U.Editable = 1 }))
    $hook = Assert-Parity $ro 'Catalogs\Editable.xml' 'deny'
    Assert-True ($hook.Json.hookSpecificOutput.permissionDecisionReason -match '-Capability on') 'capability-off refusal lacks the -Capability on step'
    $k0 = New-Project (Join-Path $Work 'k0') (Get-BinText 0 0 ([ordered]@{ $U.Locked = 0; $U.Root = 0; $U.Editable = 1; $U.Free = 1 }))
    [void](Assert-Parity $k0 'Catalogs\Locked.xml' 'allow')
}

Register-Case 'parity: support removed completely (32 bytes or less) allows; a bad header is fail-closed' {
    param($Work)
    # A bin of 32 bytes or less is the empty container a configuration keeps once vendor
    # support was removed completely (upstream support-state spec: ~16 bytes) - both the
    # PowerShell guard and the hook let the edit through.
    # [byte[]] around the sum: byte[] + byte[] is object[] in PowerShell, and New-Project
    # would write it as text ("239 187 191 ...", 43 bytes) instead of the 12-byte container.
    $tinyBytes = [byte[]]([byte[]](0xEF, 0xBB, 0xBF) + [System.Text.Encoding]::ASCII.GetBytes('{6,0,0,0}'))
    $tiny = New-Project (Join-Path $Work 'tiny') $tinyBytes
    $tinyBin = Join-Path $tiny.Cf 'Ext\ParentConfigurations.bin'
    Assert-True ((Get-Item -LiteralPath $tinyBin).Length -eq 12) "the tiny support state is not 12 bytes: $((Get-Item -LiteralPath $tinyBin).Length)"
    [void](Assert-Parity $tiny 'Catalogs\Free.xml' 'allow')
    $bad = New-Project (Join-Path $Work 'bad') ('{7,0,1,' + ('x' * 64) + '}')
    $hook = Assert-Parity $bad 'Catalogs\Free.xml' 'deny'
    Assert-True ($hook.Json.hookSpecificOutput.permissionDecisionReason -match 'ParentConfigurations\.bin') 'the unreadable-state refusal does not name the file'
}

Register-Case 'parity: an external data processor and a nested extension dump are never on support' {
    param($Work)
    $p = New-Project $Work (Get-StandardBin 0)
    [void](Assert-Parity $p 'DataProcessors\Outside.xml' 'allow')
    [void](Assert-Parity $p 'DataProcessors\Outside\Ext\ObjectModule.bsl' 'allow')
    [void](Assert-Parity $p 'cfe\Patch\Catalogs\Locked.xml' 'allow')
}

Register-Case 'parity: own configuration without a support-state file allows' {
    param($Work)
    $p = New-Project $Work $null
    [void](Assert-Parity $p 'Catalogs\Locked.xml' 'allow')
}

Register-Case 'parity: SUPPORT_GUARD=off allows; warn lets the edit through with a visible warning' {
    param($Work)
    $off = New-Project (Join-Path $Work 'off') (Get-StandardBin) "SUPPORT_GUARD_HOOK=on`nSUPPORT_GUARD=off`n"
    [void](Assert-Parity $off 'Catalogs\Locked.xml' 'allow')
    $warn = New-Project (Join-Path $Work 'warn') (Get-StandardBin) "SUPPORT_GUARD_HOOK=on`nSUPPORT_GUARD=`"Warn`"`n"
    $target = Join-Path $warn.Cf 'Catalogs\Locked.xml'
    $hook = Invoke-Hook $warn.Root $target
    Assert-Equal 'message' $hook.Decision "hook decision under warn ($($hook.Raw))"
    Assert-True ($hook.Json.systemMessage.Contains($target)) 'the warning does not name the target'
    $ps = Invoke-PsGuard $warn.Root $target
    Assert-Equal 'allow' $ps.Decision 'PowerShell guard under warn'
    Assert-True ($ps.StdErr -match 'support-guard') 'the PowerShell guard printed no warning under warn'
}

# ---------------------------------------------------------------- hook-only contract

Register-Case 'opt-in: without SUPPORT_GUARD_HOOK=on, or without .dev.env, the hook is silent' {
    param($Work)
    foreach ($envText in @("SUPPORT_GUARD=deny`n", "SUPPORT_GUARD_HOOK=off`n", "SUPPORT_GUARD_HOOK=`n", "# SUPPORT_GUARD_HOOK=on`n")) {
        $p = New-Project (Join-Path $Work ([guid]::NewGuid().ToString('N').Substring(0, 6))) (Get-StandardBin) $envText
        $hook = Invoke-Hook $p.Root (Join-Path $p.Cf 'Catalogs\Locked.xml')
        Assert-Equal '' $hook.Raw "hook output with .dev.env [$($envText.Trim())]"
    }
    $none = New-Project (Join-Path $Work 'none') (Get-StandardBin) $null
    $hook = Invoke-Hook $none.Root (Join-Path $none.Cf 'Catalogs\Locked.xml')
    Assert-Equal '' $hook.Raw 'hook output without .dev.env'
}

Register-Case 'scope: files beside the dump are not checked, even under a locked root' {
    param($Work)
    $p = New-Project $Work (Get-BinText 1 1 ([ordered]@{ $U.Root = 0 }))
    foreach ($rel in @('NOTES.md', 'Unknown\file.txt')) {
        $hook = Invoke-Hook $p.Root (Join-Path $p.Cf $rel)
        Assert-Equal 'allow' $hook.Decision "hook decision for $rel"
    }
    foreach ($rel in @('Configuration.xml', 'ConfigDumpInfo.xml', 'Ext\ParentConfigurations.bin', 'Ext\ManagedApplicationModule.bsl')) {
        $hook = Invoke-Hook $p.Root (Join-Path $p.Cf $rel)
        Assert-Equal 'deny' $hook.Decision "hook decision for $rel"
    }
}

Register-Case 'input: relative paths, file_edits arrays and malformed stdin' {
    param($Work)
    $p = New-Project $Work (Get-StandardBin)
    $rel = Invoke-Hook $p.Root '' (New-HookInput $p.Root @{ file_path = 'src/cf/Catalogs/Locked.xml'; content = 'x' } 'Write')
    Assert-Equal 'deny' $rel.Decision 'relative file_path resolved against cwd'
    $multi = Invoke-Hook $p.Root '' (New-HookInput $p.Root @{ file_edits = @(@{ file_path = (Join-Path $p.Cf 'Catalogs\Free.xml') }, @{ file_path = (Join-Path $p.Cf 'Catalogs\Locked.xml') }) } 'MultiEdit')
    Assert-Equal 'deny' $multi.Decision 'file_edits array'
    $junk = Invoke-Hook $p.Root '' 'not json {'
    Assert-Equal '' $junk.Raw 'malformed stdin must allow silently'
}

Register-Case 'wrapper: support-guard.sh needs no node without the opt-in and fails open without node' {
    param($Work)
    $sh = Get-Command sh -ErrorAction SilentlyContinue
    if (-not $sh) { Skip 'no sh on PATH' }
    $wrapper = $HookSh -replace '\\', '/'
    $p = New-Project $Work (Get-StandardBin)
    $stdin = New-HookInput $p.Root @{ file_path = (Join-Path $p.Cf 'Catalogs\Locked.xml'); old_string = 'a'; new_string = 'b' }
    $on = Invoke-Process $sh.Source @($wrapper) $stdin $p.Root @{ CLAUDE_PROJECT_DIR = $p.Root }
    Assert-Equal 0 $on.ExitCode "wrapper exit code ($($on.StdErr))"
    Assert-True ($on.StdOut -match '"permissionDecision"\s*:\s*"deny"') "wrapper did not pass the deny through: $($on.StdOut)"
    # BOM, CRLF, spaces and quotes in .dev.env, read the way DevEnv.ps1 reads them.
    [System.IO.File]::WriteAllText((Join-Path $p.Root '.dev.env'), "SUPPORT_GUARD_HOOK = `"ON`"`r`n", $Utf8Bom)
    $quoted = Invoke-Process $sh.Source @($wrapper) $stdin $p.Root @{ CLAUDE_PROJECT_DIR = $p.Root }
    Assert-True ($quoted.StdOut -match '"permissionDecision"\s*:\s*"deny"') "wrapper did not read a quoted value with BOM / CRLF: $($quoted.StdOut)"
    # Without node: PATH reduced to the folder of the POSIX tools (sed, grep, tr, head).
    $sed = Get-Command sed -ErrorAction SilentlyContinue
    $toolDir = if ($sed) { Split-Path $sed.Source -Parent } else { Split-Path $sh.Source -Parent }
    $probe = Invoke-Process $sh.Source @('-c', 'command -v sed >/dev/null && ! command -v node >/dev/null') '' $p.Root @{ PATH = $toolDir }
    if ($probe.ExitCode -ne 0) { Skip "opt-in checks passed; no PATH with sed but without node can be built from $toolDir" }
    $noNode = Invoke-Process $sh.Source @($wrapper) $stdin $p.Root @{ CLAUDE_PROJECT_DIR = $p.Root; PATH = $toolDir }
    Assert-Equal 0 $noNode.ExitCode "wrapper exit code without node ($($noNode.StdErr))"
    Assert-True ($noNode.StdOut -match 'systemMessage' -and $noNode.StdOut -match 'node') "wrapper without node gave no notice: $($noNode.StdOut)"
    Write-File (Join-Path $p.Root '.dev.env') "SUPPORT_GUARD_HOOK=off`n"
    $off = Invoke-Process $sh.Source @($wrapper) $stdin $p.Root @{ CLAUDE_PROJECT_DIR = $p.Root; PATH = $toolDir }
    Assert-Equal 0 $off.ExitCode 'wrapper exit code without the opt-in'
    Assert-Equal '' $off.StdOut.Trim() 'wrapper output without the opt-in (and without node)'
}

Register-Case 'wiring: hooks.json registers the wrapper for Edit|Write|MultiEdit; the wrapper stays LF' {
    param($Work)
    $hooks = Get-Content -LiteralPath $HooksJson -Raw -Encoding UTF8 | ConvertFrom-Json
    $entry = @($hooks.hooks.PreToolUse) | Where-Object { $_.matcher -eq 'Edit|Write|MultiEdit' } | Select-Object -First 1
    Assert-True ($null -ne $entry) 'no PreToolUse entry for Edit|Write|MultiEdit'
    Assert-True ((@($entry.hooks) | ForEach-Object { $_.command }) -match 'hooks/support-guard\.sh') 'the PreToolUse entry does not run hooks/support-guard.sh'
    Assert-True (@($hooks.hooks.SessionStart).Count -ge 1) 'the SessionStart installer hook was lost'
    $attributes = Get-Content -LiteralPath (Join-Path $RepoRoot '.gitattributes') -Raw
    Assert-True ($attributes -match 'plugins/1c-rules/hooks/support-guard\.sh\s+text\s+eol=lf') '.gitattributes does not pin support-guard.sh to LF'
    $bytes = [System.IO.File]::ReadAllBytes($HookSh)
    Assert-True (-not ([System.Text.Encoding]::ASCII.GetString($bytes).Contains("`r"))) 'support-guard.sh has CR line endings in the working tree'
}

# ---------------------------------------------------------------- run

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("1c-rules-hook-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $root -Force | Out-Null
$script:Probe = New-GuardProbe (Join-Path $root 'probe')
Write-Host "Work dir: $root" -ForegroundColor DarkGray
Write-Host "Node:     $NodeExe ($(& $NodeExe --version))" -ForegroundColor DarkGray
Write-Host "Guard:    $GuardAuthority" -ForegroundColor DarkGray
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
        $message = $_.Exception.Message
        if ($message.StartsWith('SKIP: ')) {
            $script:Skipped += $case.Name
            Write-Host "[SKIP] $($case.Name) - $($message.Substring(6))" -ForegroundColor Yellow
            continue
        }
        $script:Failures += "$($case.Name): $message"
        Write-Host "[FAIL] $($case.Name)" -ForegroundColor Red
        Write-Host "       $message" -ForegroundColor Red
    }
}

Write-Host ''
if ($index -eq 0) {
    Write-Host "No case matched filter '$Filter'." -ForegroundColor Yellow
    exit 1
}
$passed = $index - $script:Failures.Count - $script:Skipped.Count
if ($script:Failures.Count -eq 0) {
    Write-Host "$passed/$index passed, $($script:Skipped.Count) skipped." -ForegroundColor Green
    if (-not $KeepWorkDir) { Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue }
    exit 0
}
Write-Host "$passed/$index passed, $($script:Skipped.Count) skipped, $($script:Failures.Count) failed." -ForegroundColor Red
Write-Host "Work dir kept for inspection: $root" -ForegroundColor Yellow
exit 1
