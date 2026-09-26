#Requires -Version 5.1
<# Targeted, offline tests of the installer's TOOL_* migration. No installer run. #>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$installer = Join-Path $repoRoot 'install.ps1'
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($installer, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }

# Load only pure file helpers and the migration; never execute installer dispatch.
$names = @('Read-TextFile', 'Write-TextFile', 'Get-FileSha256', 'Read-DevEnvKeys', 'Ensure-ToolPolicySettings')
foreach ($name in $names) {
    $fn = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
    if (-not $fn) { throw "Missing function: $name" }
    . ([scriptblock]::Create($fn.Extent.Text))
}
function Write-Info { param([string]$Message) }
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:DevEnvFileName = '.dev.env'
$script:DevEnvExampleName = '.dev.env.example'
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('tool-policy-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null

function Assert-True($Value, [string]$Message) { if (-not $Value) { throw $Message } }

try {
    $template = Read-DevEnvKeys (Join-Path $repoRoot '.dev.env.example')
    $policyKeys = @($template.Keys | Where-Object { $_ -match '^TOOL_[A-Z_]+$' })
    Assert-True ($policyKeys.Count -gt 0) 'Template has no policy keys'
    foreach ($key in $policyKeys) { Assert-True ($template[$key] -eq 'auto') "Unexpected template default: $key" }

    foreach ($newline in @("`n", "`r`n")) {
        $target = Join-Path $fixtureRoot '.dev.env'
        # Include whitespace, empty/invalid choices, comments, Unicode, no trailing newline.
        $original = '# keep ' + [char]0x0410 + $newline +
            'TOOL_COGNEE = off' + $newline + 'TOOL_SYNTAX=required' + $newline +
            'TOOL_OPENVIKING=' + $newline + 'TOOL_DATA=typo' + $newline +
            'TOOL_CUSTOM=off' + $newline + 'PREFIX=unchanged'
        Write-TextFile -Path $target -Content $original
        $manifest = [ordered]@{ files = [ordered]@{ '.dev.env' = [ordered]@{ installedHash = 'old' } } }
        Ensure-ToolPolicySettings -Root $fixtureRoot -SourceRoot $repoRoot -Manifest $manifest
        $result = Read-TextFile $target
        Assert-True ($result.StartsWith($original + $newline)) 'Existing content was changed'
        $values = Read-DevEnvKeys $target
        foreach ($key in $policyKeys) {
            Assert-True ($values.Contains($key)) "Missing key: $key"
            Assert-True (([regex]::Matches($result, ('(?m)^' + $key + '\s*='))).Count -eq 1) "Duplicate key: $key"
        }
        Assert-True ($values['TOOL_COGNEE'] -eq 'off') 'off was overwritten'
        Assert-True ($values['TOOL_SYNTAX'] -eq 'required') 'required was overwritten'
        Assert-True ($values['TOOL_OPENVIKING'] -eq '') 'Empty value was overwritten'
        Assert-True ($values['TOOL_DATA'] -eq 'typo') 'Invalid value was silently repaired'
        Assert-True ($manifest.files['.dev.env'].installedHash -eq (Get-FileSha256 $target)) 'Manifest hash stale'
        if ($newline -eq "`r`n") { Assert-True ($result -notmatch '(?<!\r)\n') 'Mixed line endings' }
        $hash = Get-FileSha256 $target
        Ensure-ToolPolicySettings -Root $fixtureRoot -SourceRoot $repoRoot -Manifest $manifest
        Assert-True ($hash -eq (Get-FileSha256 $target)) 'Migration is not idempotent'
    }

    $emptyRoot = Join-Path $fixtureRoot 'empty'
    New-Item -ItemType Directory -Path $emptyRoot | Out-Null
    Ensure-ToolPolicySettings -Root $emptyRoot -SourceRoot $repoRoot -Manifest ([ordered]@{ files = [ordered]@{} })
    Assert-True (-not (Test-Path (Join-Path $emptyRoot '.dev.env'))) 'Migration created a missing user file'
    $target = Join-Path $fixtureRoot '.dev.env'
    Write-TextFile -Path $target -Content ''
    Ensure-ToolPolicySettings -Root $fixtureRoot -SourceRoot $repoRoot -Manifest ([ordered]@{ files = [ordered]@{} })
    Assert-True ((Read-DevEnvKeys $target).Count -eq $policyKeys.Count) 'Empty file migration failed'
    Write-Host "OK: $($policyKeys.Count) policies; preservation, LF/CRLF, idempotency, manifest, missing/empty file."
}
finally {
    $resolved = [IO.Path]::GetFullPath($fixtureRoot)
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if ($resolved.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolved -Leaf) -match '^tool-policy-tests-[a-f0-9]{32}$') {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    else { throw "Unsafe fixture cleanup refused: $resolved" }
}
