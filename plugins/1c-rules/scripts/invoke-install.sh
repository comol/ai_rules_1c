#!/bin/sh
DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
CMD=${1:-ensure}
TOOL=${2:-auto}
if [ "$#" -ge 1 ]; then shift; fi
if [ "$#" -ge 1 ]; then shift; fi
if command -v pwsh >/dev/null 2>&1; then
  exec pwsh -NoProfile -File "$DIR/invoke-install.ps1" -Action "$CMD" -Tool "$TOOL" "$@"
fi
if command -v powershell.exe >/dev/null 2>&1; then
  exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$DIR/invoke-install.ps1" -Action "$CMD" -Tool "$TOOL" "$@"
fi
echo "1c-rules installer needs PowerShell 5.1+ or pwsh" >&2
exit 127
