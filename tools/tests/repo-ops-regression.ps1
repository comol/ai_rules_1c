#Requires -Version 5.1
<#
.SYNOPSIS
    Offline regression tests for repo-ops.ps1 of the 1c-repository-manage skill.

.DESCRIPTION
    No 1C platform and no repository: every case runs the real repo-ops.ps1 against a
    fake 1cv8.exe compiled here. The fake finds /Out, /DumpResult and -Objects in its
    command line, copies a sample /Out log into place, writes the /DumpResult number,
    keeps a copy of the command line and of the objects XML, and exits with the code the
    case asks for.

    The sample logs under fixtures/repo-ops are built from the exact message texts the
    platform writes for repository operations, as recorded by upstream db-repo
    (Nikolay-Shirokov/cc-1c-skills): the lock is not atomic, "already locked by you"
    prints nothing, an unlock of an object you do not hold is a no-op line.

    NOTE: this file is deliberately pure ASCII, like tools/validate-rules.ps1 - Windows
    PowerShell 5.1 reads a BOM-less .ps1 as ANSI. Every Cyrillic object name comes from
    fixtures/repo-ops/names.txt.

.PARAMETER Filter
    Run only cases whose name matches this wildcard pattern.

.PARAMETER KeepWorkDir
    Do not delete the temp working directory - useful when a case fails.

.EXAMPLE
    powershell -NoProfile -File tools\tests\repo-ops-regression.ps1
