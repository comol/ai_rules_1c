#Requires -Version 5.1
<# Offline first-install export tests. The platform wrapper is replaced by a stub. #>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $repoRoot 'install.ps1'), [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
foreach ($name in @('Read-TextFile', 'Write-TextFile', 'Get-FileSha256', 'Read-DevEnvKeys',
    'Set-DevEnvValue', 'Test-InitialDumpSources', 'Invoke-InitialSourceDump')) {
    $fn = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
    if (-not $fn) { throw "Missing function: $name" }
    . ([scriptblock]::Create($fn.Extent.Text))
}
$script:Utf8NoBom = New-Object Text.UTF8Encoding($false)
$script:DevEnvFileName = '.dev.env'
$work = Join-Path ([IO.Path]::GetTempPath()) ('initial-dump-tests-' + [guid]::NewGuid().ToString('N'))
$source = Join-Path $work 'source'
$scriptPath = Join-Path $source 'content/skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-dump-xml.ps1'
$script:cases = 0

function Assert-True($Value, [string]$Message) { if (-not $Value) { throw $Message } }
function Write-Fixture([string]$Path, [string]$Text) {
    [void][IO.Directory]::CreateDirectory((Split-Path $Path -Parent))
    [IO.File]::WriteAllText($Path, $Text, $script:Utf8NoBom)
}
function Write-Info { param([string]$Message) $script:messages += $Message }
function Write-Warn { param([string]$Message) $script:warnings += $Message }
function Write-Manifest { param($Root, $Manifest) $script:manifestWrites++ }
function Read-YesNo {
    param([string]$Prompt, [bool]$Default)
    $script:prompts++
    Assert-True (-not $Default) 'Export must default to skip'
    return $script:accept
}
function New-Case([string]$Settings = "INFOBASE_PATH=bases/dev`nEXPORT_PATH=`n") {
    $script:cases++
    $script:project = Join-Path $work "project-$script:cases"
    Write-Fixture (Join-Path $script:project '.dev.env') $Settings
    $script:prompts = 0
    $script:manifestWrites = 0
    $script:accept = $false
    $script:NonInteractive = $false
    $script:AssumeYes = $false
    $script:messages = @()
    $script:warnings = @()
    $global:LASTEXITCODE = 0
    $script:manifest = [ordered]@{ files = [ordered]@{ '.dev.env' = [ordered]@{ installedHash = 'before' } } }
}
function Invoke-Case {
    $beforeLocation = (Get-Location).Path
    Invoke-InitialSourceDump -Root $script:project -SourceRoot $source -Manifest $script:manifest
    Assert-True ((Get-Location).Path -eq $beforeLocation) 'Working directory was not restored'
    Assert-True ($global:LASTEXITCODE -eq 0) 'Optional export failed the installer'
}

