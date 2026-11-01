# meta-validate v1.45 — Validate 1C metadata object structure
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills
# Local (same in meta-validate.py): form registrations are scalar references
# that resolve to Forms/<Name>.xml, a descriptor that parses and declares the
# same name (6a-6d); every GeneratedType category is required and named exactly
# (2); a Default*/Auxiliary* object, record or list form has that role by its
# main attribute type (6f, on top of the reference check 20); a form binds
# Description / Code only when the length is positive (6g), and the main object
# form shows a mandatory Description nobody fills (6h, warning); names are unique
# case-insensitively across attributes, tabular sections, dimensions, resources,
# addressing attributes and accounting flags (8, one report per clash);
# InformationRegister forbids Periodicity and DefaultRecordSetForm (12); a type
# spelled with an export folder name (cfg:Catalogs.X) is an error (16a).
# Format versions follow upstream check 24 (part vs descriptor = error, object vs
# the dump = warning); the former local checks 1e / 6e are retired.
[CmdletBinding(PositionalBinding=$false)]
param(
	[Parameter(Mandatory, Position=0)]
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
		$callArgs = @{ ObjectPath = $singlePath; MaxErrors = $MaxErrors; Detailed = $Detailed }
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
	$ObjectPath = Join-Path (Get-Location).ProviderPath $ObjectPath
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

$resolvedPath = (Resolve-Path $ObjectPath).ProviderPath

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
		if ($script:stopped -and $script:errors -ge $MaxErrors) { Out-Line "Stopped after $MaxErrors errors. Fix and re-run." }
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

# --- Format version ---
# Проверенный диапазон версий формата выгрузки: 2.17 (8.3.24) … 2.21 (8.5). Полная лестница —
# docs/1c-configuration-spec.md, «Лестница версий». Версию задаёт платформа ВЫГРУЗКИ, а не режим
# совместимости конфигурации. Версии ниже 2.17 (платформы 8.3.23 и старше) существуют, но навыки
# на них не проверялись — это предупреждение о непокрытии, а не о некорректности файла.
$formatVerifiedMin = "2.17"
$formatVerifiedMax = "2.21"
# Версия формата как число: "2.20" → 220. Строковое сравнение неверно ("2.9" > "2.17").
function Get-FormatRank([string]$ver) {
	if ($ver -match '^(\d+)\.(\d+)$') { return [int]$Matches[1] * 100 + [int]$Matches[2] }
	return 0
}

# Штамп версии формата — атрибут version КОРНЕВОГО элемента файла. Именно корневого: в Form.xml
# расширения ниже стоит <BaseForm version=…>. Читается только заголовок, без разбора файла.
function Get-RootVersion([string]$xmlPath) {
	if (-not (Test-Path -LiteralPath $xmlPath -PathType Leaf)) { return $null }
	$buf = New-Object byte[] 4096
	$fs = [System.IO.File]::OpenRead($xmlPath)
	try { $len = $fs.Read($buf, 0, $buf.Length) } finally { $fs.Dispose() }
	$head = [System.Text.Encoding]::UTF8.GetString($buf, 0, $len)
	$m = [regex]::Match($head, '<[A-Za-z_][\w.:-]*(\s[^>]*)?/?>')
	if (-not $m.Success) { return $null }
	$v = [regex]::Match($m.Groups[1].Value, '(?:^|\s)version="([^"]*)"')
	if ($v.Success) { return $v.Groups[1].Value }
	return $null
}

# Корень автономной внешней обработки/отчёта. Копия общего эталона (семья is_external_root,
# авторитет — cf-edit).
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

# Якорь выгрузки, в чьём дереве лежит файл: корень автономной EPF/ERF либо Configuration.xml,
# ближайший вверх. Корень обработки проверяется первым — иначе обработка, лежащая в дереве
# конфигурации, сверялась бы с конфигурацией. Нет якоря — сверять не с чем.
function Find-DumpAnchor([string]$startDir) {
	$d = $startDir
	for ($i = 0; $i -lt 15 -and $d; $i++) {
		if (Test-ExternalObjectRoot "$d.xml") { return "$d.xml" }
		$cfg = Join-Path $d "Configuration.xml"
		if (Test-Path $cfg) { return $cfg }
		$parent = [System.IO.Path]::GetDirectoryName($d)
		if (-not $parent -or $parent -eq $d) { break }
		$d = $parent
	}
	return $null
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
	"HTTPService","WebService","DefinedType",
	# Внешний источник данных и его таблица (корень файла таблицы — <Table>).
	"ExternalDataSource","Table"
)

# Валидные типы метаданных без глубоких правил валидации — раньше падали как "Unrecognized"
# (ложная ошибка на валидном объекте). Для них выполняется базовая структурная проверка (root/uuid/Name).
$structuralOnlyTypes = @(
	"Subsystem","Role","CommonForm","CommonCommand","CommandGroup","CommonAttribute",
	"CommonTemplate","CommonPicture","SessionParameter","SettingsStorage","FilterCriterion",
	"IntegrationService","Bot",
	"FunctionalOption","FunctionalOptionsParameter","Language","Style","StyleItem",
	"WSReference","XDTOPackage","DocumentNumerator","Sequence"
)

# Вложенные дескрипторы объекта: Forms/<Имя>.xml и Templates/<Имя>.xml. Корень тот же MetaDataObject,
# но в ChildObjects конфигурации они не регистрируются и первым сегментом MDObjectRef не бывают —
# в knownRoots проверки 17 их не добавлять. Принимаются, чтобы пакетный прогон по списку изменённых
# файлов не падал на них «Unrecognized».
$nestedDescriptorTypes = @("Form","Template")
# Вид формы/макета — по нему платформа выбирает читателя тела. Значения — docs/1c-configuration-spec.md,
# свойства FormType и TemplateType. Список отдельный от validPropertyValues: у авторитета meta-compile
# этих ключей нет (формы и макеты создают form-add и template-add).
$descriptorKindValues = @{
	"FormType"     = @("Managed","Ordinary")
	"TemplateType" = @("SpreadsheetDocument","BinaryData","HTMLDocument","TextDocument","ActiveDocument",
	                   "DataCompositionSchema","DataCompositionAppearanceTemplate","GraphicalSchema","GeographicalSchema","AddIn")
}

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
	"ExternalDataSource"         = @("Manager","TablesManager","CubesManager")
	# Таблица внешнего источника: имя элемента трёхчастное (Префикс.Источник.Таблица),
	# но проверка «имя оканчивается на .ИмяОбъекта» на нём работает как есть.
	"Table"                      = @("Manager","Object","Ref","List","Record","RecordSet","RecordKey","RecordManager")
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
	"AccountingRegister"         = @("Active","Period","Recorder","LineNumber","Account","PeriodAdjustment","RecordType")
	"CalculationRegister"        = @("Active","Recorder","LineNumber","RegistrationPeriod","CalculationType","ReversingEntry","ActionPeriod","BegOfActionPeriod","EndOfActionPeriod","BegOfBasePeriod","EndOfBasePeriod")
	"ChartOfAccounts"            = @("PredefinedDataName","Predefined","Ref","DeletionMark","Description","Code","Parent","Order","Type","OffBalance")
	"ChartOfCharacteristicTypes" = @("PredefinedDataName","Predefined","Ref","DeletionMark","Description","Code","Parent","IsFolder","ValueType")
	"ChartOfCalculationTypes"    = @("PredefinedDataName","Predefined","Ref","DeletionMark","Description","Code","ActionPeriodIsBasic")
	"BusinessProcess"            = @("Ref","DeletionMark","Date","Number","Started","Completed","HeadTask")
	"Task"                       = @("Ref","DeletionMark","Date","Number","Executed","Description","RoutePoint","BusinessProcess")
	"ExchangePlan"               = @("Ref","DeletionMark","Code","Description","ThisNode","SentNo","ReceivedNo","ExchangeDate")
	"DocumentJournal"            = @("Type","Ref","Date","Posted","DeletionMark","Number")
}

# Стандартные реквизиты, присутствие которых зависит от свойств объекта: у бухрегистра
# PeriodAdjustment — от длины периода корректировки, RecordType — от корреспонденции; у регистра
# накопления RecordType — от вида регистра. Их отсутствие законно, в «Missing» не попадают.
$stdAttrConditionalNames = @{
	"AccountingRegister"   = @("PeriodAdjustment","RecordType")
	"AccumulationRegister" = @("RecordType")
	# ExchangeDate — легаси-реквизит, объявлен лишь у части планов обмена: допустим, но не обязателен.
	"ExchangePlan"         = @("ExchangeDate")
}

# Types that have StandardAttributes block
$typesWithStdAttrs = @(
	"Catalog","Document","Enum",
	"InformationRegister","AccumulationRegister","AccountingRegister","CalculationRegister",
	"ChartOfAccounts","ChartOfCharacteristicTypes","ChartOfCalculationTypes",
	"BusinessProcess","Task","ExchangePlan","DocumentJournal"
)

# Имена стандартных команд вида — англ. и рус., в нижнем регистре: команда объекта с таким именем
# не загрузится («Имя команды не может совпадать с именем стандартной команды»; регистр не важен, от
# UseStandardCommands не зависит — замер 8.3.24/8.3.27). Вида нет в карте — ограничения нет
# (перечисление, план обмена; критерий отбора и таблица внешнего источника не замерены).
function Get-ReservedCommandNames {
	$openList = @("openlist", "открытьсписок")
	$create = @("create", "создать")
	$folder = @("createfolder", "создатьгруппу")
	$byValue = @("openbyvalue", "открытьпозначению")
	$basedOn = @("createbasedon", "создатьнаосновании")
	return @{
		"Catalog"                    = $openList + $create + $folder + $byValue + $basedOn
		"ChartOfCharacteristicTypes" = $openList + $create + $folder + $basedOn
		"Task"                       = $openList + $create + $byValue + $basedOn
		"Document"                   = $openList + $create + $basedOn
		"BusinessProcess"            = $openList + $create + $basedOn
		"ChartOfAccounts"            = $openList + $create + $basedOn
		"ChartOfCalculationTypes"    = $openList + $create + $basedOn
		"InformationRegister"        = $openList + $create + $byValue
		"AccumulationRegister"       = $openList
		"AccountingRegister"         = $openList
		"CalculationRegister"        = $openList
		"DocumentJournal"            = $openList
		"DataProcessor"              = @("open", "открыть")
		"Report"                     = @("open", "открыть")
	}
}

