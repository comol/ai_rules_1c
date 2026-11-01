#Requires -Version 5.1
<#
.SYNOPSIS
    Offline regression tests for the PowerShell web-* tools of 1c-metadata-manage.

.DESCRIPTION
    No Apache and no 1C platform: each case builds an Apache-shaped tree whose
    bin\httpd.exe is a fake compiled here (it only sleeps FAKE_HTTPD_MS milliseconds and
    exits), and an empty wsap24.dll. web-publish then "starts" the fake, so the real
    script runs end to end and the cases assert on default.vrd, httpd.conf and stdout.
    The Python ports are covered by tools/tests/web-python-regression.py.

    NOTE: this file is deliberately pure ASCII (Windows PowerShell 5.1 reads a BOM-less
    .ps1 as ANSI); the assertions use the ASCII parts of the tools' output.

.PARAMETER Filter
    Run only cases whose name matches this wildcard pattern.

.PARAMETER KeepWorkDir
    Do not delete the temp working directory - useful when a case fails.

.EXAMPLE
    powershell -NoProfile -File tools\tests\web-ops-regression.ps1
#>
[CmdletBinding()]
param(
    [string]$Filter = '*',
    [switch]$KeepWorkDir
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot   = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$WebScripts = Join-Path $RepoRoot 'content\skills\1c-metadata-manage\tools\1c-web-ops\scripts'
$Publish    = Join-Path $WebScripts 'web-publish.ps1'
$Info       = Join-Path $WebScripts 'web-info.ps1'
$Stop       = Join-Path $WebScripts 'web-stop.ps1'
$Unpublish  = Join-Path $WebScripts 'web-unpublish.ps1'

foreach ($required in @($Publish, $Info, $Stop, $Unpublish)) {
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
    if (-not $Text -or -not $Text.Contains($Needle)) { Fail "$What : text does not contain [$Needle]`n----`n$Text" }
}

function Assert-NotContains([string]$Text, [string]$Needle, [string]$What) {
    if ($Text -and $Text.Contains($Needle)) { Fail "$What : text unexpectedly contains [$Needle]" }
}

$FakeHttpdSource = @'
using System;
using System.Threading;

public static class FakeHttpd
{
    public static int Main(string[] args)
    {
        int ms = 0;
        int.TryParse(Environment.GetEnvironmentVariable("FAKE_HTTPD_MS") ?? "0", out ms);
        if (ms > 0) Thread.Sleep(ms);
        return 0;
    }
}
'@

function Get-FreePort {
    for ($i = 0; $i -lt 50; $i++) {
        $p = Get-Random -Minimum 18100 -Maximum 18999
        if (-not (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)) { return $p }
    }
    throw 'no free port found'
}

function Write-Utf8([string]$Path, [string]$Text, [switch]$Bom) {
    New-Item -ItemType Directory -Path (Split-Path $Path -Parent) -Force | Out-Null
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($Bom.IsPresent)))
}

# Apache-shaped tree with the fake httpd, a platform dir with an empty wsap24.dll, a
# file-infobase dir and a .dev.env so discovery never leaves the case directory.
function New-WebCase([string]$Work, [string]$ApacheRel = 'apache', [string]$Conf = '', [string[]]$DevEnv = @()) {
    $apache = Join-Path $Work $ApacheRel
    New-Item -ItemType Directory -Path (Join-Path $apache 'bin'), (Join-Path $apache 'logs') -Force | Out-Null
    Copy-Item -LiteralPath $script:FakeHttpd -Destination (Join-Path $apache 'bin\httpd.exe')
    if (-not $Conf) {
        $Conf = "Define SRVROOT `"c:/Apache24`"`nServerRoot `"`${SRVROOT}`"`nListen 80`nErrorLog `"logs/error.log`"`n# keep me`n"
    }
    Write-Utf8 (Join-Path $apache 'conf\httpd.conf') $Conf
    $platform = Join-Path $Work 'platform'
    Write-Utf8 (Join-Path $platform 'bin\wsap24.dll') ''
    $ib = Join-Path $Work 'ib'
    New-Item -ItemType Directory -Path $ib -Force | Out-Null
    Write-Utf8 (Join-Path $Work '.dev.env') ((@('# web-ops regression case') + $DevEnv) -join "`n")
    return [pscustomobject]@{
        Work = $Work; Apache = $apache; Conf = (Join-Path $apache 'conf\httpd.conf')
        Platform = $platform; Bin = (Join-Path $platform 'bin'); Ib = $ib
        Httpd = (Join-Path $apache 'bin\httpd.exe')
    }
}

function Stop-FakeHttpd($Case) {
    Get-Process httpd -ErrorAction SilentlyContinue |
        Where-Object { try { $_.Path -eq $Case.Httpd } catch { $false } } |
        Stop-Process -Force -ErrorAction SilentlyContinue
}

