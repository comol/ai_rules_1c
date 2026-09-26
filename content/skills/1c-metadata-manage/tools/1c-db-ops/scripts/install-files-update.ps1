#Requires -Version 5.1
<#
.SYNOPSIS
    Install a Windows task that refreshes a dedicated MCP Designer XML dump.
.DESCRIPTION
    Connection settings are read from ProjectRoot/.dev.env on every run.
    IndexPath must be the verified Windows host path used by MCP PATH_CODE.
    Install creates a launcher and an interactive, current-user scheduled task.
    Run stages a full export through db-dump-xml.ps1 before mirroring the files.
    Existing non-empty directories require explicit -AdoptExisting on Install.
    -CheckOnly validates without writing, connecting to 1C or registering a task.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('Install', 'Run')][string]$Action = 'Install',
    [Parameter(Mandatory)][string]$ProjectRoot,
    [Parameter(Mandatory)][string]$IndexPath,
    [ValidateRange(1, 44640)][int]$IntervalMinutes = 30,
    [switch]$AdoptExisting,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'

function Resolve-UpdatePath([string]$Value, [string]$Base) {
    if (-not [IO.Path]::IsPathRooted($Value)) { $Value = Join-Path $Base $Value }
    return [IO.Path]::GetFullPath($Value).TrimEnd('\', '/')
}

function Test-WithinPath([string]$Path, [string]$Parent) {
    return $Path.Equals($Parent, [StringComparison]::OrdinalIgnoreCase) -or
        $Path.StartsWith($Parent.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
}

function Assert-NoReparsePoint([string]$Path, [switch]$Recurse) {
    $cursor = $Path
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Каталог содержит ссылку или junction: $cursor"
            }
        }
        $cursor = Split-Path $cursor -Parent
    }
    if ($Recurse -and (Test-Path -LiteralPath $Path)) {
        foreach ($entry in Get-ChildItem -LiteralPath $Path -Force) {
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Каталог содержит ссылку или junction: $($entry.FullName)"
            }
            if ($entry.PSIsContainer) { Assert-NoReparsePoint $entry.FullName -Recurse }
        }
    }
}

function Test-ExportLog([string]$Text) {
    # Read only the platform log, not command lines containing arbitrary names.
    $match = [regex]::Match($Text, '(?s)--- Log ---\s*(.*?)\s*--- End ---')
    if (-not $match.Success -or -not $match.Groups[1].Value.Trim()) { return $false }
    $remaining = $match.Groups[1].Value -replace '(?i)\b(ошибок|предупреждений)\s+не обнаружено\b|\b(ошибок|предупреждений)\s*:\s*0\b|\berrors were not found\b|\b0 errors\b', ''
    return $remaining -notmatch '(?i)ошиб[ко]|предупреждени|не найден метод|не может быть применен|невозможно|\b(error|fatal|failed|failure|exception)\b'
}

