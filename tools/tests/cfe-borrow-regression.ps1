#Requires -Version 5.1
<#
.SYNOPSIS
    Focused regression tests for cfe-borrow / cfe-validate of the 1c-metadata-manage
    skill (support ticket 4e6f4e67, reported against 96c4d96).

.DESCRIPTION
    Each case pins one defect of the Configurator-shape comparison:

      1. Forms/<Form>.xml of a borrowed form carried an empty <InternalInfo/>;
         Configurator 2.20 marks the Form property as Extended.
      2. CommandSet ended the form-property copy, so CommandSet and every
         property after it (AutoTime, UsePostingMode, RepostOnWrite, ...) were
         lost in both the form and BaseForm.
      3. A single attribute (or tabular-section column) could not be borrowed,
         and the main attribute came only with the whole data-path cascade.
      4. A new extension ChildObjects entry was sorted by name inside its type
         group; Configurator appends it to the end of the group. (In the main
         configuration cf-edit / meta-compile follow NEW_OBJECT_POSITION, pinned
         by metadata-tools-regression.ps1.)
      5. A borrowed form always got an empty Ext/Form/Module.bsl.
      6. A borrowed Document had no <RegisterRecords/>.
      7. cfe-validate check 12 only warned about a CommonPicture / StyleItem the
         borrowed form references but the extension does not borrow. cfe-borrow
         left a style: reference to an unborrowed configuration style item.
      8. Detect-FormatVersion passed the file byte length to String.Substring.
      9. ExcludedCommand was removed inside ChildItems, leaving an element (a
         table without Add / Copy) with an empty CommandSet in both parts
         (ticket 2b392369).

    The fixtures under fixtures/cfe-borrow/ are materialized with CRLF and a
    UTF-8 BOM into a temp directory; no 1C platform or infobase is needed.

    NOTE: this file is deliberately pure ASCII (Windows PowerShell 5.1 reads a
    BOM-less .ps1 as ANSI). Cyrillic identifiers live in the fixture files; the
    assertions below address them by pattern or read them from the fixtures.

.PARAMETER Filter
    Run only cases whose name matches this wildcard pattern.

.PARAMETER KeepWorkDir
    Do not delete the temp working directory - useful when a case fails.

.EXAMPLE
    powershell -NoProfile -File tools\tests\cfe-borrow-regression.ps1
    powershell -NoProfile -File tools\tests\cfe-borrow-regression.ps1 -Filter 'attribute*'
#>
[CmdletBinding()]
param(
    [string]$Filter = '*',
    [switch]$KeepWorkDir
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot    = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$FixturesDir = Join-Path $PSScriptRoot 'fixtures\cfe-borrow'
$ScriptsDir  = Join-Path $RepoRoot 'content\skills\1c-metadata-manage\tools\1c-cfe-manage\scripts'
$CfeBorrow   = Join-Path $ScriptsDir 'cfe-borrow.ps1'
$CfeValidate = Join-Path $ScriptsDir 'cfe-validate.ps1'

foreach ($required in @($CfeBorrow, $CfeValidate, (Join-Path $FixturesDir 'base'), (Join-Path $FixturesDir 'extension'))) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing prerequisite: $required" }
}

# ---------------------------------------------------------------- infrastructure

$script:Cases    = @()
$script:Failures = @()

function Register-Case([string]$Name, [scriptblock]$Body) {
    $script:Cases += [pscustomobject]@{ Name = $Name; Body = $Body }
}

function Fail([string]$Message) { throw [System.Exception]::new($Message) }

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { Fail $Message }
}

function Assert-Equal($Expected, $Actual, [string]$What) {
    if ("$Expected" -ne "$Actual") { Fail "$What : expected [$Expected], got [$Actual]" }
}

