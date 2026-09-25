# meta-validate v1.13 — Validate 1C metadata object structure (+корневой <Type>: скаляр без структуры = ошибка)
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills
# Local (v1.13, same as meta-validate.py): the object, its form descriptors and
# Form.xml files carry the version of Configuration.xml (1e/6e); every
# GeneratedType category is required and named exactly (2); Default* /
# Auxiliary*Form references resolve and match the form role (6f); a form binds
# Description / Code only when the length is positive (6g), and the main object
# form shows a mandatory Description nobody fills (6h, warning); names are unique
# case-insensitively and across attributes, tabular sections, dimensions and
# resources (8); InformationRegister forbids Periodicity and DefaultRecordSetForm
# (12); a type spelled with an export folder name (cfg:Catalogs.X) is an error (16a).
param(
	[Parameter(Mandatory)]
	[Alias('Path')]
	[string]$ObjectPath,

	[switch]$Detailed,

	[int]$MaxErrors = 30,

	[string]$OutFile
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Batch mode: pipe-separated paths (comma reserved by PowerShell) ---

$pathList = @($ObjectPath -split '\|' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($pathList.Count -gt 1) {
	$batchOk = 0
	$batchFail = 0
	foreach ($singlePath in $pathList) {
		$callArgs = @{ ObjectPath = $singlePath; MaxErrors = $MaxErrors; Verbose = $Detailed }
		if ($OutFile) {
			$baseName = [System.IO.Path]::GetFileNameWithoutExtension($OutFile)
			$ext = [System.IO.Path]::GetExtension($OutFile)
			$dir = Split-Path $OutFile
			if (-not $dir) { $dir = "." }
			$objLeaf = [System.IO.Path]::GetFileNameWithoutExtension($singlePath)
			$callArgs.OutFile = Join-Path $dir "$baseName`_$objLeaf$ext"
		}
		& $PSCommandPath @callArgs
		if ($LASTEXITCODE -eq 0) { $batchOk++ } else { $batchFail++ }
	}
	Write-Host ""
	Write-Host "=== Batch: $($pathList.Count) objects, $batchOk passed, $batchFail failed ==="
	if ($batchFail -gt 0) { exit 1 }
	exit 0
}

# --- Resolve path ---

if (-not [System.IO.Path]::IsPathRooted($ObjectPath)) {
	$ObjectPath = Join-Path (Get-Location).Path $ObjectPath
}

if (Test-Path $ObjectPath -PathType Container) {
	$dirName = Split-Path $ObjectPath -Leaf
	$candidate = Join-Path $ObjectPath "$dirName.xml"
	$sibling = Join-Path (Split-Path $ObjectPath) "$dirName.xml"
	if (Test-Path $candidate) {
		$ObjectPath = $candidate
	} elseif (Test-Path $sibling) {
		$ObjectPath = $sibling
	} else {
		$xmlFiles = @(Get-ChildItem $ObjectPath -Filter "*.xml" -File | Select-Object -First 1)
		if ($xmlFiles.Count -gt 0) {
			$ObjectPath = $xmlFiles[0].FullName
		} else {
			Write-Host "[ERROR] No XML file found in directory: $ObjectPath"
			exit 1
		}
	}
}

# File not found — прощающий ввод для плоских объектов (SessionParameter, CommonAttribute,
# DefinedType, WSReference, … — один .xml без папки): дописать .xml к голому имени
if (-not (Test-Path $ObjectPath) -and -not [System.IO.Path]::HasExtension($ObjectPath)) {
	if (Test-Path "$ObjectPath.xml") { $ObjectPath = "$ObjectPath.xml" }
}

# File not found — check Dir/Name/Name.xml → Dir/Name.xml
if (-not (Test-Path $ObjectPath)) {
	$fileName = [System.IO.Path]::GetFileNameWithoutExtension($ObjectPath)
	$parentDir = Split-Path $ObjectPath
	$parentDirName = Split-Path $parentDir -Leaf
	if ($fileName -eq $parentDirName) {
		$candidate = Join-Path (Split-Path $parentDir) "$fileName.xml"
		if (Test-Path $candidate) { $ObjectPath = $candidate }
	}
}
if (-not (Test-Path $ObjectPath)) {
	Write-Host "[ERROR] File not found: $ObjectPath"
	exit 1
}

$resolvedPath = (Resolve-Path $ObjectPath).Path

# --- Detect config directory (for cross-object checks) ---

$script:configDir = $null
$probe = Split-Path $resolvedPath
for ($depth = 0; $depth -lt 4; $depth++) {
	if (-not $probe) { break }
	if (Test-Path (Join-Path $probe "Configuration.xml")) {
		$script:configDir = $probe
		break
	}
	$probe = Split-Path $probe
}

# Format version of the configuration the object belongs to (local, checks 1e / 6e).
$script:configVersion = ""
if ($script:configDir) {
	$cfgHeadPath = Join-Path $script:configDir "Configuration.xml"
	try {
		$cfgReader = New-Object System.IO.StreamReader($cfgHeadPath, [System.Text.Encoding]::UTF8)
		$cfgBuffer = New-Object char[] 2000
		$cfgRead = $cfgReader.Read($cfgBuffer, 0, 2000)
		$cfgReader.Close()
		$cfgHead = New-Object string($cfgBuffer, 0, $cfgRead)
		if ($cfgHead -match '<MetaDataObject[^>]+version="(\d+\.\d+)"') { $script:configVersion = $Matches[1] }
	} catch {}
}

# --- Output infrastructure ---

$script:errors = 0
$script:warnings = 0
$script:okCount = 0
$script:stopped = $false
$script:output = New-Object System.Text.StringBuilder 8192

function Out-Line {
	param([string]$msg)
	$script:output.AppendLine($msg) | Out-Null
}

function Report-OK {
	param([string]$msg)
	$script:okCount++
	if ($Detailed) { Out-Line "[OK]    $msg" }
}

function Report-Error {
	param([string]$msg)
	$script:errors++
	Out-Line "[ERROR] $msg"
	if ($script:errors -ge $MaxErrors) {
		$script:stopped = $true
	}
}

function Report-Warn {
	param([string]$msg)
	$script:warnings++
	Out-Line "[WARN]  $msg"
}

$finalize = {
	$checks = $script:okCount + $script:errors + $script:warnings
	if ($script:errors -eq 0 -and $script:warnings -eq 0 -and -not $Detailed) {
		$result = "=== Validation OK: $mdType.$objName ($checks checks) ==="
	} else {
		Out-Line ""
		Out-Line "=== Result: $($script:errors) errors, $($script:warnings) warnings ($checks checks) ==="
		$result = $script:output.ToString()
	}
	Write-Host $result

	if ($OutFile) {
		$utf8Bom = New-Object System.Text.UTF8Encoding $true
		[System.IO.File]::WriteAllText($OutFile, $result, $utf8Bom)
		Write-Host "Written to: $OutFile"
	}
}

# --- Reference tables ---

$guidPattern = '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
$identPattern = '^[A-Za-z\u0410-\u042F\u0401\u0430-\u044F\u0451_][A-Za-z0-9\u0410-\u042F\u0401\u0430-\u044F\u0451_]*$'

$validTypes = @(
	"Catalog","Document","Enum","Constant",
	"InformationRegister","AccumulationRegister","AccountingRegister","CalculationRegister",
	"ChartOfAccounts","ChartOfCharacteristicTypes","ChartOfCalculationTypes",
	"BusinessProcess","Task","ExchangePlan","DocumentJournal",
	"Report","DataProcessor",
	"CommonModule","ScheduledJob","EventSubscription",
	"HTTPService","WebService","DefinedType"
)

# Валидные типы метаданных без глубоких правил валидации — раньше падали как "Unrecognized"
# (ложная ошибка на валидном объекте). Для них выполняется базовая структурная проверка (root/uuid/Name).
$structuralOnlyTypes = @(
	"Subsystem","Role","CommonForm","CommonCommand","CommandGroup","CommonAttribute",
	"CommonTemplate","CommonPicture","SessionParameter","SettingsStorage","FilterCriterion",
	"FunctionalOption","FunctionalOptionsParameter","Language","Style","StyleItem",
	"WSReference","XDTOPackage","DocumentNumerator","Sequence"
)

# GeneratedType categories by type
$generatedTypeCategories = @{
	"Catalog"                    = @("Object","Ref","Selection","List","Manager")
	"Document"                   = @("Object","Ref","Selection","List","Manager")
	"Enum"                       = @("Ref","Manager","List")
	"Constant"                   = @("Manager","ValueManager","ValueKey")
	"InformationRegister"        = @("Record","Manager","Selection","List","RecordSet","RecordKey","RecordManager")
	"AccumulationRegister"       = @("Record","Manager","Selection","List","RecordSet","RecordKey")
	"AccountingRegister"         = @("Record","Manager","Selection","List","RecordSet","RecordKey","ExtDimensions")
	"CalculationRegister"        = @("Record","Manager","Selection","List","RecordSet","RecordKey","Recalcs")
	"ChartOfAccounts"            = @("Object","Ref","Selection","List","Manager","ExtDimensionTypes","ExtDimensionTypesRow")
	"ChartOfCharacteristicTypes" = @("Object","Ref","Selection","List","Manager","Characteristic")
	"ChartOfCalculationTypes"    = @("Object","Ref","Selection","List","Manager","DisplacingCalculationTypes","DisplacingCalculationTypesRow","BaseCalculationTypes","BaseCalculationTypesRow","LeadingCalculationTypes","LeadingCalculationTypesRow")
	"BusinessProcess"            = @("Object","Ref","Selection","List","Manager","RoutePointRef")
	"Task"                       = @("Object","Ref","Selection","List","Manager")
	"ExchangePlan"               = @("Object","Ref","Selection","List","Manager")
	"DocumentJournal"            = @("Selection","List","Manager")
	"Report"                     = @("Object","Manager")
	"DataProcessor"              = @("Object","Manager")
	"DefinedType"                = @("DefinedType")
}

# Types that have NO InternalInfo / GeneratedType
$typesWithoutInternalInfo = @("CommonModule","ScheduledJob","EventSubscription")

# StandardAttributes by type
$standardAttributesByType = @{
	"Catalog"                    = @("PredefinedDataName","Predefined","Ref","DeletionMark","IsFolder","Owner","Parent","Description","Code")
	"Document"                   = @("Posted","Ref","DeletionMark","Date","Number")
	"Enum"                       = @("Order","Ref")
	"InformationRegister"        = @("Active","LineNumber","Recorder","Period")
	"AccumulationRegister"       = @("Active","LineNumber","Recorder","Period","RecordType")
	"AccountingRegister"         = @("Active","Period","Recorder","LineNumber","Account")
	"CalculationRegister"        = @("Active","Recorder","LineNumber","RegistrationPeriod","CalculationType","ReversingEntry","ActionPeriod","BegOfActionPeriod","EndOfActionPeriod","BegOfBasePeriod","EndOfBasePeriod")
	"ChartOfAccounts"            = @("PredefinedDataName","Predefined","Ref","DeletionMark","Description","Code","Parent","Order","Type","OffBalance")
	"ChartOfCharacteristicTypes" = @("PredefinedDataName","Predefined","Ref","DeletionMark","Description","Code","Parent","IsFolder","ValueType")
	"ChartOfCalculationTypes"    = @("PredefinedDataName","Predefined","Ref","DeletionMark","Description","Code","ActionPeriodIsBasic")
	"BusinessProcess"            = @("Ref","DeletionMark","Date","Number","Started","Completed","HeadTask")
	"Task"                       = @("Ref","DeletionMark","Date","Number","Executed","Description","RoutePoint","BusinessProcess")
	"ExchangePlan"               = @("Ref","DeletionMark","Code","Description","ThisNode","SentNo","ReceivedNo")
	"DocumentJournal"            = @("Type","Ref","Date","Posted","DeletionMark","Number")
}

# Types that have StandardAttributes block
$typesWithStdAttrs = @(
	"Catalog","Document","Enum",
	"InformationRegister","AccumulationRegister","AccountingRegister","CalculationRegister",
	"ChartOfAccounts","ChartOfCharacteristicTypes","ChartOfCalculationTypes",
	"BusinessProcess","Task","ExchangePlan","DocumentJournal"
)

# ChildObjects rules: what child element types are valid for each metadata type
$childObjectRules = @{
	"Catalog"                    = @("Attribute","TabularSection","Form","Template","Command")
	"Document"                   = @("Attribute","TabularSection","Form","Template","Command")
	"ExchangePlan"               = @("Attribute","TabularSection","Form","Template","Command")
	"ChartOfAccounts"            = @("Attribute","TabularSection","Form","Template","Command","AccountingFlag","ExtDimensionAccountingFlag")
	"ChartOfCharacteristicTypes" = @("Attribute","TabularSection","Form","Template","Command")
	"ChartOfCalculationTypes"    = @("Attribute","TabularSection","Form","Template","Command")
	"BusinessProcess"            = @("Attribute","TabularSection","Form","Template","Command")
	"Task"                       = @("Attribute","TabularSection","Form","Template","Command","AddressingAttribute")
	"Report"                     = @("Attribute","TabularSection","Form","Template","Command")
	"DataProcessor"              = @("Attribute","TabularSection","Form","Template","Command")
	"Enum"                       = @("EnumValue","Form","Template","Command")
	"InformationRegister"        = @("Dimension","Resource","Attribute","Form","Template","Command")
	"AccumulationRegister"       = @("Dimension","Resource","Attribute","Form","Template","Command")
	"AccountingRegister"         = @("Dimension","Resource","Attribute","Form","Template","Command")
	"CalculationRegister"        = @("Dimension","Resource","Attribute","Form","Template","Command","Recalculation")
	"DocumentJournal"            = @("Column","Form","Template","Command")
	"HTTPService"                = @("URLTemplate")
	"WebService"                 = @("Operation")
	"Constant"                   = @("Form")
	"DefinedType"                = @()
	"CommonModule"               = @()
	"ScheduledJob"               = @()
	"EventSubscription"          = @()
}

# Группы командного интерфейса (зеркало meta-compile): раздела — без commandParameterType; формы — с параметром.
$sectionCommandGroups = @("NavigationPanelImportant","NavigationPanelOrdinary","NavigationPanelSeeAlso","ActionsPanelCreate","ActionsPanelReports","ActionsPanelTools")
$formCommandGroups    = @("FormCommandBarImportant","FormCommandBarCreateBasedOn","FormNavigationPanelImportant","FormNavigationPanelGoTo","FormNavigationPanelSeeAlso")
$validCommandGroups   = $sectionCommandGroups + $formCommandGroups

# Valid enum property values
$validPropertyValues = @{
	"CodeType"                       = @("String","Number")
	"CodeAllowedLength"              = @("Variable","Fixed")
	"NumberType"                     = @("String","Number")
	"NumberAllowedLength"            = @("Variable","Fixed")
	"Posting"                        = @("Allow","Deny")
	"RealTimePosting"                = @("Allow","Deny")
	"RegisterRecordsDeletion"        = @("AutoDelete","AutoDeleteOnUnpost","AutoDeleteOff")
	"RegisterRecordsWritingOnPost"   = @("WriteModified","WriteSelected","WriteAll")
	"DataLockControlMode"            = @("Automatic","Managed")
	"FullTextSearch"                 = @("Use","DontUse")
	"DefaultPresentation"            = @("AsDescription","AsCode")
	"HierarchyType"                  = @("HierarchyFoldersAndItems","HierarchyOfItems")
	"EditType"                       = @("InDialog","InList","BothWays")
	"WriteMode"                      = @("Independent","RecorderSubordinate")
	"InformationRegisterPeriodicity" = @("Nonperiodical","Second","Day","Month","Quarter","Year","RecorderPosition")
	"RegisterType"                   = @("Balance","Turnovers")
	"ReturnValuesReuse"              = @("DontUse","DuringRequest","DuringSession")
	"ReuseSessions"                  = @("DontUse","AutoUse")
	"FillChecking"                   = @("DontCheck","ShowError","ShowWarning")
	"Indexing"                       = @("DontIndex","Index","IndexWithAdditionalOrder")
	"DataHistory"                    = @("Use","DontUse")
	"DependenceOnCalculationTypes"   = @("DontUse","OnActionPeriod")
}

# Properties forbidden per type (would cause LoadConfigFromFiles error)
$forbiddenProperties = @{
	"ChartOfCharacteristicTypes" = @("CodeType")
	"ChartOfAccounts"            = @("Autonumbering","Hierarchical")
	"ChartOfCalculationTypes"    = @("CheckUnique","Autonumbering")
	"ExchangePlan"               = @("CodeType","CheckUnique","Autonumbering")
	# Local: the periodicity property is InformationRegisterPeriodicity, and an
	# information register has no record-set default form.
	"InformationRegister"        = @("Periodicity","DefaultRecordSetForm")
}

# GeneratedType names that do not follow <Type><Category>.<Name> (Designer dumps).
$generatedTypePrefixExceptions = @{
	"DefinedType|DefinedType"                                  = "DefinedType"
	"ChartOfCharacteristicTypes|Characteristic"                = "Characteristic"
	"CalculationRegister|Recalcs"                              = "RecalculationsManager"
	"ChartOfCalculationTypes|DisplacingCalculationTypes"       = "DisplacingCalculationTypes"
	"ChartOfCalculationTypes|DisplacingCalculationTypesRow"    = "DisplacingCalculationTypesRow"
	"ChartOfCalculationTypes|BaseCalculationTypes"             = "BaseCalculationTypes"
	"ChartOfCalculationTypes|BaseCalculationTypesRow"          = "BaseCalculationTypesRow"
	"ChartOfCalculationTypes|LeadingCalculationTypes"          = "LeadingCalculationTypes"
	"ChartOfCalculationTypes|LeadingCalculationTypesRow"       = "LeadingCalculationTypesRow"
}

# Export folder names that are sometimes written where a type belongs
# (cfg:Catalogs.X instead of cfg:CatalogRef.X) -> the reference type, if any.
$exportFolderTypes = @{
	"Catalogs" = "CatalogRef"; "Documents" = "DocumentRef"; "Enums" = "EnumRef"
	"ChartsOfAccounts" = "ChartOfAccountsRef"
	"ChartsOfCharacteristicTypes" = "ChartOfCharacteristicTypesRef"
	"ChartsOfCalculationTypes" = "ChartOfCalculationTypesRef"
	"BusinessProcesses" = "BusinessProcessRef"; "ExchangePlans" = "ExchangePlanRef"
	"Tasks" = "TaskRef"; "DefinedTypes" = "DefinedType"
	"InformationRegisters" = ""; "AccumulationRegisters" = ""; "AccountingRegisters" = ""
	"CalculationRegisters" = ""; "Constants" = ""; "DataProcessors" = ""; "Reports" = ""
	"DocumentJournals" = ""
}
$exportFolderNames = @($exportFolderTypes.Keys)

# Default*Form / Auxiliary*Form property -> role its form must have. Choice forms are
# not role-checked: vendor configurations point DefaultChoiceForm at object forms.
$defaultFormRoles = @{
	"DefaultObjectForm" = "object"; "AuxiliaryObjectForm" = "object"
	"DefaultFolderForm" = "object"; "AuxiliaryFolderForm" = "object"
	"DefaultRecordForm" = "record"; "AuxiliaryRecordForm" = "record"
	"DefaultListForm" = "list"; "AuxiliaryListForm" = "list"
}

# --- 1. Parse XML ---

Out-Line ""

$xmlDoc = $null
try {
	$xmlDoc = New-Object System.Xml.XmlDocument
	$xmlDoc.PreserveWhitespace = $false
	$xmlDoc.Load($resolvedPath)
} catch {
	Out-Line "=== Validation: (parse failed) ==="
	Out-Line ""
	Report-Error "1. XML parse failed: $($_.Exception.Message)"
	& $finalize
	exit 1
}

# --- 2. Register namespaces ---

$ns = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
$ns.AddNamespace("md", "http://v8.1c.ru/8.3/MDClasses")
$ns.AddNamespace("v8", "http://v8.1c.ru/8.1/data/core")
$ns.AddNamespace("xr", "http://v8.1c.ru/8.3/xcf/readable")
$ns.AddNamespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
$ns.AddNamespace("xs", "http://www.w3.org/2001/XMLSchema")
$ns.AddNamespace("cfg", "http://v8.1c.ru/8.1/data/enterprise/current-config")

$root = $xmlDoc.DocumentElement

# --- Check 1: Root structure ---

$check1Ok = $true

# Root must be MetaDataObject
if ($root.LocalName -ne "MetaDataObject") {
	Report-Error "1. Root element is '$($root.LocalName)', expected 'MetaDataObject'"
	& $finalize
	exit 1
}

$expectedNs = "http://v8.1c.ru/8.3/MDClasses"
if ($root.NamespaceURI -ne $expectedNs) {
	Report-Error "1. Root namespace is '$($root.NamespaceURI)', expected '$expectedNs'"
	$check1Ok = $false
}

# Version attribute
$version = $root.GetAttribute("version")
if (-not $version) {
	Report-Warn "1. Missing version attribute on MetaDataObject"
} elseif ($script:configVersion -and $version -ne $script:configVersion) {
	Report-Error "1e. Format version '$version' differs from Configuration.xml ($($script:configVersion)) — the Configurator refuses to load a dump with mixed format versions"
	$check1Ok = $false
} elseif ($version -ne "2.17" -and $version -ne "2.20") {
	Report-Warn "1. Unusual version '$version' (expected 2.17 or 2.20)"
}

# Detect type element — exactly one child element in md namespace
$typeNode = $null
$mdType = ""
$childElements = @()
foreach ($child in $root.ChildNodes) {
	if ($child.NodeType -eq 'Element' -and $child.NamespaceURI -eq $expectedNs) {
		$childElements += $child
	}
}

if ($childElements.Count -eq 0) {
	Report-Error "1. No metadata type element found inside MetaDataObject"
	& $finalize
	exit 1
} elseif ($childElements.Count -gt 1) {
	Report-Error "1. Multiple type elements found: $($childElements | ForEach-Object { $_.LocalName })"
	$check1Ok = $false
}

$typeNode = $childElements[0]
$mdType = $typeNode.LocalName

if (($validTypes -notcontains $mdType) -and ($structuralOnlyTypes -notcontains $mdType)) {
	Report-Error "1. Unrecognized metadata type: $mdType"
	& $finalize
	exit 1
}

# UUID on type element
$typeUuid = $typeNode.GetAttribute("uuid")
if (-not $typeUuid) {
	Report-Error "1. Missing uuid on <$mdType> element"
	$check1Ok = $false
} elseif ($typeUuid -notmatch $guidPattern) {
	Report-Error "1. Invalid uuid '$typeUuid' on <$mdType>"
	$check1Ok = $false
}

# Get object name early for header
$propsNode = $typeNode.SelectSingleNode("md:Properties", $ns)
$nameNode = if ($propsNode) { $propsNode.SelectSingleNode("md:Name", $ns) } else { $null }
$objName = if ($nameNode -and $nameNode.InnerText) { $nameNode.InnerText } else { "(unknown)" }

# Now emit header
$script:output.Insert(0, "=== Validation: $mdType.$objName ===$([Environment]::NewLine)") | Out-Null

if ($check1Ok) {
	Report-OK "1. Root structure: MetaDataObject/$mdType, version $version"
}

# --- Structural-only types: базовая проверка (Name), без type-specific правил ---
if ($structuralOnlyTypes -contains $mdType) {
	if ($objName -eq "(unknown)") {
		Report-Error "3. Properties: missing or empty Name"
	} elseif ($objName -notmatch $identPattern) {
		Report-Error "3. Properties: Name '$objName' is not a valid 1C identifier"
	} else {
		Report-OK "3. Properties: Name=`"$objName`" (базовая структурная проверка для $mdType)"
	}
	& $finalize
	if ($script:errors -gt 0) { exit 1 }
	exit 0
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 2: InternalInfo ---

$internalInfo = $typeNode.SelectSingleNode("md:InternalInfo", $ns)

if ($typesWithoutInternalInfo -contains $mdType) {
	# These types should NOT have InternalInfo with GeneratedType
	if ($internalInfo) {
		$genTypes = $internalInfo.SelectNodes("xr:GeneratedType", $ns)
		if ($genTypes.Count -gt 0) {
			Report-Warn "2. InternalInfo: $mdType should not have GeneratedType entries, found $($genTypes.Count)"
		} else {
			Report-OK "2. InternalInfo: absent or empty (correct for $mdType)"
		}
	} else {
		Report-OK "2. InternalInfo: absent (correct for $mdType)"
	}
} elseif ($generatedTypeCategories.ContainsKey($mdType)) {
	$expectedCategories = $generatedTypeCategories[$mdType]
	if (-not $internalInfo) {
		Report-Error "2. InternalInfo: missing (expected $($expectedCategories.Count) GeneratedType)"
	} else {
		$genTypes = $internalInfo.SelectNodes("xr:GeneratedType", $ns)
		$check2Ok = $true
		$foundCategories = @()

		foreach ($gt in $genTypes) {
			$gtName = $gt.GetAttribute("name")
			$gtCategory = $gt.GetAttribute("category")
			$foundCategories += $gtCategory

			# Validate name format: exactly <Type><Category>.<Name> for a known category
			if ($gtName -and $objName -ne "(unknown)") {
				if ($expectedCategories -ccontains $gtCategory) {
					$exceptionKey = "$mdType|$gtCategory"
					$gtPrefix = if ($generatedTypePrefixExceptions.ContainsKey($exceptionKey)) { $generatedTypePrefixExceptions[$exceptionKey] } else { "$mdType$gtCategory" }
					$expectedGtName = "$gtPrefix.$objName"
					if ($gtName -cne $expectedGtName) {
						Report-Error "2. GeneratedType '$gtCategory' name '$gtName' — expected '$expectedGtName'"
						$check2Ok = $false
					}
				} elseif (-not $gtName.EndsWith(".$objName")) {
					Report-Error "2. GeneratedType name '$gtName' does not end with '.$objName'"
					$check2Ok = $false
				}
			}

			# Validate category
			if ($expectedCategories -notcontains $gtCategory) {
				Report-Warn "2. Unexpected GeneratedType category '$gtCategory' for $mdType"
			}

			# Validate TypeId and ValueId UUIDs
			$typeId = $gt.SelectSingleNode("xr:TypeId", $ns)
			$valueId = $gt.SelectSingleNode("xr:ValueId", $ns)
			if ($typeId -and $typeId.InnerText -notmatch $guidPattern) {
				Report-Error "2. Invalid TypeId UUID in GeneratedType '$gtCategory'"
				$check2Ok = $false
			}
			if ($valueId -and $valueId.InnerText -notmatch $guidPattern) {
				Report-Error "2. Invalid ValueId UUID in GeneratedType '$gtCategory'"
				$check2Ok = $false
			}
		}

		# ExchangePlan: check for ThisNode
		if ($mdType -eq "ExchangePlan") {
			$thisNode = $internalInfo.SelectSingleNode("xr:ThisNode", $ns)
			if (-not $thisNode) {
				Report-Warn "2. ExchangePlan missing xr:ThisNode in InternalInfo"
			} elseif ($thisNode.InnerText -notmatch $guidPattern) {
				Report-Error "2. ExchangePlan xr:ThisNode has invalid UUID"
				$check2Ok = $false
			}
		}

		# Check count mismatch
		$missingCats = @($expectedCategories | Where-Object { $foundCategories -cnotcontains $_ })
		if ($missingCats.Count -gt 0) {
			Report-Error "2. Missing GeneratedType categories: $($missingCats -join ', ') — every category of $mdType is required"
			$check2Ok = $false
		}

		if ($check2Ok) {
			$catList = ($foundCategories | Sort-Object) -join ", "
			Report-OK "2. InternalInfo: $($genTypes.Count) GeneratedType ($catList)"
		}
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 3: Properties — Name, Synonym ---

if (-not $propsNode) {
	Report-Error "3. Properties block missing"
} else {
	$check3Ok = $true

	# Name
	if (-not $nameNode -or -not $nameNode.InnerText) {
		Report-Error "3. Properties: Name is missing or empty"
		$check3Ok = $false
	} else {
		$nameVal = $nameNode.InnerText
		if ($nameVal -notmatch $identPattern) {
			Report-Error "3. Properties: Name '$nameVal' is not a valid 1C identifier"
			$check3Ok = $false
		}
		if ($nameVal.Length -gt 80) {
			Report-Warn "3. Properties: Name '$nameVal' is longer than 80 characters ($($nameVal.Length))"
		}
	}

	# Synonym
	$synNode = $propsNode.SelectSingleNode("md:Synonym", $ns)
	$synPresent = $false
	if ($synNode) {
		$synItem = $synNode.SelectSingleNode("v8:item", $ns)
		if ($synItem) {
			$synContent = $synItem.SelectSingleNode("v8:content", $ns)
			if ($synContent -and $synContent.InnerText) {
				$synPresent = $true
			}
		}
	}

	if ($check3Ok) {
		$synInfo = if ($synPresent) { "Synonym present" } else { "no Synonym" }
		Report-OK "3. Properties: Name=`"$objName`", $synInfo"
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 4: Property values — enum properties ---

if ($propsNode) {
	$enumChecked = 0
	$check4Ok = $true

	foreach ($propName in $validPropertyValues.Keys) {
		$propNode = $propsNode.SelectSingleNode("md:$propName", $ns)
		if ($propNode -and $propNode.InnerText) {
			$val = $propNode.InnerText
			$allowed = $validPropertyValues[$propName]
			if ($allowed -notcontains $val) {
				Report-Error "4. Property '$propName' has invalid value '$val' (allowed: $($allowed -join ', '))"
				$check4Ok = $false
			}
			$enumChecked++
		}
	}

	# Корневой <Type> (дескриптор типа значения — Константа, ПВХ) должен быть структурным:
	# <v8:Type>/<v8:TypeSet>, а не скалярный текст. Скаляр = повреждённый тип (напр. после
	# старого meta-edit modify-property Type). См. issue #42.
	$rootTypeEl = $propsNode.SelectSingleNode("md:Type", $ns)
	if ($rootTypeEl) {
		$v8Types = $rootTypeEl.SelectNodes("v8:Type", $ns)
		$v8TypeSets = $rootTypeEl.SelectNodes("v8:TypeSet", $ns)
		$scalarText = ""
		foreach ($cn in $rootTypeEl.ChildNodes) {
			if ($cn.NodeType -eq 'Text' -or $cn.NodeType -eq 'CDATA') {
				$t = $cn.Value.Trim()
				if ($t) { $scalarText = $t; break }
			}
		}
		if ($v8Types.Count -eq 0 -and $v8TypeSets.Count -eq 0 -and $scalarText) {
			Report-Error "4. Property <Type> содержит скалярный текст '$scalarText' без структуры типа (<v8:Type>/<v8:TypeSet>) — повреждённый дескриптор типа значения"
			$check4Ok = $false
		}
	}

	if ($check4Ok) {
		Report-OK "4. Property values: $enumChecked enum properties checked"
	}
} else {
	Report-Warn "4. No Properties block to check"
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 5: StandardAttributes ---

if ($typesWithStdAttrs -contains $mdType) {
	$stdAttrNode = $propsNode.SelectSingleNode("md:StandardAttributes", $ns)
	if (-not $stdAttrNode) {
		# StandardAttributes block is optional for some types (e.g. Enum)
		Report-OK "5. StandardAttributes: absent (optional for $mdType)"
	} else {
		$stdAttrs = $stdAttrNode.SelectNodes("xr:StandardAttribute", $ns)
		$expectedStdAttrs = $standardAttributesByType[$mdType]
		$check5Ok = $true

		$foundNames = @()
		foreach ($sa in $stdAttrs) {
			$saName = $sa.GetAttribute("name")
			if ($saName) {
				$foundNames += $saName
				if ($expectedStdAttrs -notcontains $saName) {
					# AccountingRegister has dynamic ExtDimension{N}/ExtDimensionType{N} and optional PeriodAdjustment
					$isDynamic = ($mdType -eq "AccountingRegister" -and ($saName -match '^ExtDimension\d+$' -or $saName -match '^ExtDimensionType\d+$' -or $saName -eq "PeriodAdjustment"))
					# CalculationRegister has conditional period attrs
					$isCalcDynamic = ($mdType -eq "CalculationRegister" -and $saName -in @("ActionPeriod","BegOfActionPeriod","EndOfActionPeriod","BegOfBasePeriod","EndOfBasePeriod"))
					if (-not $isDynamic -and -not $isCalcDynamic) {
						Report-Warn "5. Unexpected StandardAttribute '$saName' for $mdType"
					}
				}
			} else {
				Report-Error "5. StandardAttribute without 'name' attribute"
				$check5Ok = $false
			}
		}

		if ($expectedStdAttrs) {
			$missingAttrs = @($expectedStdAttrs | Where-Object { $foundNames -notcontains $_ })
			if ($missingAttrs.Count -gt 0) {
				Report-Warn "5. Missing StandardAttributes: $($missingAttrs -join ', ')"
			}
		}

		if ($check5Ok) {
			Report-OK "5. StandardAttributes: $($stdAttrs.Count) entries"
		}
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 6: ChildObjects — allowed element types ---

$childObjNode = $typeNode.SelectSingleNode("md:ChildObjects", $ns)
$allowedChildren = $childObjectRules[$mdType]

if ($childObjNode) {
	$check6Ok = $true
	$childCounts = @{}

	foreach ($child in $childObjNode.ChildNodes) {
		if ($child.NodeType -ne 'Element') { continue }
		$childTag = $child.LocalName

		if ($allowedChildren -notcontains $childTag) {
			Report-Error "6. ChildObjects: disallowed element '$childTag' for $mdType"
			$check6Ok = $false
		}

		if (-not $childCounts.ContainsKey($childTag)) {
			$childCounts[$childTag] = 0
		}
		$childCounts[$childTag]++
	}

	if ($check6Ok) {
		$summary = ($childCounts.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)($($_.Value))" }) -join ", "
		if ($summary) {
			Report-OK "6. ChildObjects types: $summary"
		} else {
			Report-OK "6. ChildObjects: empty (valid for $mdType)"
		}
	}
} elseif ($allowedChildren.Count -eq 0) {
	Report-OK "6. ChildObjects: absent (correct for $mdType)"
} else {
	# Some types may have no children — that's OK
	Report-OK "6. ChildObjects: absent"
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 6a/6b (local): form registrations are references, and they resolve ---
#
# A form is registered in ChildObjects as a scalar reference — <Form>Name</Form> —
# and described by its own file, <ObjectDir>/Forms/<Name>.xml. Both halves are
# needed and neither was checked: an inline <Form uuid=...><Properties>… block
# (what a generic child builder produces) and a reference with no file behind it
# both passed as valid, and the defect only surfaced when the Configurator tried
# to load the dump.

if ($childObjNode) {
	$formNodes = @($childObjNode.ChildNodes | Where-Object { $_.NodeType -eq 'Element' -and $_.LocalName -eq 'Form' })
	if ($formNodes.Count -gt 0) {
		$objectDir = Join-Path (Split-Path $resolvedPath -Parent) ([System.IO.Path]::GetFileNameWithoutExtension($resolvedPath))
		$formsDir = Join-Path $objectDir 'Forms'
		$check6aOk = $true
		$check6bOk = $true
		$check6cOk = $true
		$check6dOk = $true
		$resolvedForms = 0
		foreach ($formNode in $formNodes) {
			$inlineChildren = @($formNode.ChildNodes | Where-Object { $_.NodeType -eq 'Element' })
			if ($inlineChildren.Count -gt 0) {
				$inlineName = $formNode.SelectSingleNode('md:Properties/md:Name', $ns)
				$shown = if ($inlineName) { $inlineName.InnerText } else { '<без имени>' }
				Report-Error "6a. ChildObjects/Form '$shown' описана вложенным дескриптором внутри объекта. Регистрация формы — скалярная ссылка <Form>$shown</Form>, а свойства формы живут в Forms/$shown.xml. Такую выгрузку Конфигуратор не загрузит; создавайте форму навыком form-add."
				$check6aOk = $false
				continue
			}
			$formName = $formNode.InnerText.Trim()
			if (-not $formName) {
				Report-Error "6a. ChildObjects/Form: пустая регистрация формы (нет имени)"
				$check6aOk = $false
				continue
			}
			$formMeta = Join-Path $formsDir "$formName.xml"
			if (-not (Test-Path -LiteralPath $formMeta)) {
				Report-Error "6b. Форма '$formName' зарегистрирована в ChildObjects, но её описание не найдено: $formMeta"
				$check6bOk = $false
				continue
			}
			# 6c/6d: the descriptor has to be a real, matching descriptor, not just a path
			# that exists. A scaffolder that interpolates an unescaped user string writes a
			# file the Configurator cannot read, and an existence check reports that dump
			# as valid.
			$formDoc = New-Object System.Xml.XmlDocument
			try { $formDoc.Load($formMeta) }
			catch {
				Report-Error "6c. Дескриптор формы '$formName' не разбирается как XML: $formMeta — $($_.Exception.Message). Такую выгрузку Конфигуратор не загрузит."
				$check6cOk = $false
				continue
			}
			$declaredNode = $formDoc.SelectSingleNode("/*[local-name()='MetaDataObject']/*[local-name()='Form']/*[local-name()='Properties']/*[local-name()='Name']")
			$declared = if ($declaredNode) { $declaredNode.InnerText.Trim() } else { "" }
			if (-not $declared) {
				Report-Error "6d. В дескрипторе $formMeta нет Form/Properties/Name — форма '$formName' зарегистрирована, но не описана."
				$check6dOk = $false
				continue
			}
			if ($declared -cne $formName) {
				Report-Error "6d. Имя в дескрипторе не совпадает с регистрацией: $formMeta описывает '$declared', а ChildObjects ссылается на '$formName'."
				$check6dOk = $false
				continue
			}
			$resolvedForms++
		}
		if ($check6aOk) { Report-OK "6a. Form registrations: $($formNodes.Count) scalar reference(s)" }
		if ($check6bOk) { Report-OK "6b. Form descriptors: $resolvedForms of $($formNodes.Count) resolved on disk" }
		if ($check6cOk) { Report-OK "6c. Form descriptors parse as XML: $resolvedForms" }
		if ($check6dOk) { Report-OK "6d. Form descriptor names match their registration: $resolvedForms" }
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Checks 6e-6g (local): versions, default-form references, standard fields ---
#
# 6e: a form descriptor and its Form.xml carry the version of Configuration.xml.
# 6f: a Default*/Auxiliary*Form property names a form of this object that is
#     declared in ChildObjects (or an existing common form), and an object,
#     record or list slot points at a form with that role (main attribute type).
# 6g: a form whose main attribute is this object binds <Main>.Description /
#     <Main>.Code only when DescriptionLength / CodeLength is positive — with 0
#     the standard attribute does not exist.

$declaredForms = @()
if ($childObjNode) {
	foreach ($c in $childObjNode.ChildNodes) {
		if ($c.NodeType -ne 'Element' -or $c.LocalName -ne 'Form') { continue }
		if (@($c.ChildNodes | Where-Object { $_.NodeType -eq 'Element' }).Count -gt 0) { continue }
		$fn = $c.InnerText.Trim()
		if ($fn) { $declaredForms += $fn }
	}
}
$objectDirPath = Join-Path (Split-Path $resolvedPath -Parent) ([System.IO.Path]::GetFileNameWithoutExtension($resolvedPath))
$script:formRoots = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)
$lfNs = New-Object System.Xml.XmlNamespaceManager((New-Object System.Xml.NameTable))
$lfNs.AddNamespace("f", "http://v8.1c.ru/8.3/xcf/logform")
$lfNs.AddNamespace("v8", "http://v8.1c.ru/8.1/data/core")

function Get-FormXmlRoot([string]$formName) {
	# Parsed Ext/Form.xml of a declared managed form, or $null (ordinary / absent).
	# Keys are compared case-sensitively, as the Python runtime does.
	if ($script:formRoots.ContainsKey($formName)) { return $script:formRoots[$formName] }
	$path = Join-Path (Join-Path (Join-Path (Join-Path $objectDirPath "Forms") $formName) "Ext") "Form.xml"
	$rootEl = $null
	if (Test-Path -LiteralPath $path) {
		try {
			$fdoc = New-Object System.Xml.XmlDocument
			$fdoc.Load($path)
			$rootEl = $fdoc.DocumentElement
		} catch { $rootEl = $null }
	}
	$script:formRoots[$formName] = $rootEl
	return $rootEl
}

function Get-FormMainAttribute($formRoot) {
	# @{ Name; Types } of the main attribute of a managed form, or $null.
	$fns = New-Object System.Xml.XmlNamespaceManager($formRoot.OwnerDocument.NameTable)
	$fns.AddNamespace("f", "http://v8.1c.ru/8.3/xcf/logform")
	$fns.AddNamespace("v8", "http://v8.1c.ru/8.1/data/core")
	foreach ($attr in $formRoot.SelectNodes("f:Attributes/f:Attribute", $fns)) {
		$main = $attr.SelectSingleNode("f:MainAttribute", $fns)
		if ($main -and $main.InnerText.Trim() -eq "true") {
			$types = @()
			foreach ($t in $attr.SelectNodes(".//v8:Type", $fns)) { if ($t.InnerText.Trim()) { $types += $t.InnerText.Trim() } }
			return @{ Name = $attr.GetAttribute("name"); Types = $types }
		}
	}
	return $null
}

function Get-FormRole($formRoot) {
	$main = Get-FormMainAttribute $formRoot
	if (-not $main) { return "" }
	$types = @($main.Types)
	if ($types.Count -eq 1 -and $types[0] -ceq "cfg:DynamicList") { return "list" }
	if ($types.Count -eq 1 -and $types[0] -cmatch '^cfg:\w+Object\.') { return "object" }
	if ($types.Count -eq 1 -and $types[0] -cmatch '^cfg:\w+RecordManager\.') { return "record" }
	return ""
}

if ($script:configVersion -and $declaredForms.Count -gt 0) {
	$check6eOk = $true
	foreach ($formName in $declaredForms) {
		$descriptor = Join-Path (Join-Path $objectDirPath "Forms") "$formName.xml"
		if (Test-Path -LiteralPath $descriptor) {
			$dVersion = ""
			try {
				$ddoc = New-Object System.Xml.XmlDocument
				$ddoc.Load($descriptor)
				$dVersion = $ddoc.DocumentElement.GetAttribute("version")
			} catch { $dVersion = "" }
			if ($dVersion -and $dVersion -ne $script:configVersion) {
				Report-Error "6e. Form descriptor '$formName' has version '$dVersion', Configuration.xml has '$($script:configVersion)'"
				$check6eOk = $false
			}
		}
		$formRoot = Get-FormXmlRoot $formName
		if ($formRoot) {
			$fVersion = $formRoot.GetAttribute("version")
			if ($fVersion -and $fVersion -ne $script:configVersion) {
				Report-Error "6e. Form '$formName' (Ext/Form.xml) has version '$fVersion', Configuration.xml has '$($script:configVersion)'"
				$check6eOk = $false
			}
		}
	}
	if ($check6eOk) { Report-OK "6e. Form versions match Configuration.xml ($($script:configVersion)): $($declaredForms.Count) form(s)" }
}

if ($propsNode -and $objName -ne "(unknown)") {
	$check6fOk = $true
	$checkedRefs = 0
	foreach ($prop in $propsNode.ChildNodes) {
		if ($prop.NodeType -ne 'Element') { continue }
		$propName = $prop.LocalName
		if ($propName -cnotmatch '^(Default|Auxiliary)\w*Form$') { continue }
		$ref = $prop.InnerText.Trim()
		if (-not $ref) { continue }
		$checkedRefs++
		$parts = $ref.Split('.')
		if ($parts.Count -eq 2 -and $parts[0] -ceq "CommonForm") {
			if ($script:configDir -and -not (Test-Path -LiteralPath (Join-Path (Join-Path $script:configDir "CommonForms") "$($parts[1]).xml"))) {
				Report-Error "6f. $propName = '$ref': common form '$($parts[1])' not found in CommonForms/"
				$check6fOk = $false
			}
			continue
		}
		$ownPrefix = "$mdType.$objName.Form."
		if ($parts.Count -ne 4 -or -not $ref.StartsWith($ownPrefix, [System.StringComparison]::Ordinal)) {
			Report-Error "6f. $propName = '$ref': expected '$ownPrefix<Form>' or 'CommonForm.<Name>'"
			$check6fOk = $false
			continue
		}
		if ($declaredForms -cnotcontains $parts[3]) {
			Report-Error "6f. $propName = '$ref': form '$($parts[3])' is not declared in ChildObjects"
			$check6fOk = $false
			continue
		}
		if (-not $defaultFormRoles.ContainsKey($propName)) { continue }
		$expectedRole = $defaultFormRoles[$propName]
		$formRoot = Get-FormXmlRoot $parts[3]
		if (-not $formRoot) { continue }
		$actualRole = Get-FormRole $formRoot
		if ($actualRole -and $actualRole -ne $expectedRole) {
			Report-Error "6f. $propName = '$ref': the form is a $actualRole form (main attribute type), expected a $expectedRole form"
			$check6fOk = $false
		}
	}
	if ($check6fOk -and $checkedRefs -gt 0) { Report-OK "6f. Default form references: $checkedRefs resolved" }
}

if ($propsNode -and $declaredForms.Count -gt 0 -and $objName -ne "(unknown)") {
	$zeroFields = @()
	foreach ($pair in @(@("DescriptionLength", "Description"), @("CodeLength", "Code"))) {
		$lengthNode = $propsNode.SelectSingleNode("md:$($pair[0])", $ns)
		if ($lengthNode -and $lengthNode.InnerText.Trim() -eq "0") { $zeroFields += ,$pair }
	}
	if ($zeroFields.Count -gt 0) {
		$check6gOk = $true
		$ownType = "cfg:$($mdType)Object.$objName"
		foreach ($formName in $declaredForms) {
			$formRoot = Get-FormXmlRoot $formName
			if (-not $formRoot) { continue }
			$main = Get-FormMainAttribute $formRoot
			if (-not $main -or -not $main.Name) { continue }
			$mainTypes = @($main.Types)
			if ($mainTypes.Count -ne 1 -or $mainTypes[0] -cne $ownType) { continue }
			$paths = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
			foreach ($dp in $formRoot.GetElementsByTagName("DataPath", "http://v8.1c.ru/8.3/xcf/logform")) { [void]$paths.Add($dp.InnerText.Trim()) }
			foreach ($pair in $zeroFields) {
				if ($paths.Contains("$($main.Name).$($pair[1])")) {
					Report-Error "6g. Form '$formName' binds '$($main.Name).$($pair[1])', but $($pair[0])=0 — the object has no $($pair[1])"
					$check6gOk = $false
				}
			}
		}
		if ($check6gOk) { Report-OK "6g. Standard fields: no binding to a zero-length $(($zeroFields | ForEach-Object { $_[1] }) -join '/')" }
	}
}

# 6h (warning): the main object form of an object with a mandatory Description
# (DescriptionLength > 0, FillChecking ShowError — the platform default without a
# StandardAttributes block) does not show <Main>.Description, and neither the form
# module nor the object / manager module assigns it: the item cannot be written
# from that form. A warning, not an error — the value may be filled elsewhere.
if ($propsNode -and $objName -ne "(unknown)") {
	$descLengthNode = $propsNode.SelectSingleNode("md:DescriptionLength", $ns)
	$descLength = if ($descLengthNode) { $descLengthNode.InnerText.Trim() } else { "" }
	$defaultObjectNode = $propsNode.SelectSingleNode("md:DefaultObjectForm", $ns)
	$defaultObjectRef = if ($defaultObjectNode) { $defaultObjectNode.InnerText.Trim() } else { "" }
	$ownPrefix = "$mdType.$objName.Form."
	if ($descLength -match '^\d+$' -and [int]$descLength -gt 0 -and $defaultObjectRef.StartsWith($ownPrefix, [System.StringComparison]::Ordinal) -and ($declaredForms -ccontains $defaultObjectRef.Substring($ownPrefix.Length))) {
		$stdBlock = $propsNode.SelectSingleNode("md:StandardAttributes", $ns)
		$fillNode = $propsNode.SelectSingleNode("md:StandardAttributes/xr:StandardAttribute[@name='Description']/xr:FillChecking", $ns)
		$fillChecking = if ($fillNode) { $fillNode.InnerText.Trim() } elseif ($stdBlock) { "" } else { "ShowError" }
		$defaultForm = $defaultObjectRef.Substring($ownPrefix.Length)
		$formRoot = Get-FormXmlRoot $defaultForm
		if ($fillChecking -ceq "ShowError" -and $formRoot) {
			$main = Get-FormMainAttribute $formRoot
			if ($main -and $main.Name -and @($main.Types).Count -eq 1 -and @($main.Types)[0] -ceq "cfg:$($mdType)Object.$objName") {
				$paths = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
				foreach ($dp in $formRoot.GetElementsByTagName("DataPath", "http://v8.1c.ru/8.3/xcf/logform")) { [void]$paths.Add($dp.InnerText.Trim()) }
				if (-not $paths.Contains("$($main.Name).Description")) {
					$assigned = $false
					foreach ($rel in @("Forms\$defaultForm\Ext\Form\Module.bsl", "Ext\ObjectModule.bsl", "Ext\ManagerModule.bsl")) {
						$modulePath = Join-Path $objectDirPath $rel
						if (Test-Path -LiteralPath $modulePath) {
							$moduleText = [System.IO.File]::ReadAllText($modulePath, [System.Text.Encoding]::UTF8)
							if ($moduleText -match '(?im)(?:\.\s*|^[ \t]*)(?:Наименование|Description)\s*=(?!=)') { $assigned = $true; break }
						}
					}
					if (-not $assigned) {
						Report-Warn "6h. Default object form '$defaultForm' does not show '$($main.Name).Description', which is mandatory (DescriptionLength=$descLength, FillChecking=ShowError), and no module assigns it — the item cannot be written from this form"
					}
				}
			}
		}
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 7: Attributes/Dimensions/Resources/EnumValues/Columns — UUID, Name, Type ---

function Check-ChildElement {
	param(
		[System.Xml.XmlNode]$node,
		[string]$kind,
		[bool]$requireType
	)

	$uuid = $node.GetAttribute("uuid")
	if (-not $uuid) {
		Report-Error "7. $kind missing uuid"
		return $false
	} elseif ($uuid -notmatch $guidPattern) {
		Report-Error "7. $kind has invalid uuid '$uuid'"
		return $false
	}

	$elProps = $node.SelectSingleNode("md:Properties", $ns)
	if (-not $elProps) {
		Report-Error "7. $kind (uuid=$uuid) missing Properties"
		return $false
	}

	$elName = $elProps.SelectSingleNode("md:Name", $ns)
	if (-not $elName -or -not $elName.InnerText) {
		Report-Error "7. $kind (uuid=$uuid) missing or empty Name"
		return $false
	}

	$nameVal = $elName.InnerText
	if ($nameVal -notmatch $identPattern) {
		Report-Error "7. $kind '$nameVal' has invalid identifier"
		return $false
	}

	if ($requireType) {
		$typeEl = $elProps.SelectSingleNode("md:Type", $ns)
		if (-not $typeEl) {
			Report-Error "7. $kind '$nameVal' missing Type block"
			return $false
		}
		$v8Types = $typeEl.SelectNodes("v8:Type", $ns)
		$v8TypeSets = $typeEl.SelectNodes("v8:TypeSet", $ns)
		if ($v8Types.Count -eq 0 -and $v8TypeSets.Count -eq 0) {
			Report-Error "7. $kind '$nameVal' Type block has no v8:Type or v8:TypeSet"
			return $false
		}
	}

	return $true
}

if ($childObjNode) {
	$check7Ok = $true
	$check7Count = 0
	$elementKinds = @("Attribute","Dimension","Resource","EnumValue","Column")

	foreach ($kind in $elementKinds) {
		$elements = $childObjNode.SelectNodes("md:$kind", $ns)
		$requireType = ($kind -ne "EnumValue" -and $kind -ne "Column")
		foreach ($el in $elements) {
			if ($script:stopped) { break }
			$ok = Check-ChildElement -node $el -kind $kind -requireType $requireType
			if (-not $ok) { $check7Ok = $false }
			$check7Count++
		}
	}

	if ($check7Ok -and $check7Count -gt 0) {
		Report-OK "7. Child elements: $check7Count items checked (UUID, Name, Type)"
	} elseif ($check7Count -eq 0) {
		Report-OK "7. Child elements: none to check"
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 7b: Reserved attribute names (типозависимо: стандартные реквизиты ДАННОГО типа, EN+RU) ---
# Совпадение имени собственного реквизита со стандартным (англ. или рус.) платформа не примет → ошибка.

$reservedEnRu = @{
	"Ref"="Ссылка"; "DeletionMark"="ПометкаУдаления"; "Code"="Код"; "Description"="Наименование"
	"Date"="Дата"; "Number"="Номер"; "Posted"="Проведен"; "Parent"="Родитель"; "Owner"="Владелец"
	"IsFolder"="ЭтоГруппа"; "Predefined"="Предопределенный"; "PredefinedDataName"="ИмяПредопределенныхДанных"
	"Recorder"="Регистратор"; "Period"="Период"; "LineNumber"="НомерСтроки"; "Active"="Активность"
	"Order"="Порядок"; "Type"="Тип"; "OffBalance"="Забалансовый"; "RecordType"="ВидДвижения"
	"Started"="Стартован"; "Completed"="Завершен"; "HeadTask"="ВедущаяЗадача"
	"Executed"="Выполнена"; "RoutePoint"="ТочкаМаршрута"; "BusinessProcess"="БизнесПроцесс"
	"ThisNode"="ЭтотУзел"; "SentNo"="НомерОтправленного"; "ReceivedNo"="НомерПринятого"
	"CalculationType"="ВидРасчета"; "RegistrationPeriod"="ПериодРегистрации"; "ReversingEntry"="СторноЗапись"
	"Account"="Счет"; "ValueType"="ТипЗначения"; "ActionPeriodIsBasic"="ПериодДействияБазовый"
}

$stdForType = $standardAttributesByType[$mdType]
if ($childObjNode -and $stdForType) {
	# Множество зарезервированных имён (EN + RU) в нижнем регистре.
	$reservedSet = @{}
	foreach ($en in $stdForType) {
		$reservedSet[$en.ToLower()] = $true
		$ru = $reservedEnRu[$en]
		if ($ru) { $reservedSet[$ru.ToLower()] = $true }
	}
	$check7bOk = $true
	$attrNodes = $childObjNode.SelectNodes("md:Attribute", $ns)
	foreach ($attrNode in $attrNodes) {
		$attrProps = $attrNode.SelectSingleNode("md:Properties", $ns)
		if ($attrProps) {
			$attrNameNode = $attrProps.SelectSingleNode("md:Name", $ns)
			if ($attrNameNode -and $attrNameNode.InnerText) {
				$an = $attrNameNode.InnerText
				if ($reservedSet.ContainsKey($an.ToLower())) {
					Report-Error "7b. Attribute '$an' conflicts with a standard attribute of $mdType"
					$check7bOk = $false
				}
			}
		}
	}
	if ($check7bOk) {
		Report-OK "7b. Reserved attribute names: no conflicts"
	}
} elseif ($childObjNode) {
	Report-OK "7b. Reserved attribute names: no conflicts (no standard set for $mdType)"
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 8: Name uniqueness ---

function Check-Uniqueness {
	# 1C names are case-insensitive. Pass one shared $names hashtable to check several
	# kinds against each other (attributes, tabular sections, dimensions, resources
	# are fields of one object and share a namespace).
	param(
		[System.Xml.XmlNodeList]$nodes,
		[string]$kind,
		[hashtable]$names = @{}
	)

	$hasDupes = $false

	foreach ($node in $nodes) {
		$elProps = $node.SelectSingleNode("md:Properties", $ns)
		if (-not $elProps) { continue }
		$elName = $elProps.SelectSingleNode("md:Name", $ns)
		if (-not $elName -or -not $elName.InnerText) { continue }

		$nameVal = $elName.InnerText
		$key = $nameVal.ToLowerInvariant()
		if ($names.ContainsKey($key)) {
			$other = $names[$key]
			if ($other.Kind -ceq $kind -and $other.Name -ceq $nameVal) {
				Report-Error "8. Duplicate $kind name: '$nameVal'"
			} else {
				Report-Error "8. $kind '$nameVal' clashes with $($other.Kind) '$($other.Name)' — names are case-insensitive and shared by attributes, tabular sections, dimensions and resources"
			}
			$hasDupes = $true
		} else {
			$names[$key] = @{ Kind = $kind; Name = $nameVal }
		}
	}

	return (-not $hasDupes)
}

if ($childObjNode) {
	$check8Ok = $true

	# Attributes, TabularSections, Dimensions, Resources — one shared namespace
	$fieldNames = @{}
	foreach ($fieldKind in @("Attribute", "TabularSection", "Dimension", "Resource")) {
		$fieldNodes = $childObjNode.SelectNodes("md:$fieldKind", $ns)
		if ($fieldNodes.Count -gt 0) {
			if (-not (Check-Uniqueness -nodes $fieldNodes -kind $fieldKind -names $fieldNames)) { $check8Ok = $false }
		}
	}

	# EnumValues
	$evs = $childObjNode.SelectNodes("md:EnumValue", $ns)
	if ($evs.Count -gt 0) {
		if (-not (Check-Uniqueness -nodes $evs -kind "EnumValue")) { $check8Ok = $false }
	}

	# Columns (DocumentJournal)
	$cols = $childObjNode.SelectNodes("md:Column", $ns)
	if ($cols.Count -gt 0) {
		if (-not (Check-Uniqueness -nodes $cols -kind "Column")) { $check8Ok = $false }
	}

	# URLTemplates (HTTPService)
	$urlTs = $childObjNode.SelectNodes("md:URLTemplate", $ns)
	if ($urlTs.Count -gt 0) {
		if (-not (Check-Uniqueness -nodes $urlTs -kind "URLTemplate")) { $check8Ok = $false }
	}

	# Operations (WebService)
	$ops = $childObjNode.SelectNodes("md:Operation", $ns)
	if ($ops.Count -gt 0) {
		if (-not (Check-Uniqueness -nodes $ops -kind "Operation")) { $check8Ok = $false }
	}

	if ($check8Ok) {
		Report-OK "8. Name uniqueness: all names unique"
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 9: TabularSections — internal structure ---

if ($childObjNode) {
	$tsSections = $childObjNode.SelectNodes("md:TabularSection", $ns)
	if ($tsSections.Count -gt 0) {
		$check9Ok = $true
		$tsCount = 0

		foreach ($ts in $tsSections) {
			if ($script:stopped) { break }
			$tsCount++

			# UUID
			$tsUuid = $ts.GetAttribute("uuid")
			if (-not $tsUuid -or $tsUuid -notmatch $guidPattern) {
				Report-Error "9. TabularSection #${tsCount}: invalid or missing uuid"
				$check9Ok = $false
			}

			# Name
			$tsProps = $ts.SelectSingleNode("md:Properties", $ns)
			$tsNameNode = if ($tsProps) { $tsProps.SelectSingleNode("md:Name", $ns) } else { $null }
			$tsName = if ($tsNameNode) { $tsNameNode.InnerText } else { "(unnamed)" }

			if (-not $tsNameNode -or -not $tsNameNode.InnerText) {
				Report-Error "9. TabularSection #${tsCount}: missing or empty Name"
				$check9Ok = $false
			}

			# InternalInfo with 2 GeneratedType (TabularSection + TabularSectionRow)
			$tsIntInfo = $ts.SelectSingleNode("md:InternalInfo", $ns)
			if ($tsIntInfo) {
				$tsGens = $tsIntInfo.SelectNodes("xr:GeneratedType", $ns)
				if ($tsGens.Count -lt 2) {
					Report-Warn "9. TabularSection '$tsName': expected 2 GeneratedType, found $($tsGens.Count)"
				}
			}

			# Attributes inside TS
			$tsChildObj = $ts.SelectSingleNode("md:ChildObjects", $ns)
			if ($tsChildObj) {
				$tsAttrs = $tsChildObj.SelectNodes("md:Attribute", $ns)
				$tsAttrNames = @{}
				foreach ($ta in $tsAttrs) {
					$taOk = Check-ChildElement -node $ta -kind "TabularSection '$tsName'.Attribute" -requireType $true
					if (-not $taOk) { $check9Ok = $false }

					# Check name uniqueness within TS
					$taProps = $ta.SelectSingleNode("md:Properties", $ns)
					$taName = if ($taProps) { $taProps.SelectSingleNode("md:Name", $ns) } else { $null }
					if ($taName -and $taName.InnerText) {
						if ($tsAttrNames.ContainsKey($taName.InnerText)) {
							Report-Error "9. Duplicate attribute '$($taName.InnerText)' in TabularSection '$tsName'"
							$check9Ok = $false
						} else {
							$tsAttrNames[$taName.InnerText] = $true
						}
					}
				}

				# StandardAttributes of TS: expect LineNumber
				$tsStdAttr = $tsProps.SelectSingleNode("md:StandardAttributes", $ns)
				if ($tsStdAttr) {
					$tsStdAttrs = $tsStdAttr.SelectNodes("xr:StandardAttribute", $ns)
					$hasLineNumber = $false
					foreach ($tsa in $tsStdAttrs) {
						if ($tsa.GetAttribute("name") -eq "LineNumber") { $hasLineNumber = $true }
					}
					if (-not $hasLineNumber) {
						Report-Warn "9. TabularSection '$tsName': missing LineNumber StandardAttribute"
					}
				}
			}
		}

		if ($check9Ok) {
			Report-OK "9. TabularSections: $tsCount sections, structure valid"
		}
	} else {
		Report-OK "9. TabularSections: none present"
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 10: Cross-property consistency ---

$check10Ok = $true
$check10Issues = 0

if ($propsNode) {
	# HierarchyType set but Hierarchical = false
	$hierarchical = $propsNode.SelectSingleNode("md:Hierarchical", $ns)
	$hierarchyType = $propsNode.SelectSingleNode("md:HierarchyType", $ns)
	if ($hierarchical -and $hierarchyType -and $hierarchical.InnerText -eq "false" -and $hierarchyType.InnerText) {
		Report-Warn "10. HierarchyType='$($hierarchyType.InnerText)' but Hierarchical=false"
		$check10Issues++
	}

	# CommonModule: no context enabled
	if ($mdType -eq "CommonModule") {
		$contexts = @("Server","ClientManagedApplication","ClientOrdinaryApplication","ExternalConnection","ServerCall","Global")
		$anyEnabled = $false
		foreach ($ctx in $contexts) {
			$ctxNode = $propsNode.SelectSingleNode("md:$ctx", $ns)
			if ($ctxNode -and $ctxNode.InnerText -eq "true") {
				$anyEnabled = $true
				break
			}
		}
		if (-not $anyEnabled) {
			Report-Warn "10. CommonModule: no execution context enabled"
			$check10Issues++
		}
	}

	# EventSubscription: empty Handler
	if ($mdType -eq "EventSubscription") {
		$handler = $propsNode.SelectSingleNode("md:Handler", $ns)
		if (-not $handler -or -not $handler.InnerText.Trim()) {
			Report-Error "10. EventSubscription: empty Handler"
			$check10Ok = $false
			$check10Issues++
		}

		# Empty Source
		$source = $propsNode.SelectSingleNode("md:Source", $ns)
		$hasSource = $false
		if ($source) {
			$sourceTypes = $source.SelectNodes("v8:Type", $ns)
			if ($sourceTypes.Count -gt 0) { $hasSource = $true }
		}
		if (-not $hasSource) {
			Report-Warn "10. EventSubscription: no Source types specified"
			$check10Issues++
		}
	}

	# ScheduledJob: empty MethodName
	if ($mdType -eq "ScheduledJob") {
		$method = $propsNode.SelectSingleNode("md:MethodName", $ns)
		if (-not $method -or -not $method.InnerText.Trim()) {
			Report-Error "10. ScheduledJob: empty MethodName"
			$check10Ok = $false
			$check10Issues++
		}
	}

	# AccountingRegister: ChartOfAccounts must not be empty
	if ($mdType -eq "AccountingRegister") {
		$coa = $propsNode.SelectSingleNode("md:ChartOfAccounts", $ns)
		if (-not $coa -or -not $coa.InnerText.Trim()) {
			Report-Error "10. AccountingRegister: empty ChartOfAccounts"
			$check10Ok = $false
			$check10Issues++
			Write-Host "[HINT] /meta-edit -Operation modify-property -Value `"ChartOfAccounts=ChartOfAccounts.XXX`""
		}
	}

	# CalculationRegister: ChartOfCalculationTypes must not be empty
	if ($mdType -eq "CalculationRegister") {
		$coct = $propsNode.SelectSingleNode("md:ChartOfCalculationTypes", $ns)
		if (-not $coct -or -not $coct.InnerText.Trim()) {
			Report-Error "10. CalculationRegister: empty ChartOfCalculationTypes"
			$check10Ok = $false
			$check10Issues++
			Write-Host "[HINT] /meta-edit -Operation modify-property -Value `"ChartOfCalculationTypes=ChartOfCalculationTypes.XXX`""
		}
	}

	# BusinessProcess: Task should not be empty
	if ($mdType -eq "BusinessProcess") {
		$taskProp = $propsNode.SelectSingleNode("md:Task", $ns)
		if (-not $taskProp -or -not $taskProp.InnerText.Trim()) {
			Report-Warn "10. BusinessProcess: empty Task reference"
			$check10Issues++
			Write-Host "[HINT] /meta-edit -Operation modify-property -Value `"Task=Task.XXX`""
		}
	}

	# CalculationRegister: ActionPeriod=true requires non-empty Schedule
	if ($mdType -eq "CalculationRegister") {
		$actionPeriod = $propsNode.SelectSingleNode("md:ActionPeriod", $ns)
		if ($actionPeriod -and $actionPeriod.InnerText -eq "true") {
			$schedule = $propsNode.SelectSingleNode("md:Schedule", $ns)
			if (-not $schedule -or -not $schedule.InnerText.Trim()) {
				Report-Warn "10. CalculationRegister: ActionPeriod=true but Schedule is empty — platform requires a schedule register"
				$check10Issues++
			}
		}
	}

	# DocumentJournal: RegisteredDocuments should not be empty
	if ($mdType -eq "DocumentJournal") {
		$regDocs = $propsNode.SelectSingleNode("md:RegisteredDocuments", $ns)
		$hasRegDocs = $false
		if ($regDocs) {
			$items = $regDocs.SelectNodes("v8:Type", $ns)
			if ($items.Count -gt 0) { $hasRegDocs = $true }
		}
		if (-not $hasRegDocs) {
			Report-Warn "10. DocumentJournal: no RegisteredDocuments specified"
			$check10Issues++
		}
	}

	# ChartOfAccounts: ExtDimensionTypes should be set if MaxExtDimensionCount > 0
	if ($mdType -eq "ChartOfAccounts") {
		$maxExtDim = $propsNode.SelectSingleNode("md:MaxExtDimensionCount", $ns)
		if ($maxExtDim -and [int]$maxExtDim.InnerText -gt 0) {
			$edt = $propsNode.SelectSingleNode("md:ExtDimensionTypes", $ns)
			if (-not $edt -or -not $edt.InnerText.Trim()) {
				Report-Warn "10. ChartOfAccounts: MaxExtDimensionCount>0 but ExtDimensionTypes is empty"
				$check10Issues++
				Write-Host "[HINT] /meta-edit -Operation modify-property -Value `"ExtDimensionTypes=ChartOfCharacteristicTypes.XXX`""
			}
		}
	}

	# Register: must have at least one Dimension or Resource (platform rejects empty registers)
	$regTypesAll = @("AccumulationRegister","AccountingRegister","CalculationRegister","InformationRegister")
	if ($regTypesAll -contains $mdType -and $childObjNode) {
		$dims = $childObjNode.SelectNodes("md:Dimension", $ns).Count
		$ress = $childObjNode.SelectNodes("md:Resource", $ns).Count
		$attrs = $childObjNode.SelectNodes("md:Attribute", $ns).Count
		if (($dims + $ress + $attrs) -eq 0) {
			Report-Warn "10. $mdType`: no Dimensions, Resources, or Attributes — platform will reject"
			$check10Issues++
		}
	}

	# Document: RegisterRecords references should point to existing objects in config
	if ($mdType -eq "Document" -and $script:configDir) {
		$regRecords = $propsNode.SelectSingleNode("md:RegisterRecords", $ns)
		if ($regRecords) {
			$items = $regRecords.SelectNodes("xr:Item", $ns)
			foreach ($item in $items) {
				$refVal = $item.InnerText.Trim()
				if (-not $refVal) { continue }
				# Parse "AccumulationRegister.Name" → dir AccumulationRegisters/Name
				$parts = $refVal -split '\.',2
				if ($parts.Count -eq 2) {
					$refType = $parts[0]; $refName = $parts[1]
					$dirMap = @{
						"AccumulationRegister"="AccumulationRegisters"; "InformationRegister"="InformationRegisters"
						"AccountingRegister"="AccountingRegisters"; "CalculationRegister"="CalculationRegisters"
					}
					$refDir = $dirMap[$refType]
					if ($refDir) {
						$refPath = Join-Path $script:configDir "$refDir/$refName"
						$refXml = Join-Path $script:configDir "$refDir/$refName.xml"
						if (-not (Test-Path $refPath) -and -not (Test-Path $refXml)) {
							Report-Warn "10. Document.RegisterRecords references '$refVal' but object not found in config"
							$check10Issues++
						}
					}
				}
			}
		}
	}

	# Register: must have at least one registrar document
	$registerTypes = @("AccumulationRegister","AccountingRegister","CalculationRegister","InformationRegister")
	if ($registerTypes -contains $mdType -and $script:configDir -and $objName -ne "(unknown)") {
		$needsRegistrar = $true
		# InformationRegister with WriteMode=Independent does not need a registrar
		if ($mdType -eq "InformationRegister") {
			$writeMode = $propsNode.SelectSingleNode("md:WriteMode", $ns)
			if (-not $writeMode -or $writeMode.InnerText -ne "RecorderSubordinate") {
				$needsRegistrar = $false
			}
		}
		if ($needsRegistrar) {
			$regRef = "$mdType.$objName"
			$docsDir = Join-Path $script:configDir "Documents"
			$hasRegistrar = $false
			if (Test-Path $docsDir) {
				$docXmls = Get-ChildItem $docsDir -Filter "*.xml" -File -ErrorAction SilentlyContinue
				foreach ($docXml in $docXmls) {
					$content = [System.IO.File]::ReadAllText($docXml.FullName, [System.Text.Encoding]::UTF8)
					if ($content.Contains($regRef)) {
						$hasRegistrar = $true
						break
					}
				}
			}
			if (-not $hasRegistrar) {
				Report-Warn "10. $mdType`: no registrar document found (none references '$regRef' in RegisterRecords)"
				$check10Issues++
			}
		}
	}
}

if ($check10Ok -and $check10Issues -eq 0) {
	Report-OK "10. Cross-property consistency"
} elseif ($check10Ok) {
	# Had warnings but no errors — already reported
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 11: HTTPService/WebService nested structure ---

if ($mdType -eq "HTTPService" -and $childObjNode) {
	$urlTemplates = $childObjNode.SelectNodes("md:URLTemplate", $ns)
	$check11Ok = $true
	$methodCount = 0

	$validHTTPMethods = @("GET","POST","PUT","DELETE","PATCH","HEAD","OPTIONS","MERGE","CONNECT")

	foreach ($ut in $urlTemplates) {
		if ($script:stopped) { break }

		$utProps = $ut.SelectSingleNode("md:Properties", $ns)
		$utNameNode = if ($utProps) { $utProps.SelectSingleNode("md:Name", $ns) } else { $null }
		$utName = if ($utNameNode) { $utNameNode.InnerText } else { "(unnamed)" }

		# Template property
		$tpl = if ($utProps) { $utProps.SelectSingleNode("md:Template", $ns) } else { $null }
		if (-not $tpl -or -not $tpl.InnerText.Trim()) {
			Report-Error "11. HTTPService URLTemplate '$utName': empty Template"
			$check11Ok = $false
		}

		# Methods inside URLTemplate
		$utChildObj = $ut.SelectSingleNode("md:ChildObjects", $ns)
		if ($utChildObj) {
			$methods = $utChildObj.SelectNodes("md:Method", $ns)
			foreach ($m in $methods) {
				$methodCount++
				$mProps = $m.SelectSingleNode("md:Properties", $ns)
				if ($mProps) {
					$httpMethod = $mProps.SelectSingleNode("md:HTTPMethod", $ns)
					if ($httpMethod -and $httpMethod.InnerText) {
						if ($validHTTPMethods -notcontains $httpMethod.InnerText) {
							Report-Error "11. HTTPService URLTemplate '$utName': invalid HTTPMethod '$($httpMethod.InnerText)'"
							$check11Ok = $false
						}
					} else {
						Report-Error "11. HTTPService URLTemplate '$utName': Method missing HTTPMethod"
						$check11Ok = $false
					}
				}
			}
		}
	}

	if ($check11Ok) {
		Report-OK "11. HTTPService: $($urlTemplates.Count) URLTemplate(s), $methodCount method(s)"
	}
} elseif ($mdType -eq "WebService" -and $childObjNode) {
	$operations = $childObjNode.SelectNodes("md:Operation", $ns)
	$check11Ok = $true
	$paramCount = 0

	$validDirections = @("In","Out","InOut")

	foreach ($op in $operations) {
		if ($script:stopped) { break }

		$opProps = $op.SelectSingleNode("md:Properties", $ns)
		$opNameNode = if ($opProps) { $opProps.SelectSingleNode("md:Name", $ns) } else { $null }
		$opName = if ($opNameNode) { $opNameNode.InnerText } else { "(unnamed)" }

		# ReturnType — XDTOReturningValueType
		$retType = if ($opProps) { $opProps.SelectSingleNode("md:XDTOReturningValueType", $ns) } else { $null }
		if (-not $retType -or -not $retType.InnerText.Trim()) {
			Report-Warn "11. WebService Operation '$opName': no XDTOReturningValueType"
		}

		# Parameters inside Operation
		$opChildObj = $op.SelectSingleNode("md:ChildObjects", $ns)
		if ($opChildObj) {
			$params = $opChildObj.SelectNodes("md:Parameter", $ns)
			foreach ($p in $params) {
				$paramCount++
				$pProps = $p.SelectSingleNode("md:Properties", $ns)
				if ($pProps) {
					$dir = $pProps.SelectSingleNode("md:TransferDirection", $ns)
					if ($dir -and $dir.InnerText -and $validDirections -notcontains $dir.InnerText) {
						Report-Error "11. WebService Operation '$opName': Parameter has invalid TransferDirection '$($dir.InnerText)'"
						$check11Ok = $false
					}
				}
			}
		}
	}

	if ($check11Ok) {
		Report-OK "11. WebService: $($operations.Count) operation(s), $paramCount parameter(s)"
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 12: Forbidden properties per type ---

if ($propsNode -and $forbiddenProperties.ContainsKey($mdType)) {
	$forbidden = $forbiddenProperties[$mdType]
	$check12Ok = $true
	foreach ($fp in $forbidden) {
		$fpNode = $propsNode.SelectSingleNode("md:$fp", $ns)
		if ($fpNode) {
			Report-Error "12. Forbidden property '$fp' present in $mdType (will fail on LoadConfigFromFiles)"
			$check12Ok = $false
		}
	}
	if ($check12Ok) {
		Report-OK "12. Forbidden properties: none found"
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 13: Method reference validation (EventSubscription.Handler, ScheduledJob.MethodName) ---

if ($propsNode -and $mdType -in @("EventSubscription","ScheduledJob") -and $script:configDir) {
	$check13Ok = $true
	$methodRef = $null
	$propLabel = $null

	if ($mdType -eq "EventSubscription") {
		$hNode = $propsNode.SelectSingleNode("md:Handler", $ns)
		if ($hNode) { $methodRef = $hNode.InnerText.Trim() }
		$propLabel = "Handler"
	} elseif ($mdType -eq "ScheduledJob") {
		$mNode = $propsNode.SelectSingleNode("md:MethodName", $ns)
		if ($mNode) { $methodRef = $mNode.InnerText.Trim() }
		$propLabel = "MethodName"
	}

	if ($methodRef) {
		$parts = $methodRef.Split('.')
		# Format: CommonModule.ModuleName.ProcedureName (3 parts) or ModuleName.ProcedureName (2 parts, legacy)
		if ($parts.Count -eq 3 -and $parts[0] -eq "CommonModule") {
			$cmName = $parts[1]
			$procName = $parts[2]
		} elseif ($parts.Count -eq 2) {
			$cmName = $parts[0]
			$procName = $parts[1]
		} else {
			Report-Error "13. ${mdType}.${propLabel} = '$methodRef': expected format 'CommonModule.ModuleName.ProcedureName'"
			$check13Ok = $false
			$cmName = $null
			$procName = $null
		}
		if ($cmName) {
			$cmXml = Join-Path (Join-Path $script:configDir "CommonModules") "$cmName.xml"
			if (-not (Test-Path $cmXml)) {
				Report-Error "13. ${mdType}.${propLabel}: CommonModule '$cmName' not found (expected $cmXml)"
				$check13Ok = $false
			} else {
				# Check BSL file for exported procedure
				$bslPath = Join-Path (Join-Path (Join-Path $script:configDir "CommonModules") $cmName) "Ext/Module.bsl"
				if (Test-Path $bslPath) {
					$bslContent = [System.IO.File]::ReadAllText($bslPath, [System.Text.Encoding]::UTF8)
					# Match: Procedure/Function ProcName(...) Export or Процедура/Функция ProcName(...) Экспорт
					$exportPattern = "(?mi)^[\s]*(Procedure|Function|Процедура|Функция)\s+$([regex]::Escape($procName))\s*\(.*\)\s+(Export|Экспорт)"
					if (-not [regex]::IsMatch($bslContent, $exportPattern)) {
						Report-Warn "13. ${mdType}.${propLabel}: procedure '$procName' not found as exported in CommonModule '$cmName'"
						$check13Ok = $false
					}
				} else {
					Report-Warn "13. ${mdType}.${propLabel}: BSL file not found ($bslPath), cannot verify procedure"
				}
			}
		}
	}

	if ($check13Ok) {
		Report-OK "13. Method reference: $propLabel = '$methodRef'"
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 14: DocumentJournal Column content ---

if ($mdType -eq "DocumentJournal" -and $childObjNode) {
	$columns = $childObjNode.SelectNodes("md:Column", $ns)
	$check14Ok = $true
	$colCount = 0
	$emptyRefCount = 0

	foreach ($col in $columns) {
		$colCount++
		$colProps = $col.SelectSingleNode("md:Properties", $ns)
		$colNameNode = if ($colProps) { $colProps.SelectSingleNode("md:Name", $ns) } else { $null }
		$colName = if ($colNameNode) { $colNameNode.InnerText } else { "(unnamed)" }

		$refs = if ($colProps) { $colProps.SelectSingleNode("md:References", $ns) } else { $null }
		$hasItems = $false
		if ($refs) {
			$items = $refs.SelectNodes("xr:Item", $ns)
			if ($items.Count -gt 0) { $hasItems = $true }
		}
		if (-not $hasItems) {
			Report-Error "14. DocumentJournal Column '$colName': empty References (will fail on LoadConfigFromFiles)"
			$check14Ok = $false
			$emptyRefCount++
		}
	}

	if ($check14Ok -and $colCount -gt 0) {
		Report-OK "14. DocumentJournal Columns: $colCount column(s), all have References"
	} elseif ($colCount -eq 0) {
		Report-OK "14. DocumentJournal Columns: none"
	}
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 15: Commands — Group обязателен/валиден; секц.группа несовместима с CommandParameterType ---

if ($childObjNode) {
	$commands = $childObjNode.SelectNodes("md:Command", $ns)
	$check15Ok = $true
	$cmdCount = 0
	foreach ($cmd in $commands) {
		if ($script:stopped) { break }
		$cmdCount++
		$cuuid = $cmd.GetAttribute("uuid")
		$cmdProps = $cmd.SelectSingleNode("md:Properties", $ns)
		$cmdNameNode = if ($cmdProps) { $cmdProps.SelectSingleNode("md:Name", $ns) } else { $null }
		$cmdName = if ($cmdNameNode -and $cmdNameNode.InnerText) { $cmdNameNode.InnerText } else { "(unnamed)" }
		if (-not $cuuid -or $cuuid -notmatch $guidPattern) {
			Report-Error "15. Command '$cmdName': missing or invalid uuid"; $check15Ok = $false
		}
		if ($cmdName -eq "(unnamed)") {
			Report-Error "15. Command (uuid=$cuuid): missing or empty Name"; $check15Ok = $false
		}
		$groupNode = if ($cmdProps) { $cmdProps.SelectSingleNode("md:Group", $ns) } else { $null }
		$groupVal = if ($groupNode) { $groupNode.InnerText.Trim() } else { "" }
		if (-not $groupVal) {
			Report-Error "15. Command '$cmdName': не задана группа (Group) — 1С отвергает при загрузке"; $check15Ok = $false
		} elseif (($validCommandGroups -notcontains $groupVal) -and ($groupVal -notmatch '^CommandGroup\.')) {
			Report-Error "15. Command '$cmdName': неизвестная группа '$groupVal'. Валидные: $($validCommandGroups -join ', '); либо CommandGroup.<Имя>"; $check15Ok = $false
		} elseif ($sectionCommandGroups -contains $groupVal) {
			$cptNode = if ($cmdProps) { $cmdProps.SelectSingleNode("md:CommandParameterType", $ns) } else { $null }
			$hasCpt = $cptNode -and (($cptNode.SelectNodes("v8:Type", $ns).Count -gt 0) -or ($cptNode.SelectNodes("v8:TypeSet", $ns).Count -gt 0))
			if ($hasCpt) {
				Report-Error "15. Command '$cmdName': тип параметра (CommandParameterType) недоступен для команд командного интерфейса раздела ('$groupVal')"; $check15Ok = $false
			}
		}
	}
	if ($check15Ok -and $cmdCount -gt 0) {
		Report-OK "15. Commands: $cmdCount command(s), groups valid"
	}
}

# --- Check 16a (local): a type spelled with an export folder name ---
# cfg:Catalogs.X is the directory of the dump, not a type; the platform refuses it.
# Checked without a configuration directory: the spelling is wrong on its own.

$folderTypeValues = New-Object 'System.Collections.Generic.Dictionary[string,string]' ([System.StringComparer]::Ordinal)
foreach ($tn in $root.SelectNodes("//v8:Type | //v8:TypeSet", $ns)) {
	$tv = $tn.InnerText.Trim()
	if (-not $tv) { continue }
	$bare = if ($tv.Contains(":")) { $tv.Substring($tv.IndexOf(":") + 1) } else { $tv }
	if (-not $bare.Contains(".")) { continue }
	$headSeg = $bare.Substring(0, $bare.IndexOf("."))
	if ($exportFolderNames -ccontains $headSeg) { $folderTypeValues[$tv] = $headSeg }
}
$folderTypeKeys = [string[]]@($folderTypeValues.Keys)
[Array]::Sort($folderTypeKeys, [System.StringComparer]::Ordinal)
foreach ($tv in $folderTypeKeys) {
	$headSeg = $folderTypeValues[$tv]
	$refKind = $exportFolderTypes[$headSeg]
	$hint = if ($refKind) { " — a reference type is '$refKind.<Name>'" } else { "" }
	Report-Error "16a. Type '$tv' uses the export folder name '$headSeg' instead of a type$hint"
}

# --- Check 16: Reference type existence — типы вида CatalogRef.X должны разрешаться в объекты конфигурации ---
# WARN-уровень: ложное срабатывание на частичных выгрузках хуже пропуска. Расширения (CFE) пропускаем —
# их типы ссылаются на объекты базовой конфигурации, которых нет в выгрузке расширения.

if ($script:configDir) {
	$isExtension = $false
	$cfgXmlPath = Join-Path $script:configDir "Configuration.xml"
	if (Test-Path $cfgXmlPath) {
		$cfgContent = [System.IO.File]::ReadAllText($cfgXmlPath, [System.Text.Encoding]::UTF8)
		if ($cfgContent.Contains("ConfigurationExtensionPurpose")) { $isExtension = $true }
	}
	if (-not $isExtension) {
		$refDirMap = @{
			"CatalogRef"="Catalogs"; "DocumentRef"="Documents"; "EnumRef"="Enums"
			"ChartOfAccountsRef"="ChartsOfAccounts"; "ChartOfCharacteristicTypesRef"="ChartsOfCharacteristicTypes"
			"ChartOfCalculationTypesRef"="ChartsOfCalculationTypes"; "BusinessProcessRef"="BusinessProcesses"
			"ExchangePlanRef"="ExchangePlans"; "TaskRef"="Tasks"; "DefinedType"="DefinedTypes"
		}
		$typeNodes = $xmlDoc.SelectNodes("//v8:Type", $ns)
		$checkedRefs = @{}   # refKey -> $true если найден; для OK-условия
		$missingRefs = @{}   # refKey -> refDir
		foreach ($tn in $typeNodes) {
			$tv = $tn.InnerText.Trim()
			if (-not $tv) { continue }
			$colonIdx = $tv.IndexOf(':')
			if ($colonIdx -ge 0) { $tv = $tv.Substring($colonIdx + 1) }
			$dotIdx = $tv.IndexOf('.')
			if ($dotIdx -lt 0) { continue }
			$refCat = $tv.Substring(0, $dotIdx)
			$refName = $tv.Substring($dotIdx + 1)
			$refDir = $refDirMap[$refCat]
			if (-not $refDir -or -not $refName) { continue }
			$refKey = "$refCat.$refName"
			if ($checkedRefs.ContainsKey($refKey)) { continue }
			$refFolder = Join-Path $script:configDir (Join-Path $refDir $refName)
			$refFile = Join-Path $script:configDir (Join-Path $refDir "$refName.xml")
			if ((Test-Path $refFolder) -or (Test-Path $refFile)) {
				$checkedRefs[$refKey] = $true
			} else {
				$checkedRefs[$refKey] = $false
				$missingRefs[$refKey] = $refDir
			}
		}
		if ($missingRefs.Count -gt 0) {
			foreach ($mk in ($missingRefs.Keys | Sort-Object)) {
				Report-Warn "16. Ссылочный тип '$mk' не найден в конфигурации ($($missingRefs[$mk])/) — при загрузке будет ошибка неизвестного типа"
			}
		} elseif ($checkedRefs.Count -gt 0) {
			Report-OK "16. Reference types: $($checkedRefs.Count) resolved"
		}
	}
}

# --- Check 18: свойства, появившиеся в новых версиях формата ---
# Реестр «тег → минимальная версия формата». Служит двум целям: (1) поймать свойство в файле со
# слишком старым штампом — при сборке на старой платформе оно будет молча отброшено (платформа
# рапортует успех, а свойство теряется); (2) подсказать, что конструкция требует более нового
# формата. Расширяется одной строкой на свойство — задел под 2.21 (8.5) и последующие.
$versionedProps = @{
	"TypeReductionMode" = "2.20"   # режим приведения типов (стандартные реквизиты, измерения РС)
	"LineNumberLength"  = "2.20"   # длина номера строки ТЧ (5..9)
}
# Версия формата как число: "2.20" → 220. Строковое сравнение неверно ("2.9" > "2.17").
function Get-FormatRank([string]$v) {
	if ($v -match '^(\d+)\.(\d+)$') { return [int]$Matches[1] * 100 + [int]$Matches[2] }
	return 0
}
$fileRank = Get-FormatRank $version
if ($fileRank -gt 0) {
	foreach ($vp in ($versionedProps.Keys | Sort-Object)) {
		$nodes = $xmlDoc.SelectNodes("//md:$vp | //xr:$vp", $ns)
		if ($nodes -and $nodes.Count -gt 0 -and $fileRank -lt (Get-FormatRank $versionedProps[$vp])) {
			Report-Error "18. <$vp> появился в формате $($versionedProps[$vp]), а файл объявлен как $version — на платформе этой версии свойство будет отброшено при загрузке"
		}
	}
}

# --- Check 19: LineNumberLength — допустимый диапазон 5..9 ---
# Длина номера строки ТЧ: 5 (до 99 999 строк) … 9 (до 999 999 999). Границы — из документации 1С.
foreach ($lnl in @($xmlDoc.SelectNodes("//md:LineNumberLength", $ns))) {
	$raw = $lnl.InnerText.Trim()
	if ($raw -notmatch '^\d+$') {
		Report-Error "19. LineNumberLength='$raw' — должно быть целое число 5..9"
	} elseif ([int]$raw -lt 5 -or [int]$raw -gt 9) {
		Report-Error "19. LineNumberLength=$raw вне допустимого диапазона 5..9"
	}
}

# --- Check 17: MDObjectRef form — ссылка должна указывать на ОБЪЕКТ метаданных, а не на тип ссылки ---
# Owners/BasedOn/RegisterRecords/RegisteredDocuments/References содержат путь вида "Catalog.Валюты".
# "CatalogRef.Валюты" — частая ошибка (тип ссылки вместо объекта): платформа отвечает
# «Неизвестный объект метаданных». Вида метаданных, оканчивающегося на Ref, не существует → ERROR.
# Неизвестный первый сегмент без Ref — только WARN (список видов может быть неполон).

$mdRefNodes = $xmlDoc.SelectNodes("//*[@xsi:type='xr:MDObjectRef']", $ns)
if ($mdRefNodes -and $mdRefNodes.Count -gt 0) {
	$knownRoots = @($validTypes) + @($structuralOnlyTypes)
	$badRefForm = @{}      # значение -> $true (ссылочная форма, гарантированно нерабочая)
	$unknownRoot = @{}     # значение -> корень
	foreach ($rn in $mdRefNodes) {
		$rv = $rn.InnerText.Trim()
		if (-not $rv) { continue }
		$root = $rv.Split('.')[0]
		if ($knownRoots -ccontains $root) { continue }
		if ($root -cmatch 'Ref$') { $badRefForm[$rv] = $true } else { $unknownRoot[$rv] = $root }
	}
	foreach ($bk in ($badRefForm.Keys | Sort-Object)) {
		$fixed = $bk -replace '^([A-Za-z]+)Ref\.', '$1.'
		Report-Error "17. MDObjectRef '$bk' — ссылка на ТИП, а не на объект метаданных; нужно '$fixed' (иначе «Неизвестный объект метаданных» при загрузке)"
	}
	foreach ($uk in ($unknownRoot.Keys | Sort-Object)) {
		Report-Warn "17. MDObjectRef '$uk' — неизвестный вид метаданных '$($unknownRoot[$uk])' (опечатка?)"
	}
	if ($badRefForm.Count -eq 0 -and $unknownRoot.Count -eq 0) {
		Report-OK "17. MDObjectRef form: $($mdRefNodes.Count) checked"
	}
}

# --- Final output ---

& $finalize

if ($script:errors -gt 0) {
	exit 1
}
exit 0
