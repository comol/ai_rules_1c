# repo-ops v1.2 — 1C configuration repository (хранилище конфигурации) operations
# Part of the 1c-repository-manage skill (1c-rules).
# Conventions follow 1c-metadata-manage/tools/1c-db-ops (encoding fallback,
# non-interactive launch, secret masking, exit-0 log-lie detection, /DumpResult).
# v1.1 (2026-11-01) ports the platform-log learnings of upstream db-repo
# (Nikolay-Shirokov/cc-1c-skills, MIT; 478e7489 and later): line-by-line verdict per
# object, root-only capture, owner substitution, received-objects list, connection hints.
# v1.2 (2026-11-12) fixes found on a live repository (8.3.27): a quote in a commit comment
# is doubled, diff without -Version resolves the head first, a forced unlock that leaves
# another user's lock in place is a failure.
<#
.SYNOPSIS
    Операции с хранилищем конфигурации 1С в пакетном режиме Конфигуратора.

.DESCRIPTION
    Единственная санкционированная точка выполнения команд хранилища
    (/ConfigurationRepository*) в наборе 1c-rules. Скрипт инкапсулирует то, что
    теряет ad-hoc командная строка: точный XML списка объектов, кодировки /Out,
    ложный код возврата 0, построчный разбор лога захвата / помещения, маскирование
    паролей, запрет операций над всей конфигурацией и двойное подтверждение -force.

    Параметры подключения по умолчанию читаются из .dev.env (поиск вверх от
    текущего каталога): PLATFORM_PATH, INFOBASE_KIND, INFOBASE_PATH, INFOBASE_ROLE,
    IB_USER, IB_PASSWORD, REPOSITORY_PATH, REPOSITORY_USER, REPOSITORY_PASSWORD,
    REPOSITORY_ALLOW_FORCE, EXPORT_PATH. Явные параметры скрипта имеют приоритет.

.PARAMETER Operation
    status  — отчёт по последней версии хранилища (проверка подключения)
    history — отчёт по истории версий (BeginVersion/EndVersion/GroupBy)
    diff    — сравнение основной конфигурации с версией хранилища
    lock    — захват точного списка объектов
    update  — получение точного списка объектов из хранилища
    commit  — помещение точного списка объектов (Comment обязателен)
    unlock  — отмена захвата точного списка объектов
    dump    — выгрузка версии хранилища в CF/CFE

.PARAMETER Objects
    Точные полные имена метаданных (Справочник.Номенклатура,
    Document.SalesOrder). Обязателен для lock/commit/unlock/update, опционален
    для diff. Пустой список и `*` запрещены: без -Objects платформа применяет
    операцию ко ВСЕЙ конфигурации. Корень «Конфигурация» допустим только сам по
    себе (без -IncludeChildObjects): он нужен, чтобы добавить объект верхнего
    уровня. Реквизит, табличная часть, измерение, ресурс заменяются владельцем.

.EXAMPLE
    .\repo-ops.ps1 -Operation status

.EXAMPLE
    .\repo-ops.ps1 -Operation lock -Objects "Справочник.Номенклатура,Документ.ЗаказКлиента"

.EXAMPLE
    .\repo-ops.ps1 -Operation lock -Objects "Конфигурация"

.EXAMPLE
    .\repo-ops.ps1 -Operation commit -Objects "Справочник.Номенклатура" -Comment "Задача 123: новый реквизит"
#>

[CmdletBinding(PositionalBinding=$false)]
param(
    # Not Mandatory: a mandatory parameter is prompted for interactively, which hangs a
    # batch launch. The empty value is checked below.
    [Parameter(Mandatory=$false)]
    [ValidateSet("status", "history", "diff", "lock", "update", "commit", "unlock", "dump")]
    [string]$Operation,

    [Parameter(Mandatory=$false)]
    [string[]]$Objects = @(),

    [Parameter(Mandatory=$false)]
    [string]$Comment,

    # -1 = latest version: -v is omitted (the platform takes the head); diff reads the head
    # number first, because /CompareCfg requires -SecondVersion for the repository side
    [Parameter(Mandatory=$false)]
    [int]$Version = -1,

    # history bounds; 0 = unset (key omitted). status always reports -NBegin -1.
    [Parameter(Mandatory=$false)]
    [int]$BeginVersion = 0,

    [Parameter(Mandatory=$false)]
    [int]$EndVersion = 0,

    [Parameter(Mandatory=$false)]
    [ValidateSet("", "version", "object", "comment")]
    [string]$GroupBy = "",

    [Parameter(Mandatory=$false)]
    [switch]$IncludeChildObjects,

    [Parameter(Mandatory=$false)]
    [switch]$Revised,

    [Parameter(Mandatory=$false)]
    [switch]$KeepLocked,

    # Force is double-gated: REPOSITORY_ALLOW_FORCE=true in .dev.env AND the
    # per-call confirmation switch. Both must be present.
    [Parameter(Mandatory=$false)]
    [switch]$Force,

    [Parameter(Mandatory=$false)]
    [switch]$ConfirmForce,

    # unlock -Force discards other people's / local uncommitted changes — its
    # confirmation switch is named after the consequence, not the mechanism.
    [Parameter(Mandatory=$false)]
    [switch]$ConfirmDiscardChanges,

    # dump target (.cf / .cfe)
    [Parameter(Mandatory=$false)]
    [string]$OutputFile,

    # report target for status/history/diff; default: %TEMP%\1c-repo-reports\<op>-<stamp>.txt (kept)
    [Parameter(Mandatory=$false)]
    [string]$ReportFile,

    # how much of the report to print inline; the full file always stays on disk
    [Parameter(Mandatory=$false)]
    [int]$MaxReportChars = 16000,

    # 0 = no timeout. On expiry the Designer process is killed and exit is 1.
    [Parameter(Mandatory=$false)]
    [int]$TimeoutSeconds = 0,

    # connection overrides (.dev.env wins otherwise)
    [Parameter(Mandatory=$false)]
    [string]$V8Path,

    [Parameter(Mandatory=$false)]
    [string]$InfoBasePath,

    [Parameter(Mandatory=$false)]
    [string]$InfoBaseServer,

    [Parameter(Mandatory=$false)]
    [string]$InfoBaseRef,

    [Parameter(Mandatory=$false)]
    [string]$UserName,

    [Parameter(Mandatory=$false)]
    [string]$Password,

    [Parameter(Mandatory=$false)]
    [string]$RepositoryPath,

    [Parameter(Mandatory=$false)]
    [string]$RepositoryUser,

    [Parameter(Mandatory=$false)]
    [string]$RepositoryPassword,

    # extension repository (adds -Extension to /ConfigurationRepository* commands)
    [Parameter(Mandatory=$false)]
    [string]$Extension
)

# An unhandled error inside try/finally without catch ended the script with exit 0 —
# a false success without the platform ever running. Any such error is exit 1.
trap { Write-Host "Error: $($_.Exception.Message) ($($_.InvocationInfo.ScriptName):$($_.InvocationInfo.ScriptLineNumber))" -ForegroundColor Red; exit 1 }

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if (-not $Operation) {
    Write-Host "Error: -Operation is required (status, history, diff, lock, update, commit, unlock, dump)" -ForegroundColor Red
    exit 1
}