# File text without BOM, line breaks normalized to LF (the tools write CRLF).
function Read-Text([string]$Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $offset = if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { 3 } else { 0 }
    return ([System.Text.Encoding]::UTF8.GetString($bytes, $offset, $bytes.Length - $offset) -replace "`r`n", "`n")
}

function Test-SameBytes([byte[]]$Before, [string]$Path) {
    return ([Convert]::ToBase64String($Before) -eq [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($Path)))
}

# Materializes a fixture tree with a UTF-8 BOM and the requested EOL.
function Copy-Fixture([string]$Name, [string]$Dest, [string]$Eol = "`r`n") {
    $src = Join-Path $FixturesDir $Name
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    $bom = New-Object System.Text.UTF8Encoding($true)
    foreach ($file in (Get-ChildItem -LiteralPath $src -Recurse -File)) {
        $rel = $file.FullName.Substring($src.Length).TrimStart('\', '/')
        $out = Join-Path $Dest $rel
        New-Item -ItemType Directory -Path (Split-Path $out -Parent) -Force | Out-Null
        $text = Read-Text $file.FullName
        if ($Eol -ne "`n") { $text = $text -replace "`n", $Eol }
        [System.IO.File]::WriteAllText($out, $text, $bom)
    }
}

function Invoke-Tool([string]$Script, [string[]]$ToolArgs, [string]$WorkDir) {
    $stdout = [System.IO.Path]::GetTempFileName()
    $stderr = [System.IO.Path]::GetTempFileName()
    try {
        $psArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$Script`"")
        foreach ($a in $ToolArgs) {
            if ($a -match '\s') { $psArgs += "`"$a`"" } else { $psArgs += $a }
        }
        $psExe = if ($PSVersionTable.PSEdition -eq 'Core' -and -not $IsWindows) { Join-Path $PSHOME 'pwsh' } else { 'powershell.exe' }
        $proc = Start-Process -FilePath $psExe -ArgumentList $psArgs `
            -WorkingDirectory $WorkDir -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        return [pscustomobject]@{
            ExitCode = $proc.ExitCode
            StdOut   = (Get-Content -LiteralPath $stdout -Raw -Encoding UTF8)
            StdErr   = (Get-Content -LiteralPath $stderr -Raw -Encoding UTF8)
        }
    } finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

# A fresh base configuration + extension pair for one case.
function New-Workspace([string]$Work) {
    $ws = [pscustomobject]@{ Work = $Work; Base = (Join-Path $Work 'base'); Ext = (Join-Path $Work 'ext') }
    Copy-Fixture 'base' $ws.Base
    Copy-Fixture 'extension' $ws.Ext
    return $ws
}

function Invoke-Borrow($Ws, [string]$Object, [string[]]$Extra = @(), [int]$ExpectExit = 0) {
    $toolArgs = @('-ExtensionPath', $Ws.Ext, '-ConfigPath', $Ws.Base, '-Object', $Object) + $Extra
    $run = Invoke-Tool $CfeBorrow $toolArgs $Ws.Work
    Assert-Equal $ExpectExit $run.ExitCode "cfe-borrow $Object exit code (stderr: $($run.StdErr))"
    return $run
}

function Invoke-Validate($Ws) {
    return (Invoke-Tool $CfeValidate @('-ExtensionPath', $Ws.Ext, '-Detailed') $Ws.Work)
}

function Get-Xml([string]$Path) {
    $doc = New-Object System.Xml.XmlDocument
    $doc.PreserveWhitespace = $true
    $doc.Load($Path)
    $ns = New-Object System.Xml.XmlNamespaceManager($doc.NameTable)
    $ns.AddNamespace('md', 'http://v8.1c.ru/8.3/MDClasses')
    $ns.AddNamespace('xr', 'http://v8.1c.ru/8.3/xcf/readable')
    return [pscustomobject]@{ Doc = $doc; Ns = $ns }
}

# <Type> block of a named attribute, as text with its own line layout (LF).
function Get-AttributeTypeText($Xml, [string]$XPath) {
    $node = $Xml.Doc.SelectSingleNode($XPath, $Xml.Ns)
    Assert-True ($null -ne $node) "node not found: $XPath"
    $type = $node.SelectSingleNode('md:Properties/md:Type', $Xml.Ns)
    return ([regex]::Replace($type.OuterXml, '\s+xmlns(?::\w+)?="[^"]*"', '') -replace "`r`n", "`n")
}

# Text between the line after $StartMarker and the first $EndMarker after it.
function Get-Slice([string]$Text, [string]$StartMarker, [string]$EndMarker) {
    $s = $Text.IndexOf($StartMarker)
    Assert-True ($s -ge 0) "marker not found: $StartMarker"
    $s = $Text.IndexOf("`n", $s) + 1
    $e = $Text.IndexOf($EndMarker, $s)
    Assert-True ($e -ge 0) "marker not found: $EndMarker"
    return $Text.Substring($s, $e - $s)
}

function Add-Tab([string]$Block) {
    # BaseForm shifts every tag line one tab deeper; a continuation line of a text keeps its bytes.
    return (($Block.TrimEnd("`n") -split "`n" | ForEach-Object { if ($_ -match '^\s*<') { "`t$_" } else { $_ } }) -join "`n") + "`n"
}

function Get-ChildObjectEntries([string]$ConfigurationXml) {
    $text = Read-Text $ConfigurationXml
    $block = [regex]::Match($text, '(?s)<ChildObjects>(.*?)</ChildObjects>').Groups[1].Value
    return @([regex]::Matches($block, '<(\w+)>([^<]*)</\1>') | ForEach-Object { "$($_.Groups[1].Value):$($_.Groups[2].Value)" })
}

$FormRel     = 'Documents\Zakaz\Forms\DocumentForm'
$FormObject  = 'Document.Zakaz.Form.DocumentForm'

# ---------------------------------------------------------------- 1. form metadata InternalInfo

Register-Case 'form metadata: InternalInfo marks the Form property Extended' {
    param($work)
    $ws = New-Workspace $work
    Invoke-Borrow $ws $FormObject | Out-Null
    $meta = Read-Text (Join-Path $ws.Ext "$FormRel.xml")
    $expected = "`t`t<InternalInfo>`n`t`t`t<xr:PropertyState>`n`t`t`t`t<xr:Property>Form</xr:Property>`n`t`t`t`t<xr:State>Extended</xr:State>`n`t`t`t</xr:PropertyState>`n`t`t</InternalInfo>`n`t`t<Properties>"
    Assert-True $meta.Contains($expected) "form metadata lacks the 2.20 PropertyState block:`n$meta"
    Assert-True (-not $meta.Contains('<InternalInfo/>')) 'form metadata still has an empty InternalInfo'
    $srcUuid = (Get-Xml (Join-Path $ws.Base "$FormRel.xml")).Doc.DocumentElement.SelectSingleNode('*[local-name()="Form"]').GetAttribute('uuid')
    Assert-True $meta.Contains("<ExtendedConfigurationObject>$srcUuid</ExtendedConfigurationObject>") 'form is not linked to the source form uuid'
}

# ---------------------------------------------------------------- 2. CommandSet and the properties after it

Register-Case 'form: CommandSet and every property before AutoCommandBar reach the form and BaseForm' {
    param($work)
    $ws = New-Workspace $work
    Invoke-Borrow $ws $FormObject | Out-Null
    $src = Read-Text (Join-Path $ws.Base "$FormRel\Ext\Form.xml")
    $out = Read-Text (Join-Path $ws.Ext "$FormRel\Ext\Form.xml")
    $srcProps = Get-Slice $src '<Form ' "`t<AutoCommandBar"
    foreach ($probe in @("`t<CommandSet>`n`t`t<ExcludedCommand>Copy</ExcludedCommand>", "`t<AutoTime>CurrentOrLast</AutoTime>", "`t<UsePostingMode>Auto</UsePostingMode>", "`t<RepostOnWrite>true</RepostOnWrite>")) {
        Assert-True $srcProps.Contains($probe) "fixture sanity: source properties lack $probe"
    }
    Assert-Equal $srcProps (Get-Slice $out '<Form ' "`t<AutoCommandBar") 'form properties of the borrowed form'
    Assert-Equal (Add-Tab $srcProps) (Get-Slice $out '<BaseForm ' "`t`t<AutoCommandBar") 'form properties of BaseForm'
}

# ---------------------------------------------------------------- 3. single attribute, column, main attribute alone

Register-Case 'attribute: Document.X.Attribute.Y borrows that attribute alone' {
    param($work)
    $ws = New-Workspace $work
    Invoke-Borrow $ws 'Document.Zakaz.Attribute.Kontragent' | Out-Null
    $objFile = Join-Path $ws.Ext 'Documents\Zakaz.xml'
    $ext = Get-Xml $objFile
    $src = Get-Xml (Join-Path $ws.Base 'Documents\Zakaz.xml')
    $attrs = $ext.Doc.SelectNodes('/md:MetaDataObject/md:Document/md:ChildObjects/md:Attribute', $ext.Ns)
    Assert-Equal 1 $attrs.Count 'adopted attributes'
    Assert-Equal 0 ($ext.Doc.SelectNodes('//md:TabularSection', $ext.Ns)).Count 'adopted tabular sections'
    $a = $attrs[0]
    Assert-Equal 'Kontragent' $a.SelectSingleNode('md:Properties/md:Name', $ext.Ns).InnerText 'attribute name'
    Assert-Equal 'Adopted' $a.SelectSingleNode('md:Properties/md:ObjectBelonging', $ext.Ns).InnerText 'ObjectBelonging'
    $srcAttrXPath = '/md:MetaDataObject/md:Document/md:ChildObjects/md:Attribute[md:Properties/md:Name="Kontragent"]'
    $srcUuid = $src.Doc.SelectSingleNode($srcAttrXPath, $src.Ns).GetAttribute('uuid')
    Assert-Equal $srcUuid $a.SelectSingleNode('md:Properties/md:ExtendedConfigurationObject', $ext.Ns).InnerText 'ExtendedConfigurationObject'
    Assert-Equal (Get-AttributeTypeText $src $srcAttrXPath) (Get-AttributeTypeText $ext '/md:MetaDataObject/md:Document/md:ChildObjects/md:Attribute') 'attribute <Type> block'
    # The type object is borrowed as a shell; nothing else cascades.
    Assert-True (Test-Path (Join-Path $ws.Ext 'Catalogs\Kontragenty.xml')) 'type object Catalog.Kontragenty not borrowed'
    Assert-True (-not (Test-Path (Join-Path $ws.Ext 'Catalogs\Nomenklatura.xml'))) 'Catalog.Nomenklatura borrowed by a cascade'
    $entries = Get-ChildObjectEntries (Join-Path $ws.Ext 'Configuration.xml')
    Assert-True ($entries -contains 'Catalog:Kontragenty') 'Catalog.Kontragenty not registered'
    Assert-True ($entries -contains 'Document:Zakaz') 'Document.Zakaz not registered'
    # Re-run is idempotent.
    $before = [System.IO.File]::ReadAllBytes($objFile)
    Invoke-Borrow $ws 'Document.Zakaz.Attribute.Kontragent' | Out-Null
    Assert-True (Test-SameBytes $before $objFile) 're-borrow changed the object file'
    # An unknown attribute is refused, not taken for an object name.
    $bad = Invoke-Borrow $ws 'Document.Zakaz.Attribute.Missing' -ExpectExit 1
    Assert-True ($bad.StdErr -match 'Source attribute not found') "unexpected refusal: $($bad.StdErr)"
}

Register-Case 'attribute: a tabular-section column path borrows the section with that column' {
    param($work)
    $ws = New-Workspace $work
    Invoke-Borrow $ws 'Document.Zakaz.TabularSection.Tovary.Attribute.Kolichestvo' | Out-Null
    Invoke-Borrow $ws 'Document.Zakaz.TabularSection.Tovary.Attribute.Nomenklatura' | Out-Null
    $ext = Get-Xml (Join-Path $ws.Ext 'Documents\Zakaz.xml')
    $src = Get-Xml (Join-Path $ws.Base 'Documents\Zakaz.xml')
    $tsList = $ext.Doc.SelectNodes('/md:MetaDataObject/md:Document/md:ChildObjects/md:TabularSection', $ext.Ns)
    Assert-Equal 1 $tsList.Count 'adopted tabular sections'
    Assert-Equal 0 ($ext.Doc.SelectNodes('/md:MetaDataObject/md:Document/md:ChildObjects/md:Attribute', $ext.Ns)).Count 'top-level attributes'
    $ts = $tsList[0]
    $srcTsXPath = '/md:MetaDataObject/md:Document/md:ChildObjects/md:TabularSection[md:Properties/md:Name="Tovary"]'
    $srcTs = $src.Doc.SelectSingleNode($srcTsXPath, $src.Ns)
    Assert-Equal $srcTs.GetAttribute('uuid') $ts.SelectSingleNode('md:Properties/md:ExtendedConfigurationObject', $ext.Ns).InnerText 'tabular section ExtendedConfigurationObject'
    $cats = @($ts.SelectNodes('md:InternalInfo/xr:GeneratedType', $ext.Ns) | ForEach-Object { $_.GetAttribute('category') })
    Assert-Equal 'TabularSection,TabularSectionRow' ($cats -join ',') 'tabular section generated types'
    $cols = @($ts.SelectNodes('md:ChildObjects/md:Attribute', $ext.Ns))
    Assert-Equal 'Kolichestvo,Nomenklatura' (($cols | ForEach-Object { $_.SelectSingleNode('md:Properties/md:Name', $ext.Ns).InnerText }) -join ',') 'columns in borrow order'
    foreach ($col in $cols) {
        $name = $col.SelectSingleNode('md:Properties/md:Name', $ext.Ns).InnerText
        $srcColXPath = "$srcTsXPath/md:ChildObjects/md:Attribute[md:Properties/md:Name=`"$name`"]"
        Assert-Equal $src.Doc.SelectSingleNode($srcColXPath, $src.Ns).GetAttribute('uuid') $col.SelectSingleNode('md:Properties/md:ExtendedConfigurationObject', $ext.Ns).InnerText "column $name ExtendedConfigurationObject"
        Assert-Equal (Get-AttributeTypeText $src $srcColXPath) (Get-AttributeTypeText $ext "/md:MetaDataObject/md:Document/md:ChildObjects/md:TabularSection/md:ChildObjects/md:Attribute[md:Properties/md:Name=`"$name`"]") "column $name <Type> block"
    }
    Assert-True (Test-Path (Join-Path $ws.Ext 'Catalogs\Nomenklatura.xml')) 'column type object Catalog.Nomenklatura not borrowed'
    Assert-True (-not (Test-Path (Join-Path $ws.Ext 'Catalogs\Kontragenty.xml'))) 'Catalog.Kontragenty borrowed without being asked for'
    $v = Invoke-Validate $ws
    Assert-Equal 0 $v.ExitCode "cfe-validate after column borrowing:`n$($v.StdOut)"
}

