#Requires -Version 5.1
<# Offline tests: fake 1C exporter and in-memory Task Scheduler; real file mirroring in TEMP only. #>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$work = Join-Path ([IO.Path]::GetTempPath()) ("files-update-' test-" + [guid]::NewGuid().ToString('N'))
$toolDir = Join-Path $work 'tools/1c-db-ops/scripts'
$scriptPath = Join-Path $toolDir 'install-files-update.ps1'
$global:FilesUpdateTestTasks = @{}
$script:checks = 0

function Assert($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
    $script:checks++
}
function Write-Text([string]$Path, [string]$Text) {
    [void][IO.Directory]::CreateDirectory((Split-Path $Path -Parent))
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($true)))
}
# These mocks never reach the Windows scheduler, including in CI.
function Get-ScheduledTask {
    param($TaskName, $TaskPath, $ErrorAction)
    if ($TaskName) { return $global:FilesUpdateTestTasks[$TaskName] }
    return @($global:FilesUpdateTestTasks.Values)
}
function New-ScheduledTaskAction { param($Execute, $Argument, $WorkingDirectory) [pscustomobject]@{Execute=$Execute; Arguments=$Argument; WorkingDirectory=$WorkingDirectory} }
function New-ScheduledTaskTrigger { param([switch]$Once, $At, $RepetitionInterval) [pscustomobject]@{At=$At; Interval=$RepetitionInterval} }
function New-ScheduledTaskPrincipal { param($UserId, $LogonType, $RunLevel) [pscustomobject]@{UserId=$UserId; LogonType=$LogonType; RunLevel=$RunLevel} }
function New-ScheduledTaskSettingsSet { param($MultipleInstances, [switch]$StartWhenAvailable, $ExecutionTimeLimit, [switch]$AllowStartIfOnBatteries, [switch]$DontStopIfGoingOnBatteries) [pscustomobject]@{MultipleInstances=$MultipleInstances; ExecutionTimeLimit=$ExecutionTimeLimit} }
function Register-ScheduledTask {
    param($TaskName, $TaskPath, $Action, $Trigger, $Principal, $Settings, $Description, [switch]$Force)
    $global:FilesUpdateTestTasks[$TaskName] = [pscustomobject]@{TaskName=$TaskName; Actions=@($Action); Trigger=$Trigger; Principal=$Principal; Settings=$Settings; Description=$Description; State='Ready'}
}
function Invoke-Tool([hashtable]$Extra = @{}, [int]$Expected = 0) {
    $script:output = @(& $scriptPath -ProjectRoot $project -IndexPath $dest @Extra 2>&1 | ForEach-Object { "$_" }) -join "`n"
    Assert ($LASTEXITCODE -eq $Expected) "Unexpected exit $LASTEXITCODE (wanted $Expected): $script:output"
    Assert ($script:output -notmatch 'fixture-password') 'Credential leaked to output'
}

