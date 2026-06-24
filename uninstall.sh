#!/usr/bin/env bash
# cc-ledger uninstaller — removes the hook entry and hook file. Leaves your registry and
# protocol (~/.claude/ledger/) intact so a reinstall keeps your real config.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_HOOKS="$HOME/.claude/hooks"
DEST_LEDGER="$HOME/.claude/ledger"
SETTINGS="$HOME/.claude/settings.json"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[cc-ledger] error: python3 is required but was not found on PATH." >&2
  exit 1
fi

python3 "$SCRIPT_DIR/lib/settings_merge.py" remove \
  --settings "$SETTINGS" \
  --event SessionStart \
  --command "python3 ~/.claude/hooks/ledger_session_start.py"

rm -f "$DEST_HOOKS/ledger_session_start.py"

echo "[cc-ledger] removed the SessionStart hook entry and hook file."
echo "[cc-ledger] left $DEST_LEDGER intact (your registry + protocol). Delete it manually if you want a full wipe."