function Invoke-WebTool([string]$Script, [string[]]$ToolArgs, [string]$WorkDir, [int]$HttpdMs = 0) {
    $stdout = Join-Path $WorkDir ('stdout-' + [guid]::NewGuid().ToString('N') + '.txt')
    $stderr = $stdout + '.err'
    $savedMs = $env:FAKE_HTTPD_MS
    try {
        $env:FAKE_HTTPD_MS = "$HttpdMs"
        $psArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$Script`"")
        foreach ($a in $ToolArgs) {
            if ($a -match '\s' -or $a -eq '') { $psArgs += "`"$a`"" } else { $psArgs += $a }
        }
        $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $psArgs `
            -WorkingDirectory $WorkDir -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $out = [System.IO.File]::ReadAllText($stdout, [System.Text.Encoding]::UTF8) + [System.IO.File]::ReadAllText($stderr, [System.Text.Encoding]::UTF8)
        return [pscustomobject]@{ ExitCode = $proc.ExitCode; Out = $out }
    } finally {
        $env:FAKE_HTTPD_MS = $savedMs
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

function Get-Tree([string]$Root) {
    $h = @{}
    foreach ($f in (Get-ChildItem -LiteralPath $Root -Recurse -File)) {
        $h[$f.FullName.Substring($Root.Length)] = (Get-FileHash -LiteralPath $f.FullName).Hash
    }
    return (($h.Keys | Sort-Object | ForEach-Object { "$_=$($h[$_])" }) -join "`n")
}

# ---------------------------------------------------------------- cases: web-publish

Register-Case 'web-publish: credentials are XML-escaped in default.vrd, a quote is refused' {
    param($Work)
    $c = New-WebCase $Work
    $port = Get-FreePort
    try {
        $r = Invoke-WebTool $Publish @('-V8Path', $c.Bin, '-InfoBasePath', $c.Ib, '-AppName', 'demo',
            '-UserName', 'u&<1', '-Password', 'p&w<x>;y', '-ApachePath', $c.Apache, '-Port', "$port") $Work 4000
        Assert-Equal 0 $r.ExitCode "publish exit`n$($r.Out)"
        Assert-Contains $r.Out "http://localhost:$port/demo" 'URL printed'
        $vrd = [xml][System.IO.File]::ReadAllText((Join-Path $c.Apache 'publish\demo\default.vrd'))
        Assert-Equal ('File="' + $c.Ib + '";Usr="u&<1";Pwd="p&w<x>;y";') $vrd.point.ib 'ib attribute round-trips'
        Assert-Equal 'true' $vrd.point.ws.publishExtensionsByDefault 'extension SOAP services published'
        Assert-Equal 'true' $vrd.point.httpServices.publishExtensionsByDefault 'extension HTTP services published'
        Assert-Equal 'true' $vrd.point.standardOdata.enable 'OData element'
        $conf = [System.IO.File]::ReadAllText($c.Conf)
        Assert-True ($conf -match "(?m)^Listen $port\s*$") 'own listener'
        Assert-True ($conf -match '(?m)^#Listen 80') 'stock listener commented'
        Assert-Contains $conf '# keep me' 'unrelated settings kept'
    } finally { Stop-FakeHttpd $c }
    $r = Invoke-WebTool $Publish @('-V8Path', $c.Bin, '-InfoBasePath', $c.Ib, '-AppName', 'quoted',
        '-Password', 'a\"b', '-ApachePath', $c.Apache, '-Port', "$port") $Work
    Assert-Equal 1 $r.ExitCode 'quote in a password'
    Assert-True (-not (Test-Path (Join-Path $c.Apache 'publish\quoted'))) 'nothing written for a refused password'
    $r = Invoke-WebTool $Publish @('-V8Path', $c.Bin, '-InfoBasePath', $c.Ib, '-AppName', 'a.b',
        '-ApachePath', $c.Apache, '-Port', "$port") $Work
    Assert-Equal 1 $r.ExitCode 'invalid AppName'
}

