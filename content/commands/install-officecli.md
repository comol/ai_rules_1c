---
description: Install OfficeCLI for creating, reading and editing Word, Excel and PowerPoint files without Microsoft Office
userOnly: true
argumentHint: "[status]"
---

# /install-officecli — install OfficeCLI

Installs [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI), a standalone CLI for `.docx`, `.xlsx` and `.pptx` files. Microsoft Office and a separate .NET runtime are not required. This is an optional, user-level tool; it does not require a 1C infobase or a purchased MCP bundle.

Follow the current [installation documentation](https://github.com/iOfficeAI/OfficeCLI#installation). Shell on Windows — `content/skills/powershell-windows/SKILL.md`.

An explicit `/install-officecli` invocation or selection in `/installtools` authorizes installation. Show the chosen commands and proceed without asking for the same selection again. `/install-officecli status` is detection only.

## Steps

### 1. Detect an existing installation

Resolve `officecli` with `Get-Command officecli -ErrorAction SilentlyContinue` on Windows or `command -v officecli` on macOS/Linux. If it is absent from `PATH`, also check the native install location: `%LOCALAPPDATA%\OfficeCLI\officecli.exe` on Windows, `~/.local/bin/officecli` on macOS/Linux. Probe an existing binary by its absolute path with `--version`.

For every probe and verification call, temporarily set `OFFICECLI_SKIP_UPDATE=1` in the child/process environment to suppress background updates, then restore its previous value. Never invoke bare `officecli`, `officecli install`, a package installer or a skill installer during detection.

- Version succeeds: `installed`; report its version and resolved path. Skip installation unless repair/reinstall was explicitly requested. A missing `PATH` entry alone is not a reason to reinstall.
- No executable found: `not installed`.
- An executable exists but fails: `uncertain`; show the actual error, do not overwrite it automatically.

For `status`, report the result and stop without downloads, questions or configuration changes. Otherwise, for an existing working binary continue to verification; for a missing binary continue below.

### 2. Install the native binary

Detect the host OS and architecture; use the matching upstream installer for Windows, macOS or Linux on x64/ARM64. Stop with a clear explanation for an unsupported platform. Prefer the native installer so Node.js/npm are not prerequisites.

Before execution, read the downloaded script and summarize its actual effects. The upstream scripts install the binary, adjust the user's `PATH`/shell profile if needed, and on first installation copy an OfficeCLI skill into detected AI clients' user directories. Preserve any existing customized OfficeCLI skill before replacement and report the affected paths. Do not infer skill success from the binary's version alone.

#### Windows (PowerShell)

Download to a unique temporary directory:

```powershell
$OfficeCliSetupDir = Join-Path ([IO.Path]::GetTempPath()) ('officecli-setup-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $OfficeCliSetupDir -ErrorAction Stop | Out-Null
$OfficeCliSetupScript = Join-Path $OfficeCliSetupDir 'install.ps1'
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.ps1' -OutFile $OfficeCliSetupScript -UseBasicParsing -ErrorAction Stop
Get-Content -LiteralPath $OfficeCliSetupScript
```

After inspecting that script, run it in a separate PowerShell process so an upstream `exit` does not terminate the calling session:

```powershell
$OfficeCliPreviousSkipUpdate = $env:OFFICECLI_SKIP_UPDATE
try {
    $env:OFFICECLI_SKIP_UPDATE = '1'
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $OfficeCliSetupScript
    if ($LASTEXITCODE -ne 0) { throw 'OfficeCLI installation failed' }
} finally {
    $env:OFFICECLI_SKIP_UPDATE = $OfficeCliPreviousSkipUpdate
}
$OfficeCliBinDir = Join-Path $env:LOCALAPPDATA 'OfficeCLI'
if (($env:Path -split ';') -notcontains $OfficeCliBinDir) {
    $env:Path = "$OfficeCliBinDir;$env:Path"
}
```

The execution-policy override applies only to that child process. The default fresh-install path is `%LOCALAPPDATA%\OfficeCLI\officecli.exe`; use the actual installer output if a repair reused another location. Do not replace the entire current `PATH` with a value read from the registry.

#### macOS / Linux (Bash)

Require existing `curl` and `bash`; if either is missing, report the prerequisite. Download and inspect:

```bash
officecli_setup_dir=$(mktemp -d) || exit 1
officecli_setup_script="$officecli_setup_dir/install.sh"
curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh -o "$officecli_setup_script" || exit 1
cat "$officecli_setup_script"
```

After inspection:

```bash
OFFICECLI_SKIP_UPDATE=1 bash "$officecli_setup_script" || exit 1
export PATH="$HOME/.local/bin:$PATH"
```

The default fresh-install path is `~/.local/bin/officecli`. Use the actual installer output for an existing custom location. Do not use `sudo` for a normal user-level install.

If download or installation fails, stop this installer and report the failing step. Do not claim success from the installer's final message alone or silently switch installation methods. When repairing a package-manager installation, use its existing manager instead of overwriting it with the native installer.

### 3. Verify and report

Resolve the executable again and run `officecli --version` and `officecli --help` with temporary `OFFICECLI_SKIP_UPDATE=1`; both must exit successfully. If the current shell still cannot resolve it, verify using the actual absolute path and report that a terminal/client restart is needed to pick up `PATH`. Check any reported skill files separately; missing skills mean CLI-only installation, not full agent integration.

Do not run `officecli install` again merely to verify: it can change client integrations. Do not register MCP servers, change `.dev.env` or enable UI tests as part of this command. Clean up only the temporary setup directory created by this invocation, after checking its resolved path.

Final report in Russian, short: `installed`, `already present` or `failed: <reason>`; CLI version and path; skill paths actually installed (or CLI-only); restart only when needed. The tool menu is `/installtools` (`content/commands/installtools.md`).

## Parameters

- `/install-officecli` — detect and install if missing, then verify.
- `/install-officecli status` — report installation state only.
