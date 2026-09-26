#Requires -Version 5.1
<#
.SYNOPSIS
    Read-only integrity check of a complete hierarchical Designer XML dump (CF or CFE).
.DESCRIPTION
    Checks declared objects against disk, nested subsystems, metadata versions,
    configuration/subsystem references and an optional ConfigDumpInfo.xml.
    Does not replace cf-validate/cfe-validate, object validators or platform checks.
    Local implementation; no md-sparrow source code or runtime dependency.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][Alias('Path')][string]$ConfigPath,
    [ValidateSet('Text', 'Json')][string]$Format = 'Text',
    [string]$OutFile
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$script:Findings = New-Object System.Collections.Generic.List[object]
$script:Objects = @{}
$script:ReferenceSources = New-Object System.Collections.Generic.List[object]
$inputPath = if ([System.IO.Path]::IsPathRooted($ConfigPath)) { $ConfigPath } else { Join-Path (Get-Location).Path $ConfigPath }
$script:RootPath = [System.IO.Path]::GetFullPath($inputPath)
$script:ScanFailed = $false
$script:OutputPath = $null
$MetadataNamespace = 'http://v8.1c.ru/8.3/MDClasses'
$Identifier = '^[\p{L}_][\p{L}\p{Nd}_]*$'
# Same directory vocabulary as cf-validate; only immediate descriptor files are scanned.
# Ext, modules, forms, templates and supplier dumps are not mistaken for root objects.
$TypeDirectories = [ordered]@{
    Language='Languages'; Subsystem='Subsystems'; StyleItem='StyleItems'; Style='Styles'
    CommonPicture='CommonPictures'; SessionParameter='SessionParameters'; Role='Roles'
    CommonTemplate='CommonTemplates'; FilterCriterion='FilterCriteria'; CommonModule='CommonModules'
    Bot='Bots'; CommonAttribute='CommonAttributes'; ExchangePlan='ExchangePlans'
    XDTOPackage='XDTOPackages'; WebService='WebServices'; HTTPService='HTTPServices'; WSReference='WSReferences'
    EventSubscription='EventSubscriptions'; ScheduledJob='ScheduledJobs'; SettingsStorage='SettingsStorages'
    FunctionalOption='FunctionalOptions'; FunctionalOptionsParameter='FunctionalOptionsParameters'
    DefinedType='DefinedTypes'; CommonCommand='CommonCommands'; CommandGroup='CommandGroups'
    Constant='Constants'; CommonForm='CommonForms'; Catalog='Catalogs'; Document='Documents'
    DocumentNumerator='DocumentNumerators'; Sequence='Sequences'; DocumentJournal='DocumentJournals'
    Enum='Enums'; Report='Reports'; DataProcessor='DataProcessors'; InformationRegister='InformationRegisters'
    AccumulationRegister='AccumulationRegisters'; ChartOfCharacteristicTypes='ChartsOfCharacteristicTypes'
    ChartOfAccounts='ChartsOfAccounts'; AccountingRegister='AccountingRegisters'
    ChartOfCalculationTypes='ChartsOfCalculationTypes'; CalculationRegister='CalculationRegisters'
    BusinessProcess='BusinessProcesses'; Task='Tasks'; IntegrationService='IntegrationServices'
    WebSocketClient='WebSocketClients'
}