# --- .dev.env (self-contained copy of the DevEnv contract: nearest file walking
# up, '' when absent, quotes stripped, never throws) ---
function Find-DevEnvFile {
    $dir = (Get-Location).ProviderPath
    for ($i = 0; $i -lt 20 -and $dir; $i++) {
        $candidate = Join-Path $dir '.dev.env'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
        $parent = Split-Path $dir -Parent
        if (-not $parent -or $parent -eq $dir) { break }
        $dir = $parent
    }
    return $null
}

function Get-DevEnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)
    try {
        $file = Find-DevEnvFile
        if (-not $file) { return '' }
        foreach ($line in (Get-Content -LiteralPath $file -Encoding UTF8 -ErrorAction Stop)) {
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            $trim = $line.TrimStart()
            if ($trim.StartsWith('#')) { continue }
            if ($trim -match '^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
                if ($Matches[1] -ne $Name) { continue }
                $val = $Matches[2].Trim()
                if ($val.Length -ge 2 -and
                    (($val.StartsWith('"') -and $val.EndsWith('"')) -or
                     ($val.StartsWith("'") -and $val.EndsWith("'")))) {
                    $val = $val.Substring(1, $val.Length - 2).Trim()
                }
                return $val
            }
        }
    } catch { }
    return ''
}

# --- Shared helpers (same contracts as 1c-db-ops) ---
function Protect-Secrets {
    param([string]$Text, [string[]]$Secrets)
    foreach ($s in $Secrets) { if ($s) { $Text = $Text.Replace($s, '***') } }
    return $Text
}

