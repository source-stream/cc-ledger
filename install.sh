#!/usr/bin/env bash
# cc-ledger installer — lays the toolkit into ~/.claude/. Idempotent and
# non-destructive: re-running changes nothing, never overwrites your registry/protocol,
# and merges the hook entry structurally (see lib/settings_merge.py).
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_HOOKS="$HOME/.claude/hooks"
DEST_LEDGER="$HOME/.claude/ledger"
SETTINGS="$HOME/.claude/settings.json"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[cc-ledger] error: python3 is required but was not found on PATH." >&2
  exit 1
fi

mkdir -p "$DEST_HOOKS" "$DEST_LEDGER"

# Hooks
cp "$SCRIPT_DIR/hooks/ledger_session_start.py" "$DEST_HOOKS/"

# Seed registry + protocol ONLY if absent (never clobber a real registry).
if [ ! -f "$DEST_LEDGER/groups.json" ]; then
  cp "$SCRIPT_DIR/config/groups.example.json" "$DEST_LEDGER/groups.json"
  echo "[cc-ledger] seeded $DEST_LEDGER/groups.json (edit it for your real groups)"
else
  echo "[cc-ledger] kept existing $DEST_LEDGER/groups.json"
fi
if [ ! -f "$DEST_LEDGER/protocol.md" ]; then
  cp "$SCRIPT_DIR/protocol/template.md" "$DEST_LEDGER/protocol.md"
  echo "[cc-ledger] seeded $DEST_LEDGER/protocol.md"
else
  echo "[cc-ledger] kept existing $DEST_LEDGER/protocol.md"
fi

# Structural, backed-up, idempotent settings merge.
python3 "$SCRIPT_DIR/lib/settings_merge.py" add \
  --settings "$SETTINGS" \
  --event SessionStart \
  --command "python3 ~/.claude/hooks/ledger_session_start.py"

cat <<EOF

[cc-ledger] install complete.
Next steps:
  1. Edit $DEST_LEDGER/groups.json to describe your real groups (channels + match).
  2. In a work repo you want on the ledger, opt it in:
       $SCRIPT_DIR/bin/ledger-enable <group> [project]
  3. Make sure the Slack MCP is enabled in Claude Code.
EOF
