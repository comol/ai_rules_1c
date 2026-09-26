---
description: Install OpenViking persistent memory with its native HTTP MCP endpoint and register it in the active AI client
userOnly: true
---

# /install-openviking — install OpenViking persistent memory

Install the official OpenViking package and connect its built-in HTTP MCP endpoint. Use the server id `openviking`. A separate MCP proxy is unnecessary.

Memory routing and triage scope follow `content/rules/project-memory.md` after `.dev.env` `TOOL_*` policy. Installation preserves every provider choice; `TOOL_OPENVIKING=off` allows explicitly requested setup checks but still excludes ordinary memory use. A client config entry alone does not prove callable tools. Connecting this provider does not enable or disable another.

Official references (recheck the selected release before installation):

- [Agent setup](https://docs.openviking.ai/en/getting-started/04-setup-for-agent)
- [Server deployment and readiness](https://docs.openviking.ai/en/getting-started/03-quickstart-server)
- [MCP integration and tool reference](https://docs.openviking.ai/en/guides/06-mcp-integration)
- [Source and releases](https://github.com/volcengine/OpenViking)

## 1. Detect and choose deployment

Inspect the active client's MCP entries, exposed OpenViking tools, any existing installation manifest, package/process or Docker container, and the configured health endpoint. The defaults are `http://127.0.0.1:1933/health` and `http://127.0.0.1:1933/mcp`. Remote installations do not need a local Python package.

Reuse an existing healthy endpoint. Preserve existing config, credentials, workspace and unrelated MCP entries. A stopped server is not evidence that its data can be replaced; inspect it before repair or update. Do not start another process against an existing workspace or occupied port.

For a new installation, prefer the published Python package in an isolated environment, including on Windows. Use an existing remote endpoint when supplied; use the official Docker image when Docker deployment is selected. Ask only for missing deployment and model settings, reusing the user's existing choice from `/installtools`.

Collect the configuration path, durable absolute `storage.workspace`, and the provider/model/endpoint/auth settings for both `embedding.dense` and `vlm`. Do not guess model names, dimensions or credentials. Use the official configuration guide for the chosen providers; an LLM account alone does not confirm embedding support. For local models, the official `openviking-server init` wizard can configure supported providers.

Default local root: `~/.openviking` (resolved to an absolute path on the host), containing `ov.conf`, `data/`, `.venv/`, logs and a secret-free `install.manifest.json`. Offer another absolute root when needed. Keep secrets and memory data outside source control; protect config permissions and never print keys. Do not overwrite an existing `ov.conf` with wizard defaults.

## 2. Install and configure the local package

Check the current release's supported Python version and available wheel for this OS/architecture. Prefer prebuilt artifacts; do not add native build toolchains automatically if a wheel is unavailable. Offer a compatible Python environment or the Docker option instead.

For a fresh Windows installation, use the confirmed Python executable and root; the following assumes `python` resolves to that executable:

```powershell
$ovRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.openviking'
$ovVenv = Join-Path $ovRoot '.venv'
New-Item -ItemType Directory -Path $ovRoot -Force | Out-Null
python -m venv "$ovVenv"
if ($LASTEXITCODE -ne 0) { throw 'Failed to create the OpenViking environment' }
$ovPython = Join-Path $ovVenv 'Scripts/python.exe'
& $ovPython -m pip install --upgrade --only-binary=openviking openviking
if ($LASTEXITCODE -ne 0) { throw 'Failed to install OpenViking' }
$ovServer = Join-Path $ovVenv 'Scripts/openviking-server.exe'
$env:OPENVIKING_CONFIG_FILE = Join-Path $ovRoot 'ov.conf'
```

On Linux/macOS, use the equivalent native shell, `.venv/bin/python` and `.venv/bin/openviking-server` paths. Do not recreate an existing environment during detection.

Create UTF-8 JSON `ov.conf` from the confirmed settings or use `openviking-server init` interactively in the selected environment. Include the absolute `storage.workspace` and provider-specific `embedding.dense` / `vlm` settings. Add optional settings only when required by that provider or requested by the user. Preserve any existing configuration through a targeted merge and retain a protected backup before editing it.

Validate using the selected executable and config environment:

```powershell
& $ovServer doctor
if ($LASTEXITCODE -ne 0) { throw 'OpenViking configuration or model checks failed' }
```

Do not claim readiness after installation alone. Resolve missing configuration, authentication or model access before starting the service; report a blocker when a required setting is unavailable.

## 3. Start and check the server

Bind a local package installation explicitly to loopback. For a background helper on Windows, keep its window hidden and capture logs:

```powershell
$ovProcess = Start-Process -FilePath $ovServer `
  -ArgumentList @('--host', '127.0.0.1', '--port', '1933') `
  -WorkingDirectory $ovRoot -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $ovRoot 'server.stdout.log') `
  -RedirectStandardError (Join-Path $ovRoot 'server.stderr.log')
Invoke-RestMethod -Uri 'http://127.0.0.1:1933/health' -TimeoutSec 10
```

The child inherits `OPENVIKING_CONFIG_FILE`. Adapt the port consistently if the selected port is occupied; never terminate an unrelated listener. Poll health for at most two minutes during startup, checking the process and redacted logs on failure. `/health` confirms that the process runs; `doctor` and the memory smoke check below cover configuration and operations.

Record the installed version, Python/executable paths, config/workspace paths, endpoint, launch method and time in `install.manifest.json`, without credentials. Record how to start and stop this exact installation. A background process does not configure startup after reboot: report this honestly and set up an OS service only when requested.

## 4. Register and verify MCP

Merge an entry named `openviking` into the active client's native MCP configuration, following `/installmcp` and `/install-agent-browser` path/merge rules. Preserve every unrelated entry, including Cognee and templates memory.

Canonical fragment for clients accepting `mcpServers`:

```json
{
  "mcpServers": {
    "openviking": {
      "url": "http://127.0.0.1:1933/mcp"
    }
  }
}
```

Add `type: "http"` only when required by that client. Use the native remote schema for OpenCode and the corresponding `[mcp_servers.openviking]` TOML table for Codex. For remote authentication, use a scoped user key via the supported secret/environment mechanism and the server's documented bearer or `X-Api-Key` header; never log it or use an administrative root key for ordinary memory operations.

After the client reload/restart, inspect the live schema: current versions expose `remember` with a `messages` list of `{role, content}`, retrieval via `search` / `find`, and `health`. Read actual names and parameters from the exposed tools before calling them; do not assume a Cognee-style `recall` signature.

Call the health tool, store one harmless uniquely identified test fact, then retrieve that fact. Account for extraction/indexing completion before a bounded retry. If precise cleanup is possible, delete only the isolated test artifact through the exposed deletion tool after checking its returned URI; never delete a shared memory file or directory to remove a test. If the client cannot reload in this session, report configuration complete but MCP operations unverified, with the remaining smoke check.

## Existing remote endpoint

Use the supplied HTTPS MCP URL and its supported authentication. Check `/health` when the deployment exposes it, then register and perform the MCP smoke check. Do not change the remote server, install a local package, or assume the remote service uses the default port. Missing HTTP health access alone is inconclusive; successful MCP health and memory operations can verify a remote endpoint.

## Docker alternative

Use the official `ghcr.io/volcengine/openviking` image, confirming its release and recording the resolved digest. Prepare a dedicated mounted config directory with `ov.conf`; its `storage.workspace` must use a persistent container path such as `/app/.openviking/data`. Mount that host directory to `/app/.openviking`, the image's documented default config location. Do not reuse a host-only workspace path inside the container or silently migrate existing data.

Verify Docker first, then pull the selected image and run one detached container with a stable name, `--restart unless-stopped`, loopback host publication `-p 127.0.0.1:1933:1933`, and the confirmed absolute bind mount. The service must listen on the container interface for port publication; follow the selected image's documented configuration. Preserve any existing container and mounts until a deliberate repair/update is agreed. Run `openviking-server doctor` in the container, inspect redacted logs and `/health`, then register and smoke-test the native `/mcp` endpoint as above. Never treat container startup alone as success.

## Update, disable and removal

- Update only when requested. Back up config and persistent workspace consistently with the installed version's backup procedure, record the existing version/image digest, stop the owned process/container, update it and restart against the same workspace. Read migration requirements before changing versions; rerun configuration, health and MCP checks. Keep the backup for rollback and never downgrade an already migrated workspace blindly.
- Disable: stop only this installation and disable/remove only its `openviking` MCP entry. Preserve the workspace and config.
- Deleting memory is a separate destructive action requiring explicit confirmation naming the exact data path. Uninstallation must not delete memory implicitly.
