#Requires -Version 5.1
<# Targeted, offline tests of the installer's CODE_OWNER question and migration. No installer run. #>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$installer = Join-Path $repoRoot 'install.ps1'
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($installer, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }

# Load only pure file helpers and the code-owner functions; never execute installer dispatch.
$names = @('Read-TextFile', 'Write-TextFile', 'Get-FileSha256', 'Read-DevEnvKeys',
    'Test-CodeOwnerPromptAllowed', 'Read-CodeOwnerChoice', 'Resolve-CodeOwnerAnswer', 'Ensure-CodeOwnerSetting')
foreach ($name in $names) {
    $fn = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
    if (-not $fn) { throw "Missing function: $name" }
    . ([scriptblock]::Create($fn.Extent.Text))
}
function Write-Info { param([string]$Message) }
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:DevEnvFileName = '.dev.env'
$script:CodeOwnerKey = 'CODE_OWNER'
$script:NonInteractive = $true
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('code-owner-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null

function Assert-True($Value, [string]$Message) { if (-not $Value) { throw $Message } }
function Reset-CodeOwnerAnswer { $script:CodeOwnerAnswer = $null; $script:CodeOwnerAsked = $false }
function New-Manifest { return [ordered]@{ files = [ordered]@{ '.dev.env' = [ordered]@{ installedHash = 'old' } } } }

try {
    # The shipped template carries the default explicitly.
    $template = Read-DevEnvKeys (Join-Path $repoRoot '.dev.env.example')
    Assert-True ($template['CODE_OWNER'] -eq 'user') 'Template default is not CODE_OWNER=user'

    # Unattended run: no prompt, 'user' appended, existing content and line endings kept.
    Assert-True (-not (Test-CodeOwnerPromptAllowed)) 'Prompt allowed under -NonInteractive'
    foreach ($newline in @("`n", "`r`n")) {
        Reset-CodeOwnerAnswer
        $target = Join-Path $fixtureRoot '.dev.env'
        $original = '# keep ' + [char]0x0410 + $newline + 'USE_EDT=false' + $newline + 'PREFIX=unchanged'
        Write-TextFile -Path $target -Content $original
        $manifest = New-Manifest
        Ensure-CodeOwnerSetting -Root $fixtureRoot -Manifest $manifest
        $result = Read-TextFile $target
        Assert-True ($result.StartsWith($original + $newline)) 'Existing content was changed'
        Assert-True ((Read-DevEnvKeys $target)['CODE_OWNER'] -eq 'user') 'Unattended default is not user'
        Assert-True (([regex]::Matches($result, '(?m)^CODE_OWNER\s*=')).Count -eq 1) 'CODE_OWNER written more than once'
        Assert-True (-not $script:CodeOwnerAsked) 'Unattended run reported a question'
        Assert-True ($manifest.files['.dev.env'].installedHash -eq (Get-FileSha256 $target)) 'Manifest hash stale'
        if ($newline -eq "`r`n") { Assert-True ($result -notmatch '(?<!\r)\n') 'Mixed line endings' }

        # A second pass is a no-op.
        $hash = Get-FileSha256 $target
        Ensure-CodeOwnerSetting -Root $fixtureRoot -Manifest $manifest
        Assert-True ($hash -eq (Get-FileSha256 $target)) 'Second pass changed the file'
    }

    # A present key is the user's: any value, empty or invalid included, stays untouched.
    foreach ($value in @('agent', 'user', '', 'typo')) {
        Reset-CodeOwnerAnswer
        $target = Join-Path $fixtureRoot '.dev.env'
        Write-TextFile -Path $target -Content ("PREFIX=x`nCODE_OWNER=$value`n")
        $hash = Get-FileSha256 $target
        $manifest = New-Manifest
        Ensure-CodeOwnerSetting -Root $fixtureRoot -Manifest $manifest
        Assert-True ($hash -eq (Get-FileSha256 $target)) "Present value '$value' was rewritten"
        Assert-True ($manifest.files['.dev.env'].installedHash -eq 'old') "Manifest touched for present value '$value'"
        Assert-True ($null -eq $script:CodeOwnerAnswer) "Question resolved for present value '$value'"
    }

    # No .dev.env: nothing is created.
    $empty = Join-Path $fixtureRoot 'no-env'
    New-Item -ItemType Directory -Path $empty | Out-Null
    Ensure-CodeOwnerSetting -Root $empty -Manifest (New-Manifest)
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $empty '.dev.env'))) '.dev.env created where none existed'

    # Answer mapping: 2 / agent pick the model; Enter, other text or a failing prompt keep the user.
    $script:NonInteractive = $false
    # Pairs, not a hashtable: hashtable keys ignore case, and 'agent' / 'AGENT' are both cases.
    $cases = @(@('1', 'user'), @('2', 'agent'), @('agent', 'agent'), @('AGENT', 'agent'), @(' 2 ', 'agent'), @('yes', 'user'))
    foreach ($case in $cases) {
        $script:StubAnswer = $case[0]
        function Read-Required { param($Prompt, $DefaultValue) return $script:StubAnswer }
        Assert-True ((Read-CodeOwnerChoice) -eq $case[1]) "Answer '$($case[0])' did not map to $($case[1])"
    }
    function Read-Required { param($Prompt, $DefaultValue) throw 'console unavailable' }
    Assert-True ((Read-CodeOwnerChoice) -eq 'user') 'A failing prompt did not fall back to user'

    # Interactive run: asked once per run, the answer reused for every project.
    function Test-CodeOwnerPromptAllowed { return $true }
    $script:PromptCount = 0
    function Read-Required { param($Prompt, $DefaultValue) $script:PromptCount++; return '2' }
    Reset-CodeOwnerAnswer
    foreach ($project in @('first', 'second')) {
        $root = Join-Path $fixtureRoot $project
        New-Item -ItemType Directory -Path $root | Out-Null
        Write-TextFile -Path (Join-Path $root '.dev.env') -Content "PREFIX=x`n"
        Ensure-CodeOwnerSetting -Root $root -Manifest (New-Manifest)
        Assert-True ((Read-DevEnvKeys (Join-Path $root '.dev.env'))['CODE_OWNER'] -eq 'agent') "Interactive answer not persisted in $project"
    }
    Assert-True ($script:PromptCount -eq 1) "Question asked $script:PromptCount times in one run"
    Assert-True ($script:CodeOwnerAsked) 'Interactive run not reported as asked'

    Write-Host 'OK: CODE_OWNER question and migration'
}
finally {
    $resolved = [IO.Path]::GetFullPath($fixtureRoot)
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if ($resolved.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolved -Leaf) -match '^code-owner-tests-[a-f0-9]{32}$') {
        if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
    }
    else { throw "Unsafe fixture cleanup refused: $resolved" }
}