function Get-UpdatePlan {
    if ($env:OS -ne 'Windows_NT') { throw 'Команда доступна только в Windows.' }
    $root = Resolve-UpdatePath $ProjectRoot (Get-Location).Path
    $dest = Resolve-UpdatePath $IndexPath $root
    if (-not (Test-Path -LiteralPath (Join-Path $root '.dev.env') -PathType Leaf)) {
        throw 'В корне проекта отсутствует .dev.env. Создайте его через установщик правил.'
    }
    if ($dest -eq [IO.Path]::GetPathRoot($dest).TrimEnd('\') -or (Test-WithinPath $root $dest)) {
        throw 'Каталог индексации не может быть корнем диска, проекта или его родителем.'
    }
    Assert-NoReparsePoint $dest -Recurse
    . (Join-Path $PSScriptRoot '../../_common/DevEnv.ps1')
    Push-Location -LiteralPath $root
    try {
        $values = @{}
        foreach ($key in @('PLATFORM_PATH', 'INFOBASE_KIND', 'INFOBASE_PATH', 'IB_USER', 'IB_PASSWORD', 'EXTENSION_NAME', 'EXPORT_PATH', 'EXTENSIONS_PATH')) {
            $values[$key] = Get-1CDevEnvValue $key
            if ($values[$key] -match '["\r\n]') { throw "Недопустимая кавычка или перевод строки в $key." }
        }
    } finally { Pop-Location }
    if (-not $values.PLATFORM_PATH -or -not $values.INFOBASE_PATH) {
        throw 'Заполните PLATFORM_PATH и INFOBASE_PATH в .dev.env.'
    }
    if (-not $values.INFOBASE_KIND) { $values.INFOBASE_KIND = 'file' }
    if ($values.INFOBASE_KIND -notin @('file', 'server')) { throw 'INFOBASE_KIND должен быть file или server.' }
    $v8 = Join-Path (Resolve-UpdatePath $values.PLATFORM_PATH $root) 'bin/1cv8.exe'
    if (-not (Test-Path -LiteralPath $v8 -PathType Leaf)) { throw 'Не найден PLATFORM_PATH\bin\1cv8.exe.' }
    $dump = @{ V8Path = $v8; Mode = 'Full'; Format = 'Hierarchical' }
    if ($values.INFOBASE_KIND -eq 'file') {
        $dump.InfoBasePath = Resolve-UpdatePath $values.INFOBASE_PATH $root
        if (-not (Test-Path -LiteralPath (Join-Path $dump.InfoBasePath '1Cv8.1CD') -PathType Leaf)) {
            throw 'В INFOBASE_PATH не найден файл 1Cv8.1CD.'
        }
        if ((Test-WithinPath $dest $dump.InfoBasePath) -or (Test-WithinPath $dump.InfoBasePath $dest)) {
            throw 'Каталог индексации пересекается с файловой базой.'
        }
    } else {
        $connection = $values.INFOBASE_PATH -split '[/\\]', 2
        if ($connection.Count -ne 2 -or -not $connection[0] -or -not $connection[1]) {
            throw 'Для серверной базы INFOBASE_PATH должен иметь вид сервер/имяБазы.'
        }
        $dump.InfoBaseServer = $connection[0]
        $dump.InfoBaseRef = $connection[1]
    }
    foreach ($pair in @(@('IB_USER', 'UserName'), @('IB_PASSWORD', 'Password'), @('EXTENSION_NAME', 'Extension'))) {
        if ($values[$pair[0]]) { $dump[$pair[1]] = $values[$pair[0]] }
    }
    foreach ($key in @('EXPORT_PATH', 'EXTENSIONS_PATH')) {
        $source = if ($values[$key]) { Resolve-UpdatePath $values[$key] $root } elseif ($key -eq 'EXTENSIONS_PATH') { Join-Path $root 'cfe' } else { $root }
        # A dedicated child of the project is allowed when EXPORT_PATH is the project root.
        if ($source -ne $root -and ((Test-WithinPath $dest $source) -or (Test-WithinPath $source $dest))) {
            throw "Каталог индексации пересекается с $key. Выберите отдельный каталог."
        }
    }
    if (Test-Path -LiteralPath $dest) {
        foreach ($entry in Get-ChildItem -LiteralPath $dest -Recurse -Force) {
            if ($entry.Name -in @('.git', '.dev.env', 'AGENTS.md') -or $entry.Extension -eq '.mdo') {
                throw 'Каталог содержит рабочий проект или исходники EDT. Нужен отдельный Designer XML dump.'
            }
        }
    }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $id = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes(($root + '|' + $dest).ToLowerInvariant())))).Replace('-', '').Substring(0, 16) }
    finally { $sha.Dispose() }
    $state = Join-Path $root ('.1c-files-update/' + $id)
    if ((Test-WithinPath $dest (Join-Path $root '.1c-files-update')) -or (Test-WithinPath $state $dest)) {
        throw 'Каталог индексации пересекается с каталогом скрипта и журналов.'
    }
    Assert-NoReparsePoint $state -Recurse
    $owner = Join-Path $dest '.1c-files-update.json'
    if (Test-Path -LiteralPath $owner) {
        $ownership = Get-Content -LiteralPath $owner -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($ownership.ProjectRoot -ne $root -or $ownership.IndexPath -ne $dest) { throw 'Каталог индексации принадлежит другому заданию.' }
    } elseif ($Action -eq 'Run') {
        throw 'Нет маркера установленного задания. Повторите /installfilesupdatescript.'
    } elseif ((Test-Path -LiteralPath $dest) -and (Get-ChildItem -LiteralPath $dest -Force | Select-Object -First 1) -and -not $AdoptExisting) {
        throw 'Каталог уже содержит файлы. Для передачи отдельного dump-каталога заданию требуется -AdoptExisting.'
    }
    return [pscustomobject]@{ Root=$root; Destination=$dest; State=$state; Owner=$owner; Dump=$dump; TaskName=('1C-MCP-Files-' + $id) }
}

