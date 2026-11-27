#Requires -Version 5.1
<#
.SYNOPSIS
    Read-only dump hygiene and nested-orphan check for 1C Designer XML / BSL sources.
.DESCRIPTION
    Complements dump-validate.ps1 (which covers root Configuration.xml composition):
      1. Nested orphans inside metadata objects: unregistered Forms/ and Templates/
         files or folders, missing files for registered <Form>/<Template>, orphan
         object directories without a sibling <Name>.xml, and stray temp/backup/
         quarantine files inside the dump.
      2. BSL hygiene (whole dump via -ConfigPath or targeted files via -Paths):
         invalid UTF-8, missing UTF-8 BOM, mixed CRLF/LF endings, unresolved
         git/resync conflict markers, unclosed #Область/#Если/#Вставка/#Удаление
         directives, uncommented Сообщить() calls, and bare TODO/FIXME without a
         task reference.
    Read-only: never modifies, repairs or deletes any file.
#>
[CmdletBinding(PositionalBinding=$false)]
param(
    [Alias('Path')]
    [string]$ConfigPath,

    [string[]]$Paths,

    [ValidateSet('Text', 'Json')]
    [string]$Format = 'Text',

    [string]$OutFile,

    [switch]$FailOnWarn
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if (-not $ConfigPath -and (-not $Paths -or $Paths.Count -eq 0)) {
    Write-Error 'Specify -ConfigPath <dump-directory> and/or -Paths <bsl-or-xml-files>.'
    exit 2
}

$script:Findings = New-Object System.Collections.Generic.List[object]
$script:FilesChecked = 0
$script:RootPath = ''
$MetadataNamespace = 'http://v8.1c.ru/8.3/MDClasses'

$ObjectFolders = @(
    'Catalogs','Documents','Enums','ExchangePlans','ChartsOfCharacteristicTypes',
    'ChartsOfAccounts','ChartsOfCalculationTypes','BusinessProcesses','Tasks',
    'InformationRegisters','AccumulationRegisters','AccountingRegisters','CalculationRegisters',
    'Reports','DataProcessors','DocumentJournals','FilterCriteria','SettingsStorages',
    'ExternalDataSources'
)

$StrayPatterns = @('*.bak','*.orig','*.tmp','*.rej','*~')

function Add-Finding {
    param(
        [string]$Kind,
        [ValidateSet('error','warning')][string]$Severity,
        [string]$RelPath,
        [string]$Message
    )
    $script:Findings.Add([PSCustomObject]@{
        kind     = $Kind
        severity = $Severity
        path     = $RelPath
        message  = $Message
    })
}

function Get-RelPath([string]$fullPath) {
    if (-not $script:RootPath) { return $fullPath }
    $r = $script:RootPath.TrimEnd('\','/')
    if ($fullPath.StartsWith($r + '\', [System.StringComparison]::OrdinalIgnoreCase) -or
        $fullPath.StartsWith($r + '/', [System.StringComparison]::OrdinalIgnoreCase)) {
        return ($fullPath.Substring($r.Length + 1) -replace '\\','/')
    }
    return ($fullPath -replace '\\','/')
}

function Test-BslFile([string]$fullPath) {
    $script:FilesChecked++
    $rel = Get-RelPath $fullPath
    try {
        $bytes = [System.IO.File]::ReadAllBytes($fullPath)
    } catch {
        Add-Finding -Kind 'bsl-unreadable' -Severity 'error' -RelPath $rel -Message "Cannot read file: $($_.Exception.Message)"
        return
    }

    if ($bytes.Length -eq 0) { return }

    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    if (-not $hasBom) {
        Add-Finding -Kind 'bsl-no-bom' -Severity 'warning' -RelPath $rel -Message 'BSL file is missing UTF-8 BOM (Configurator expects UTF-8 with BOM).'
    }

    $strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
    try {
        $offset = if ($hasBom) { 3 } else { 0 }
        $text = $strictUtf8.GetString($bytes, $offset, $bytes.Length - $offset)
    } catch {
        Add-Finding -Kind 'bsl-invalid-utf8' -Severity 'error' -RelPath $rel -Message 'BSL file contains invalid UTF-8 byte sequence.'
        return
    }

    # Line endings
    $hasCrLf = $text.Contains("`r`n")
    $withoutCrLf = $text.Replace("`r`n", '')
    $hasBareLf = $withoutCrLf.Contains("`n")
    $hasBareCr = $withoutCrLf.Contains("`r")
    if ($hasBareCr -or ($hasCrLf -and $hasBareLf)) {
        Add-Finding -Kind 'bsl-mixed-eol' -Severity 'warning' -RelPath $rel -Message 'BSL file mixes CRLF and LF (or contains bare CR).'
    }

    $lines = $text -replace "`r`n", "`n" -replace "`r", "`n" -split "`n"
    $inMultilineStr = $false
    $stack = New-Object System.Collections.Generic.Stack[object]

    $reConflict = [regex]::new('^(?:<{7}\s|={7}\s*$|>{7}\s)')
    $reResyncConflict = [regex]::new('//\s*\[РЕСИНК-КОНФЛИКТ\]', 'IgnoreCase')
    $reSoobschit = [regex]::new('(?<![\w.])(?:Сообщить|Message)\s*\(', 'IgnoreCase')
    $reBareTodo = [regex]::new('//\s*(?:TODO|FIXME)\b(.*)$', 'IgnoreCase')
    $reTaskRef = [regex]::new('(?:#\d+|No\.\s*\S+|№\s*\S+|[A-Z]{2,10}-\d+|\bТЗ[- ]?\d+|\b[0-9a-f]{7,}\b)', 'IgnoreCase')

    $reRegionStart = [regex]::new('^#\s*(?:Область|Region)\b', 'IgnoreCase')
    $reRegionEnd   = [regex]::new('^#\s*(?:КонецОбласти|EndRegion)\b', 'IgnoreCase')
    $reIfStart     = [regex]::new('^#\s*(?:Если|If)\b', 'IgnoreCase')
    $reIfEnd       = [regex]::new('^#\s*(?:КонецЕсли|EndIf)\b', 'IgnoreCase')
    $reInsStart    = [regex]::new('^#\s*(?:Вставка|Insert)\b', 'IgnoreCase')
    $reInsEnd      = [regex]::new('^#\s*(?:КонецВставки|EndInsert)\b', 'IgnoreCase')
    $reDelStart    = [regex]::new('^#\s*(?:Удаление|Delete)\b', 'IgnoreCase')
    $reDelEnd      = [regex]::new('^#\s*(?:КонецУдаления|EndDelete)\b', 'IgnoreCase')

    $soobschitCount = 0
    $bareTodoCount = 0

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        $lineNo = $i + 1
        $trim = $line.TrimStart()

        if ($reConflict.IsMatch($line)) {
            Add-Finding -Kind 'bsl-conflict-marker' -Severity 'error' -RelPath $rel -Message "Line ${lineNo}: unresolved Git merge conflict marker."
            continue
        }
        if ($reResyncConflict.IsMatch($line)) {
            Add-Finding -Kind 'bsl-resync-conflict' -Severity 'error' -RelPath $rel -Message "Line ${lineNo}: unresolved cfe-patch-method [РЕСИНК-КОНФЛИКТ] marker."
        }

        if ($inMultilineStr -and -not $trim.StartsWith('|')) { $inMultilineStr = $false }

        # Strip string literals & extract code vs comment
        $codeSb = New-Object System.Text.StringBuilder
        $commentPart = ''
        $k = 0
        while ($k -lt $line.Length) {
            $ch = $line[$k]
            if ($inMultilineStr) {
                if ($ch -eq '"') {
                    if ($k + 1 -lt $line.Length -and $line[$k + 1] -eq '"') { $k += 2; continue }
                    $inMultilineStr = $false
                }
                $k++; continue
            }
            if ($ch -eq '"') { $inMultilineStr = $true; $k++; continue }
            if ($ch -eq '/' -and $k + 1 -lt $line.Length -and $line[$k + 1] -eq '/') {
                $commentPart = $line.Substring($k)
                break
            }
            [void]$codeSb.Append($ch)
            $k++
        }

        $code = $codeSb.ToString()
        $codeTrim = $code.Trim()

        # Preprocessor balance (skip lines inside multiline strings)
        if ($codeTrim.StartsWith('#')) {
            if ($reRegionStart.IsMatch($codeTrim))   { $stack.Push(@{ Kind = 'Region'; Line = $lineNo }) }
            elseif ($reRegionEnd.IsMatch($codeTrim)) {
                if ($stack.Count -eq 0 -or $stack.Peek().Kind -ne 'Region') {
                    Add-Finding -Kind 'bsl-unbalanced-directive' -Severity 'error' -RelPath $rel -Message "Line ${lineNo}: unexpected #КонецОбласти / #EndRegion."
                } else { [void]$stack.Pop() }
            }
            elseif ($reIfStart.IsMatch($codeTrim))   { $stack.Push(@{ Kind = 'If'; Line = $lineNo }) }
            elseif ($reIfEnd.IsMatch($codeTrim)) {
                if ($stack.Count -eq 0 -or $stack.Peek().Kind -ne 'If') {
                    Add-Finding -Kind 'bsl-unbalanced-directive' -Severity 'error' -RelPath $rel -Message "Line ${lineNo}: unexpected #КонецЕсли / #EndIf."
                } else { [void]$stack.Pop() }
            }
            elseif ($reInsStart.IsMatch($codeTrim))  { $stack.Push(@{ Kind = 'Insert'; Line = $lineNo }) }
            elseif ($reInsEnd.IsMatch($codeTrim)) {
                if ($stack.Count -eq 0 -or $stack.Peek().Kind -ne 'Insert') {
                    Add-Finding -Kind 'bsl-unbalanced-directive' -Severity 'error' -RelPath $rel -Message "Line ${lineNo}: unexpected #КонецВставки / #EndInsert."
                } else { [void]$stack.Pop() }
            }
            elseif ($reDelStart.IsMatch($codeTrim))  { $stack.Push(@{ Kind = 'Delete'; Line = $lineNo }) }
            elseif ($reDelEnd.IsMatch($codeTrim)) {
                if ($stack.Count -eq 0 -or $stack.Peek().Kind -ne 'Delete') {
                    Add-Finding -Kind 'bsl-unbalanced-directive' -Severity 'error' -RelPath $rel -Message "Line ${lineNo}: unexpected #КонецУдаления / #EndDelete."
                } else { [void]$stack.Pop() }
            }
        }

        if ($soobschitCount -lt 3 -and $reSoobschit.IsMatch($code)) {
            $soobschitCount++
            Add-Finding -Kind 'bsl-soobschit' -Severity 'warning' -RelPath $rel -Message "Line ${lineNo}: direct Сообщить() / Message() call (use СообщениеПользователю or БСП wrapper)."
        }

        if ($bareTodoCount -lt 3 -and $commentPart) {
            $tm = $reBareTodo.Match($commentPart)
            if ($tm.Success -and -not $reTaskRef.IsMatch($tm.Groups[1].Value)) {
                $bareTodoCount++
                Add-Finding -Kind 'bsl-bare-todo' -Severity 'warning' -RelPath $rel -Message "Line ${lineNo}: TODO/FIXME without task reference (use TODO No.<task>)."
            }
        }
    }

    while ($stack.Count -gt 0) {
        $unclosed = $stack.Pop()
        Add-Finding -Kind 'bsl-unbalanced-directive' -Severity 'error' -RelPath $rel -Message "Line $($unclosed.Line): unclosed #$($unclosed.Kind) directive."
    }
}

function Test-ObjectNestedOrphans([string]$objXmlPath) {
    $script:FilesChecked++
    $objDir = [System.IO.Path]::Combine([System.IO.Path]::GetDirectoryName($objXmlPath), [System.IO.Path]::GetFileNameWithoutExtension($objXmlPath))
    if (-not (Test-Path -LiteralPath $objDir -PathType Container)) { return }

    $xmlDoc = New-Object System.Xml.XmlDocument
    try {
        $xmlDoc.Load($objXmlPath)
    } catch {
        Add-Finding -Kind 'xml-unreadable' -Severity 'error' -RelPath (Get-RelPath $objXmlPath) -Message "Cannot parse metadata XML: $($_.Exception.Message)"
        return
    }

    $nsMgr = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
    $nsMgr.AddNamespace('md', $MetadataNamespace)

    $rootChild = $null
    foreach ($n in $xmlDoc.DocumentElement.ChildNodes) {
        if ($n.NodeType -eq 'Element') { $rootChild = $n; break }
    }
    if (-not $rootChild) { return }

    $childObjs = $rootChild.SelectSingleNode('md:ChildObjects', $nsMgr)
    $regForms = @{}
    $regTemplates = @{}
    if ($childObjs) {
        foreach ($c in $childObjs.ChildNodes) {
            if ($c.NodeType -ne 'Element') { continue }
            $txt = $c.InnerText.Trim()
            if (-not $txt) { continue }
            if ($c.LocalName -eq 'Form') { $regForms[$txt] = $true }
            elseif ($c.LocalName -eq 'Template') { $regTemplates[$txt] = $true }
        }
    }

    foreach ($pair in @(@('Forms', $regForms, 'orphan-form', 'missing-form'), @('Templates', $regTemplates, 'orphan-template', 'missing-template'))) {
        $subName = $pair[0]; $regSet = $pair[1]; $orphanKind = $pair[2]; $missingKind = $pair[3]
        $subDir = Join-Path $objDir $subName

        if (Test-Path -LiteralPath $subDir -PathType Container) {
            $seenOnDisk = @{}
            foreach ($f in (Get-ChildItem -LiteralPath $subDir -File -Filter '*.xml' -ErrorAction SilentlyContinue)) {
                $stem = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
                $seenOnDisk[$stem] = $true
                if (-not $regSet.ContainsKey($stem)) {
                    Add-Finding -Kind $orphanKind -Severity 'error' -RelPath (Get-RelPath $f.FullName) -Message "Unregistered $subName descriptor '$stem' (not in parent ChildObjects)."
                }
            }
            foreach ($d in (Get-ChildItem -LiteralPath $subDir -Directory -ErrorAction SilentlyContinue)) {
                if (-not $regSet.ContainsKey($d.Name) -and -not $seenOnDisk.ContainsKey($d.Name)) {
                    Add-Finding -Kind $orphanKind -Severity 'error' -RelPath (Get-RelPath $d.FullName) -Message "Orphan $subName directory '$($d.Name)' (no descriptor and not in parent ChildObjects)."
                }
            }
        }

        foreach ($name in $regSet.Keys) {
            $desc = Join-Path $subDir "$name.xml"
            if (-not (Test-Path -LiteralPath $desc -PathType Leaf)) {
                Add-Finding -Kind $missingKind -Severity 'error' -RelPath (Get-RelPath $desc) -Message "Registered $subName entry '$name' has no descriptor file on disk."
            }
        }
    }
}

# --- Main ---

if ($ConfigPath) {
    $resolvedCfg = (Resolve-Path -LiteralPath $ConfigPath).ProviderPath
    if ((Test-Path -LiteralPath $resolvedCfg -PathType Leaf) -and ([System.IO.Path]::GetFileName($resolvedCfg) -ieq 'Configuration.xml')) {
        $resolvedCfg = [System.IO.Path]::GetDirectoryName($resolvedCfg)
    }
    if (-not (Test-Path -LiteralPath $resolvedCfg -PathType Container)) {
        Write-Error "Directory not found: $ConfigPath"
        exit 2
    }
    $script:RootPath = $resolvedCfg

    # 1. Stray backup / temp / quarantine artifacts inside the dump
    foreach ($pattern in $StrayPatterns) {
        foreach ($st in (Get-ChildItem -LiteralPath $resolvedCfg -Recurse -File -Filter $pattern -ErrorAction SilentlyContinue)) {
            Add-Finding -Kind 'stray-file' -Severity 'warning' -RelPath (Get-RelPath $st.FullName) -Message "Stray temporary/backup file inside configuration dump."
        }
    }
    foreach ($qd in (Get-ChildItem -LiteralPath $resolvedCfg -Recurse -Directory -Filter '.remove-form-quarantine*' -ErrorAction SilentlyContinue)) {
        Add-Finding -Kind 'stray-quarantine' -Severity 'error' -RelPath (Get-RelPath $qd.FullName) -Message 'Leftover remove-form quarantine directory inside dump.'
    }

    # 2. Orphan object directories (Catalogs/Foo/ without Catalogs/Foo.xml) and nested Forms/Templates orphans
    foreach ($folder in $ObjectFolders) {
        $kindDir = Join-Path $resolvedCfg $folder
        if (-not (Test-Path -LiteralPath $kindDir -PathType Container)) { continue }

        foreach ($xmlFile in (Get-ChildItem -LiteralPath $kindDir -File -Filter '*.xml' -ErrorAction SilentlyContinue)) {
            Test-ObjectNestedOrphans $xmlFile.FullName
        }

        foreach ($subDir in (Get-ChildItem -LiteralPath $kindDir -Directory -ErrorAction SilentlyContinue)) {
            $xmlSibling = "$($subDir.FullName).xml"
            if (-not (Test-Path -LiteralPath $xmlSibling -PathType Leaf)) {
                Add-Finding -Kind 'orphan-object-dir' -Severity 'error' -RelPath (Get-RelPath $subDir.FullName) -Message "Object directory without sibling descriptor '$($subDir.Name).xml'."
            }
        }
    }

    # 3. BSL files across the dump (unless -Paths explicitly narrows BSL scope)
    if (-not $Paths -or $Paths.Count -eq 0) {
        foreach ($bsl in (Get-ChildItem -LiteralPath $resolvedCfg -Recurse -File -Filter '*.bsl' -ErrorAction SilentlyContinue)) {
            Test-BslFile $bsl.FullName
        }
    }
}

if ($Paths -and $Paths.Count -gt 0) {
    foreach ($p in $Paths) {
        if (-not (Test-Path -LiteralPath $p)) {
            Add-Finding -Kind 'missing-path' -Severity 'error' -RelPath $p -Message 'Specified path does not exist.'
            continue
        }
        $rp = (Resolve-Path -LiteralPath $p).ProviderPath
        if (Test-Path -LiteralPath $rp -PathType Container) {
            foreach ($bsl in (Get-ChildItem -LiteralPath $rp -Recurse -File -Filter '*.bsl' -ErrorAction SilentlyContinue)) {
                Test-BslFile $bsl.FullName
            }
        } elseif ($rp.EndsWith('.bsl', [System.StringComparison]::OrdinalIgnoreCase)) {
            Test-BslFile $rp
        } elseif ($rp.EndsWith('.xml', [System.StringComparison]::OrdinalIgnoreCase)) {
            Test-ObjectNestedOrphans $rp
        }
    }
}

$errCount = @($script:Findings | Where-Object { $_.severity -eq 'error' }).Count
$warnCount = @($script:Findings | Where-Object { $_.severity -eq 'warning' }).Count
$failed = ($errCount -gt 0) -or ($FailOnWarn -and $warnCount -gt 0)
$status = if ($errCount -gt 0) { 'invalid' } elseif ($warnCount -gt 0) { 'warnings' } else { 'valid' }

if ($Format -eq 'Json') {
    $payload = [PSCustomObject]@{
        schema_version = 1
        status         = $status
        root           = $script:RootPath
        files_checked  = $script:FilesChecked
        errors         = $errCount
        warnings       = $warnCount
        findings       = @($script:Findings.ToArray())
    }
    $outText = $payload | ConvertTo-Json -Depth 6
} else {
    $linesOut = New-Object System.Collections.Generic.List[string]
    foreach ($f in $script:Findings) {
        $tag = if ($f.severity -eq 'error') { '[ERROR]' } else { '[WARN] ' }
        $linesOut.Add("$tag $($f.kind) $($f.path): $($f.message)")
    }
    if ($errCount -eq 0 -and $warnCount -eq 0) {
        $linesOut.Add("=== Hygiene OK ($($script:FilesChecked) files checked) ===")
    } else {
        $linesOut.Add("---")
        $linesOut.Add("Errors: $errCount, Warnings: $warnCount ($($script:FilesChecked) files checked)")
    }
    $outText = ($linesOut -join [Environment]::NewLine)
}

if ($OutFile) {
    $outFull = [System.IO.Path]::GetFullPath($OutFile)
    if ($script:RootPath) {
        $rNorm = $script:RootPath.TrimEnd('\','/') + [System.IO.Path]::DirectorySeparatorChar
        if ($outFull.StartsWith($rNorm, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Error 'OutFile must be outside the checked dump directory.'
            exit 2
        }
    }
    [System.IO.File]::WriteAllText($outFull, $outText, (New-Object System.Text.UTF8Encoding $true))
}

Write-Output $outText
if ($failed) { exit 1 } else { exit 0 }
