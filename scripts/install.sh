#!/usr/bin/env bash
# Compatibility CLI: both installation entry points use install.ps1.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
repo_dir="$(cd -- "$script_dir/.." && pwd)"
target=""
tools=""
mcp_host=""
publish_url=""

usage() {
    cat <<'EOF'
Usage: install.sh <target-dir> [options]
  --tools <list>       Comma-separated adapter IDs; otherwise auto-detect.
  --host <host>        Default MCP hostname for new connections.
  --publish-url <url>  Default infobase publication URL for new connections.
  --help, -h          Show this help.
Requires PowerShell 7 (pwsh). Existing MCP connections are preserved.
EOF
}

while (($#)); do
    case "$1" in
        --help|-h) usage; exit 0 ;;
        --tools|--host|--publish-url)
            (($# >= 2)) || { echo "Missing value for $1" >&2; exit 2; }
            case "$1" in
                --tools) tools="$2" ;;
                --host) mcp_host="$2" ;;
                --publish-url) publish_url="$2" ;;
            esac
            shift 2 ;;
        --*) echo "Unknown option: $1" >&2; exit 2 ;;
        *) [[ -z "$target" ]] || { echo "Unexpected argument: $1" >&2; exit 2; }
           target="$1"; shift ;;
    esac
done
[[ -n "$target" && -d "$target" ]] || { usage >&2; exit 2; }
command -v pwsh >/dev/null || { echo "PowerShell 7 (pwsh) is required; target unchanged." >&2; exit 1; }
target="$(cd -- "$target" && pwd)"
command_name=init
[[ ! -f "$target/.ai-rules.json" ]] || command_name=update
args=(-NoLogo -NoProfile -File "$repo_dir/install.ps1" "$command_name"
      -ProjectRoot "$target" -Source "$repo_dir" -NonInteractive)
[[ -z "$tools" ]] || args+=(-Tools "$tools")
[[ -z "$mcp_host" ]] || args+=(-McpHost "$mcp_host")
[[ -z "$publish_url" ]] || args+=(-InfobasePublishUrl "$publish_url")
exec pwsh "${args[@]}"