Register-Case 'form: -BorrowMainAttribute Only adds the main attribute without the cascade' {
    param($work)
    $ws = New-Workspace $work
    Invoke-Borrow $ws $FormObject @('-BorrowMainAttribute', 'Only') | Out-Null
    $out = Read-Text (Join-Path $ws.Ext "$FormRel\Ext\Form.xml")
    Assert-Equal 2 ([regex]::Matches($out, '<Attribute name="[^"]+" id="1000001">\s*<Type><v8:Type>cfg:DocumentObject\.Zakaz</v8:Type></Type>\s*<MainAttribute>true</MainAttribute>')).Count 'main attribute in the form and in BaseForm'
    Assert-Equal 0 ([regex]::Matches($out, 'DataPath>')).Count 'data paths left in the borrowed form'
    # Stripped the same way in both parts: BaseForm ChildItems is the form's ChildItems one tab deeper.
    $formItems = Get-Slice $out '<Form ' "`n`t<Attributes>"
    $formItems = $formItems.Substring($formItems.IndexOf("`n`t<ChildItems>") + 1) + "`n"
    $baseItems = Get-Slice $out '<BaseForm ' "`n`t`t<Attributes>"
    $baseItems = $baseItems.Substring($baseItems.IndexOf("`n`t`t<ChildItems>") + 1) + "`n"
    Assert-Equal (Add-Tab $formItems) $baseItems 'BaseForm ChildItems vs form ChildItems'
    $obj = Read-Text (Join-Path $ws.Ext 'Documents\Zakaz.xml')
    Assert-True (-not ($obj -match '<Attribute ')) 'object attributes cascaded into the borrowed document'
    Assert-True (-not (Test-Path (Join-Path $ws.Ext 'Catalogs\Kontragenty.xml'))) 'attribute type objects cascaded'
}

