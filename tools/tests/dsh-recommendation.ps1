#Requires -Version 5.1
<# Targeted, offline tests of the installer's DSH recommendation after the first init. No installer run. #>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$installer = Join-Path $repoRoot 'install.ps1'
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($installer, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }

# Load only the pure helpers and the recommendation functions; never execute installer dispatch.
$names = @('Read-TextFile', 'Get-DshHomeCandidates', 'Test-DshSignal', 'Test-CabinetLoginStored', 'Write-DshRecommendation')
foreach ($name in $names) {
    $fn = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
    if (-not $fn) { throw "Missing function: $name" }
    . ([scriptblock]::Create($fn.Extent.Text))
}

# Init calls the recommendation only on a first install.
$init = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Invoke-Init' }, $true)
if (-not $init) { throw 'Missing function: Invoke-Init' }
if ($init.Extent.Text -notmatch 'if \(-not \$existing\) \{ Write-DshRecommendation -Root \$Root \}') {
    throw 'Invoke-Init does not limit the DSH recommendation to a first install'
}
$update = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Invoke-Update' }, $true)
if ($update -and $update.Extent.Text -match 'Write-DshRecommendation') { throw 'Update repeats the DSH recommendation' }

$script:Out = New-Object System.Collections.Generic.List[string]
function Write-Info { param([string]$Message) $script:Out.Add($Message) }
function Assert-True($Value, [string]$Message) { if (-not $Value) { throw $Message } }
function Invoke-Recommendation([string]$Root) {
    $script:Out.Clear()
    Write-DshRecommendation -Root $Root
    return ($script:Out -join "`n")
}

$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('dsh-recommendation-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null

try {
    $project = Join-Path $fixtureRoot 'project'
    New-Item -ItemType Directory -Path $project | Out-Null
    $script:Candidates = @()
    function Get-DshHomeCandidates { return @($script:Candidates) }

    # No DSH, no stored login: purchase page plus the command that downloads it.
    $text = Invoke-Recommendation $project
    Assert-True ($text -match 'https://vibecoding1c\.ru/harnesses') 'Purchase page missing'
    Assert-True ($text -match '/installdsh') '/installdsh missing'
    Assert-True ($text -match 'portable') 'Portable note missing without a stored login'
    Assert-True ($text -notmatch 'disk\.yandex|yadi\.sk|harnessaccess') 'A download address leaked into the text'
    $plain = $text

    # The memory.md login entry written by /installmcp switches to the "install now" line.
    Set-Content -LiteralPath (Join-Path $project 'memory.md') -Encoding UTF8 -Value @(
        '# Project memory', '',
        '## 2026-11-01 - MCP Distribution - vibecoding1c.ru credentials', '- **Rule:** tilda_login=<email>')
    Assert-True (Test-CabinetLoginStored -Root $project) 'Stored login not detected'
    $text = Invoke-Recommendation $project
    Assert-True ($text -match 'https://vibecoding1c\.ru/harnesses') 'Purchase page missing with a stored login'
    Assert-True ($text -match '/installdsh') '/installdsh missing with a stored login'
    Assert-True ($text -ne $plain) 'Stored login did not change the second line'

    # Mentioning the entry in prose is not a stored login.
    Set-Content -LiteralPath (Join-Path $project 'memory.md') -Encoding UTF8 -Value 'See MCP Distribution - vibecoding1c.ru credentials in another project.'
    Assert-True (-not (Test-CabinetLoginStored -Root $project)) 'Prose mention detected as a stored login'
    Remove-Item -LiteralPath (Join-Path $project 'memory.md')
    Assert-True (-not (Test-CabinetLoginStored -Root $project)) 'Missing memory.md detected as a stored login'

    # A recorded folder with a launcher silences the recommendation.
    $dsh = Join-Path $fixtureRoot 'DSH-Desktop-1C-0.1.0-win-x64'
    New-Item -ItemType Directory -Path $dsh | Out-Null
    Set-Content -LiteralPath (Join-Path $dsh 'DSH-Desktop-1C.exe') -Value 'stub'
    $script:Candidates = @($dsh)
    Assert-True (Test-DshSignal) 'Unpacked DSH not detected'
    Assert-True ((Invoke-Recommendation $project) -eq '') 'Recommendation shown although DSH is unpacked'

    # A stale variable (folder gone) or a folder without a launcher does not count.
    $script:Candidates = @((Join-Path $fixtureRoot 'missing'))
    Assert-True (-not (Test-DshSignal)) 'Missing folder detected as DSH'
    $empty = Join-Path $fixtureRoot 'empty'
    New-Item -ItemType Directory -Path $empty | Out-Null
    $script:Candidates = @($empty)
    Assert-True (-not (Test-DshSignal)) 'Folder without a launcher detected as DSH'
    Assert-True ((Invoke-Recommendation $project) -match '/installdsh') 'Recommendation missing for a stale DSH_1C_HOME'

    Write-Host 'OK: DSH recommendation'
}
finally {
    $resolved = [IO.Path]::GetFullPath($fixtureRoot)
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if ($resolved.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolved -Leaf) -match '^dsh-recommendation-tests-[a-f0-9]{32}$') {
        if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
    }
    else { throw "Unsafe fixture cleanup refused: $resolved" }
}
