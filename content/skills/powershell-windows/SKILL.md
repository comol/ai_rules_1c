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
