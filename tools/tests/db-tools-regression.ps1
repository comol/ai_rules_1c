#Requires -Version 5.1
<#
.SYNOPSIS
    No-platform regressions for the db-* / epf-* launch tools of the 1c-metadata-manage skill.

.DESCRIPTION
    The tools under content/skills/1c-metadata-manage/tools/1c-db-ops (and epf-build / epf-dump)
    launch the 1C platform. These cases run the real scripts against a FAKE platform: a tiny
    console program compiled here and named 1cv8.exe. It records its command line, writes the
    /DumpResult and /Out files the way the platform does, and exits with a chosen code. No 1C
    platform, licence or infobase is needed, and nothing outside the temp work dir is touched.

    Pinned behaviour:
      - an unhandled error inside try/finally exits 1 (top-level trap), not 0;
      - db-load-xml -Files without -Mode is a partial load, never a full one;
      - a batch command smuggled through .dev.env PLATFORM_ARGS is refused before any launch;
      - repository credentials come from .dev.env REPOSITORY_*, /ConfigurationRepositoryP is
        masked in the printed command line and passed unmasked to the platform;
      - /DumpResult: a non-zero or missing result fails an exit-0 launch;
      - db-update -Dynamic auto/disable, and log failure lines raise its exit code;
      - db-update -SessionTerminate sits right after /UpdateDBCfg (1cv8) / is --session-terminate= (ibcmd)
        and is refused through the additional-argument parameters;
      - the extension applicability check is opt-in (-ApplyCheck);
      - db-cfe-admin refuses an empty -Name/-Extension and gates delete behind -DryRun/-Force.

    NOTE: pure ASCII on purpose (Windows PowerShell 5.1 reads a BOM-less .ps1 as ANSI); Cyrillic
    platform messages are written as \u escapes and decoded at run time.

.PARAMETER Filter
    Run only cases whose name matches this wildcard pattern.

.PARAMETER KeepWorkDir
    Do not delete the temp working directory.

.EXAMPLE
    powershell -NoProfile -File tools\tests\db-tools-regression.ps1
#>
[CmdletBinding()]
param(
    [string]$Filter = '*',
    [switch]$KeepWorkDir
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$ToolsDir = Join-Path $RepoRoot 'content\skills\1c-metadata-manage\tools'
$DbOps    = Join-Path $ToolsDir '1c-db-ops\scripts'
$LoadXml  = Join-Path $DbOps 'db-load-xml.ps1'
$DumpXml  = Join-Path $DbOps 'db-dump-xml.ps1'
$DumpCf   = Join-Path $DbOps 'db-dump-cf.ps1'
$Update   = Join-Path $DbOps 'db-update.ps1'
$CfeAdmin = Join-Path $DbOps 'db-cfe-admin.ps1'
foreach ($required in @($LoadXml, $DumpXml, $DumpCf, $Update, $CfeAdmin)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing prerequisite: $required" }
}

function U([string]$Escaped) { return [regex]::Unescape($Escaped) }

# ---------------------------------------------------------------- infrastructure

$script:Cases    = @()
$script:Failures = @()

function Register-Case([string]$Name, [scriptblock]$Body) {
    $script:Cases += [pscustomobject]@{ Name = $Name; Body = $Body }
}
function Fail([string]$Message) { throw [System.Exception]::new($Message) }
function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { Fail $Message } }
function Assert-Equal($Expected, $Actual, [string]$What) {
    if ("$Expected" -ne "$Actual") { Fail "$What : expected [$Expected], got [$Actual]" }
}