try {
    [void][IO.Directory]::CreateDirectory($toolDir)
    Copy-Item -LiteralPath (Join-Path $repo 'content/skills/1c-metadata-manage/tools/1c-db-ops/scripts/install-files-update.ps1') -Destination $scriptPath
    [void][IO.Directory]::CreateDirectory((Join-Path $work 'tools/_common'))
    Copy-Item -LiteralPath (Join-Path $repo 'content/skills/1c-metadata-manage/tools/_common/DevEnv.ps1') -Destination (Join-Path $work 'tools/_common/DevEnv.ps1')
    Write-Text (Join-Path $toolDir 'db-dump-xml.ps1') @'
param($ConfigDir, $Mode, $Format, $V8Path, $InfoBasePath, $InfoBaseServer, $InfoBaseRef, $UserName, $Password, $Extension)
$PSBoundParameters | Export-Clixml -LiteralPath 'last-call.xml'
if (Test-Path -LiteralPath 'export-fails') { Write-Host $Password; exit 7 }
if (Test-Path -LiteralPath 'export-empty') { Write-Host '--- Log ---'; Write-Host 'ok'; Write-Host '--- End ---'; exit 0 }
[void][IO.Directory]::CreateDirectory($ConfigDir)
[IO.File]::WriteAllText((Join-Path $ConfigDir 'Configuration.xml'), '<MetaDataObject><Configuration/></MetaDataObject>')
[IO.File]::WriteAllText((Join-Path $ConfigDir 'ConfigDumpInfo.xml'), '<ConfigDumpInfo/>')
[IO.File]::WriteAllText((Join-Path $ConfigDir 'fresh.txt'), 'new snapshot')
Write-Host '--- Log ---'
if (Test-Path -LiteralPath 'log-text') { Write-Host (Get-Content -LiteralPath 'log-text' -Raw -Encoding UTF8) } else { Write-Host '0 errors' }
Write-Host '--- End ---'
exit 0
'@
    $project = Join-Path $work 'project with spaces'
    $dest = Join-Path $work 'MCP dump'
    $envFile = Join-Path $project '.dev.env'
    $envText = "PLATFORM_PATH=platform`nINFOBASE_KIND=file`nINFOBASE_PATH=base`nIB_USER=fixture-user`nIB_PASSWORD='fixture-password'`nEXPORT_PATH=src/cf`nEXTENSIONS_PATH=src/cfe`n"
    Write-Text $envFile $envText
    Write-Text (Join-Path $project 'platform/bin/1cv8.exe') 'stub'
    Write-Text (Join-Path $project 'base/1Cv8.1CD') 'stub'

    Invoke-Tool @{CheckOnly=$true}
    Assert (-not (Test-Path -LiteralPath $dest)) 'CheckOnly wrote the destination'
    Assert ($global:FilesUpdateTestTasks.Count -eq 0) 'CheckOnly registered a task'
    Invoke-Tool @{WhatIf=$true}
    Assert (-not (Test-Path -LiteralPath (Join-Path $project '.1c-files-update'))) 'WhatIf wrote scripts'
    Invoke-Tool @{IntervalMinutes=60}
    Assert ($global:FilesUpdateTestTasks.Count -eq 1) 'Installation did not create exactly one task'
    $task = @($global:FilesUpdateTestTasks.Values)[0]
    $launcher = [regex]::Match($task.Actions[0].Arguments, '-File "(.*)"').Groups[1].Value
    $state = Split-Path $launcher -Parent
    Assert (Test-Path -LiteralPath $launcher) 'Launcher missing'
    Assert ($task.Trigger.Interval.TotalMinutes -eq 60) 'Custom interval lost'
    Assert ($task.Principal.LogonType -eq 'Interactive' -and $task.Principal.RunLevel -eq 'Limited') 'Unexpected scheduler identity'
    Assert ($task.Settings.MultipleInstances -eq 'IgnoreNew') 'Concurrent task runs allowed'
    Assert ($task.Actions[0].WorkingDirectory -eq $project) 'Wrong working directory'
    Assert ((Get-Content -LiteralPath $launcher -Raw) -notmatch 'fixture-password') 'Password persisted in launcher'
    Invoke-Tool
    Assert ($global:FilesUpdateTestTasks.Count -eq 1 -and @($global:FilesUpdateTestTasks.Values)[0].Trigger.Interval.TotalMinutes -eq 30) 'Reinstall duplicated task or ignored interval'

    # Run the generated launcher in its actual host: spaces and apostrophes must survive.
    $hostExe = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    & $hostExe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $launcher | Out-Null
    Assert ($LASTEXITCODE -eq 0) 'Generated launcher failed'
    Assert (Test-Path -LiteralPath (Join-Path $dest 'Configuration.xml')) 'Dump not published'
    Assert ((Get-Content -LiteralPath (Join-Path $state 'last-run.log') -Raw) -match 'SUCCESS') 'Success not recorded'
    $call = Import-Clixml (Join-Path $project 'last-call.xml')
    Assert ($call.InfoBasePath -eq (Join-Path $project 'base') -and $call.Mode -eq 'Full') 'File connection/full mode mapping failed'

    Write-Text $envFile ($envText.Replace('INFOBASE_KIND=file', 'INFOBASE_KIND=server').Replace('INFOBASE_PATH=base', 'INFOBASE_PATH=server/changed') + "EXTENSION_NAME=Custom`n")
    Write-Text (Join-Path $dest 'obsolete.txt') 'old'
    Invoke-Tool @{Action='Run'}
    $call = Import-Clixml (Join-Path $project 'last-call.xml')
    Assert ($call.InfoBaseServer -eq 'server' -and $call.InfoBaseRef -eq 'changed' -and $call.Extension -eq 'Custom') 'Runtime did not reread .dev.env'
    Assert (-not (Test-Path -LiteralPath (Join-Path $dest 'obsolete.txt'))) 'Deleted metadata left stale files'
    Assert ($call.Password -eq 'fixture-password') 'Quoted password changed'

    foreach ($failure in @('export-fails', 'export-empty')) {
        Write-Text (Join-Path $project $failure) 'yes'
        Write-Text (Join-Path $dest 'preserve.txt') 'last good snapshot'
        Invoke-Tool @{Action='Run'} 1
        Assert (Test-Path -LiteralPath (Join-Path $dest 'preserve.txt')) "$failure touched live files"
        Assert ((Get-Content -LiteralPath (Join-Path $state 'last-run.log') -Raw) -notmatch 'fixture-password') 'Secret in failure log'
        Remove-Item -LiteralPath (Join-Path $project $failure)
    }
    # Diagnostic text can contradict process exit 0; a success fragment must not hide it.
    foreach ($text in @('0 errors; error: failed', '0 errors; exception')) {
        Write-Text (Join-Path $project 'log-text') $text
        Invoke-Tool @{Action='Run'} 1
        Assert (Test-Path -LiteralPath (Join-Path $dest 'preserve.txt')) 'Bad log published files'
    }
    Remove-Item -LiteralPath (Join-Path $project 'log-text')
    $lock = [IO.File]::Open((Join-Path $state 'run.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    try { Invoke-Tool @{Action='Run'} 1 } finally { $lock.Dispose() }

    # Reject unsafe destinations without creating a task or connecting to 1C.
    $originalDest = $dest
    foreach ($unsafe in @($project, $work, (Join-Path $project 'src/cf'), (Join-Path $project '.1c-files-update/nested'))) {
        $dest = $unsafe
        Invoke-Tool @{CheckOnly=$true} 1
    }
    $dest = Join-Path $work 'existing dump'
    Write-Text (Join-Path $dest 'old.xml') '<old/>'
    Invoke-Tool @{CheckOnly=$true} 1
    Invoke-Tool @{AdoptExisting=$true; CheckOnly=$true}
    Assert (-not (Test-Path -LiteralPath (Join-Path $dest '.1c-files-update.json'))) 'Adoption preflight wrote a marker'
    Write-Text (Join-Path $dest '.git/config') 'project'
    Invoke-Tool @{AdoptExisting=$true; CheckOnly=$true} 1
    $dest = $originalDest
    $global:FilesUpdateTestTasks[$task.TaskName].Description = 'foreign task'
    Invoke-Tool @{} 1
    Write-Text $envFile 'INFOBASE_PATH='
    Invoke-Tool @{CheckOnly=$true} 1

    # The new command/helper must actually be delivered by the normal installer.
    $packageRoot = Join-Path $work 'installed project'
    [void][IO.Directory]::CreateDirectory($packageRoot)
    $packageLog = Join-Path $work 'package.log'
    & $hostExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'install.ps1') init `
        -ProjectRoot $packageRoot -Source $repo -Tools cursor -NonInteractive -McpMode managed *> $packageLog
    Assert ($LASTEXITCODE -eq 0) "Rules installer failed: $(Get-Content -LiteralPath $packageLog -Tail 12 | Out-String)"
    $installedCommand = Join-Path $packageRoot '.cursor/commands/installfilesupdatescript.md'
    $installedTool = Join-Path $packageRoot '.cursor/skills/1c-metadata-manage/tools/1c-db-ops/scripts/install-files-update.ps1'
    Assert (Test-Path -LiteralPath $installedCommand) 'Command missing from installed package'
    Assert (Test-Path -LiteralPath $installedTool) 'Helper missing from installed package'
    Assert ((Get-Content -LiteralPath $installedCommand -Raw) -match 'canonical skills directory') 'Installed command lacks canonical helper resolution'
    Assert ((Get-Content -LiteralPath (Join-Path $packageRoot 'AGENTS.md') -Raw) -match '\.cursor/skills/') 'Canonical skills mapping missing from installed AGENTS.md'
    Assert ((Get-FileHash -LiteralPath $installedTool).Hash -eq (Get-FileHash -LiteralPath $scriptPath).Hash) 'Helper was altered by installer'
    Write-Output "PASS: $script:checks checks; no live 1C or scheduled tasks used."
} finally {
    $resolved = [IO.Path]::GetFullPath($work)
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe test cleanup path' }
    if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
    Remove-Variable -Name FilesUpdateTestTasks -Scope Global
}