function Add-Finding([string]$Kind, [string]$File, [string]$Object, [string]$Message) {
    $relative = $File
    $prefix = $script:RootPath.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if ($File.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        $relative = $File.Substring($prefix.Length)
    }
    $script:Findings.Add([pscustomobject][ordered]@{
        kind=$Kind; severity='error'; path=$relative.Replace('\', '/'); object=$Object; message=$Message
    })
}

function Read-Xml([string]$File, [string]$Object) {
    try {
        $document = New-Object System.Xml.XmlDocument
        $document.XmlResolver = $null
        $settings = New-Object System.Xml.XmlReaderSettings
        $settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
        $settings.XmlResolver = $null
        $reader = [System.Xml.XmlReader]::Create($File, $settings)
        try { $document.Load($reader) } finally { $reader.Dispose() }
        return ,$document
    } catch {
        Add-Finding 'xml-unreadable' $File $Object "Не удалось прочитать XML: $($_.Exception.Message)"
        return $null
    }
}

function Get-MetadataNode($Document, [string]$Type, [string]$File, [string]$Object) {
    $root = $Document.DocumentElement
    if ($root.LocalName -ne 'MetaDataObject' -or $root.NamespaceURI -ne $MetadataNamespace) {
        Add-Finding 'metadata-root-invalid' $File $Object 'Ожидается MetaDataObject в пространстве имён MDClasses.'
        return $null
    }
    $node = $root.SelectSingleNode("*[local-name()='$Type' and namespace-uri()='$MetadataNamespace']")
    if (-not $node) { Add-Finding 'metadata-root-invalid' $File $Object "Не найден объект $Type." }
    return $node
}

function Test-ObjectFile([string]$File, [string]$Type, [string]$Name, [string]$Key) {
    # Keep existing but unreadable objects in the inventory: do not cascade into false missing-reference reports.
    if ($script:Objects.ContainsKey($Key)) { return }
    $script:Objects[$Key] = $File
    $document = Read-Xml $File $Key
    if (-not $document) { return }
    $node = Get-MetadataNode $document $Type $File $Key
    if (-not $node) { return }
    $objectVersion = $document.DocumentElement.GetAttribute('version')
    if (-not $objectVersion) {
        Add-Finding 'version-unreadable' $File $Key 'Не указана версия формата объекта.'
    } elseif ($objectVersion -ne $script:DumpVersion) {
        Add-Finding 'version-mismatch' $File $Key "Версия объекта $objectVersion отличается от версии конфигурации $script:DumpVersion."
    }
    $nameNode = $node.SelectSingleNode("*[local-name()='Properties']/*[local-name()='Name']")
    if (-not $nameNode -or $nameNode.InnerText -cne $Name) {
        Add-Finding 'name-mismatch' $File $Key "Имя внутри XML не совпадает с именем файла $Name.xml."
    }
    if ($Type -eq 'Subsystem') {
        $script:ReferenceSources.Add([pscustomobject]@{ File=$File; Key=$Key; Node=$node })
        Test-Composition $node ([System.IO.Path]::ChangeExtension($File, $null)) $Key $File
    }
}

function Test-Composition($Node, [string]$Directory, [string]$ParentKey, [string]$OwnerFile) {
    $composition = $Node.SelectSingleNode("*[local-name()='ChildObjects']")
    $declared = @{}
    $allowed = if ($ParentKey) { @('Subsystem') } else { @($TypeDirectories.Keys) }
    if (-not $composition -and -not $ParentKey) {
        Add-Finding 'composition-missing' $OwnerFile '' 'Не найден состав конфигурации ChildObjects.'
    }
    if ($composition) {
        foreach ($entry in $composition.ChildNodes) {
            if ($entry.NodeType -ne 'Element') { continue }
            $type = $entry.LocalName
            $name = $entry.InnerText.Trim()
            $key = if ($ParentKey) { "$ParentKey.$type.$name" } else { "$type.$name" }
            if ($allowed -notcontains $type) {
                Add-Finding 'unknown-type' $OwnerFile $key "Неизвестный для этого состава тип $type."
                continue
            }
            if ($name -notmatch $Identifier) {
                Add-Finding 'invalid-name' $OwnerFile $key 'Некорректное имя объекта в составе.'
                continue
            }
            if ($declared.ContainsKey($key)) {
                Add-Finding 'duplicate-entry' $OwnerFile $key 'Объект объявлен в составе несколько раз.'
                continue
            }
            $declared[$key] = $true
            $file = Join-Path (Join-Path $Directory $TypeDirectories[$type]) "$name.xml"
            if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
                Add-Finding 'missing-file' $file $key 'Объект объявлен в составе, но файл отсутствует.'
            } else { Test-ObjectFile $file $type $name $key }
        }
    }
    foreach ($type in $allowed) {
        $folder = Join-Path $Directory $TypeDirectories[$type]
        if (-not (Test-Path -LiteralPath $folder -PathType Container)) { continue }
        foreach ($file in (Get-ChildItem -LiteralPath $folder -File -Filter '*.xml' | Sort-Object Name)) {
            $key = if ($ParentKey) { "$ParentKey.$type.$($file.BaseName)" } else { "$type.$($file.BaseName)" }
            if (-not $declared.ContainsKey($key)) {
                Add-Finding 'orphan-file' $file.FullName $key 'Файл объекта отсутствует в объявленном составе.'
                Test-ObjectFile $file.FullName $type $file.BaseName $key
            }
        }
    }
}

# Resolve the owning metadata object, not embedded attributes or module names.
function Get-ObjectKey([string]$Reference) {
    $parts = $Reference.Split('.')
    if ($parts.Count -lt 2 -or ($parts[0] -ne 'Configuration' -and -not $TypeDirectories.Contains($parts[0]))) { return $null }
    if ($parts[1] -notmatch $Identifier) { return $null }
    $key = "$($parts[0]).$($parts[1])"
    if ($parts[0] -eq 'Subsystem') {
        for ($i = 2; $i + 1 -lt $parts.Count -and $parts[$i] -eq 'Subsystem'; $i += 2) {
            if ($parts[$i + 1] -notmatch $Identifier) { return $null }
            $key += ".Subsystem.$($parts[$i + 1])"
        }
    }
    return $key
}

