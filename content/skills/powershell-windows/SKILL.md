---
name: powershell-windows
description: "PowerShell scripting rules for Windows environment. Use when running shell commands, Docker operations, or HTTP requests on Windows PowerShell."
---

# PowerShell Windows — Scripting Rules

## Core Principles

### 1. Command Separation
- Windows PowerShell 5.1 does not support `&&`; PowerShell 7 does.
- For independent commands use `;`: `Set-Location "path"; Get-ChildItem`.
- For dependent native commands preserve short-circuit semantics explicitly:
  ```powershell
  git add .
  if ($LASTEXITCODE -eq 0) { git commit -m "message" }
  ```

### 2. Path Quoting
- **Always use double quotes** for paths with spaces:
  ```powershell
  cd "D:\My Projects\MyApp"
  ```

### 3. Script Execution
- For .bat/.cmd files:
  ```powershell
  ./gradlew clean build
  .\gradlew.bat clean build
  ```

### 4. Docker Commands
- Specify full path to docker-compose files:
  ```powershell
  docker-compose -f "D:\My Projects\app\docker-compose.yml" up -d
  ```

### 5. HTTP Requests
- Prefer PowerShell-native HTTP so behavior does not depend on whether `curl`
  resolves to an alias or `curl.exe`:
  ```powershell
  Invoke-WebRequest -Uri "http://localhost:9090/status" -UseBasicParsing
  ```

### 6. Waiting/Delays
- **Wrong**: `timeout 10`
- **Correct**:
  ```powershell
  Start-Sleep -Seconds 10
  ```

### 7. JSON Handling
- JSON parsing:
  ```powershell
  $response = Invoke-WebRequest -Uri "http://localhost:9090/status" -UseBasicParsing
  $json = $response.Content | ConvertFrom-Json
  $json | ConvertTo-Json -Depth 3
  ```

### 8. Process Checking
- Process search:
  ```powershell
  Get-Process -Name "java" -ErrorAction SilentlyContinue
  ```

### 9. Docker Operations
- Stop containers:
  ```powershell
  docker-compose -f "path\to\file.yml" down
  ```
- Build images:
  ```powershell
  docker-compose -f "path\to\file.yml" build --no-cache
  ```

### 10. Error Handling
- Ignore errors:
  ```powershell
  Get-Process -Name "java" -ErrorAction SilentlyContinue
  ```

### 11. Cyrillic Paths, Encoding and Silent Delete Traps
- **PS 5.1 script encoding:** save any `.ps1` containing Cyrillic literals with UTF-8 **BOM** (or pure ASCII with `[char]` escapes); BOM-less UTF-8 is read as ANSI by Windows PowerShell 5.1 (`1С` becomes `1РЎ`).
- **UTF-8 stdout:** `Get-Content -Encoding UTF8` sets input encoding only — PowerShell pipelines (`Get-Content`, `rg | Select-String`) can still re-encode stdout to the OEM code page and corrupt Cyrillic (`U+FFFD`). Prefer `[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)` or Python with `-X utf8` (`sys.stdout.reconfigure(encoding="utf-8")`).
- **Batch files (`.bat`/`.cmd`):** keep platform-launch batch files in single-byte OEM/ANSI encoding, not UTF-8; for unattended 1C CLI runs, Latin technical user names avoid Win32 argument transcoding traps.
- **Verify recursive deletion on Cyrillic paths:** some runtimes (notably Node recursive `fs.rm` on Windows) can return without throwing while leaving a Cyrillic directory on disk. Always confirm deletion with `Test-Path -LiteralPath` rather than trusting exit code 0 alone.
- **Stop after two encoding misses:** if a shell tool fails twice to locate an existing Cyrillic path, switch to a Unicode-native tool (agent file tools, PowerShell `-LiteralPath`, or Python) instead of retrying the same shell wrapper.

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `&& is not recognized` | Running Windows PowerShell 5.1 | Use `;` only for independent commands; use `$LASTEXITCODE` for conditional chaining |
| `curl` behaves unexpectedly | Windows PowerShell alias / executable resolution differs | Use `Invoke-WebRequest`, or call `curl.exe` explicitly when its CLI semantics are required |
| `timeout` behaves unexpectedly | Console utility semantics differ from shell sleep | Use `Start-Sleep` |
| `Path not found` | Missing quotes on spaced path | Wrap path in double quotes |

## Correct Command Examples

```powershell
# Change directory and execute command
cd "D:\My Projects\MyApp"; ./gradlew clean build -x test

# Wait and make HTTP request
Start-Sleep -Seconds 10; Invoke-WebRequest -Uri "http://localhost:9090/status" -UseBasicParsing

# Docker operations
docker-compose -f "D:\My Projects\MyApp\docker-compose.yml" down
docker-compose -f "D:\My Projects\MyApp\docker-compose.yml" build --no-cache
docker-compose -f "D:\My Projects\MyApp\docker-compose.yml" up -d

# Check server status
$response = Invoke-WebRequest -Uri "http://localhost:9090/status" -UseBasicParsing
$json = $response.Content | ConvertFrom-Json
Write-Host "Transport: $($json.mcp.transport)"
```