Register-Case 'form: an element CommandSet keeps its ExcludedCommand list in the form and BaseForm' {
    param($work)
    $ws = New-Workspace $work
    Invoke-Borrow $ws $FormObject | Out-Null
    $out = Read-Text (Join-Path $ws.Ext "$FormRel\Ext\Form.xml")
    Assert-Equal 2 ([regex]::Matches($out, '<CommandSet>\s*<ExcludedCommand>Add</ExcludedCommand>\s*<ExcludedCommand>Copy</ExcludedCommand>\s*</CommandSet>')).Count 'table CommandSet with Add/Copy in the form and in BaseForm'
    Assert-Equal 0 ([regex]::Matches($out, '<CommandSet>\s*</CommandSet>|<CommandSet/>')).Count 'empty CommandSet in the borrowed form'
}

# ---------------------------------------------------------------- 4. ChildObjects order

Register-Case 'ChildObjects: a borrowed object is appended to the end of its type group' {
    param($work)
    $ws = New-Workspace $work
    Invoke-Borrow $ws 'Catalog.Alpha ;; Document.Zakaz ;; Catalog.Kontragenty' | Out-Null
    $entries = @(Get-ChildObjectEntries (Join-Path $ws.Ext 'Configuration.xml') | Where-Object { $_ -notlike 'Language:*' })
    Assert-Equal 'Catalog:Zeta,Catalog:Alpha,Catalog:Kontragenty,Document:Zakaz' ($entries -join ',') 'extension ChildObjects order'
}