try {
    Write-Fixture $scriptPath @'
param($ConfigDir, $Mode, $InfoBasePath, $InfoBaseServer, $InfoBaseRef, $V8Path, $UserName, $Password, $Extension)
$PSBoundParameters | Export-Clixml -LiteralPath (Join-Path (Get-Location).Path 'invocation.xml')
if (Test-Path -LiteralPath 'fail-export') { exit 7 }
if (Test-Path -LiteralPath 'empty-export') { exit 0 }
[void][IO.Directory]::CreateDirectory($ConfigDir)
[IO.File]::WriteAllText((Join-Path $ConfigDir 'Configuration.xml'), '<MetaDataObject/>')
exit 0
'@

    New-Case 'INFOBASE_PATH='
    Invoke-Case
    Assert-True ($script:prompts -eq 0) 'Missing connection prompted'

    New-Case
    $before = Get-FileSha256 (Join-Path $project '.dev.env')
    Invoke-Case
    Assert-True ($script:prompts -eq 1) 'Empty configured project did not offer export'
    Assert-True ($before -eq (Get-FileSha256 (Join-Path $project '.dev.env'))) 'Decline changed settings'
    Assert-True (-not (Test-Path (Join-Path $project 'invocation.xml'))) 'Decline launched export'

    foreach ($flag in @('NonInteractive', 'AssumeYes')) {
        New-Case
        Set-Variable -Name $flag -Value $true -Scope Script
        Invoke-Case
        Assert-True ($script:prompts -eq 0) "$flag prompted"
        Assert-True (-not (Test-Path (Join-Path $project 'invocation.xml'))) "$flag connected to the infobase"
        Assert-True (($script:messages -join ' ') -match '/loadfrom1cbase full') 'Missing later entry point'
    }

    foreach ($sourceFile in @('Configuration.xml', 'custom/ConfigurationExtension.xml', 'src/cf/ConfigDumpInfo.xml',
        'partial/Catalogs/Item/Ext/Module.bsl', 'edt/src/Configuration/Configuration.mdo')) {
        New-Case
        Write-Fixture (Join-Path $project $sourceFile) 'existing source'
        Invoke-Case
        Assert-True ($script:prompts -eq 0) "Existing source prompted: $sourceFile"
    }

    New-Case
    foreach ($file in @('.git/config', 'README.md', 'openspec/specs/README.md', '.cursor/skills/example/template.bsl',
        '.agents/skills/example/Configuration.xml', 'node_modules/example/Module.bsl')) {
        Write-Fixture (Join-Path $project $file) 'scaffold'
    }
    $script:accept = $true
    Invoke-Case
    $call = Import-Clixml (Join-Path $project 'invocation.xml')
    Assert-True ($script:prompts -eq 1 -and $call.Mode -eq 'Full') 'Scaffold suppressed the offer or wrong mode'
    Assert-True ($call.ConfigDir -eq (Join-Path $project 'src/cf')) 'Wrong new main root'
    Assert-True (-not $call.ContainsKey('Extension')) 'Main export selected an extension'
    Assert-True ((Read-DevEnvKeys (Join-Path $project '.dev.env'))['EXPORT_PATH'] -eq 'src/cf') 'New source root not persisted'
    Assert-True ($manifest.files['.dev.env'].installedHash -eq (Get-FileSha256 (Join-Path $project '.dev.env'))) 'Manifest hash stale'
    Assert-True ($script:manifestWrites -eq 1 -and $manifest.files.Count -eq 1) 'Sources became installer-owned'

    New-Case "INFOBASE_PATH=`"server/base`"`nINFOBASE_KIND=server`nEXPORT_PATH=custom dump`nIB_USER=User`nIB_PASSWORD='test secret'`n"
    $script:accept = $true
    Invoke-Case
    $call = Import-Clixml (Join-Path $project 'invocation.xml')
    Assert-True ($call.InfoBaseServer -eq 'server' -and $call.InfoBaseRef -eq 'base') 'Server mapping failed'
    Assert-True ($call.ConfigDir -eq (Join-Path $project 'custom dump')) 'Configured path ignored'
    Assert-True ($call.Password -eq 'test secret') 'Quoted credential parsing failed'
    Assert-True (($script:messages -join ' ') -notmatch 'test secret') 'Secret printed'

    New-Case "INFOBASE_PATH=bases/dev`nEXTENSION_NAME=Custom`nEXPORT_PATH=src/cf`nEXTENSIONS_PATH=src/extensions`n"
    $script:accept = $true
    Invoke-Case
    $call = Import-Clixml (Join-Path $project 'invocation.xml')
    Assert-True ($call.Extension -eq 'Custom' -and $call.ConfigDir -eq (Join-Path $project 'src/extensions/Custom')) 'Extension wrote to main root'

    foreach ($extra in @('', "EXPORT_PATH = `r`n", "EXTENSION_NAME=Custom`r`n")) {
        New-Case ("INFOBASE_PATH=bases/dev`r`n# keep this`r`n" + $extra)
        $script:accept = $true
        Invoke-Case
        $values = Read-DevEnvKeys (Join-Path $project '.dev.env')
        $key = if ($extra -match 'EXTENSION_NAME') { 'EXTENSIONS_PATH' } else { 'EXPORT_PATH' }
        Assert-True (-not [string]::IsNullOrWhiteSpace($values[$key])) "Missing/space-padded $key was not saved"
        $envText = Read-TextFile (Join-Path $project '.dev.env')
        Assert-True ($envText -notmatch '(?<!\r)\n') 'Setting write mixed line endings'
        Assert-True ($envText.Contains('# keep this')) 'Setting write removed user comment'
    }

    New-Case "INFOBASE_PATH=bases/dev`nEXPORT_PATH=../existing dump`n"
    Write-Fixture (Join-Path $work 'existing dump/Configuration.xml') 'existing'
    Invoke-Case
    Assert-True ($script:prompts -eq 0) 'Configured external sources ignored'

    foreach ($setting in @('USE_EDT=true', 'INFOBASE_KIND=invalid', 'INFOBASE_KIND=server', 'EXPORT_PATH=occupied')) {
        New-Case ("INFOBASE_PATH=bases`n" + $setting)
        Write-Fixture (Join-Path $project 'occupied/keep.txt') 'keep'
        $script:accept = $true
        Invoke-Case
        Assert-True (-not (Test-Path (Join-Path $project 'invocation.xml'))) "Unsafe export launched: $setting"
        Assert-True ((Get-Content (Join-Path $project 'occupied/keep.txt') -Raw) -eq 'keep') 'Existing file changed'
    }

    foreach ($marker in @('fail-export', 'empty-export')) {
        New-Case
        Write-Fixture (Join-Path $project $marker) ''
        $script:accept = $true
        Invoke-Case
        Assert-True ($script:warnings.Count -gt 0) "False success: $marker"
    }

    # Exercise real dispatch too: offer after init, never after re-init/update/add.
    Copy-Item -LiteralPath (Join-Path $repoRoot 'adapters') -Destination $source -Recurse
    foreach ($file in @('AGENTS.md', 'USER-RULES.md', 'memory.md', 'LLM-RULES.md')) {
        Write-Fixture (Join-Path $source $file) "# $file"
    }
    Write-Fixture (Join-Path $source '.dev.env.example') "INFOBASE_PATH=`nEXPORT_PATH=`n"
    Write-Fixture (Join-Path $source 'content/rules/probe.md') "---`ndescription: Test`nalwaysApply: false`ncategory: workflow`n---`n# Test"
    foreach ($directory in @('content/agents', 'content/commands')) { [void][IO.Directory]::CreateDirectory((Join-Path $source $directory)) }
    Write-Fixture (Join-Path $source 'content/mcp-servers.json') '{"servers":[]}'
    New-Case
    $installer = Join-Path $repoRoot 'install.ps1'
    foreach ($operation in @('first-init', 're-init', 'update', 'add')) {
        [string[]]$arguments = switch ($operation) {
            'first-init' { @('init', '-Tools', 'other') }
            're-init' { @('init', '-Tools', 'other') }
            'update' { @('update') }
            'add' { @('add', '-Tool', 'cursor') }
        }
        $log = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer @arguments `
            -ProjectRoot $project -Source $source -NonInteractive -McpMode managed 2>&1 | Out-String
        Assert-True ($LASTEXITCODE -eq 0) "Installer $operation failed: $log"
        $offered = $log -match '/loadfrom1cbase full'
        Assert-True ($offered -eq ($operation -eq 'first-init')) "Wrong offer lifecycle for $operation"
        Assert-True (-not (Test-Path (Join-Path $project 'invocation.xml'))) 'Unattended lifecycle launched export'
    }
    Write-Host "OK: $script:cases initial-export cases plus init/re-init/update/add; no real infobase accessed."
}
finally {
    $resolved = [IO.Path]::GetFullPath($work)
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if ($resolved.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolved -Leaf) -match '^initial-dump-tests-[a-f0-9]{32}$') {
        if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
    }
    else { throw "Unsafe fixture cleanup refused: $resolved" }
}