function Install-FilesUpdate($Plan) {
    $launcher = Join-Path $Plan.State 'update-files.ps1'
    $description = '1c-rules MCP files: ' + $Plan.State
    $existing = Get-ScheduledTask -TaskPath '\' -ErrorAction Stop | Where-Object TaskName -eq $Plan.TaskName
    if ($existing -and $existing.Description -ne $description) { throw 'Имя задания занято чужим заданием.' }
    if ($existing -and $existing.State -eq 'Running') { throw 'Задание выполняется. Дождитесь завершения перед переустановкой.' }
    [void][IO.Directory]::CreateDirectory($Plan.State)
    [void][IO.Directory]::CreateDirectory($Plan.Destination)
    $ownerText = @{ ProjectRoot=$Plan.Root; IndexPath=$Plan.Destination } | ConvertTo-Json
    [IO.File]::WriteAllText($Plan.Owner, $ownerText, (New-Object Text.UTF8Encoding($true)))
    # Only paths are persisted. Quote as PowerShell literals, never interpolate env values as code.
    $tool = $PSCommandPath.Replace("'", "''")
    $root = $Plan.Root.Replace("'", "''")
    $dest = $Plan.Destination.Replace("'", "''")
    $body = "# Generated by /installfilesupdatescript. Connection settings stay in .dev.env.`r`n& '$tool' -Action Run -ProjectRoot '$root' -IndexPath '$dest'`r`nexit `$LASTEXITCODE`r`n"
    [IO.File]::WriteAllText($launcher, $body, (New-Object Text.UTF8Encoding($true)))
    $hostExe = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $taskAction = New-ScheduledTaskAction -Execute $hostExe -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $launcher + '"') -WorkingDirectory $Plan.Root
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
    $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $Plan.TaskName -TaskPath '\' -Action $taskAction -Trigger $trigger -Principal $principal -Settings $settings -Description $description -Force | Out-Null
    $installed = Get-ScheduledTask -TaskName $Plan.TaskName -TaskPath '\' -ErrorAction Stop
    if ($installed.Actions.Arguments -notcontains $taskAction.Arguments) { throw 'Не удалось подтвердить действие установленного задания.' }
    Write-Output "Задание: $($Plan.TaskName); интервал: $IntervalMinutes мин.; пользователь должен быть в системе."
    Write-Output "Скрипт: $launcher"
    Write-Output "Каталог MCP: $($Plan.Destination); журнал: $(Join-Path $Plan.State 'last-run.log')"
}

function Invoke-FilesUpdate($Plan) {
    $lock = [IO.File]::Open((Join-Path $Plan.State 'run.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $log = Join-Path $Plan.State 'last-run.log'
    $stage = [IO.Path]::GetFullPath((Join-Path $Plan.State 'staging'))
    try {
        [IO.File]::WriteAllText($log, ((Get-Date).ToString('o') + " START`r`n"), (New-Object Text.UTF8Encoding($true)))
        # Check the resolved deletion boundary before every recursive cleanup.
        if (-not (Test-WithinPath $stage $Plan.State) -or $stage -eq $Plan.State) { throw 'Некорректный временный каталог.' }
        Assert-NoReparsePoint $stage -Recurse
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
        [void][IO.Directory]::CreateDirectory($stage)
        $params = $Plan.Dump
        $params.ConfigDir = $stage
        Push-Location -LiteralPath $Plan.Root
        try {
            $global:LASTEXITCODE = 0
            $output = (& (Join-Path $PSScriptRoot 'db-dump-xml.ps1') @params *>&1 | Out-String)
            $exitCode = $LASTEXITCODE
        } finally { Pop-Location }
        if ($params.Password) { $output = $output.Replace($params.Password, '***') }
        Add-Content -LiteralPath $log -Value $output -Encoding UTF8
        if ($exitCode -ne 0 -or -not (Test-ExportLog $output)) { throw 'Выгрузка 1С завершилась ошибкой или не подтверждена журналом.' }
        foreach ($name in @('Configuration.xml', 'ConfigDumpInfo.xml')) {
            $file = Join-Path $stage $name
            if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "В выгрузке отсутствует $name." }
            $xml = New-Object Xml.XmlDocument
            $xml.XmlResolver = $null
            $xml.Load($file)
            if (-not $xml.DocumentElement) { throw "Пустой XML: $name." }
        }
        # Preserve the directory itself (Docker mounts may refer to it). Mirroring is not atomic.
        Assert-NoReparsePoint $Plan.Destination -Recurse
        Copy-Item -LiteralPath $Plan.Owner -Destination (Join-Path $stage '.1c-files-update.json')
        & (Join-Path $env:SystemRoot 'System32/robocopy.exe') $stage $Plan.Destination /MIR /R:1 /W:1 /NP /NFL /NDL /NJH /NJS 2>&1 | Out-File -LiteralPath $log -Append -Encoding UTF8
        if ($LASTEXITCODE -lt 0 -or $LASTEXITCODE -ge 8) { throw 'Ошибка копирования файлов MCP. Каталог может быть обновлён частично; см. журнал.' }
        Add-Content -LiteralPath $log -Value ((Get-Date).ToString('o') + ' SUCCESS') -Encoding UTF8
    } catch {
        Add-Content -LiteralPath $log -Value ('FAILED: ' + $_.Exception.Message) -Encoding UTF8
        throw
    } finally { $lock.Dispose() }
}

try {
    $plan = Get-UpdatePlan
    if ($CheckOnly) {
        # Do not return Dump: it contains the credentials.
        $plan | Select-Object Root, Destination, State, TaskName
    } elseif ($PSCmdlet.ShouldProcess($plan.Destination, $Action)) {
        if ($Action -eq 'Install') { Install-FilesUpdate $plan } else { Invoke-FilesUpdate $plan }
    }
    exit 0
} catch {
    Write-Error $_.Exception.Message -ErrorAction Continue
    exit 1
}
