# Shared 1C platform path resolution for skill PowerShell tools.
# Accepts the same shapes as .dev.env PLATFORM_PATH (version install dir),
# the bin directory, or a full path to 1cv8.exe.

function Resolve-V8ExePath {
    param(
        [Parameter(Mandatory = $false)]
        [string]$V8Path
    )

    if ([string]::IsNullOrWhiteSpace($V8Path)) {
        $searchRoots = @(
            (Join-Path $env:ProgramFiles '1cv8')
        )
        if (${env:ProgramFiles(x86)}) {
            $searchRoots += (Join-Path ${env:ProgramFiles(x86)} '1cv8')
        }

        $found = foreach ($root in ($searchRoots | Where-Object { $_ -and (Test-Path $_) })) {
            Get-ChildItem -Path (Join-Path $root '*\bin\1cv8.exe') -ErrorAction SilentlyContinue
        }
        $best = @($found | Sort-Object FullName -Descending | Select-Object -First 1)
        if ($best.Count -gt 0) {
            return $best[0].FullName
        }
        return $null
    }

    $inputPath = $V8Path.Trim().TrimEnd('\', '/')

    if ($inputPath -match '[/\\]1cv8\.exe$') {
        if (Test-Path -LiteralPath $inputPath) {
            return (Resolve-Path -LiteralPath $inputPath).Path
        }
        return $null
    }

    if (-not (Test-Path -LiteralPath $inputPath -PathType Container)) {
        return $null
    }

    $directExe = Join-Path $inputPath '1cv8.exe'
    if (Test-Path -LiteralPath $directExe) {
        return (Resolve-Path -LiteralPath $directExe).Path
    }

    $binExe = Join-Path $inputPath 'bin\1cv8.exe'
    if (Test-Path -LiteralPath $binExe) {
        return (Resolve-Path -LiteralPath $binExe).Path
    }

    return $null
}

function Resolve-V8BinPath {
    param(
        [Parameter(Mandatory = $false)]
        [string]$V8Path
    )

    $exe = Resolve-V8ExePath -V8Path $V8Path
    if ($exe) {
        return (Split-Path -Parent $exe)
    }
    return $null
}
