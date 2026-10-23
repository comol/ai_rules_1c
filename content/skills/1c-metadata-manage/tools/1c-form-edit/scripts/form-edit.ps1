# form-edit v1.10 — Edit 1C managed form elements
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills
# Local: DynamicList attributes require settings.mainTable or settings.query
# and emit <Settings xsi:type="DynamicList">. An attribute without a source
# loads into the designer but the form fails to open
# ("не задан ни текст запроса, ни основная таблица").
# Local: Button and Command children are written in the platform order, and a
# command's picture-and-text Representation is TextPicture - the upstream order
# and value were refused with an XDTO exception on load.
# Local (v1.7): elements and attributes are compiled by form-compile (the same DSL
# keys, the same output) and imported with fresh ids and the target's indent - the
# reduced emitters of v1.6 dropped textEdit, maxWidth, chooseType, minValue / maxValue,
# choiceParameters, choiceParameterLinks, choiceList, format, save and the
# AdditionSource of table additions with «unknown key ... ignored». Commands,
# formEvents and elementEvents keep their own emitters.
# Local (v1.7): `before` places the new elements ahead of a named element; `into`
# also takes a command bar, context menu, popup or button group (a table's, an
# element's, the form's own AutoCommandBar). A button in the ChildItems of a Table
# is refused - its columns live there, the buttons go to the table's command bar.
# Local (v1.8): `set` changes properties and events of existing elements and of the form
# (a property is compiled by form-compile and replaces / is inserted by the child order the
# vendor dumps show; null / [] / {} removes it); it runs before the additions and only sees the
# elements the form had before this edit.
# Local (v1.9): `move` puts existing elements (with their subtree and ids) into / after / before
# another place, `remove` takes elements out with their companions; a removal that is still
# referenced (AdditionSource, StandardCommand buttons, ConditionalAppearance, Items.X data paths,
# Elements.X in Module.bsl) is refused unless "force": true. Order: remove, move, set, additions.
# Local (v1.10): `conditionalAppearance` appends the compiled items to the form's own
# ConditionalAppearance (last child of Attributes, created when absent); an attribute added to
# a form that has one now goes before it.
param(
	[Parameter(Mandatory)]
	[Alias('Path')]
	[string]$FormPath,

	[Parameter(Mandatory)]
	[string]$JsonPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Support guard (Ext/ParentConfigurations.bin) ---
# Canon: docs/support-manage.md. Blocks edits of vendor objects "на замке" /
# read-only configs unless allowed. Trigger = bin present; reaction from
# .dev.env SUPPORT_GUARD (deny|warn|off, default deny; .v8-project.json
# editingAllowedCheck stays as the upstream fallback). Fail-closed on an
# unreadable support state (bin exists but cannot be parsed — same reaction);
# other guard errors degrade to allow with a stderr notice.
function Get-RootUuid([string]$xmlPath) {
	if (-not (Test-Path $xmlPath)) { return $null }
	try {
		[xml]$mx = Get-Content -Path $xmlPath -Encoding UTF8
		$el = $mx.DocumentElement.FirstChild
		while ($el -and $el.NodeType -ne 'Element') { $el = $el.NextSibling }
		if ($el) { $u = $el.GetAttribute("uuid"); if ($u) { return $u } }
	} catch {}
	return $null
}
function Test-ExternalObjectRoot([string]$xmlPath) {
	if (-not (Test-Path $xmlPath)) { return $false }
	try {
		[xml]$mx = Get-Content -Path $xmlPath -Encoding UTF8
		$el = $mx.DocumentElement.FirstChild
		while ($el -and $el.NodeType -ne 'Element') { $el = $el.NextSibling }
		if ($el) { return @('ExternalDataProcessor','ExternalReport') -contains $el.LocalName }
	} catch {}
	return $false
}
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
function Get-EditMode([string]$cfgDir) {
	try {
		# 1c-rules: .dev.env SUPPORT_GUARD wins over .v8-project.json editingAllowedCheck.
		$__devEnvHelper = Join-Path $PSScriptRoot '../../_common/DevEnv.ps1'
		if (Test-Path $__devEnvHelper) {
		    . $__devEnvHelper
		    $__devEnvMode = (Get-1CDevEnvValue 'SUPPORT_GUARD').ToLower()
		    if (@('deny', 'warn', 'off') -contains $__devEnvMode) { return $__devEnvMode }
		}
		$pj = Find-V8Project (Get-Location).Path
		if (-not $pj) { $pj = Find-V8Project $cfgDir }
		if (-not $pj) { return 'deny' }
		$proj = Get-Content -Raw $pj | ConvertFrom-Json
		$cfgFull = [System.IO.Path]::GetFullPath($cfgDir).TrimEnd('\', '/')
		if ($proj.databases) {
			foreach ($db in $proj.databases) {
				if ($db.configSrc) {
					$src = [System.IO.Path]::GetFullPath($db.configSrc).TrimEnd('\', '/')
					if ($cfgFull -eq $src -or $cfgFull.StartsWith($src + [System.IO.Path]::DirectorySeparatorChar)) {
						if ($db.editingAllowedCheck) { return $db.editingAllowedCheck }
					}
				}
			}
		}
		if ($proj.editingAllowedCheck) { return $proj.editingAllowedCheck }
		return 'deny'
	} catch { return 'deny' }
}
function Assert-EditAllowed([string]$targetPath, [string]$require) {
	try {
		$rp = $targetPath
		try { $rp = (Resolve-Path $targetPath -ErrorAction Stop).Path } catch {}
		# Autonomous external object (EPF/ERF): never part of a config on support (issue #39).
		if (Test-ExternalObjectRoot $rp) { return }
		$elemUuid = Get-RootUuid $rp
		$cfgDir = $null; $binPath = $null
		$d = if (Test-Path $rp -PathType Container) { $rp } else { [System.IO.Path]::GetDirectoryName($rp) }
		for ($i = 0; $i -lt 12 -and $d; $i++) {
			if (Test-ExternalObjectRoot "$d.xml") { return }
			if (-not $elemUuid) { $elemUuid = Get-RootUuid "$d.xml" }
			if (-not $cfgDir) {
				$cand = Join-Path (Join-Path $d "Ext") "ParentConfigurations.bin"
				if ((Test-Path $cand) -or (Test-Path (Join-Path $d "Configuration.xml"))) { $cfgDir = $d; $binPath = $cand }
			}
			if ($elemUuid -and $cfgDir) { break }
			$parent = [System.IO.Path]::GetDirectoryName($d)
			if ($parent -eq $d) { break }
			$d = $parent
		}
		# New object (no element file): fall back to config root uuid.
		if (-not $elemUuid -and $cfgDir) { $elemUuid = Get-RootUuid (Join-Path $cfgDir "Configuration.xml") }
		if (-not $binPath -or -not (Test-Path $binPath)) { return }
		# Bin present: an unreadable / unparseable support state must not silently
		# degrade to allow — fail closed via the SUPPORT_GUARD reaction instead.
		$G = 0; $K = 0; $text = $null; $parseOk = $false
		try {
			$bytes = [System.IO.File]::ReadAllBytes($binPath)
			if ($bytes.Length -gt 32) {
				$start = 0
				if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { $start = 3 }
				$text = [System.Text.Encoding]::UTF8.GetString($bytes, $start, $bytes.Length - $start)
				$hm = [regex]::Match($text, '^\{6,(\d+),(\d+),')
				if ($hm.Success) {
					$G = [int]$hm.Groups[1].Value
					$K = [int]$hm.Groups[2].Value
					$parseOk = $true
				}
			}
		} catch {}
		if (-not $parseOk) {
			$mode = Get-EditMode $cfgDir
			if ($mode -eq 'off') { return }
			$msg = "[support-guard] Файл состояния поддержки «$binPath» существует, но не читается или не разбирается — состояние объекта неизвестно, он может быть на замке."
			if ($mode -eq 'warn') { [Console]::Error.WriteLine("$msg Продолжаю по SUPPORT_GUARD=warn."); return }
			[Console]::Error.WriteLine("$msg`nРедактирование остановлено (fail-closed). Проверьте целостность выгрузки, либо задайте SUPPORT_GUARD = warn|off в .dev.env (канон — docs/support-manage.md).")
			exit 1
		}
		if ($K -eq 0) { return }
		$best = $null
		if ($elemUuid) {
			$u = [regex]::Escape($elemUuid.ToLower())
			foreach ($m in [regex]::Matches($text, "([0-2]),0,$u")) {
				$f1 = [int]$m.Groups[1].Value
				if ($null -eq $best -or $f1 -lt $best) { $best = $f1 }
			}
		}
		$blocked = $false; $code = ""; $reason = ""
		if ($G -eq 1) { $blocked = $true; $code = "capability-off"; $reason = "возможность изменения конфигурации выключена (вся конфигурация read-only)" }
		elseif ($require -eq 'removed') {
			if ($null -ne $best -and $best -ne 2) { $blocked = $true; $code = "not-removed"; $reason = "объект не снят с поддержки — удаление сломает обновления" }
		}
		else {
			if ($null -ne $best -and $best -eq 0) { $blocked = $true; $code = "locked"; $reason = "объект на замке — редактирование сломает обновления" }
		}
		if (-not $blocked) { return }
		$mode = Get-EditMode $cfgDir
		if ($mode -eq 'off') { return }
		# Use Console.Error (not Write-Error) — under ErrorActionPreference=Stop the
		# latter throws and would be swallowed by this function's own catch.
		if ($mode -eq 'warn') { [Console]::Error.WriteLine("[support-guard] ПРЕДУПРЕЖДЕНИЕ: $reason. Цель: $rp"); return }
		$head = "[support-guard] Редактирование отклонено: это объект типовой конфигурации на поддержке поставщика, прямое редактирование молча сломает будущие обновления."
		$cfe = "Рекомендуемый путь: внести доработку в расширение (навыки cfe-borrow / cfe-patch-method) — состояние поддержки менять не нужно, обновления вендора сохраняются."
		$offNote = "Снять проверку: SUPPORT_GUARD = warn|off в .dev.env (канон — docs/support-manage.md)."
		if ($code -eq "capability-off") {
			$state = "Состояние: у всей конфигурации выключена возможность изменения (режим read-only «из коробки») — поэтому объект «$rp» редактировать нельзя."
			$fix = "Либо снять защиту явно (навык support-edit, два шага):`n  1. support-edit -Path ""$cfgDir"" -Capability on — включить возможность изменения (объекты пока остаются на замке);`n  2. support-edit -Path ""$rp"" -Set editable — открыть этот объект для редактирования.`n  Изменение применяется в базу полной загрузкой выгрузки и обходит механизм обновлений вендора."
		} elseif ($code -eq "not-removed") {
			$state = "Состояние: объект «$rp» на поддержке (не снят с поддержки) — его удаление разорвёт обновления вендора."
			$fix = "Либо сначала снять объект с поддержки, затем удалять:`n  support-edit -Path ""$rp"" -Set off-support — объект уходит из-под обновлений, после этого удаление безопасно."
		} else {
			$state = "Состояние: объект «$rp» на замке (возможность изменения конфигурации включена, но сам объект не редактируется)."
			$fix = "Либо разрешить редактирование этого объекта (навык support-edit, выбрать одно):`n  support-edit -Path ""$rp"" -Set editable — редактировать и дальше получать обновления вендора (возможны конфликты слияния);`n  support-edit -Path ""$rp"" -Set off-support — снять с поддержки: обновления по объекту больше не приходят."
		}
		[Console]::Error.WriteLine("$head`n$state`n$cfe`n$fix`n$offNote")
		exit 1
	} catch {
		[Console]::Error.WriteLine("[support-guard] Проверка состояния поддержки не выполнена ($($_.Exception.Message)) — продолжаю без блокировки.")
		return
	}
}

# === 1. Load Form.xml ===

if (-not (Test-Path $FormPath)) {
	Write-Error "File not found: $FormPath"
	exit 1
}
if (-not (Test-Path $JsonPath)) {
	Write-Error "File not found: $JsonPath"
	exit 1
}

$resolvedFormPath = (Resolve-Path $FormPath).Path
Assert-EditAllowed $resolvedFormPath 'editable'
$xmlDoc = New-Object System.Xml.XmlDocument
$xmlDoc.PreserveWhitespace = $true
try {
	$xmlDoc.Load($resolvedFormPath)
} catch {
	Write-Host "[ERROR] XML parse error: $($_.Exception.Message)"
	exit 1
}

$formNs = "http://v8.1c.ru/8.3/xcf/logform"
$v8Ns = "http://v8.1c.ru/8.1/data/core"
$nsMgr = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
$nsMgr.AddNamespace("f", $formNs)
$nsMgr.AddNamespace("v8", $v8Ns)
$nsMgr.AddNamespace("dcsset", "http://v8.1c.ru/8.1/data-composition-system/settings")

$root = $xmlDoc.DocumentElement

# === 2. Load JSON ===

$def = Get-Content -Raw -Encoding UTF8 $JsonPath | ConvertFrom-Json

# === 3. Form name + header ===

$formName = [System.IO.Path]::GetFileNameWithoutExtension($FormPath)
$parentDir = [System.IO.Path]::GetDirectoryName($resolvedFormPath)
if ($parentDir) {
	$extDir = [System.IO.Path]::GetFileName($parentDir)
	if ($extDir -eq "Ext") {
		$formDir = [System.IO.Path]::GetDirectoryName($parentDir)
		if ($formDir) { $formName = [System.IO.Path]::GetFileName($formDir) }
	}
}

Write-Host "=== form-edit: $formName ==="
Write-Host ""

# === 4. Scan max IDs per pool ===

$script:nextElemId = 0
$script:nextAttrId = 0
$script:nextCmdId = 0

# Scan ALL element IDs via XPath (includes companions like ExtendedTooltip, ContextMenu)
$rootCI = $root.SelectSingleNode("f:ChildItems", $nsMgr)
if ($rootCI) {
	foreach ($elem in $rootCI.SelectNodes(".//*[@id]")) {
		$id = $elem.GetAttribute("id")
		if ($id -and $id -ne "-1") {
			try { $intId = [int]$id; if ($intId -gt $script:nextElemId) { $script:nextElemId = $intId } } catch {}
		}
	}
}
# The form's own AutoCommandBar (id -1) and the buttons inside it
$acb = $root.SelectSingleNode("f:AutoCommandBar", $nsMgr)
if ($acb) {
	foreach ($elem in $acb.SelectNodes("descendant-or-self::*[@id]")) {
		$id = $elem.GetAttribute("id")
		if ($id -and $id -ne "-1") {
			try { $intId = [int]$id; if ($intId -gt $script:nextElemId) { $script:nextElemId = $intId } } catch {}
		}
	}
}

# Scan attribute IDs (including column IDs — same pool)
foreach ($attr in $root.SelectNodes("f:Attributes/f:Attribute", $nsMgr)) {
	$id = $attr.GetAttribute("id")
	if ($id) {
		try { $intId = [int]$id; if ($intId -gt $script:nextAttrId) { $script:nextAttrId = $intId } } catch {}
	}
	# Column IDs are in the same pool as attribute IDs
	foreach ($col in $attr.SelectNodes("f:Columns/f:Column", $nsMgr)) {
		$colId = $col.GetAttribute("id")
		if ($colId) {
			try { $intColId = [int]$colId; if ($intColId -gt $script:nextAttrId) { $script:nextAttrId = $intColId } } catch {}
		}
	}
}

# Scan command IDs
foreach ($cmd in $root.SelectNodes("f:Commands/f:Command", $nsMgr)) {
	$id = $cmd.GetAttribute("id")
	if ($id) {
		try { $intId = [int]$id; if ($intId -gt $script:nextCmdId) { $script:nextCmdId = $intId } } catch {}
	}
}

$script:nextElemId++
$script:nextAttrId++
$script:nextCmdId++

# --- 4b. Auto-detect extension mode (BaseForm present) ---
$script:isExtension = $false
$baseForm = $root.SelectSingleNode("f:BaseForm", $nsMgr)
if ($baseForm) {
	$script:isExtension = $true
	if ($script:nextAttrId -lt 1000000) { $script:nextAttrId = 1000000 }
	if ($script:nextCmdId -lt 1000000) { $script:nextCmdId = 1000000 }
	if ($script:nextElemId -lt 1000000) { $script:nextElemId = 1000000 }
}

function New-ElemId { $id = $script:nextElemId; $script:nextElemId++; return $id }
function New-AttrId { $id = $script:nextAttrId; $script:nextAttrId++; return $id }
function New-CmdId { $id = $script:nextCmdId; $script:nextCmdId++; return $id }

# === 5. Fragment helpers (StringBuilder) for commands and events ===
# Elements and attributes do not come from here: they are compiled by form-compile
# (section 9). Only the emitters of commands, formEvents and elementEvents stay local.

$script:xml = New-Object System.Text.StringBuilder 4096

function X {
	param([string]$text)
	$script:xml.AppendLine($text) | Out-Null
}

function Esc-Xml {
	param([string]$s)
	return $s.Replace('&','&amp;').Replace('<','&lt;').Replace('>','&gt;').Replace('"','&quot;')
}

function Emit-MLText {
	param([string]$tag, [string]$text, [string]$indent)
	X "$indent<$tag>"
	X "$indent`t<v8:item>"
	X "$indent`t`t<v8:lang>ru</v8:lang>"
	X "$indent`t`t<v8:content>$(Esc-Xml $text)</v8:content>"
	X "$indent`t</v8:item>"
	X "$indent</$tag>"
}

function Test-IsDynamicListType {
	param([string]$typeStr)
	return ($typeStr -eq "DynamicList" -or $typeStr -eq "cfg:DynamicList")
}

function Test-DynamicListSource {
	param($settings)
	if (-not $settings) { return $false }
	$main = "$($settings.mainTable)".Trim()
	$query = "$($settings.query)".Trim()
	return ($main -ne "" -or $query -ne "")
}

# Уникальность имён внутри JSON-определения (1С: своя коллекция — свой неймспейс).
function Assert-EditUnique {
	param([string]$name, [hashtable]$seen, [string]$ctx)
	if ($seen.ContainsKey($name)) {
		Write-Host "[ERROR] Duplicate $ctx '$name' in JSON definition — names must be unique in 1C form"
		exit 1
	}
	$seen[$name] = $true
}

# === 6. Find elements by name ===

# Element tree only (ChildItems, recursively): the lookup of elementEvents.
function Find-Element($startNode, [string]$targetName) {
	foreach ($child in $startNode.ChildNodes) {
		if ($child.NodeType -ne 'Element') { continue }
		$childName = $child.GetAttribute("name")
		if ($childName -eq $targetName) { return $child }
		$ci = $child.SelectSingleNode("f:ChildItems", $nsMgr)
		if ($ci) {
			$found = Find-Element $ci $targetName
			if ($found) { return $found }
		}
	}
	return $null
}

# Every named node of the form's element tree: the form's own AutoCommandBar and
# ChildItems with all descendants, companions (ExtendedTooltip, ContextMenu, a table's
# AutoCommandBar, the table additions) included. <Event name=".."> is not an element.
function Get-NamedNodes {
	$list = New-Object System.Collections.ArrayList
	foreach ($top in @($root.SelectNodes('f:AutoCommandBar | f:ChildItems', $nsMgr))) {
		if ($top.GetAttribute("name")) { [void]$list.Add($top) }
		foreach ($n in $top.SelectNodes('.//*[@name]')) {
			if ($n.NamespaceURI -eq $formNs -and $n.LocalName -ne 'Event') { [void]$list.Add($n) }
		}
	}
	return $list
}

function Find-Target([string]$targetName) {
	foreach ($n in @(Get-NamedNodes)) {
		if ($n.GetAttribute("name") -eq $targetName) { return $n }
	}
	return $null
}

# === 7. Detect indent level of a container's children ===

# Indent of the line a node starts on (the whitespace before it); by depth when it has none.
function Get-NodeIndent($node) {
	$prev = $node.PreviousSibling
	if ($prev -and ($prev.NodeType -eq 'Whitespace' -or $prev.NodeType -eq 'SignificantWhitespace')) {
		$i = $prev.Value.LastIndexOf("`n")
		if ($i -ge 0) { return $prev.Value.Substring($i + 1) }
	}
	$depth = 0
	$current = $node.ParentNode
	while ($current -and $current.NodeType -eq 'Element') { $depth++; $current = $current.ParentNode }
	return "`t" * $depth
}

function Get-ChildIndent($container) {
	foreach ($child in $container.ChildNodes) {
		if ($child.NodeType -eq 'Whitespace' -or $child.NodeType -eq 'SignificantWhitespace') {
			$text = $child.Value
			if ($text -match '^\r?\n(\t+)$') { return $Matches[1] }
			if ($text -match '^\r?\n(\t+)') { return $Matches[1] }
		}
	}
	# No children yet: one tab deeper than the container itself
	return (Get-NodeIndent $container) + "`t"
}

# ChildItems of an element, created when absent. It is the last child of every element
# that has one (after HorizontalAlign / Autofill of a command bar, after the companions
# and events of the others), on its own lines whether the owner was a self-closing tag or not.
function Ensure-ChildItems($owner) {
	$ci = $owner.SelectSingleNode("f:ChildItems", $nsMgr)
	if ($ci) { return $ci }
	$ownerIndent = Get-NodeIndent $owner
	$ci = $xmlDoc.CreateElement("ChildItems", $formNs)
	$last = $owner.LastChild
	if ($last -and ($last.NodeType -eq 'Whitespace' -or $last.NodeType -eq 'SignificantWhitespace')) {
		$owner.InsertBefore($xmlDoc.CreateWhitespace("`r`n$ownerIndent`t"), $last) | Out-Null
		$owner.InsertBefore($ci, $last) | Out-Null
	} else {
		$owner.AppendChild($xmlDoc.CreateWhitespace("`r`n$ownerIndent`t")) | Out-Null
		$owner.AppendChild($ci) | Out-Null
		$owner.AppendChild($xmlDoc.CreateWhitespace("`r`n$ownerIndent")) | Out-Null
	}
	return $ci
}

# === 8. Insert node into container ===

function Insert-IntoContainer($container, $newNode, $afterName, $childIndent, $beforeName = $null) {
	$refNode = $null
	$beforeAnchor = $false

	if ($beforeName) {
		# Insert before the named element
		foreach ($child in $container.ChildNodes) {
			if ($child.NodeType -eq 'Element' -and $child.GetAttribute("name") -eq $beforeName) {
				$refNode = $child
				$beforeAnchor = $true
				break
			}
		}
		if (-not $refNode) {
			Write-Host "[WARN] before='$beforeName' not found in target container, appending at end"
		}
	} elseif ($afterName) {
		# Find the after-element, then insert after it
		$afterElem = $null
		foreach ($child in $container.ChildNodes) {
			if ($child.NodeType -eq 'Element' -and $child.GetAttribute("name") -eq $afterName) {
				$afterElem = $child
				break
			}
		}
		if ($afterElem) {
			$refNode = $afterElem.NextSibling
		} else {
			Write-Host "[WARN] after='$afterName' not found in target container, appending at end"
		}
	}

	if (-not $refNode) {
		# Append at end: insert before trailing whitespace
		$trailing = $container.LastChild
		if ($trailing -and ($trailing.NodeType -eq 'Whitespace' -or $trailing.NodeType -eq 'SignificantWhitespace')) {
			$refNode = $trailing
		}
	}

	$ws = $xmlDoc.CreateWhitespace("`r`n$childIndent")
	if ($refNode -and $beforeAnchor) {
		# The anchor keeps the whitespace in front of it: node, line break, anchor
		$container.InsertBefore($newNode, $refNode) | Out-Null
		$container.InsertBefore($ws, $refNode) | Out-Null
	} elseif ($refNode) {
		$container.InsertBefore($ws, $refNode) | Out-Null
		$container.InsertBefore($newNode, $refNode) | Out-Null
	} else {
		# Container is empty (self-closing) — add framing whitespace
		$container.AppendChild($ws) | Out-Null
		$container.AppendChild($newNode) | Out-Null
		$parentIndent = if ($childIndent.Length -gt 1) { $childIndent.Substring(0, $childIndent.Length - 1) } else { "" }
		$closeWs = $xmlDoc.CreateWhitespace("`r`n$parentIndent")
		$container.AppendChild($closeWs) | Out-Null
	}
}

# === 8b. Target of a placement (add and move) ===

$script:holderTags = @('UsualGroup','ColumnGroup','Pages','Page','Table','AutoCommandBar','ContextMenu','CommandBar','ButtonGroup','Popup')
$script:cmdHolderTags = @('AutoCommandBar','ContextMenu','CommandBar','ButtonGroup','Popup')

# The container a placement (into / after / before) leads to; nothing is changed in the form.
# Mode: plain | cmd (command bar, context menu, popup, button group) | table.
function Resolve-Target([string]$intoName, [string]$afterName, [string]$beforeName) {
	$owner = $null
	$targetCI = $null
	$mode = 'plain'
	if ($intoName) {
		$owner = Find-Target $intoName
		if (-not $owner) {
			Write-Host "[ERROR] Target '$intoName' not found"
			exit 1
		}
		if ($script:holderTags -notcontains $owner.LocalName) {
			Write-Host "[ERROR] Target '$intoName' is <$($owner.LocalName)> and holds no elements. Possible: group, pages, page, table, command bar, context menu, popup, button group"
			exit 1
		}
		$targetCI = $owner.SelectSingleNode("f:ChildItems", $nsMgr)
	} elseif ($afterName -or $beforeName) {
		# Find the anchor globally and use its parent as target
		$anchorName = if ($beforeName) { $beforeName } else { $afterName }
		$anchor = Find-Target $anchorName
		if (-not $anchor) {
			Write-Host "[ERROR] Element '$anchorName' not found"
			exit 1
		}
		if ($anchor.ParentNode.LocalName -ne 'ChildItems') {
			Write-Host "[ERROR] '$anchorName' is <$($anchor.LocalName)>, a part of its element, not an item of a container — name the container with into"
			exit 1
		}
		$targetCI = $anchor.ParentNode
		$owner = $targetCI.ParentNode
	} else {
		$owner = $root
		$targetCI = $rootCI
	}
	if (-not [object]::ReferenceEquals($owner, $root)) {
		if ($script:cmdHolderTags -contains $owner.LocalName) { $mode = 'cmd' }
		elseif ($owner.LocalName -eq 'Table') { $mode = 'table' }
	}
	return [pscustomobject]@{ Owner = $owner; TargetCI = $targetCI; Mode = $mode }
}

# Why an element of this tag cannot go into the target (or $null).
function Get-PlacementError($target, [string]$tag, [string]$name) {
	$owner = $target.Owner
	$ownerName = if ([object]::ReferenceEquals($owner, $root)) { "form" } else { $owner.GetAttribute("name") }
	if ($target.Mode -eq 'table' -and @('Button','ButtonGroup','Popup','CommandBar') -contains $tag) {
		$tableBar = $owner.SelectSingleNode("f:AutoCommandBar", $nsMgr)
		$hint = if ($tableBar) { "use into: `"$($tableBar.GetAttribute('name'))`"" } else { "the table has no command bar of its own" }
		return "'$name' is <$tag>: the ChildItems of table '$ownerName' hold its columns, buttons go to its command bar — $hint"
	}
	if ($target.Mode -eq 'cmd' -and @('Button','ButtonGroup','Popup') -notcontains $tag) {
		return "'$name' is <$tag>: '$ownerName' takes buttons, button groups and popups only"
	}
	return $null
}

# The ChildItems of the target, created when the owner has none.
function Ensure-TargetCI($target) {
	if ($target.TargetCI) { return $target.TargetCI }
	$owner = $target.Owner
	if ([object]::ReferenceEquals($owner, $root)) {
		# Create ChildItems section in form — insert after Events or AutoCommandBar
		$ci = $xmlDoc.CreateElement("ChildItems", $formNs)
		$insertAfter = $root.SelectSingleNode("f:Events", $nsMgr)
		if (-not $insertAfter) { $insertAfter = $root.SelectSingleNode("f:AutoCommandBar", $nsMgr) }
		if ($insertAfter) {
			$refNode = $insertAfter.NextSibling
			$ws = $xmlDoc.CreateWhitespace("`r`n`t")
			$root.InsertBefore($ws, $refNode) | Out-Null
			$root.InsertBefore($ci, $refNode) | Out-Null
		} else {
			$root.AppendChild($xmlDoc.CreateWhitespace("`r`n`t")) | Out-Null
			$root.AppendChild($ci) | Out-Null
		}
		# Also update $rootCI reference
		$script:rootCI = $ci
		return $ci
	}
	return (Ensure-ChildItems $owner)
}

# The Attributes section of the form, created when absent (after ChildItems, else Events, else AutoCommandBar).
function Ensure-AttrsSection {
	$attrsSection = $root.SelectSingleNode("f:Attributes", $nsMgr)
	if ($attrsSection) { return $attrsSection }
	$attrsSection = $xmlDoc.CreateElement("Attributes", $formNs)
	$insertAfter = $rootCI
	if (-not $insertAfter) { $insertAfter = $root.SelectSingleNode("f:Events", $nsMgr) }
	if (-not $insertAfter) { $insertAfter = $root.SelectSingleNode("f:AutoCommandBar", $nsMgr) }
	if ($insertAfter) {
		$refNode = $insertAfter.NextSibling
		$ws = $xmlDoc.CreateWhitespace("`r`n`t")
		$root.InsertBefore($ws, $refNode) | Out-Null
		$root.InsertBefore($attrsSection, $refNode) | Out-Null
	} else {
		$root.AppendChild($xmlDoc.CreateWhitespace("`r`n`t")) | Out-Null
		$root.AppendChild($attrsSection) | Out-Null
	}
	return $attrsSection
}

# === 9. Generate fragment, parse, import nodes ===

$allNsDecl = 'xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" xmlns:dcssch="http://v8.1c.ru/8.1/data-composition-system/schema"'

function Parse-Fragment([string]$xmlText) {
	$fragDoc = New-Object System.Xml.XmlDocument
	$fragDoc.PreserveWhitespace = $true
	$fragDoc.LoadXml($xmlText)
	return $fragDoc
}

function Import-ElementNodes($fragDoc) {
	$nodes = @()
	foreach ($child in $fragDoc.DocumentElement.ChildNodes) {
		if ($child.NodeType -eq 'Element') {
			$nodes += $xmlDoc.ImportNode($child, $true)
		}
	}
	return $nodes
}

# --- 9b. Compile bridge: elements and attributes are written by form-compile ---
# A second copy of the emitters drifted from the compiler (textEdit, maxWidth,
# choiceParameters, save, AdditionSource of the table additions, ... were dropped
# with «unknown key ... ignored»). The new items go into a temporary DSL, form-compile
# compiles it into a temporary Form.xml (outside Forms\<Name>\Ext, so no parent object
# is touched), and the compiled nodes are renumbered, re-indented and imported below.
# Commands stay with the emitters above: the compiler writes their children in an
# order the platform refused (CHANGELOG 2026-10-01).

$script:compileScript = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../1c-form-compile/scripts/form-compile.ps1'))

function Invoke-FormCompileFragment($dsl) {
	if (-not (Test-Path -LiteralPath $script:compileScript)) {
		Write-Host "[ERROR] form-compile not found: $script:compileScript"
		exit 1
	}
	$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("form-edit-" + [guid]::NewGuid().ToString('N'))
	try {
		New-Item -ItemType Directory -Path $tmp -Force | Out-Null
		$dslPath = Join-Path $tmp 'fragment.json'
		$outPath = Join-Path $tmp 'Form.xml'
		[System.IO.File]::WriteAllText($dslPath, ($dsl | ConvertTo-Json -Depth 50), (New-Object System.Text.UTF8Encoding($true)))

		# form-compile ends with exit: a child process of the same PowerShell edition.
		$psi = New-Object System.Diagnostics.ProcessStartInfo
		$psi.FileName = (Get-Process -Id $PID).Path
		# -Command, not -File: a refusal of the compiler (Write-Error under Stop) arrives as its plain
		# message instead of the host's decorated error record.
		$q = { param([string]$s) "'" + $s.Replace("'", "''") + "'" }
		$cmd = "try { & " + (& $q $script:compileScript) + " -JsonPath " + (& $q $dslPath) + " -OutputPath " + (& $q $outPath) + "; exit `$LASTEXITCODE } catch { [Console]::Error.WriteLine(`$_.Exception.Message); exit 1 }"
		$psi.Arguments = '-NoProfile -ExecutionPolicy Bypass -Command "' + $cmd + '"'
		$psi.UseShellExecute = $false
		$psi.CreateNoWindow = $true
		$psi.RedirectStandardOutput = $true
		$psi.RedirectStandardError = $true
		$psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
		$psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
		$proc = [System.Diagnostics.Process]::Start($psi)
		$errTask = $proc.StandardError.ReadToEndAsync()
		$outText = $proc.StandardOutput.ReadToEnd()
		$proc.WaitForExit()
		$errText = $errTask.Result
		$lines = @((($outText + "`n" + $errText) -split "\r?\n") | Where-Object { $_.Trim() -ne '' })

		if ($proc.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $outPath)) {
			foreach ($l in $lines) {
				if ($l -match 'Configuration\.xml not found above') { continue }
				Write-Host $l
			}
			Write-Host "[ERROR] form-compile refused the definition — nothing was written"
			exit 1
		}

		# The compiler's warnings (the host localizes the «WARNING:» prefix) replace form-edit's own
		# «unknown key» ones; its summary and the note about the temporary path do not.
		foreach ($l in $lines) {
			if ($l -match 'Configuration\.xml not found above') { continue }
			if ($l -match '^\[OK\] Compiled' -or $l -match '^\s+(Elements\+IDs|Attributes|Commands|Parameters|Registered):') { continue }
			Write-Host $l.Trim()
		}

		$compiled = New-Object System.Xml.XmlDocument
		$compiled.PreserveWhitespace = $true
		$compiled.Load($outPath)
		return $compiled
	} finally {
		Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
	}
}

# Leading whitespace of every line inside an imported subtree: srcIndent -> dstIndent.
# Only whitespace-only nodes are touched, so a multi-line text of an element stays as written.
function Set-NodeIndent($node, [string]$srcIndent, [string]$dstIndent) {
	if ($srcIndent -eq $dstIndent) { return }
	$pattern = "(?<=\n)" + [regex]::Escape($srcIndent)
	foreach ($child in @($node.ChildNodes)) {
		if ($child.NodeType -eq 'Whitespace' -or $child.NodeType -eq 'SignificantWhitespace') {
			if ($child.Value.IndexOf("`n") -ge 0) { $child.Value = [regex]::Replace($child.Value, $pattern, $dstIndent) }
		} elseif ($child.NodeType -eq 'Element') {
			Set-NodeIndent $child $srcIndent $dstIndent
		}
	}
}

# Fresh element ids, in document order, for the subtree (the form's own bar, id -1, never
# occurs inside it). References inside Form.xml are by name, so nothing else changes.
function Set-ElementIds($node) {
	foreach ($n in @($node.SelectNodes('descendant-or-self::*[@id]'))) {
		if ($n.GetAttribute("id") -eq "-1") { continue }
		$n.SetAttribute("id", [string](New-ElemId))
	}
}

# Prefixes the imported nodes use (as element or attribute names, and in xsi:type / type
# texts such as cfg:CatalogObject.X) must be declared on the target's <Form>; a form that
# lacks one gets the compiler's declaration there instead of a copy on every node.
function Ensure-Namespaces($srcDoc, $nodes) {
	$text = (@($nodes | ForEach-Object { $_.OuterXml }) -join "`n")
	# get_Attributes(): a child element <Attributes> shadows the property in PowerShell's XML adapter
	foreach ($a in $srcDoc.DocumentElement.get_Attributes()) {
		if ($a.Prefix -ne 'xmlns') { continue }
		$prefix = $a.LocalName
		if ($text -notmatch ('(?<![\w.:/-])' + [regex]::Escape($prefix) + ':(?=[A-Za-z_])')) { continue }
		$have = $root.GetNamespaceOfPrefix($prefix)
		if ($have -and $have -ne $a.Value) {
			Write-Host "[ERROR] Prefix '$prefix' is bound to '$have' in this form, the compiled items need '$($a.Value)'"
			exit 1
		}
		if (-not $have) {
			$decl = $xmlDoc.CreateAttribute("xmlns", $prefix, "http://www.w3.org/2000/xmlns/")
			$decl.Value = $a.Value
			$first = $null
			$rootAttrs = $root.get_Attributes()
			foreach ($ra in $rootAttrs) { if ($ra.Prefix -ne 'xmlns' -and $ra.Name -ne 'xmlns') { $first = $ra; break } }
			if ($first) { $rootAttrs.InsertBefore($decl, $first) | Out-Null } else { $rootAttrs.Append($decl) | Out-Null }
		}
	}
}

function Get-TablePaths($els, [hashtable]$acc) {
	foreach ($e in @($els)) {
		if ($null -eq $e) { continue }
		if ($null -ne $e.PSObject.Properties["table"] -and $null -ne $e.table -and $e.path) { $acc["$($e.path)"] = $true }
		if ($e.PSObject.Properties["children"] -and $e.children) { Get-TablePaths $e.children $acc }
	}
}

# === 9c. set: properties and events of existing elements and of the form ===

# Child order of the elements, derived from the vendor dumps (scan of every Form.xml under
# the 1C projects: 29727 files, 14917 distinct, 473382 elements of these tags plus the
# 14917 <Form> roots): for every parent tag the pairwise precedence of its child tags
# was counted, the majority direction became an edge, a topological sort gave the list,
# ties and tags that never meet come out by their mean relative position. The platform
# tolerates some variation, the majority order is what the Configurator writes.
# A property that has to be inserted goes before the first child of a greater rank.
$script:childRank = @{
	'Form' = 'Scale,Title,Width,Height,WindowOpeningMode,EnterKeyBehavior,AutoSaveDataInSettings,SaveDataInSettings,SettingsStorage,AutoTitle,HorizontalSpacing,HorizontalAlign,VerticalAlign,AutoURL,Group,ChildItemsWidth,VerticalSpacing,AutoFillCheck,Customizable,Enabled,CommandBarLocation,VerticalScroll,ScalingMode,ConversationsRepresentation,MobileDeviceCommandBarContent,CommandSet,AutoTime,GroupList,UsePostingMode,ReportResult,RepostOnWrite,DetailsData,ShowTitle,UseForFoldersAndItems,ReportFormType,ShowCloseButton,VariantAppearance,AutoShowState,CustomSettingsFolder,ReportResultViewMode,CollapseItemsByImportanceVariant,ViewModeApplicationOnSetReportResult,AutoCommandBar,Events,ChildItems,Attributes,Commands,Parameters,BaseForm,CommandInterface'
	'InputField' = 'DataPath,Visible,UserVisible,Enabled,DefaultItem,ReadOnly,SkipOnInput,Title,TitleTextColor,TitleBackColor,TitleFont,TitleLocation,TitleHeight,ToolTip,ToolTipRepresentation,WarningOnEditRepresentation,WarningOnEdit,Shortcut,HorizontalAlign,GroupHorizontalAlign,GroupVerticalAlign,VerticalAlign,EditMode,FooterBackColor,FixingInTable,CellHyperlink,AutoCellHeight,ShowInHeader,HeaderPicture,HeaderHorizontalAlign,FooterDataPath,FooterTextColor,FooterText,FooterFont,ShowInFooter,FooterHorizontalAlign,FooterPicture,Width,AutoMaxWidth,MaxWidth,Height,AutoMaxHeight,MaxHeight,HorizontalStretch,AllowInputEmptyMultipleValues,VerticalStretch,Wrap,PasswordMode,MultiLine,ExtendedEdit,DropListButton,ChoiceButton,ChoiceButtonRepresentation,ClearButton,SpinButton,MarkNegatives,OpenButton,Mask,CreateButton,ListChoiceMode,AutoChoiceIncomplete,ExtendedEditMultipleValues,QuickChoice,ChoiceFoldersAndItems,Format,EditFormat,AutoMarkIncomplete,ChooseType,IncompleteChoiceMode,TypeDomainEnabled,TextEdit,MinValue,ChoiceForm,EditTextUpdate,MaxValue,ChoiceParameterLinks,ChoiceParameters,ChoiceButtonPicture,ChoiceList,AutoCorrectionOnTextInput,AutoShowOpenButtonMode,AvailableTypes,ChoiceListButton,TextColor,ChoiceListHeight,DropListWidth,BackColor,TypeLink,BorderColor,Font,SpecialTextInputMode,InputHint,ChoiceHistoryOnInput,SpellCheckingOnTextInput,HeightControlVariant,AutoShowClearButtonMode,ContextMenu,ExtendedTooltip,Events'
	'CheckBoxField' = 'DataPath,Visible,UserVisible,Enabled,ReadOnly,SkipOnInput,DefaultItem,Title,TitleTextColor,TitleBackColor,TitleFont,TitleLocation,TitleHeight,ToolTip,HorizontalAlign,FooterHorizontalAlign,CellHyperlink,ToolTipRepresentation,GroupHorizontalAlign,WarningOnEditRepresentation,VerticalAlign,GroupVerticalAlign,EditMode,ShowInHeader,FooterDataPath,FixingInTable,WarningOnEdit,HeaderPicture,ShowInFooter,ThreeState,HeaderHorizontalAlign,CheckBoxType,EditFormat,BackColor,ItemTitleHeight,ItemHeight,EqualItemsWidth,ContextMenu,ExtendedTooltip,Events'
	'RadioButtonField' = 'DataPath,Visible,DefaultItem,Enabled,SkipOnInput,ReadOnly,Title,UserVisible,TitleTextColor,TitleFont,TitleLocation,TitleHeight,ToolTip,Shortcut,HorizontalAlign,ToolTipRepresentation,WarningOnEditRepresentation,EditMode,VerticalAlign,GroupHorizontalAlign,GroupVerticalAlign,WarningOnEdit,FooterHorizontalAlign,RadioButtonType,ItemWidth,ItemHeight,ItemTitleHeight,ColumnsCount,EqualColumnsWidth,ChoiceList,BorderColor,Font,ContextMenu,ExtendedTooltip,Events'
	'LabelDecoration' = 'UserVisible,Visible,Enabled,Width,AutoMaxWidth,MaxWidth,Height,AutoMaxHeight,MaxHeight,HorizontalStretch,VerticalStretch,SkipOnInput,TextColor,Font,Title,ToolTip,ToolTipRepresentation,GroupHorizontalAlign,GroupVerticalAlign,Hyperlink,HorizontalAlign,VerticalAlign,TitleHeight,BackColor,BorderColor,Border,ContextMenu,ExtendedTooltip,Events'
	'LabelField' = 'DataPath,Visible,Enabled,UserVisible,DefaultItem,ReadOnly,SkipOnInput,Title,TitleTextColor,WarningOnEditRepresentation,TitleBackColor,TitleFont,TitleLocation,TitleHeight,Shortcut,ToolTip,ToolTipRepresentation,HorizontalAlign,VerticalAlign,GroupHorizontalAlign,EditMode,FixingInTable,CellHyperlink,AutoCellHeight,ShowInHeader,FooterText,ShowInFooter,HeaderPicture,HeaderHorizontalAlign,FooterDataPath,FooterHorizontalAlign,GroupVerticalAlign,Width,AutoMaxWidth,MaxWidth,Height,AutoMaxHeight,MaxHeight,HorizontalStretch,MarkNegatives,VerticalStretch,Format,Hiperlink,Border,BorderColor,PasswordMode,TextColor,BackColor,Font,ContextMenu,ExtendedTooltip,Events'
	'PictureDecoration' = 'Visible,Enabled,Width,AutoMaxWidth,MaxWidth,Height,AutoMaxHeight,MaxHeight,HorizontalStretch,VerticalStretch,SkipOnInput,TextColor,Font,Title,ToolTip,ToolTipRepresentation,GroupHorizontalAlign,GroupVerticalAlign,Hyperlink,PictureSize,Zoomable,ImageScale,NonselectedPictureText,Picture,BorderColor,Border,FileDragMode,ContextMenu,ExtendedTooltip,Events'
	'PictureField' = 'DataPath,Visible,UserVisible,ReadOnly,SkipOnInput,Title,TitleTextColor,TitleBackColor,Enabled,TitleFont,TitleLocation,TitleHeight,GroupHorizontalAlign,WarningOnEditRepresentation,ToolTip,GroupVerticalAlign,ToolTipRepresentation,HorizontalAlign,EditMode,FixingInTable,CellHyperlink,ShowInHeader,Shortcut,HeaderPicture,HeaderHorizontalAlign,AutoCellHeight,ShowInFooter,FooterHorizontalAlign,Width,AutoMaxWidth,Height,AutoMaxHeight,FooterDataPath,FooterText,MaxWidth,MaxHeight,HorizontalStretch,VerticalStretch,PictureSize,Zoomable,Hyperlink,NonselectedPictureText,EnableDrag,ValuesPicture,TextColor,Font,BorderColor,Border,FileDragMode,ContextMenu,ExtendedTooltip,Events'
	'CalendarField' = 'DataPath,DefaultItem,Title,TitleLocation,ToolTip,SkipOnInput,ToolTipRepresentation,Width,Height,AutoMaxHeight,AutoMaxWidth,ShowMonthsPanel,MaxHeight,SelectionMode,VerticalStretch,ShowCurrentDate,HorizontalStretch,WidthInMonths,CalendarNavigation,EnableDrag,HeightInMonths,Border,ContextMenu,ExtendedTooltip,Events'
	'Table' = 'Representation,Visible,TitleHeight,TitleLocation,CommandBarLocation,Enabled,UserVisible,Autofill,ReadOnly,SkipOnInput,DefaultItem,ChangeRowSet,ChangeRowOrder,Width,AutoMaxWidth,MaxWidth,Height,AutoMaxHeight,MaxHeight,HeightInTableRows,HeightControlVariant,AutoMaxRowsCount,MaxRowsCount,ChoiceMode,MultipleChoice,RowInputMode,SelectionMode,RowSelectionMode,Header,HeaderHeight,Footer,FooterHeight,HorizontalScrollBar,VerticalScrollBar,HorizontalLines,VerticalLines,UseAlternationRowColor,AutoInsertNewRow,AutoAddIncomplete,AutoMarkIncomplete,SearchOnInput,InitialListView,InitialTreeView,HorizontalStretch,VerticalStretch,Output,EnableStartDrag,EnableDrag,FileDragMode,DataPath,RowPictureDataPath,RowsPicture,TextColor,BackColor,BorderColor,Font,Title,BehaviorOnHorizontalCompression,TitleTextColor,Shortcut,TitleFont,CommandSet,ToolTip,ToolTipRepresentation,SearchStringLocation,ViewStatusLocation,RefreshRequest,SearchControlLocation,CurrentRowUse,AutoRefresh,AutoRefreshPeriod,Period,ChoiceFoldersAndItems,RestoreCurrentRow,GroupHorizontalAlign,GroupVerticalAlign,RowFilter,TopLevelParent,ViewMode,ShowRoot,SettingsNamedItemDetailedRepresentation,AllowRootChoice,UpdateOnDataChange,UserSettingsGroup,AllowGettingCurrentRowURL,ContextMenu,AutoCommandBar,ExtendedTooltip,SearchStringAddition,ViewStatusAddition,SearchControlAddition,Events,ChildItems'
	'UsualGroup' = 'UserVisible,Visible,Enabled,ReadOnly,EnableContentChange,Title,TitleTextColor,TitleFont,ToolTip,ToolTipRepresentation,Shortcut,Width,Height,HorizontalStretch,VerticalStretch,GroupHorizontalAlign,GroupVerticalAlign,Group,ChildrenAlign,HorizontalSpacing,VerticalSpacing,HorizontalAlign,VerticalAlign,Behavior,CollapsedRepresentationTitle,Collapsed,ControlRepresentation,Representation,Format,United,ShowLeftMargin,ChildItemsWidth,ShowTitle,TitleDataPath,BackColor,ThroughAlign,CurrentRowUse,ExtendedTooltip,ChildItems'
	'ColumnGroup' = 'Visible,ReadOnly,UserVisible,EnableContentChange,Enabled,Title,TitleTextColor,TitleFont,ToolTip,ToolTipRepresentation,Width,Height,HorizontalStretch,VerticalStretch,Group,ShowTitle,TitleBackColor,ShowInHeader,HeaderPicture,HeaderHorizontalAlign,FixingInTable,ExtendedTooltip,ChildItems'
	'Pages' = 'UserVisible,Visible,Enabled,ReadOnly,EnableContentChange,Title,TitleFont,ToolTip,ToolTipRepresentation,Width,Height,HorizontalStretch,VerticalStretch,GroupHorizontalAlign,GroupVerticalAlign,PagesRepresentation,CurrentRowUse,ExtendedTooltip,Events,ChildItems'
	'Page' = 'Visible,UserVisible,Enabled,ReadOnly,EnableContentChange,Title,GroupVerticalAlign,TitleTextColor,Shortcut,TitleFont,ToolTip,ToolTipRepresentation,Width,Height,HorizontalStretch,VerticalStretch,Picture,Format,Group,ChildrenAlign,HorizontalSpacing,VerticalSpacing,ChildItemsWidth,ScrollOnCompress,HorizontalAlign,VerticalAlign,ShowTitle,TitleDataPath,BackColor,ExtendedTooltip,ChildItems'
	'Button' = 'Type,Visible,TitleHeight,UserVisible,Representation,DefaultButton,SkipOnInput,Enabled,DefaultItem,Width,AutoMaxWidth,MaxWidth,Height,AutoMaxHeight,MaxHeight,HorizontalStretch,GroupHorizontalAlign,Check,GroupVerticalAlign,VerticalStretch,CommandName,Parameter,DataPath,TextColor,BackColor,BorderColor,Font,Picture,Title,RepresentationInContextMenu,ToolTipRepresentation,Shape,PictureLocation,ShapeRepresentation,LocationInCommandBar,ExtendedTooltip'
	'ButtonGroup' = 'Visible,UserVisible,EnableContentChange,Title,GroupVerticalAlign,Width,ToolTip,ToolTipRepresentation,HorizontalStretch,GroupHorizontalAlign,Representation,CommandSource,VerticalStretch,ExtendedTooltip,ChildItems'
	'CommandBar' = 'Visible,Item,Enabled,ReadOnly,EnableContentChange,Title,ToolTip,Width,ToolTipRepresentation,Height,HorizontalStretch,VerticalStretch,GroupHorizontalAlign,GroupVerticalAlign,HorizontalLocation,CommandSource,ExtendedTooltip,ChildItems'
	'Popup' = 'UserVisible,Visible,EnableContentChange,Title,TitleFont,ToolTip,TitleTextColor,Width,HorizontalStretch,Picture,VerticalStretch,ToolTipRepresentation,GroupHorizontalAlign,CommandSource,Representation,BackColor,ShapeRepresentation,ExtendedTooltip,ChildItems'
}
$script:rankIndex = @{}
foreach ($rk in $script:childRank.Keys) {
	$rh = @{}
	$ri = 0
	foreach ($rt in ($script:childRank[$rk] -split ',')) { $rh[$rt] = $ri; $ri++ }
	$script:rankIndex[$rk] = $rh
}

# Children that are not properties: companions, events, the element tree, the form's sections.
$script:structTagsElement = @('ContextMenu','ExtendedTooltip','AutoCommandBar','SearchStringAddition','ViewStatusAddition','SearchControlAddition','Events','ChildItems')
$script:structTagsForm = @('AutoCommandBar','Events','ChildItems','Attributes','Commands','Parameters','BaseForm','CommandInterface')

function Get-StructTags([string]$tag) {
	if ($tag -eq 'Form') { return $script:structTagsForm }
	return $script:structTagsElement
}

function Get-PropTags([string]$tag) {
	$struct = Get-StructTags $tag
	return @($script:childRank[$tag] -split ',' | Where-Object { $struct -notcontains $_ })
}

function Get-RankOf([string]$parentTag, [string]$childTag) {
	$h = $script:rankIndex[$parentTag]
	if ($h -and $h.ContainsKey($childTag)) { return $h[$childTag] }
	return -1
}

# DSL key -> XML tag where it is not the PascalCase of the key (the emitters of form-compile).
# An alternative after | is taken when the first is not a property of the element (LabelField
# spells its hyperlink Hiperlink in the platform's XML).
$script:setKeyTag = @{
	path = 'DataPath'; markIncomplete = 'AutoMarkIncomplete'; tooltip = 'ToolTip'
	tooltipRepresentation = 'ToolTipRepresentation'; hidden = 'Visible'; visible = 'Visible'
	disabled = 'Enabled'; enabled = 'Enabled'; command = 'CommandName'; commandName = 'CommandName'
	stdCommand = 'CommandName'; checked = 'Check'; collapsedTitle = 'CollapsedRepresentationTitle'
	src = 'Picture'; loadTransparent = 'Picture'; transparentPixel = 'Picture'; picture = 'Picture'
	hyperlink = 'Hyperlink|Hiperlink'; columnGroup = 'Group'; excludedCommands = 'CommandSet'
}

# Keys that change what the element is made of: its tree, companions, name or type.
$script:setRefusedKeys = @{
	children = 'the content of a group moves with move / remove / elements'
	columns = 'the columns of a table are elements - use elements, move or remove'
	name = 'an element is not renamed'
	contextMenu = 'the context menu is a companion'
	extendedTooltip = 'the extended tooltip is a companion'
	commandBar = 'the command bar is a companion'
	tableAutofill = 'the command bar is a companion'
	additions = 'the additions of a table are companions'
	events = 'use on / off'
	handlers = 'use on / off'
	displayImportance = 'DisplayImportance is an attribute of the element, not a property'
}
# DSL type keys: a key that would make form-compile read the probe as another element.
$script:setTypeKeyNames = @('input','check','radio','label','labelField','table','pages','page','button','calendar','cmdBar','popup','buttonGroup','picField','picture','columnGroup','group')

$script:setTypeKeys = @{
	InputField = 'input'; CheckBoxField = 'check'; LabelDecoration = 'label'; LabelField = 'labelField'
	Table = 'table'; UsualGroup = 'group'; Pages = 'pages'; Page = 'page'; Button = 'button'
	PictureDecoration = 'picture'; PictureField = 'picField'; CalendarField = 'calendar'
	CommandBar = 'cmdBar'; Popup = 'popup'; RadioButtonField = 'radio'; ColumnGroup = 'columnGroup'
	ButtonGroup = 'buttonGroup'
}

function Get-SetKeyTag([string]$key, [string]$tag) {
	$props = Get-PropTags $tag
	$cand = if ($script:setKeyTag.ContainsKey($key)) { "$($script:setKeyTag[$key])" } else { $key.Substring(0, 1).ToUpper() + $key.Substring(1) }
	foreach ($alt in ($cand -split '\|')) {
		if ($props -ccontains $alt) { return $alt }
	}
	return $null
}

function Test-SetRemoval($v) {
	if ($null -eq $v) { return $true }
	if ($v -is [array]) { return ($v.Count -eq 0) }
	if ($v -is [System.Management.Automation.PSCustomObject]) { return (@($v.PSObject.Properties).Count -eq 0) }
	return $false
}

function Remove-NodeWithWs($node) {
	$parent = $node.ParentNode
	$prev = $node.PreviousSibling
	if ($prev -and ($prev.NodeType -eq 'Whitespace' -or $prev.NodeType -eq 'SignificantWhitespace')) { $parent.RemoveChild($prev) | Out-Null }
	$parent.RemoveChild($node) | Out-Null
}

# A property goes before the first child of a greater rank; a tag outside the table goes before
# the first companion / ChildItems / Events; nothing greater - at the end.
function Insert-ByRank($parent, [string]$parentTag, $newNode, [string]$childIndent) {
	$ref = $null
	$rank = Get-RankOf $parentTag $newNode.LocalName
	if ($rank -ge 0) {
		foreach ($c in $parent.ChildNodes) {
			if ($c.NodeType -ne 'Element') { continue }
			if ((Get-RankOf $parentTag $c.LocalName) -gt $rank) { $ref = $c; break }
		}
	} else {
		Write-Host "[WARN] <$($newNode.LocalName)> is not in the child order table of <$parentTag> - placed before the companions, ChildItems and Events"
		$struct = Get-StructTags $parentTag
		foreach ($c in $parent.ChildNodes) {
			if ($c.NodeType -eq 'Element' -and $struct -contains $c.LocalName) { $ref = $c; break }
		}
	}
	if ($ref) {
		$parent.InsertBefore($newNode, $ref) | Out-Null
		$parent.InsertBefore($xmlDoc.CreateWhitespace("`r`n$childIndent"), $ref) | Out-Null
	} else {
		Insert-IntoContainer -container $parent -newNode $newNode -afterName $null -childIndent $childIndent
	}
}

function Get-ChildByTag($parent, [string]$tag) {
	foreach ($c in $parent.ChildNodes) {
		if ($c.NodeType -eq 'Element' -and $c.LocalName -eq $tag) { return $c }
	}
	return $null
}

function New-EventNode([string]$name, [string]$handler, [string]$callType) {
	$ev = $xmlDoc.CreateElement("Event", $formNs)
	$ev.SetAttribute("name", $name)
	if ($callType) { $ev.SetAttribute("callType", $callType) }
	$ev.InnerText = $handler
	return $ev
}

function Format-EventLabel([string]$name, [string]$callType) {
	if ($callType) { return "$name[$callType]" }
	return $name
}

# on: entries {name, handler, callType}; an event of the same name and callType is replaced.
function Merge-Events($target, [string]$tag, $entries, $changes) {
	if ($null -eq $entries -or @($entries).Count -eq 0) { return }
	$evs = Get-ChildByTag $target 'Events'
	$childIndent = Get-ChildIndent $target
	if (-not $evs) {
		$evs = $xmlDoc.CreateElement("Events", $formNs)
		Insert-ByRank $target $tag $evs $childIndent
	}
	$evIndent = $childIndent + "`t"
	foreach ($e in @($entries)) {
		$old = $null
		foreach ($c in $evs.ChildNodes) {
			if ($c.NodeType -eq 'Element' -and $c.LocalName -eq 'Event' -and $c.GetAttribute("name") -eq $e.name -and $c.GetAttribute("callType") -eq "$($e.callType)") { $old = $c; break }
		}
		$new = New-EventNode $e.name $e.handler $e.callType
		if ($old) {
			if ($old.InnerText -ne $e.handler) {
				$evs.ReplaceChild($new, $old) | Out-Null
				[void]$changes.Add("~event $(Format-EventLabel $e.name $e.callType)")
			}
		} else {
			Insert-IntoContainer -container $evs -newNode $new -afterName $null -childIndent $evIndent
			[void]$changes.Add("+event $(Format-EventLabel $e.name $e.callType)")
		}
	}
}

# off: entries {name, callType}; no callType - every event of that name. An emptied Events goes.
function Remove-Events($target, [string]$what, $entries, $changes) {
	if ($null -eq $entries -or @($entries).Count -eq 0) { return }
	$evs = Get-ChildByTag $target 'Events'
	foreach ($e in @($entries)) {
		$hits = @()
		if ($evs) {
			foreach ($c in $evs.ChildNodes) {
				if ($c.NodeType -ne 'Element' -or $c.LocalName -ne 'Event' -or $c.GetAttribute("name") -ne $e.name) { continue }
				if ($e.callType -and $c.GetAttribute("callType") -ne "$($e.callType)") { continue }
				$hits += $c
			}
		}
		if ($hits.Count -eq 0) {
			Write-Host "[INFO] $what has no event '$(Format-EventLabel $e.name $e.callType)' - nothing to remove"
			continue
		}
		foreach ($h in $hits) {
			[void]$changes.Add("-event $(Format-EventLabel $e.name $h.GetAttribute('callType'))")
			Remove-NodeWithWs $h
		}
	}
	if ($evs -and @($evs.ChildNodes | Where-Object { $_.NodeType -eq 'Element' }).Count -eq 0) { Remove-NodeWithWs $evs }
}

function Read-SetEvents($raw, [string]$what, [bool]$needHandler) {
	$list = New-Object System.Collections.ArrayList
	if ($null -eq $raw) { return ,$list }
	foreach ($e in @($raw)) {
		if ($e -is [string]) {
			if ($needHandler) {
				Write-Host "[ERROR] set ${what}: event '$e' needs a handler - the form has no handler naming rule, give { `"event`": `"$e`", `"handler`": `"...`" }"
				exit 1
			}
			[void]$list.Add([pscustomobject]@{ name = $e; handler = $null; callType = $null })
		} elseif ($e -is [System.Management.Automation.PSCustomObject] -and $e.event) {
			if ($needHandler -and -not $e.handler) {
				Write-Host "[ERROR] set ${what}: event '$($e.event)' needs a handler"
				exit 1
			}
			[void]$list.Add([pscustomobject]@{ name = "$($e.event)"; handler = if ($e.handler) { "$($e.handler)" } else { $null }; callType = if ($e.callType) { "$($e.callType)" } else { $null } })
		} else {
			Write-Host "[ERROR] set ${what}: an event is a name or { `"event`": ..., `"handler`": ..., `"callType`": ... }"
			exit 1
		}
	}
	return ,$list
}

function Read-SetOff($raw, [string]$what) {
	$list = Read-SetEvents $raw $what $false
	return ,$list
}

# === 9d. remove and move: existing elements ===
# Order of one JSON: remove, move, set, then the additions (elements, attributes, commands,
# events). What an earlier step removed is gone for the later ones.

function Test-InSubtrees($node, $roots) {
	for ($a = $node; $a; $a = $a.ParentNode) {
		foreach ($r in $roots) { if ([object]::ReferenceEquals($a, $r)) { return $true } }
	}
	return $false
}

# An item of a ChildItems (not a companion, which is a part of its owner).
function Get-ItemNode([string]$name, [string]$what) {
	$node = Find-Target $name
	if (-not $node) { Write-Host "[ERROR] ${what}: element '$name' not found"; exit 1 }
	if ($node.ParentNode.LocalName -ne 'ChildItems') {
		Write-Host "[ERROR] ${what}: '$name' is <$($node.LocalName)>, a part of its element, not an item of a container"
		exit 1
	}
	return $node
}

# An emptied ChildItems goes with its framing; the platform writes a group without children
# (and a command bar without items) without ChildItems, an empty bar as a self-closing tag.
function Remove-EmptyChildItems($ci) {
	if (-not $ci -or -not $ci.ParentNode) { return }
	if (@($ci.ChildNodes | Where-Object { $_.NodeType -eq 'Element' }).Count -gt 0) { return }
	$owner = $ci.ParentNode
	Remove-NodeWithWs $ci
	if ($owner.NodeType -eq 'Element' -and @($owner.ChildNodes | Where-Object { $_.NodeType -eq 'Element' }).Count -eq 0 -and -not [object]::ReferenceEquals($owner, $root)) {
		foreach ($c in @($owner.ChildNodes)) { $owner.RemoveChild($c) | Out-Null }
		$owner.IsEmpty = $true
	}
}

# Code of a BSL module without comments and the content of string literals (a string goes on
# on the next line while it is not closed; "" inside a string is a quote).
function Get-BslCodeLines([string]$text) {
	$out = New-Object System.Collections.ArrayList
	$inStr = $false
	foreach ($line in ($text -split "`r?`n")) {
		$sb = New-Object System.Text.StringBuilder
		$i = 0
		$len = $line.Length
		while ($i -lt $len) {
			$c = $line[$i]
			if ($inStr) {
				if ($c -eq '"') {
					if ($i + 1 -lt $len -and $line[$i + 1] -eq '"') { $i += 2; continue }
					$inStr = $false
					[void]$sb.Append(' ')
				}
				$i++
				continue
			}
			if ($c -eq '"') { $inStr = $true; [void]$sb.Append(' '); $i++; continue }
			if ($c -eq '/' -and $i + 1 -lt $len -and $line[$i + 1] -eq '/') { break }
			[void]$sb.Append($c)
			$i++
		}
		[void]$out.Add($sb.ToString())
	}
	return ,$out
}

$removeNames = @()
$moveNames = @()
if ($def.remove) { $removeNames = @($def.remove | ForEach-Object { "$_" }) }
if ($def.move -and $def.move.elements) { $moveNames = @($def.move.elements | ForEach-Object { "$_" }) }
foreach ($mn in $moveNames) {
	if ($removeNames -contains $mn) { Write-Host "[ERROR] '$mn' is both removed and moved"; exit 1 }
}
$script:removedNames = @{}
$removedLines = New-Object System.Collections.ArrayList
$movedLines = New-Object System.Collections.ArrayList

# --- remove ---
if ($removeNames.Count -gt 0) {
	$rmSeen = @{}
	$rmNodes = @()
	foreach ($rn in $removeNames) {
		if ($rmSeen.ContainsKey($rn)) { Write-Host "[ERROR] remove: '$rn' is named twice"; exit 1 }
		$rmSeen[$rn] = $true
		$rmNodes += (Get-ItemNode $rn 'remove')
	}
	# nested ones leave with the outer one
	$rmRoots = @($rmNodes | Where-Object { $n0 = $_; -not (@($rmNodes | Where-Object { -not [object]::ReferenceEquals($_, $n0) -and (Test-InSubtrees $n0.ParentNode @($_)) }).Count -gt 0) })

	# names of everything that leaves: the elements, their descendants and companions
	$gone = @{}
	foreach ($r in $rmRoots) {
		foreach ($nn in $r.SelectNodes('descendant-or-self::*[@name]')) {
			if ($nn.LocalName -ne 'Event') { $gone[$nn.GetAttribute("name")] = $true }
		}
	}

	# --- references from outside the removed subtrees ---
	$refs = New-Object System.Collections.ArrayList
	$nameLetter = '[\p{L}\p{N}_]'
	function Get-RefWhere($e) {
		$holder = $e.ParentNode
		while ($holder -and $holder.NodeType -eq 'Element' -and -not $holder.GetAttribute("name")) { $holder = $holder.ParentNode }
		if ($holder -and $holder.NodeType -eq 'Element' -and $holder.GetAttribute("name")) { return "<$($e.LocalName)> of <$($holder.LocalName)> '$($holder.GetAttribute('name'))'" }
		return "<$($e.LocalName)>"
	}
	foreach ($e in @($xmlDoc.SelectNodes('//*'))) {
		if (Test-InSubtrees $e $rmRoots) { continue }
		$text = $null
		foreach ($cn in $e.ChildNodes) { if ($cn.NodeType -eq 'Text' -or $cn.NodeType -eq 'CDATA') { $text = "$($cn.Value)"; break } }
		if ($null -eq $text) { continue }
		$ln = $e.LocalName
		if ($ln -eq 'Item' -and $e.ParentNode.LocalName -eq 'AdditionSource' -and $gone.ContainsKey($text.Trim())) {
			[void]$refs.Add([pscustomobject]@{ Name = $text.Trim(); Where = "AdditionSource of '$($e.ParentNode.ParentNode.GetAttribute('name'))'" })
			continue
		}
		if ($ln -eq 'AssociatedTableElementId' -and $gone.ContainsKey($text.Trim())) {
			[void]$refs.Add([pscustomobject]@{ Name = $text.Trim(); Where = "command '$($e.ParentNode.GetAttribute('name'))' (AssociatedTableElementId)" })
			continue
		}
		if ($ln -eq 'CommandName') {
			foreach ($m in [regex]::Matches($text, 'Form\.Item\.([^.\s]+)\.')) {
				if ($gone.ContainsKey($m.Groups[1].Value)) { [void]$refs.Add([pscustomobject]@{ Name = $m.Groups[1].Value; Where = (Get-RefWhere $e) + " ($text)" }) }
			}
			continue
		}
		foreach ($m in [regex]::Matches($text, "(?<!$nameLetter)Items\.($nameLetter+)(?!$nameLetter)")) {
			if ($gone.ContainsKey($m.Groups[1].Value)) { [void]$refs.Add([pscustomobject]@{ Name = $m.Groups[1].Value; Where = (Get-RefWhere $e) + " ($($text.Trim()))" }) }
		}
	}
	foreach ($f in @($root.SelectNodes('f:Attributes/f:ConditionalAppearance//dcsset:selection/dcsset:item/dcsset:field', $nsMgr))) {
		if ($gone.ContainsKey($f.InnerText.Trim())) { [void]$refs.Add([pscustomobject]@{ Name = $f.InnerText.Trim(); Where = "the selection of the ConditionalAppearance of the form" }) }
	}

	# --- the form module ---
	$modulePath = $null
	$moduleText = $null
	$extPath = [System.IO.Path]::GetDirectoryName($resolvedFormPath)
	if ($extPath -and [System.IO.Path]::GetFileName($extPath) -eq "Ext") {
		$modulePath = Join-Path (Join-Path $extPath "Form") "Module.bsl"
		if (Test-Path -LiteralPath $modulePath) { $moduleText = [System.IO.File]::ReadAllText($modulePath, (New-Object System.Text.UTF8Encoding($false))) }
	}
	if ($moduleText) {
		$codeLines = Get-BslCodeLines $moduleText
		foreach ($gn in @($gone.Keys)) {
			$re = New-Object System.Text.RegularExpressions.Regex("(?<!$nameLetter)(Элементы|Items)\.$([regex]::Escape($gn))(?!$nameLetter)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
			for ($li = 0; $li -lt $codeLines.Count; $li++) {
				if ($re.IsMatch($codeLines[$li])) { [void]$refs.Add([pscustomobject]@{ Name = $gn; Where = "Module.bsl line $($li + 1)" }) }
			}
		}
	}

	$force = ($null -ne $def.PSObject.Properties['force'] -and $def.force -eq $true)
	foreach ($rf in $refs) {
		if ($force) { Write-Host "[WARN] '$($rf.Name)' is referenced by $($rf.Where) - removed anyway (force)" }
		else { Write-Host "[ERROR] '$($rf.Name)' is referenced by $($rf.Where)" }
	}
	if ($refs.Count -gt 0 -and -not $force) {
		Write-Host "[ERROR] nothing was written: remove what refers to the elements first, or give `"force`": true"
		exit 1
	}

	# --- handlers the removed subtrees had ---
	if ($moduleText) {
		foreach ($r in $rmRoots) {
			foreach ($ev in @($r.SelectNodes('descendant-or-self::*[local-name()="Events"]/*[local-name()="Event"]'))) {
				$h = $ev.InnerText.Trim()
				if (-not $h) { continue }
				if ([regex]::IsMatch($moduleText, "(?im)^\s*(Процедура|Функция|Procedure|Function)\s+$([regex]::Escape($h))\s*\(")) {
					$evOwner = $ev.ParentNode.ParentNode
					Write-Host "[INFO] handler '$h' (event $($ev.GetAttribute('name')) of '$($evOwner.GetAttribute('name'))') stays in Module.bsl - delete it when nothing else calls it"
				}
			}
		}
	}

	# --- remove ---
	$oldCIs = @()
	foreach ($r in $rmRoots) {
		$cnt = @($r.SelectNodes('descendant-or-self::*[@id]')).Count
		[void]$removedLines.Add("  - [$($r.LocalName)] $($r.GetAttribute('name')) ($cnt nodes)")
		$oldCIs += $r.ParentNode
		Remove-NodeWithWs $r
	}
	foreach ($ci in $oldCIs) { Remove-EmptyChildItems $ci }
	foreach ($gn in @($gone.Keys)) { $script:removedNames[$gn] = $true }
	$rootCI = $root.SelectSingleNode("f:ChildItems", $nsMgr)
}

# --- move ---
if ($moveNames.Count -gt 0) {
	$mv = $def.move
	$mInto = if ($mv.into) { "$($mv.into)" } else { $null }
	$mAfter = if ($mv.after) { "$($mv.after)" } else { $null }
	$mBefore = if ($mv.before) { "$($mv.before)" } else { $null }
	if (-not ($mInto -or $mAfter -or $mBefore)) { Write-Host "[ERROR] move: give into, after or before - where the elements go"; exit 1 }
	if ($mAfter -and $mBefore) { Write-Host "[ERROR] move: 'after' and 'before' exclude each other - give one anchor"; exit 1 }
	foreach ($an in @($mInto, $mAfter, $mBefore)) {
		if ($an -and $script:removedNames.ContainsKey($an)) { Write-Host "[ERROR] move: '$an' is removed by this edit"; exit 1 }
	}
	$mvSeen = @{}
	$mvNodes = @()
	foreach ($mn in $moveNames) {
		if ($mvSeen.ContainsKey($mn)) { Write-Host "[ERROR] move: '$mn' is named twice"; exit 1 }
		$mvSeen[$mn] = $true
		$mvNodes += (Get-ItemNode $mn 'move')
	}
	$mTarget = Resolve-Target $mInto $mAfter $mBefore
	foreach ($anchor in @($mAfter, $mBefore)) {
		if (-not $anchor) { continue }
		if ($mvSeen.ContainsKey($anchor)) { Write-Host "[ERROR] move: the anchor '$anchor' is one of the moved elements"; exit 1 }
		$inside = $false
		if ($mTarget.TargetCI) {
			foreach ($c in $mTarget.TargetCI.ChildNodes) { if ($c.NodeType -eq 'Element' -and $c.GetAttribute("name") -eq $anchor) { $inside = $true; break } }
		}
		if (-not $inside) { Write-Host "[ERROR] move: '$anchor' is not an item of the target container - name the container with into"; exit 1 }
	}
	foreach ($mnode in $mvNodes) {
		if (Test-InSubtrees $mTarget.Owner @($mnode)) {
			Write-Host "[ERROR] move: '$($mnode.GetAttribute('name'))' cannot go into itself or into its own descendant"
			exit 1
		}
		$perr = Get-PlacementError $mTarget $mnode.LocalName $mnode.GetAttribute("name")
		if ($perr) { Write-Host "[ERROR] move: $perr"; exit 1 }
	}

	$mCI = Ensure-TargetCI $mTarget
	$mIndent = Get-ChildIndent $mCI
	$oldCIs = @()
	$oldIndents = @()
	foreach ($mnode in $mvNodes) {
		$oldIndents += (Get-NodeIndent $mnode)
		$oldCIs += $mnode.ParentNode
		Remove-NodeWithWs $mnode
	}
	$k = 0
	$mAfterCur = $mAfter
	foreach ($mnode in $mvNodes) {
		Set-NodeIndent $mnode $oldIndents[$k] $mIndent
		Insert-IntoContainer -container $mCI -newNode $mnode -afterName $mAfterCur -childIndent $mIndent -beforeName $mBefore
		if ($mAfterCur) { $mAfterCur = $mnode.GetAttribute("name") }
		$posStr = if ($mInto) { "into $mInto" } else { "" }
		if ($mAfter) { $posStr += $(if ($posStr) { ", " } else { "" }) + "after $mAfter" }
		if ($mBefore) { $posStr += $(if ($posStr) { ", " } else { "" }) + "before $mBefore" }
		[void]$movedLines.Add("  > [$($mnode.LocalName)] $($mnode.GetAttribute('name')) ($posStr)")
		$k++
	}
	foreach ($ci in $oldCIs) { Remove-EmptyChildItems $ci }
	$rootCI = $root.SelectSingleNode("f:ChildItems", $nsMgr)
}

$changedLines = New-Object System.Collections.ArrayList
$changedCount = 0

if ($def.set -and @($def.set).Count -gt 0) {
	$plans = New-Object System.Collections.ArrayList
	$seenSet = @{}
	$probeEls = New-Object System.Collections.ArrayList
	$formDsl = [ordered]@{}
	$n = 0
	foreach ($item in @($def.set)) {
		$n++
		$isForm = ($null -ne $item.PSObject.Properties['form'] -and $item.form -eq $true)
		$plan = [pscustomobject]@{ IsForm = $isForm; Node = $null; Tag = 'Form'; Name = ''; SetTags = (New-Object System.Collections.ArrayList); RmTags = (New-Object System.Collections.ArrayList); On = $null; Off = $null; Probe = $null }
		if ($isForm) {
			$plan.Name = $formName
			$plan.Node = $root
			if ($seenSet.ContainsKey('<form>')) { Write-Host "[ERROR] set: the form appears twice - one item per element"; exit 1 }
			$seenSet['<form>'] = $true
			$props = Get-PropTags 'Form'
			$titleGiven = $false
			$userProps = [ordered]@{}
			foreach ($p in $item.PSObject.Properties) {
				$k = $p.Name; $v = $p.Value
				if ($k -eq 'form') { continue }
				if ($k -eq 'on') { $plan.On = Read-SetEvents $v 'form' $true; continue }
				if ($k -eq 'off') { $plan.Off = Read-SetOff $v 'form'; continue }
				if ($k -eq 'title') {
					if ($null -eq $v -or "$v" -eq '') { [void]$plan.RmTags.Add('Title') } else { [void]$plan.SetTags.Add('Title'); $formDsl['title'] = "$v"; $titleGiven = $true }
					continue
				}
				if ($k -eq 'properties') {
					if ($v -isnot [System.Management.Automation.PSCustomObject]) { Write-Host "[ERROR] set form: properties is an object { name: value }"; exit 1 }
					foreach ($pp in $v.PSObject.Properties) {
						$pk = $pp.Name
						if ($pk -eq 'title') { Write-Host "[ERROR] set form: give title next to properties, not inside"; exit 1 }
						$ptag = $pk.Substring(0, 1).ToUpper() + $pk.Substring(1)
						if ($props -notcontains $ptag) { Write-Host "[ERROR] set form: '$pk' is not a form property known to the order table (<$ptag>)"; exit 1 }
						if ($null -eq $pp.Value -or "$($pp.Value)" -eq '' -or (Test-SetRemoval $pp.Value)) { [void]$plan.RmTags.Add($ptag) }
						else { [void]$plan.SetTags.Add($ptag); $userProps[$pk] = $pp.Value }
					}
					continue
				}
				Write-Host "[ERROR] set form: unknown key '$k' - the form item takes title, properties, on, off"
				exit 1
			}
			if ($userProps.Count -gt 0 -or $titleGiven) {
				# a title makes form-compile add autoTitle: false; "" is its suppress marker
				if ($titleGiven -and -not $userProps.Contains('autoTitle')) { $userProps['autoTitle'] = '' }
				if ($userProps.Count -gt 0) { $formDsl['properties'] = [pscustomobject]$userProps }
			}
			if ($plan.On -and $plan.On.Count -gt 0) {
				$evMap = [ordered]@{}
				foreach ($e in $plan.On) { if (-not $evMap.Contains($e.name)) { $evMap[$e.name] = $e.handler } }
				$formDsl['events'] = [pscustomobject]$evMap
			}
			foreach ($t in $plan.SetTags) { if ($plan.RmTags -contains $t) { Write-Host "[ERROR] set form: '$t' is both set and removed"; exit 1 } }
		} else {
			$ename = "$($item.element)"
			if (-not $ename) { Write-Host "[ERROR] set item #$n names no element (and is not form: true)"; exit 1 }
			if ($seenSet.ContainsKey($ename)) { Write-Host "[ERROR] set: element '$ename' appears twice - one item per element"; exit 1 }
			$seenSet[$ename] = $true
			if ($script:removedNames.ContainsKey($ename)) { Write-Host "[ERROR] set: element '$ename' is removed by this edit"; exit 1 }
			$node = Find-Target $ename
			if (-not $node) { Write-Host "[ERROR] set: element '$ename' not found (set works on the elements the form has before this edit)"; exit 1 }
			$tag = $node.LocalName
			if (-not $script:setTypeKeys.ContainsKey($tag)) {
				Write-Host "[ERROR] set does not support <$tag> yet ('$ename')$(if (@('ContextMenu','ExtendedTooltip','AutoCommandBar','SearchStringAddition','ViewStatusAddition','SearchControlAddition') -contains $tag) { ' - companions are changed through the keys of their owner' })"
				exit 1
			}
			$plan.Node = $node; $plan.Tag = $tag; $plan.Name = $ename
			$typeKey = $script:setTypeKeys[$tag]
			$typeVal = $ename
			if ($tag -eq 'UsualGroup' -or $tag -eq 'ColumnGroup') { $typeVal = 'vertical' }
			$probe = [ordered]@{}
			$hasTitle = $false
			foreach ($p in $item.PSObject.Properties) {
				$k = $p.Name; $v = $p.Value
				if ($k -eq 'element') { continue }
				if ($k -eq 'on') { $plan.On = Read-SetEvents $v "'$ename'" $false; continue }
				if ($k -eq 'off') { $plan.Off = Read-SetOff $v "'$ename'"; continue }
				if ($k -eq 'form') { Write-Host "[ERROR] set '$ename': form belongs to an item of its own"; exit 1 }
				if ($script:setRefusedKeys.ContainsKey($k)) { Write-Host "[ERROR] set '$ename': key '$k' is not accepted - $($script:setRefusedKeys[$k])"; exit 1 }
				# group (UsualGroup) and columnGroup (ColumnGroup) are the type key and the orientation at once
				$isOrient = (($tag -eq 'UsualGroup' -and $k -eq 'group') -or ($tag -eq 'ColumnGroup' -and $k -eq 'columnGroup'))
				if (-not $isOrient -and $script:setTypeKeyNames -contains $k) {
					$keyOk = (($k -eq 'picture' -and @('Button','Popup','Page') -contains $tag) -or ($k -eq 'group' -and $tag -eq 'Page'))
					if (-not $keyOk) {
						Write-Host "[ERROR] set '$ename': key '$k' is a type key of form-compile - it would turn the element into another one"
						exit 1
					}
				}
				$ptag = Get-SetKeyTag $k $tag
				if (-not $ptag) { Write-Host "[ERROR] set '$ename': key '$k' is not a property of <$tag> (no such child in the order table)"; exit 1 }
				if (Test-SetRemoval $v) {
					if ($plan.RmTags -notcontains $ptag) { [void]$plan.RmTags.Add($ptag) }
					continue
				}
				if ($plan.SetTags -notcontains $ptag) { [void]$plan.SetTags.Add($ptag) }
				if ($isOrient) { $typeVal = "$v"; continue }
				$probe[$k] = $v
				if ($k -eq 'title') { $hasTitle = $true }
			}
			foreach ($t in $plan.SetTags) { if ($plan.RmTags -contains $t) { Write-Host "[ERROR] set '$ename': <$t> is both set and removed"; exit 1 } }
			$el = [ordered]@{}
			$el[$typeKey] = $typeVal
			$el['name'] = $ename
			if (-not $hasTitle) { $el['title'] = '' }
			foreach ($k in $probe.Keys) { $el[$k] = $probe[$k] }
			if ($plan.On -and $plan.On.Count -gt 0) {
				$onNames = @()
				foreach ($e in $plan.On) { if ($onNames -notcontains $e.name) { $onNames += $e.name } }
				$el['on'] = $onNames
				foreach ($e in $plan.On) { if ($plan.Off -and @($plan.Off | Where-Object { $_.name -eq $e.name }).Count -gt 0) { Write-Host "[ERROR] set '$ename': event '$($e.name)' is both in on and in off"; exit 1 } }
			}
			$probeObj = [pscustomobject]$el
			$ownerTag = $node.ParentNode.ParentNode.LocalName
			if (@('Button','ButtonGroup','Popup') -contains $tag -and @('AutoCommandBar','ContextMenu','CommandBar','ButtonGroup','Popup') -contains $ownerTag) {
				$bar = [ordered]@{ cmdBar = "FormEditTmpBar$n"; children = @($probeObj) }
				[void]$probeEls.Add([pscustomobject]$bar)
			} else {
				[void]$probeEls.Add($probeObj)
			}
		}
		[void]$plans.Add($plan)
	}

	# --- Compile the probes (one run for all items) ---
	$cDoc = $null
	if ($probeEls.Count -gt 0 -or $formDsl.Count -gt 0) {
		$setDsl = [ordered]@{}
		foreach ($k in $formDsl.Keys) { $setDsl[$k] = $formDsl[$k] }
		if ($probeEls.Count -gt 0) { $setDsl['elements'] = @($probeEls) }
		$cDoc = Invoke-FormCompileFragment ([pscustomobject]$setDsl)
		$cRootSet = $cDoc.DocumentElement
		$cNsSet = New-Object System.Xml.XmlNamespaceManager($cDoc.NameTable)
		$cNsSet.AddNamespace("f", $formNs)
	}

	# --- Plan: which compiled nodes go where ---
	$srcForNs = @()
	foreach ($plan in $plans) {
		$plan | Add-Member -NotePropertyName CompEl -NotePropertyValue $null
		$plan | Add-Member -NotePropertyName AutoHandlers -NotePropertyValue @{}
		if ($plan.IsForm) { $plan.CompEl = $cRootSet }
		elseif ($cDoc) { $plan.CompEl = $cRootSet.SelectSingleNode("//f:$($plan.Tag)[@name='$($plan.Name)']", $cNsSet) }
		if ($plan.CompEl) {
			foreach ($t in $plan.SetTags) {
				$sn = Get-ChildByTag $plan.CompEl $t
				if ($sn) { $srcForNs += $sn }
			}
			foreach ($ev in @($plan.CompEl.SelectNodes('f:Events/f:Event', $cNsSet))) { $plan.AutoHandlers[$ev.GetAttribute("name")] = $ev.InnerText }
		}
		if (-not $plan.IsForm -and $plan.SetTags.Count -gt 0 -and -not $plan.CompEl) {
			Write-Host "[ERROR] set '$($plan.Name)': form-compile produced no element - nothing was written"
			exit 1
		}
		foreach ($e in @($plan.On)) {
			if ($e -and -not $e.handler) {
				if (-not $plan.AutoHandlers.ContainsKey($e.name)) { Write-Host "[ERROR] set '$($plan.Name)': no handler name for event '$($e.name)' - nothing was written"; exit 1 }
				$e.handler = $plan.AutoHandlers[$e.name]
			}
		}
	}
	if ($srcForNs.Count -gt 0) { Ensure-Namespaces $cDoc $srcForNs }

	# --- Apply ---
	foreach ($plan in $plans) {
		$target = $plan.Node
		$tag = $plan.Tag
		$what = if ($plan.IsForm) { 'the form' } else { "'$($plan.Name)'" }
		$changes = New-Object System.Collections.ArrayList
		$dst = Get-ChildIndent $target
		$src = if ($plan.CompEl) { Get-ChildIndent $plan.CompEl } else { $dst }

		foreach ($t in $plan.RmTags) {
			$old = Get-ChildByTag $target $t
			if ($old) { Remove-NodeWithWs $old; [void]$changes.Add("-$t") }
			else { Write-Host "[INFO] $what has no <$t> - nothing to remove" }
		}
		foreach ($t in $plan.SetTags) {
			$sn = if ($plan.CompEl) { Get-ChildByTag $plan.CompEl $t } else { $null }
			$old = Get-ChildByTag $target $t
			if ($sn) {
				$imp = $xmlDoc.ImportNode($sn, $true)
				Set-NodeIndent $imp $src $dst
				if ($old) {
					if ($old.OuterXml -ne $imp.OuterXml) {
						$target.ReplaceChild($imp, $old) | Out-Null
						[void]$changes.Add("~$t")
					}
				} else {
					Insert-ByRank $target $tag $imp $dst
					[void]$changes.Add("+$t")
				}
			} elseif ($old) {
				# the compiler writes a property only when it differs from the default
				Remove-NodeWithWs $old
				[void]$changes.Add("-$t")
			}
		}
		Remove-Events $target $what $plan.Off $changes
		Merge-Events $target $tag $plan.On $changes

		if ($changes.Count -gt 0) {
			[void]$changedLines.Add("  ~ [$tag] $($plan.Name): $($changes -join ', ')")
			$changedCount++
		} else {
			Write-Host "[INFO] ${what}: already as requested"
		}
	}
}

# === 10. Add elements and attributes ===

$addedElems = @()
$addedAttrs = @()
$companionCount = 0

$hasElems = [bool]($def.elements -and $def.elements.Count -gt 0)
$hasAttrs = [bool]($def.attributes -and $def.attributes.Count -gt 0)

if ($hasElems -or $hasAttrs) {
	$intoName = if ($def.into) { "$($def.into)" } else { $null }
	$afterName = if ($def.after) { "$($def.after)" } else { $null }
	$beforeName = if ($def.before) { "$($def.before)" } else { $null }
	if ($hasElems -and $afterName -and $beforeName) {
		Write-Host "[ERROR] 'after' and 'before' exclude each other — give one anchor"
		exit 1
	}

	# --- Target container (nothing is changed in the form yet) ---
	$owner = $null
	$targetCI = $null
	$mode = 'plain'   # plain | cmd (command bar, context menu, popup, button group) | table
	$target = $null
	if ($hasElems) {
		$target = Resolve-Target $intoName $afterName $beforeName
		$owner = $target.Owner
		$targetCI = $target.TargetCI
		$mode = $target.Mode
	}

	# --- Attributes: refusals first, they are cheap ---
	$existingAttrs = @{}
	foreach ($ea in $root.SelectNodes("f:Attributes/f:Attribute", $nsMgr)) { $existingAttrs[$ea.GetAttribute("name")] = $ea }
	$dslAttrNames = @{}
	if ($hasAttrs) {
		# Уникальность имён реквизитов: внутри JSON-определения (+ колонки в пределах реквизита) и
		# против уже существующих реквизитов формы.
		foreach ($attr in $def.attributes) {
			Assert-EditUnique -name "$($attr.name)" -seen $dslAttrNames -ctx 'attribute name'
			if ($attr.columns) {
				$dslColNames = @{}
				foreach ($col in $attr.columns) { Assert-EditUnique -name "$($col.name)" -seen $dslColNames -ctx "column name of '$($attr.name)'" }
			}
			if ($existingAttrs.ContainsKey("$($attr.name)")) {
				Write-Host "[ERROR] Attribute '$($attr.name)' already exists in form — attribute names must be unique"
				exit 1
			}
			if ((Test-IsDynamicListType "$($attr.type)") -and -not (Test-DynamicListSource $attr.settings)) {
				Write-Host "[ERROR] Attribute '$($attr.name)': DynamicList requires settings.mainTable or settings.query — otherwise the form fails to open"
				exit 1
			}
		}
	}

	# --- Temporary DSL ---
	$dsl = New-Object PSObject
	$stubNames = @{}
	if ($hasElems) {
		$dslElements = @($def.elements)
		if ($mode -eq 'cmd') {
			# the compiler applies its command-bar rules (CommandBarButton, ...) to the children of a cmdBar
			$bar = New-Object PSObject
			$bar | Add-Member -NotePropertyName "cmdBar" -NotePropertyValue "FormEditTmpBar"
			$bar | Add-Member -NotePropertyName "children" -NotePropertyValue $dslElements
			$dslElements = @($bar)
		}
		$dsl | Add-Member -NotePropertyName "elements" -NotePropertyValue $dslElements
	}
	$dslAttributes = @()
	$dslAttrTypes = @{}
	if ($hasAttrs) {
		foreach ($attr in $def.attributes) {
			$dslAttrTypes["$($attr.name)"] = if ($attr.type) { "$($attr.type)" } else { "(no type)" }
			# form-compile infers the main attribute (and its SavedData) from a single object-like
			# attribute; the form being edited already has its own.
			if ($null -eq $attr.PSObject.Properties["main"]) { $attr | Add-Member -NotePropertyName "main" -NotePropertyValue $false }
			$dslAttributes += $attr
		}
	}
	if ($hasElems) {
		# A table bound to a DynamicList attribute of the form gets the list-table defaults of the
		# compiler only when it sees that attribute: a stub stands in for it and is discarded.
		$tablePaths = @{}
		Get-TablePaths $def.elements $tablePaths
		foreach ($tp in @($tablePaths.Keys)) {
			if ($dslAttrNames.ContainsKey($tp) -or -not $existingAttrs.ContainsKey($tp)) { continue }
			$typeNode = $existingAttrs[$tp].SelectSingleNode("f:Type/v8:Type", $nsMgr)
			if (-not $typeNode -or $typeNode.InnerText.Trim() -ne "cfg:DynamicList") { continue }
			$settings = New-Object PSObject
			$mt = $existingAttrs[$tp].SelectSingleNode("f:Settings/f:MainTable", $nsMgr)
			if ($mt -and $mt.InnerText.Trim()) { $settings | Add-Member -NotePropertyName "mainTable" -NotePropertyValue $mt.InnerText.Trim() }
			else { $settings | Add-Member -NotePropertyName "query" -NotePropertyValue "stub" }
			$stub = New-Object PSObject
			$stub | Add-Member -NotePropertyName "name" -NotePropertyValue $tp
			$stub | Add-Member -NotePropertyName "type" -NotePropertyValue "DynamicList"
			$stub | Add-Member -NotePropertyName "main" -NotePropertyValue $false
			$stub | Add-Member -NotePropertyName "settings" -NotePropertyValue $settings
			$dslAttributes += $stub
			$stubNames[$tp] = $true
		}
	}
	if ($dslAttributes.Count -gt 0) { $dsl | Add-Member -NotePropertyName "attributes" -NotePropertyValue $dslAttributes }

	$compiled = Invoke-FormCompileFragment $dsl
	$cRoot = $compiled.DocumentElement
	$cNs = New-Object System.Xml.XmlNamespaceManager($compiled.NameTable)
	$cNs.AddNamespace("f", $formNs)

	# --- Compiled elements ---
	$srcElems = @()
	$srcElemIndent = "`t`t"
	if ($hasElems) {
		$srcCI = $cRoot.SelectSingleNode("f:ChildItems", $cNs)
		if ($srcCI -and $mode -eq 'cmd') {
			$srcBar = $srcCI.SelectSingleNode("f:CommandBar", $cNs)
			$srcCI = if ($srcBar) { $srcBar.SelectSingleNode("f:ChildItems", $cNs) } else { $null }
		}
		if ($srcCI) {
			foreach ($child in $srcCI.ChildNodes) {
				if ($child.NodeType -eq 'Element') { $srcElems += $child }
			}
			foreach ($child in $srcCI.ChildNodes) {
				if ($child.NodeType -eq 'Whitespace' -and $child.Value -match '^\r?\n(\t+)') { $srcElemIndent = $Matches[1]; break }
			}
		}

		foreach ($n in $srcElems) {
			$perr = Get-PlacementError $target $n.LocalName $n.GetAttribute("name")
			if ($perr) { Write-Host "[ERROR] $perr"; exit 1 }
		}

		# Имена элементов уникальны (требование 1С; дубль = битый XML, форма не откроется): против всех
		# уже существующих узлов формы, компаньоны включены. Внутри определения следит form-compile.
		$existingNames = @{}
		foreach ($nn in @(Get-NamedNodes)) { $existingNames[$nn.GetAttribute("name")] = $nn }
		foreach ($n in $srcElems) {
			foreach ($nn in $n.SelectNodes('descendant-or-self::*[@name]')) {
				if ($nn.LocalName -eq 'Event') { continue }
				$nm = $nn.GetAttribute("name")
				if ($existingNames.ContainsKey($nm)) {
					Write-Host "[ERROR] Element '$nm' already exists in form (id=$($existingNames[$nm].GetAttribute('id'))) — element names must be unique"
					exit 1
				}
			}
		}
	}

	# --- Compiled attributes ---
	$srcAttrs = @()
	foreach ($a in $cRoot.SelectNodes("f:Attributes/f:Attribute", $cNs)) {
		if (-not $stubNames.ContainsKey($a.GetAttribute("name"))) { $srcAttrs += $a }
	}

	Ensure-Namespaces $compiled ($srcElems + $srcAttrs)

	# --- Elements: target container, ids, indent, insertion ---
	if ($hasElems -and $srcElems.Count -gt 0) {
		if (-not $targetCI) { $targetCI = Ensure-TargetCI $target }
		$childIndent = Get-ChildIndent $targetCI

		$importedNodes = @()
		foreach ($n in $srcElems) {
			$node = $xmlDoc.ImportNode($n, $true)
			Set-NodeIndent $node $srcElemIndent $childIndent
			Set-ElementIds $node
			$importedNodes += $node
		}

		# Report: what was added, from the compiled nodes
		$companionTags = @('ExtendedTooltip','ContextMenu','SearchStringAddition','ViewStatusAddition','SearchControlAddition','AutoCommandBar')
		foreach ($node in $importedNodes) {
			$dp = $node.SelectSingleNode("f:DataPath", $nsMgr)
			$pathStr = if ($dp) { " -> $($dp.InnerText)" } else { "" }
			$evNames = @($node.SelectNodes("f:Events/f:Event", $nsMgr) | ForEach-Object { $_.GetAttribute("name") })
			$evtStr = if ($evNames.Count -gt 0) { " {$($evNames -join ', ')}" } else { "" }
			$addedElems += "  + [$($node.LocalName)] $($node.GetAttribute('name'))$pathStr$evtStr"
			$companionCount += @($node.SelectNodes('descendant-or-self::*[@id]') | Where-Object { $companionTags -contains $_.LocalName }).Count
		}

		# Insert each imported node
		foreach ($node in $importedNodes) {
			Insert-IntoContainer -container $targetCI -newNode $node -afterName $afterName -childIndent $childIndent -beforeName $beforeName
			# Only use afterName for the first insertion; subsequent ones go after the previous
			if ($afterName) { $afterName = $node.GetAttribute("name") }
		}
	}

	# --- Attributes ---
	if ($srcAttrs.Count -gt 0) {
		$attrsSection = Ensure-AttrsSection

		# Detect indent for attribute children
		$attrChildIndent = Get-ChildIndent $attrsSection
		if (-not $attrChildIndent -or $attrChildIndent -eq "") { $attrChildIndent = "`t`t" }

		foreach ($a in $srcAttrs) {
			$node = $xmlDoc.ImportNode($a, $true)
			Set-NodeIndent $node "`t`t" $attrChildIndent
			$attrId = New-AttrId
			$node.SetAttribute("id", [string]$attrId)
			# Column ids are per attribute, from 1 (as the platform writes them), direct columns
			# and those inside AdditionalColumns alike, in document order
			$colId = 1
			foreach ($col in $node.SelectNodes("f:Columns//f:Column", $nsMgr)) { $col.SetAttribute("id", [string]$colId); $colId++ }
			$typeStr = $dslAttrTypes[$node.GetAttribute("name")]
			$addedAttrs += "  + $($node.GetAttribute('name')): $typeStr (id=$attrId)"
			# the form's ConditionalAppearance is the last child of Attributes: attributes go before it
			$caExisting = Get-ChildByTag $attrsSection 'ConditionalAppearance'
			if ($caExisting) {
				$attrsSection.InsertBefore($node, $caExisting) | Out-Null
				$attrsSection.InsertBefore($xmlDoc.CreateWhitespace("`r`n$attrChildIndent"), $caExisting) | Out-Null
			} else {
				Insert-IntoContainer -container $attrsSection -newNode $node -afterName $null -childIndent $attrChildIndent
			}
		}
	}
}

# === 11. Conditional appearance of the form ===
# form-compile writes it as the last child of <Attributes> (the grammar of a dynamic list's
# conditionalAppearance, form-dsl-spec.md 7c); the compiled items are appended to the form's own
# block, which is created when there is none. A selection field that is no element of the form is
# a warning: the compiler does not check it either.

$addedCA = @()

if ($def.conditionalAppearance -and @($def.conditionalAppearance).Count -gt 0) {
	$caDsl = [pscustomobject]@{ conditionalAppearance = @($def.conditionalAppearance) }
	$caDoc = Invoke-FormCompileFragment $caDsl
	$caNs = New-Object System.Xml.XmlNamespaceManager($caDoc.NameTable)
	$caNs.AddNamespace("f", $formNs)
	$caNs.AddNamespace("dcsset", "http://v8.1c.ru/8.1/data-composition-system/settings")
	$srcCA = $caDoc.DocumentElement.SelectSingleNode("f:Attributes/f:ConditionalAppearance", $caNs)
	$srcItems = @()
	if ($srcCA) { $srcItems = @($srcCA.SelectNodes("dcsset:item", $caNs)) }
	if ($srcItems.Count -eq 0) {
		Write-Host "[ERROR] conditionalAppearance: form-compile produced no items - nothing was written"
		exit 1
	}
	Ensure-Namespaces $caDoc $srcItems

	# selection fields: elements the form has (after this edit) plus the new ones
	$known = @{}
	foreach ($nn in @(Get-NamedNodes)) { $known[$nn.GetAttribute("name")] = $true }
	foreach ($f in $srcItems) {
		foreach ($fld in @($f.SelectNodes("dcsset:selection/dcsset:item/dcsset:field", $caNs))) {
			$fname = $fld.InnerText.Trim()
			if (-not $known.ContainsKey($fname)) {
				Write-Host "[WARN] conditionalAppearance: selection field '$fname' is not an element of the form"
			}
		}
	}

	$attrsSectionCA = Ensure-AttrsSection
	$caNode = Get-ChildByTag $attrsSectionCA 'ConditionalAppearance'
	if (-not $caNode) {
		$caNode = $xmlDoc.CreateElement("ConditionalAppearance", $formNs)
		Insert-IntoContainer -container $attrsSectionCA -newNode $caNode -afterName $null -childIndent (Get-ChildIndent $attrsSectionCA)
	}
	$caSrcIndent = Get-ChildIndent $srcCA
	$caDstIndent = (Get-ChildIndent $attrsSectionCA) + "`t"
	# after the last item; the block's own viewMode / userSettingID (if any) stay behind it
	$lastItem = $null
	foreach ($c in $caNode.ChildNodes) { if ($c.NodeType -eq 'Element' -and $c.LocalName -eq 'item') { $lastItem = $c } }
	foreach ($si in $srcItems) {
		$imp = $xmlDoc.ImportNode($si, $true)
		Set-NodeIndent $imp $caSrcIndent $caDstIndent
		if ($lastItem) {
			$ref = $lastItem.NextSibling
			$caNode.InsertBefore($xmlDoc.CreateWhitespace("`r`n$caDstIndent"), $ref) | Out-Null
			$caNode.InsertBefore($imp, $ref) | Out-Null
		} else {
			Insert-IntoContainer -container $caNode -newNode $imp -afterName $null -childIndent $caDstIndent
		}
		$lastItem = $imp
		$fields = @($imp.SelectNodes("dcsset:selection/dcsset:item/dcsset:field", $nsMgr) | ForEach-Object { $_.InnerText.Trim() })
		$fieldStr = if ($fields.Count -gt 0) { $fields -join ', ' } else { "(all)" }
		$addedCA += "  + selection: $fieldStr"
	}
}

# === 12. Add commands ===

$addedCmds = @()

if ($def.commands -and $def.commands.Count -gt 0) {
	$cmdsSection = $root.SelectSingleNode("f:Commands", $nsMgr)
	if (-not $cmdsSection) {
		# Create Commands section — insert after Parameters or Attributes
		$cmdsSection = $xmlDoc.CreateElement("Commands", $formNs)
		$insertAfter = $root.SelectSingleNode("f:Parameters", $nsMgr)
		if (-not $insertAfter) { $insertAfter = $root.SelectSingleNode("f:Attributes", $nsMgr) }
		if (-not $insertAfter) { $insertAfter = $rootCI }
		if ($insertAfter) {
			$refNode = $insertAfter.NextSibling
			$ws = $xmlDoc.CreateWhitespace("`r`n`t")
			$root.InsertBefore($ws, $refNode) | Out-Null
			$root.InsertBefore($cmdsSection, $refNode) | Out-Null
		} else {
			$root.AppendChild($xmlDoc.CreateWhitespace("`r`n`t")) | Out-Null
			$root.AppendChild($cmdsSection) | Out-Null
		}
	}

	$cmdChildIndent = Get-ChildIndent $cmdsSection
	if (-not $cmdChildIndent -or $cmdChildIndent -eq "") { $cmdChildIndent = "`t`t" }

	# Уникальность имён команд: внутри JSON-определения и против существующих команд формы.
	$dslCmdNames = @{}
	foreach ($cmd in $def.commands) {
		Assert-EditUnique -name "$($cmd.name)" -seen $dslCmdNames -ctx 'command name'
		$existingCmd = $cmdsSection.SelectSingleNode("f:Command[@name='$($cmd.name)']", $nsMgr)
		if ($existingCmd) {
			Write-Host "[ERROR] Command '$($cmd.name)' already exists in form — command names must be unique"
			exit 1
		}
	}

	# Generate command fragments
	$script:xml = New-Object System.Text.StringBuilder 1024
	X "<_F $allNsDecl>"
	foreach ($cmd in $def.commands) {
		$cmdId = New-CmdId
		$cmdName = "$($cmd.name)"
		X "$cmdChildIndent<Command name=`"$cmdName`" id=`"$cmdId`">"
		$inner = "$cmdChildIndent`t"

		if ($cmd.title) { Emit-MLText -tag "Title" -text "$($cmd.title)" -indent $inner }

		# Platform order: Title, Shortcut, Picture, Action, Representation. A
		# Picture after Action was refused with an XDTO exception on load.
		if ($cmd.shortcut) { X "$inner<Shortcut>$($cmd.shortcut)</Shortcut>" }
		if ($cmd.picture) {
			X "$inner<Picture>"
			X "$inner`t<xr:Ref>$($cmd.picture)</xr:Ref>"
			X "$inner`t<xr:LoadTransparent>true</xr:LoadTransparent>"
			X "$inner</Picture>"
		}

		# Support single action with optional callType, or multiple actions
		if ($cmd.actions) {
			# Multiple actions: [{ "callType": "Before", "handler": "..." }, ...]
			foreach ($act in $cmd.actions) {
				$actHandler = "$($act.handler)"
				$callTypeAttr = if ($act.callType) { " callType=`"$($act.callType)`"" } else { "" }
				X "$inner<Action$callTypeAttr>$actHandler</Action>"
			}
		} elseif ($cmd.action) {
			$callTypeAttr = if ($cmd.callType) { " callType=`"$($cmd.callType)`"" } else { "" }
			X "$inner<Action$callTypeAttr>$($cmd.action)</Action>"
		}

		if ($cmd.representation) {
			# A command spells picture-and-text TextPicture; PictureAndText is the button's
			# spelling and is not a value of the command property.
			$cmdRepr = if ("$($cmd.representation)" -eq 'PictureAndText') { 'TextPicture' } else { "$($cmd.representation)" }
			X "$inner<Representation>$cmdRepr</Representation>"
		}

		X "$cmdChildIndent</Command>"
		$actionStr = if ($cmd.action) { " -> $($cmd.action)" } elseif ($cmd.actions) { " -> $($cmd.actions.Count) action(s)" } else { "" }
		$addedCmds += "  + ${cmdName}${actionStr} (id=$cmdId)"
	}
	X "</_F>"

	$fragDoc = Parse-Fragment $script:xml.ToString()
	$importedCmds = Import-ElementNodes $fragDoc

	foreach ($node in $importedCmds) {
		Insert-IntoContainer -container $cmdsSection -newNode $node -afterName $null -childIndent $cmdChildIndent
	}
}

# === 12b. Add form-level events ===

$addedFormEvents = @()

if ($def.formEvents -and $def.formEvents.Count -gt 0) {
	$eventsSection = $root.SelectSingleNode("f:Events", $nsMgr)
	if (-not $eventsSection) {
		# Create Events section — insert after AutoCommandBar or at the beginning
		$eventsSection = $xmlDoc.CreateElement("Events", $formNs)
		$insertAfter = $root.SelectSingleNode("f:AutoCommandBar", $nsMgr)
		if ($insertAfter) {
			# Insert after AutoCommandBar (Events come after AutoCommandBar in 1C)
			$ws1 = $xmlDoc.CreateWhitespace("`r`n`t")
			$ws2 = $xmlDoc.CreateWhitespace("`r`n`t")
			if ($insertAfter.NextSibling) {
				$root.InsertBefore($ws1, $insertAfter.NextSibling) | Out-Null
				$root.InsertBefore($eventsSection, $ws1) | Out-Null
				$root.InsertBefore($ws2, $eventsSection) | Out-Null
			} else {
				$root.AppendChild($xmlDoc.CreateWhitespace("`r`n`t")) | Out-Null
				$root.AppendChild($eventsSection) | Out-Null
				$root.AppendChild($xmlDoc.CreateWhitespace("`r`n")) | Out-Null
			}
		} else {
			$firstChild = $root.FirstChild
			if ($firstChild) {
				$ws = $xmlDoc.CreateWhitespace("`r`n`t")
				$root.InsertBefore($eventsSection, $firstChild) | Out-Null
				$root.InsertBefore($ws, $eventsSection) | Out-Null
			} else {
				$root.AppendChild($xmlDoc.CreateWhitespace("`r`n`t")) | Out-Null
				$root.AppendChild($eventsSection) | Out-Null
			}
		}
	}

	$evtChildIndent = Get-ChildIndent $eventsSection
	if (-not $evtChildIndent -or $evtChildIndent -eq "") { $evtChildIndent = "`t`t" }

	# Generate event fragments
	$script:xml = New-Object System.Text.StringBuilder 512
	X "<_F $allNsDecl>"
	foreach ($fe in $def.formEvents) {
		$feName = "$($fe.name)"
		$feHandler = "$($fe.handler)"
		$callTypeAttr = if ($fe.callType) { " callType=`"$($fe.callType)`"" } else { "" }
		X "$evtChildIndent<Event name=`"$feName`"$callTypeAttr>$feHandler</Event>"
		$ctStr = if ($fe.callType) { "[$($fe.callType)]" } else { "" }
		$addedFormEvents += "  + $feName${ctStr} -> $feHandler"
	}
	X "</_F>"

	$fragDoc = Parse-Fragment $script:xml.ToString()
	$importedEvents = Import-ElementNodes $fragDoc

	foreach ($node in $importedEvents) {
		Insert-IntoContainer -container $eventsSection -newNode $node -afterName $null -childIndent $evtChildIndent
	}
}

# === 12c. Add element-level events ===

$addedElemEvents = @()

if ($def.elementEvents -and $def.elementEvents.Count -gt 0) {
	if (-not $rootCI) {
		$rootCI = $root.SelectSingleNode("f:ChildItems", $nsMgr)
	}

	foreach ($ee in $def.elementEvents) {
		$targetName = "$($ee.element)"
		$targetEl = Find-Element $rootCI $targetName
		if (-not $targetEl) {
			Write-Host "[WARN] Element '$targetName' not found — skipping elementEvent"
			continue
		}

		# Find or create Events element within the target
		$targetEvents = $targetEl.SelectSingleNode("f:Events", $nsMgr)
		if (-not $targetEvents) {
			$targetEvents = $xmlDoc.CreateElement("Events", $formNs)
			# Insert Events before closing tag (after last property, before ChildItems if any)
			$ciNode = $targetEl.SelectSingleNode("f:ChildItems", $nsMgr)
			if ($ciNode) {
				$ws = $xmlDoc.CreateWhitespace("`r`n" + (Get-ChildIndent $targetEl))
				$targetEl.InsertBefore($ws, $ciNode) | Out-Null
				$targetEl.InsertBefore($targetEvents, $ciNode) | Out-Null
			} else {
				$trailing = $targetEl.LastChild
				if ($trailing -and ($trailing.NodeType -eq 'Whitespace' -or $trailing.NodeType -eq 'SignificantWhitespace')) {
					$ws = $xmlDoc.CreateWhitespace("`r`n" + (Get-ChildIndent $targetEl))
					$targetEl.InsertBefore($ws, $trailing) | Out-Null
					$targetEl.InsertBefore($targetEvents, $trailing) | Out-Null
				} else {
					$targetEl.AppendChild($xmlDoc.CreateWhitespace("`r`n" + (Get-ChildIndent $targetEl))) | Out-Null
					$targetEl.AppendChild($targetEvents) | Out-Null
				}
			}
		}

		$eeChildIndent = Get-ChildIndent $targetEvents
		if (-not $eeChildIndent -or $eeChildIndent -eq "") {
			$parentIndent = Get-ChildIndent $targetEl
			$eeChildIndent = "$parentIndent`t"
		}

		# Create Event element
		$eeName = "$($ee.name)"
		$eeHandler = "$($ee.handler)"
		$callTypeAttr = if ($ee.callType) { " callType=`"$($ee.callType)`"" } else { "" }

		$script:xml = New-Object System.Text.StringBuilder 256
		X "<_F $allNsDecl>"
		X "$eeChildIndent<Event name=`"$eeName`"$callTypeAttr>$eeHandler</Event>"
		X "</_F>"

		$fragDoc = Parse-Fragment $script:xml.ToString()
		$importedEE = Import-ElementNodes $fragDoc

		foreach ($node in $importedEE) {
			Insert-IntoContainer -container $targetEvents -newNode $node -afterName $null -childIndent $eeChildIndent
		}

		$ctStr = if ($ee.callType) { "[$($ee.callType)]" } else { "" }
		$addedElemEvents += "  + $targetName.$eeName${ctStr} -> $eeHandler"
	}
}

# === 13. Save ===

$content = $xmlDoc.OuterXml
# Ensure encoding declaration is uppercase UTF-8
$content = $content -replace '^<\?xml version="1.0" encoding="utf-8"\?>', '<?xml version="1.0" encoding="UTF-8"?>'
# Match Configurator's compact empty tags without altering literal XML text.
# PreserveWhitespace alone does not preserve the self-closing tag spelling.
$content = [regex]::Replace($content, '(?s)<!\[CDATA\[.*?\]\]>|<!--.*?-->|<\?.*?\?>|(?<=\S) />', { param($m) if ($m.Value -eq ' />') { '/>' } else { $m.Value } })
$targetEol = if ([System.IO.File]::ReadAllText($resolvedFormPath) -match "`r`n") { "`r`n" } else { "`n" }
$content = ($content -replace "`r`n", "`n") -replace "`n", $targetEol

$enc = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($resolvedFormPath, $content, $enc)

# === 14. Summary ===

if ($script:isExtension) {
	Write-Host "[EXTENSION] BaseForm detected — IDs start at 1000000+"
	Write-Host ""
}

if ($removedLines.Count -gt 0) {
	Write-Host "Removed:"
	foreach ($line in $removedLines) { Write-Host $line }
	Write-Host ""
}

if ($movedLines.Count -gt 0) {
	Write-Host "Moved:"
	foreach ($line in $movedLines) { Write-Host $line }
	Write-Host ""
}

if ($changedLines.Count -gt 0) {
	Write-Host "Changed:"
	foreach ($line in $changedLines) { Write-Host $line }
	Write-Host ""
}

if ($addedFormEvents.Count -gt 0) {
	Write-Host "Added form events:"
	foreach ($line in $addedFormEvents) { Write-Host $line }
	Write-Host ""
}

if ($addedElemEvents.Count -gt 0) {
	Write-Host "Added element events:"
	foreach ($line in $addedElemEvents) { Write-Host $line }
	Write-Host ""
}

if ($addedElems.Count -gt 0) {
	$posStr = ""
	if ($def.into) { $posStr += "into $($def.into)" }
	if ($def.after) { if ($posStr) { $posStr += ", " }; $posStr += "after $($def.after)" }
	if ($def.before) { if ($posStr) { $posStr += ", " }; $posStr += "before $($def.before)" }
	if ($posStr) { $posStr = " ($posStr)" }
	Write-Host "Added elements${posStr}:"
	foreach ($line in $addedElems) { Write-Host $line }
	Write-Host ""
}

if ($addedAttrs.Count -gt 0) {
	Write-Host "Added attributes:"
	foreach ($line in $addedAttrs) { Write-Host $line }
	Write-Host ""
}

if ($addedCA.Count -gt 0) {
	Write-Host "Added conditional appearance:"
	foreach ($line in $addedCA) { Write-Host $line }
	Write-Host ""
}

if ($addedCmds.Count -gt 0) {
	Write-Host "Added commands:"
	foreach ($line in $addedCmds) { Write-Host $line }
	Write-Host ""
}

Write-Host "---"
$totalParts = @()
if ($removedLines.Count -gt 0) { $totalParts += "$($removedLines.Count) removed element(s)" }
if ($movedLines.Count -gt 0) { $totalParts += "$($movedLines.Count) moved element(s)" }
if ($changedCount -gt 0) { $totalParts += "$changedCount changed element(s)" }
if ($addedFormEvents.Count -gt 0) { $totalParts += "$($addedFormEvents.Count) form event(s)" }
if ($addedElemEvents.Count -gt 0) { $totalParts += "$($addedElemEvents.Count) element event(s)" }
if ($addedElems.Count -gt 0) {
	$compStr = if ($companionCount -gt 0) { " (+$companionCount companions)" } else { "" }
	$totalParts += "$($addedElems.Count) element(s)$compStr"
}
if ($addedAttrs.Count -gt 0) { $totalParts += "$($addedAttrs.Count) attribute(s)" }
if ($addedCmds.Count -gt 0) { $totalParts += "$($addedCmds.Count) command(s)" }
if ($addedCA.Count -gt 0) { $totalParts += "$($addedCA.Count) conditional appearance item(s)" }
Write-Host "Total: $($totalParts -join ', ')"
Write-Host "Run /form-validate to verify."