# Порядок групп в <ChildObjects> объекта по виду. Это xs:sequence <Вид>ChildObjects из MDClasses XSD,
# сверенный выгрузкой платформы: выгрузка сама ставит группы в этот порядок, так что вставка не на место
# даёт дифф при следующей выгрузке. Единого порядка нет — у документа Form стоит до TabularSection.
function Get-ObjectChildOrder {
	return @{
		"Catalog"                    = @("Attribute", "TabularSection", "Form", "Template", "Command")
		"Document"                   = @("Attribute", "Form", "TabularSection", "Template", "Command")
		"ExchangePlan"               = @("Attribute", "TabularSection", "Form", "Template", "Command")
		"ChartOfCharacteristicTypes" = @("Attribute", "TabularSection", "Form", "Template", "Command")
		"ChartOfAccounts"            = @("Attribute", "TabularSection", "AccountingFlag", "ExtDimensionAccountingFlag", "Form", "Template", "Command")
		"ChartOfCalculationTypes"    = @("Attribute", "TabularSection", "Form", "Template", "Command")
		"BusinessProcess"            = @("Attribute", "TabularSection", "Form", "Template", "Command")
		"Task"                       = @("Attribute", "TabularSection", "Form", "Template", "AddressingAttribute", "Command")
		"DataProcessor"              = @("Attribute", "TabularSection", "Form", "Template", "Command")
		"Report"                     = @("Attribute", "TabularSection", "Form", "Template", "Command")
		"ExternalDataProcessor"      = @("Attribute", "TabularSection", "Form", "Template")
		"ExternalReport"             = @("Attribute", "TabularSection", "Form", "Template")
		"Enum"                       = @("EnumValue", "Form", "Template", "Command")
		"InformationRegister"        = @("Resource", "Attribute", "Dimension", "Form", "Template", "Command")
		"AccumulationRegister"       = @("Resource", "Attribute", "Dimension", "Form", "Template", "Command")
		"AccountingRegister"         = @("Dimension", "Resource", "Attribute", "Form", "Template", "Command")
		"CalculationRegister"        = @("Resource", "Attribute", "Dimension", "Recalculation", "Form", "Template", "Command")
		"DocumentJournal"            = @("Column", "Form", "Template", "Command")
		"Table"                      = @("Field", "Form", "Command", "Template")
		"ExternalDataSource"         = @("Table", "Cube", "Function")
		"Cube"                       = @("DimensionTable", "Dimension", "Resource", "Form", "Command", "Template")
		"DimensionTable"             = @("Field", "Form", "Command", "Template")
		"FilterCriterion"            = @("Form", "Command")
		"SettingsStorage"            = @("Form", "Template")
		"TabularSection"             = @("Attribute")
	}
}


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
	# Внешний источник: таблицы перечислены именами, функции лежат полными узлами.
	"ExternalDataSource"         = @("Table","Function","Cube")
	"Table"                      = @("Field","Form","Template","Command")
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
	"RegisterRecordsWritingOnPost"   = @("WriteModified","WriteSelected")
	# AutomaticAndManaged — только у внешнего источника данных и его таблиц.
	"DataLockControlMode"            = @("Automatic","Managed","AutomaticAndManaged")
	"FullTextSearch"                 = @("Use","DontUse")
	"DefaultPresentation"            = @("AsDescription","AsCode")
	# Уточнение по виду объекта («Вид.Свойство») — раньше общего списка. AsNumber («в виде номера»)
	# есть только у задачи: у справочника и прочих платформа его отвергает (8.3.24 и 8.5.1).
	"Task.DefaultPresentation"       = @("AsDescription","AsNumber")
	"HierarchyType"                  = @("HierarchyFoldersAndItems","HierarchyOfItems")
	"EditType"                       = @("InDialog","InList","BothWays")
	"WriteMode"                      = @("Independent","RecorderSubordinate")
	"InformationRegisterPeriodicity" = @("Nonperiodical","Second","Day","Month","Quarter","Year","RecorderPosition")
	"RegisterType"                   = @("Balance","Turnovers")
	"ReturnValuesReuse"              = @("DontUse","DuringRequest","DuringSession")
	"ReuseSessions"                  = @("DontUse","Use","AutoUse")
	"FillChecking"                   = @("DontCheck","ShowError")
	"Indexing"                       = @("DontIndex","Index","IndexWithAdditionalOrder")
	"DataHistory"                    = @("Use","DontUse")
	"CreateOnInput"                  = @("Auto","Use","DontUse")
	"ChoiceHistoryOnInput"           = @("Auto","DontUse")
	"DependenceOnCalculationTypes"   = @("DontUse","OnActionPeriod","OnRegistrationPeriod")
	# Значения — по XSD платформы; не встреченные в выгрузках БП/УНФ/ERP подтверждены загрузкой и
	# выгрузкой на 8.3.24 и 8.5.1. Имя с разным смыслом у разных владельцев — только ключом «Контекст.Свойство».
	"ChoiceFoldersAndItems"             = @("Items","Folders","FoldersAndItems")
	"NumberPeriodicity"                 = @("Nonperiodical","Year","Quarter","Month","Day")
	"ParameterUseMode"                  = @("Single","Multiple")
	"Representation"                    = @("Auto","Text","Picture","PictureAndText")
	"OnMainServerUnavalableBehavior"    = @("Auto","MakeDisable","DontChangeBehavior")
	"FormType"                          = @("Managed","Ordinary")
	"MoveBoundaryOnPosting"             = @("DontMove","Move")
	"SequenceFilling"                   = @("AutoFill","AutoFillOff")
	"TaskNumberAutoPrefix"              = @("BusinessProcessNumber","DontUse")
	"AutoUse"                           = @("DontUse","Use")
	"DataSeparation"                    = @("DontUse","Separate")
	"UsersSeparation"                   = @("DontUse","Separate")
	"AuthenticationSeparation"          = @("DontUse","Separate")
	"ConfigurationExtensionsSeparation" = @("DontUse","Separate")
	"SeparatedDataUse"                  = @("Independently","IndependentlyAndSimultaneously")
	"TemplateType"                      = @("SpreadsheetDocument","BinaryData","ActiveDocument","HTMLDocument","TextDocument","GeographicalSchema","GraphicalSchema","DataCompositionSchema","DataCompositionAppearanceTemplate","AddIn")
	"UseInInterfaceCompatibilityMode"   = @("Any","Taxi","Version85")
	"TypeReductionMode"                 = @("TransformValues","DeleteData","Deny")
	"TransactionsIsolationLevel"        = @("Auto","ReadUncommitted","ReadCommitted","RepeatableRead","Serializable")
	"TableType"                         = @("Table","Expression")
	"TableDataType"                     = @("NonobjectData","ObjectData")
	"ChoiceDataGetModeOnInputByString"  = @("Directly","Background")
	"HTTPMethod"                        = @("GET","HEAD","PUT","POST","DELETE","PATCH","MERGE","OPTIONS","TRACE","CONNECT","PROPFIND","PROPPATCH","MOVE","COPY","LOCK","UNLOCK","MKCOL","Any")
	"TransferDirection"                 = @("In","Out","InOut")
	"ValueChange"                       = @("Clear","DontChange")
	# QuickChoice у справочника и других ссылочных — булево; перечислением он бывает здесь:
	"Constant.QuickChoice"              = @("Auto","Use","DontUse")
	"CommonAttribute.QuickChoice"       = @("Auto","Use","DontUse")
	"Attribute.QuickChoice"             = @("Auto","Use","DontUse")
	# Use: у реквизита и ТЧ — для групп/элементов; у состава общего реквизита — Auto/Use/DontUse;
	# у регламентного задания — булево, у параметра функциональных опций — список (общего ключа нет).
	"Attribute.Use"                     = @("ForItem","ForFolder","ForFolderAndItem")
	"TabularSection.Use"                = @("ForItem","ForFolder","ForFolderAndItem")
	"CommonAttributeContent.Use"        = @("Auto","Use","DontUse")
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
$versionRank = Get-FormatRank $version
if (-not $version) {
	Report-Warn "1. Missing version attribute on MetaDataObject"
} elseif ($versionRank -eq 0) {
	Report-Error "1. Malformed version '$version' (expected N.N)"
} elseif ($versionRank -lt (Get-FormatRank $formatVerifiedMin)) {
	Report-Warn "1. Format version '$version' is below the tested range $formatVerifiedMin-$formatVerifiedMax — skills were not verified on it"
} elseif ($versionRank -gt (Get-FormatRank $formatVerifiedMax)) {
	Report-Warn "1. Format version '$version' is above the tested range $formatVerifiedMin-$formatVerifiedMax — skills were not verified on it"
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

if (($validTypes -notcontains $mdType) -and ($structuralOnlyTypes -notcontains $mdType) -and ($nestedDescriptorTypes -notcontains $mdType)) {
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

# --- Check 24: версия формата согласована внутри объекта; сверка с выгрузкой ---
# Части объекта — дескриптор X.xml и штампованные тела X/Ext/*.xml — платформа загружает только в одной
# версии: «Версия формата загружаемого файла … отличается от версии формата ранее загруженных файлов».
# Формы и макеты объекта (Forms/F.xml + F/Ext/Form.xml, Templates/T.xml + T/Ext/Template.xml) — такие же
# пары, проверяются вместе с объектом. Объекты разных версий между собой платформа грузит, это лишь неоднородность выгрузки (типично после
# мержа веток, выгруженных разными платформами) — поэтому сверка с выгрузкой только предупреждает.
# Стоит до ранних выходов: нужна каждому корню, включая structural-only и вложенные дескрипторы.
$objBaseDir = Split-Path $resolvedPath
$objDir = Join-Path $objBaseDir ([System.IO.Path]::GetFileNameWithoutExtension($resolvedPath))
$verDescriptors = @($resolvedPath)
foreach ($sub in @("Forms","Templates")) {
	$subDir = Join-Path $objDir $sub
	if (-not (Test-Path $subDir -PathType Container)) { continue }
	$names = @(Get-ChildItem $subDir -Filter "*.xml" -File | ForEach-Object { $_.Name })
	[Array]::Sort($names, [StringComparer]::Ordinal)
	foreach ($n in $names) { $verDescriptors += (Join-Path $subDir $n) }
}
$verRel = { param($p) $p.Substring($objBaseDir.Length).TrimStart('\', '/') -replace '\\', '/' }
$verErrors = 0
$verBodies = 0
foreach ($desc in $verDescriptors) {
	if ($script:stopped) { break }
	$descVer = if ($desc -eq $resolvedPath) { $version } else { Get-RootVersion $desc }
	if (-not $descVer) { continue }
	$extDir = Join-Path (Join-Path (Split-Path $desc) ([System.IO.Path]::GetFileNameWithoutExtension($desc))) "Ext"
	if (-not (Test-Path $extDir -PathType Container)) { continue }
	$bodyNames = @(Get-ChildItem $extDir -Filter "*.xml" -File | ForEach-Object { $_.Name })
	[Array]::Sort($bodyNames, [StringComparer]::Ordinal)
	foreach ($bn in $bodyNames) {
		$body = Join-Path $extDir $bn
		$bodyVer = Get-RootVersion $body
		if (-not $bodyVer) { continue }
		# У заимствованной формы расширения второй штамп — <BaseForm version=…>; платформа сверяет с
		# дескриптором и его.
		if ($bn -ceq "Form.xml") {
			$bodyText = [System.IO.File]::ReadAllText($body, [System.Text.Encoding]::UTF8)
			$bfm = [regex]::Match($bodyText, '<BaseForm\s[^>]*?version="([^"]*)"')
			if ($bfm.Success -and $bfm.Groups[1].Value -ne $descVer) {
				$verErrors++
				Report-Error "24. $(& $verRel $body) <BaseForm> is stamped $($bfm.Groups[1].Value), its descriptor $(& $verRel $desc) $descVer — the platform refuses to load parts of one object in different formats"
				if ($script:stopped) { break }
			}
		}
		if ($bodyVer -eq $descVer) { $verBodies++; continue }
		$verErrors++
		Report-Error "24. $(& $verRel $body) is stamped $bodyVer, its descriptor $(& $verRel $desc) $descVer — the platform refuses to load parts of one object in different formats"
		if ($script:stopped) { break }
	}
}
if ($verErrors -eq 0 -and $verBodies -gt 0) {
	Report-OK "24. Format version: $verBodies stamped part(s) agree with their descriptors"
}
$dumpAnchor = Find-DumpAnchor $objBaseDir
$dumpVer = if ($dumpAnchor) { Get-RootVersion $dumpAnchor } else { $null }
if ($dumpVer) {
	$verOff = @()
	foreach ($desc in $verDescriptors) {
		$dv = if ($desc -eq $resolvedPath) { $version } else { Get-RootVersion $desc }
		if ($dv -and $dv -ne $dumpVer) { $verOff += "$(& $verRel $desc) $dv" }
	}
	if ($verOff.Count -gt 0) {
		$shown = ($verOff | Select-Object -First 5) -join ", "
		if ($verOff.Count -gt 5) { $shown += ", … (+$($verOff.Count - 5))" }
		Report-Warn "24. Format version differs from the dump ($dumpVer): $shown — the platform loads it, but the dump is no longer uniform (typical after merging branches dumped by different platforms)"
	} else {
		Report-OK "24. Format version: matches the dump ($dumpVer)"
	}
}

# Проверка 4 — значения свойств-перечислений. Блоком: её зовут и для видов без глубоких правил
# (общая форма, команда, общий реквизит, макет…) — иначе их перечисления не проверялись вовсе.
$check4 = {
	if ($propsNode) {
		$enumChecked = 0
		$check4Ok = $true

		# Общие свойства плюс свойства, заданные только для своего вида («Constant.QuickChoice»):
		# остальные ключи с точкой — уточнения чужих видов и контекстов (реквизит, состав), не корня
		$rootProps = @($validPropertyValues.Keys | Where-Object { -not $_.Contains('.') })
		$rootProps += @($validPropertyValues.Keys | Where-Object { $_.StartsWith("$mdType.") } | ForEach-Object { $_.Substring($mdType.Length + 1) })
		foreach ($propName in ($rootProps | Select-Object -Unique)) {
			$propNode = $propsNode.SelectSingleNode("md:$propName", $ns)
			if ($propNode -and $propNode.InnerText) {
				$val = $propNode.InnerText
				$allowed = $validPropertyValues["$mdType.$propName"]
				if (-not $allowed) { $allowed = $validPropertyValues[$propName] }
				# Регистр значим: платформа читает перечисление по точному имени (-notcontains его не различал)
				if ($allowed -cnotcontains $val) {
					Report-Error "4. Property '$propName' has invalid value '$val' (allowed: $($allowed -join ', '))"
					$check4Ok = $false
				}
				$enumChecked++
			}
		}

		# Значения у реквизитов, измерений, ресурсов и табличных частей: QuickChoice здесь — перечисление
		# (в корне справочника — булево), Use у реквизита и ТЧ — для групп/элементов. Ключи «Attribute.*»,
		# «TabularSection.*»; иначе — общий ключ свойства.
		$childCommon4 = @('CreateOnInput', 'FullTextSearch', 'DataHistory', 'ChoiceHistoryOnInput')
		$coNode4 = $typeNode.SelectSingleNode("md:ChildObjects", $ns)
		$items4 = New-Object System.Collections.ArrayList
		if ($coNode4) {
			foreach ($ch in $coNode4.ChildNodes) {
				if ($ch.NodeType -ne 'Element') { continue }
				[void]$items4.Add($ch)
				if ($ch.LocalName -eq 'TabularSection') {
					foreach ($tsAttr in $ch.SelectNodes("md:ChildObjects/md:Attribute", $ns)) { [void]$items4.Add($tsAttr) }
				}
			}
		}
		foreach ($it in $items4) {
			$itProps = $it.SelectSingleNode("md:Properties", $ns)
			if (-not $itProps) { continue }
			$ctx = if ($it.LocalName -eq 'TabularSection') { 'TabularSection' } else { 'Attribute' }
			$names = if ($ctx -eq 'TabularSection') { @('Use') } elseif ($it.LocalName -eq 'Attribute') { @('QuickChoice', 'ChoiceFoldersAndItems', 'Use') + $childCommon4 } else { @('QuickChoice', 'ChoiceFoldersAndItems') + $childCommon4 }
			$itName = $itProps.SelectSingleNode("md:Name", $ns)
			foreach ($pn in $names) {
				$pnode = $itProps.SelectSingleNode("md:$pn", $ns)
				if (-not $pnode -or -not $pnode.InnerText) { continue }
				$allowed = $validPropertyValues["$ctx.$pn"]
				if (-not $allowed) { $allowed = $validPropertyValues[$pn] }
				if (-not $allowed) { continue }
				if ($allowed -cnotcontains $pnode.InnerText) {
					Report-Error "4. $($it.LocalName) '$(if ($itName) { $itName.InnerText })': property '$pn' has invalid value '$($pnode.InnerText)' (allowed: $($allowed -join ', '))"
					$check4Ok = $false
				}
				$enumChecked++
			}
		}
		# Состав общего реквизита: Use элемента состава — Auto/Use/DontUse
		foreach ($cu in $propsNode.SelectNodes("md:Content/xr:Item/xr:Use", $ns)) {
			$allowed = $validPropertyValues["CommonAttributeContent.Use"]
			if ($cu.InnerText -and $allowed -cnotcontains $cu.InnerText) {
				Report-Error "4. Content item: property 'Use' has invalid value '$($cu.InnerText)' (allowed: $($allowed -join ', '))"
				$check4Ok = $false
			}
			$enumChecked++
		}

		# Корневой <Type> (дескриптор типа значения — Константа, ПВХ) должен быть структурным:
		# <v8:Type>/<v8:TypeSet>, а не скалярный текст. Скаляр = повреждённый тип (напр. после
		# старого meta-edit modify-property Type). См. issue #42. У элемента стиля <Type> — вид элемента
		# (Color/Font/Border), скаляр там штатный.
		$rootTypeEl = if ($mdType -ne 'StyleItem') { $propsNode.SelectSingleNode("md:Type", $ns) } else { $null }
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
				Report-Error "4. Property <Type> contains scalar text '$scalarText' without a type structure (<v8:Type>/<v8:TypeSet>) — corrupted value type descriptor"
				$check4Ok = $false
			}
		}

		if ($check4Ok) {
			Report-OK "4. Property values: $enumChecked enum properties checked"
		}
	} else {
		Report-Warn "4. No Properties block to check"
	}
}

# --- Structural-only types: базовая проверка (Name) и значения перечислений, без type-specific правил ---
if ($structuralOnlyTypes -contains $mdType) {
	if ($objName -eq "(unknown)") {
		Report-Error "3. Properties: missing or empty Name"
	} elseif ($objName -notmatch $identPattern) {
		Report-Error "3. Properties: Name '$objName' is not a valid 1C identifier"
	} else {
		Report-OK "3. Properties: Name=`"$objName`" (basic structure check for $mdType)"
	}
	& $check4
	& $finalize
	if ($script:errors -gt 0) { exit 1 }
	exit 0
}

# --- Вложенные дескрипторы Form/Template: Name и вид формы/макета ---
if ($nestedDescriptorTypes -contains $mdType) {
	if ($objName -eq "(unknown)") {
		Report-Error "3. Properties: missing or empty Name"
	} elseif ($objName -notmatch $identPattern) {
		Report-Error "3. Properties: Name '$objName' is not a valid 1C identifier"
	} else {
		Report-OK "3. Properties: Name=`"$objName`" (basic structure check for $mdType)"
	}
	$kindProp = if ($mdType -eq "Form") { "FormType" } else { "TemplateType" }
	$kindNode = if ($propsNode) { $propsNode.SelectSingleNode("md:$kindProp", $ns) } else { $null }
	$kindValue = if ($kindNode) { $kindNode.InnerText } else { "" }
	$allowed = $descriptorKindValues[$kindProp]
	# Регистрозависимо, как у платформы и в py-порте (-contains сравнивает без учёта регистра).
	if (-not $kindValue) {
		Report-Error "3. Property '$kindProp' is missing on <$mdType>"
	} elseif ($allowed -cnotcontains $kindValue) {
		Report-Error "3. Property '$kindProp' has invalid value '$kindValue' (allowed: $($allowed -join ', '))"
	} else {
		Report-OK "3. Property '$kindProp' = $kindValue"
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
					if ($mdType -eq "Table") {
						# ExternalDataSources/<Source>/Tables/<Table>.xml -> ExternalDataSourceTable<Category>.<Source>.<Table>
						$tablesDir = Split-Path $resolvedPath -Parent
						$edsName = if ((Split-Path $tablesDir -Leaf) -ceq "Tables") { Split-Path (Split-Path $tablesDir -Parent) -Leaf } else { "" }
						$expectedGtName = if ($edsName) { "ExternalDataSourceTable$gtCategory.$edsName.$objName" } else { $gtName }
					}
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
		if ($missingCats.Count -gt 0 -and $mdType -eq "Table") {
			Report-Warn "2. Missing GeneratedType categories: $($missingCats -join ', ')"
		} elseif ($missingCats.Count -gt 0) {
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

& $check4

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
					# AccountingRegister: пары субконто, число которых задаётся планом счетов
					$isDynamic = ($mdType -eq "AccountingRegister" -and ($saName -match '^ExtDimension\d+$' -or $saName -match '^ExtDimensionType\d+$'))
					if (-not $isDynamic) {
						Report-Warn "5. Unexpected StandardAttribute '$saName' for $mdType"
					}
				}
			} else {
				Report-Error "5. StandardAttribute without 'name' attribute"
				$check5Ok = $false
			}
		}

		if ($expectedStdAttrs) {
			$condNames = $stdAttrConditionalNames[$mdType]; if (-not $condNames) { $condNames = @() }
			$missingAttrs = @($expectedStdAttrs | Where-Object { $foundNames -notcontains $_ -and $condNames -notcontains $_ })
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

	# Порядок групп: загрузка примет любой, но выгрузка переставит по канону вида — дифф без правок
	$order = (Get-ObjectChildOrder)[$mdType]
	if ($order) {
		$prevTag = $null; $prevRank = -1
		foreach ($child in $childObjNode.ChildNodes) {
			if ($child.NodeType -ne 'Element' -or -not ($order -ccontains $child.LocalName)) { continue }
			$rank = [array]::IndexOf([string[]]$order, $child.LocalName)
			if ($rank -lt $prevRank) {
				$present = @($order | Where-Object { $childCounts.ContainsKey($_) })
				Report-Warn "6. ChildObjects order: <$($child.LocalName)> after <$prevTag>; platform dump reorders $mdType children as $($present -join ' -> ')"
				break
			}
			$prevTag = $child.LocalName; $prevRank = $rank
		}
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

# --- Checks 6f-6h (local): default-form roles, standard fields ---
#
# Form versions are check 24; whether a Default*/Auxiliary*Form reference
# resolves at all is check 20. The local checks add what neither covers:
# 6f: an object, record or list slot of this object points at a form with that
#     role (main attribute type).
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

if ($propsNode -and $objName -ne "(unknown)") {
	$check6fOk = $true
	$checkedRoles = 0
	$ownPrefix = "$mdType.$objName.Form."
	foreach ($prop in $propsNode.ChildNodes) {
		if ($prop.NodeType -ne 'Element') { continue }
		$propName = $prop.LocalName
		if (-not $defaultFormRoles.ContainsKey($propName)) { continue }
		$ref = $prop.InnerText.Trim()
		# Only a declared form of this object: a missing, foreign or common form is check 20.
		if (-not $ref.StartsWith($ownPrefix, [System.StringComparison]::Ordinal)) { continue }
		$formName = $ref.Substring($ownPrefix.Length)
		if ($formName.Contains('.') -or ($declaredForms -cnotcontains $formName)) { continue }
		$formRoot = Get-FormXmlRoot $formName
		if (-not $formRoot) { continue }
		$checkedRoles++
		$expectedRole = $defaultFormRoles[$propName]
		$actualRole = Get-FormRole $formRoot
		if ($actualRole -and $actualRole -ne $expectedRole) {
			Report-Error "6f. $propName = '$ref': the form is a $actualRole form (main attribute type), expected a $expectedRole form"
			$check6fOk = $false
		}
	}
	if ($check6fOk -and $checkedRoles -gt 0) { Report-OK "6f. Default form roles: $checkedRoles checked" }
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
						Report-Warn "6h. Default object form '$defaultForm' does not show '$($main.Name).Description', which is mandatory (DescriptionLength=$descLength, FillChecking=ShowError), and no form, object or manager module assigns it — writing from this form fails unless the value is filled elsewhere"
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
		# Пустой <Type/> — это тип «Произвольный», штатная конструкция: в типовых так описаны
		# служебные реквизиты обработок, платформа принимает и сохраняет её без изменений
		# (проверено round-trip). Ошибкой здесь был бы отказ там, где платформа не отказывает.
		$typeEl = $elProps.SelectSingleNode("md:Type", $ns)
		if (-not $typeEl) {
			# Блока Type нет вовсе: загрузка проходит, но платформа молча подставляет тип нового
			# реквизита — Строка(10). Загрузку это не рвёт, а замысел теряет, отсюда WARN.
			Report-Warn "7. $kind '$nameVal' — no Type block; on load the platform substitutes String(10)"
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

# Колонка ТЧ — стандартные реквизиты строки: «ТабличнаяЧасть.X - Недопустимое имя реквизита -
# НомерСтроки» (замер 8.3.24). НомерСтроки — у любого объекта, Ссылка — только у ссылочного (у обработки
# колонка Ссылка законна — замер и ERP); Номер — можно.
$check7bColOk = $true
if ($childObjNode) {
	$tsRowReserved = @{ "linenumber" = $true; "номерстроки" = $true }
	if ($stdForType -contains "Ref") { $tsRowReserved["ref"] = $true; $tsRowReserved["ссылка"] = $true }
	foreach ($tsNode in $childObjNode.SelectNodes("md:TabularSection", $ns)) {
		$tsNameNode = $tsNode.SelectSingleNode("md:Properties/md:Name", $ns)
		$tsLabel = if ($tsNameNode) { $tsNameNode.InnerText } else { "?" }
		foreach ($colNode in $tsNode.SelectNodes("md:ChildObjects/md:Attribute", $ns)) {
			$colName = $colNode.SelectSingleNode("md:Properties/md:Name", $ns)
			if ($colName -and $tsRowReserved.ContainsKey($colName.InnerText.ToLower())) {
				Report-Error "7b. TabularSection.${tsLabel}: column '$($colName.InnerText)' conflicts with a standard attribute of a tabular section row"
				$check7bColOk = $false
			}
		}
	}
}

if ($childObjNode -and $stdForType) {
	# Множество зарезервированных имён (EN + RU) в нижнем регистре.
	$reservedSet = @{}
	foreach ($en in $stdForType) {
		$reservedSet[$en.ToLower()] = $true
		$ru = $reservedEnRu[$en]
		if ($ru) { $reservedSet[$ru.ToLower()] = $true }
	}
	$check7bOk = $true
	# Измерение и ресурс регистра — те же зарезервированные имена, что у реквизита («Недопустимое имя
	# измерения - Период», замер 8.3.24)
	$attrNodes = $childObjNode.SelectNodes("md:Attribute | md:Dimension | md:Resource", $ns)
	foreach ($attrNode in $attrNodes) {
		$attrProps = $attrNode.SelectSingleNode("md:Properties", $ns)
		if ($attrProps) {
			$attrNameNode = $attrProps.SelectSingleNode("md:Name", $ns)
			if ($attrNameNode -and $attrNameNode.InnerText) {
				$an = $attrNameNode.InnerText
				if ($reservedSet.ContainsKey($an.ToLower())) {
					Report-Error "7b. $($attrNode.LocalName) '$an' conflicts with a standard attribute of $mdType"
					$check7bOk = $false
				}
			}
		}
	}
	if ($check7bOk -and $check7bColOk) {
		Report-OK "7b. Reserved attribute names: no conflicts"
	}
} elseif ($childObjNode -and $check7bColOk) {
	Report-OK "7b. Reserved attribute names: no conflicts (no standard set for $mdType)"
}

if ($script:stopped) { & $finalize; exit 1 }

# --- Check 8: Name uniqueness ---

function Check-Uniqueness {
	# 1C names are case-insensitive. Pass one shared $names hashtable to check several
	# kinds against each other (attributes, tabular sections, dimensions, resources,
	# addressing attributes and accounting flags share one namespace).
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
				Report-Error "8. $kind '$nameVal' clashes with $($other.Kind) '$($other.Name)' — names are case-insensitive and shared by attributes, tabular sections, dimensions, resources, addressing attributes and accounting flags"
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

	# Реквизит, ТЧ, измерение, ресурс, реквизит адресации и признак учёта объекта — одно пространство имён
	# без учёта регистра: платформа отвергает загрузку («Задано одинаковое имя для реквизита и табличной
	# части / измерения / ресурса / реквизита адресации», замер 8.3.24). Колонке ТЧ имя реквизита объекта
	# не мешает, признаку учёта субконто — тоже (он колонка ТЧ видов субконто). Local: one shared table,
	# so a clash is reported once, with both kinds named.
	$fieldNames = @{}
	foreach ($fieldKind in @("Attribute", "TabularSection", "Dimension", "Resource", "AddressingAttribute", "AccountingFlag")) {
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
	# HierarchyType платформа пишет всегда, независимо от Hierarchical, и при выключенной иерархии
	# просто его игнорирует (проверено: значение переживает round-trip). Дефолтное значение поэтому
	# ни о чём не говорит — предупреждаем только о явно заданном другом типе иерархии: это похоже
	# на "тип иерархии выбрали, а саму иерархию включить забыли".
	if ($hierarchical -and $hierarchyType -and $hierarchical.InnerText -eq "false" -and
		$hierarchyType.InnerText -and $hierarchyType.InnerText -ne "HierarchyFoldersAndItems") {
		Report-Warn "10. HierarchyType='$($hierarchyType.InnerText)' but Hierarchical=false"
		$check10Issues++
	}

	# Код/номер нулевой длины во вводе по строке: платформа отвергает загрузку — «Указано неверное
	# поле для ввода по строке: Код/Номер» (8.3.24, 8.5.1). Бывает после правки длины в 0 без чистки
	# InputByString (meta-edit так больше не делает, но ручную правку это не страхует).
	$ibsFields = @($propsNode.SelectNodes("md:InputByString/xr:Field", $ns) | ForEach-Object { $_.InnerText.Trim() })
	foreach ($pair in @(@("CodeLength", "Code"), @("NumberLength", "Number"))) {
		$lenNode = $propsNode.SelectSingleNode("md:$($pair[0])", $ns)
		if (-not $lenNode -or $lenNode.InnerText.Trim() -ne "0") { continue }
		$hit = $ibsFields | Where-Object { $_ -cmatch "\.StandardAttribute\.$($pair[1])$" } | Select-Object -First 1
		if ($hit) {
			Report-Error "10. InputByString contains '$hit' but $($pair[0])=0 — the platform rejects it (invalid input-by-string field)"
			$check10Ok = $false
			$check10Issues++
		}
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
		# Источник задают и наборами типов (<v8:TypeSet>cfg:CatalogObject</v8:TypeSet>) — в типовых
		# так описана каждая четвёртая подписка. Реально пустой источник платформа отвергает:
		# «ПодпискаНаСобытие.X - Источник событий должен быть задан», поэтому это ошибка.
		$hasSource = $false
		if ($source) {
			$sourceTypes = $source.SelectNodes("v8:Type", $ns)
			$sourceTypeSets = $source.SelectNodes("v8:TypeSet", $ns)
			if ($sourceTypes.Count -gt 0 -or $sourceTypeSets.Count -gt 0) { $hasSource = $true }
		}
		if (-not $hasSource) {
			Report-Error "10. EventSubscription: event source is not set — the platform rejects the load"
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
		# Регистрируемые документы платформа перечисляет как <xr:Item xsi:type="xr:MDObjectRef">,
		# так же их пишет meta-compile; форма с <v8:Type> сохранена на случай иных выгрузок.
		# Пустой состав платформа отвергает: «Для журнала не заданы регистрируемые документы».
		$hasRegDocs = $false
		if ($regDocs) {
			$items = $regDocs.SelectNodes("v8:Type", $ns)
			$refItems = $regDocs.SelectNodes("xr:Item", $ns)
			if ($items.Count -gt 0 -or $refItems.Count -gt 0) { $hasRegDocs = $true }
		}
		if (-not $hasRegDocs) {
			Report-Error "10. DocumentJournal: no registered documents — the platform rejects the load"
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
					# Список параметров переносится на следующие строки, и Экспорт оказывается не на
					# строке с именем — в типовых так объявлена каждая обработчик-процедура с длинной
					# сигнатурой. Отсюда (?s) для содержимого скобок и \s (а не пробел) перед Экспорт.
					$exportPattern = "(?smi)^[ 	]*(Procedure|Function|Процедура|Функция)[ 	]+$([regex]::Escape($procName))[ 	]*\([^)]*\)\s+(Export|Экспорт)"
					if (-not [regex]::IsMatch($bslContent, $exportPattern)) {
						Report-Warn "13. ${mdType}.${propLabel}: procedure '$procName' not found as exported in CommonModule '$cmName'"
						$check13Ok = $false
					}
				} elseif (Test-Path ([System.IO.Path]::ChangeExtension($bslPath, "bin"))) {
					# Модуль поставщика выгружен в двоичном виде (Module.bin) — текста нет by design,
					# проверять нечего. Предупреждать здесь значило бы шуметь о норме.
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
	$reservedCmd = (Get-ReservedCommandNames)[$mdType]
	if (-not $reservedCmd) { $reservedCmd = @() }
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
		} elseif ($reservedCmd -contains $cmdName) {
			Report-Error "15. Command '${cmdName}': name conflicts with a standard command of $mdType"; $check15Ok = $false
		}
		$groupNode = if ($cmdProps) { $cmdProps.SelectSingleNode("md:Group", $ns) } else { $null }
		$groupVal = if ($groupNode) { $groupNode.InnerText.Trim() } else { "" }
		if (-not $groupVal) {
			Report-Error "15. Command '$cmdName': group (Group) is not set — the platform rejects the load"; $check15Ok = $false
		} elseif (($validCommandGroups -notcontains $groupVal) -and ($groupVal -notmatch '^CommandGroup\.')) {
			Report-Error "15. Command '$cmdName': unknown group '$groupVal'. Valid: $($validCommandGroups -join ', '); or CommandGroup.<Name>"; $check15Ok = $false
		} elseif ($sectionCommandGroups -contains $groupVal) {
			$cptNode = if ($cmdProps) { $cmdProps.SelectSingleNode("md:CommandParameterType", $ns) } else { $null }
			$hasCpt = $cptNode -and (($cptNode.SelectNodes("v8:Type", $ns).Count -gt 0) -or ($cptNode.SelectNodes("v8:TypeSet", $ns).Count -gt 0))
			if ($hasCpt) {
				Report-Error "15. Command '$cmdName': parameter type (CommandParameterType) is not available for commands of the section command interface ('$groupVal')"; $check15Ok = $false
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
foreach ($tn in $xmlDoc.SelectNodes("//v8:Type | //v8:TypeSet", $ns)) {
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

# --- Состав конфигурации (ChildObjects из Configuration.xml) ---
# Платформа судит о существовании объекта по СОСТАВУ, а не по наличию файла. Файла может не быть
# в частичной выгрузке: такой фрагмент грузится через /LoadConfigFromFiles -listFile слиянием с базой,
# и ссылка на невыгруженный объект остаётся рабочей. Отсюда два разных исхода:
#   нет в составе        -> платформа отвергнет загрузку всегда -> ERROR
#   в составе, файла нет -> полная загрузка упадёт, частичная пройдёт -> WARN
# ChildObjects конфигурации — плоский список <Вид>Имя</Вид>, поэтому ищем подстроку в границах секции
# без копирования и без разбора XML. Кэш живёт только в пределах одного объекта: в batch-режиме
# каждый следующий разбирается заново (в PS — новая область видимости скрипта при вызове через &,
# в py — вовсе новый процесс), так что полная карта (~100 мс) оплачивалась бы каждым объектом.

$script:cfgText = $null
$script:cfgChildStart = -1
$script:cfgChildLen = 0
$script:cfgTextLoaded = $false

function Initialize-ConfigText {
	if ($script:cfgTextLoaded) { return }
	$script:cfgTextLoaded = $true
	if (-not $script:configDir) { return }
	$cfgPath = Join-Path $script:configDir "Configuration.xml"
	if (-not (Test-Path $cfgPath)) { return }
	try {
		$script:cfgText = [System.IO.File]::ReadAllText($cfgPath, [System.Text.Encoding]::UTF8)
	} catch {
		$script:cfgText = $null
		return
	}
	$s = $script:cfgText.IndexOf('<ChildObjects>', [System.StringComparison]::Ordinal)
	$e = $script:cfgText.LastIndexOf('</ChildObjects>', [System.StringComparison]::Ordinal)
	if ($s -ge 0 -and $e -gt $s) {
		$script:cfgChildStart = $s
		$script:cfgChildLen = $e - $s
	}
}

function Test-ConfigIsExtension {
	Initialize-ConfigText
	if (-not $script:cfgText) { return $false }
	return $script:cfgText.Contains("ConfigurationExtensionPurpose")
}

# $true — объект есть в составе; $false — нет; $null — состав неизвестен (нет Configuration.xml
# или в нём нет ChildObjects), тогда вызывающий оставляет мягкий уровень.
function Test-InConfigComposition([string]$kind, [string]$name) {
	Initialize-ConfigText
	if ($script:cfgChildStart -lt 0) { return $null }
	$needle = "<$kind>$name</$kind>"
	if ($script:cfgText.IndexOf($needle, $script:cfgChildStart, $script:cfgChildLen, [System.StringComparison]::Ordinal) -ge 0) {
		return $true
	}
	# Промах по точному совпадению — сверяем без учёта регистра, как это делает платформа.
	# Порядок именно такой: Ordinal на порядок дешевле, а промахи редки.
	return ($script:cfgText.IndexOf($needle, $script:cfgChildStart, $script:cfgChildLen, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
}

# --- Check 16: Reference type existence — типы вида CatalogRef.X должны разрешаться в объекты конфигурации ---
# Уровень выбирается по составу конфигурации: типа нет в ChildObjects — «Неизвестное имя типа» при
# загрузке (ERROR); объект в составе есть, а файла в выгрузке нет — частичная выгрузка (WARN).
# Расширения (CFE) пропускаем — их типы ссылаются на объекты базовой конфигурации, которых в выгрузке
# расширения нет.

if ($script:configDir) {
	$isExtension = Test-ConfigIsExtension
	if (-not $isExtension) {
		$refDirMap = @{
			"CatalogRef"="Catalogs"; "DocumentRef"="Documents"; "EnumRef"="Enums"
			"ChartOfAccountsRef"="ChartsOfAccounts"; "ChartOfCharacteristicTypesRef"="ChartsOfCharacteristicTypes"
			"ChartOfCalculationTypesRef"="ChartsOfCalculationTypes"; "BusinessProcessRef"="BusinessProcesses"
			"ExchangePlanRef"="ExchangePlans"; "TaskRef"="Tasks"; "DefinedType"="DefinedTypes"
		}
		$typeNodes = $xmlDoc.SelectNodes("//v8:Type", $ns)
		$checkedRefs = @{}   # refKey -> $true если найден; для OK-условия
		$missingRefs = @{}   # refKey -> refDir; объект есть в составе, файла в выгрузке нет
		$absentRefs = @{}    # refKey -> refDir; объекта нет в составе конфигурации
		$unknownRefs = @{}   # refKey -> refDir; состав неизвестен (Configuration.xml без ChildObjects)
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
				# Вид метаданных в ChildObjects — это тип без суффикса Ref (CatalogRef -> Catalog);
				# DefinedType суффикса не имеет и пишется в состав как есть.
				$refKindTag = if ($refCat.EndsWith("Ref")) { $refCat.Substring(0, $refCat.Length - 3) } else { $refCat }
				$inComposition = Test-InConfigComposition $refKindTag $refName
				if ($inComposition -eq $false) {
					$absentRefs[$refKey] = $refDir
				} elseif ($inComposition -eq $true) {
					$missingRefs[$refKey] = $refDir
				} else {
					$unknownRefs[$refKey] = $refDir
				}
			}
		}
		if ($absentRefs.Count -gt 0) {
			foreach ($ak in ($absentRefs.Keys | Sort-Object)) {
				Report-Error "16. Reference type '$ak' — the object is not in the configuration ($($absentRefs[$ak])/) — «Неизвестное имя типа» on load"
			}
		}
		if ($missingRefs.Count -gt 0) {
			foreach ($mk in ($missingRefs.Keys | Sort-Object)) {
				Report-Warn "16. Reference type '$mk' — the object is in the configuration, but its file is not in the dump ($($missingRefs[$mk])/)"
			}
		}
		if ($unknownRefs.Count -gt 0) {
			foreach ($uk in ($unknownRefs.Keys | Sort-Object)) {
				Report-Warn "16. Reference type '$uk' not found in the configuration ($($unknownRefs[$uk])/)"
			}
		}
		if ($absentRefs.Count -eq 0 -and $missingRefs.Count -eq 0 -and $unknownRefs.Count -eq 0 -and $checkedRefs.Count -gt 0) {
			Report-OK "16. Reference types: $($checkedRefs.Count) resolved"
		}
	}
}

# --- Check 22: имя типа — грамматика (уровень 1) и словарь по контексту владельца (уровень 2) ---
# УРОВЕНЬ 1 не зависит ни от версии платформы, ни от состава конфигурации: содержимое <v8:Type>
# всегда несёт префикс пространства имён (xs:/v8:/cfg:/dNpM:/ent:/…). Голое имя платформа не примет
# никогда — так выглядит и тип СУБД («varchar(150)»), и опечатка («Srting(20)»).
# УРОВЕНЬ 2 — словарь: у хранимого объекта набор типов у́же, чем у обработки или отчёта, где
# доступны ТаблицаЗначений, ОписаниеТипов, Картинка и прочие рантайм-типы. Здесь только
# предупреждение: список конечен, но пополняется с версиями платформы.
$knownXsTypes = @("xs:string", "xs:decimal", "xs:boolean", "xs:dateTime", "xs:base64Binary")
$knownV8Types = @("ValueStorage", "UUID", "Null", "Type", "ValueTable", "ValueTree", "ValueList",
	"ValueListType", "StandardPeriod", "StandardBeginningDate", "PointInTime", "TypeDescription",
	"FixedArray", "FixedMap", "FixedStructure", "FillChecking", "Universal")
# Ссылочные метатипы: с именем объекта (<Метатип>.<Имя>) — конкретный тип, без имени — множество.
$refMetaTypes = @("CatalogRef", "DocumentRef", "EnumRef", "ChartOfAccountsRef",
	"ChartOfCharacteristicTypesRef", "ChartOfCalculationTypesRef", "ExchangePlanRef",
	"BusinessProcessRef", "BusinessProcessRoutePointRef", "TaskRef", "AnyRef", "AnyIBRef")
# Прочие имена пространства current-config без точки — платформенные, состав конфигурации их не меняет.
$cfgBareNames = @("ConstantsSet", "ReportBuilder", "FilterCriterion", "DynamicList")
# Виды, чьи реквизиты ХРАНЯТСЯ в базе: там рантайм-типы недопустимы. У обработки и отчёта — наоборот.
$storedOwnerTypes = @("Catalog", "Document", "DocumentJournal", "InformationRegister",
	"AccumulationRegister", "AccountingRegister", "CalculationRegister", "ChartOfAccounts",
	"ChartOfCharacteristicTypes", "ChartOfCalculationTypes", "ExchangePlan", "BusinessProcess",
	"Task", "Constant", "Table")

function Test-StorableType([string]$t) {
	if ($knownXsTypes -contains $t) { return $true }
	if ($t -eq "v8:ValueStorage" -or $t -eq "v8:UUID" -or $t -eq "v8:Null") { return $true }
	$m = [regex]::Match($t, '^(?:cfg|d\d+p\d+):(.+)$')
	if (-not $m.Success) { return $false }
	$name = $m.Groups[1].Value
	$base = if ($name.Contains('.')) { $name.Substring(0, $name.IndexOf('.')) } else { $name }
	if ($refMetaTypes -contains $base) { return $true }
	if ($base -eq "DefinedType" -or $base -eq "Characteristic" -or $base -eq "ExternalDataSourceTableRef") { return $true }
	return $false
}

$typeNodes22 = @($xmlDoc.SelectNodes("//v8:Type", $ns)) + @($xmlDoc.SelectNodes("//v8:TypeSet", $ns))
# Уровень 2 смотрит только на типы САМИХ реквизитов: параметры команд, характеристики и стандартные
# реквизиты живут по другим правилам, и мешать их в один котёл нельзя.
$attrTypePaths = @("Attribute", "Dimension", "Resource", "Column", "Field", "AddressingAttribute",
	"AccountingFlag", "ExtDimensionAccountingFlag")
$badGrammar = @{}
$unknownVocab = @{}
$notStorable = @{}
$typesSeen = 0
foreach ($tn in $typeNodes22) {
	$t = "$($tn.InnerText)".Trim()
	if (-not $t) { continue }
	$typesSeen++
	# Local: an export folder name in place of a type is reported once, by 16a.
	if ($folderTypeValues.ContainsKey($t)) { continue }
	if (-not $t.Contains(':')) {
		$badGrammar[$t] = $true
		continue
	}
	$prefix = $t.Substring(0, $t.IndexOf(':'))
	$local = $t.Substring($t.IndexOf(':') + 1)
	if ($prefix -eq "xs") {
		if ($knownXsTypes -notcontains $t) { $unknownVocab[$t] = $true }
	} elseif ($prefix -eq "v8") {
		if ($knownV8Types -notcontains $local) { $unknownVocab[$t] = $true }
	} elseif ($prefix -eq "cfg" -or $prefix -match '^d\d+p\d+$') {
		# Имя объекта конфигурации проверяет Check 16; здесь — только форма и платформенная часть.
		if (-not $local.Contains('.')) {
			if (($refMetaTypes -notcontains $local) -and ($cfgBareNames -notcontains $local) -and
			    ($local -notmatch '^[A-Za-z][A-Za-z0-9]*(Object|Manager|List|Selection|RecordSet|RecordKey|RecordManager)$')) {
				$unknownVocab[$t] = $true
			}
		} elseif ($local -notmatch '^[A-Za-z][A-Za-z0-9]*\.[^.]+(\.[^.]+)?$') {
			$badGrammar[$t] = $true
		}
	}
	# Прочие пространства (ent:, v8ui:, dcs*:, mxl: …) — форму имени не навязываем: там свои словари.

	if ($storedOwnerTypes -contains $mdType) {
		$owner = $tn.ParentNode          # <Type>
		$props = if ($owner) { $owner.ParentNode } else { $null }     # <Properties>
		$child = if ($props) { $props.ParentNode } else { $null }     # <Attribute>/<Field>/…
		if ($child -and ($attrTypePaths -contains $child.LocalName) -and -not (Test-StorableType $t)) {
			$notStorable[$t] = $child.LocalName
		}
	}
}

if ($badGrammar.Count -gt 0) {
	foreach ($bk in ($badGrammar.Keys | Sort-Object)) {
		Report-Error "22. Type '$bk' — not a platform type name: the namespace prefix is missing or the reference type form is wrong. On load: «Неизвестное имя типа»"
	}
}
if ($notStorable.Count -gt 0) {
	foreach ($nk in ($notStorable.Keys | Sort-Object)) {
		Report-Warn "22. Type '$nk' on element $($notStorable[$nk]) of object ${mdType}: such types occur on attributes of data processors and reports, but not of objects stored in the infobase"
	}
}
if ($unknownVocab.Count -gt 0) {
	foreach ($uk in ($unknownVocab.Keys | Sort-Object)) {
		Report-Warn "22. Type '$uk' is not in the list of known platform types — check the spelling (the list grows with platform versions)"
	}
}
if ($badGrammar.Count -eq 0 -and $notStorable.Count -eq 0 -and $unknownVocab.Count -eq 0 -and $typesSeen -gt 0) {
	Report-OK "22. Type names: $typesSeen checked"
}

# --- Check 23: тип-множество там, где его не принимают ---
# Три уровня строгости, все замерены загрузкой в базу на 8.3.24.1691:
#  ERROR — множество в составе определяемого типа: платформа отвергает файл целиком
#          («ОпределяемыйТип.<Имя> - Недопустимый тип»), проверено на ОпределяемыйТип,
#          Характеристика, ЛюбаяСсылка и голых ссылках;
#  WARN  — голый метатип в типе значения ПВХ: загрузка проходит, но Конфигуратор такой тип не
#          предлагает (в дереве выбора это папка без флажка), а ЛюбаяСсылка на выгрузке
#          возвращается как ЛюбаяСсылкаИБ;
#  WARN  — определяемый тип или характеристика одним из составного: Конфигуратор даёт
#          выбрать их только единственными (характеристику — даже с другой характеристикой). В корпусе erp+acc 6500 единственных против 1 составного — и этот один
#          лежит в типовой ERP (Документ.НачислениеИСписаниеБонусныхБаллов.Баллы), поэтому не ошибка.
$typeBlocks23 = @($xmlDoc.SelectNodes("//md:Type | //md:ValueType", $ns))
$dtSetsSeen = 0
$dtSetsBad = $false
foreach ($tb in $typeBlocks23) {
	$sets = @($tb.SelectNodes("v8:TypeSet", $ns))
	if ($sets.Count -eq 0) { continue }
	$dtSetsSeen++
	$members = $tb.SelectNodes("v8:Type", $ns).Count + $sets.Count
	$ownerKind = $tb.ParentNode.ParentNode.get_LocalName()   # <Type> → <Properties> → <DefinedType>/…
	foreach ($st in $sets) {
		$raw = $st.InnerText.Trim() -replace '^(?:cfg|d\d+p\d+):', ''
		if ($ownerKind -eq "DefinedType") {
			$dtSetsBad = $true
			Report-Error "23. Defined type '$objName': contains the type set '$raw' — the platform will not load such a file («Недопустимый тип»). A defined type may contain only concrete types"
			continue
		}
		if ($ownerKind -eq "ChartOfCharacteristicTypes" -and $raw -notmatch '^DefinedType\.') {
			$dtSetsBad = $true
			Report-Warn "23. Chart of characteristic types '$objName': value type '$raw' is not offered by Designer (in the type picker it is a folder without a checkbox); AnyRef comes back as AnyIBRef on dump"
		}
		if ($members -gt 1 -and $raw -match '^(DefinedType|Characteristic)\.') {
			$dtSetsBad = $true
			Report-Warn "23. Composite type contains '$raw' — Designer allows a defined type or a characteristic only as the sole type; the platform loads it"
		}
	}
}
if ($dtSetsSeen -gt 0 -and -not $dtSetsBad) { Report-OK "23. Type sets: $dtSetsSeen block(s) checked" }

# --- Check 18: свойства, появившиеся в новых версиях формата ---
# Реестр «тег → минимальная версия формата». Служит двум целям: (1) поймать свойство в файле со
# слишком старым штампом — при сборке на старой платформе оно будет молча отброшено (платформа
# рапортует успех, а свойство теряется); (2) подсказать, что конструкция требует более нового
# формата. Расширяется одной строкой на свойство — задел под 2.21 (8.5) и последующие.
$versionedProps = @{
	"TypeReductionMode" = "2.18"   # режим приведения типов (стандартные реквизиты, измерения РС)
	"LineNumberLength"  = "2.20"   # длина номера строки ТЧ (5..9)
	# 2.21 (8.5): подтверждено синтетикой — одни исходники, выгрузка с 8.3.27 и с 8.5.1.
	"Color"                          = "2.21"   # цвет значения перечисления
	"AuxiliaryVariantForm"           = "2.21"   # вспомогательная форма варианта отчёта
	"UseInInterfaceCompatibilityMode" = "2.21"  # использование общей формы в режиме совместимости интерфейса
}
$fileRank = $versionRank
if ($fileRank -gt 0) {
	foreach ($vp in ($versionedProps.Keys | Sort-Object)) {
		$nodes = $xmlDoc.SelectNodes("//md:$vp | //xr:$vp", $ns)
		if ($nodes -and $nodes.Count -gt 0 -and $fileRank -lt (Get-FormatRank $versionedProps[$vp])) {
			Report-Error "18. <$vp> appeared in format $($versionedProps[$vp]), but the file declares $version — the platform of that version drops the property on load"
		}
	}
}

# --- Check 19: LineNumberLength — допустимый диапазон 5..9 ---
# Длина номера строки ТЧ: 5 (до 99 999 строк) … 9 (до 999 999 999). Границы — из документации 1С.
foreach ($lnl in @($xmlDoc.SelectNodes("//md:LineNumberLength", $ns))) {
	$raw = $lnl.InnerText.Trim()
	if ($raw -notmatch '^\d+$') {
		Report-Error "19. LineNumberLength='$raw' — must be an integer 5..9"
	} elseif ([int]$raw -lt 5 -or [int]$raw -gt 9) {
		Report-Error "19. LineNumberLength=$raw is out of range 5..9"
	}
}

# --- Check 25: многоязычная строка (LocalStringType) — только элементы v8:item, без простого текста ---
# Простой текст в таком теге платформа не загружает: «Ошибка преобразования данных XDTO … LocalStringType».
$localStringTags = @('Synonym','ToolTip','Explanation','ObjectPresentation','ExtendedObjectPresentation','ListPresentation',
	'ExtendedListPresentation','RecordPresentation','ExtendedRecordPresentation','ExtendedPresentation','Format','EditFormat')
$lsXPath = ($localStringTags | ForEach-Object { "//md:$_|//xr:$_" }) -join '|'
foreach ($ls in @($xmlDoc.SelectNodes($lsXPath, $ns))) {
	$plain = (@($ls.ChildNodes | Where-Object { $_.NodeType -eq 'Text' -or $_.NodeType -eq 'CDATA' } | ForEach-Object { $_.Value }) -join '').Trim()
	if (-not $plain) { continue }
	$owner = $ls.ParentNode.SelectSingleNode("md:Name|xr:Name", $ns)
	$where = if ($owner -and $owner.InnerText.Trim() -ne $objName) { " of '$($owner.InnerText.Trim())'" } else { "" }
	Report-Error "25. <$($ls.LocalName)>$where holds plain text '$plain' — a multilingual string needs <v8:item> elements; the platform rejects the load"
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
		Report-Error "17. MDObjectRef '$bk' — refers to a TYPE, not to a metadata object; should be '$fixed' (otherwise «Неизвестный объект метаданных» on load)"
	}
	foreach ($uk in ($unknownRoot.Keys | Sort-Object)) {
		Report-Warn "17. MDObjectRef '$uk' — unknown metadata kind '$($unknownRoot[$uk])' (typo?)"
	}
	if ($badRefForm.Count -eq 0 -and $unknownRoot.Count -eq 0) {
		Report-OK "17. MDObjectRef form: $($mdRefNodes.Count) checked"
	}
}

# --- Check 20: Default*Form / Auxiliary*Form — ссылка на существующую форму ---
# Платформа отвергает загрузку: «Неизвестный объект метаданных - Catalog.Товары.Form.НетТакойФормы».
# Две формы записи: "CommonForm.Имя" и "<Вид>.<Объект>.Form.<Форма>", причём объект может быть чужим
# (DefaultListForm документа указывает на форму журнала документов). Для СВОЕГО объекта проверяем
# регистрацию формы в ChildObjects — работает и на одиночном файле; для чужого и общей формы нужна
# конфигурация. Заимствованные объекты расширения (ObjectBelonging=Adopted) пропускаем: их формы
# живут в основной конфигурации, в выгрузке расширения их нет.
#
# Уровень везде выбирается по составу, а не по наличию файла (см. Test-InConfigComposition):
# нет в ChildObjects — платформа откажет и при полной, и при частичной загрузке (ERROR);
# в составе есть, а файла в выгрузке нет — это фрагмент частичной выгрузки, и загрузится он или нет,
# зависит от состояния конфигурации БД, которого валидатору не видно (WARN).

$formOwnerDirMap = @{
	"Catalog"="Catalogs"; "Document"="Documents"; "DocumentJournal"="DocumentJournals"
	"Enum"="Enums"; "Report"="Reports"; "DataProcessor"="DataProcessors"
	"InformationRegister"="InformationRegisters"; "AccumulationRegister"="AccumulationRegisters"
	"AccountingRegister"="AccountingRegisters"; "CalculationRegister"="CalculationRegisters"
	"ChartOfAccounts"="ChartsOfAccounts"; "ChartOfCharacteristicTypes"="ChartsOfCharacteristicTypes"
	"ChartOfCalculationTypes"="ChartsOfCalculationTypes"; "BusinessProcess"="BusinessProcesses"
	"Task"="Tasks"; "ExchangePlan"="ExchangePlans"; "SettingsStorage"="SettingsStorages"
	"FilterCriterion"="FilterCriteria"; "ExternalDataSource"="ExternalDataSources"
}

$belongingNode = $typeNode.SelectSingleNode("md:Properties/md:ObjectBelonging", $ns)
$isAdopted = $belongingNode -and $belongingNode.InnerText.Trim() -eq "Adopted"

if (-not $isAdopted) {
	$isExtension20 = Test-ConfigIsExtension

	# формы своего объекта: имена из ChildObjects (сравнение регистронезависимое — как у платформы)
	$ownForms = @{}
	if ($childObjNode) {
		foreach ($child in $childObjNode.ChildNodes) {
			if ($child.NodeType -eq 'Element' -and $child.LocalName -eq "Form") {
				# Local: an inline descriptor (6a) is counted by its declared name, not by its text.
				$inlineName20 = $child.SelectSingleNode("md:Properties/md:Name", $ns)
				$fn = if ($inlineName20) { $inlineName20.InnerText.Trim() } else { $child.InnerText.Trim() }
				if ($fn) { $ownForms[$fn.ToLowerInvariant()] = $fn }
			}
		}
	}
	$ownDir = Join-Path (Split-Path $resolvedPath) $objName

	function Test-FormFile20 {
		param([string]$baseDir, [string]$formName)
		$formsDir = Join-Path $baseDir "Forms"
		if (Test-Path (Join-Path $formsDir "$formName.xml")) { return $true }
		if (Test-Path (Join-Path (Join-Path $formsDir $formName) "Form.xml")) { return $true }
		if (Test-Path (Join-Path (Join-Path (Join-Path $formsDir $formName) "Ext") "Form.xml")) { return $true }
		return $false
	}

	$formRefNodes = @($xmlDoc.SelectNodes("//*[substring(local-name(), string-length(local-name()) - 3) = 'Form']"))
	$formRefsChecked = 0
	$formRefBad = $false
	foreach ($frn in $formRefNodes) {
		$tag = $frn.LocalName
		# ChoiceForm — «форма выбора» реквизита, ссылка того же вида, что и Default*Form.
		if ($tag -notmatch '^(Default|Auxiliary)[A-Za-z]*Form$' -and $tag -ne 'ChoiceForm') { continue }
		$ref = $frn.InnerText.Trim()
		if (-not $ref) { continue }
		# Значением бывает GUID (erp: Report.СверкаДанныхОУиБУ, DefaultVariantForm) — проверить
		# его без обхода всех форм нельзя; cf-validate (Check 9) такие тоже пропускает.
		if ($ref -match '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$') { continue }
		$parts = $ref.Split('.')
		$formRefsChecked++

		if ($parts.Count -eq 2 -and $parts[0] -eq "CommonForm") {
			if ($isExtension20 -or -not $script:configDir) { continue }
			$cfDir = Join-Path (Join-Path $script:configDir "CommonForms") $parts[1]
			$cfOk = (Test-Path "$cfDir.xml") -or (Test-Path (Join-Path (Join-Path $cfDir "Ext") "Form.xml")) -or (Test-Path (Join-Path $cfDir "Form.xml"))
			if (-not $cfOk) {
				$cfInComposition = Test-InConfigComposition "CommonForm" $parts[1]
				if ($cfInComposition -eq $true) {
					Report-Warn "20. $tag '$ref' — the common form is in the configuration, but the form file is not in the dump (CommonForms/$($parts[1]))"
				} else {
					Report-Error "20. $tag '$ref' — the common form is not in the configuration (CommonForms/$($parts[1])) — «Неизвестный объект метаданных» on load"
					$formRefBad = $true
				}
			}
			continue
		}

		# Ссылка на форму таблицы внешнего источника — шестичастная:
		# ExternalDataSource.<Источник>.Table.<Таблица>.Form.<Форма>. Сводим её к четырём частям
		# (вид = Table, объект = имя таблицы), дальше проверка общая.
		if ($parts.Count -eq 6 -and $parts[0] -eq "ExternalDataSource" -and $parts[2] -eq "Table" -and $parts[4] -eq "Form") {
			$parts = @("Table", $parts[3], "Form", $parts[5])
		}

		if ($parts.Count -ne 4 -or $parts[2] -ne "Form") {
			Report-Warn "20. $tag '$ref' — unexpected form reference shape (expected 'CommonForm.<Name>' or '<Kind>.<Object>.Form.<Form>')"
			continue
		}

		$refKind = $parts[0]; $refObj = $parts[1]; $refForm = $parts[3]

		if ($refKind.ToLowerInvariant() -eq $mdType.ToLowerInvariant() -and $refObj.ToLowerInvariant() -eq $objName.ToLowerInvariant()) {
			if (-not $ownForms.ContainsKey($refForm.ToLowerInvariant())) {
				$known = if ($ownForms.Count -gt 0) { ($ownForms.Values | Sort-Object) -join ", " } else { "no forms" }
				Report-Error "20. $tag '$ref' — form '$refForm' is not registered in the object's ChildObjects (present: $known) — «Неизвестный объект метаданных» on load"
				$formRefBad = $true
			}
			# Local: a registered form without its descriptor file is check 6b (always an ERROR).
			continue
		}

		# чужой объект (например журнал документов) — нужна конфигурация
		if ($isExtension20 -or -not $script:configDir) { continue }
		$refDir20 = $formOwnerDirMap[$refKind]
		if (-not $refDir20) {
			Report-Warn "20. $tag '$ref' — unknown metadata kind '$refKind' (typo?)"
			continue
		}
		$refObjXml = Join-Path (Join-Path $script:configDir $refDir20) "$refObj.xml"
		if (-not (Test-Path $refObjXml)) {
			$objInComposition = Test-InConfigComposition $refKind $refObj
			if ($objInComposition -eq $false) {
				Report-Error "20. $tag '$ref' — object '$refKind.$refObj' is not in the configuration ($refDir20/) — «Неизвестный объект метаданных» on load"
				$formRefBad = $true
			} elseif ($objInComposition -eq $true) {
				Report-Warn "20. $tag '$ref' — object '$refKind.$refObj' is in the configuration, but its file is not in the dump ($refDir20/)"
			} else {
				Report-Warn "20. $tag '$ref' — object '$refKind.$refObj' not found in the configuration ($refDir20/)"
			}
			continue
		}
		if (-not (Test-FormFile20 (Join-Path (Join-Path $script:configDir $refDir20) $refObj) $refForm)) {
			Report-Error "20. $tag '$ref' — form '$refForm' not found on object '$refKind.$refObj' — «Неизвестный объект метаданных» on load"
			$formRefBad = $true
		}
	}

	if ($formRefsChecked -gt 0 -and -not $formRefBad) {
		Report-OK "20. Form refs: $formRefsChecked resolved"
	}
}

# --- Check 21: таблица внешнего источника — ссылки на поля и наличие ключа ---
# Свойства таблицы ссылаются на её же поля полным путём. Опечатка в имени поля даёт
# «Неизвестный объект метаданных» при загрузке, а найти её глазами в шестичастном пути трудно.
if ($mdType -eq "Table") {
	$fieldNames = @{}
	if ($childObjNode) {
		foreach ($f in $childObjNode.SelectNodes("md:Field/md:Properties/md:Name", $ns)) {
			$fieldNames[$f.InnerText] = $true
		}
	}
	$edsRefsChecked = 0
	$edsRefsBad = $false
	foreach ($spec in @(
		@("KeyFields", "xr:Field"), @("InputByString", "xr:Field"), @("DataLockFields", "xr:Field"),
		@("PresentationField", $null), @("ParentField", $null), @("DataVersionField", $null))) {
		$tag = $spec[0]
		$refs = @()
		if ($spec[1]) {
			foreach ($n in $propsNode.SelectNodes("md:$tag/$($spec[1])", $ns)) { $refs += $n.InnerText }
		} else {
			$n = $propsNode.SelectSingleNode("md:$tag", $ns)
			if ($n -and $n.InnerText) { $refs += $n.InnerText }
		}
		foreach ($ref in $refs) {
			$edsRefsChecked++
			$parts = $ref -split '\.'
			# Ожидается ExternalDataSource.<Источник>.Table.<Таблица>.Field.<Поле>
			if ($parts.Count -ne 6 -or $parts[0] -ne "ExternalDataSource" -or $parts[2] -ne "Table" -or $parts[4] -ne "Field") {
				Report-Error "21. $tag '$ref' — expected ExternalDataSource.<Source>.Table.<Table>.Field.<Field>"
				$edsRefsBad = $true
				continue
			}
			if ($parts[3] -ne $objName) {
				Report-Error "21. $tag '$ref' — refers to a field of ANOTHER table (this one: $objName)"
				$edsRefsBad = $true
				continue
			}
			if (-not $fieldNames.ContainsKey($parts[5])) {
				$known = if ($fieldNames.Count -gt 0) { ($fieldNames.Keys | Sort-Object) -join ", " } else { "no fields" }
				Report-Error "21. $tag '$ref' — field '$($parts[5])' is not in the table (present: $known)"
				$edsRefsBad = $true
			}
		}
	}
	if ($edsRefsChecked -gt 0 -and -not $edsRefsBad) { Report-OK "21. Field refs: $edsRefsChecked resolved" }

	# Ключ: загрузка XML таблицу без ключа принимает (проверено на платформе), а Конфигуратор
	# интерактивно требует. Отсюда предупреждение, а не ошибка: рабочие конфигурации без ключа есть.
	$keyNodes = @($propsNode.SelectNodes("md:KeyFields/xr:Field", $ns))
	if ($keyNodes.Count -eq 0) {
		Report-Warn "21. KeyFields is empty — the platform loads such a table, but the record form and the record set will be unavailable"
	}
}

# --- Final output ---

& $finalize

if ($script:errors -gt 0) {
	exit 1
}
exit 0
