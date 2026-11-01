# v8-xsd-fetch v1.2 — Download 1C platform XSD schemas (dump format) into .v8-xsd
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills
# Local: the schema directory comes from .dev.env V8_XSD_PATH first (same order as skd-validate).
# Local: -Ref is resolved to a commit SHA through the commits API before the tree is listed; raw
#   URLs and source.json carry that commit SHA. Upstream took the `sha` of git/trees/<ref>, which
#   is documented as the tree SHA (raw.githubusercontent.com answers 404 for a tree SHA) and only
#   equals the commit SHA by a quirk of the API. A truncated tree listing is refused.
# Local: the schema directory gets a `.gitignore` of `*` — the schemas are 1C-Soft property and
#   must never be committed.
<#
.SYNOPSIS
    Загрузка XSD-схем формата выгрузки 1С по версиям формата

.DESCRIPTION
    Скачивает schemas/designer/<версия>/*.xsd из репозитория yellow-hammer/namespace-forest
    в каталог схем проекта: -OutPath, иначе V8_XSD_PATH из .dev.env, иначе xsdPath из
    .v8-project.json, иначе .v8-xsd рядом с .dev.env / .v8-project.json (нет их — в текущем
    каталоге).

.EXAMPLE
    .\v8-xsd-fetch.ps1 -Versions "2.20,2.21"

.EXAMPLE
    .\v8-xsd-fetch.ps1 -List
#>

[CmdletBinding(PositionalBinding=$false)]
param(
	# Списком одной строкой: powershell -File не связывает массивы
	[Parameter(Mandatory=$false)]
	[string]$Versions,

	[Parameter(Mandatory=$false)]
	[string]$OutPath,

	[Parameter(Mandatory=$false)]
	[string]$Ref = "main",

	[Parameter(Mandatory=$false)]
	[switch]$Force,

	[Parameter(Mandatory=$false)]
	[switch]$List
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repo = "yellow-hammer/namespace-forest"
$repoUrl = "https://github.com/$repo"

# Текст README — в templates/ навыка, одна копия на оба порта
$readmeTemplate = Join-Path $PSScriptRoot "../templates/README.md"

function Find-V8Project([string]$startDir) {
	$d = $startDir
	for ($i = 0; $i -lt 20 -and $d; $i++) {
		$pj = Join-Path $d ".v8-project.json"
		if (Test-Path $pj) { return $pj }
		$parent = [System.IO.Path]::GetDirectoryName($d)
		if ($parent -eq $d) { break }
		$d = $parent
	}
	return $null
}

function Fail([string]$msg) {
	Write-Host "Error: $msg" -ForegroundColor Red
	exit 1
}

# --- Версии: проверяем до сети ---
$wanted = @()
if ($Versions) {
	foreach ($v in ($Versions -split '[,;\s]+')) {
		if (-not $v) { continue }
		if ($v -notmatch '^\d+\.\d+$') { Fail "неверная версия формата '$v' (ожидается вида 2.20)" }
		if ($wanted -notcontains $v) { $wanted += $v }
	}
}

# --- Каталог схем ---
# Local: порядок — как Get-XsdRootCandidate в skd-validate: V8_XSD_PATH из .dev.env (относительный
# путь — от каталога .dev.env); без ключа — xsdPath из .v8-project.json; иначе .v8-xsd рядом с
# .dev.env, потом рядом с .v8-project.json; нет ни того, ни другого — в текущем каталоге.
$cwd = (Get-Location).ProviderPath
$pj = Find-V8Project $cwd
$target = $null
$envDir = $null
$envXsd = ''
$__devEnvHelper = Join-Path $PSScriptRoot '../../_common/DevEnv.ps1'
if (Test-Path -LiteralPath $__devEnvHelper) {
	. $__devEnvHelper
	$envFile = Find-1CDevEnvFile
	if ($envFile) {
		$envDir = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($envFile))
		$envXsd = Get-1CDevEnvValue 'V8_XSD_PATH'
	}
}
$pjXsd = $null
if ($pj) {
	$pjDir = [System.IO.Path]::GetDirectoryName($pj)
	try { $cfg = Get-Content -LiteralPath $pj -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $cfg = $null }
	if ($cfg -and $cfg.xsdPath) {
		$pjXsd = if ([System.IO.Path]::IsPathRooted($cfg.xsdPath)) { $cfg.xsdPath } else { Join-Path $pjDir $cfg.xsdPath }
	}
}
if ($OutPath) {
	$target = if ([System.IO.Path]::IsPathRooted($OutPath)) { $OutPath } else { Join-Path $cwd $OutPath }
} elseif ($envXsd) {
	$target = if ([System.IO.Path]::IsPathRooted($envXsd)) { $envXsd } else { Join-Path $envDir $envXsd }
} elseif ($pjXsd) {
	$target = $pjXsd
} elseif ($envDir) {
	$target = Join-Path $envDir ".v8-xsd"
} elseif ($pj) {
	$target = Join-Path ([System.IO.Path]::GetDirectoryName($pj)) ".v8-xsd"
} else {
	$target = Join-Path $cwd ".v8-xsd"
}
$target = [System.IO.Path]::GetFullPath($target)
if (Test-Path -LiteralPath $target -PathType Leaf) { Fail "каталог схем '$target' — это файл" }

# --- Состав репозитория ---
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$wc = New-Object System.Net.WebClient
$wc.Headers.Add("User-Agent", "v8-xsd-fetch")
$wc.Encoding = [System.Text.Encoding]::UTF8
# Local: сначала ref → SHA коммита (commits API, media type .sha отдаёт одну строку), потом
# состав дерева этого коммита. raw.githubusercontent.com понимает ветку, тег или коммит, но не
# SHA дерева, а поле sha ответа git/trees по документации — SHA дерева.
# WebClient в .NET Framework после запроса убирает из Headers User-Agent и Accept, а API без
# User-Agent отвечает 403, поэтому заголовки ставятся перед каждым запросом.
function Get-GitHubApi([string]$url, [string]$accept) {
	$wc.Headers["User-Agent"] = "v8-xsd-fetch"
	if ($accept) { $wc.Headers["Accept"] = $accept } else { [void]$wc.Headers.Remove("Accept") }
	return [string]$wc.DownloadString($url)
}
try {
	$commit = (Get-GitHubApi "https://api.github.com/repos/$repo/commits/$([uri]::EscapeDataString($Ref))" "application/vnd.github.sha").Trim()
	if ($commit -notmatch '^[0-9a-f]{40}$') { throw "ответ commits API — не SHA коммита: '$commit'" }
	$tree = Get-GitHubApi "https://api.github.com/repos/$repo/git/trees/${commit}?recursive=1" "application/vnd.github+json" | ConvertFrom-Json
} catch {
	Fail "не удалось получить состав $repo@${Ref}: $($_.Exception.Message)`nСкачайте вручную каталоги schemas/designer/<версия> из $repoUrl в '$target'"
}
if ($tree.truncated) {
	Fail "состав $repo@$Ref ($commit) отдан не полностью (truncated)`nСкачайте вручную каталоги schemas/designer/<версия> из $repoUrl в '$target'"
}

$byVersion = @{}
foreach ($node in $tree.tree) {
	if ($node.type -ne 'blob') { continue }
	$m = [regex]::Match($node.path, '^schemas/designer/(\d+\.\d+)/([^/]+\.xsd)$')
	if (-not $m.Success) { continue }
	$v = $m.Groups[1].Value
	if (-not $byVersion.ContainsKey($v)) { $byVersion[$v] = New-Object System.Collections.ArrayList }
	[void]$byVersion[$v].Add(@{ path = $node.path; name = $m.Groups[2].Value })
}
$available = @($byVersion.Keys | Sort-Object { [version]$_ })
if ($available.Count -eq 0) { Fail "в $repo@$Ref нет каталогов schemas/designer/<версия>" }

if ($List) {
	Write-Host "Версии формата в $repo@${Ref}:"
	foreach ($v in $available) {
		$mark = if (Test-Path -LiteralPath (Join-Path $target $v) -PathType Container) { "  (есть локально)" } else { "" }
		Write-Host "  $v — $($byVersion[$v].Count) схем$mark"
	}
	Write-Host "Каталог схем: $target"
	exit 0
}

if ($wanted.Count -eq 0) { $wanted = $available }
$missing = @($wanted | Where-Object { $available -notcontains $_ })
if ($missing.Count -gt 0) {
	Fail "версии $($missing -join ', ') нет в $repo@$Ref (есть: $($available -join ', '))"
}

# --- Загрузка ---
if (-not (Test-Path -LiteralPath $target)) { New-Item -ItemType Directory -Path $target -Force | Out-Null }
# Local: схемы — собственность 1С-Софт, в Git им не место. `.gitignore` со звёздочкой прячет весь
# каталог (вместе с собой) в любом репозитории, до первого скачанного файла.
$gitignorePath = Join-Path $target ".gitignore"
if (-not (Test-Path -LiteralPath $gitignorePath)) {
	[System.IO.File]::WriteAllText($gitignorePath, "# XSD-схемы платформы 1С (собственность ООО «1С-Софт») в Git не добавляются`n*`n", (New-Object System.Text.UTF8Encoding($false)))
}
$fetched = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# Происхождение — по версиям: уже лежащие файлы без -Force не перекачиваются, поэтому коммит
# версии обновляем, только когда её файлы действительно скачаны в этом запуске
$srcPath = Join-Path $target "source.json"
$srcVers = @{}
if (Test-Path -LiteralPath $srcPath) {
	try {
		# pwsh 7.5+ без -DateKind String сделал бы из fetched DateTime, и неперекачанная версия
		# переписалась бы в формате локали; в 5.1 и pwsh до 7.5 ключа нет.
		$cfj = @{}
		if ((Get-Command ConvertFrom-Json).Parameters.ContainsKey('DateKind')) { $cfj.DateKind = 'String' }
		$old = Get-Content -LiteralPath $srcPath -Raw -Encoding UTF8 | ConvertFrom-Json @cfj
		if ($old.versions -is [PSCustomObject]) {
			foreach ($pr in $old.versions.PSObject.Properties) {
				# pwsh 6 и 7.0–7.4 ключа DateKind не знают — формат наш, возвращаем его без потерь
				$f = $pr.Value.fetched
				if ($f -is [datetime]) { $f = $f.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ', [Globalization.CultureInfo]::InvariantCulture) }
				$srcVers[$pr.Name] = @{ ref = "$($pr.Value.ref)"; commit = "$($pr.Value.commit)"; fetched = "$f" }
			}
		}
	} catch { }
}

$totalNew = 0
foreach ($v in ($wanted | Sort-Object { [version]$_ })) {
	$dir = Join-Path $target $v
	if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
	$got = 0; $kept = 0
	foreach ($f in $byVersion[$v]) {
		$dest = Join-Path $dir $f.name
		if ((Test-Path -LiteralPath $dest) -and -not $Force) { $kept++; continue }
		# Файлы берём по коммиту, а не по ветке: весь набор — из одного состояния репозитория
		$url = "https://raw.githubusercontent.com/$repo/$commit/$($f.path)"
		try {
			$wc.Headers["User-Agent"] = "v8-xsd-fetch"
			$bytes = $wc.DownloadData($url)
		} catch {
			Fail "не удалось скачать $($f.path): $($_.Exception.Message)"
		}
		[System.IO.File]::WriteAllBytes($dest, $bytes)
		$got++
	}
	$totalNew += $got
	if ($got -gt 0) { $srcVers[$v] = @{ ref = $Ref; commit = $commit; fetched = $fetched } }
	$line = "  ${v}: скачано $got"
	if ($kept -gt 0) { $line += ", уже было $kept" }
	Write-Host $line
}

# --- README и source.json ---
$readmePath = Join-Path $target "README.md"
if (-not (Test-Path -LiteralPath $readmePath) -and (Test-Path -LiteralPath $readmeTemplate)) {
	Copy-Item -LiteralPath $readmeTemplate -Destination $readmePath
}
$localVersions = @(Get-ChildItem -LiteralPath $target -Directory |
	Where-Object { $_.Name -match '^\d+\.\d+$' } |
	ForEach-Object { $_.Name } | Sort-Object { [version]$_ })
# Руками, а не ConvertTo-Json: форматирование PS 5.1 не совпало бы с py-портом.
# Версия без записи о происхождении (скопирована вручную) — с пустыми полями.
function Esc-Json([string]$s) { return ($s -replace '\\', '\\' -replace '"', '\"') }
$verLines = @()
foreach ($v in $localVersions) {
	$e = if ($srcVers.ContainsKey($v)) { $srcVers[$v] } else { @{ ref = ''; commit = ''; fetched = '' } }
	$verLines += "    `"$v`": { `"ref`": `"$(Esc-Json $e.ref)`", `"commit`": `"$(Esc-Json $e.commit)`", `"fetched`": `"$(Esc-Json $e.fetched)`" }"
}
$verBlock = if ($verLines.Count -gt 0) { "{`n" + ($verLines -join ",`n") + "`n  }" } else { "{}" }
$srcJson = "{`n  `"repository`": `"$repoUrl`",`n  `"versions`": $verBlock`n}`n"
$enc = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($srcPath, $srcJson, $enc)

Write-Host "Схемы: $target (скачано файлов: $totalNew)"