#>
[CmdletBinding()]
param(
    [string]$Filter = '*',
    [switch]$KeepWorkDir
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot    = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$FixturesDir = Join-Path $PSScriptRoot 'fixtures\repo-ops'
$RepoOps     = Join-Path $RepoRoot 'content\skills\1c-repository-manage\tools\1c-repo-ops\scripts\repo-ops.ps1'

foreach ($required in @($RepoOps, $FixturesDir)) {
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

function Assert-Contains([string]$Text, [string]$Needle, [string]$What) {
    if (-not $Text -or -not $Text.Contains($Needle)) { Fail "$What : output does not contain [$Needle]`n----`n$Text" }
}

function Assert-NotContains([string]$Text, [string]$Needle, [string]$What) {
    if ($Text -and $Text.Contains($Needle)) { Fail "$What : output unexpectedly contains [$Needle]" }
}

$script:Names = @{}
foreach ($line in [System.IO.File]::ReadAllLines((Join-Path $FixturesDir 'names.txt'), [System.Text.Encoding]::UTF8)) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $k, $v = $line -split '=', 2
    $script:Names[$k.Trim()] = $v.Trim()
}
function N([string]$Key) {
    if (-not $script:Names.ContainsKey($Key)) { throw "names.txt has no key $Key" }
    return $script:Names[$Key]
}

$FakeSource = @'
using System;
using System.IO;
using System.Text;

public static class Fake1cv8
{
    public static int Main(string[] args)
    {
        string outPath = null, resultPath = null, objectsPath = null, reportPath = null;
        for (int i = 0; i < args.Length - 1; i++)
        {
            string a = args[i];
            if (string.Equals(a, "/Out", StringComparison.OrdinalIgnoreCase)) outPath = args[i + 1];
            else if (string.Equals(a, "/DumpResult", StringComparison.OrdinalIgnoreCase)) resultPath = args[i + 1];
            else if (string.Equals(a, "-Objects", StringComparison.OrdinalIgnoreCase)) objectsPath = args[i + 1];
            else if (string.Equals(a, "/ConfigurationRepositoryReport", StringComparison.OrdinalIgnoreCase)) reportPath = args[i + 1];
        }
        string capture = Environment.GetEnvironmentVariable("FAKE1C_CAPTURE");
        if (!string.IsNullOrEmpty(capture))
        {
            File.WriteAllText(capture, Environment.CommandLine, new UTF8Encoding(true));
            if (objectsPath != null && File.Exists(objectsPath)) File.Copy(objectsPath, capture + ".objects.xml", true);
        }
        string log = Environment.GetEnvironmentVariable("FAKE1C_LOG");
        if (outPath != null && !string.IsNullOrEmpty(log) && File.Exists(log)) File.Copy(log, outPath, true);
        if (reportPath != null) File.WriteAllText(reportPath, "fake repository report", new UTF8Encoding(true));
        int exit = 0;
        int.TryParse(Environment.GetEnvironmentVariable("FAKE1C_EXIT") ?? "0", out exit);
        string result = Environment.GetEnvironmentVariable("FAKE1C_RESULT");
        if (resultPath != null && result != "none")
            File.WriteAllText(resultPath, string.IsNullOrEmpty(result) ? exit.ToString() : result);
        return exit;
    }
}
'@

function New-FakePlatform([string]$Dir) {
    New-Item -ItemType Directory -Path $Dir -Force | Out-Null
    $exe = Join-Path $Dir '1cv8.exe'
    Add-Type -TypeDefinition $FakeSource -OutputAssembly $exe -OutputType ConsoleApplication
    return $exe
}

# One case = one work dir with a .dev.env (so discovery never walks into the real
# environment), a fake infobase and a private TEMP.
function New-RepoCase([string]$Work, [string[]]$DevEnv = @()) {
    $ib = Join-Path $Work 'ib'
    New-Item -ItemType Directory -Path $ib -Force | Out-Null
    [System.IO.File]::WriteAllBytes((Join-Path $ib '1Cv8.1CD'), [byte[]]@())
    $tmp = Join-Path $Work 'tmp'
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    $lines = @('# repo-ops regression case') + $DevEnv
    [System.IO.File]::WriteAllText((Join-Path $Work '.dev.env'), (($lines -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding($false)))
    return [pscustomobject]@{ Work = $Work; Ib = $ib; Tmp = $tmp; Capture = (Join-Path $Work 'capture.txt') }
}

function Invoke-RepoOps($Case, [string[]]$ToolArgs, [string]$Log = '', [int]$Exit = 0, [string]$Result = '', [switch]$NoDefaults) {
    $stdout = Join-Path $Case.Work ('stdout-' + [guid]::NewGuid().ToString('N') + '.txt')
    $stderr = $stdout + '.err'
    Remove-Item -LiteralPath $Case.Capture, ($Case.Capture + '.objects.xml') -Force -ErrorAction SilentlyContinue
    $saved = @{}
    foreach ($k in 'FAKE1C_LOG', 'FAKE1C_EXIT', 'FAKE1C_RESULT', 'FAKE1C_CAPTURE', 'TEMP', 'TMP') { $saved[$k] = [Environment]::GetEnvironmentVariable($k) }
    try {
        $env:FAKE1C_LOG = if ($Log) { Join-Path $FixturesDir $Log } else { '' }
        $env:FAKE1C_EXIT = "$Exit"
        $env:FAKE1C_RESULT = $Result
        $env:FAKE1C_CAPTURE = $Case.Capture
        $env:TEMP = $Case.Tmp
        $env:TMP = $Case.Tmp
        $all = @()
        if (-not $NoDefaults) {
            $all += @('-V8Path', $script:FakeExe, '-InfoBasePath', $Case.Ib, '-RepositoryPath', (Join-Path $Case.Work 'repo'), '-RepositoryUser', 'Admin')
        }
        $all += $ToolArgs
        $psArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$RepoOps`"")
        foreach ($a in $all) {
            if ($a -match '[\s]' -or $a -eq '') { $psArgs += "`"$a`"" } else { $psArgs += $a }
        }
        $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $psArgs `
            -WorkingDirectory $Case.Work -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $out = [System.IO.File]::ReadAllText($stdout, [System.Text.Encoding]::UTF8)
        $err = [System.IO.File]::ReadAllText($stderr, [System.Text.Encoding]::UTF8)
        $objects = $null
        if (Test-Path -LiteralPath ($Case.Capture + '.objects.xml')) {
            $objects = [System.IO.File]::ReadAllText(($Case.Capture + '.objects.xml'), [System.Text.Encoding]::UTF8)
        }
        $cmd = $null
        if (Test-Path -LiteralPath $Case.Capture) { $cmd = [System.IO.File]::ReadAllText($Case.Capture, [System.Text.Encoding]::UTF8) }
        return [pscustomobject]@{
            ExitCode = $proc.ExitCode; Out = ($out + $err); Objects = $objects
            CommandLine = $cmd; Launched = ($null -ne $cmd)
        }
    } finally {
        foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) }
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------- cases: lock

Register-Case 'lock: a partial lock reports every object and fails as a conflict' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'lock', '-Objects', (N 'catalog'), '-IncludeChildObjects') 'lock-partial.log' 1
    Assert-Equal 1 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'Locked by you now (1):' 'locked list'
    Assert-Contains $r.Out ("  " + (N 'catalog')) 'locked object named'
    Assert-Contains $r.Out ((N 'form') + ' ') 'blocked object named'
    Assert-Contains $r.Out 'held by Ivanov' 'holder named'
    Assert-Contains $r.Out '[partial]' 'partial lock called out'
    Assert-Contains $r.Out 'never resolve it with -Force' 'conflict rule'
}

Register-Case 'lock: every requested object held by another user is a plain conflict' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'lock', '-Objects', (N 'catalog')) 'lock-all-blocked.log' 1
    Assert-Equal 1 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'held by Ivanov' 'holder named'
    Assert-NotContains $r.Out '[partial]' 'nothing of ours is held'
}

Register-Case 'lock: already locked by you prints nothing and is a no-op success' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'lock', '-Objects', (N 'catalog')) '' 0
    Assert-Equal 0 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'Already locked by you' 'no-op named'
    Assert-Contains $r.CommandLine '/DumpResult' 'batch verdict file requested'
    Assert-Contains $r.CommandLine '/DisableStartupMessages' 'startup messages disabled'
}

Register-Case 'lock: received objects are listed, saved and get the export command' {
    param($Work)
    $c = New-RepoCase $Work @('EXPORT_PATH=src/cf')
    $r = Invoke-RepoOps $c @('-Operation', 'lock', '-Objects', (N 'catalog'), '-Revised') 'lock-received.log' 0
    Assert-Equal 0 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'objects received from the repository (1):' 'received named'
    Assert-Contains $r.Out 'db-dump-xml.ps1' 'export command printed'
    Assert-Contains $r.Out '-Mode Partial -ObjectsFile' 'objects file passed'
    Assert-Contains $r.Out '-ConfigDir "src/cf"' 'EXPORT_PATH used'
    Assert-Contains $r.CommandLine '-revised' 'revised passed'
    $m = [regex]::Match($r.Out, 'Received objects list \(one owner per line\): (\S+)')
    Assert-True $m.Success 'received list path printed'
    $listed = @([System.IO.File]::ReadAllLines($m.Groups[1].Value, [System.Text.Encoding]::UTF8))
    Assert-Equal (N 'catalog') ($listed -join '|') 'received list content'
}

Register-Case 'lock: a clean lock suggests no re-export' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'lock', '-Objects', (N 'partner')) 'lock-owner.log' 0
    Assert-Equal 0 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'Locked by you now (1):' 'locked list'
    Assert-NotContains $r.Out 'received from the repository' 'no received warning'
    Assert-NotContains $r.Out 'db-dump-xml' 'no export command'
}

Register-Case 'lock: an attribute and a tabular section lock their owner once' {
    param($Work)
    $c = New-RepoCase $Work
    $objects = (N 'partnerAttr') + ',' + (N 'partnerTs')
    $r = Invoke-RepoOps $c @('-Operation', 'lock', '-Objects', $objects) 'lock-owner.log' 0
    Assert-Equal 0 $r.ExitCode 'exit code'
    Assert-Contains $r.Out ((N 'partnerAttr') + ' -> ' + (N 'partner')) 'substitution named'
    Assert-True ($null -ne $r.Objects) 'objects XML passed to the platform'
    Assert-Equal 1 ([regex]::Matches($r.Objects, '<Object ')).Count 'one object entry'
    Assert-Contains $r.Objects ('fullName="' + (N 'partner') + '"') 'owner in the list'
}

Register-Case 'lock: the root alone is allowed, the root with child objects is refused' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'lock', '-Objects', (N 'root')) '' 0
    Assert-Equal 0 $r.ExitCode 'root-only lock'
    Assert-Contains $r.Objects '<Configuration includeChildObjects="false"/>' 'root element'
    Assert-NotContains $r.Objects 'fullName=' 'no object entry for the root'
    $r = Invoke-RepoOps $c @('-Operation', 'lock', '-Objects', 'Configuration', '-IncludeChildObjects') '' 0
    Assert-Equal 1 $r.ExitCode 'root with children'
    Assert-Contains $r.Out 'means the WHOLE configuration' 'refusal names the scope'
    Assert-True (-not $r.Launched) 'platform not started'
    $r = Invoke-RepoOps $c @('-Operation', 'commit', '-Objects', ((N 'root') + ',' + (N 'partner')), '-Comment', 'TASK-1: new catalog') 'commit-unchanged.log' 0
    Assert-Equal 0 $r.ExitCode 'root plus new object commit'
    Assert-Contains $r.Objects '<Configuration includeChildObjects="false"/>' 'root in the commit list'
    Assert-Contains $r.Objects ('fullName="' + (N 'partner') + '"') 'new object in the commit list'
}

# ---------------------------------------------------------------- cases: unlock / commit / update

Register-Case 'unlock: an object you do not hold is a no-op, not a failure' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'unlock', '-Objects', (N 'catalog')) 'unlock-noop.log' 0
    Assert-Equal 0 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'nothing to release (no-op)' 'no-op named'
    Assert-NotContains $r.Out 'failure line' 'not elevated by the log scan'
}

Register-Case 'unlock: local changes refuse the unlock and name the objects' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'unlock', '-Objects', (N 'catalog')) 'unlock-modified.log' 1
    Assert-Equal 1 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'Unlock refused: these objects have local changes (1):' 'refusal named'
}

Register-Case 'commit: nothing changed creates no version and says so' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'commit', '-Objects', (N 'catalog'), '-Comment', 'TASK-1: x') 'commit-unchanged.log' 0
    Assert-Equal 0 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'Unchanged - not committed (1):'.Replace(' - ', ' ' + [char]0x2014 + ' ') 'unchanged list'
    Assert-Contains $r.Out 'No new repository version was created' 'no version'
}

Register-Case 'update: success without an operation block means an unbound infobase' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'update', '-Objects', (N 'catalog')) 'update-unbound.log' 0
    Assert-Equal 1 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'printed no repository operation block' 'refusal named'
    $r = Invoke-RepoOps $c @('-Operation', 'update', '-Objects', (N 'catalog')) 'update-current.log' 0
    Assert-Equal 0 $r.ExitCode 'bound and current'
    Assert-Contains $r.Out 'already current' 'nothing to receive'
}

Register-Case 'missing objects and an empty platform list are errors' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'lock', '-Objects', (N 'missing')) 'missing.log' 0
    Assert-Equal 1 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'objects not found in the configuration (1):' 'missing named'
    Assert-Contains $r.Out (N 'missing') 'missing object printed'
}

# ---------------------------------------------------------------- cases: verdict and connection

Register-Case 'verdict: /DumpResult decides when the exit code is 0' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'commit', '-Objects', (N 'catalog'), '-Comment', 'TASK-1: x') 'commit-unchanged.log' 0 'none'
    Assert-Equal 1 $r.ExitCode 'result file missing'
    Assert-Contains $r.Out '/DumpResult was not written' 'missing result named'
    $r = Invoke-RepoOps $c @('-Operation', 'commit', '-Objects', (N 'catalog'), '-Comment', 'TASK-1: x') 'commit-unchanged.log' 0 '101'
    Assert-True ($r.ExitCode -ne 0) 'non-zero result fails the run'
    Assert-Contains $r.Out '/DumpResult reports 101' 'result value named'
}

Register-Case 'connection: tcp server unreachable versus missing credentials' {
    param($Work)
    $c = New-RepoCase $Work
    $r = Invoke-RepoOps $c @('-Operation', 'status', '-V8Path', $script:FakeExe, '-InfoBasePath', $c.Ib, '-RepositoryPath', 'tcp://srv01/app', '-RepositoryUser', 'Admin') 'connection.log' 1 -NoDefaults
    Assert-Equal 1 $r.ExitCode 'exit code'
    Assert-Contains $r.Out 'repository server unreachable at srv01:1542' 'server named'
    Assert-NotContains $r.Out 'credentials missing' 'credentials are set'
    $r = Invoke-RepoOps $c @('-Operation', 'status', '-V8Path', $script:FakeExe, '-InfoBasePath', $c.Ib, '-RepositoryPath', 'tcp://srv01:2541/app') 'connection.log' 1 -NoDefaults
    Assert-Contains $r.Out 'repository credentials missing' 'empty user named'
    Assert-Contains $r.Out 'srv01:2541' 'explicit port kept'
    $r = Invoke-RepoOps $c @('-Operation', 'status', '-V8Path', $script:FakeExe, '-InfoBasePath', $c.Ib, '-RepositoryPath', 'tcp://srv01/app', '-RepositoryUser', 'Admin') 'connection.log' 0 -NoDefaults
    Assert-Equal 1 $r.ExitCode 'exit 0 with the connection line is elevated'
}

# ---------------------------------------------------------------- cases: gates

Register-Case 'gates: empty list, wildcard and force stay refused before any launch' {
    param($Work)
    $c = New-RepoCase $Work
    foreach ($callArgs in @(
            @('-Operation', 'lock'),
            @('-Operation', 'commit', '-Objects', '*', '-Comment', 'x'),
            @('-Operation', 'commit', '-Objects', (N 'catalog')),
            @('-Operation', 'unlock', '-Objects', (N 'catalog'), '-Force', '-ConfirmDiscardChanges'),
            @('-Operation', 'status', '-Objects', (N 'catalog')))) {
        $r = Invoke-RepoOps $c $callArgs '' 0
        Assert-Equal 1 $r.ExitCode ("refused: " + ($callArgs -join ' '))
        Assert-True (-not $r.Launched) ("platform not started: " + ($callArgs -join ' '))
    }
    $c2 = New-RepoCase (Join-Path $Work 'allow') @('REPOSITORY_ALLOW_FORCE=true')
    $r = Invoke-RepoOps $c2 @('-Operation', 'update', '-Objects', (N 'catalog'), '-Force') '' 0
    Assert-Equal 1 $r.ExitCode 'force without confirmation'
    Assert-True (-not $r.Launched) 'platform not started without confirmation'
}

Register-Case 'gates: INFOBASE_ROLE=prod allows only read-only operations on the project base' {
    param($Work)
    $c = New-RepoCase $Work @('INFOBASE_PATH=ib', 'INFOBASE_ROLE=prod', 'REPOSITORY_PATH=repo', 'REPOSITORY_USER=Admin')
    $base = @('-V8Path', $script:FakeExe)
    $r = Invoke-RepoOps $c ($base + @('-Operation', 'lock', '-Objects', (N 'catalog'))) '' 0 -NoDefaults
    Assert-Equal 1 $r.ExitCode 'lock refused'
    Assert-Contains $r.Out 'INFOBASE_ROLE=prod' 'role named'
    Assert-True (-not $r.Launched) 'platform not started'
    $r = Invoke-RepoOps $c ($base + @('-Operation', 'lock', '-Objects', (N 'catalog'), '-InfoBasePath', $c.Ib)) '' 0 -NoDefaults
    Assert-Equal 1 $r.ExitCode 'the same base spelled explicitly is refused too'
    $r = Invoke-RepoOps $c ($base + @('-Operation', 'status')) '' 0 -NoDefaults
    Assert-Equal 0 $r.ExitCode 'status runs'
    Assert-Contains $r.CommandLine ('/F "' + $c.Ib + '"') 'relative INFOBASE_PATH anchored at the .dev.env root'
}

# ---------------------------------------------------------------- run

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("1c-rules-repo-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $root -Force | Out-Null
Write-Host "Work dir: $root" -ForegroundColor DarkGray
$script:FakeExe = New-FakePlatform (Join-Path $root 'fake-platform\bin')
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