try {
    if (Test-Path -LiteralPath $script:RootPath -PathType Leaf) {
        $configurationFile = $script:RootPath
        $script:RootPath = Split-Path $configurationFile -Parent
    } else { $configurationFile = Join-Path $script:RootPath 'Configuration.xml' }
    if ($OutFile) {
        $outputCandidate = if ([System.IO.Path]::IsPathRooted($OutFile)) { $OutFile } else { Join-Path (Get-Location).Path $OutFile }
        $outputCandidate = [System.IO.Path]::GetFullPath($outputCandidate)
        $rootPrefix = $script:RootPath.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
        if ($outputCandidate -eq $script:RootPath -or $outputCandidate.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'OutFile должен находиться вне проверяемой выгрузки: исходные файлы не изменяются.'
        }
        $script:OutputPath = $outputCandidate
    }
    if (-not (Test-Path -LiteralPath $configurationFile -PathType Leaf)) {
        Add-Finding 'configuration-missing' $configurationFile '' 'Не найден Configuration.xml полной выгрузки.'
    } else {
        $configuration = Read-Xml $configurationFile ''
        if ($configuration) {
            $node = Get-MetadataNode $configuration 'Configuration' $configurationFile ''
            $script:DumpVersion = $configuration.DocumentElement.GetAttribute('version')
            if (-not $script:DumpVersion) {
                Add-Finding 'version-unreadable' $configurationFile '' 'Не указана версия формата конфигурации.'
            }
            if ($node -and $script:DumpVersion) {
                $nameNode = $node.SelectSingleNode("*[local-name()='Properties']/*[local-name()='Name']")
                if ($nameNode -and $nameNode.InnerText) { $script:Objects["Configuration.$($nameNode.InnerText)"] = $configurationFile }
                $script:ReferenceSources.Add([pscustomobject]@{ File=$configurationFile; Key=''; Node=$node })
                Test-Composition $node $script:RootPath '' $configurationFile
                foreach ($source in $script:ReferenceSources) {
                    # Only reference-bearing properties. A comment containing Catalog.X is ordinary text.
                    $properties = $source.Node.SelectSingleNode("*[local-name()='Properties']")
                    if (-not $properties) { continue }
                    $references = if ($source.Key) {
                        $properties.SelectNodes("*[local-name()='Content']//*[not(*)]")
                    } else {
                        $properties.SelectNodes("*[starts-with(local-name(),'Default')]/descendant-or-self::*[not(*)]")
                    }
                    $seen = @{}
                    foreach ($reference in $references) {
                        $key = Get-ObjectKey $reference.InnerText.Trim()
                        if ($key -and -not $seen.ContainsKey($key) -and -not $script:Objects.ContainsKey($key)) {
                            Add-Finding 'dangling-reference' $source.File $key 'Ссылка ведёт на отсутствующий объект выгрузки.'
                            $seen[$key] = $true
                        }
                    }
                }
                $infoFile = Join-Path $script:RootPath 'ConfigDumpInfo.xml'
                if (Test-Path -LiteralPath $infoFile -PathType Leaf) {
                    $info = Read-Xml $infoFile ''
                    if ($info) {
                        if ($info.DocumentElement.LocalName -ne 'ConfigDumpInfo' -or $info.DocumentElement.NamespaceURI -ne 'http://v8.1c.ru/8.3/xcf/dumpinfo') {
                            Add-Finding 'dump-info-invalid' $infoFile '' 'Ожидается корневой элемент ConfigDumpInfo в пространстве имён dumpinfo.'
                        } else {
                            $infoFormat = $info.DocumentElement.GetAttribute('format')
                            if ($infoFormat -and $infoFormat -ne 'Hierarchical') {
                                Add-Finding 'dump-format-unsupported' $infoFile '' "Поддерживается только иерархическая выгрузка; получен формат $infoFormat."
                            }
                            if ($info.DocumentElement.GetAttribute('version') -ne $script:DumpVersion) {
                                Add-Finding 'dump-info-version' $infoFile '' 'Версия ConfigDumpInfo.xml отличается от версии конфигурации.'
                            }
                            $seen = @{}
                            foreach ($entry in $info.SelectNodes("//*[local-name()='Metadata'][@name]")) {
                                $key = Get-ObjectKey $entry.GetAttribute('name')
                                if ($key -and -not $seen.ContainsKey($key) -and -not $script:Objects.ContainsKey($key)) {
                                    Add-Finding 'dump-info-extra' $infoFile $key 'ConfigDumpInfo.xml содержит отсутствующий объект выгрузки.'
                                    $seen[$key] = $true
                                }
                            }
                        }
                    }
                }
            }
        }
    }
} catch {
    $script:ScanFailed = $true
    Add-Finding 'scan-error' $script:RootPath '' "Обход выгрузки не завершён: $($_.Exception.Message)"
}

$status = if ($script:ScanFailed) { 'error' } elseif ($script:Findings.Count) { 'invalid' } else { 'valid' }
$result = [pscustomobject][ordered]@{
    schema_version=1; status=$status; root=$script:RootPath
    objects_checked=$script:Objects.Count; findings=@($script:Findings.ToArray())
}
if ($Format -eq 'Json') { $text = $result | ConvertTo-Json -Depth 5 } else {
    $lines = @("Проверка полной выгрузки: $status; объектов: $($result.objects_checked); ошибок: $($result.findings.Count)")
    $lines += @($result.findings | ForEach-Object { "[$($_.kind)] $($_.path): $($_.message) $($_.object)" })
    $text = $lines -join [Environment]::NewLine
}
if ($script:OutputPath) { [System.IO.File]::WriteAllText($script:OutputPath, $text, (New-Object System.Text.UTF8Encoding($true))) }
Write-Output $text
if ($status -ne 'valid') { exit 1 }
exit 0
