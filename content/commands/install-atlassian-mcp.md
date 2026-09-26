---
description: Install and configure mcp-atlassian for Jira and Confluence in the active AI client
userOnly: true
---

# /install-atlassian-mcp — install Jira and Confluence MCP

Installs [mcp-atlassian](https://github.com/sooperset/mcp-atlassian) for Jira, Confluence, or both. It is optional and independent of the purchased 1C MCP bundle.

Use upstream [installation](https://mcp-atlassian.soomiles.com/docs/installation), [authentication](https://mcp-atlassian.soomiles.com/docs/authentication), and [configuration](https://mcp-atlassian.soomiles.com/docs/configuration) documentation. Recheck the chosen release's options before installing; the default is `uvx` with client-managed stdio. On Windows, use the `powershell-windows` skill.

## Steps

### 1. Detect and collect missing settings

Inspect the active client's MCP configuration and exposed tools for an existing Atlassian connection, including entries with a custom name. Reuse a working connection; do not create a duplicate or replace another account. Configuration presence alone does not prove authentication or tool availability. During detection, do not run `uvx mcp-atlassian --help`: it can download and execute the package.

Reuse choices already made in `/installtools`. Ask one compact question only for missing information:

- Services: Jira, Confluence, or both; actual base URL and Cloud or Server/Data Center authentication for each selected service. Preserve deployment context paths; Confluence Cloud normally uses `/wiki`.
- Authentication source: an existing protected env file, or credentials the user will enter locally. Do not ask for tokens in chat.
- Access: read-only by default for a new connection; enable write tools when requested. Preserve the access mode of an existing connection.

Only configure selected services. Do not infer a Confluence URL from a Jira URL, reuse a token across services without confirmation, or change unrelated `.dev.env` settings.

### 2. Prepare the runtime

Check `uv --version` and `uvx --version`. If missing, install `uv` using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/) for the host OS. Windows:

```powershell
Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
uv --version
if ($LASTEXITCODE -ne 0) { throw 'uv installation failed' }
uvx --version
if ($LASTEXITCODE -ne 0) { throw 'uvx is unavailable' }
```

Resolve the executable from the actual host (`Get-Command uvx` on Windows, `command -v uvx` on Linux/macOS). Prefer its absolute path when the AI client does not inherit the shell's `PATH`.

After installation has been selected, download the package and check its CLI:

```powershell
uvx mcp-atlassian --help
if ($LASTEXITCODE -ne 0) { throw 'mcp-atlassian package check failed' }
```

On Linux/macOS, use the same invocation and check its exit status in the native shell. Confirm `--env-file` and `--transport` in the installed CLI help. This check does not authenticate to Atlassian. Do not leave a standalone server running: the MCP client owns its process.

If the user selects Docker, use the upstream image `ghcr.io/sooperset/mcp-atlassian:latest` (or their requested release tag). Check `docker version`, pull that image, and stop this installer on failure. Skip `uv` in this branch. Register a stdio container with the argument array:

```json
["run", "--rm", "-i", "--env-file", "/absolute/path/mcp-atlassian.env", "ghcr.io/sooperset/mcp-atlassian:latest", "--transport", "stdio"]
```

Use the actual host env-file path and selected image. Do not add a TTY (`-t`), port publishing, or a background service to this stdio setup.

### 3. Store credentials outside the repository

Reuse the selected protected env file, or create a UTF-8 `mcp-atlassian.env` under the user's private configuration directory outside the repository. Use the host's normal permissions to restrict access to the current user (Windows ACL or Unix mode `600`). Preserve an existing file through a targeted edit; never overwrite it with a sample.

Populate only the selected service's variables:

- Jira Cloud: `JIRA_URL`, `JIRA_USERNAME` (account email), `JIRA_API_TOKEN`.
- Confluence Cloud: `CONFLUENCE_URL`, `CONFLUENCE_USERNAME` (account email), `CONFLUENCE_API_TOKEN`.
- Jira Server/Data Center with PAT: `JIRA_URL`, `JIRA_PERSONAL_TOKEN`.
- Confluence Server/Data Center with PAT: `CONFLUENCE_URL`, `CONFLUENCE_PERSONAL_TOKEN`.

Cloud API tokens are created in [Atlassian account settings](https://id.atlassian.com/manage-profile/security/api-tokens); Server/Data Center PATs are created on the corresponding instance. For scoped Cloud tokens, OAuth, or mTLS, follow the selected release's authentication procedure and URL requirements rather than substituting them into a different authentication mode.

Set `READ_ONLY_MODE=true` for a new read-only connection, or `false` for requested write access. Keep TLS verification enabled. Add `JIRA_PROJECTS_FILTER` / `CONFLUENCE_SPACES_FILTER` only when the user provides the intended project or space keys.

Do not echo credentials, pass token values on command lines, or write them into tracked files, examples, logs, or memory. If the user must fill in credentials locally, complete the independent package preparation and report configuration as pending; do not register an enabled connection with sample values. Inspect only which required variables are present, without displaying their values.

### 4. Register in the active client

Resolve the active client's config path and native schema using `content/commands/installmcp.md` Step 7 and the existing configuration. Merge only the `mcp-atlassian` entry, retaining other servers and settings. If an existing Atlassian entry uses another name, update that entry instead. Respect an explicitly disabled entry; installation is not permission to silently re-enable it.

For clients using `mcpServers`, the stdio entry has this shape:

```json
{
  "mcpServers": {
    "mcp-atlassian": {
      "command": "uvx",
      "args": ["mcp-atlassian", "--env-file", "/absolute/path/mcp-atlassian.env", "--transport", "stdio"]
    }
  }
}
```

Substitute the resolved executable and real absolute env-file path before saving. Keep every argument as a separate array item, including paths containing spaces; escape Windows paths for the target format. In the Docker branch, use `command: "docker"` and the argument array from Step 2; Docker reads the host env file, so do not also pass that path as a server-side `--env-file` argument.

Convert the same executable and arguments to the client's native schema: Codex uses a `[mcp_servers.mcp-atlassian]` TOML table; OpenCode uses `mcp.mcp-atlassian` with `type: "local"`, a `command` array beginning with the executable, and `enabled: true` for a new entry. Do not paste a `mcpServers` wrapper into clients with a different schema. If the client has no supported MCP integration, report that limitation instead of inventing a config path.

Validate the saved JSON/JSONC/TOML using a compatible parser. Keep the connection local and client-managed; remote HTTP deployment is a separate, explicitly requested setup using upstream transport/authentication documentation.

### 5. Verify and report

1. Confirm package preparation (CLI help, or Docker image pull) and config parsing succeeded.
2. Reload MCP or request one client restart. When invoked through `/installtools`, defer the shared restart to its final step.
3. When tools become available, confirm discovery and perform one bounded read-only request per configured service using the exposed schema: `jira_search` with a narrow JQL query, and/or `confluence_search` with a narrow CQL query. An authenticated empty result is valid; an authorization, network, or tool error is not a successful check.
4. Do not create issues, pages, comments, or transitions as an installation test. Distinguish `configured; awaiting restart/credentials` from a verified connection.

Report briefly in Russian: selected runtime, configured services and access mode, modified config and env-file paths (no secrets), actual verification results, and any remaining user action. On failure, retain unrelated configuration and report the failed stage without disabling TLS or changing authentication modes automatically.
