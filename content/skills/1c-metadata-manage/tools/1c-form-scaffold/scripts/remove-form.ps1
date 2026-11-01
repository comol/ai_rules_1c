# form-remove v1.11 — Remove form from 1C object
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills, synced at
#         2e75b0f483eb020e9f09562d1a7be1982bc5ac6e.
# Licence: MIT, Copyright (c) 2025-2026 Nick Shirokov. Full notice and permission
#          text: ../../../NOTICE.md (installed as skills/1c-metadata-manage/NOTICE.md).
# Local: hardening on top of upstream, kept in step with remove-form.py —
#        1C-identifier validation and path containment, the -DryRun / -Force gate,
#        and a bounded transaction whose deletions are reversible renames into a
#        quarantine on the same filesystem. From upstream 1.5–1.11 only the
#        reference check of 93d9511a is taken (full-reference match instead of the
#        "Form.<Name>" tail, scan of the rest of the configuration) and ProviderPath
#        (d7a66b63). Upstream's -Force means "also clean foreign references"; here
#        -Force stays the deletion gate and the cleaning is the separate
#        -CleanReferences switch, inside the same transaction.
param(
	[Parameter(Mandatory)]
	[Alias("ProcessorName")]
	[string]$ObjectName,

	[Parameter(Mandatory)]
	[string]$FormName,

	[string]$SrcDir = "src",

	[switch]$DryRun,

	[switch]$Force,

	# Also clear references to the form in OTHER files of the configuration
	# (ChoiceForm / Default*Form slots, ChoiceForm / SettingsStorage inside forms,
	# home-page items). Without it such references stop the removal.
	[switch]$CleanReferences
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

$QuarantineName = ".remove-form-quarantine"

# A 1C metadata identifier: a Latin or Cyrillic letter or underscore, then letters,
# digits and underscores, up to the platform's 128-character limit. An allowlist on
# purpose - it rejects path separators, "..", drive letters, UNC prefixes, trailing
# dots and spaces (which Windows silently strips) and look-alike letters from other
# scripts. Same expression as remove-form.py.
$IdentifierRe = "^[A-Za-z_А-яЁё][0-9A-Za-z_А-яЁё]{0,127}$"

function Deny([string]$Message, [int]$Code) {
	# Write-Error under $ErrorActionPreference = "Stop" raises a terminating error and
	# always exits 1, so a documented exit code would never be reached. Write to
	# stderr directly instead.
	[Console]::Error.WriteLine($Message)
	exit $Code
}

function Assert-Identifier([string]$Value, [string]$What) {
	if ($Value -cnotmatch $IdentifierRe) {
		Deny "Недопустимое имя ${What}: '$Value'. Ожидается идентификатор 1С (латиница или кириллица, цифры и подчёркивание, не начинается с цифры, до 128 символов)." 2
	}
}

function Test-LinkOrReparse([string]$Path) {
	$item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
	if (-not $item) { return $false }
	return (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
}

function Resolve-Full([string]$Path) {
	# Join-Path would produce "C:\cwd\C:bs" for an already-rooted path, which
	# GetFullPath rejects outright.
	if ([System.IO.Path]::IsPathRooted($Path)) { return [System.IO.Path]::GetFullPath($Path) }
	return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).ProviderPath $Path))
}

