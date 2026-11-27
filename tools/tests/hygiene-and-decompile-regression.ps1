#Requires -Version 5.1
<#
.SYNOPSIS
    Regression tests for hygiene-check.ps1, meta-decompile.ps1, and form-decompile.ps1.
#>
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).ProviderPath
$hygieneScript = Join-Path $repoRoot 'content\skills\1c-metadata-manage\tools\1c-cf-manage\scripts\hygiene-check.ps1'
$cfInit = Join-Path $repoRoot 'content\skills\1c-metadata-manage\tools\1c-cf-manage\scripts\cf-init.ps1'
$metaCompile = Join-Path $repoRoot 'content\skills\1c-metadata-manage\tools\1c-meta-compile\scripts\meta-compile.ps1'
$formAdd = Join-Path $repoRoot 'content\skills\1c-metadata-manage\tools\1c-form-scaffold\scripts\form-add.ps1'
$metaDecompile = Join-Path $repoRoot 'content\skills\1c-metadata-manage\tools\1c-meta-decompile\scripts\meta-decompile.ps1'
$formDecompile = Join-Path $repoRoot 'content\skills\1c-metadata-manage\tools\1c-form-decompile\scripts\form-decompile.ps1'

$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ("1c-rules-hyg-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Force $workDir | Out-Null

$passed = 0
$failed = 0
function Assert-Case([string]$name, [scriptblock]$body) {
    try {
        & $body
        Write-Host "[PASS] $name"
        $script:passed++
    } catch {
        Write-Host "[FAIL] $name : $($_.Exception.Message)" -ForegroundColor Red
        $script:failed++
    }
}

try {
    $dump = Join-Path $workDir 'cf'
    New-Item -ItemType Directory -Force $dump | Out-Null
    & powershell.exe -NoProfile -File $cfInit -Name TestHygiene -OutputDir $dump | Out-Null
    $catJson = Join-Path $workDir 'cat.json'
    '{"type":"Catalog","name":"Номенклатура","attributes":["Артикул: String(25)"]}' | Set-Content -Encoding UTF8 $catJson
    & powershell.exe -NoProfile -File $metaCompile -JsonPath $catJson -OutputDir $dump | Out-Null
    & powershell.exe -NoProfile -File $formAdd -ObjectPath "$dump\Catalogs\Номенклатура.xml" -FormName "ФормаЭлемента" | Out-Null

    Assert-Case 'hygiene-check: clean freshly scaffolded dump passes with exit 0' {
        $out = & powershell.exe -NoProfile -File $hygieneScript -ConfigPath $dump -Format Json
        if ($LASTEXITCODE -ne 0) { throw "Expected exit 0, got $LASTEXITCODE : $out" }
        $obj = $out | ConvertFrom-Json
        if ($obj.status -ne 'valid' -or $obj.errors -ne 0) { throw "Expected valid/0 errors, got $($obj.status)/$($obj.errors)" }
    }

    Assert-Case 'hygiene-check: detects unregistered orphan form, orphan object dir, stray .bak, bad BSL' {
        # 1. Orphan form XML
        New-Item -ItemType Directory -Force "$dump\Catalogs\Номенклатура\Forms" | Out-Null
        '<MetaDataObject/>' | Set-Content -Encoding UTF8 "$dump\Catalogs\Номенклатура\Forms\ПризрачнаяФорма.xml"
        # 2. Orphan object directory
        New-Item -ItemType Directory -Force "$dump\Catalogs\БезДескриптора" | Out-Null
        # 3. Stray .bak file
        'backup' | Set-Content -Encoding UTF8 "$dump\Catalogs\Номенклатура.xml.bak"
        # 4. BSL issues: no BOM + unbalanced #Область + Сообщить + bare TODO + conflict marker
        $bslPath = "$dump\Catalogs\Номенклатура\Forms\ФормаЭлемента\Ext\Form\Module.bsl"
        $badBsl = "#Область Тест`r`nПроцедура П()`r`n`tСообщить(""x"");`r`n`t// TODO починить`r`n<<<<<<< HEAD`r`nКонецПроцедуры`r`n"
        [System.IO.File]::WriteAllText($bslPath, $badBsl, (New-Object System.Text.UTF8Encoding $false))

        $out = & powershell.exe -NoProfile -File $hygieneScript -ConfigPath $dump -Format Json
        if ($LASTEXITCODE -ne 1) { throw "Expected exit 1, got $LASTEXITCODE" }
        $obj = $out | ConvertFrom-Json
        $kinds = @($obj.findings | ForEach-Object { $_.kind })
        foreach ($req in @('orphan-form','orphan-object-dir','stray-file','bsl-no-bom','bsl-unbalanced-directive','bsl-soobschit','bsl-bare-todo','bsl-conflict-marker')) {
            if ($kinds -notcontains $req) { throw "Missing expected finding kind '$req'. Got: $($kinds -join ', ')" }
        }
    }

    Assert-Case 'hygiene-check: -Paths targeted mode validates a single clean BSL file' {
        $goodBsl = Join-Path $workDir 'good.bsl'
        $txt = "#Область Служебные`r`n// TODO No.123 допустимо`r`nПроцедура А()`r`nКонецПроцедуры`r`n#КонецОбласти`r`n"
        [System.IO.File]::WriteAllText($goodBsl, $txt, (New-Object System.Text.UTF8Encoding $true))
        $out = & powershell.exe -NoProfile -File $hygieneScript -Paths $goodBsl -FailOnWarn
        if ($LASTEXITCODE -ne 0) { throw "Expected exit 0 on clean BSL, got $LASTEXITCODE : $out" }
    }

    Assert-Case 'meta-decompile: emits valid JSON draft for catalog XML' {
        $outJson = Join-Path $workDir 'decompiled_cat.json'
        & powershell.exe -NoProfile -File $metaDecompile -ObjectPath "$dump\Catalogs\Номенклатура.xml" -OutputPath $outJson | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "meta-decompile failed ($LASTEXITCODE)" }
        $parsed = Get-Content -Raw -Encoding UTF8 $outJson | ConvertFrom-Json
        if ($parsed.type -ne 'Catalog' -or $parsed.name -ne 'Номенклатура') { throw "Unexpected decompile output: $($parsed.type)/$($parsed.name)" }
    }

    Assert-Case 'form-decompile: emits valid JSON draft for managed Form.xml' {
        $outJson = Join-Path $workDir 'decompiled_form.json'
        & powershell.exe -NoProfile -File $formDecompile -FormPath "$dump\Catalogs\Номенклатура\Forms\ФормаЭлемента\Ext\Form.xml" -OutputPath $outJson | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "form-decompile failed ($LASTEXITCODE)" }
        $parsed = Get-Content -Raw -Encoding UTF8 $outJson | ConvertFrom-Json
        if (-not $parsed) { throw "form-decompile produced empty JSON" }
    }
} finally {
    Remove-Item -Recurse -Force $workDir -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Passed: $passed, Failed: $failed"
if ($failed -gt 0) { exit 1 }
exit 0