function ConvertTo-CleanPath {
    param([string]$Value, [string]$ParamName)
    if (-not $Value) { return $Value }
    $v = $Value.Trim()
    if ($v.Length -ge 2 -and $v[0] -eq $v[-1] -and ($v[0] -eq '"' -or $v[0] -eq "'")) {
        $v = $v.Substring(1, $v.Length - 2).Trim()
    }
    if ($v.Length -gt 3 -and ($v[-1] -eq '\' -or $v[-1] -eq '/')) { $v = $v.Substring(0, $v.Length - 1) }
    if ($v.Contains('"')) {
        Write-Host "Error: $ParamName contains a quote character: $Value" -ForegroundColor Red
        exit 1
    }
    return $v
}

function Resolve-InfoBasePath {
    # The platform resolves a relative /F path against its own current directory, which a
    # PowerShell Set-Location does not change. A relative infobase path is anchored at the
    # project root (the .dev.env directory), else at the working directory. "C:x" (relative
    # to drive C's current directory) is refused: its meaning differs per process.
    param([string]$Path)
    if (-not $Path) { return $Path }
    if ($Path -match '^[A-Za-z]:(?![\\/])') {
        Write-Host "Error: infobase path '$Path' is relative to the current directory of drive $($Path.Substring(0, 2)) - use a full path" -ForegroundColor Red
        exit 1
    }
    if ($Path -notmatch '^([A-Za-z]:[\\/]|[\\/]{2})') {
        $base = (Get-Location).ProviderPath
        $envFile = Find-DevEnvFile
        if ($envFile) { $base = [System.IO.Path]::GetDirectoryName($envFile) }
        $joined = if ($Path -match '^[\\/]') { [System.IO.Path]::GetPathRoot($base).TrimEnd('\', '/') + $Path }
            else { [System.IO.Path]::Combine($base, $Path) }
        $Path = [System.IO.Path]::GetFullPath($joined)
    }
    while ($Path.Length -gt 3 -and ($Path[-1] -eq '\' -or $Path[-1] -eq '/')) { $Path = $Path.Substring(0, $Path.Length - 1) }
    return $Path
}

function Get-ExitAnnotation {
    param([int]$Code)
    $win = @{
        -1073741819 = "0xC0000005 (access violation)"
        -1073741515 = "0xC0000135 (missing DLL)"
        -1073740791 = "0xC0000409 (stack overrun)"
    }
    if ($win.ContainsKey($Code)) {
        return " — abnormal termination, exception $($win[$Code]); repository locks may be left half-applied; run -Operation status before retrying"
    }
    return ""
}

function ConvertFrom-PlatformBytes {
    # Strict UTF-8 first, cp866 fallback — guessing outright mangles Cyrillic.
    param([byte[]]$Bytes)
    if (-not $Bytes -or $Bytes.Length -eq 0) { return '' }
    try {
        $strict = New-Object System.Text.UTF8Encoding($false, $true)
        return $strict.GetString($Bytes)
    } catch {
        return [System.Text.Encoding]::GetEncoding(866).GetString($Bytes)
    }
}

function Read-PlatformTextFile {
    # /Out logs and txt reports: BOM decides when present; otherwise strict UTF-8
    # with cp1251 fallback (older platforms write ANSI). Deterministic on both
    # Windows PowerShell 5.1 and pwsh 7.
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -eq 0) { return '' }
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        return [System.Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)
    }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        return [System.Text.Encoding]::Unicode.GetString($bytes, 2, $bytes.Length - 2)
    }
    try {
        $strict = New-Object System.Text.UTF8Encoding($false, $true)
        return $strict.GetString($bytes)
    } catch {
        return [System.Text.Encoding]::GetEncoding(1251).GetString($bytes)
    }
}

function Invoke-PlatformProcess {
    # Non-interactive launch: closed stdin makes an auth prompt fast-fail instead
    # of hanging; both pipes are drained async (sequential reads deadlock).
    # The caller pre-quotes tokens the 1C way (File="C:\a b", /N"user").
    param([string]$Exe, [string[]]$ProcArgs, [int]$TimeoutSec)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Exe
    $psi.Arguments = $ProcArgs -join ' '
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $p = [System.Diagnostics.Process]::Start($psi)
    $p.StandardInput.Close()
    $outMs = New-Object System.IO.MemoryStream
    $errMs = New-Object System.IO.MemoryStream
    $outTask = $p.StandardOutput.BaseStream.CopyToAsync($outMs)
    $errTask = $p.StandardError.BaseStream.CopyToAsync($errMs)
    $timedOut = $false
    if ($TimeoutSec -gt 0) {
        if (-not $p.WaitForExit($TimeoutSec * 1000)) {
            $timedOut = $true
            try { $p.Kill() } catch { }
            $p.WaitForExit()
        }
    } else {
        $p.WaitForExit()
    }
    # Bounded drain: a grandchild that inherited the pipes (crashpad_handler on 8.5) keeps
    # them open after the Designer exits, and reading to EOF would wait forever. The
    # verdict comes from /Out and /DumpResult; stdout is diagnostics only.
    [void][System.Threading.Tasks.Task]::WaitAll(@($outTask, $errTask), 10000)
    $out = ConvertFrom-PlatformBytes $outMs.ToArray()
    $err = ConvertFrom-PlatformBytes $errMs.ToArray()
    if ($err) { $out += $err }
    return [pscustomobject]@{ Output = $out; ExitCode = $p.ExitCode; TimedOut = $timedOut }
}

function Write-PlatformOutput {
    param([string]$Text)
    if (-not $Text) { return }
    $t = $Text.TrimEnd()
    if (-not $t) { return }
    $limit = 65536
    if ($t.Length -gt $limit) {
        $t = "[... обрезано, показаны последние $limit символов ...]`r`n" + $t.Substring($t.Length - $limit)
    }
    Write-Host "--- Вывод платформы ---"
    Write-Host $t
    Write-Host "--- End ---"
}

# --- Object names ---
# The configuration root: alone it is one object (needed to add or remove a top-level
# object); with child objects it is the WHOLE configuration.
$script:ConfigRootAliases = @('Конфигурация', 'Configuration')

# Parts that are NOT repository objects: they live inside the owner's XML, with no file or
# UUID of their own. Asked for one, the platform answers «Загруженный список объектов пуст»
# without a name or a reason. Forms, templates and commands ARE separate objects.
$script:InlineChildKinds = @(
    'Реквизит', 'Attribute',
    'СтандартныйРеквизит', 'StandardAttribute',
    'РеквизитАдресации', 'AddressingAttribute',
    'ТабличнаяЧасть', 'TabularSection',
    'Измерение', 'Dimension',
    'Ресурс', 'Resource',
    'Графа', 'Column',
    'ЗначениеПеречисления', 'EnumValue',
    'ПризнакУчета', 'ПризнакУчёта', 'AccountingFlag',
    'ПризнакУчетаСубконто', 'ПризнакУчётаСубконто', 'ExtDimensionAccountingFlag'
)

function Test-ConfigRoot {
    param([string]$Name)
    foreach ($a in $script:ConfigRootAliases) { if ($Name -ieq $a) { return $true } }
    return $false
}

function Get-ObjectKey {
    # Matches a requested name with the name the platform prints. The platform ACCEPTS
    # Catalog.Номенклатура but always ANSWERS Справочник.Номенклатура, so only the own
    # names (odd path segments) are compared; they are the same in both spellings.
    param([string]$Name)
    $segs = $Name -split '\.'
    $own = @()
    for ($i = 1; $i -lt $segs.Count; $i += 2) { $own += $segs[$i] }
    if ($own.Count -eq 0) { $own = @($segs[0]) }
    return ($own -join '.').ToLowerInvariant()
}

# --- Platform log, line by line ---
# The exit code does not tell what happened: a lock is not atomic (exit 1 with part of the
# objects captured), and "already locked by you" prints nothing at all. Texts as the
# platform writes them (upstream db-repo, verified on 8.3.24 / 8.3.27).
function Read-RepoLog {
    param([string]$LogText)
    $r = @{
        Locked = @(); LockedByOther = @(); Received = @(); Committed = @()
        Unchanged = @(); Unlocked = @(); NotLocked = @(); Modified = @(); Missing = @()
        EmptyList = $false; HasOperationBlock = $false
    }
    if (-not $LogText) { return $r }
    $inMissing = $false
    foreach ($rawLine in ($LogText -split "`r?`n")) {
        $line = $rawLine.Trim().TrimStart([char]0xFEFF)
        if (-not $line) { $inMissing = $false; continue }
        if ($line -match '^-+\s*Начало операции с хранилищем') { $r.HasOperationBlock = $true; $inMissing = $false; continue }
        if ($line -match '^-+\s*Операция с хранилищем') { $inMissing = $false; continue }
        if ($line -match '^Объекты, отсутствующие в обеих конфигурациях') { $inMissing = $true; continue }
        if ($inMissing) { $r.Missing += $line; continue }
        if ($line -match 'Загруженный список объектов пуст') { $r.EmptyList = $true }
        elseif ($line -match '^Объект захвачен для редактирования другим пользователем:\s*(.+?)\s*\((.+?)\)\s*$') {
            $r.LockedByOther += [pscustomobject]@{ Name = $Matches[1]; Holder = $Matches[2] }
        }
        elseif ($line -match '^Объект захвачен для редактирования:\s*(.+)$')       { $r.Locked += $Matches[1].Trim() }
        elseif ($line -match '^Объект получен из хранилища:\s*(.+)$')              { $r.Received += $Matches[1].Trim() }
        elseif ($line -match '^Объект помещен в хранилище:\s*(.+)$')               { $r.Committed += $Matches[1].Trim() }
        elseif ($line -match '^Объект не был изменен:\s*(.+)$')                    { $r.Unchanged += $Matches[1].Trim() }
        elseif ($line -match '^Захват объекта отменен:\s*(.+)$')                   { $r.Unlocked += $Matches[1].Trim() }
        elseif ($line -match '^Объект не захвачен для редактирования:\s*(.+)$')    { $r.NotLocked += $Matches[1].Trim() }
        elseif ($line -match "^Объект '(.+?)' был изменен")                        { $r.Modified += $Matches[1] }
    }
    return $r
}

# Long lists: the head inline, the whole list in a file the agent can read.
$script:ListLimit = 20
$script:ReportRoot = Join-Path ([System.IO.Path]::GetTempPath()) "1c-repo-reports"

function Save-NameList {
    param([string[]]$Names, [string]$Key)
    if (-not (Test-Path $script:ReportRoot)) { New-Item -ItemType Directory -Path $script:ReportRoot -Force | Out-Null }
    $path = Join-Path $script:ReportRoot ("{0}-{1}-{2}.txt" -f $Key, (Get-Date -Format "yyyyMMdd-HHmmss"), (Get-Random))
    [System.IO.File]::WriteAllLines($path, [string[]]$Names, (New-Object System.Text.UTF8Encoding($true)))
    return $path
}

function Write-NameList {
    param([string]$Title, [string[]]$Names, [string]$Color = 'Green', [string]$Key = 'objects')
    if (-not $Names -or $Names.Count -eq 0) { return }
    Write-Host "$Title ($($Names.Count)):" -ForegroundColor $Color
    $limit = [Math]::Min($Names.Count, $script:ListLimit)
    foreach ($n in $Names[0..($limit - 1)]) { Write-Host "  $n" }
    if ($Names.Count -gt $script:ListLimit) {
        Write-Host "  ... and $($Names.Count - $script:ListLimit) more; full list: $(Save-NameList $Names $Key)" -ForegroundColor Yellow
    }
}

function Get-OwnerObjects {
    # Exportable owners of the received names; the root is not exportable by name.
    param([string[]]$Names)
    $owners = New-Object System.Collections.Generic.List[string]
    foreach ($n in $Names) {
        $parts = $n -split '\.'
        if ($parts.Count -lt 2) { continue }
        $owner = "$($parts[0]).$($parts[1])"
        if (-not $owners.Contains($owner)) { $owners.Add($owner) }
    }
    return @($owners)
}

function Write-ReceivedObjects {
    # lock -Revised, update and unlock -Force silently bring newer versions into the
    # infobase. The source files of those objects are now stale: loading them later
    # reverts teammates' changes without any error. Name them, save the list, print the
    # export command — the export itself is not run here (it would overwrite local edits).
    param([string[]]$Received)
    if (-not $Received -or $Received.Count -eq 0) { return }
    Write-Host ""
    Write-NameList "[warning] the infobase configuration changed — objects received from the repository" $Received 'Yellow' 'received-all'
    $owners = Get-OwnerObjects $Received
    if ($owners.Count -gt 0) {
        $listPath = Save-NameList $owners 'received'
        $dumpScript = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\1c-metadata-manage\tools\1c-db-ops\scripts\db-dump-xml.ps1'))
        if (-not (Test-Path -LiteralPath $dumpScript)) { $dumpScript = 'skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-dump-xml.ps1' }
        $connArg = if ($script:ConnServer) { "-InfoBaseServer `"$($script:ConnServer)`" -InfoBaseRef `"$($script:ConnRef)`"" } else { "-InfoBasePath `"$($script:ConnFile)`"" }
        $exportDir = Get-DevEnvValue 'EXPORT_PATH'
        if (-not $exportDir) { $exportDir = '<source dir>' }
        Write-Host "Received objects list (one owner per line): $listPath" -ForegroundColor Yellow
        Write-Host "The source files of these objects are older than the infobase now. Re-export them BEFORE editing" -ForegroundColor Yellow
        Write-Host "(docs/repo-sdlc.md -> Source files follow the infobase); loading the old files reverts teammates' changes silently:" -ForegroundColor Yellow
        Write-Host "  powershell -NoProfile -File `"$dumpScript`" $connArg -ConfigDir `"$exportDir`" -Mode Partial -ObjectsFile `"$listPath`""
        Write-Host "  (or /getconfigfiles selected-object export with this list). Stop if a file to refresh carries local edits." -ForegroundColor Yellow
    }
    if (@($Received | Where-Object { ($_ -split '\.').Count -eq 1 }).Count -gt 0) {
        Write-Host "The configuration root was received — it is not exportable by name; use an incremental export (/loadfrom1cbase changes)." -ForegroundColor Yellow
    }
}

# --- Verdict for the object operations ---
# Measures "is the requested state reached", not "did anything change". Exit 0 = reached
# (including already-there no-ops); exit 1 = not reached or reached only in part — a
# partial lock is a lock conflict (Safety invariant 3), so it is reported per object.
function Get-RepoVerdict {
    param([string]$Op, [hashtable]$Log, [int]$PlatformExit, [string[]]$Requested = @())

    if ($Log.Missing.Count -gt 0) {
        Write-NameList "Error: objects not found in the configuration" $Log.Missing 'Red' 'missing'
        Write-Host "Possible causes: a typo (Справочник.Номенклатура and Catalog.Номенклатура are both accepted);" -ForegroundColor Yellow
        Write-Host "  the infobase is behind the repository and the object appeared later (update first);" -ForegroundColor Yellow
        Write-Host "  not a repository object (attribute / tabular section / dimension / resource) — name its owner." -ForegroundColor Yellow
        return 1
    }
    if ($Log.EmptyList) {
        Write-Host "Error: the platform answered 'Загруженный список объектов пуст' — none of the names is a repository object it knows." -ForegroundColor Red
        Write-Host "  Check spelling and that the infobase is not behind the repository; parts of an object are locked through their owner." -ForegroundColor Yellow
        return 1
    }

    switch ($Op) {
        'lock' {
            $mentioned = @($Log.Locked | ForEach-Object { Get-ObjectKey $_ }) + @($Log.LockedByOther | ForEach-Object { Get-ObjectKey $_.Name })
            $silent = @($Requested | Where-Object { $mentioned -notcontains (Get-ObjectKey $_) })
            Write-NameList "Locked by you now" $Log.Locked 'Green' 'locked'
            if ($Log.LockedByOther.Count -gt 0) {
                Write-NameList "Locked by another user — NOT taken" @($Log.LockedByOther | ForEach-Object { "$($_.Name) — held by $($_.Holder)" }) 'Yellow' 'blocked'
                if ($Log.Locked.Count -gt 0 -or $silent.Count -gt 0) {
                    Write-Host "[partial] the lock is not atomic: the objects listed as locked by you$(if ($silent.Count -gt 0) { ' and the requested ones the platform did not mention (already yours)' }) ARE held by you now." -ForegroundColor Yellow
                    Write-Host "          Keep them for a re-scoped plan or release them with -Operation unlock." -ForegroundColor Yellow
                }
                Write-Host "Lock conflict: report the holder(s) to the user and stop that part of the work; never resolve it with -Force." -ForegroundColor Red
                Write-ReceivedObjects $Log.Received
                return 1
            }
            if ($Log.Locked.Count -eq 0) {
                if ($PlatformExit -eq 0) {
                    # The platform prints no line for an object you already hold.
                    Write-Host "Already locked by you — the platform reports nothing for objects you hold; nothing changed." -ForegroundColor Green
                    Write-ReceivedObjects $Log.Received
                    return 0
                }
                Write-Host "Lock failed (code $PlatformExit)$(Get-ExitAnnotation $PlatformExit)" -ForegroundColor Red
                Write-ReceivedObjects $Log.Received
                return 1
            }
            if ($silent.Count -gt 0 -and $PlatformExit -eq 0) {
                Write-NameList "Already yours (no platform line)" $silent 'Green' 'already-locked'
            }
            if ($PlatformExit -ne 0) {
                Write-Host "Lock reported failure (code $PlatformExit)$(Get-ExitAnnotation $PlatformExit) although the objects above were locked — read the log." -ForegroundColor Red
            }
            Write-ReceivedObjects $Log.Received
            if ($PlatformExit -ne 0) { return 1 }
            return 0
        }
        'unlock' {
            # A plain unlock is atomic: with local changes the platform refuses the whole call.
            if ($PlatformExit -ne 0) {
                if ($Log.Modified.Count -gt 0) {
                    Write-NameList "Unlock refused: these objects have local changes" $Log.Modified 'Red' 'modified'
                    Write-Host "Commit them, or — only with the user's explicit approval — discard them (-Force -ConfirmDiscardChanges)." -ForegroundColor Yellow
                } else {
                    Write-Host "Unlock failed (code $PlatformExit)$(Get-ExitAnnotation $PlatformExit)" -ForegroundColor Red
                }
                return 1
            }
            if ($Log.LockedByOther.Count -gt 0) {
                # Verified on 8.3.27: the platform names the holder, keeps the lock and still
                # reports «Отмена захвата объектов в хранилище успешно завершена» with exit 0 —
                # with -force too, and for a repository administrator too.
                $held = @($Log.LockedByOther | ForEach-Object { "$($_.Name) — held by $($_.Holder)" })
                if ($Force) {
                    Write-NameList "Locked by another user — NOT released (a batch -force does not release another user's lock)" $held 'Red' 'blocked'
                    Write-Host "Report the holder(s) to the user; the holder releases the lock." -ForegroundColor Yellow
                    Write-ReceivedObjects $Log.Received
                    return 1
                }
                Write-NameList "Locked by another user — not yours, nothing to release" $held 'Yellow' 'blocked'
            }
            Write-NameList "Lock released" $Log.Unlocked 'Green' 'unlocked'
            Write-NameList "Not locked by you — nothing to release (no-op)" $Log.NotLocked 'Yellow' 'not-locked'
            if ($Log.Unlocked.Count -eq 0) { Write-Host "Nothing was released — no change." -ForegroundColor Green }
            Write-ReceivedObjects $Log.Received
            return 0
        }
        'commit' {
            Write-NameList "Committed to the repository" $Log.Committed 'Green' 'committed'
            Write-NameList "Unchanged — not committed" $Log.Unchanged 'Yellow' 'unchanged'
            Write-NameList "Not locked by you — lock them first, then commit again" $Log.NotLocked 'Red' 'not-locked'
            if ($Log.LockedByOther.Count -gt 0) {
                Write-NameList "Locked by another user" @($Log.LockedByOther | ForEach-Object { "$($_.Name) — held by $($_.Holder)" }) 'Red' 'blocked'
            }
            if ($PlatformExit -ne 0) {
                # The platform prints a bare «Ошибка помещения изменений объектов в хранилище»
                # with no object and no reason, the same for every cause.
                Write-Host "Commit failed (code $PlatformExit)$(Get-ExitAnnotation $PlatformExit). The platform names no reason; check:" -ForegroundColor Red
                Write-Host "  - the objects are locked by you (-Operation lock);" -ForegroundColor Yellow
                Write-Host "  - no other user holds them;" -ForegroundColor Yellow
                Write-Host "  - the repository user has the right to commit; the repository did not move (update -Revised, re-verify)." -ForegroundColor Yellow
                return 1
            }
            if ($Log.NotLocked.Count -gt 0 -or $Log.LockedByOther.Count -gt 0) { return 1 }
            if ($Log.Committed.Count -eq 0) {
                Write-Host "No new repository version was created: there was nothing to commit." -ForegroundColor Yellow
            }
            return 0
        }
        'update' {
            if ($PlatformExit -ne 0) {
                Write-Host "Update from the repository failed (code $PlatformExit)$(Get-ExitAnnotation $PlatformExit)" -ForegroundColor Red
                return 1
            }
            if (-not $Log.HasOperationBlock) {
                # A bound infobase always logs the operation block, even with nothing to get.
                # Without it the infobase is most likely NOT bound, and UpdateCfg on an unbound
                # infobase replaces the whole configuration and still reports success.
                Write-Host "Error: the platform reported success but printed no repository operation block." -ForegroundColor Red
                Write-Host "       The infobase is probably NOT bound to the repository — check its state before any further call." -ForegroundColor Red
                return 1
            }
            Write-NameList "Received from the repository" $Log.Received 'Green' 'received-list'
            if ($Log.Received.Count -eq 0) {
                Write-Host "Nothing to receive — the objects are already current." -ForegroundColor Green
                return 0
            }
            Write-ReceivedObjects $Log.Received
            return 0
        }
    }
    return $PlatformExit
}

# --- Connection failures: name the cause, not just the symptom ---
function Write-ConnectionHint {
    param([string]$LogText, [string]$RepoPath, [string]$RepoUser)
    if (-not $LogText) { return }
    if ($LogText -match 'Неправильное имя или пароль пользователя|Идентификация пользователя не выполнена') {
        Write-Host "[connection] credentials rejected: IB_USER / IB_PASSWORD (infobase) or REPOSITORY_USER / REPOSITORY_PASSWORD (repository) are wrong — re-ask the user once (dev-standards-env.md credential policy)." -ForegroundColor Yellow
    }
    if ($LogText -match 'Соединение с хранилищем конфигурации не установлено') {
        # The same message covers missing credentials and an unreachable repository —
        # tell them apart by what is known: the user name and the address scheme.
        if (-not $RepoUser) {
            Write-Host "[connection] repository credentials missing: REPOSITORY_USER is empty, and the platform answers 'connection not established' for that too. Ask the user for the repository user and password." -ForegroundColor Yellow
        }
        if ($RepoPath -match '^tcp://([^/]+)') {
            $hostPort = $Matches[1]
            if ($hostPort -notmatch ':\d+$') { $hostPort += ':1542 (default port)' }
            Write-Host "[connection] repository server unreachable at $hostPort$(if ($RepoUser) { ' — the credentials are set, so the server is the suspect' }): check that the repository server (crserver) runs, the port, and that its version matches the platform." -ForegroundColor Yellow
        } elseif ($RepoPath -match '^https?://') {
            Write-Host "[connection] repository web publication unreachable at ${RepoPath}: check the web server and the repository publication." -ForegroundColor Yellow
        } elseif ($RepoUser) {
            Write-Host "[connection] repository not reachable at $RepoPath with the given user: check that the directory exists and is accessible (share, permissions), then REPOSITORY_USER / REPOSITORY_PASSWORD." -ForegroundColor Yellow
        }
    }
    if ($LogText -match 'Конфигурация не подключена к хранилищу|не подключена к хранилищу') {
        Write-Host "[connection] the infobase is not bound to the repository. Binding is a user-run act (SKILL.md -> Safety invariant 6)." -ForegroundColor Yellow
    }
}

# --- Resolve connection parameters (explicit > .dev.env > autodetect) ---
$V8Path = ConvertTo-CleanPath $V8Path '-V8Path'
$InfoBasePath = ConvertTo-CleanPath $InfoBasePath '-InfoBasePath'
$RepositoryPath = ConvertTo-CleanPath $RepositoryPath '-RepositoryPath'

if (-not $V8Path) { $V8Path = Get-DevEnvValue 'PLATFORM_PATH' }
if (-not $V8Path) {
    $found = Get-ChildItem @("C:\Program Files\1cv8\*\bin\1cv8.exe", "C:\Program Files (x86)\1cv8\*\bin\1cv8.exe") -ErrorAction SilentlyContinue |
        Sort-Object { try { [version]$_.Directory.Parent.Name } catch { [version]"0.0" } } -Descending |
        Select-Object -First 1
    if ($found) {
        $V8Path = $found.FullName
        Write-Host "Auto-selected platform $($found.Directory.Parent.Name): $V8Path" -ForegroundColor Yellow
    } else {
        Write-Host "Error: 1C executable not found. Set PLATFORM_PATH in .dev.env or pass -V8Path" -ForegroundColor Red
        exit 1
    }
}
if (Test-Path $V8Path -PathType Container) {
    $v8Candidate = Join-Path $V8Path "1cv8.exe"
    if (-not (Test-Path $v8Candidate)) { $v8Candidate = Join-Path $V8Path "bin\1cv8.exe" }
    $V8Path = $v8Candidate
}
if (-not (Test-Path $V8Path)) {
    Write-Host "Error: 1C executable not found at $V8Path" -ForegroundColor Red
    exit 1
}
if ((Split-Path $V8Path -Leaf) -match '^ibcmd') {
    Write-Host "Error: repository operations require the Designer (1cv8.exe); ibcmd has no configuration-repository mode" -ForegroundColor Red
    exit 1
}

$devIbPath = Get-DevEnvValue 'INFOBASE_PATH'
$devIbKind = Get-DevEnvValue 'INFOBASE_KIND'
if (-not $devIbKind) { $devIbKind = 'file' }

$connectionToken = $null
$targetIsDevEnvBase = $false
$script:ConnServer = $null; $script:ConnRef = $null; $script:ConnFile = $null
if ($InfoBaseServer -and $InfoBaseRef) {
    $connectionToken = "/S `"$InfoBaseServer/$InfoBaseRef`""
    $script:ConnServer = $InfoBaseServer; $script:ConnRef = $InfoBaseRef
    $targetIsDevEnvBase = ($devIbKind -eq 'server' -and $devIbPath -and ($devIbPath -replace '\\', '/') -ieq "$InfoBaseServer/$InfoBaseRef")
} elseif ($InfoBasePath) {
    $InfoBasePath = Resolve-InfoBasePath $InfoBasePath
    $connectionToken = "/F `"$InfoBasePath`""
    $script:ConnFile = $InfoBasePath
    if ($devIbKind -ne 'server' -and $devIbPath) {
        $targetIsDevEnvBase = ((Resolve-InfoBasePath (ConvertTo-CleanPath $devIbPath 'INFOBASE_PATH')) -ieq $InfoBasePath)
    }
} else {
    if (-not $devIbPath) {
        Write-Host "Error: infobase connection is not configured. Set INFOBASE_PATH in .dev.env or pass -InfoBasePath / -InfoBaseServer + -InfoBaseRef" -ForegroundColor Red
        exit 1
    }
    $targetIsDevEnvBase = $true
    if ($devIbKind -eq 'server') {
        $connectionToken = "/S `"$devIbPath`""
        $srvParts = $devIbPath -split '[\\/]', 2
        $script:ConnServer = $srvParts[0]; $script:ConnRef = if ($srvParts.Count -gt 1) { $srvParts[1] } else { '' }
    } else {
        $InfoBasePath = Resolve-InfoBasePath (ConvertTo-CleanPath $devIbPath 'INFOBASE_PATH')
        $connectionToken = "/F `"$InfoBasePath`""
        $script:ConnFile = $InfoBasePath
    }
}
if ($InfoBasePath -and -not (Test-Path (Join-Path $InfoBasePath "1Cv8.1CD"))) {
    Write-Host "Error: information base not found at $InfoBasePath (no 1Cv8.1CD)" -ForegroundColor Red
    exit 1
}

if (-not $UserName) { $UserName = Get-DevEnvValue 'IB_USER' }
if (-not $Password) { $Password = Get-DevEnvValue 'IB_PASSWORD' }
if (-not $RepositoryPath) { $RepositoryPath = Get-DevEnvValue 'REPOSITORY_PATH' }
if (-not $RepositoryUser) { $RepositoryUser = Get-DevEnvValue 'REPOSITORY_USER' }
if (-not $RepositoryPassword) { $RepositoryPassword = Get-DevEnvValue 'REPOSITORY_PASSWORD' }

if (-not $RepositoryPath) {
    Write-Host "Error: the configuration is not bound to a repository in this project (.dev.env REPOSITORY_PATH is empty and -RepositoryPath was not passed)." -ForegroundColor Red
    Write-Host "If the project does use a configuration repository, set REPOSITORY_PATH in .dev.env (local path or tcp://server/alias)." -ForegroundColor Red
    exit 1
}

# --- Operation-specific validation ---
$objectOps = @('lock', 'update', 'commit', 'unlock')

# Comma-separated convention: `powershell.exe -File` cannot bind arrays.
$Objects = @($Objects | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$seen = @{}
$objectList = @()
$substitutions = @()
foreach ($name in $Objects) {
    if ($name -eq '*') {
        Write-Host "Error: wildcard '*' is forbidden — repository operations run only on an explicit object list" -ForegroundColor Red
        exit 1
    }
    if ($name.Contains('"')) {
        Write-Host "Error: object name contains a quote character: $name" -ForegroundColor Red
        exit 1
    }
    if (Test-ConfigRoot $name) {
        # The root alone is one object — locking it lets a new top-level object be added.
        # The root WITH its child objects is the whole configuration: refused.
        if ($IncludeChildObjects) {
            Write-Host "Error: '$name' with -IncludeChildObjects means the WHOLE configuration, not just its root — forbidden." -ForegroundColor Red
            Write-Host "       To add or remove a top-level object, lock the root alone (without -IncludeChildObjects)." -ForegroundColor Yellow
            exit 1
        }
        $name = 'Конфигурация'
    } elseif ($name -notmatch '\.') {
        Write-Host "Error: '$name' is not a metadata full name (expected Type.Name, e.g. Справочник.Номенклатура / Catalog.Products, or the root Конфигурация)" -ForegroundColor Red
        exit 1
    } else {
        $segs = $name -split '\.'
        if ($segs.Count -ge 3 -and ($script:InlineChildKinds -contains $segs[2])) {
            # Owner substitution: an attribute / tabular section / dimension / resource is not a
            # repository object; its owner is the smallest unit that can be locked for it.
            $owner = "$($segs[0]).$($segs[1])"
            $substitutions += "$name -> $owner"
            $name = $owner
        }
    }
    if (-not $seen.ContainsKey($name.ToLowerInvariant())) {
        $seen[$name.ToLowerInvariant()] = $true
        $objectList += $name
    }
}
if ($substitutions.Count -gt 0) {
    Write-Host "[note] parts of an object are not repository objects — the owner object is used instead:" -ForegroundColor Yellow
    foreach ($s in $substitutions) { Write-Host "  $s" -ForegroundColor Yellow }
}

if (($objectOps -contains $Operation) -and $objectList.Count -eq 0) {
    Write-Host "Error: -Objects is required for '$Operation'. An empty list is forbidden: the platform without -Objects applies the operation to the WHOLE configuration." -ForegroundColor Red
    exit 1
}
if ($objectList.Count -gt 0 -and -not (($objectOps + @('diff')) -contains $Operation)) {
    Write-Host "Error: -Objects does not apply to '$Operation'" -ForegroundColor Red
    exit 1
}

if ($Operation -eq 'commit') {
    if (-not $Comment -or -not $Comment.Trim()) {
        Write-Host "Error: -Comment is required for commit (task reference + what changed)" -ForegroundColor Red
        exit 1
    }
}

if ($Operation -eq 'dump') {
    if (-not $OutputFile) {
        Write-Host "Error: -OutputFile is required for dump" -ForegroundColor Red
        exit 1
    }
    $OutputFile = [System.IO.Path]::GetFullPath($OutputFile)
    $ext = [System.IO.Path]::GetExtension($OutputFile).ToLowerInvariant()
    if ($ext -ne '.cf' -and $ext -ne '.cfe') {
        Write-Host "Error: -OutputFile must have a .cf or .cfe extension" -ForegroundColor Red
        exit 1
    }
    $outDir = Split-Path $OutputFile -Parent
    if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }
}

if ($Extension -and $Operation -eq 'diff') {
    Write-Host "Error: -Extension is not supported for diff; compare extension configurations via /CompareCfg with ConfigurationExtension types manually (see docs/repo-ops.md)" -ForegroundColor Red
    exit 1
}

# --- INFOBASE_ROLE=prod: only read-only operations through the project infobase ---
# lock / update / commit / unlock change that infobase or publish from it; they belong to
# the user (dev-standards-env.md -> INFOBASE_ROLE). A copy the user names explicitly is
# identified on its own terms.
if (($objectOps -contains $Operation) -and $targetIsDevEnvBase -and ((Get-DevEnvValue 'INFOBASE_ROLE') -ieq 'prod')) {
    Write-Host "Error: .dev.env INFOBASE_ROLE=prod — '$Operation' changes this infobase or publishes from it. Only status / history / diff / dump run here; hand the operation to the user." -ForegroundColor Red
    exit 1
}

# --- Force double opt-in ---
if ($Force) {
    $allowForce = (Get-DevEnvValue 'REPOSITORY_ALLOW_FORCE')
    if ($allowForce -ne 'true') {
        Write-Host "Error: -Force is disabled for this project. Set REPOSITORY_ALLOW_FORCE=true in .dev.env only for an approved maintenance window, with the user's explicit consent." -ForegroundColor Red
        exit 1
    }
    if ($Operation -eq 'unlock') {
        if (-not $ConfirmDiscardChanges) {
            Write-Host "Error: forced unlock can DISCARD uncommitted changes (yours or another developer's). Re-run with -ConfirmDiscardChanges only after the user explicitly approved losing them." -ForegroundColor Red
            exit 1
        }
    } elseif ($Operation -eq 'update' -or $Operation -eq 'commit') {
        if (-not $ConfirmForce) {
            Write-Host "Error: -Force for '$Operation' requires the explicit -ConfirmForce switch in the same call (approved by the user for this specific operation)." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Error: -Force is not applicable to '$Operation'" -ForegroundColor Red
        exit 1
    }
}

# --- Temp workspace ---
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) "repo_ops_$(Get-Random)"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Reports survive the run: the agent reads the file instead of swallowing
# megabytes of history/diff into its context.
$reportOps = @('status', 'history', 'diff')
if (($reportOps -contains $Operation) -and -not $ReportFile) {
    if (-not (Test-Path $script:ReportRoot)) { New-Item -ItemType Directory -Path $script:ReportRoot -Force | Out-Null }
    $ReportFile = Join-Path $script:ReportRoot ("{0}-{1}.txt" -f $Operation, (Get-Date -Format "yyyyMMdd-HHmmss"))
}

function Write-ObjectListXml {
    # Exact object list in the http://v8.1c.ru/8.3/config/objects format. UTF-8
    # with BOM; attribute values XML-escaped. includeChildObjects is explicit on
    # every entry so the file reads unambiguously. The root is its own element.
    param([string[]]$Names, [bool]$WithChildren, [string]$Path)
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine('<?xml version="1.0" encoding="UTF-8"?>')
    [void]$sb.AppendLine('<Objects xmlns="http://v8.1c.ru/8.3/config/objects" version="1.0">')
    $childFlag = 'false'
    if ($WithChildren) { $childFlag = 'true' }
    foreach ($n in $Names) {
        if (Test-ConfigRoot $n) {
            # Validation refused the root with children above; the root entry is root-only.
            [void]$sb.AppendLine('  <Configuration includeChildObjects="false"/>')
            continue
        }
        $esc = $n.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;').Replace('"', '&quot;')
        [void]$sb.AppendLine("  <Object fullName=`"$esc`" includeChildObjects=`"$childFlag`"/>")
    }
    [void]$sb.AppendLine('</Objects>')
    $enc = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($Path, $sb.ToString(), $enc)
}

function Get-RepoHeadVersion {
    # /CompareCfg has no "latest" for a ConfigurationRepository side: without -SecondVersion
    # the platform answers «Не указана версия хранилища» (verified on 8.3.27). The head
    # number comes from a one-version report, the same call as -Operation status.
    # Returns -1 when the number cannot be read.
    param([string[]]$BaseArgs, [string]$WorkDir)
    $headReport = Join-Path $WorkDir "head_report.txt"
    $headLog = Join-Path $WorkDir "head_log.txt"
    $headArgs = $BaseArgs + @(
        "/ConfigurationRepositoryReport `"$headReport`"", "-NBegin -1", "-ReportFormat txt",
        "/Out `"$headLog`"", "/DisableStartupDialogs", "/DisableStartupMessages")
    $run = Invoke-PlatformProcess $V8Path $headArgs $TimeoutSeconds
    $report = Read-PlatformTextFile $headReport
    if (-not $run.TimedOut -and $run.ExitCode -eq 0 -and $report -match '(?m)^Версия:\s*(\d+)') {
        return [int]$Matches[1]
    }
    Write-Host "Error: the repository head version could not be read for diff (code $($run.ExitCode)); pass -Version explicitly or run -Operation status." -ForegroundColor Red
    $headLogText = Read-PlatformTextFile $headLog
    if ($headLogText) {
        Write-Host "--- Log (/Out) ---"
        Write-Host $headLogText.TrimEnd()
        Write-Host "--- End ---"
    }
    return -1
}

try {
    # --- Build the argument line (pre-quoted, 1C style) ---
    $arguments = @("DESIGNER")
    $arguments += $connectionToken
    if ($UserName) { $arguments += "/N`"$UserName`"" }
    if ($Password) { $arguments += "/P`"$Password`"" }
    $arguments += "/ConfigurationRepositoryF `"$RepositoryPath`""
    if ($RepositoryUser) { $arguments += "/ConfigurationRepositoryN`"$RepositoryUser`"" }
    if ($RepositoryPassword) { $arguments += "/ConfigurationRepositoryP`"$RepositoryPassword`"" }

    $objectsXml = $null
    if ($objectList.Count -gt 0) {
        $objectsXml = Join-Path $tempDir "objects.xml"
        Write-ObjectListXml $objectList $IncludeChildObjects.IsPresent $objectsXml
    }

    switch ($Operation) {
        'status' {
            $arguments += "/ConfigurationRepositoryReport `"$ReportFile`""
            $arguments += "-NBegin -1"
            $arguments += "-ReportFormat txt"
        }
        'history' {
            $arguments += "/ConfigurationRepositoryReport `"$ReportFile`""
            if ($BeginVersion -gt 0) { $arguments += "-NBegin $BeginVersion" }
            if ($EndVersion -gt 0) { $arguments += "-NEnd $EndVersion" }
            if ($GroupBy -eq 'object') { $arguments += "-GroupByObject" }
            elseif ($GroupBy -eq 'comment') { $arguments += "-GroupByComment" }
            $arguments += "-ReportFormat txt"
        }
        'diff' {
            if ($Version -lt 0) {
                $Version = Get-RepoHeadVersion $arguments $tempDir
                if ($Version -lt 0) { exit 1 }
                Write-Host "Comparing with the repository head: version $Version"
            }
            $arguments += "/CompareCfg -FirstConfigurationType MainConfiguration -SecondConfigurationType ConfigurationRepository"
            if ($Version -ge 0) { $arguments += "-SecondVersion $Version" }
            if ($objectsXml) { $arguments += "-Objects `"$objectsXml`"" }
            $arguments += "-ReportType Brief -IncludeChangedObjects -IncludeDeletedObjects -IncludeAddedObjects"
            $arguments += "-ReportFormat txt -ReportFile `"$ReportFile`""
        }
        'lock' {
            $arguments += "/ConfigurationRepositoryLock -Objects `"$objectsXml`""
            if ($Revised) { $arguments += "-revised" }
        }
        'update' {
            $arguments += "/ConfigurationRepositoryUpdateCfg"
            if ($Version -ge 0) { $arguments += "-v $Version" }
            $arguments += "-Objects `"$objectsXml`""
            if ($Revised) { $arguments += "-revised" }
            if ($Force) { $arguments += "-force" }
        }
        'commit' {
            $arguments += "/ConfigurationRepositoryCommit -Objects `"$objectsXml`""
            # multi-line comments go as repeated -comment keys; an internal quote is
            # doubled the 1C way (""). A backslash escape (\") cuts the stored comment at
            # the quote and drops the rest of the line (verified on 8.3.27).
            foreach ($line in ($Comment.Trim() -replace "`r`n", "`n") -split "`n") {
                $escLine = $line -replace '"', '""'
                $arguments += "-comment `"$escLine`""
            }
            if ($KeepLocked) { $arguments += "-keepLocked" }
            if ($Force) { $arguments += "-force" }
        }
        'unlock' {
            $arguments += "/ConfigurationRepositoryUnLock -Objects `"$objectsXml`""
            if ($Force) { $arguments += "-force" }
        }
        'dump' {
            $arguments += "/ConfigurationRepositoryDumpCfg `"$OutputFile`""
            if ($Version -ge 0) { $arguments += "-v $Version" }
        }
    }

    if ($Extension -and $Operation -ne 'diff') {
        $arguments += "-Extension `"$Extension`""
    }

    $outFile = Join-Path $tempDir "repo_log.txt"
    $resultFile = Join-Path $tempDir "repo_result.txt"
    $arguments += "/Out `"$outFile`""
    # Batch verdict (content/rules/designer-batch-checks.md): the result number beside /Out.
    $arguments += "/DumpResult `"$resultFile`""
    $arguments += "/DisableStartupDialogs"
    $arguments += "/DisableStartupMessages"

    # --- Execute ---
    $display = Protect-Secrets ($arguments -join ' ') @($Password, $RepositoryPassword)
    Write-Host "Running: 1cv8.exe $display"
    $run = Invoke-PlatformProcess $V8Path $arguments $TimeoutSeconds
    $exitCode = $run.ExitCode

    if ($run.TimedOut) {
        Write-Host "Error: '$Operation' exceeded $TimeoutSeconds s and the Designer was terminated. The infobase or repository may hold a stale connection — run -Operation status before retrying." -ForegroundColor Red
        Write-PlatformOutput $run.Output
        exit 1
    }

    # --- /DumpResult: exit 0 with a non-zero or missing result is a failed run ---
    $resultText = Read-PlatformTextFile $resultFile
    $resultCode = $null
    if ($null -ne $resultText -and $resultText.Trim() -match '^-?\d+') { $resultCode = [int]$Matches[0] }
    if ($exitCode -eq 0) {
        if ($null -eq $resultCode) {
            Write-Host "[error] the platform exited 0 but /DumpResult was not written — the batch verdict is unknown" -ForegroundColor Red
            $exitCode = 1
        } elseif ($resultCode -ne 0) {
            Write-Host "[error] the platform exited 0 but /DumpResult reports $resultCode" -ForegroundColor Red
            $exitCode = $resultCode
        }
    }

    # --- /Out log: the platform reports here in batch mode, and it can write a
    # failure while still exiting 0 — scan and elevate. Per-object lines (lock /
    # unlock / commit / update) are classified by Read-RepoLog below, not here:
    # «Объект не захвачен для редактирования» is an unlock no-op, not a failure. ---
    $logContent = Read-PlatformTextFile $outFile
    $fatalLogPatterns = @(
        'Ошибка работы с хранилищем конфигурации',
        'Ошибка соединения с хранилищем конфигурации',
        'Соединение с хранилищем конфигурации не установлено',
        'Не удалось подключиться к хранилищу',
        'не подключена к хранилищу',
        'Неправильное имя или пароль пользователя',
        'Идентификация пользователя не выполнена',
        'Ошибка формирования отчета',
        'Ошибка сравнения конфигураций',
        'Ошибка обновления конфигурации базы данных',
        'В данной версии не существует указанных объектов',
        'Загруженный список объектов пуст'
    )
    $logFailures = @()
    if ($logContent) {
        foreach ($line in ($logContent -split "`r?`n")) {
            foreach ($pat in $fatalLogPatterns) {
                if ($line -match [regex]::Escape($pat)) { $logFailures += $line.Trim(); break }
            }
        }
    }

    if ($exitCode -eq 0 -and $logFailures.Count -gt 0) {
        Write-Host "[error] the /Out log contains $($logFailures.Count) failure line(s) although the platform exited 0:" -ForegroundColor Red
        foreach ($f in $logFailures) { Write-Host "  $f" -ForegroundColor Red }
        $exitCode = 1
    }

    # --- Per-object verdict (object operations) ---
    if ($objectOps -contains $Operation) {
        # The verdict gets the code after /DumpResult and the log scan, so it is 0 only
        # when all three signals agree; a non-zero platform code is kept for the report.
        $parsed = Read-RepoLog $logContent
        $verdict = Get-RepoVerdict $Operation $parsed $exitCode $objectList
        if ($verdict -ne 0 -and $exitCode -eq 0) { $exitCode = 1 }
    }

    # --- Result ---
    if ($exitCode -eq 0) {
        Write-Host "Repository operation '$Operation' completed successfully" -ForegroundColor Green
        if ($Operation -eq 'dump') {
            if (Test-Path $OutputFile) {
                $size = (Get-Item $OutputFile).Length
                Write-Host "Dump file: $OutputFile ($size bytes)"
            } else {
                Write-Host "[error] the platform exited 0 but $OutputFile was not created" -ForegroundColor Red
                $exitCode = 1
            }
        }
    } else {
        Write-Host "Repository operation '$Operation' failed (code: $exitCode)$(Get-ExitAnnotation $exitCode)" -ForegroundColor Red
        Write-ConnectionHint $logContent $RepositoryPath $RepositoryUser
    }

    if ($logContent) {
        Write-Host "--- Log (/Out) ---"
        $lt = $logContent.TrimEnd()
        if ($lt.Length -gt 65536) { $lt = "[... обрезано ...]`r`n" + $lt.Substring($lt.Length - 65536) }
        Write-Host $lt
        Write-Host "--- End ---"
    }
    Write-PlatformOutput $run.Output

    # --- Report: print a bounded excerpt, keep the full file for targeted reads ---
    if (($reportOps -contains $Operation) -and $exitCode -eq 0) {
        $report = Read-PlatformTextFile $ReportFile
        if ($null -eq $report) {
            Write-Host "[error] the platform exited 0 but the report file was not created: $ReportFile" -ForegroundColor Red
            $exitCode = 1
        } else {
            Write-Host "Report file: $ReportFile ($($report.Length) chars)"
            Write-Host "--- Report ---"
            if ($report.Length -gt $MaxReportChars) {
                Write-Host $report.Substring(0, $MaxReportChars)
                Write-Host "[... обрезано: показаны первые $MaxReportChars из $($report.Length) символов; полный отчёт — в файле выше ...]"
            } else {
                Write-Host $report
            }
            Write-Host "--- End ---"
        }
    }

    exit $exitCode

} finally {
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