Register-Case 'web-publish: rewriting the global block keeps bind address, PidFile and ErrorLog' {
    param($Work)
    $conf = @(
        '#Listen 80  # commented by web-publish.py',
        '# --- 1C: global ---',
        'Listen 127.0.0.1:18081',
        'LoadModule _1cws_module "C:/old/bin/wsap24.dll"',
        'PidFile "C:/py/logs/1c-web-httpd.pid"',
        'ErrorLog "C:/py/logs/error.log"',
        '# --- End: global ---', '') -join "`n"
    $c = New-WebCase $Work -Conf $conf
    $port = Get-FreePort
    try {
        $r = Invoke-WebTool $Publish @('-V8Path', $c.Bin, '-InfoBasePath', $c.Ib, '-AppName', 'demo',
            '-ApachePath', $c.Apache, '-Port', "$port") $Work 4000
        Assert-Equal 0 $r.ExitCode "publish exit`n$($r.Out)"
        Assert-Contains $r.Out "http://127.0.0.1:$port/demo" 'URL uses the bind address'
        $text = [System.IO.File]::ReadAllText($c.Conf)
        $block = [regex]::Match($text, '(?s)# --- 1C: global ---(.*?)# --- End: global ---').Groups[1].Value
        Assert-True ($block -match "(?m)^Listen 127\.0\.0\.1:$port\s*$") 'bind address kept, port changed'
        Assert-True ($block -notmatch "(?m)^Listen $port\s*$") 'no all-interfaces listener'
        Assert-Contains $block 'PidFile "C:/py/logs/1c-web-httpd.pid"' 'PidFile kept'
        Assert-Contains $block 'ErrorLog "C:/py/logs/error.log"' 'ErrorLog kept'
        Assert-Contains $block ('LoadModule _1cws_module "' + ($c.Bin -replace '\\', '/') + '/wsap24.dll"') 'module path refreshed'
        Assert-NotContains $block 'C:/old/' 'old module dropped'
    } finally { Stop-FakeHttpd $c }
}

Register-Case 'web-publish: .dev.env PLATFORM_PATH install dir, relative -InfoBasePath at the .dev.env root' {
    param($Work)
    $c = New-WebCase $Work -DevEnv @("PLATFORM_PATH=$Work\platform")
    $nested = Join-Path $Work 'nested'
    New-Item -ItemType Directory -Path $nested -Force | Out-Null
    $port = Get-FreePort
    try {
        $r = Invoke-WebTool $Publish @('-InfoBasePath', 'ib', '-AppName', 'rel', '-ApachePath', $c.Apache, '-Port', "$port") $nested 4000
        Assert-Equal 0 $r.ExitCode "publish exit`n$($r.Out)"
        $vrd = [xml][System.IO.File]::ReadAllText((Join-Path $c.Apache 'publish\rel\default.vrd'))
        Assert-Equal ('File="' + $c.Ib + '";') $vrd.point.ib 'anchored at the .dev.env directory'
    } finally { Stop-FakeHttpd $c }
    $r = Invoke-WebTool $Publish @('-InfoBasePath', 'C:ib', '-AppName', 'drive', '-ApachePath', $c.Apache, '-Port', "$port") $nested
    Assert-Equal 1 $r.ExitCode 'drive-relative path refused'
    Assert-True (-not (Test-Path (Join-Path $c.Apache 'publish\drive'))) 'nothing written for C:x'
}

# ---------------------------------------------------------------- cases: web-info / web-stop / web-unpublish