$FakeSource = @'
using System;
using System.IO;
using System.Text;
public static class FakePlatform {
    // FAKE1C_LOG    - append the command line here (one launch per line)
    // FAKE1C_RESULT - text written to the /DumpResult file ("none" = do not write it)
    // FAKE1C_OUT    - UTF-8 file copied into the /Out file
    // FAKE1C_EXIT   - exit code
    public static int Main(string[] args) {
        string log = Environment.GetEnvironmentVariable("FAKE1C_LOG");
        if (!String.IsNullOrEmpty(log)) File.AppendAllText(log, Environment.CommandLine + "\n", new UTF8Encoding(false));
        string result = Environment.GetEnvironmentVariable("FAKE1C_RESULT");
        string outSrc = Environment.GetEnvironmentVariable("FAKE1C_OUT");
        for (int i = 0; i + 1 < args.Length; i++) {
            if (String.Equals(args[i], "/DumpResult", StringComparison.OrdinalIgnoreCase) && result != "none")
                File.WriteAllText(args[i + 1], String.IsNullOrEmpty(result) ? "0" : result);
            if (String.Equals(args[i], "/Out", StringComparison.OrdinalIgnoreCase)) {
                string text = (!String.IsNullOrEmpty(outSrc) && File.Exists(outSrc)) ? File.ReadAllText(outSrc, Encoding.UTF8) : "";
                File.WriteAllText(args[i + 1], text, new UTF8Encoding(true));
            }
        }
        string code = Environment.GetEnvironmentVariable("FAKE1C_EXIT");
        return String.IsNullOrEmpty(code) ? 0 : Int32.Parse(code);
    }
}
'@

# A fake platform install: <root>\fake-platform\bin\1cv8.exe. The install-dir shape is the one
# .dev.env PLATFORM_PATH uses, so it also exercises the bin\1cv8.exe resolution.
function New-FakePlatform([string]$Root) {
    $bin = Join-Path $Root 'fake-platform\bin'
    New-Item -ItemType Directory -Path $bin -Force | Out-Null
    $exe = Join-Path $bin '1cv8.exe'
    Add-Type -TypeDefinition $FakeSource -OutputAssembly $exe -OutputType ConsoleApplication
    return (Split-Path $bin -Parent)
}

# A project dir with .dev.env and an "infobase" that only has to pass the 1Cv8.1CD existence check.
function New-Project([string]$Work, [string[]]$DevEnvLines) {
    $proj = Join-Path $Work 'project'
    New-Item -ItemType Directory -Path (Join-Path $proj 'ib') -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $proj 'ib\1Cv8.1CD'), 'not a real infobase')
    New-Item -ItemType Directory -Path (Join-Path $proj 'src\Catalogs') -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $proj 'src\Catalogs\Item.xml'), '<x/>')
    $lines = @("PLATFORM_PATH=$($script:FakeInstall)") + @($DevEnvLines)
    [IO.File]::WriteAllText((Join-Path $proj '.dev.env'), (($lines -join "`r`n") + "`r`n"), (New-Object System.Text.UTF8Encoding($false)))
    return $proj
}

