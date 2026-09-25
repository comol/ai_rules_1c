# form-validate v1.10 — Validate 1C managed form
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills
# Local: DynamicList attributes without MainTable and QueryText are an error —
# the form loads but fails to open.
# Local (v1.10): the root version must equal Configuration.xml (1); a type spelled
# with an export folder name (cfg:Catalogs.X) is an error (12); the main attribute
# of a default object / record form belongs to the owner and a zero-length
# Description / Code is not bound (12b); Module.bsl is checked against the
# handlers Form.xml references (13) and for form-data conversion outside
# &НаСервере (14).
param(
	[Parameter(Mandatory)]
	[Alias('Path')]
	[string]$FormPath,

	[switch]$Detailed,

	[int]$MaxErrors = 30
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Resolve path ---
# A: Directory → Ext/Form.xml
if (Test-Path $FormPath -PathType Container) {
	$FormPath = Join-Path (Join-Path $FormPath "Ext") "Form.xml"
}
# B1: Missing Ext/ (e.g. Forms/Форма/Form.xml → Forms/Форма/Ext/Form.xml)
if (-not (Test-Path $FormPath)) {
	$fn = [System.IO.Path]::GetFileName($FormPath)
	if ($fn -eq "Form.xml") {
		$c = Join-Path (Join-Path (Split-Path $FormPath) "Ext") $fn
		if (Test-Path $c) { $FormPath = $c }
	}
}
# B2: Descriptor (Forms/Форма.xml → Forms/Форма/Ext/Form.xml)
if (-not (Test-Path $FormPath) -and $FormPath.EndsWith(".xml")) {
	$stem = [System.IO.Path]::GetFileNameWithoutExtension($FormPath)
	$dir = Split-Path $FormPath
	$c = Join-Path (Join-Path (Join-Path $dir $stem) "Ext") "Form.xml"
	if (Test-Path $c) { $FormPath = $c }
}

# --- Load XML ---

if (-not (Test-Path $FormPath)) {
	Write-Error "File not found: $FormPath"
	exit 1
}

$xmlDoc = New-Object System.Xml.XmlDocument
$xmlDoc.PreserveWhitespace = $false
try {
	$xmlDoc.Load((Resolve-Path $FormPath).Path)
} catch {
	Write-Host "[ERROR] XML parse error: $($_.Exception.Message)"
	Write-Host ""
	Write-Host "---"
	Write-Host "Errors: 1, Warnings: 0"
	exit 1
}

$nsMgr = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
$nsMgr.AddNamespace("f", "http://v8.1c.ru/8.3/xcf/logform")
$nsMgr.AddNamespace("v8", "http://v8.1c.ru/8.1/data/core")

$root = $xmlDoc.DocumentElement

# --- Detect context: config vs EPF/ERF ---
# Walk up from FormPath looking for Configuration.xml → config context
# No Configuration.xml → external data processor / report (EPF/ERF)
$script:isConfigContext = $false
$script:configVersion = ""
$walkDir = Split-Path (Resolve-Path $FormPath) -Parent
for ($i = 0; $i -lt 15; $i++) {
	if (-not $walkDir -or $walkDir -eq (Split-Path $walkDir)) { break }
	if (Test-Path (Join-Path $walkDir "Configuration.xml")) {
		$script:isConfigContext = $true
		# Local: the format version of the configuration (Check 1).
		try {
			$cfgReader = New-Object System.IO.StreamReader((Join-Path $walkDir "Configuration.xml"), [System.Text.Encoding]::UTF8)
			$cfgBuffer = New-Object char[] 2000
			$cfgRead = $cfgReader.Read($cfgBuffer, 0, 2000)
			$cfgReader.Close()
			$cfgHead = New-Object string($cfgBuffer, 0, $cfgRead)
			if ($cfgHead -match '<MetaDataObject[^>]+version="(\d+\.\d+)"') { $script:configVersion = $Matches[1] }
		} catch {}
		break
	}
	$walkDir = Split-Path $walkDir
}

# --- Counters ---

$errors = 0
$warnings = 0
$stopped = $false
$script:okCount = 0

function Report-OK {
	param([string]$msg)
	$script:okCount++
	if ($Detailed) { Write-Host "[OK]    $msg" }
}

function Report-Error {
	param([string]$msg)
	$script:errors++
	Write-Host "[ERROR] $msg"
	if ($script:errors -ge $MaxErrors) {
		$script:stopped = $true
	}
}

function Report-Warn {
	param([string]$msg)
	$script:warnings++
	Write-Host "[WARN]  $msg"
}

# --- Form name from path ---

$formName = [System.IO.Path]::GetFileNameWithoutExtension($FormPath)
$parentDir = [System.IO.Path]::GetDirectoryName($FormPath)
if ($parentDir) {
	$extDir = [System.IO.Path]::GetFileName($parentDir)
	if ($extDir -eq "Ext") {
		$formDir = [System.IO.Path]::GetDirectoryName($parentDir)
		if ($formDir) { $formName = [System.IO.Path]::GetFileName($formDir) }
	}
}

if ($Detailed) {
	Write-Host "=== Validation: $formName ==="
	Write-Host ""
}

# Early BaseForm detection (used in Check 5 to skip base element DataPath validation)
$hasBaseForm = ($root.SelectSingleNode("f:BaseForm", $nsMgr) -ne $null)

# --- Check 1: Root element and version ---

if ($root.LocalName -ne "Form") {
	Report-Error "Root element is '$($root.LocalName)', expected 'Form'"
} else {
	$version = $root.GetAttribute("version")
	if ($version -and $script:configVersion -and $version -ne $script:configVersion) {
		Report-Error "Form version='$version' differs from Configuration.xml ($($script:configVersion)) — the Configurator refuses to load a dump with mixed format versions"
	} elseif ($version -eq "2.17" -or $version -eq "2.20") {
		Report-OK "Root element: Form version=$version"
	} elseif ($version) {
		Report-Warn "Form version='$version' (expected 2.17 or 2.20)"
	} else {
		Report-Warn "Form version attribute missing"
	}
}

# --- Check 2: AutoCommandBar ---

if (-not $stopped) {
	$acb = $root.SelectSingleNode("f:AutoCommandBar", $nsMgr)
	if ($acb) {
		$acbName = $acb.GetAttribute("name")
		$acbId = $acb.GetAttribute("id")
		if ($acbId -eq "-1") {
			Report-OK "AutoCommandBar: name='$acbName', id=$acbId"
		} else {
			Report-Error "AutoCommandBar id='$acbId', expected '-1'"
		}
	} else {
		Report-Error "AutoCommandBar element missing"
	}
}

# --- Collect all elements with IDs ---

$elementIds = @{}    # id -> name (element ID pool)
$elementNames = @{}  # name -> id (имена элементов уникальны в пределах формы)
$allElements = @() # @{Name; Tag; Id; ParentName; Node}

function Collect-Elements {
	param($node, [string]$parentName)

	foreach ($child in $node.ChildNodes) {
		if ($child.NodeType -ne 'Element') { continue }

		$name = $child.GetAttribute("name")
		$id = $child.GetAttribute("id")

		if ($name -and $id) {
			$tag = $child.LocalName

			$script:allElements += @{
				Name       = $name
				Tag        = $tag
				Id         = $id
				ParentName = $parentName
				Node       = $child
			}

			# Track element IDs (skip AutoCommandBar which has -1)
			if ($id -ne "-1") {
				if ($elementIds.ContainsKey($id)) {
					Report-Error "Duplicate element id=${id}: '$name' and '$($elementIds[$id])'"
				} else {
					$elementIds[$id] = $name
				}

				# Имена элементов уникальны (требование 1С)
				if ($elementNames.ContainsKey($name)) {
					Report-Error "Duplicate element name '$name': id=${id} and id=$($elementNames[$name])"
				} else {
					$elementNames[$name] = $id
				}
			}

			# Recurse into ChildItems
			$childItems = $child.SelectSingleNode("f:ChildItems", $nsMgr)
			if ($childItems) {
				Collect-Elements -node $childItems -parentName $name
			}
		}
	}
}

# Collect from ChildItems
$childItemsRoot = $root.SelectSingleNode("f:ChildItems", $nsMgr)
if ($childItemsRoot) {
	Collect-Elements -node $childItemsRoot -parentName "(root)"
}

# Also collect from AutoCommandBar's ChildItems
$acb = $root.SelectSingleNode("f:AutoCommandBar", $nsMgr)
if ($acb) {
	$acbChildren = $acb.SelectSingleNode("f:ChildItems", $nsMgr)
	if ($acbChildren) {
		Collect-Elements -node $acbChildren -parentName "ФормаКоманднаяПанель"
	}
}

# --- Check 3: Unique element IDs ---

if (-not $stopped) {
	$dupCount = ($allElements | Group-Object { $_.Id } | Where-Object { $_.Count -gt 1 -and $_.Name -ne "-1" }).Count
	if ($dupCount -eq 0) {
		Report-OK "Unique element IDs: $($elementIds.Count) elements"
	}
}

# --- Collect attributes (separate ID pool) ---

$attrMap = @{}    # name -> node
$attrIds = @{}    # id -> name
$attrNodes = $root.SelectNodes("f:Attributes/f:Attribute", $nsMgr)
foreach ($attr in $attrNodes) {
	$attrName = $attr.GetAttribute("name")
	$attrId = $attr.GetAttribute("id")
	if ($attrName) {
		# Имена реквизитов уникальны среди реквизитов (отдельный неймспейс от элементов)
		if ($attrMap.ContainsKey($attrName)) {
			Report-Error "Duplicate attribute name '$attrName': id=${attrId} and id=$($attrMap[$attrName].GetAttribute('id'))"
		}
		$attrMap[$attrName] = $attr
	}
	if ($attrId -and $attrId -ne "") {
		if ($attrIds.ContainsKey($attrId)) {
			Report-Error "Duplicate attribute id=${attrId}: '$attrName' and '$($attrIds[$attrId])'"
		} else {
			$attrIds[$attrId] = $attrName
		}
	}

	# Column IDs are a separate sub-pool per attribute — check uniqueness within parent
	$colIds = @{}
	$colNames = @{}  # имена колонок уникальны в пределах своего реквизита
	foreach ($col in $attr.SelectNodes("f:Columns/f:Column", $nsMgr)) {
		$colId = $col.GetAttribute("id")
		$colName = $col.GetAttribute("name")
		if ($colId -and $colId -ne "") {
			if ($colIds.ContainsKey($colId)) {
				Report-Error "Duplicate column id=${colId} in '$attrName': '$colName' and '$($colIds[$colId])'"
			} else {
				$colIds[$colId] = $colName
			}
		}
		if ($colName) {
			if ($colNames.ContainsKey($colName)) {
				Report-Error "Duplicate column name '$colName' in '$attrName': id=${colId} and id=$($colNames[$colName])"
			} else {
				$colNames[$colName] = $colId
			}
		}
	}

	$typeVal = ""
	foreach ($tn in $attr.SelectNodes("f:Type/v8:Type", $nsMgr)) {
		if ($tn.InnerText) { $typeVal = $tn.InnerText; break }
	}
	if ($typeVal -eq "cfg:DynamicList") {
		$mainTable = $attr.SelectSingleNode("f:Settings/f:MainTable", $nsMgr)
		$queryText = $attr.SelectSingleNode("f:Settings/f:QueryText", $nsMgr)
		$hasMain = $mainTable -and $mainTable.InnerText.Trim()
		$hasQuery = $queryText -and $queryText.InnerText.Trim()
		if (-not $hasMain -and -not $hasQuery) {
			Report-Error "Attribute '$attrName': DynamicList has neither MainTable nor QueryText — the form will fail to open"
		}
	}
}

if (-not $stopped) {
	$attrDupCount = ($attrIds.GetEnumerator() | Group-Object Value | Where-Object { $_.Count -gt 1 }).Count
	if ($attrDupCount -eq 0 -and $attrIds.Count -gt 0) {
		Report-OK "Unique attribute IDs: $($attrIds.Count) entries"
	}
}

# --- Collect commands (separate ID pool) ---

$cmdMap = @{}   # name -> node
$cmdIds = @{}   # id -> name
$cmdNodes = $root.SelectNodes("f:Commands/f:Command", $nsMgr)
foreach ($cmd in $cmdNodes) {
	$cmdName = $cmd.GetAttribute("name")
	$cmdId = $cmd.GetAttribute("id")
	if ($cmdName) {
		# Имена команд уникальны среди команд (отдельный неймспейс)
		if ($cmdMap.ContainsKey($cmdName)) {
			Report-Error "Duplicate command name '$cmdName': id=${cmdId} and id=$($cmdMap[$cmdName].GetAttribute('id'))"
		}
		$cmdMap[$cmdName] = $cmd
	}
	if ($cmdId -and $cmdId -ne "") {
		if ($cmdIds.ContainsKey($cmdId)) {
			Report-Error "Duplicate command id=${cmdId}: '$cmdName' and '$($cmdIds[$cmdId])'"
		} else {
			$cmdIds[$cmdId] = $cmdName
		}
	}
}

if (-not $stopped) {
	if ($cmdIds.Count -gt 0) {
		$cmdDupCount = ($cmdIds.GetEnumerator() | Group-Object Value | Where-Object { $_.Count -gt 1 }).Count
		if ($cmdDupCount -eq 0) {
			Report-OK "Unique command IDs: $($cmdIds.Count) entries"
		}
	}
}

# --- Collect parameters (separate name pool, без id) ---

$paramNames = @{}  # name -> $true (имена параметров уникальны среди параметров)
foreach ($param in $root.SelectNodes("f:Parameters/f:Parameter", $nsMgr)) {
	$paramName = $param.GetAttribute("name")
	if ($paramName) {
		if ($paramNames.ContainsKey($paramName)) {
			Report-Error "Duplicate parameter name '$paramName'"
		} else {
			$paramNames[$paramName] = $true
		}
	}
}

# --- Check 4: Companion elements ---

# Define required companions per element type
$companionRules = @{
	"InputField"        = @("ContextMenu", "ExtendedTooltip")
	"CheckBoxField"     = @("ContextMenu", "ExtendedTooltip")
	"LabelDecoration"   = @("ContextMenu", "ExtendedTooltip")
	"LabelField"        = @("ContextMenu", "ExtendedTooltip")
	"PictureDecoration" = @("ContextMenu", "ExtendedTooltip")
	"PictureField"      = @("ContextMenu", "ExtendedTooltip")
	"CalendarField"     = @("ContextMenu", "ExtendedTooltip")
	"UsualGroup"        = @("ExtendedTooltip")
	"Pages"             = @("ExtendedTooltip")
	"Page"              = @("ExtendedTooltip")
	"Button"            = @("ExtendedTooltip")
	"Table"             = @("ContextMenu", "AutoCommandBar", "SearchStringAddition", "ViewStatusAddition", "SearchControlAddition")
}

if (-not $stopped) {
	$companionErrors = 0
	$companionChecked = 0

	foreach ($el in $allElements) {
		if ($stopped) { break }
		$tag = $el.Tag
		$elName = $el.Name
		$node = $el.Node

		if (-not $companionRules.ContainsKey($tag)) { continue }

		$required = $companionRules[$tag]
		$companionChecked++

		foreach ($compTag in $required) {
			$compNode = $node.SelectSingleNode("f:$compTag", $nsMgr)
			if (-not $compNode) {
				Report-Error "[$tag] '$elName': missing companion <$compTag>"
				$companionErrors++
			}
		}
	}

	if ($companionErrors -eq 0 -and $companionChecked -gt 0) {
		Report-OK "Companion elements: $companionChecked elements checked"
	}
}

# --- Check 5: DataPath -> Attribute references ---

if (-not $stopped) {
	$pathErrors = 0
	$pathChecked = 0
	$pathBaseSkipped = 0

	# All data-binding tags whose value is an attribute path (root must exist in <Attributes>).
	$bindingTags = @('DataPath','TitleDataPath','FooterDataPath','HeaderDataPath',
		'MultipleValueDataPath','MultipleValuePresentDataPath','RowPictureDataPath','MultipleValuePictureDataPath')

	foreach ($el in $allElements) {
		if ($stopped) { break }
		$tag = $el.Tag
		$elName = $el.Name
		$node = $el.Node

		# Skip companion elements
		if ($tag -in @("ContextMenu", "ExtendedTooltip", "AutoCommandBar", "SearchStringAddition", "ViewStatusAddition", "SearchControlAddition")) {
			continue
		}

		# In borrowed forms, skip DataPath check for base elements (id < 1000000)
		if ($hasBaseForm -and $el.Id) {
			try { if ([int]$el.Id -lt 1000000) { $pathBaseSkipped++; continue } } catch {}
		}

		foreach ($bTag in $bindingTags) {
			if ($stopped) { break }
			$dpNode = $node.SelectSingleNode("f:$bTag", $nsMgr)
			if (-not $dpNode) { continue }

			$dataPath = $dpNode.InnerText.Trim()
			if (-not $dataPath) { continue }

			# Opaque platform-internal shapes — not validatable from Form.xml alone:
			#   - bare numeric (e.g. "10", "1000003") — internal index
			#   - "N/M:<uuid>" — metadata reference by UUID
			if ($dataPath -match '^\d+$' -or $dataPath -match '^\d+/\d+:[0-9a-fA-F-]+$') {
				continue
			}

			$pathChecked++

			# Extract root segment of path, strip array indices like [0]
			$cleanPath = $dataPath -replace '\[\d+\]', ''
			# Strip leading '~' (current row of DynamicList: ~Список.Поле)
			if ($cleanPath.StartsWith('~')) { $cleanPath = $cleanPath.Substring(1) }
			$segments = $cleanPath -split '\.'
			$rootAttr = $segments[0]

			# Resolve Items.<TableName>.CurrentData.<Field>... — table element, not attribute
			if ($rootAttr -eq 'Items') {
				if ($segments.Count -lt 3 -or $segments[2] -ne 'CurrentData') {
					Report-Warn "[$tag] '$elName': $bTag='$dataPath' — unknown Items.* shape, expected Items.<Table>.CurrentData.*"
					continue
				}
				$tableName = $segments[1]
				$tableEl = $null
				foreach ($candidate in $allElements) {
					if ($candidate.Tag -eq 'Table' -and $candidate.Name -eq $tableName) {
						$tableEl = $candidate
						break
					}
				}
				if (-not $tableEl) {
					Report-Error "[$tag] '$elName': $bTag='$dataPath' — table element '$tableName' not found"
					$pathErrors++
					continue
				}
				$tableDpNode = $tableEl.Node.SelectSingleNode("f:DataPath", $nsMgr)
				if (-not $tableDpNode -or -not $tableDpNode.InnerText.Trim()) {
					# Table without DataPath — can't resolve further, accept silently
					continue
				}
				$tableDp = $tableDpNode.InnerText.Trim() -replace '\[\d+\]', ''
				if ($tableDp.StartsWith('~')) { $tableDp = $tableDp.Substring(1) }
				$rootAttr = ($tableDp -split '\.')[0]
			}

			if (-not $attrMap.ContainsKey($rootAttr)) {
				Report-Error "[$tag] '$elName': $bTag='$dataPath' — attribute '$rootAttr' not found"
				$pathErrors++
			}
		}
	}

	$pathMsg = ""
	if ($pathChecked -gt 0) { $pathMsg = "$pathChecked paths checked" }
	if ($pathBaseSkipped -gt 0) {
		$skipNote = "$pathBaseSkipped base skipped"
		$pathMsg = if ($pathMsg) { "$pathMsg, $skipNote" } else { $skipNote }
	}
	if ($pathErrors -eq 0 -and $pathMsg) {
		Report-OK "Data bindings: $pathMsg"
	} elseif ($pathErrors -eq 0) {
		Report-OK "Data bindings: none"
	}
}

# --- Check 6: Button command references ---

if (-not $stopped) {
	$cmdErrors = 0
	$cmdChecked = 0

	foreach ($el in $allElements) {
		if ($stopped) { break }
		$tag = $el.Tag
		$elName = $el.Name
		$node = $el.Node

		if ($tag -ne "Button") { continue }

		$cmdNode = $node.SelectSingleNode("f:CommandName", $nsMgr)
		if (-not $cmdNode) { continue }

		$cmdRef = $cmdNode.InnerText.Trim()
		if (-not $cmdRef) { continue }

		# Form.Command.XXX -> check command XXX exists
		if ($cmdRef -match '^Form\.Command\.(.+)$') {
			$cmdName = $Matches[1]
			$cmdChecked++
			if (-not $cmdMap.ContainsKey($cmdName)) {
				Report-Error "[Button] '$elName': CommandName='$cmdRef' — command '$cmdName' not found in Commands"
				$cmdErrors++
			}
		}
		# Form.StandardCommand.XXX — skip, standard commands always exist
	}

	if ($cmdErrors -eq 0 -and $cmdChecked -gt 0) {
		Report-OK "Command references: $cmdChecked buttons checked"
	} elseif ($cmdChecked -eq 0) {
		Report-OK "Command references: none"
	}
}

# --- Check 7: Events have handler names ---

if (-not $stopped) {
	$eventErrors = 0
	$eventChecked = 0

	# Form-level events
	$formEvents = $root.SelectSingleNode("f:Events", $nsMgr)
	if ($formEvents) {
		foreach ($evt in $formEvents.SelectNodes("f:Event", $nsMgr)) {
			$evtName = $evt.GetAttribute("name")
			$handler = $evt.InnerText.Trim()
			$eventChecked++
			if (-not $handler) {
				Report-Error "Form event '$evtName': empty handler name"
				$eventErrors++
			}
		}
	}

	# Element-level events
	foreach ($el in $allElements) {
		if ($stopped) { break }
		$tag = $el.Tag
		$elName = $el.Name
		$node = $el.Node

		$eventsNode = $node.SelectSingleNode("f:Events", $nsMgr)
		if (-not $eventsNode) { continue }

		foreach ($evt in $eventsNode.SelectNodes("f:Event", $nsMgr)) {
			$evtName = $evt.GetAttribute("name")
			$handler = $evt.InnerText.Trim()
			$eventChecked++
			if (-not $handler) {
				Report-Error "[$tag] '$elName' event '$evtName': empty handler name"
				$eventErrors++
			}
		}
	}

	if ($eventErrors -eq 0 -and $eventChecked -gt 0) {
		Report-OK "Event handlers: $eventChecked events checked"
	} elseif ($eventChecked -eq 0) {
		Report-OK "Event handlers: none"
	}
}

# --- Check 8: Command actions ---

if (-not $stopped) {
	$actionErrors = 0
	$actionChecked = 0

	foreach ($cmd in $cmdNodes) {
		if ($stopped) { break }
		$cmdName = $cmd.GetAttribute("name")
		$actionNode = $cmd.SelectSingleNode("f:Action", $nsMgr)
		$actionChecked++
		if (-not $actionNode -or -not $actionNode.InnerText.Trim()) {
			Report-Error "Command '$cmdName': missing or empty Action"
			$actionErrors++
		}
	}

	if ($actionErrors -eq 0 -and $actionChecked -gt 0) {
		Report-OK "Command actions: $actionChecked commands checked"
	} elseif ($actionChecked -eq 0) {
		Report-OK "Command actions: none"
	}
}

# --- Check 9: MainAttribute count ---

if (-not $stopped) {
	$mainCount = 0
	foreach ($attr in $attrNodes) {
		$mainNode = $attr.SelectSingleNode("f:MainAttribute", $nsMgr)
		if ($mainNode -and $mainNode.InnerText -eq "true") {
			$mainCount++
		}
	}

	if ($mainCount -le 1) {
		$mainInfo = if ($mainCount -eq 1) { "1 main attribute" } else { "no main attribute" }
		Report-OK "MainAttribute: $mainInfo"
	} else {
		Report-Error "Multiple MainAttribute=true ($mainCount found, expected 0 or 1)"
	}
}

# --- Check 10: Title must be multilingual XML (not plain text) ---

if (-not $stopped) {
	$titleNode = $root.SelectSingleNode("f:Title", $nsMgr)
	if ($titleNode) {
		$v8items = $titleNode.SelectNodes("v8:item", $nsMgr)
		if ($v8items.Count -eq 0 -and $titleNode.InnerText.Trim() -ne "") {
			Report-Error "Form Title is plain text ('$($titleNode.InnerText.Trim())') — must be multilingual XML (<v8:item>). Use top-level 'title' key in form-compile DSL."
		} else {
			Report-OK "Title: multilingual XML"
		}
	}
}

# --- Check 11: Extension-specific validations ---

$baseFormNode = $root.SelectSingleNode("f:BaseForm", $nsMgr)
$isExtension = ($baseFormNode -ne $null)

if (-not $stopped -and $isExtension) {
	# 11a. BaseForm version
	$bfVersion = $baseFormNode.GetAttribute("version")
	if ($bfVersion) {
		Report-OK "BaseForm: version=$bfVersion"
	} else {
		Report-Warn "BaseForm: version attribute missing"
	}

	# 11b. callType values validation (Before, After, Override)
	$validCallTypes = @("Before", "After", "Override")
	$ctErrors = 0
	$ctChecked = 0

	# Check form-level events
	$formEventsNode = $root.SelectSingleNode("f:Events", $nsMgr)
	if ($formEventsNode) {
		foreach ($evt in $formEventsNode.SelectNodes("f:Event", $nsMgr)) {
			$ct = $evt.GetAttribute("callType")
			if ($ct) {
				$ctChecked++
				if ($validCallTypes -notcontains $ct) {
					Report-Error "Form event '$($evt.GetAttribute('name'))': invalid callType='$ct' (expected: Before, After, Override)"
					$ctErrors++
				}
			}
		}
	}

	# Check element-level events
	foreach ($el in $allElements) {
		if ($stopped) { break }
		$eventsNode = $el.Node.SelectSingleNode("f:Events", $nsMgr)
		if (-not $eventsNode) { continue }
		foreach ($evt in $eventsNode.SelectNodes("f:Event", $nsMgr)) {
			$ct = $evt.GetAttribute("callType")
			if ($ct) {
				$ctChecked++
				if ($validCallTypes -notcontains $ct) {
					Report-Error "[$($el.Tag)] '$($el.Name)' event '$($evt.GetAttribute('name'))': invalid callType='$ct'"
					$ctErrors++
				}
			}
		}
	}

	# Check command actions
	foreach ($cmd in $cmdNodes) {
		if ($stopped) { break }
		$cmdName = $cmd.GetAttribute("name")
		foreach ($action in $cmd.SelectNodes("f:Action", $nsMgr)) {
			$ct = $action.GetAttribute("callType")
			if ($ct) {
				$ctChecked++
				if ($validCallTypes -notcontains $ct) {
					Report-Error "Command '$cmdName' Action: invalid callType='$ct'"
					$ctErrors++
				}
			}
		}
	}

	if (-not $stopped -and $ctErrors -eq 0 -and $ctChecked -gt 0) {
		Report-OK "callType values: $ctChecked checked"
	}

	# 11c. Extension ID ranges — warn if extension-added attrs/commands have id < 1000000
	# Collect BaseForm attribute names to distinguish added ones
	$baseAttrNames = @{}
	$baseCmdNames = @{}
	$bfNs = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
	$bfNs.AddNamespace("f", "http://v8.1c.ru/8.3/xcf/logform")
	foreach ($bAttr in $baseFormNode.SelectNodes("f:Attributes/f:Attribute", $bfNs)) {
		$baName = $bAttr.GetAttribute("name")
		if ($baName) { $baseAttrNames[$baName] = $true }
	}
	foreach ($bCmd in $baseFormNode.SelectNodes("f:Commands/f:Command", $bfNs)) {
		$bcName = $bCmd.GetAttribute("name")
		if ($bcName) { $baseCmdNames[$bcName] = $true }
	}

	$idWarnCount = 0
	foreach ($attr in $attrNodes) {
		$aName = $attr.GetAttribute("name")
		$aId = $attr.GetAttribute("id")
		if ($aName -and -not $baseAttrNames.ContainsKey($aName) -and $aId) {
			try {
				$intId = [int]$aId
				if ($intId -lt 1000000) {
					Report-Warn "Attribute '$aName' (id=$aId): extension-added attribute has id < 1000000"
					$idWarnCount++
				}
			} catch {}
		}
	}

	foreach ($cmd in $cmdNodes) {
		$cName = $cmd.GetAttribute("name")
		$cId = $cmd.GetAttribute("id")
		if ($cName -and -not $baseCmdNames.ContainsKey($cName) -and $cId) {
			try {
				$intId = [int]$cId
				if ($intId -lt 1000000) {
					Report-Warn "Command '$cName' (id=$cId): extension-added command has id < 1000000"
					$idWarnCount++
				}
			} catch {}
		}
	}

	if (-not $stopped -and $idWarnCount -eq 0) {
		$extAttrCount = ($attrNodes | Where-Object { -not $baseAttrNames.ContainsKey($_.GetAttribute("name")) }).Count
		$extCmdCount = ($cmdNodes | Where-Object { -not $baseCmdNames.ContainsKey($_.GetAttribute("name")) }).Count
		if (($extAttrCount + $extCmdCount) -gt 0) {
			Report-OK "Extension ID ranges: $extAttrCount attr(s), $extCmdCount cmd(s) — all >= 1000000"
		}
	}
}

# Check callType without BaseForm (structural warning)
if (-not $stopped -and -not $isExtension) {
	$callTypeWithoutBase = $false
	$feNode = $root.SelectSingleNode("f:Events", $nsMgr)
	if ($feNode) {
		foreach ($evt in $feNode.SelectNodes("f:Event", $nsMgr)) {
			if ($evt.GetAttribute("callType")) { $callTypeWithoutBase = $true; break }
		}
	}
	if (-not $callTypeWithoutBase) {
		foreach ($cmd in $cmdNodes) {
			foreach ($action in $cmd.SelectNodes("f:Action", $nsMgr)) {
				if ($action.GetAttribute("callType")) { $callTypeWithoutBase = $true; break }
			}
			if ($callTypeWithoutBase) { break }
		}
	}
	if ($callTypeWithoutBase) {
		Report-Warn "callType attributes found but no BaseForm — possible incorrect structure"
	}
}

# --- Check 12: Type values validation ---

$knownInvalidTypes = @(
	"FormDataStructure","FormDataCollection","FormDataTree","FormDataTreeItem","FormDataCollectionItem"
	"FormGroup","FormField","FormButton","FormDecoration","FormTable"
)
$validClosedTypes = @(
	"xs:boolean","xs:string","xs:decimal","xs:dateTime","xs:binary"
	"v8:FillChecking","v8:Null","v8:StandardPeriod","v8:StandardBeginningDate","v8:Type"
	"v8:TypeDescription","v8:UUID","v8:ValueListType","v8:ValueTable","v8:ValueTree"
	"v8:Universal","v8:FixedArray","v8:FixedStructure"
	"v8ui:Color","v8ui:Font","v8ui:FormattedString","v8ui:HorizontalAlign"
	"v8ui:Picture","v8ui:SizeChangeMode","v8ui:VerticalAlign"
	"dcsset:DataCompositionComparisonType","dcsset:DataCompositionFieldPlacement"
	"dcsset:Filter","dcsset:SettingsComposer","dcsset:DataCompositionSettings"
	"dcssch:DataCompositionSchema"
	"dcscor:DataCompositionComparisonType","dcscor:DataCompositionGroupType"
	"dcscor:DataCompositionPeriodAdditionType","dcscor:DataCompositionSortDirection","dcscor:Field"
	"ent:AccountType","ent:AccumulationRecordType","ent:AccountingRecordType"
)
$validCfgPrefixes = @(
	"AccountingRegisterRecordSet","AccumulationRegisterRecordSet"
	"BusinessProcessObject","BusinessProcessRef"
	"CatalogObject","CatalogRef"
	"ChartOfAccountsObject","ChartOfAccountsRef"
	"ChartOfCalculationTypesObject","ChartOfCalculationTypesRef"
	"ChartOfCharacteristicTypesObject","ChartOfCharacteristicTypesRef"
	"ConstantsSet","DataProcessorObject","DocumentObject","DocumentRef"
	"DynamicList","EnumRef","ExchangePlanObject","ExchangePlanRef"
	"ExternalDataProcessorObject","ExternalReportObject"
	"InformationRegisterRecordManager","InformationRegisterRecordSet"
	"ReportObject","TaskObject","TaskRef"
)

# Export folder names that are sometimes written where a type belongs -> the
# reference type, if the kind has one.
$exportFolderTypes = New-Object 'System.Collections.Generic.Dictionary[string,string]' ([System.StringComparer]::Ordinal)
foreach ($pair in @(
	@("Catalogs","CatalogRef"), @("Documents","DocumentRef"), @("Enums","EnumRef"),
	@("ChartsOfAccounts","ChartOfAccountsRef"), @("ChartsOfCharacteristicTypes","ChartOfCharacteristicTypesRef"),
	@("ChartsOfCalculationTypes","ChartOfCalculationTypesRef"), @("BusinessProcesses","BusinessProcessRef"),
	@("ExchangePlans","ExchangePlanRef"), @("Tasks","TaskRef"), @("DefinedTypes","DefinedType"),
	@("InformationRegisters",""), @("AccumulationRegisters",""), @("AccountingRegisters",""),
	@("CalculationRegisters",""), @("Constants",""), @("DataProcessors",""), @("Reports",""), @("DocumentJournals","")
)) { $exportFolderTypes[$pair[0]] = $pair[1] }

if (-not $stopped) {
	$typeNodes = $root.SelectNodes("//v8:Type", $nsMgr)
	$typeOk = $true
	$typeChecked = 0
	$typeInvalid = 0
	foreach ($tn in $typeNodes) {
		$tv = $tn.InnerText.Trim()
		if (-not $tv) { continue }
		$typeChecked++
		if ($tv -in $knownInvalidTypes) {
			Report-Error "12. Type '$tv': invalid runtime/UI type (not valid in XDTO schema)"
			$typeOk = $false; $typeInvalid++
			continue
		}
		if ($tv -in $validClosedTypes) { continue }
		if ($tv -match '^cfg:(.+)$') {
			$cfgVal = $Matches[1]
			if ($cfgVal -eq "DynamicList") { continue }
			# Local: cfg:Catalogs.X is the export folder name, not a type — the platform
			# refuses it (was an "unrecognized prefix" warning).
			if ($cfgVal -cmatch '^([^.]+)\.' -and $exportFolderTypes.ContainsKey($Matches[1])) {
				$folder = $Matches[1]
				$hint = if ($exportFolderTypes[$folder]) { " — a reference type is 'cfg:$($exportFolderTypes[$folder]).<Name>'" } else { "" }
				Report-Error "12. Type '$tv': export folder name '$folder' instead of a type$hint"
				$typeOk = $false; $typeInvalid++
				continue
			}
			if ($cfgVal -match '^([^.]+)\.') {
				$pfx = $Matches[1]
				if ($pfx -in $validCfgPrefixes) {
					# ExternalDataProcessorObject/ExternalReportObject valid only for EPF/ERF, not config
					if ($script:isConfigContext -and ($pfx -eq "ExternalDataProcessorObject" -or $pfx -eq "ExternalReportObject")) {
						Report-Error "12. Type '$tv': External* type in configuration context (use DataProcessorObject/ReportObject instead)"
						$typeOk = $false; $typeInvalid++
					}
					continue
				}
			}
			Report-Warn "12. Type '$tv': unrecognized cfg prefix"
			$typeOk = $false
			continue
		}
		if ($tv -match ':') { continue }
		Report-Warn "12. Type '$tv': bare type without namespace prefix"
		$typeOk = $false
	}
	if ($typeChecked -eq 0) {
		Report-OK "12. Types: no type values to check"
	} elseif ($typeOk) {
		Report-OK "12. Types: $typeChecked values, all valid"
	}
}

# --- Check 12b (local): the owner of a default object / record form ---
# A form reached through DefaultObjectForm / DefaultFolderForm / DefaultRecordForm
# (or the Auxiliary* twin) of a catalog, document, chart, exchange plan, business
# process, task or information register receives an object of that owner: its main
# attribute must be <Kind>Object.<Owner> (InformationRegisterRecordManager for a
# register). A form copied from another object keeps the other owner's type and
# loads, but fails when it is opened. Data processors and reports are not checked:
# vendor configurations share one processor's object between several of them.
# The same main attribute must not bind Description / Code when the owner's
# DescriptionLength / CodeLength is 0 — the standard attribute does not exist.

$ownerKinds = @("Catalog","Document","ChartOfAccounts","ChartOfCharacteristicTypes","ChartOfCalculationTypes","ExchangePlan","BusinessProcess","Task","InformationRegister")
$ownerDescriptor = $null
if (-not $stopped -and $formName) {
	$formDirPath = Split-Path (Split-Path (Resolve-Path $FormPath).Path -Parent) -Parent
	$formsDirPath = Split-Path $formDirPath -Parent
	if ((Split-Path $formsDirPath -Leaf) -ceq "Forms") {
		$ownerDirPath = Split-Path $formsDirPath -Parent
		$ownerXmlPath = "$ownerDirPath.xml"
		if (Test-Path -LiteralPath $ownerXmlPath) {
			try {
				$ownerDoc = New-Object System.Xml.XmlDocument
				$ownerDoc.Load($ownerXmlPath)
				$ownerDescriptor = $ownerDoc
			} catch { $ownerDescriptor = $null }
		}
	}
}
if ($ownerDescriptor) {
	$mdNs = New-Object System.Xml.XmlNamespaceManager($ownerDescriptor.NameTable)
	$mdNs.AddNamespace("md", "http://v8.1c.ru/8.3/MDClasses")
	$ownerNode = $null
	foreach ($c in $ownerDescriptor.DocumentElement.ChildNodes) { if ($c.NodeType -eq 'Element') { $ownerNode = $c; break } }
	$ownerProps = if ($ownerNode) { $ownerNode.SelectSingleNode("md:Properties", $mdNs) } else { $null }
	$ownerKind = if ($ownerNode) { $ownerNode.LocalName } else { "" }
	$ownerNameNode = if ($ownerProps) { $ownerProps.SelectSingleNode("md:Name", $mdNs) } else { $null }
	$ownerName = if ($ownerNameNode) { $ownerNameNode.InnerText.Trim() } else { "" }
	$mainAttr = $null
	foreach ($attr in $attrNodes) {
		$mainNode = $attr.SelectSingleNode("f:MainAttribute", $nsMgr)
		if ($mainNode -and $mainNode.InnerText -eq "true") { $mainAttr = $attr; break }
	}
	$mainTypes = @()
	if ($mainAttr) { foreach ($tn in $mainAttr.SelectNodes("f:Type/v8:Type", $nsMgr)) { if ($tn.InnerText.Trim()) { $mainTypes += $tn.InnerText.Trim() } } }
	if ($ownerProps -and $ownerName -and ($ownerKinds -ccontains $ownerKind)) {
		$ownFormRef = "$ownerKind.$ownerName.Form.$formName"
		$slots = @()
		foreach ($slot in @("DefaultObjectForm","DefaultFolderForm","DefaultRecordForm","AuxiliaryObjectForm","AuxiliaryFolderForm","AuxiliaryRecordForm")) {
			$slotNode = $ownerProps.SelectSingleNode("md:$slot", $mdNs)
			if ($slotNode -and $slotNode.InnerText.Trim() -ceq $ownFormRef) { $slots += $slot }
		}
		if ($slots.Count -gt 0 -and $mainAttr) {
			$expectedType = if ($ownerKind -eq "InformationRegister") { "cfg:InformationRegisterRecordManager.$ownerName" } else { "cfg:$($ownerKind)Object.$ownerName" }
			if ($mainTypes.Count -ne 1 -or $mainTypes[0] -cne $expectedType) {
				Report-Error "12b. Main attribute '$($mainAttr.GetAttribute('name'))' has type '$($mainTypes -join ', ')', but the form is $($slots -join ' / ') of $ownerKind.$ownerName — expected '$expectedType' (form copied from another object?)"
			} else {
				Report-OK "12b. Owner: main attribute '$($mainAttr.GetAttribute('name'))' is $expectedType"
			}
		}
		if ($mainAttr -and $mainTypes.Count -eq 1 -and $mainTypes[0] -ceq "cfg:$($ownerKind)Object.$ownerName") {
			$mainName = $mainAttr.GetAttribute("name")
			$boundPaths = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
			foreach ($dp in $root.GetElementsByTagName("DataPath", "http://v8.1c.ru/8.3/xcf/logform")) { [void]$boundPaths.Add($dp.InnerText.Trim()) }
			foreach ($pair in @(@("DescriptionLength","Description"), @("CodeLength","Code"))) {
				$lengthNode = $ownerProps.SelectSingleNode("md:$($pair[0])", $mdNs)
				if ($lengthNode -and $lengthNode.InnerText.Trim() -eq "0" -and $boundPaths.Contains("$mainName.$($pair[1])")) {
					Report-Error "12b. '$mainName.$($pair[1])' is bound, but $ownerKind.$ownerName has $($pair[0])=0 — the object has no $($pair[1])"
				}
			}
		}
	}
}

# --- Check 13 (local): Form.xml handlers against Module.bsl ---
# Every event handler and command Action named in Form.xml must be a procedure of
# the form module, declared once (a duplicate does not compile — error). The rest
# are warnings, because vendor configurations ship all of them: a handler that is
# missing, has no compilation directive, runs in the wrong context (client event
# on a server procedure, *AtServer event or command on a client one), or has more
# mandatory parameters than the platform passes for that event.
# Check 14 (local): РеквизитФормыВЗначение / ЗначениеВРеквизитФормы need the form
# context on the server — a call in a procedure explicitly compiled &НаКлиенте,
# &НаСервереБезКонтекста or &НаКлиентеНаСервереБезКонтекста is an error. A procedure
# without a directive is server-side in a form module and is accepted.

$modulePath = Join-Path (Join-Path (Split-Path (Resolve-Path $FormPath).Path -Parent) "Form") "Module.bsl"
$directiveMap = @{
	"наклиенте" = "client"; "atclient" = "client"
	"насервере" = "server"; "atserver" = "server"
	"насерверебезконтекста" = "servernc"; "atservernocontext" = "servernc"
	"наклиентенасерверебезконтекста" = "clientservernc"; "atclientatservernocontext" = "clientservernc"
	"наклиентенасервере" = "clientserver"; "atclientatserver" = "clientserver"
}
# Largest number of parameters the platform passes to a handler, per element tag and
# event (a handler may declare fewer). Unlisted events are not arity-checked.
$eventArity = @{
	"Form|OnCreateAtServer" = 2; "Form|OnOpen" = 1; "Form|NotificationProcessing" = 3; "Form|ExternalEvent" = 3
	"Form|FillCheckProcessingAtServer" = 2; "Form|BeforeClose" = 4; "Form|OnClose" = 1; "Form|ChoiceProcessing" = 2
	"Form|OnReadAtServer" = 1; "Form|BeforeWrite" = 2; "Form|BeforeWriteAtServer" = 3; "Form|OnWriteAtServer" = 3
	"Form|AfterWriteAtServer" = 2; "Form|AfterWrite" = 1
	"InputField|OnChange" = 1; "InputField|StartChoice" = 4; "InputField|Clearing" = 2; "InputField|ChoiceProcessing" = 5
	"InputField|AutoComplete" = 6; "InputField|TextEditEnd" = 5; "InputField|Opening" = 2
	"CheckBoxField|OnChange" = 1; "LabelDecoration|Click" = 2; "LabelDecoration|URLProcessing" = 3
	"LabelField|OnChange" = 1; "LabelField|Click" = 2; "LabelField|URLProcessing" = 3; "RadioButtonField|OnChange" = 1
	"Pages|OnCurrentPageChange" = 2
	"Table|Selection" = 4; "Table|OnActivateRow" = 1; "Table|ChoiceProcessing" = 3; "Table|OnStartEdit" = 3
	"Table|BeforeAddRow" = 6; "Table|BeforeRowChange" = 2; "Table|BeforeDeleteRow" = 2; "Table|AfterDeleteRow" = 1
	"Table|OnChange" = 1; "Table|OnEditEnd" = 3
	"Command|Action" = 1
}

function Get-BslProcedures([string[]]$lines) {
	# name (lower case) -> list of @{ Name; Line; Directive; Params; Required }
	$result = @{}
	$declRe = [regex]::new('^\s*(?:(?:Асинх|Async)\s+)?(?:Процедура|Функция|Procedure|Function)\s+([\w]+)\s*\(', 'IgnoreCase')
	for ($i = 0; $i -lt $lines.Count; $i++) {
		$m = $declRe.Match($lines[$i])
		if (-not $m.Success) { continue }
		$name = $m.Groups[1].Value
		# Directive: walk back over blank lines, comments and annotations.
		$directive = $null
		for ($j = $i - 1; $j -ge 0; $j--) {
			$t = $lines[$j].Trim()
			if (-not $t -or $t.StartsWith("//")) { continue }
			if ($t.StartsWith("&")) {
				$dm = [regex]::Match($t, '^&\s*(\w+)')
				if ($dm.Success -and $directiveMap.ContainsKey($dm.Groups[1].Value.ToLowerInvariant())) { $directive = $directiveMap[$dm.Groups[1].Value.ToLowerInvariant()] }
				continue
			}
			break
		}
		# Parameters: the text between the declaration's parentheses (strings and
		# comments skipped, may span lines).
		$buf = New-Object System.Text.StringBuilder
		$depth = 0; $inStr = $false; $closed = $false
		for ($j = $i; $j -lt [Math]::Min($i + 40, $lines.Count) -and -not $closed; $j++) {
			$s = $lines[$j]
			$k = if ($j -eq $i) { $m.Index + $m.Length - 1 } else { 0 }
			while ($k -lt $s.Length) {
				$ch = $s[$k]
				if ($inStr) { [void]$buf.Append($ch); if ($ch -eq '"') { $inStr = $false }; $k++; continue }
				if ($ch -eq '"') { $inStr = $true; [void]$buf.Append($ch) }
				elseif ($ch -eq '/' -and $k + 1 -lt $s.Length -and $s[$k + 1] -eq '/') { break }
				elseif ($ch -eq '(') { $depth++; if ($depth -gt 1) { [void]$buf.Append($ch) } }
				elseif ($ch -eq ')') { $depth--; if ($depth -eq 0) { $closed = $true; break }; [void]$buf.Append($ch) }
				elseif ($depth -ge 1) { [void]$buf.Append($ch) }
				$k++
			}
			[void]$buf.Append(' ')
		}
		$params = $null; $required = $null
		if ($closed) {
			$parts = @(); $cur = New-Object System.Text.StringBuilder; $pInStr = $false; $pDepth = 0
			foreach ($ch in $buf.ToString().ToCharArray()) {
				if ($pInStr) { [void]$cur.Append($ch); if ($ch -eq '"') { $pInStr = $false }; continue }
				if ($ch -eq '"') { $pInStr = $true }
				if ($ch -eq '(') { $pDepth++ }
				if ($ch -eq ')') { $pDepth-- }
				if ($ch -eq ',' -and $pDepth -eq 0) { $parts += $cur.ToString(); $cur = New-Object System.Text.StringBuilder; continue }
				[void]$cur.Append($ch)
			}
			$parts += $cur.ToString()
			$parts = @($parts | Where-Object { $_.Trim() })
			$params = $parts.Count
			$required = @($parts | Where-Object { -not $_.Contains("=") }).Count
		}
		$key = $name.ToLowerInvariant()
		if (-not $result.ContainsKey($key)) { $result[$key] = @() }
		$result[$key] += @{ Name = $name; Line = $i + 1; Directive = $directive; Params = $params; Required = $required }
	}
	return $result
}

function Get-FormDataConversions([string[]]$lines) {
	# @{ Line; Procedure; Directive; Call } for every unqualified conversion call
	$found = @()
	$declRe = [regex]::new('^\s*(?:(?:Асинх|Async)\s+)?(?:Процедура|Функция|Procedure|Function)\s+([\w]+)\s*\(', 'IgnoreCase')
	$endRe = [regex]::new('^\s*(?:КонецПроцедуры|КонецФункции|EndProcedure|EndFunction)\b', 'IgnoreCase')
	$callRe = [regex]::new('(?<![\w.])(РеквизитФормыВЗначение|ЗначениеВРеквизитФормы|FormAttributeToValue|ValueToFormAttribute)\s*\(', 'IgnoreCase')
	$cur = $null; $curDirective = $null; $pending = $null; $inStr = $false
	for ($i = 0; $i -lt $lines.Count; $i++) {
		$line = $lines[$i]
		# Strip string literals (a multi-line literal continues on lines starting with |) and comments.
		if ($inStr -and -not $line.TrimStart().StartsWith("|")) { $inStr = $false }
		$code = New-Object System.Text.StringBuilder
		$k = 0
		while ($k -lt $line.Length) {
			$ch = $line[$k]
			if ($inStr) {
				if ($ch -eq '"') {
					if ($k + 1 -lt $line.Length -and $line[$k + 1] -eq '"') { $k += 2; continue }
					$inStr = $false
				}
				$k++; continue
			}
			if ($ch -eq '"') { $inStr = $true; $k++; continue }
			if ($ch -eq '/' -and $k + 1 -lt $line.Length -and $line[$k + 1] -eq '/') { break }
			[void]$code.Append($ch); $k++
		}
		$c = $code.ToString()
		$t = $c.Trim()
		if ($t.StartsWith("&")) {
			$dm = [regex]::Match($t, '^&\s*(\w+)')
			if ($dm.Success -and $directiveMap.ContainsKey($dm.Groups[1].Value.ToLowerInvariant())) { $pending = $directiveMap[$dm.Groups[1].Value.ToLowerInvariant()] }
			continue
		}
		$dmatch = $declRe.Match($c)
		if ($dmatch.Success) { $cur = $dmatch.Groups[1].Value; $curDirective = $pending; $pending = $null }
		if ($endRe.IsMatch($c)) { $cur = $null; $curDirective = $null; continue }
		foreach ($cm in $callRe.Matches($c)) {
			$found += @{ Line = $i + 1; Procedure = $cur; Directive = $curDirective; Call = $cm.Groups[1].Value }
		}
	}
	return $found
}

if (-not $stopped -and (Test-Path -LiteralPath $modulePath)) {
	$moduleLines = [System.IO.File]::ReadAllLines($modulePath, [System.Text.Encoding]::UTF8)
	$procedures = Get-BslProcedures $moduleLines

	# References: form events, element events, command actions. In a borrowed form
	# (BaseForm) only the extension's own references are checked: an event with a
	# callType, an element with id >= 1000000, a command absent from the base form.
	$refs = @()
	$baseCmds = @{}
	if ($hasBaseForm) {
		foreach ($bCmd in $root.SelectNodes("f:BaseForm/f:Commands/f:Command", $nsMgr)) { $baseCmds[$bCmd.GetAttribute("name")] = $true }
	}
	$formEventsNode = $root.SelectSingleNode("f:Events", $nsMgr)
	if ($formEventsNode) {
		foreach ($evt in $formEventsNode.SelectNodes("f:Event", $nsMgr)) {
			if ($hasBaseForm -and -not $evt.GetAttribute("callType")) { continue }
			$refs += @{ Owner = "Form"; Event = $evt.GetAttribute("name"); Handler = $evt.InnerText.Trim(); Where = "Form event '$($evt.GetAttribute('name'))'" }
		}
	}
	foreach ($el in $allElements) {
		$eventsNode = $el.Node.SelectSingleNode("f:Events", $nsMgr)
		if (-not $eventsNode) { continue }
		$isBaseElement = $false
		if ($hasBaseForm) { try { $isBaseElement = ([int]$el.Id -lt 1000000) } catch {} }
		foreach ($evt in $eventsNode.SelectNodes("f:Event", $nsMgr)) {
			if ($isBaseElement -and -not $evt.GetAttribute("callType")) { continue }
			$refs += @{ Owner = $el.Tag; Event = $evt.GetAttribute("name"); Handler = $evt.InnerText.Trim(); Where = "[$($el.Tag)] '$($el.Name)' event '$($evt.GetAttribute('name'))'" }
		}
	}
	foreach ($cmd in $cmdNodes) {
		$cName = $cmd.GetAttribute("name")
		foreach ($action in $cmd.SelectNodes("f:Action", $nsMgr)) {
			if ($hasBaseForm -and $baseCmds.ContainsKey($cName) -and -not $action.GetAttribute("callType")) { continue }
			$refs += @{ Owner = "Command"; Event = "Action"; Handler = $action.InnerText.Trim(); Where = "Command '$cName'" }
		}
	}

	$handlerErrors = 0
	$handlerWarnings = 0
	$handlersChecked = 0
	$seenDuplicates = @{}
	foreach ($ref in $refs) {
		if ($stopped) { break }
		if (-not $ref.Handler) { continue }
		$handlersChecked++
		$decls = $procedures[$ref.Handler.ToLowerInvariant()]
		if (-not $decls) {
			Report-Warn "13. $($ref.Where): handler '$($ref.Handler)' not found in Module.bsl"
			$handlerWarnings++
			continue
		}
		if (@($decls).Count -gt 1) {
			if (-not $seenDuplicates.ContainsKey($ref.Handler.ToLowerInvariant())) {
				$seenDuplicates[$ref.Handler.ToLowerInvariant()] = $true
				Report-Error "13. Handler '$($ref.Handler)' is declared $(@($decls).Count) times in Module.bsl (lines $((@($decls) | ForEach-Object { $_.Line }) -join ', ')) — the module does not compile"
				$handlerErrors++
			}
			continue
		}
		$decl = @($decls)[0]
		# Events are named by an identifier; a UUID-named event carries no contract here.
		if ($ref.Event -cnotmatch '^[A-Za-z]\w*$') { continue }
		if (-not $decl.Directive) {
			Report-Warn "13. $($ref.Where): handler '$($decl.Name)' (line $($decl.Line)) has no compilation directive — it compiles &НаСервере"
			$handlerWarnings++
		} else {
			$serverEvent = $ref.Event.EndsWith("AtServer")
			if ($serverEvent -and $decl.Directive -ne "server" -and $decl.Directive -ne "servernc") {
				Report-Warn "13. $($ref.Where): handler '$($decl.Name)' (line $($decl.Line)) is not a server procedure — a *AtServer event needs &НаСервере"
				$handlerWarnings++
			} elseif (-not $serverEvent -and $decl.Directive -ne "client") {
				Report-Warn "13. $($ref.Where): handler '$($decl.Name)' (line $($decl.Line)) is not &НаКлиенте — client events and commands run on the client"
				$handlerWarnings++
			}
		}
		$arityKey = "$($ref.Owner)|$($ref.Event)"
		if ($eventArity.ContainsKey($arityKey) -and $null -ne $decl.Required -and $decl.Required -gt $eventArity[$arityKey]) {
			Report-Warn "13. $($ref.Where): handler '$($decl.Name)' (line $($decl.Line)) requires $($decl.Required) parameters, the platform passes at most $($eventArity[$arityKey])"
			$handlerWarnings++
		}
	}
	if ($handlerErrors -eq 0 -and $handlerWarnings -eq 0) {
		if ($handlersChecked -gt 0) { Report-OK "13. Handlers: $handlersChecked references match Module.bsl" } else { Report-OK "13. Handlers: none referenced" }
	}

	$conversionErrors = 0
	foreach ($conv in (Get-FormDataConversions $moduleLines)) {
		if ($stopped) { break }
		if ($conv.Directive -and $conv.Directive -ne "server") {
			$dirName = switch ($conv.Directive) { "client" { "&НаКлиенте" } "servernc" { "&НаСервереБезКонтекста" } "clientservernc" { "&НаКлиентеНаСервереБезКонтекста" } default { "&НаКлиентеНаСервере" } }
			Report-Error "14. Module.bsl line $($conv.Line): $($conv.Call) in '$($conv.Procedure)' compiled $dirName — it needs the form context on the server (&НаСервере)"
			$conversionErrors++
		}
	}
	if ($conversionErrors -eq 0) { Report-OK "14. Form data conversion: server context only" }
}

# --- Summary ---

$checks = $script:okCount + $errors + $warnings

if ($errors -eq 0 -and $warnings -eq 0 -and -not $Detailed) {
	Write-Host "=== Validation OK: Form.$formName ($checks checks) ==="
} else {
	Write-Host ""
	if ($Detailed) {
		Write-Host "---"
		Write-Host "Total: $($allElements.Count) elements, $($attrNodes.Count) attributes, $($cmdNodes.Count) commands"
	}

	if ($stopped) {
		Write-Host "Stopped after $MaxErrors errors. Fix and re-run."
	}

	Write-Host "=== Result: $errors errors, $warnings warnings ($checks checks) ==="
}

if ($errors -gt 0) {
	exit 1
} else {
	exit 0
}