function Assert-Inside([string]$Path, [string]$Parent, [string]$What) {
	# Parent-relative only. On its own this is not containment: when the parent is
	# itself a link, both sides sit inside the same foreign directory and the check
	# passes. Assert-Chain below anchors everything at the one directory the caller
	# actually vouched for.
	$realParent = (Resolve-Full $Parent).TrimEnd('\', '/')
	$real = Resolve-Full $Path
	if ((Split-Path $real -Parent) -ne $realParent) {
		Deny "Путь $What выходит за пределы каталога ${realParent}: $real. Операция отклонена." 2
	}
	if ((Test-Path -LiteralPath $Path) -and (Test-LinkOrReparse $Path)) {
		Deny "Путь $What является символической ссылкой / точкой повторной обработки: $Path. Удаление отклонено — проверьте выгрузку вручную." 2
	}
}

function Assert-Chain([string]$Root, [string]$Path, [string]$What) {
	# Every component between the trusted -SrcDir and $Path must be a real directory
	# entry. A junction / symlink anywhere on the way - the object directory as much
	# as Forms\ or the form itself - redirects the whole subtree out of the tree, and
	# Resolve-Full is lexical so it cannot see that on its own. Same walk as
	# require_chain() in remove-form.py.
	$rootFull = (Resolve-Full $Root).TrimEnd('\', '/')
	$current  = Resolve-Full $Path
	$chain    = New-Object System.Collections.ArrayList
	while ($current.TrimEnd('\', '/') -ne $rootFull) {
		[void]$chain.Add($current)
		$parent = Split-Path $current -Parent
		if (-not $parent -or $parent -eq $current) {
			Deny "Путь $What выходит за пределы каталога ${rootFull}: $(Resolve-Full $Path). Операция отклонена." 2
		}
		$current = $parent
	}
	foreach ($component in $chain) {
		if ((Test-Path -LiteralPath $component) -and (Test-LinkOrReparse $component)) {
			Deny "Путь $What проходит через символическую ссылку / точку повторной обработки: $component. Удаление отклонено — проверьте выгрузку вручную." 2
		}
	}
}

# Remove an element together with the whitespace in front of it; an emptied container
# becomes self-closing (<ChildObjects/>, as the Configurator writes it). Upstream
# Remove-NodeWithIndent; mirrored by drop_element_keeping_indent in remove-form.py.
function Remove-NodeWithIndent([System.Xml.XmlNode]$Node) {
	$parent = $Node.ParentNode
	if (-not $parent) { return }
	$prev = $Node.PreviousSibling
	if ($prev -and $prev.NodeType -eq [System.Xml.XmlNodeType]::Whitespace) {
		$parent.RemoveChild($prev) | Out-Null
	}
	$parent.RemoveChild($Node) | Out-Null
	if ($parent.SelectNodes("*").Count -eq 0) { $parent.IsEmpty = $true }
}

# Clear every reference to the form in a document, matched on the FULL reference
# "<Kind>.<Object>.Form.<Name>" (upstream 93d9511a). The old tail match "Form\.<Name>$"
# also blanked DocumentJournal.J.Form.<Name> and CommonForm.<Name> slots. The canonical
# "not set" depends on the file: an empty slot in an object / Configuration.xml, an
# absent property inside Ext/Form.xml, and a home-page Item is cut out whole.
# Returns the touched slots, for the plan.
function Clear-FormRefs([System.Xml.XmlDocument]$Doc, [string]$Ref) {
	$isFormFile = $Doc.DocumentElement -and $Doc.DocumentElement.LocalName -eq "Form"
	$touched = @()
	foreach ($node in @($Doc.SelectNodes("//*"))) {
		if ($node.NodeType -ne [System.Xml.XmlNodeType]::Element) { continue }
		if ($node.SelectNodes("*").Count -gt 0) { continue }   # leaves only
		# Case-insensitive like the platform (-ne; .lower() in remove-form.py).
		if ($node.InnerText.Trim() -ne $Ref) { continue }
		$ln = $node.LocalName
		$parent = $node.ParentNode
		if ($ln -eq "Form" -and $parent -and $parent.LocalName -eq "Item") {
			$touched += "remove Item/Form"
			Remove-NodeWithIndent $parent
		} elseif ($isFormFile) {
			$touched += "remove $ln"
			Remove-NodeWithIndent $node
		} else {
			$touched += "clear $ln"
			$node.IsEmpty = $true
		}
	}
	return $touched
}

# The bytes that replace $Path: compact empty tags and the file's own EOL, BOM always.
function Get-RenderedXml([System.Xml.XmlDocument]$Doc, [string]$Path) {
	$xmlText = $Doc.OuterXml
	$xmlText = [regex]::Replace($xmlText, '(?s)<!\[CDATA\[.*?\]\]>|<!--.*?-->|<\?.*?\?>|(?<=\S) />', { param($m) if ($m.Value -eq ' />') { '/>' } else { $m.Value } })
	$targetEol = if ([System.IO.File]::ReadAllText($Path) -match "`r`n") { "`r`n" } else { "`n" }
	return ($xmlText -replace "`r`n", "`n") -replace "`n", $targetEol
}

# --- Input validation: before a single path is built ---

Assert-Identifier $ObjectName "объекта (-ObjectName)"
Assert-Identifier $FormName "формы (-FormName)"

# --- Проверки ---

$rootXmlPath = Join-Path $SrcDir "$ObjectName.xml"
if (-not (Test-Path $rootXmlPath)) {
	Deny "Корневой файл обработки не найден: $rootXmlPath" 1
}

$processorDir = Join-Path $SrcDir $ObjectName
$formsDir = Join-Path $processorDir "Forms"
$formMetaPath = Join-Path $formsDir "$FormName.xml"
$formDir = Join-Path $formsDir $FormName

Assert-Inside $rootXmlPath $SrcDir "корневого XML"
Assert-Inside $processorDir $SrcDir "каталога объекта"
Assert-Inside $formsDir $processorDir "каталога Forms"
Assert-Inside $formMetaPath $formsDir "метаданных формы"
Assert-Inside $formDir $formsDir "каталога формы"

foreach ($pair in @(
		@($rootXmlPath, "корневого XML"),
		@($processorDir, "каталога объекта"),
		@($formsDir, "каталога Forms"),
		@($formMetaPath, "метаданных формы"),
		@($formDir, "каталога формы"))) {
	Assert-Chain $SrcDir $pair[0] $pair[1]
}

if (-not (Test-Path $formMetaPath)) {
	Deny "Метаданные формы не найдены: $formMetaPath" 1
}

# --- Preflight: parse and modify XML in memory before deleting anything ---

$rootXmlFull = Resolve-Path $rootXmlPath
$xmlDoc = New-Object System.Xml.XmlDocument
$xmlDoc.PreserveWhitespace = $true
$xmlDoc.Load($rootXmlFull.ProviderPath)

$nsMgr = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
$nsMgr.AddNamespace("md", "http://v8.1c.ru/8.3/MDClasses")

# Kind and name of the object: the full form reference is built from them.
$typeNode = $null
foreach ($c in $xmlDoc.DocumentElement.ChildNodes) {
	if ($c.NodeType -eq [System.Xml.XmlNodeType]::Element) { $typeNode = $c; break }
}
if (-not $typeNode) {
	Deny "Не удалось определить вид объекта в $rootXmlPath" 1
}
$mdType = $typeNode.LocalName
$nameNode = $typeNode.SelectSingleNode("md:Properties/md:Name", $nsMgr)
$objMetaName = if ($nameNode -and $nameNode.InnerText.Trim()) { $nameNode.InnerText.Trim() } else { $ObjectName }
$formRef = "$mdType.$objMetaName.Form.$FormName"

# Удалить <Form>FormName</Form> из ChildObjects
$formNodes = $xmlDoc.SelectNodes("//md:ChildObjects/md:Form", $nsMgr)
$formNodeFound = $false
foreach ($node in $formNodes) {
	if ($node.InnerText -eq $FormName) {
		$formNodeFound = $true
		Remove-NodeWithIndent $node
		break
	}
}
if (-not $formNodeFound) {
	Deny "Form is not registered in ChildObjects: $FormName" 1
}

# Clear every slot of the object itself that points to this form: form-add writes the
# purpose-specific Default*/Auxiliary*Form, attributes may carry a ChoiceForm.
$ownTouched = @(Clear-FormRefs $xmlDoc $formRef)

# --- References from the rest of the configuration (upstream 93d9511a) ---
#
# The configuration root is -SrcDir or one of its three parents that holds
# Configuration.xml. Without one (an external data processor, a partial tree) only
# the object's own directory is scanned - its other forms can still point here.
$srcFull = (Resolve-Full $SrcDir).TrimEnd('\', '/')
$scanRoot = $null
$probe = $srcFull
for ($depth = 0; $depth -lt 4 -and $probe; $depth++) {
	if (Test-Path -LiteralPath (Join-Path $probe "Configuration.xml")) { $scanRoot = $probe; break }
	$up = Split-Path $probe -Parent
	if (-not $up -or $up -eq $probe) { break }
	$probe = $up
}
$configFound = [bool]$scanRoot
if (-not $scanRoot) { $scanRoot = (Resolve-Full $processorDir).TrimEnd('\', '/') }

$skipFiles = @((Resolve-Full $rootXmlPath), (Resolve-Full $formMetaPath))
$skipDirs = @((Resolve-Full $formDir), (Join-Path $srcFull $QuarantineName)) | ForEach-Object { $_.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar }
$refPattern = '<([A-Za-z0-9_.]+)>' + [regex]::Escape($formRef) + '</'
$foreign = New-Object System.Collections.ArrayList   # @{ Path; Rel; Tags; Doc; Touched; Payload }
if (Test-Path -LiteralPath $scanRoot -PathType Container) {
	# Ordinal order, as sorted() in remove-form.py, so both runtimes print the same plan.
	$files = [string[]]@([System.IO.Directory]::EnumerateFiles($scanRoot, "*.xml", [System.IO.SearchOption]::AllDirectories))
	[System.Array]::Sort($files, [System.StringComparer]::Ordinal)
	foreach ($fp in $files) {
		if ($skipFiles -contains $fp) { continue }
		$skip = $false
		foreach ($d in $skipDirs) { if ($fp.StartsWith($d, [System.StringComparison]::OrdinalIgnoreCase)) { $skip = $true; break } }
		if ($skip) { continue }
		$content = [System.IO.File]::ReadAllText($fp, [System.Text.Encoding]::UTF8)
		if (-not $content.Contains($formRef)) { continue }
		$tags = @([regex]::Matches($content, $refPattern) | ForEach-Object { $_.Groups[1].Value })
		if ($tags.Count -eq 0) { continue }
		[void]$foreign.Add(@{ Path = $fp; Rel = $fp.Substring($scanRoot.Length + 1); Tags = $tags; Doc = $null; Touched = @(); Payload = $null })
	}
}

if ($CleanReferences) {
	foreach ($ref in $foreign) {
		# Every file this run writes must be reached without a link on the way.
		Assert-Chain $scanRoot $ref.Path "файла со ссылкой ($($ref.Rel))"
		$doc = New-Object System.Xml.XmlDocument
		$doc.PreserveWhitespace = $true
		$doc.Load($ref.Path)
		$ref.Touched = @(Clear-FormRefs $doc $formRef)
		if ($ref.Touched.Count -eq 0) {
			Deny "Ссылку на $formRef в $($ref.Rel) нельзя очистить автоматически (она не в отдельном свойстве). Уберите её вручную и повторите." 1
		}
		$ref.Doc = $doc
	}
}

# --- Safety gate ---

Write-Host "Planned changes:"
Write-Host "  modify: $rootXmlPath (remove ChildObjects/Form '$FormName')"
foreach ($step in $ownTouched) {
	Write-Host "  modify: $rootXmlPath ($step)"
}
Write-Host "  delete: $formMetaPath"
if (Test-Path $formDir) { Write-Host "  delete: $formDir (recursive)" }
if ($foreign.Count -gt 0) {
	Write-Host "References to $formRef from other files: $($foreign.Count)"
	foreach ($ref in $foreign) {
		if ($CleanReferences) {
			foreach ($step in ($ref.Touched | Sort-Object -Unique)) {
				Write-Host "  modify: $(Join-Path $scanRoot $ref.Rel) ($step)"
			}
		} else {
			$tagList = ($ref.Tags | Sort-Object -Unique) -join ', '
			Write-Host "  reference: $(Join-Path $scanRoot $ref.Rel) <$tagList>"
		}
	}
	if (-not $CleanReferences) {
		Write-Host "  These references block the removal: clear them by hand, or add -CleanReferences to clear them in the same transaction."
	}
}
if (-not $configFound) {
	Write-Host "[WARN] Configuration.xml not found within three levels above -SrcDir: only $scanRoot was checked for references."
}

if ($DryRun) {
	Write-Host "[DRY-RUN] No files changed."
	exit 0
}
if (-not $Force) {
	Deny "Removal requires explicit -Force. Run with -DryRun first to review the plan." 2
}
if ($foreign.Count -gt 0 -and -not $CleanReferences) {
	Deny "Форма $formRef используется в других файлах ($($foreign.Count)) — удаление остановлено, ничего не изменено. Уберите ссылки или повторите с -Force -CleanReferences." 2
}

# Render now: a serialization failure must surface before anything is deleted.
$rootPayload = Get-RenderedXml $xmlDoc $rootXmlFull.ProviderPath
foreach ($ref in $foreign) {
	if ($ref.Doc) { $ref.Payload = Get-RenderedXml $ref.Doc $ref.Path }
}

# --- Mutation: one bounded transaction, rolled back as a whole on any failure ---
#
# Deletions are renames into a quarantine directory on the same filesystem, so every
# step is reversible and none can stop half-way. The quarantine is discarded only
# after the whole transaction has committed.

$quarantine = Join-Path (Resolve-Full $SrcDir) $QuarantineName
if (Test-Path -LiteralPath $quarantine) {
	Deny "Найден каталог карантина от прерванного запуска: $quarantine. Проверьте его содержимое и удалите вручную, затем повторите операцию." 2
}

$formDirExisted = Test-Path $formDir
$formDirTarget = Resolve-Full $formDir
$metaTarget = Resolve-Full $formMetaPath
$rootTarget = $rootXmlFull.ProviderPath
$backup = Join-Path $quarantine "root-backup.xml"
$parkedDir = Join-Path $quarantine "form-dir"
$parkedMeta = Join-Path $quarantine "form-meta.xml"

# Discarding the quarantine is deliberately NOT one of the undo steps. As a step it
# was the oldest one and therefore ran last, i.e. after earlier restores had already
# failed: the tree kept the hole and the only surviving copy of the deleted files was
# removed together with the quarantine the error message was pointing at. It is now
# removed only when nothing is outstanding - see the catch block below.
#
# Parked = $true marks a payload that was *moved* into the quarantine: it is
# outstanding for exactly as long as it is still there, which is read off the
# filesystem rather than off a flag. The root backup is a copy, so its own restore
# result decides.
$undo = New-Object System.Collections.ArrayList
New-Item -ItemType Directory -Path $quarantine -Force | Out-Null

try {
	Copy-Item -LiteralPath $rootTarget -Destination $backup -Force
	[void]$undo.Add(@{ What = "restore $rootTarget"; Parked = $false; Restored = $false
		Recovery = [pscustomobject]@{ From = $backup; To = $rootTarget }
		Action = { Copy-Item -LiteralPath $backup -Destination $rootTarget -Force } })

	if ($formDirExisted) {
		[System.IO.Directory]::Move($formDirTarget, $parkedDir)
		[void]$undo.Add(@{ What = "put back $formDirTarget"; Parked = $true; Restored = $false
			Recovery = [pscustomobject]@{ From = $parkedDir; To = $formDirTarget }
			Action = { [System.IO.Directory]::Move($parkedDir, $formDirTarget) } })
	}

	[System.IO.File]::Move($metaTarget, $parkedMeta)
	[void]$undo.Add(@{ What = "put back $metaTarget"; Parked = $true; Restored = $false
		Recovery = [pscustomobject]@{ From = $parkedMeta; To = $metaTarget }
		Action = { [System.IO.File]::Move($parkedMeta, $metaTarget) } })

	# Serialize into the quarantine first, then swap the file in atomically.
	$encBom = New-Object System.Text.UTF8Encoding($true)
	$staged = Join-Path $quarantine "root-new.xml"
	[System.IO.File]::WriteAllText($staged, $rootPayload, $encBom)
	Move-Item -LiteralPath $staged -Destination $rootTarget -Force

	# -CleanReferences: the other files, each backed up first so the rollback can put
	# its original bytes back.
	$refIndex = 0
	foreach ($ref in $foreign) {
		if (-not $ref.Doc) { continue }
		$refIndex++
		$refTarget = $ref.Path
		$refBackup = Join-Path $quarantine "ref-backup-$refIndex.xml"
		Copy-Item -LiteralPath $refTarget -Destination $refBackup -Force
		[void]$undo.Add(@{ What = "restore $refTarget"; Parked = $false; Restored = $false
			Recovery = [pscustomobject]@{ From = $refBackup; To = $refTarget }
			Action = { Copy-Item -LiteralPath $refBackup -Destination $refTarget -Force }.GetNewClosure() })
		$refStaged = Join-Path $quarantine "ref-new-$refIndex.xml"
		[System.IO.File]::WriteAllText($refStaged, $ref.Payload, $encBom)
		Move-Item -LiteralPath $refStaged -Destination $refTarget -Force
	}
}
catch {
	$failure = $_.Exception.Message
	$problems = @()
	for ($i = $undo.Count - 1; $i -ge 0; $i--) {
		try { & $undo[$i].Action; $undo[$i].Restored = $true } catch { $problems += "$($undo[$i].What): $($_.Exception.Message)" }
	}

	$outstanding = New-Object System.Collections.ArrayList
	foreach ($step in $undo) {
		$stillOnlyCopy = if ($step.Parked) { Test-Path -LiteralPath $step.Recovery.From } else { -not $step.Restored }
		if ($stillOnlyCopy) { [void]$outstanding.Add($step.Recovery) }
	}

	# The primary failure first and unmasked - it is what has to be acted on.
	[Console]::Error.WriteLine("[error] Операция прервана: $failure")
	if ($outstanding.Count -gt 0 -or $problems.Count -gt 0) {
		[Console]::Error.WriteLine("[error] Откат (rollback) выполнен не полностью.")
		foreach ($problem in $problems) { [Console]::Error.WriteLine("  - не удалось: $problem") }
		if ($outstanding.Count -gt 0) {
			[Console]::Error.WriteLine("[error] Карантин $quarantine НЕ удалён: в нём единственные копии перечисленного ниже. Восстановите вручную:")
			foreach ($item in $outstanding) { [Console]::Error.WriteLine("  - $($item.From) -> $($item.To)") }
		}
	}
	else {
		$kept = $false
		try { Remove-Item -LiteralPath $quarantine -Recurse -Force } catch { $kept = $true }
		if ($kept) {
			[Console]::Error.WriteLine("[error] Откат (rollback) выполнен, дерево исходников не изменено, но каталог карантина остался — удалите вручную: $quarantine")
		}
		else {
			[Console]::Error.WriteLine("[error] Откат (rollback) выполнен, дерево исходников не изменено.")
		}
	}
	exit 1
}

try {
	Remove-Item -LiteralPath $quarantine -Recurse -Force
}
catch {
	[Console]::Error.WriteLine("[error] Форма удалена, но каталог карантина не удалён ($($_.Exception.Message)). Удалите вручную: $quarantine")
	exit 1
}

if ($formDirExisted) {
	Write-Host "[OK] Removed directory: $formDir"
}
Write-Host "[OK] Removed file: $formMetaPath"
Write-Host "[OK] Form $FormName removed from $rootXmlPath"
foreach ($ref in $foreign) {
	if ($ref.Doc) { Write-Host "[OK] Cleared reference in $($ref.Rel): $(($ref.Touched | Sort-Object -Unique) -join ', ')" }
}
