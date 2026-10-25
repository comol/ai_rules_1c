#Requires -Version 5.1
<# Offline installer regressions for source paths, EXPORT_PATH and installed links. #>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Installer = Join-Path $RepoRoot 'install.ps1'
$Work = Join-Path ([IO.Path]::GetTempPath()) ('installer-paths-' + [guid]::NewGuid().ToString('N'))
$SourceRoot = Join-Path $Work 'source repository with long name'
$Utf8 = New-Object Text.UTF8Encoding $false
$script:Passed = 0
$script:ShortPathChecked = $false

function Write-Fixture([string]$Path, [string]$Text) {
    [void][IO.Directory]::CreateDirectory((Split-Path $Path -Parent))
    [IO.File]::WriteAllText($Path, $Text, $Utf8)
}
function Assert-True($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Read-Json([string]$Path) { Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }
function Pass([string]$Name) { $script:Passed++; Write-Host "OK  $Name" }
function Invoke-Installer([string]$Project, [string[]]$Arguments, [string]$SourcePath = $SourceRoot) {
    $log = Join-Path $Work ('run-' + [guid]::NewGuid().ToString('N') + '.log')
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Installer @Arguments `
        -ProjectRoot $Project -Source $SourcePath -NonInteractive -McpMode managed *> $log
    Assert-True ($LASTEXITCODE -eq 0) "Installer failed: $(Get-Content -LiteralPath $log -Raw)"
    return (Get-Content -LiteralPath $log -Raw)
}
function Assert-Links([string]$Path, [string]$RulesDir, [string]$RulesExt, [string]$AgentsDir,
    [string]$CommandsDir, [string]$SkillsDir, [string]$AgentExt = 'md') {
    $text = [IO.File]::ReadAllText($Path)
    foreach ($expected in @("$RulesDir/probe.$RulesExt", "$AgentsDir/probe.$AgentExt",
        "$CommandsDir/probe.md", "$SkillsDir/probe/docs/detail.md")) {
        Assert-True ($text.Contains($expected)) "Missing installed reference $expected in $Path"
    }
    Assert-True (-not ($text -match 'content/(rules|agents|commands|skills)/')) "Source reference leaked into $Path"
}
function Assert-RelativeLinks([string]$Project, [string]$Tool) {
    $checked = 0; $placeholders = @(); $notInstalled = @(); $broken = @()
    $adapter = Get-AdapterForTool -Root $SourceRoot -Tool $Tool
    $manifest = Read-Json (Join-Path $Project '.ai-rules.json')
    $contentPrefix = [IO.Path]::GetFullPath((Join-Path $SourceRoot 'content')).TrimEnd('/', '\') + [IO.Path]::DirectorySeparatorChar
    $comparison = if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    foreach ($file in Get-ChildItem -LiteralPath $Project -Force -Recurse -File | Where-Object { $_.Extension -in @('.md', '.mdc', '.toml') }) {
        $rel = Get-InstallerRelativePath -BasePath $Project -ChildPath $file.FullName
        $entryProperty = $manifest.files.PSObject.Properties[$rel]
        $sourceFile = $null
        if ($entryProperty -and $entryProperty.Value.source) {
            $sourceFile = Join-Path $SourceRoot $entryProperty.Value.source
            if (Test-Path -LiteralPath $sourceFile -PathType Container) {
                $marker = '/' + (Split-Path $sourceFile -Leaf) + '/'
                $offset = ('/' + $rel).IndexOf($marker, [StringComparison]::Ordinal)
                if ($offset -ge 0) { $sourceFile = Join-Path $sourceFile ('/' + $rel).Substring($offset + $marker.Length) }
                else { $sourceFile = $null }
            }
        }
        $text = [IO.File]::ReadAllText($file.FullName)
        foreach ($match in [regex]::Matches($text, '(?m)(?:!?\[[^\]\r\n]*\]\([ \t]*|^[ \t]{0,3}\[[^\]\r\n]+\]:[ \t]*)(?<dest><[^>\r\n]+>|[^\s)\r\n]+)')) {
            $dest = $match.Groups['dest'].Value.Trim('<', '>')
            $detail = "$rel -> $dest"
            if ($dest -match '^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|[/\\#?])') { continue }
            if ($dest -match 'YYYY-MM') { $placeholders += $detail; continue }
            $path = [Uri]::UnescapeDataString(($dest -split '[#?]', 2)[0])
            $section = $null
            if ($sourceFile -and (Test-Path -LiteralPath $sourceFile -PathType Leaf)) {
                $sourceTarget = [IO.Path]::GetFullPath((Join-Path (Split-Path $sourceFile -Parent) $path))
                if ($sourceTarget.StartsWith($contentPrefix, $comparison)) {
                    $section = ($sourceTarget.Substring($contentPrefix.Length).Replace('\', '/') -split '/', 2)[0]
                }
            }
            if ($section -in @('rules', 'agents', 'commands', 'skills', 'docs') -and
                (-not $adapter.Contains($section) -or -not $adapter[$section].copyTo)) {
                $notInstalled += "$detail (section=$section)"
            }
            elseif (-not (Test-Path -LiteralPath (Join-Path $file.DirectoryName $path))) { $broken += $detail }
            $checked++
        }
    }
    Assert-True ($checked -gt 0) 'No relative links were checked'
    Assert-True ($broken.Count -eq 0) "Relative links: checked=$checked; broken=$($broken.Count); not-installed-section=$($notInstalled.Count); placeholders=$($placeholders.Count); $($broken -join '; ')"
    return @{ Checked = $checked; Resolved = $checked - $notInstalled.Count; Broken = $broken.Count; NotInstalled = $notInstalled; Placeholders = $placeholders }
}
function Assert-AdapterLinkTargets([string]$Project, [string]$DocumentRel, [string]$Tool) {
    # Independent check of declared copyTo targets, not just file existence.
    $adapter = Get-AdapterForTool -Root $SourceRoot -Tool $Tool
    $file = Join-Path $Project $DocumentRel
    $labels = @{ rule = 'rules'; agent = 'agents'; command = 'commands'; skill = 'skills' }
    $checked = 0
    foreach ($link in [regex]::Matches([IO.File]::ReadAllText($file), '\[(?<label>rule|agent|command|skill)\]\((?<dest>[^)]+)\)')) {
        $section = $labels[$link.Groups['label'].Value]
        if (-not $adapter.Contains($section) -or -not $adapter[$section].copyTo) { continue }
        $expected = ([string]$adapter[$section].copyTo).Replace('{name}', 'probe').TrimEnd('/', '\')
        if ($section -eq 'skills') { $expected += '/docs/detail.md' }
        $expectedFull = [IO.Path]::GetFullPath((Join-Path $Project $expected))
        $dest = [Uri]::UnescapeDataString(($link.Groups['dest'].Value -split '[#?]', 2)[0])
        $actualFull = [IO.Path]::GetFullPath((Join-Path (Split-Path $file -Parent) $dest))
        Assert-True ([string]::Equals($actualFull, $expectedFull, [StringComparison]::OrdinalIgnoreCase)) "Foreign adapter target: $DocumentRel -> $dest; expected $expected for $Tool"
        Assert-True (Test-Path -LiteralPath $actualFull) "Missing adapter target: $DocumentRel -> $dest"
        $checked++
    }
    Assert-True ($checked -gt 0) "No adapter-owned targets checked in $DocumentRel"
    return $checked
}
function Assert-ManifestHashes([string]$Project) {
    $manifest = Read-Json (Join-Path $Project '.ai-rules.json')
    foreach ($property in $manifest.files.PSObject.Properties) {
        if ($property.Value.userModified) { continue }
        $path = Join-Path $Project $property.Name
        Assert-True (Test-Path -LiteralPath $path) "Manifest path missing: $($property.Name)"
        $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        Assert-True ($actual -eq $property.Value.installedHash) "Manifest hash mismatch: $($property.Name)"
    }
}

try {
    [void][IO.Directory]::CreateDirectory($SourceRoot)
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'adapters') -Destination $SourceRoot -Recurse
    $refs = 'See content/rules/probe.md, content/agents/probe.md, content/commands/probe.md and content/skills/probe/docs/detail.md.'
    Write-Fixture (Join-Path $SourceRoot 'AGENTS.md') "# Rules`n$refs"
    foreach ($file in @('USER-RULES.md', 'memory.md', 'LLM-RULES.md')) { Write-Fixture (Join-Path $SourceRoot $file) "# $file" }
    Write-Fixture (Join-Path $SourceRoot '.dev.env.example') "EXPORT_PATH=`nINFOBASE_PATH=`nUSE_EDT=false`nPLATFORM_VERSION=`nPREFIX=`n"
    Write-Fixture (Join-Path $SourceRoot 'content/mcp-servers.json') '{"servers":[]}'
    Write-Fixture (Join-Path $SourceRoot 'content/rules/probe.md') "---`ndescription: Fixture`nalwaysApply: false`ncategory: workflow`n---`n# Rule`n$refs"
    Write-Fixture (Join-Path $SourceRoot 'content/agents/probe.md') "---`nname: probe`ndescription: Fixture`ntools: [Read, Grep, Glob, MCP]`nisSubagent: true`n---`n# Agent`n$refs"
    Write-Fixture (Join-Path $SourceRoot 'content/commands/probe.md') "---`ndescription: Fixture`n---`n# Command`n$refs"
    Write-Fixture (Join-Path $SourceRoot 'content/skills/probe/SKILL.md') "---`nname: probe`ndescription: Fixture`n---`n# Skill`n$refs"
    $relativeRefs = '[rule](../../../rules/probe.md#gate) [agent](../../../agents/probe.md) [command](../../../commands/probe.md) [sibling](local.md) [external](https://example.invalid/rules/probe.md) [placeholder](../../../docs/archive/enhancements/YYYY-MM/feature-name.md)'
    Write-Fixture (Join-Path $SourceRoot 'content/skills/probe/docs/detail.md') "# Detail`n$refs`n$relativeRefs`n[rule-ref]: ../../../rules/probe.md#gate"
    Write-Fixture (Join-Path $SourceRoot 'content/skills/probe/docs/local.md') '# Local sibling'
    Add-Content -LiteralPath (Join-Path $SourceRoot 'content/agents/probe.md') -Value '`n[rule](../rules/probe.md) [command](../commands/probe.md)' -Encoding UTF8
    Add-Content -LiteralPath (Join-Path $SourceRoot 'content/commands/probe.md') -Value '`n[rule](../rules/probe.md) [agent](../agents/probe.md) [skill](../skills/probe/docs/detail.md)' -Encoding UTF8
    Write-Fixture (Join-Path $SourceRoot 'content/skills/probe/scripts/probe.ps1') "# $refs`nWrite-Output 'verbatim'"
    Write-Fixture (Join-Path $SourceRoot 'content/skills/probe/stale.txt') 'prune this managed file'
    [IO.File]::WriteAllBytes((Join-Path $SourceRoot 'content/skills/probe/payload.bin'), [byte[]](0..255))
    Write-Fixture (Join-Path $SourceRoot 'openspec/specs/nested/spec.md') '# Scaffold'
    Write-Fixture (Join-Path $SourceRoot 'content/openspec-bundle/version.txt') 'fixture'
    Write-Fixture (Join-Path $SourceRoot 'content/openspec-bundle/cursor/.cursor/commands/opsx/probe.md') '# Bundle'
    $sourceHashes = @{}
    Get-ChildItem -LiteralPath $SourceRoot -Recurse -File | ForEach-Object { $sourceHashes[$_.FullName] = (Get-FileHash -LiteralPath $_.FullName).Hash }

    # Import helpers through the AST without executing the installer's dispatch.
    $tokens = $null; $parseErrors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile($Installer, [ref]$tokens, [ref]$parseErrors)
    Assert-True ($parseErrors.Count -eq 0) 'Installer did not parse'
    foreach ($name in @('Resolve-InstallerExistingPath', 'Get-InstallerRelativePath', 'Get-1cProjectInfo',
        'Get-1cFieldValue', 'Get-1cSynonymRu', 'Get-EnvFileValue', 'Read-DevEnvKeys', 'Convert-AgentsMdPaths',
        'Resolve-CanonicalArtifactLayouts', 'Get-AdapterForTool', 'Parse-SimpleYaml', 'Read-TextFile',
        'ConvertFrom-AdapterYaml', 'Get-YamlIndent', 'Test-YamlBlank', 'Invoke-YamlBlock',
        'Invoke-YamlBlockArray', 'ConvertFrom-YamlInlineValue', 'Split-YamlFlow', 'ConvertFrom-Scalar',
        'Invoke-CodexAgentTemplate', 'ConvertTo-TomlString', 'Get-RelativeLinkPath', 'Get-LegacyRelativeLinkPath')) {
        $function = $ast.Find({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
        if ($function) { . ([scriptblock]::Create($function.Extent.Text)) }
    }
    $script:DevEnvFileName = '.dev.env'

    $linkBase = [IO.Path]::GetFullPath((Join-Path $Work 'link project/skills'))
    $linkTarget = [IO.Path]::GetFullPath((Join-Path $Work 'link project/rules/probe space#name.mdc'))
    foreach ($baseDir in @($linkBase, ($linkBase + [IO.Path]::DirectorySeparatorChar))) {
        $relative = Get-RelativeLinkPath -BaseDirectory $baseDir -TargetPath $linkTarget
        $legacy = Get-LegacyRelativeLinkPath -BaseDirectory $baseDir -TargetPath $linkTarget
        Assert-True ($relative -ceq '../rules/probe space#name.mdc') "Filesystem relative path corrupted: $relative"
        Assert-True ($legacy -ceq $relative) "PS5.1 fallback differs: $legacy"
    }
    Pass 'Absolute filesystem paths with spaces/hash use Path.GetRelativePath or the equivalent PS5.1 fallback'

    $project = Join-Path $Work 'project directory with long name'
    Write-Fixture (Join-Path $project '.dev.env') "EXPORT_PATH=`"src/custom dump`"`nINFOBASE_PATH=`nUSE_EDT=false`n"
    Write-Fixture (Join-Path $project 'src/custom dump/Configuration.xml') '<MetaDataObject><Configuration><Properties><Name>SelectedConfig</Name><Version>1.2</Version><CompatibilityMode>Version8_3_25</CompatibilityMode></Properties></Configuration></MetaDataObject>'
    Write-Fixture (Join-Path $project 'src/custom dump/Catalogs/Item.xml') '<Item/>'
    Write-Fixture (Join-Path $project 'src/custom dump/Subsystems/Selected.xml') '<Subsystem/>'
    Write-Fixture (Join-Path $project 'Configuration.xml') '<MetaDataObject><Properties><Name>WrongRoot</Name></Properties></MetaDataObject>'
    Write-Fixture (Join-Path $project '.cursor/rules/user.mdc') 'user-owned'

    $shortSource = $SourceRoot; $shortProject = $project
    try {
        $fso = New-Object -ComObject Scripting.FileSystemObject
        $sourceAlias = $fso.GetFolder($SourceRoot).ShortPath
        $projectAlias = $fso.GetFolder($project).ShortPath
        if ($sourceAlias -ne $SourceRoot -and $projectAlias -ne $project) {
            $shortSource = $sourceAlias; $shortProject = $projectAlias
            $script:ShortPathChecked = $true
        }
    } catch { Write-Host "SKIP  Windows 8.3 aliases unavailable: $($_.Exception.Message)" }
    if (-not $script:ShortPathChecked) { Write-Host 'SKIP  Volume did not provide distinct short paths; long-path cases still run.' }

    $child = Join-Path $SourceRoot 'content/skills/probe/docs/detail.md'
    Assert-True ((Get-InstallerRelativePath -BasePath $shortSource -ChildPath $child) -eq 'content/skills/probe/docs/detail.md') 'Mixed short/long relative path was corrupted'
    $outside = Join-Path $Work 'source repository with long name sibling/outside.md'
    Write-Fixture $outside 'outside'
    $refused = $false
    try { $null = Get-InstallerRelativePath -BasePath $shortSource -ChildPath $outside } catch { $refused = $true }
    Assert-True $refused 'Sibling prefix escaped the source base'
    Pass 'Relative paths normalize aliases and reject paths outside the base'

    $null = Invoke-Installer $shortProject @('init', '-Tools', 'cursor') $shortSource
    foreach ($rel in @('AGENTS.md', '.cursor/rules/probe.mdc', '.cursor/agents/probe.md', '.cursor/commands/probe.md',
        '.cursor/skills/probe/SKILL.md', '.cursor/skills/probe/docs/detail.md')) {
        Assert-Links (Join-Path $project $rel) '.cursor/rules' 'mdc' '.cursor/agents' '.cursor/commands' '.cursor/skills'
    }
    foreach ($rel in @('scripts/probe.ps1', 'payload.bin')) {
        Assert-True ((Get-FileHash -LiteralPath (Join-Path $SourceRoot "content/skills/probe/$rel")).Hash -eq
            (Get-FileHash -LiteralPath (Join-Path $project ".cursor/skills/probe/$rel")).Hash) "Non-Markdown changed: $rel"
    }
    Assert-True (Test-Path -LiteralPath (Join-Path $project 'openspec/specs/nested/spec.md')) 'Scaffold path was corrupted'
    Assert-True (Test-Path -LiteralPath (Join-Path $project '.cursor/commands/opsx/probe.md')) 'Bundle path was corrupted'
    $manifest = Read-Json (Join-Path $project '.ai-rules.json')
    Assert-True ($manifest.foreignFiles.cursor -contains '.cursor/rules/user.mdc') 'Foreign scan path was corrupted'
    Assert-True ($manifest.integrations.openspec.files -contains 'openspec/specs/nested/spec.md') 'Integration scan path was corrupted'
    Assert-True (([IO.File]::ReadAllText((Join-Path $project 'openspec/project.md'))).Contains('SelectedConfig')) 'Explicit relative EXPORT_PATH ignored'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $project 'src/custom dump/openspec'))) 'Generated context was written inside source dump'
    Assert-ManifestHashes $project
    foreach ($path in $sourceHashes.Keys) { Assert-True ($sourceHashes[$path] -eq (Get-FileHash -LiteralPath $path).Hash) "Installer mutated source: $path" }
    Pass 'Init through short paths installs correct links, scans, scaffold and bundle without changing sources'

    $null = Invoke-Installer $shortProject @('update') $shortSource
    $manifest = Read-Json (Join-Path $project '.ai-rules.json')
    foreach ($property in $manifest.files.PSObject.Properties) { Assert-True (-not $property.Value.userModified) "Clean transformed file became userModified: $($property.Name)" }
    Assert-ManifestHashes $project
    Pass 'Clean update hashes transformed bytes and does not mark installed files userModified'

    Write-Fixture (Join-Path $project '.cursor/rules/probe.mdc') 'my rule'
    Write-Fixture (Join-Path $project '.cursor/skills/probe/docs/detail.md') 'my skill docs'
    Write-Fixture (Join-Path $project '.cursor/skills/probe/local.txt') 'my extra file'
    Write-Fixture (Join-Path $project 'openspec/project.md') 'my project description'
    Add-Content -LiteralPath (Join-Path $SourceRoot 'content/commands/probe.md') -Value "`nVersion two: $refs" -Encoding UTF8
    $staleSource = [IO.Path]::GetFullPath((Join-Path $SourceRoot 'content/skills/probe/stale.txt'))
    Assert-True ($staleSource.StartsWith([IO.Path]::GetFullPath($SourceRoot) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) 'Unsafe fixture removal'
    Remove-Item -LiteralPath $staleSource
    $null = Invoke-Installer $shortProject @('update') $shortSource
    foreach ($entry in @(@('.cursor/rules/probe.mdc', 'my rule'), @('.cursor/skills/probe/docs/detail.md', 'my skill docs'),
        @('.cursor/skills/probe/local.txt', 'my extra file'), @('openspec/project.md', 'my project description'))) {
        Assert-True (([IO.File]::ReadAllText((Join-Path $project $entry[0]))) -eq $entry[1]) "User content lost: $($entry[0])"
    }
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $project '.cursor/skills/probe/stale.txt'))) 'Stale managed skill file survived pruning'
    Assert-Links (Join-Path $project '.cursor/commands/probe.md') '.cursor/rules' 'mdc' '.cursor/agents' '.cursor/commands' '.cursor/skills'
    $manifest = Read-Json (Join-Path $project '.ai-rules.json')
    Assert-True $manifest.files.'.cursor/rules/probe.mdc'.userModified 'Edited rule ownership lost'
    Assert-True $manifest.files.'.cursor/skills/probe/docs/detail.md'.userModified 'Edited skill ownership lost'
    Assert-ManifestHashes $project
    Pass 'Update preserves modified rules, skills and project.md while pruning only stale managed skill files'

    foreach ($client in @('opencode', 'opencode,cursor')) {
        $multi = Join-Path $Work $client
        [void][IO.Directory]::CreateDirectory($multi)
        $null = Invoke-Installer $multi @('init', '-Tools', $client)
        $cursorWins = $client.Contains(',')
        $rules = if ($cursorWins) { '.cursor/rules' } else { '.opencode/rules' }
        $ext = if ($cursorWins) { 'mdc' } else { 'md' }
        $agents = if ($cursorWins) { '.cursor/agents' } else { '.opencode/agent' }
        $commands = if ($cursorWins) { '.cursor/commands' } else { '.opencode/command' }
        $skills = if ($cursorWins) { '.cursor/skills' } else { '.claude/skills' }
        foreach ($rel in @('AGENTS.md', '.opencode/agent/probe.md', '.opencode/command/probe.md', '.claude/skills/probe/docs/detail.md')) {
            Assert-Links (Join-Path $multi $rel) $rules $ext $agents $commands $skills
        }
        Assert-ManifestHashes $multi
    }
    Pass 'Single and multiple clients use canonical layouts including OpenCode singular directories'

    $null = Invoke-Installer $project @('add', '-Tool', 'opencode')
    Assert-Links (Join-Path $project '.opencode/agent/probe.md') '.cursor/rules' 'mdc' '.cursor/agents' '.cursor/commands' '.cursor/skills'
    Assert-True (([IO.File]::ReadAllText((Join-Path $project '.cursor/rules/probe.mdc'))) -eq 'my rule') 'Add overwrote an existing user edit'
    Pass 'Add resolves new file links against the complete active client set'

    $absoluteProject = Join-Path $Work 'absolute-export-project'
    Write-Fixture (Join-Path $absoluteProject '.dev.env') ("EXPORT_PATH='" + (Join-Path $project 'src/custom dump') + "'`n")
    $info = Get-1cProjectInfo -Root $absoluteProject
    Assert-True ($info.Detected -and $info.Name -eq 'SelectedConfig' -and $info.PlatformVersion -eq '8.3.25') 'Absolute EXPORT_PATH was ignored'
    Assert-True ($info.Subsystems -contains 'Selected' -and @($info.Counts.Values)[0] -eq 1) 'Subsystems/counts used the wrong source root'
    Write-Fixture (Join-Path $absoluteProject 'Configuration.xml') '<MetaDataObject><Properties><Name>RootFallback</Name></Properties></MetaDataObject>'
    Write-Fixture (Join-Path $absoluteProject '.dev.env') 'EXPORT_PATH=missing'
    Assert-True (-not (Get-1cProjectInfo -Root $absoluteProject).Detected) 'Missing explicit EXPORT_PATH fell back to an unrelated root'
    Write-Fixture (Join-Path $absoluteProject '.dev.env') 'EXPORT_PATH='
    Assert-True ((Get-1cProjectInfo -Root $absoluteProject).Name -eq 'RootFallback') 'Empty EXPORT_PATH did not use project root'
    $unselected = Join-Path $Work 'unselected-nested'
    Write-Fixture (Join-Path $unselected 'nested/Configuration.xml') '<MetaDataObject><Properties><Name>NeverGuess</Name></Properties></MetaDataObject>'
    Assert-True (-not (Get-1cProjectInfo -Root $unselected).Detected) 'Detection chose an arbitrary nested configuration'
    Pass 'Source discovery honors absolute/relative/empty/missing EXPORT_PATH without recursive guessing'

    $layouts = [ordered]@{
        rules = @{ Dir = '.codex/rules'; Ext = 'md'; Template = '.codex/rules/{name}.md' }
        agents = @{ Dir = '.codex/agents'; Ext = 'toml'; Template = '.codex/agents/{name}.toml' }
        commands = @{ Dir = '~/.codex/prompts'; Ext = 'md'; Template = '~/.codex/prompts/{name}.md' }
        skills = @{ Dir = '.codex/skills'; Ext = ''; Template = '.codex/skills/{name}/' }
    }
    $body = Convert-AgentsMdPaths -Text $refs -Layouts $layouts
    $template = 'developer_instructions = """' + "`n{body}`n" + '"""'
    $rendered = Invoke-CodexAgentTemplate -Template $template -Fm ([ordered]@{}) -Body $body
    Assert-True ($rendered.Contains('.codex/agents/probe.toml') -and $rendered.Contains('~/.codex/prompts/probe.md')) 'TOML agent body paths were not transformed'
    $layouts.agents.Template = '.agents/agents/{name}/agent.md'
    $nested = Convert-AgentsMdPaths -Text 'content/agents/probe.md content/agents/<name>.md' -Layouts $layouts
    Assert-True ($nested -eq '.agents/agents/probe/agent.md .agents/agents/<name>/agent.md') 'Full copyTo template was truncated'
    Pass 'Agent-body conversion preserves TOML paths and full copyTo templates without global writes'

    # Check the orchestration order without changing the optional-dump unit contract.
    foreach ($operation in @('Invoke-Init', 'Invoke-Update')) {
        $fn = $ast.Find({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $operation }, $true)
        $bodyText = $fn.Extent.Text
        Assert-True ($bodyText.IndexOf('Place-DevEnv -Root') -lt $bodyText.IndexOf('Invoke-OpenSpecProjectMd -Root')) "$operation generates context before .dev.env"
    }
    $init = $ast.Find({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Invoke-Init' }, $true).Extent.Text
    Assert-True ($init.LastIndexOf('Invoke-OpenSpecProjectMd -Root') -gt $init.IndexOf('Invoke-InitialSourceDump -Root')) 'Initial dump cannot refresh project context'
    Pass 'Context generation follows .dev.env placement and optional initial source export'

    # Run the real init flow with explicit test consent and a local export stub.
    # This verifies the post-export project.md write, not just function order.
    Write-Fixture (Join-Path $SourceRoot 'content/skills/1c-metadata-manage/tools/1c-db-ops/scripts/db-dump-xml.ps1') @'
param($ConfigDir, $Mode, $InfoBasePath)
[void][IO.Directory]::CreateDirectory($ConfigDir)
[IO.File]::WriteAllText((Join-Path $ConfigDir 'Configuration.xml'), '<MetaDataObject><Configuration><Properties><Name>DumpedConfig</Name></Properties></Configuration></MetaDataObject>')
exit 0
'@
    $exportProject = Join-Path $Work 'accepted-export-project'
    Write-Fixture (Join-Path $exportProject '.dev.env') "INFOBASE_PATH=fixture-only`nEXPORT_PATH=`nUSE_EDT=false`n"
    $wrapper = Join-Path $Work 'accepted-export.ps1'
    Write-Fixture $wrapper @'
param($InstallerFile, $ProjectFixture, $SourceFixture)
$ErrorActionPreference = 'Stop'
$installerText = [IO.File]::ReadAllText($InstallerFile)
$dispatch = $installerText.IndexOf('# SECTION 14: MAIN DISPATCH')
if ($dispatch -lt 0) { throw 'Installer dispatch marker missing' }
. ([scriptblock]::Create($installerText.Substring(0, $dispatch)))
function Read-YesNo { param($Prompt, $Default) return $true }
function Read-Required { param($Prompt, $DefaultValue) return $DefaultValue }
function Read-Choice { param($Prompt, $Options, $Default) return $Default }
$script:NonInteractive = $false
$script:AssumeYes = $false
$script:McpMode = 'managed'
Invoke-Init -Root $ProjectFixture -SourceRootRequested $SourceFixture -RequestedTools @('cursor')
'@
    $exportLog = Join-Path $Work 'accepted-export.log'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $wrapper -InstallerFile $Installer `
        -ProjectFixture $exportProject -SourceFixture $SourceRoot *> $exportLog
    Assert-True ($LASTEXITCODE -eq 0) "Accepted export failed: $(Get-Content -LiteralPath $exportLog -Raw)"
    Assert-True (([IO.File]::ReadAllText((Join-Path $exportProject 'openspec/project.md'))).Contains('DumpedConfig')) 'Successful initial dump did not refresh project.md'
    Assert-True ((Get-1cProjectInfo -Root $exportProject).Name -eq 'DumpedConfig') 'New EXPORT_PATH was not used after export'
    Assert-ManifestHashes $exportProject
    Pass 'Successful initial export refreshes project context and manifest through the real init flow'

    foreach ($tool in @('cursor', 'claude-code', 'kimi', 'opencode')) {
        $relativeProject = Join-Path $Work "relative-$tool"
        [void][IO.Directory]::CreateDirectory($relativeProject)
        $null = Invoke-Installer $relativeProject @('init', '-Tools', $tool)
        $first = Assert-RelativeLinks -Project $relativeProject -Tool $tool
        Assert-True ($first.Placeholders.Count -eq 1) "Placeholder was changed for $tool"
        $expectedNotInstalled = if ($tool -eq 'kimi') { 2 } else { 0 }
        Assert-True ($first.NotInstalled.Count -eq $expectedNotInstalled) "Unexpected uninstalled-section links for $tool"
        $adapter = Get-AdapterForTool -Root $SourceRoot -Tool $tool
        $copies = @()
        foreach ($section in @('rules', 'agents', 'commands', 'skills')) {
            if ($adapter.Contains($section) -and $adapter[$section].copyTo) { $copies += "$section=$($adapter[$section].copyTo)" }
        }
        Write-Host "ADAPTER $tool`: $($copies -join '; ')"
        $ownedDocuments = @($adapter.agents.copyTo.Replace('{name}', 'probe'),
            ($adapter.skills.copyTo.Replace('{name}', 'probe').TrimEnd('/', '\') + '/docs/detail.md'))
        if ($adapter.Contains('commands') -and $adapter.commands.copyTo) { $ownedDocuments += $adapter.commands.copyTo.Replace('{name}', 'probe') }
        $ownedTargets = 0
        foreach ($document in $ownedDocuments) { $ownedTargets += Assert-AdapterLinkTargets -Project $relativeProject -DocumentRel $document -Tool $tool }
        Write-Host "OWNER-TARGETS $tool`: $ownedTargets match declared copyTo"
        # Negative control: an installed section with a missing target must still fail.
        $ruleFixture = [IO.Path]::GetFullPath((Join-Path $relativeProject $adapter.rules.copyTo.Replace('{name}', 'probe')))
        Assert-True ($ruleFixture.StartsWith([IO.Path]::GetFullPath($relativeProject) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) 'Unsafe negative fixture path'
        $ruleBytes = [IO.File]::ReadAllBytes($ruleFixture)
        try {
            Remove-Item -LiteralPath $ruleFixture
            $refusedMissingTarget = $false
            try { $null = Assert-RelativeLinks -Project $relativeProject -Tool $tool }
            catch { $refusedMissingTarget = $_.Exception.Message -match 'broken=[1-9]' }
            Assert-True $refusedMissingTarget "Missing installed rule was not reported as broken for $tool"
        }
        finally { [IO.File]::WriteAllBytes($ruleFixture, $ruleBytes) }
        $beforeUpdate = @{}
        foreach ($file in Get-ChildItem -LiteralPath $relativeProject -Force -Recurse -File | Where-Object { $_.Extension -in @('.md', '.mdc', '.toml') }) {
            $beforeUpdate[$file.FullName] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        }
        $null = Invoke-Installer $relativeProject @('update')
        $second = Assert-RelativeLinks -Project $relativeProject -Tool $tool
        Assert-True ($first.Checked -eq $second.Checked -and $first.Placeholders.Count -eq $second.Placeholders.Count -and
            ($first.NotInstalled -join "`n") -ceq ($second.NotInstalled -join "`n")) "Relative link census changed on repeat update for $tool"
        foreach ($path in $beforeUpdate.Keys) {
            Assert-True ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $beforeUpdate[$path]) "Repeated update changed $path"
        }
        Assert-ManifestHashes $relativeProject
        Write-Host "LINKS $tool`: checked=$($second.Checked); resolved=$($second.Resolved); broken=$($second.Broken); not-installed-section=$($second.NotInstalled.Count); placeholders=$($second.Placeholders.Count); repeat update byte-identical"
        foreach ($detail in $second.NotInstalled) { Write-Host "  NOT-INSTALLED-SECTION $tool`: $detail" }
        foreach ($detail in $second.Placeholders) { Write-Host "  PLACEHOLDER $tool`: $detail" }
    }
    Pass 'Cross-section relative links use adapter-owned paths; placeholders and repeat updates are stable'

    foreach ($toolsCase in @('claude-code,opencode', 'opencode,claude-code', 'cursor,claude-code,kimi,opencode')) {
        $sharedProject = Join-Path $Work ('owner-' + $toolsCase.Replace(',', '-'))
        [void][IO.Directory]::CreateDirectory($sharedProject)
        $null = Invoke-Installer $sharedProject @('init', '-Tools', $toolsCase)
        $sharedDoc = '.claude/skills/probe/docs/detail.md'
        $sharedTargets = Assert-AdapterLinkTargets -Project $sharedProject -DocumentRel $sharedDoc -Tool 'claude-code'
        $checkedOwned = $sharedTargets
        foreach ($toolId in ($toolsCase -split ',')) {
            $caseAdapter = Get-AdapterForTool -Root $SourceRoot -Tool $toolId
            $checkedOwned += Assert-AdapterLinkTargets -Project $sharedProject -DocumentRel $caseAdapter.agents.copyTo.Replace('{name}', 'probe') -Tool $toolId
            if ($caseAdapter.Contains('commands') -and $caseAdapter.commands.copyTo) {
                $checkedOwned += Assert-AdapterLinkTargets -Project $sharedProject -DocumentRel $caseAdapter.commands.copyTo.Replace('{name}', 'probe') -Tool $toolId
            }
            if ($toolId -in @('cursor', 'kimi')) {
                $skillDoc = $caseAdapter.skills.copyTo.Replace('{name}', 'probe').TrimEnd('/', '\') + '/docs/detail.md'
                $checkedOwned += Assert-AdapterLinkTargets -Project $sharedProject -DocumentRel $skillDoc -Tool $toolId
            }
        }
        $doc = Join-Path $sharedProject $sharedDoc
        $firstBytes = [IO.File]::ReadAllBytes($doc)
        # A valid foreign file must be rejected too: existence alone is insufficient.
        if (-not (Test-Path -LiteralPath (Join-Path $sharedProject '.cursor/rules/probe.mdc'))) {
            Write-Fixture (Join-Path $sharedProject '.cursor/rules/probe.mdc') '# existing foreign rule'
        }
        $foreignDoc = [IO.File]::ReadAllText($doc).Replace('../../../rules-1c/probe.md', '../../../../.cursor/rules/probe.mdc')
        try {
            [IO.File]::WriteAllText($doc, $foreignDoc, $Utf8)
            $refusedForeign = $false
            try { $null = Assert-AdapterLinkTargets -Project $sharedProject -DocumentRel $sharedDoc -Tool 'claude-code' }
            catch { $refusedForeign = $_.Exception.Message -like 'Foreign adapter target:*' }
            Assert-True $refusedForeign 'Existing foreign rule was accepted for a Claude-owned shared document'
        }
        finally { [IO.File]::WriteAllBytes($doc, $firstBytes) }
        $before = @{}
        foreach ($f in Get-ChildItem -LiteralPath $sharedProject -Force -Recurse -File | Where-Object { $_.Extension -in @('.md', '.mdc', '.toml') }) {
            $before[$f.FullName] = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
        }
        $null = Invoke-Installer $sharedProject @('update')
        foreach ($p in $before.Keys) {
            # Cursor is active in the full multi-client case and refreshes its own rule.
            if ($toolsCase.StartsWith('cursor,') -and $p -eq (Join-Path $sharedProject '.cursor/rules/probe.mdc')) { continue }
            Assert-True ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -eq $before[$p]) "Owner layouts changed on repeat update: $p"
        }
        Assert-True ((Assert-AdapterLinkTargets -Project $sharedProject -DocumentRel $sharedDoc -Tool 'claude-code') -eq $sharedTargets) 'Shared owner changed after update'
        Assert-ManifestHashes $sharedProject
        Write-Host "OWNER $toolsCase`: targets=$checkedOwned; foreign-targets=0; shared-rule=.claude/rules-1c/probe.md; repeat update byte-identical"
    }
    Pass 'Shared directory owner beats writer order; foreign existing trees are rejected'

    Write-Host "OK: $script:Passed installer path cases; real 8.3 paths checked: $script:ShortPathChecked; no network or infobase accessed."
}
finally {
    $resolved = [IO.Path]::GetFullPath($Work)
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if ($resolved.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolved -Leaf) -match '^installer-paths-[a-f0-9]{32}$') {
        if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
    }
    else { throw "Unsafe fixture cleanup refused: $resolved" }
}