# ---------------------------------------------------------------- 5. form module

Register-Case 'form module: no empty Module.bsl, an existing one survives re-borrow' {
    param($work)
    $ws = New-Workspace $work
    Invoke-Borrow $ws $FormObject | Out-Null
    $moduleDir = Join-Path $ws.Ext "$FormRel\Ext\Form"
    $module = Join-Path $moduleDir 'Module.bsl'
    Assert-True (-not (Test-Path $module)) 'an empty Module.bsl was written for the borrowed form'
    Assert-True (-not (Test-Path $moduleDir)) 'an empty Ext/Form directory was left behind'
    New-Item -ItemType Directory -Path $moduleDir -Force | Out-Null
    $code = "&AtClient`r`nProcedure Probe()`r`nEndProcedure`r`n"
    [System.IO.File]::WriteAllText($module, $code, (New-Object System.Text.UTF8Encoding($true)))
    $before = [System.IO.File]::ReadAllBytes($module)
    Invoke-Borrow $ws $FormObject | Out-Null
    Assert-True (Test-Path $module) 're-borrow deleted the form module'
    Assert-True (Test-SameBytes $before $module) 're-borrow changed the form module'
}

# ---------------------------------------------------------------- 6. Document RegisterRecords

Register-Case 'document: a borrowed Document carries an empty RegisterRecords' {
    param($work)
    $ws = New-Workspace $work
    Invoke-Borrow $ws 'Document.Zakaz' | Out-Null
    $obj = Read-Text (Join-Path $ws.Ext 'Documents\Zakaz.xml')
    Assert-True ($obj -match "</ExtendedConfigurationObject>`n`t`t`t<RegisterRecords/>`n`t`t</Properties>") "no <RegisterRecords/> in the borrowed document:`n$obj"
}

