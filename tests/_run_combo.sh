#!/bin/bash
# tests/_run_combo.sh — thin wrapper to run combo_smoke.sh without
# PowerShell->bash quoting/env-propagation issues on Windows.
# Usage: bash tests/_run_combo.sh <site> <expected...> -- <absent...>
set -e
SITE="$1"; shift
EXPECTED=""
ABSENT=""
SEEN_DDASH=0
for a in "$@"; do
  if [ "$a" = "--" ]; then SEEN_DDASH=1; continue; fi
  if [ "$SEEN_DDASH" = "1" ]; then ABSENT="$ABSENT $a"; else EXPECTED="$EXPECTED $a"; fi
done
export COMBO_SMOKE_SITE="$SITE"
export COMBO_SMOKE_EXPECTED="$(echo $EXPECTED)"
export COMBO_SMOKE_ABSENT="$(echo $ABSENT)"
exec bash tests/combo_smoke.sh