#!/usr/bin/env python3
"""Offline Linux installer checks against real Bash/PowerShell entry points."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    pwsh = shutil.which("pwsh")
    check(pwsh, "PowerShell 7 is required")
    with tempfile.TemporaryDirectory(prefix="fork-install-") as work:
        root = Path(work)
        home = root / "isolated home"
        home.mkdir()
        target = root / "project with spaces"
        target.mkdir()
        env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), BASH_ENV=os.devnull, ENV=os.devnull,
                   XDG_CONFIG_HOME=str(home / ".config"),
                   XDG_DATA_HOME=str(home / ".local/share"))
        for key in ("BASESAI_MCP_GLOBAL_ROOT", "MCP_OPERATOR_TOKEN", "MCP_GLOBAL_ROOT"):
            env.pop(key, None)
        write(target / ".dev.env", "USE_EDT=false\nSUBAGENT_MODEL_CODING=sonnet\n"
              "SUBAGENT_MODEL_CODING__OPENCODE=fixture/coder\n"
              "SUBAGENT_MODEL_ANALYSIS__OPENCODE=fixture/reviewer\n")
        configs = {
            ".cursor/mcp.json": ("mcpServers", "1c-code-metadata-mcp"),
            ".mcp.json": ("mcpServers", "1c-code-metadata-mcp"),
            "opencode.json": ("mcp", "onec-code-metadata-mcp"),
            ".qwen/settings.json": ("mcpServers", "1c-code-metadata-mcp"),
            ".kimi-code/mcp.json": ("mcpServers", "1c-code-metadata-mcp"),
            ".kilo/kilo.json": ("mcp", "1c-code-metadata-mcp"),
        }
        connection = {"url": "http://127.0.0.1:9191/custom/mcp",
                      "headers": {"Authorization": "fixture-only"}, "enabled": False}
        for path, (key, server_id) in configs.items():
            write(target / path, json.dumps({key: {server_id: connection,
                  "user-server": {"url": "http://127.0.0.1:9999/mcp"}},
                  "user-setting": "keep"}))
        codex = '[mcp_servers.custom]\nurl = "http://127.0.0.1:9099/mcp"\n\n[features]\nmulti_agent = false\n'
        write(target / ".codex/config.toml", codex)
        tools = "cursor,claude-code,opencode,codex,kimi,kilocode,qwen"
        command = ["bash", str(REPO / "scripts/install.sh"), str(target), "--tools", tools,
                   "--host", "127.0.0.1", "--publish-url", "http://127.0.0.1:1/TestBase/ru/"]
        def run(args):
            result = subprocess.run(args, cwd=root, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            check(result.returncode == 0, result.stdout)
            return result.stdout
        run(command)
        check((target / ".codex/config.toml").read_text() == codex, "Codex settings changed")
        for path, (key, server_id) in configs.items():
            config = json.loads((target / path).read_text())
            check(config[key][server_id] == connection, path + ": existing connection changed")
            check("user-server" in config[key] and config["user-setting"] == "keep", path + ": user keys lost")
        check((target / ".opencode/agent/developer.md").is_file(), "OpenCode adapter did not install")
        check("disallowedTools:" in (target / ".claude/agents/explorer.md").read_text(), "Claude readonly intent lost")
        check("readonly: true" in (target / ".cursor/agents/explorer.md").read_text(), "Cursor readonly intent lost")
        for path in [".codex/skills/openspec-propose/SKILL.md",
                     ".opencode/command/opsx-propose.md"]:
            check((target / path).is_file(), "OpenSpec bundle missing: " + path)
        # Update a previously installer-owned connection without changing its source catalog.
        config_path = target / ".cursor/mcp.json"
        config = json.loads(config_path.read_text())
        managed_id = "1c-syntax-checker-mcp"
        config["mcpServers"][managed_id] = connection
        config_path.write_text(json.dumps(config))
        run(command)  # wrapper chooses update; user edits are preserved
        run([pwsh, "-NoLogo", "-NoProfile", "-File", str(REPO / "install.ps1"), "update",
             "-ProjectRoot", str(target), "-Source", str(REPO), "-NonInteractive",
             "-ForcePaths", ".cursor/mcp.json"])
        check(json.loads(config_path.read_text())["mcpServers"][managed_id] == connection,
              "Forced update replaced configured managed connection")
        manifest_mcp = json.loads((target / ".ai-rules.json").read_text())["files"][".cursor/mcp.json"]
        check(managed_id in manifest_mcp.get("managedServers", []),
              "Changed server lost ownership tracking")
        check(manifest_mcp.get("installedServers", {}).get(managed_id) == connection,
              "Changed server baseline was not refreshed: " + repr(manifest_mcp.get("installedServers", {})))
        check((target / ".codex/config.toml").read_text() == codex, "Codex changed on update")
        # Invalid JSON must survive even an explicit forced regeneration request.
        config_path.write_text("{invalid fixture JSON")
        bad = subprocess.run([pwsh, "-NoProfile", "-File", str(REPO / "install.ps1"), "update",
                              "-ProjectRoot", str(target), "-Source", str(REPO), "-NonInteractive",
                              "-ForcePaths", ".cursor/mcp.json"], cwd=root, env=env, capture_output=True)
        check(bad.returncode != 0 and config_path.read_text() == "{invalid fixture JSON",
              "Invalid client config was overwritten")
        # Removing rules must not delete connections whose endpoints the user replaced.
        # A connection changed after this manifest was written remains user-owned.
        changed_after_update = dict(connection, url="http://127.0.0.1:9292/after-update/mcp")
        config["mcpServers"][managed_id] = changed_after_update
        config_path.write_text(json.dumps(config))
        remove = subprocess.run([pwsh, "-NoProfile", "-File", str(REPO / "install.ps1"),
                                 "remove", "cursor", "-ProjectRoot", str(target),
                                 "-Source", str(REPO), "-NonInteractive"], cwd=root, env=env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        check(remove.returncode == 0, remove.stdout)
        after_remove = json.loads(config_path.read_text())["mcpServers"]
        check(after_remove.get(managed_id) == changed_after_update and "user-server" in after_remove,
              "Removing rules deleted a changed MCP endpoint: " + repr(after_remove))
        # Missing runtime must fail before creating any target files.
        empty = root / "empty project"
        empty.mkdir()
        no_pwsh = root / "no-pwsh"
        no_pwsh.mkdir()
        for binary in ("dirname",):
            (no_pwsh / binary).symlink_to(shutil.which(binary))
        missing_env = dict(env, PATH=str(no_pwsh))
        result = subprocess.run([shutil.which("bash"), str(REPO / "scripts/install.sh"), str(empty)],
                                env=missing_env, capture_output=True)
        check(result.returncode != 0 and not list(empty.iterdir()), "Missing runtime wrote target")
        print("PASS: seven adapters; CLI arguments; OpenSpec; MCP preservation; invalid config; missing runtime")


if __name__ == "__main__":
    main()