# ---------------------------------------------------------------- 7. cfe-validate check 12 (+ check 11 module warning)

Register-Case 'cfe-validate: fresh form borrow is clean; an unborrowed CommonPicture / StyleItem is an error' {
    param($work)
    $ws = New-Workspace $work
    Invoke-Borrow $ws $FormObject | Out-Null
    $v = Invoke-Validate $ws
    Assert-Equal 0 $v.ExitCode "cfe-validate after a form borrow:`n$($v.StdOut)"
    Assert-True (-not ($v.StdOut -match 'Module\.bsl missing')) "borrowed form without a module reported:`n$($v.StdOut)"
    Assert-True (-not ($v.StdOut -match '\[(ERROR|WARN)\]\s+12\.')) "check 12 complained about a complete borrow:`n$($v.StdOut)"
    # Drop the auto-borrowed picture and style item from the extension: the form now references both.
    $cfg = Join-Path $ws.Ext 'Configuration.xml'
    $text = [System.IO.File]::ReadAllText($cfg)
    $text = [regex]::Replace($text, '\r?\n\t*<(CommonPicture|StyleItem)>[^<]*</\1>', '')
    [System.IO.File]::WriteAllText($cfg, $text, (New-Object System.Text.UTF8Encoding($true)))
    $v = Invoke-Validate $ws
    Assert-Equal 1 $v.ExitCode "cfe-validate exit code with unborrowed dependencies:`n$($v.StdOut)"
    Assert-True ($v.StdOut -match '\[ERROR\] 12\. [^\r\n]*CommonPicture\.PicA') "missing CommonPicture is not an error:`n$($v.StdOut)"
    Assert-True ($v.StdOut -match '\[ERROR\] 12\. [^\r\n]*StyleItem\.') "missing StyleItem is not an error:`n$($v.StdOut)"
    Assert-True (-not ($v.StdOut -match 'FormTextColor')) "platform style item reported:`n$($v.StdOut)"
}

