#!/bin/sh
# support-guard.sh - opt-in gate of the experimental support-guard PreToolUse hook.
#
# Registered by hooks.json for every Edit / Write / MultiEdit, so it has to cost nothing
# for a project that did not opt in: without SUPPORT_GUARD_HOOK=on in the nearest .dev.env
# it exits at once and never needs Node. With the opt-in it hands stdin to
# support-guard.mjs; a missing node fails open with one notice (systemMessage).
# The .dev.env lookup follows DevEnv.ps1: nearest file walking up, at most 20 levels,
# first KEY= line wins, value trimmed, one pair of matching quotes removed.

DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)

find_dev_env() {
  d=$1
  i=0
  while [ "$i" -lt 20 ] && [ -n "$d" ]; do
    if [ -f "$d/.dev.env" ]; then
      printf '%s\n' "$d/.dev.env"
      return 0
    fi
    p=$(dirname -- "$d")
    [ "$p" = "$d" ] && break
    d=$p
    i=$((i + 1))
  done
  return 1
}

# CLAUDE_PROJECT_DIR is a Windows path under Git Bash; dirname walks forward slashes only.
start=$(printf '%s' "${CLAUDE_PROJECT_DIR:-$PWD}" | tr '\\' '/')
env_file=$(find_dev_env "$start") || exit 0

bom=$(printf '\357\273\277')
value=$(LC_ALL=C sed -e "1s/^$bom//" -e 's/\r$//' "$env_file" 2>/dev/null |
  grep -E '^[[:space:]]*SUPPORT_GUARD_HOOK[[:space:]]*=' | head -n 1 |
  sed -e 's/^[^=]*=//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
      -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/" -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' |
  tr 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' 'abcdefghijklmnopqrstuvwxyz')

[ "$value" = "on" ] || exit 0

if ! command -v node >/dev/null 2>&1; then
  printf '%s\n' '{"systemMessage":"[support-guard] SUPPORT_GUARD_HOOK=on, but node is not on PATH: hook skipped, edit allowed (needs Node 18+)."}'
  exit 0
fi

exec node "$DIR/support-guard.mjs"
