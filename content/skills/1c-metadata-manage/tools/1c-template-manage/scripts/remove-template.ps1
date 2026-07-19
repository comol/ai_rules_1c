# template-remove v1.2 — Remove template from 1C object
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills
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
$xmlDoc.Load($rootXmlFull.Path)

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
	Write-Error "Removal requires explicit -Force. Run with -DryRun first to review the plan."
	exit 2
}

# Serialize to a temporary file first. If XML generation fails, the source tree
# remains untouched. Commit the root registration change before deleting files.
$encBom = New-Object System.Text.UTF8Encoding($true)
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Encoding = $encBom
$settings.Indent = $false

$tempRootXml = $rootXmlFull.Path + ".remove-template.tmp"
$stream = New-Object System.IO.FileStream($tempRootXml, [System.IO.FileMode]::Create)
$writer = [System.Xml.XmlWriter]::Create($stream, $settings)
try {
	$xmlDoc.Save($writer)
}
finally {
	$writer.Close()
	$stream.Close()
}
Move-Item -Path $tempRootXml -Destination $rootXmlFull.Path -Force

if (Test-Path $templateDir) {
	Remove-Item -Path $templateDir -Recurse -Force
	Write-Host "[OK] Removed directory: $templateDir"
}
Remove-Item -Path $templateMetaPath -Force
Write-Host "[OK] Removed file: $templateMetaPath"
Write-Host "[OK] Template $TemplateName removed from $rootXmlPath"