Register-Case 'form: an unborrowed configuration style is stripped, a platform style stays' {
    param($work)
    $ws = New-Workspace $work
    $srcForm = Read-Text (Join-Path $ws.Base "$FormRel\Ext\Form.xml")
    $styleNames = @([regex]::Matches($srcForm, 'style:([^<"\s]+)') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique)
    $platform = 'FormTextColor'
    $configStyle = @($styleNames | Where-Object { $_ -and ($_ -ne $platform) })
    Assert-True ($configStyle.Count -ge 1) 'fixture has no configuration style reference'
    Remove-Item -LiteralPath (Join-Path $ws.Base 'StyleItems') -Recurse -Force
    Invoke-Borrow $ws $FormObject | Out-Null
    $out = Read-Text (Join-Path $ws.Ext "$FormRel\Ext\Form.xml")
    foreach ($name in $configStyle) {
        Assert-True (-not $out.Contains("style:$name")) "unborrowed style reference left in the form: $name"
    }
    Assert-True $out.Contains("style:$platform") 'platform style item was stripped'
    Assert-True (-not (Test-Path (Join-Path $ws.Ext 'StyleItems'))) 'a missing source style item was still borrowed'
}

# ---------------------------------------------------------------- 8. Detect-FormatVersion character length

Register-Case 'format version: a short Cyrillic Configuration.xml does not throw on Substring' {
    param($work)
    $ws = New-Workspace $work
    $cfg = Join-Path $ws.Ext 'Configuration.xml'
    $cyr = -join @(0x0422, 0x0435, 0x0441, 0x0442 | ForEach-Object { [char]$_ })
    $short = "<?xml version=`"1.0`" encoding=`"UTF-8`"?>`r`n" +
        "<MetaDataObject xmlns=`"http://v8.1c.ru/8.3/MDClasses`" version=`"2.20`">`r`n" +
        "`t<Configuration uuid=`"e0e0e0e0-0000-4000-8000-000000000001`">`r`n" +
        "`t`t<Properties><Name>$cyr</Name><NamePrefix></NamePrefix></Properties>`r`n" +
        "`t`t<ChildObjects></ChildObjects>`r`n" +
        "`t</Configuration>`r`n</MetaDataObject>`r`n"
    [System.IO.File]::WriteAllText($cfg, $short, (New-Object System.Text.UTF8Encoding($true)))
    $fileBytes = [System.IO.File]::ReadAllBytes($cfg)
    $charLen = ([System.IO.File]::ReadAllText($cfg, [System.Text.Encoding]::UTF8)).Length
    $byteLen = $fileBytes.Length
    $reproduces = $false
    if (($byteLen -le 2000) -and ($byteLen -gt $charLen)) { $reproduces = $true }
    Assert-True $reproduces "fixture did not reproduce the byte/char mismatch ($byteLen bytes, $charLen chars)"
    $run = Invoke-Borrow $ws 'Catalog.Alpha'
    $stderrText = ''
    if ($null -ne $run.StdErr) { $stderrText = [string]$run.StdErr }
    $substringThrew = $stderrText.Contains('Substring')
    Assert-True (-not $substringThrew) "Detect-FormatVersion still uses file byte length: $stderrText"
    Assert-Equal 0 $run.ExitCode "borrow after a short Cyrillic Configuration.xml (stderr: $stderrText)"
    $saved = Read-Text $cfg
    $hasVersion = $saved.Contains('version="2.20"')
    $hasCatalog = $saved.Contains('<Catalog>Alpha</Catalog>')
    Assert-True $hasVersion 'format version was not read from the short Configuration.xml'
    Assert-True $hasCatalog 'borrow did not register the object'
}

