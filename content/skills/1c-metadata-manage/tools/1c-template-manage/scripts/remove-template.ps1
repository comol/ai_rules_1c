# template-remove v1.9 — Remove template from 1C object
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills
# Local: preflight parse, atomic root-XML write and -DryRun / -Force safety gate (refusal
#   without -Force exits 2) on top of upstream v1.9; PositionalBinding=$false as in every other writing tool
#   (upstream left this one out).
[CmdletBinding(PositionalBinding=$false)]
param(
	[Parameter(Mandatory)]
	[Alias("ProcessorName")]
	[string]$ObjectName,

	[Parameter(Mandatory)]
	[string]$TemplateName,

	[string]$SrcDir = "src",

	[switch]$DryRun,

	[switch]$Force
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

# --- Проверки ---

$rootXmlPath = Join-Path $SrcDir "$ObjectName.xml"
if (-not (Test-Path $rootXmlPath)) {
	Write-Error "Корневой файл обработки не найден: $rootXmlPath"
	exit 1
}

$processorDir = Join-Path $SrcDir $ObjectName
$templatesDir = Join-Path $processorDir "Templates"
$templateMetaPath = Join-Path $templatesDir "$TemplateName.xml"
$templateDir = Join-Path $templatesDir $TemplateName

if (-not (Test-Path $templateMetaPath)) {
	Write-Error "Метаданные макета не найдены: $templateMetaPath"
	exit 1
}

# --- Preflight: parse and modify XML in memory before deleting anything ---

$rootXmlFull = Resolve-Path $rootXmlPath
$xmlDoc = New-Object System.Xml.XmlDocument
$xmlDoc.PreserveWhitespace = $true
$xmlDoc.Load($rootXmlFull.ProviderPath)

$nsMgr = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
$nsMgr.AddNamespace("md", "http://v8.1c.ru/8.3/MDClasses")

# Удалить <Template>TemplateName</Template> из ChildObjects
$templateNodes = $xmlDoc.SelectNodes("//md:ChildObjects/md:Template", $nsMgr)
$templateNodeFound = $false
foreach ($node in $templateNodes) {
	if ($node.InnerText -eq $TemplateName) {
		$templateNodeFound = $true
		$parent = $node.ParentNode
		# Удалить предшествующий whitespace
		$prev = $node.PreviousSibling
		if ($prev -and $prev.NodeType -eq [System.Xml.XmlNodeType]::Whitespace) {
			$parent.RemoveChild($prev) | Out-Null
		}
		$parent.RemoveChild($node) | Out-Null
		# Опустевший контейнер: остаётся отступ-whitespace, и XmlWriter пишет пару
		# <ChildObjects>\n\t\t</ChildObjects>. Платформа пишет только <ChildObjects/>
		# (1394 самозакрывающихся на acc+erp, пустых пар ни в одной форме — 0).
		if ($parent.SelectNodes("*").Count -eq 0) { $parent.IsEmpty = $true }
		break
	}
}
if (-not $templateNodeFound) {
	Write-Error "Template is not registered in ChildObjects: $TemplateName"
	exit 1
}

# Очистить MainDataCompositionSchema если указывала на этот макет
$mainDCS = $xmlDoc.SelectSingleNode("//md:MainDataCompositionSchema", $nsMgr)
if ($mainDCS -and $mainDCS.InnerText -match "Template\.$([regex]::Escape($TemplateName))$") {
	$mainDCS.InnerText = ""
	Write-Host "[PLAN] Clear MainDataCompositionSchema"
}

# Serialize in memory now, so a serialization failure stops before anything is touched.
$encBom = New-Object System.Text.UTF8Encoding($true)
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Encoding = $encBom
$settings.Indent = $false
$settings.NewLineHandling = [System.Xml.NewLineHandling]::None

# Через MemoryStream, а не прямо в файл: нужен шаг пост-обработки строки.
$memStream = New-Object System.IO.MemoryStream
$writer = [System.Xml.XmlWriter]::Create($memStream, $settings)
try {
	$xmlDoc.Save($writer)
	$writer.Flush()
}
finally {
	$writer.Close()
}

$xmlText = [System.Text.Encoding]::UTF8.GetString($memStream.ToArray())
$memStream.Close()
if ($xmlText.Length -gt 0 -and $xmlText[0] -eq [char]0xFEFF) { $xmlText = $xmlText.Substring(1) }
$xmlText = $xmlText.Replace('encoding="utf-8"', 'encoding="UTF-8"')
# Пустой элемент: XmlWriter отдаёт `<a />`, Конфигуратор пишет `<a/>`. Внутри
# CDATA/комментария/инструкции обработки ` />` может быть содержимым (там `>` не
# экранируется), поэтому они идут первыми ветками альтернации и возвращаются как есть.
$xmlText = [regex]::Replace($xmlText, '(?s)<!\[CDATA\[.*?\]\]>|<!--.*?-->|<\?.*?\?>|(?<=\S) />', { param($m) if ($m.Value -eq ' />') { '/>' } else { $m.Value } })
# Целевой перевод строки: стиль файла-назначения — правка наследует его (#44/#46/#47).
$targetEol = if ([System.IO.File]::ReadAllText($rootXmlFull.ProviderPath) -notmatch "`r`n") { "`n" } else { "`r`n" }
$xmlText = ($xmlText -replace "`r`n", "`n") -replace "`n", $targetEol

# --- Safety gate ---

Write-Host "Planned changes:"
Write-Host "  modify: $rootXmlPath (remove ChildObjects/Template '$TemplateName')"
Write-Host "  delete: $templateMetaPath"
if (Test-Path $templateDir) { Write-Host "  delete: $templateDir (recursive)" }

if ($DryRun) {
	Write-Host "[DRY-RUN] No files changed."
	exit 0
}
if (-not $Force) {
	# stderr + exit 2 (the toolkit's refusal code): Write-Error under Stop would end the run with 1.
	[Console]::Error.WriteLine("[ERROR] Removal requires explicit -Force. Run with -DryRun first to review the plan.")
	exit 2
}

# Write a temporary file first and move it over the root XML: the registration
# change is committed atomically before any template file is deleted.
$tempRootXml = $rootXmlFull.ProviderPath + ".remove-template.tmp"
[System.IO.File]::WriteAllText($tempRootXml, $xmlText, $encBom)
Move-Item -LiteralPath $tempRootXml -Destination $rootXmlFull.ProviderPath -Force

if (Test-Path $templateDir) {
	Remove-Item -Path $templateDir -Recurse -Force
	Write-Host "[OK] Removed directory: $templateDir"
}
Remove-Item -Path $templateMetaPath -Force
Write-Host "[OK] Removed file: $templateMetaPath"
Write-Host "[OK] Template $TemplateName removed from $rootXmlPath"