Register-Case 'web-info: bind address, effective ErrorLog, error filter, masked password, default path' {
    param($Work)
    $port = Get-FreePort
    $apacheFwd = (Join-Path $Work 'tools\apache24') -replace '\\', '/'
    $conf = @(
        'ErrorLog "logs/error.log"',
        '# --- 1C: global ---',
        "Listen 127.0.0.1:$port",
        'LoadModule _1cws_module "C:/p/bin/wsap24.dll"',
        "ErrorLog `"$apacheFwd/logs/custom.log`"",
        '# --- End: global ---',
        '# --- 1C Publication: demo ---',
        'Alias "/demo" "x"',
        '# --- End: demo ---', '') -join "`n"
    $c = New-WebCase $Work -ApacheRel 'tools\apache24' -Conf $conf
    $vrd = '<?xml version="1.0" encoding="UTF-8"?>' + "`n" +
        '<point xmlns="http://v8.1c.ru/8.2/virtual-resource-system" base="/demo" ib="File=&quot;C:\b&quot;;Pwd=&quot;s3cr&amp;t&quot;;">' + "`n" +
        '    <standardOdata enable="true"/>' + "`n" +
        '    <ws pointEnableCommon="true" publishExtensionsByDefault="true"/>' + "`n" +
        '    <httpServices publishByDefault="true" publishExtensionsByDefault="true"/>' + "`n" + '</point>' + "`n"
    Write-Utf8 (Join-Path $c.Apache 'publish\demo\default.vrd') $vrd -Bom
    Write-Utf8 (Join-Path $c.Apache 'logs\custom.log') ((@(
        '[Sun Nov 01 10:00:00.000 2026] [mpm_winnt:notice] [pid 1:tid 1] AH00455: started-notice',
        '[Sun Nov 01 10:00:01.000 2026] [core:error] [pid 1:tid 1] boom-error',
        '[Sun Nov 01 10:00:02.000 2026] [mpm_winnt:crit] [pid 1:tid 1] AH02538: own-restart') -join "`n") + "`n")
    Write-Utf8 (Join-Path $c.Apache 'logs\error.log') "[Sun Nov 01 09:00:00.000 2026] [core:error] [pid 1] stale-default-log`n"
    $r = Invoke-WebTool $Info @() $Work
    Assert-Equal 0 $r.ExitCode 'info exit'
    Assert-Contains $r.Out ('Path:   ' + $c.Apache) 'default Apache path is the working directory'
    Assert-Contains $r.Out "127.0.0.1:$port" 'port parsed with the bind address'
    Assert-Contains $r.Out "http://127.0.0.1:$port/demo" 'URL uses the bind address'
    Assert-Contains $r.Out '[WS+ext HTTP+ext OData]' 'services and extension flags'
    Assert-Contains $r.Out 'Pwd=***' 'password masked'
    Assert-NotContains $r.Out 's3cr' 'password not printed'
    Assert-Contains $r.Out 'custom.log' 'effective ErrorLog'
    Assert-Contains $r.Out 'boom-error' 'error line shown'
    Assert-NotContains $r.Out 'started-notice' 'notice filtered'
    Assert-NotContains $r.Out 'own-restart' 'AH02538 filtered'
    Assert-NotContains $r.Out 'stale-default-log' 'overridden ErrorLog not read'
}

Register-Case 'web-stop: stops only the Apache under the working directory' {
    param($Work)
    $c = New-WebCase $Work -ApacheRel 'tools\apache24'
    $saved = $env:FAKE_HTTPD_MS
    try {
        $env:FAKE_HTTPD_MS = '30000'
        $p = Start-Process -FilePath $c.Httpd -PassThru -WindowStyle Hidden
    } finally { $env:FAKE_HTTPD_MS = $saved }
    try {
        Start-Sleep -Milliseconds 300
        $r = Invoke-WebTool $Stop @() $Work
        Assert-Equal 0 $r.ExitCode 'stop exit'
        Start-Sleep -Milliseconds 300
        Assert-True ($p.HasExited) 'the fake Apache was stopped'
    } finally { Stop-FakeHttpd $c }
}

Register-Case 'web-unpublish: names validated, DryRun read-only, Force required, Force removes' {
    param($Work)
    $conf = @(
        '# --- 1C: global ---', 'Listen 18082', 'LoadModule _1cws_module "C:/p/bin/wsap24.dll"', '# --- End: global ---',
        '# --- 1C Publication: demo ---', 'Alias "/demo" "x"', '# --- End: demo ---', '') -join "`n"
    $c = New-WebCase $Work -Conf $conf
    Write-Utf8 (Join-Path $c.Apache 'publish\demo\default.vrd') '<point/>'
    $before = Get-Tree $Work
    foreach ($bad in @('..', 'a\b', '*')) {
        $r = Invoke-WebTool $Unpublish @('-AppName', $bad, '-ApachePath', $c.Apache, '-Force') $Work
        Assert-Equal 1 $r.ExitCode "invalid name $bad"
    }
    $r = Invoke-WebTool $Unpublish @('-All', '-AppName', 'demo', '-ApachePath', $c.Apache, '-Force') $Work
    Assert-Equal 1 $r.ExitCode '-All with -AppName'
    $r = Invoke-WebTool $Unpublish @('-AppName', 'demo', '-ApachePath', $c.Apache, '-DryRun') $Work
    Assert-Equal 0 $r.ExitCode 'dry run'
    $r = Invoke-WebTool $Unpublish @('-AppName', 'demo', '-ApachePath', $c.Apache) $Work
    Assert-Equal 2 $r.ExitCode 'force required'
    Assert-Equal $before (Get-Tree $Work) 'tree untouched by refusals and dry run'
    $r = Invoke-WebTool $Unpublish @('-AppName', 'DEMO', '-ApachePath', $c.Apache, '-Force') $Work
    Assert-Equal 0 $r.ExitCode "unpublish exit`n$($r.Out)"
    Assert-True (-not (Test-Path (Join-Path $c.Apache 'publish\demo'))) 'publication dir removed'
    $text = [System.IO.File]::ReadAllText($c.Conf)
    Assert-NotContains $text '1C Publication: demo' 'publication block removed'
    Assert-NotContains $text '# --- 1C: global ---' 'global block removed with the last publication'
}

# ---------------------------------------------------------------- run

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("1c-rules-web-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $root -Force | Out-Null
Write-Host "Work dir: $root" -ForegroundColor DarkGray
$script:FakeHttpd = Join-Path $root 'fake-httpd.exe'
Add-Type -TypeDefinition $FakeHttpdSource -OutputAssembly $script:FakeHttpd -OutputType ConsoleApplication
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