# ---------------------------------------------------------------- run

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("1c-rules-cfe-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $root -Force | Out-Null
Write-Host "Work dir: $root" -ForegroundColor DarkGray
Write-Host ''

$index = 0
foreach ($case in $script:Cases) {
    if ($case.Name -notlike $Filter) { continue }
    $index++
    $work = Join-Path $root ("case{0:d2}" -f $index)
    New-Item -ItemType Directory -Path $work -Force | Out-Null
    try {
        & $case.Body $work
        Write-Host "[PASS] $($case.Name)" -ForegroundColor Green
    } catch {
        $script:Failures += "$($case.Name): $($_.Exception.Message)"
        Write-Host "[FAIL] $($case.Name)" -ForegroundColor Red
        Write-Host "       $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ''
if ($index -eq 0) {
    Write-Host "No case matched filter '$Filter'." -ForegroundColor Yellow
    exit 1
}
if ($script:Failures.Count -eq 0) {
    Write-Host "$index/$index passed." -ForegroundColor Green
    if (-not $KeepWorkDir) { Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue }
    exit 0
}
Write-Host "$($index - $script:Failures.Count)/$index passed, $($script:Failures.Count) failed." -ForegroundColor Red
Write-Host "Work dir kept for inspection: $root" -ForegroundColor Yellow
exit 1