function Invoke-Tool([string]$Script, [string[]]$ToolArgs, [string]$WorkDir, [hashtable]$Fake = @{}) {
    $stdout = [System.IO.Path]::GetTempFileName()
    $stderr = [System.IO.Path]::GetTempFileName()
    $log = Join-Path $WorkDir ('fake-' + [guid]::NewGuid().ToString('N').Substring(0, 6) + '.log')
    $saved = @{}
    $vars = @{ FAKE1C_LOG = $log; FAKE1C_RESULT = ''; FAKE1C_OUT = ''; FAKE1C_EXIT = '' }
    foreach ($k in $Fake.Keys) { $vars[$k] = $Fake[$k] }
    try {
        foreach ($k in $vars.Keys) {
            $saved[$k] = [Environment]::GetEnvironmentVariable($k)
            [Environment]::SetEnvironmentVariable($k, $vars[$k])
        }
        $psArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$Script`"")
        foreach ($a in $ToolArgs) {
            if ($a -match '\s') { $psArgs += "`"$a`"" } else { $psArgs += $a }
        }
        $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $psArgs `
            -WorkingDirectory $WorkDir -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $launches = @()
        if (Test-Path -LiteralPath $log) {
            $launches = @([IO.File]::ReadAllLines($log, [System.Text.Encoding]::UTF8) | Where-Object { $_ })
        }
        return [pscustomobject]@{
            ExitCode = $proc.ExitCode
            StdOut   = [string](Get-Content -LiteralPath $stdout -Raw -Encoding UTF8)
            StdErr   = [string](Get-Content -LiteralPath $stderr -Raw -Encoding UTF8)
            Launches = $launches
        }
    } finally {
        foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) }
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

function Write-Utf8([string]$Path, [string]$Text) {
    [IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

# ---------------------------------------------------------------- cases

Register-Case 'trap: an unhandled error inside try/finally exits 1, not 0' {
    param($Work)
    # Not an executable: CreateProcess throws inside the script's try/finally. Without the
    # top-level trap PowerShell 5.1 runs finally, continues, and exits 0 with nothing done.
    $bad = Join-Path $Work 'broken\1cv8.exe'
    New-Item -ItemType Directory -Path (Split-Path $bad -Parent) -Force | Out-Null
    Write-Utf8 $bad 'this is not a program'
    New-Item -ItemType Directory -Path (Join-Path $Work 'ib') -Force | Out-Null
    Write-Utf8 (Join-Path $Work 'ib\1Cv8.1CD') 'x'
    $run = Invoke-Tool $DumpCf @('-V8Path', $bad, '-InfoBasePath', (Join-Path $Work 'ib'), '-OutputFile', (Join-Path $Work 'out.cf')) $Work
    Assert-Equal 1 $run.ExitCode "exit code (stdout: $($run.StdOut))"
    Assert-True ($run.StdOut -match 'Error: .*db-dump-cf\.ps1:\d+') "trap message with script:line missing: $($run.StdOut)"
}

Register-Case 'db-load-xml: -Files without -Mode is a partial load' {
    param($Work)
    $proj = New-Project $Work @()
    $run = Invoke-Tool $LoadXml @('-InfoBasePath', 'ib', '-ConfigDir', 'src', '-Files', 'Catalogs/Item.xml') $proj
    Assert-Equal 0 $run.ExitCode "exit code (stdout: $($run.StdOut))"
    Assert-Equal 1 $run.Launches.Count 'platform launches'
    $cmd = $run.Launches[0]
    Assert-True ($cmd -match '/LoadConfigFromFiles' -and $cmd -match '-listFile' -and $cmd -match '-partial') "not a partial load: $cmd"
    Assert-True ($cmd -match '/DumpResult') "no /DumpResult on the launch: $cmd"
    Assert-True ($cmd -match [regex]::Escape((Join-Path $proj 'ib'))) "relative -InfoBasePath not resolved from the .dev.env root: $cmd"
}

Register-Case 'db-load-xml: -AllExtensions with -Files is refused before any launch' {
    param($Work)
    $proj = New-Project $Work @()
    $run = Invoke-Tool $LoadXml @('-InfoBasePath', 'ib', '-ConfigDir', 'src', '-Files', 'Catalogs/Item.xml', '-AllExtensions') $proj
    Assert-Equal 1 $run.ExitCode 'exit code'
    Assert-Equal 0 $run.Launches.Count 'platform launches'
}

Register-Case 'db-dump-xml: -Objects with -Mode Changes dumps only the objects' {
    param($Work)
    $proj = New-Project $Work @()
    $out = Join-Path $proj 'dump'
    New-Item -ItemType Directory -Path $out -Force | Out-Null
    Write-Utf8 (Join-Path $out 'Configuration.xml') '<x/>'
    $run = Invoke-Tool $DumpXml @('-InfoBasePath', 'ib', '-ConfigDir', $out, '-Mode', 'Changes', '-Objects', 'Catalog.Item') $proj
    Assert-Equal 0 $run.ExitCode "exit code (stdout: $($run.StdOut))"
    Assert-True ($run.Launches[0] -match '-listFile' -and $run.Launches[0] -notmatch '-update') "not a partial dump: $($run.Launches[0])"
}

Register-Case 'PLATFORM_ARGS: a smuggled batch command is refused' {
    param($Work)
    $proj = New-Project $Work @('PLATFORM_ARGS=/CheckConfig')
    $run = Invoke-Tool $LoadXml @('-InfoBasePath', 'ib', '-ConfigDir', 'src', '-Files', 'Catalogs/Item.xml') $proj
    Assert-Equal 1 $run.ExitCode 'exit code'
    Assert-True ($run.StdOut -match '/CheckConfig is a batch command') "refusal message missing: $($run.StdOut)"
    Assert-Equal 0 $run.Launches.Count 'platform launches'
}

Register-Case 'repository: .dev.env credentials are passed, the password is masked on screen' {
    param($Work)
    $proj = New-Project $Work @('REPOSITORY_PATH=C:\fake\repo', 'REPOSITORY_USER=dev', 'REPOSITORY_PASSWORD=Pw-31337')
    $run = Invoke-Tool $LoadXml @('-InfoBasePath', 'ib', '-ConfigDir', 'src', '-Files', 'Catalogs/Item.xml') $proj
    Assert-Equal 0 $run.ExitCode "exit code (stdout: $($run.StdOut))"
    $cmd = $run.Launches[0]
    Assert-True ($cmd.Contains('/ConfigurationRepositoryF"C:\fake\repo"')) "repository path not passed: $cmd"
    Assert-True ($cmd.Contains('/ConfigurationRepositoryN"dev"')) "repository user not passed: $cmd"
    Assert-True ($cmd.Contains('/ConfigurationRepositoryP"Pw-31337"')) "repository password not passed: $cmd"
    Assert-True ($run.StdOut.Contains('/ConfigurationRepositoryP***')) "masked token missing: $($run.StdOut)"
    Assert-True (-not $run.StdOut.Contains('Pw-31337')) 'repository password echoed'
}

Register-Case 'repository: an explicit -RepositoryPassword is masked as well' {
    param($Work)
    $proj = New-Project $Work @()
    $run = Invoke-Tool $Update @('-InfoBasePath', 'ib', '-RepositoryPath', 'C:\r', '-RepositoryPassword', 'Xy-777') $proj
    Assert-Equal 0 $run.ExitCode "exit code (stdout: $($run.StdOut))"
    Assert-True ($run.Launches[0].Contains('/ConfigurationRepositoryP"Xy-777"')) "password not passed: $($run.Launches[0])"
    Assert-True (-not $run.StdOut.Contains('Xy-777')) 'repository password echoed'
}

Register-Case 'repository: the hint names the action for a repository-bound infobase' {
    param($Work)
    $proj = New-Project $Work @()
    $logFile = Join-Path $Work 'out.txt'
    Write-Utf8 $logFile (U '\u0442\u0435\u043a\u0443\u0449\u0430\u044f \u043a\u043e\u043d\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u044f \u043f\u043e\u043c\u0435\u0449\u0435\u043d\u0430 \u0432 \u0445\u0440\u0430\u043d\u0438\u043b\u0438\u0449\u0435')
    $run = Invoke-Tool $LoadXml @('-InfoBasePath', 'ib', '-ConfigDir', 'src', '-Mode', 'Full') $proj @{ FAKE1C_OUT = $logFile; FAKE1C_EXIT = '1'; FAKE1C_RESULT = '1' }
    Assert-Equal 1 $run.ExitCode 'exit code'
    Assert-True ($run.StdOut -match '\[hint\].*\r?\n.*1c-repository-manage') "repository hint missing: $($run.StdOut)"
}

Register-Case 'DumpResult: a non-zero or missing batch result fails an exit-0 launch' {
    param($Work)
    $proj = New-Project $Work @()
    $run = Invoke-Tool $DumpCf @('-InfoBasePath', 'ib', '-OutputFile', 'x.cf') $proj @{ FAKE1C_RESULT = '1' }
    Assert-Equal 1 $run.ExitCode 'exit code with result 1'
    Assert-True ($run.StdOut -match 'batch result 1 reported by /DumpResult') "verdict message missing: $($run.StdOut)"
    $run = Invoke-Tool $DumpCf @('-InfoBasePath', 'ib', '-OutputFile', 'x.cf') $proj @{ FAKE1C_RESULT = 'none' }
    Assert-Equal 1 $run.ExitCode 'exit code without a result file'
    Assert-True ($run.StdOut -match '/DumpResult wrote no result') "missing-result message missing: $($run.StdOut)"
}

Register-Case 'DumpResult: every Designer tool of the family passes it' {
    param($Work)
    $proj = New-Project $Work @()
    foreach ($f in @('in.cf', 'in.dt', 'in.epf')) { Write-Utf8 (Join-Path $proj $f) 'x' }
    $calls = @(
        @{ Script = 'db-dump-dt.ps1'; Args = @('-OutputFile', 'x.dt') },
        @{ Script = 'db-load-dt.ps1'; Args = @('-InputFile', 'in.dt') },
        @{ Script = 'db-load-cf.ps1'; Args = @('-InputFile', 'in.cf') },
        @{ Script = '..\..\1c-epf-dump\scripts\epf-dump.ps1'; Args = @('-InputFile', 'in.epf', '-OutputDir', 'out') },
        @{ Script = '..\..\1c-epf-build\scripts\epf-build.ps1'; Args = @('-SourceFile', 'src\Catalogs\Item.xml', '-OutputFile', 'x.epf', '-Checks', 'off') }
    )
    foreach ($c in $calls) {
        $run = Invoke-Tool (Join-Path $DbOps $c.Script) (@('-InfoBasePath', 'ib') + $c.Args) $proj
        Assert-True ($run.Launches.Count -ge 1) "$($c.Script): no platform launch (stdout: $($run.StdOut))"
        Assert-True ($run.Launches[-1] -match '^"[^"]+1cv8\.exe" DESIGNER ' -and $run.Launches[-1] -match '/DumpResult "') "$($c.Script): $($run.Launches[-1])"
    }
}

Register-Case 'db-update: -Dynamic auto / disable reach the platform as -Dynamic+ / -Dynamic-' {
    param($Work)
    $proj = New-Project $Work @()
    $run = Invoke-Tool $Update @('-InfoBasePath', 'ib', '-Dynamic', 'auto') $proj
    Assert-Equal 0 $run.ExitCode "exit code (stdout: $($run.StdOut))"
    Assert-True ($run.Launches[0] -match '-Dynamic\+') "auto: $($run.Launches[0])"
    $run = Invoke-Tool $Update @('-InfoBasePath', 'ib', '-Dynamic', 'disable') $proj
    Assert-True ($run.Launches[0] -match '-Dynamic-(\s|$)') "disable: $($run.Launches[0])"
    $run = Invoke-Tool $Update @('-InfoBasePath', 'ib', '-Dynamic', 'off') $proj
    Assert-True ($run.Launches[0] -match '-Dynamic-(\s|$)') "off: $($run.Launches[0])"
}

Register-Case 'db-update: -SessionTerminate lands right after /UpdateDBCfg (1cv8) and as --session-terminate= (ibcmd)' {
    param($Work)
    $proj = New-Project $Work @()
    $run = Invoke-Tool $Update @('-InfoBasePath', 'ib', '-Dynamic', 'auto', '-SessionTerminate', 'force') $proj
    Assert-Equal 0 $run.ExitCode "1cv8 exit code (stdout: $($run.StdOut))"
    Assert-True ($run.Launches[0] -match '/UpdateDBCfg -Dynamic\+ -SessionTerminate force /Out ') "1cv8 command line: $($run.Launches[0])"
    # The same fake program, named ibcmd.exe, selects the ibcmd branch.
    $ibcmd = Join-Path $script:FakeInstall 'bin\ibcmd.exe'
    Copy-Item -LiteralPath (Join-Path $script:FakeInstall 'bin\1cv8.exe') -Destination $ibcmd -Force
    $run = Invoke-Tool $Update @('-V8Path', $ibcmd, '-InfoBasePath', 'ib', '-SessionTerminate', 'force') $proj
    Assert-Equal 0 $run.ExitCode "ibcmd exit code (stdout: $($run.StdOut))"
    Assert-True ($run.Launches[0] -match 'config apply .*--session-terminate=force') "ibcmd command line: $($run.Launches[0])"
    $run = Invoke-Tool $Update @('-InfoBasePath', 'ib', '-AdditionalV8Arguments:-SessionTerminate,force') $proj
    Assert-True ($run.ExitCode -ne 0) 'a duplicate -SessionTerminate through the additional arguments was accepted'
    Assert-Equal 0 $run.Launches.Count 'the platform was launched despite the refused argument'
    Assert-True ("$($run.StdOut)$($run.StdErr)" -match 'use -SessionTerminate') "no hint to the new parameter: $($run.StdOut)"
    $run = Invoke-Tool $Update @('-V8Path', $ibcmd, '-InfoBasePath', 'ib', '-AdditionalIbcmdArguments:--session-terminate=force') $proj
    Assert-True ($run.ExitCode -ne 0) 'a duplicate --session-terminate through the additional arguments was accepted'
    Assert-True ("$($run.StdOut)$($run.StdErr)" -match 'use -SessionTerminate') "no hint for the ibcmd spelling: $($run.StdOut)"
    $run = Invoke-Tool $Update @('-InfoBasePath', 'ib', '-SessionTerminate', 'maybe') $proj
    Assert-True ($run.ExitCode -ne 0) 'an unknown -SessionTerminate mode was accepted'
    Assert-Equal 0 $run.Launches.Count 'the platform was launched with an unknown mode'
}

Register-Case 'db-update: a failure line in the log raises the exit code' {
    param($Work)
    $proj = New-Project $Work @()
    foreach ($msg in @(
            (U '\u0414\u043b\u044f \u0440\u0430\u0431\u043e\u0442\u044b \u0441 \u043a\u043e\u043d\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u0435\u0439 \u043d\u0435\u043e\u0431\u0445\u043e\u0434\u0438\u043c\u0430 \u0432\u0435\u0440\u0441\u0438\u044f \u043f\u043b\u0430\u0442\u0444\u043e\u0440\u043c\u044b \u043d\u0435 \u043c\u0435\u043d\u044c\u0448\u0435, \u0447\u0435\u043c 8.3.27'),
            (U '\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0438 \u043a\u043e\u043d\u0444\u0438\u0433\u0443\u0440\u0430\u0446\u0438\u0438 \u0431\u0430\u0437\u044b \u0434\u0430\u043d\u043d\u044b\u0445'))) {
        $logFile = Join-Path $Work 'update-out.txt'
        Write-Utf8 $logFile $msg
        $run = Invoke-Tool $Update @('-InfoBasePath', 'ib') $proj @{ FAKE1C_OUT = $logFile }
        Assert-Equal 1 $run.ExitCode "exit code for a log line (stdout: $($run.StdOut))"
        Assert-True ($run.StdOut -match 'failure line') "failure block missing: $($run.StdOut)"
    }
}

Register-Case 'applicability check: off by default, -ApplyCheck runs it with /DumpResult' {
    param($Work)
    $proj = New-Project $Work @()
    $run = Invoke-Tool $LoadXml @('-InfoBasePath', 'ib', '-ConfigDir', 'src', '-Files', 'Catalogs/Item.xml', '-Extension', 'Ext1') $proj
    Assert-Equal 0 $run.ExitCode "exit code (stdout: $($run.StdOut))"
    Assert-Equal 1 $run.Launches.Count 'launches without -ApplyCheck'
    $run = Invoke-Tool $LoadXml @('-InfoBasePath', 'ib', '-ConfigDir', 'src', '-Files', 'Catalogs/Item.xml', '-Extension', 'Ext1', '-ApplyCheck') $proj
    Assert-Equal 0 $run.ExitCode "exit code with -ApplyCheck (stdout: $($run.StdOut))"
    Assert-Equal 2 $run.Launches.Count 'launches with -ApplyCheck'
    Assert-True ($run.Launches[1] -match '/CheckCanApplyConfigurationExtensions' -and $run.Launches[1] -match '/DumpResult') "check launch: $($run.Launches[1])"
    # A refusal fails the run when the check was asked for. The fake writes the same /Out text for
    # both launches: harmless in the load log, a refusal line for the applicability check.
    $refusal = Join-Path $Work 'refusal.txt'
    Write-Utf8 $refusal 'Extension Ext1: method Item.OnWrite not found'
    $run = Invoke-Tool $LoadXml @('-InfoBasePath', 'ib', '-ConfigDir', 'src', '-Files', 'Catalogs/Item.xml', '-Extension', 'Ext1', '-ApplyCheck') $proj @{ FAKE1C_OUT = $refusal }
    Assert-Equal 1 $run.ExitCode "exit code for a refused extension (stdout: $($run.StdOut))"
    Assert-True ($run.StdOut -match 'will not apply it') "refusal block missing: $($run.StdOut)"
}

Register-Case 'db-cfe-admin: empty extension name never reaches the platform' {
    param($Work)
    $proj = New-Project $Work @()
    foreach ($param in @('-Name', '-Extension')) {
        $run = Invoke-Tool $CfeAdmin @('-Command', 'delete', '-InfoBasePath', 'ib', $param, '""', '-Force') $proj
        Assert-Equal 1 $run.ExitCode "exit code for $param empty"
        Assert-Equal 0 $run.Launches.Count "launches for $param empty"
    }
    $run = Invoke-Tool $CfeAdmin @('-Command', 'delete', '-InfoBasePath', 'ib', '-Force') $proj
    Assert-Equal 1 $run.ExitCode 'exit code without a name'
    Assert-Equal 0 $run.Launches.Count 'launches without a name'
}

Register-Case 'db-cfe-admin: delete prints the plan with -DryRun and needs -Force' {
    param($Work)
    $proj = New-Project $Work @()
    $listOut = Join-Path $Work 'list.txt'
    Write-Utf8 $listOut "Ext1`r`nExt2`r`n"
    $run = Invoke-Tool $CfeAdmin @('-Command', 'delete', '-InfoBasePath', 'ib', '-Extension', 'Ext2', '-DryRun') $proj @{ FAKE1C_OUT = $listOut }
    Assert-Equal 0 $run.ExitCode "dry-run exit code (stdout: $($run.StdOut))"
    Assert-True ($run.StdOut -match 'Ext2' -and $run.StdOut -match 'DRY-RUN') "plan missing: $($run.StdOut)"
    Assert-True (-not ($run.Launches -match '/DeleteCfg')) 'dry-run deleted'
    $run = Invoke-Tool $CfeAdmin @('-Command', 'delete', '-InfoBasePath', 'ib', '-Extension', 'Ext2') $proj @{ FAKE1C_OUT = $listOut }
    Assert-Equal 2 $run.ExitCode 'exit code without -Force'
    Assert-True (-not ($run.Launches -match '/DeleteCfg')) 'deleted without -Force'
    Assert-True ($run.Launches[0] -match '/DumpDBCfgList' -and $run.Launches[0] -match '/DumpResult') "list launch: $($run.Launches[0])"
}

# ---------------------------------------------------------------- run

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("1c-rules-dbregr-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $root -Force | Out-Null
Write-Host "Work dir: $root" -ForegroundColor DarkGray
$script:FakeInstall = New-FakePlatform $root
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
