#!/usr/bin/env bash
# cc-ledger installer — lays the toolkit into ~/.claude/. Idempotent and
# non-destructive: re-running changes nothing, never overwrites your registry/protocol,
# and merges the hook entry structurally (see lib/settings_merge.py).
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_HOOKS="$HOME/.claude/hooks"
DEST_LEDGER="$HOME/.claude/ledger"
DEST_SKILL="$HOME/.claude/skills/ledger-init"
SETTINGS="$HOME/.claude/settings.json"

# Optional reinforcement hooks (off by default).
WITH_PR_NUDGE=0
WITH_SUBAGENT=0
for arg in "$@"; do
  case "$arg" in
    --with-pr-nudge) WITH_PR_NUDGE=1 ;;
    --with-subagent) WITH_SUBAGENT=1 ;;
    *) echo "[cc-ledger] unknown option: $arg" >&2; exit 2 ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "[cc-ledger] error: python3 is required but was not found on PATH." >&2
  exit 1
fi

mkdir -p "$DEST_HOOKS" "$DEST_LEDGER" "$DEST_SKILL"

# Hooks (copy all; only registered ones run).
cp "$SCRIPT_DIR"/hooks/*.py "$DEST_HOOKS/"

# Setup wizard skill (/ledger-init) + its bundled helper, co-located so SKILL.md can
# call it via ${CLAUDE_SKILL_DIR}/ledger-init.
cp "$SCRIPT_DIR/skills/ledger-init/SKILL.md" "$DEST_SKILL/"
cp "$SCRIPT_DIR/bin/ledger-init" "$DEST_SKILL/"
chmod +x "$DEST_SKILL/ledger-init" 2>/dev/null || true

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

if [ "$WITH_PR_NUDGE" -eq 1 ]; then
  python3 "$SCRIPT_DIR/lib/settings_merge.py" add \
    --settings "$SETTINGS" \
    --event PostToolUse \
    --matcher Bash \
    --command "python3 ~/.claude/hooks/ledger_pr_nudge.py"
  echo "[cc-ledger] enabled PR-nudge (PostToolUse/Bash)"
fi

if [ "$WITH_SUBAGENT" -eq 1 ]; then
  python3 "$SCRIPT_DIR/lib/settings_merge.py" add \
    --settings "$SETTINGS" \
    --event SubagentStart \
    --command "python3 ~/.claude/hooks/ledger_subagent_start.py"
  echo "[cc-ledger] enabled SubagentStart read-only briefing"
fi

cat <<EOF

[cc-ledger] install complete.
Optional reinforcement (re-run with these flags to enable; both off by default):
  --with-pr-nudge   remind to post the PR milestone after 'gh pr create' / 'git push'
  --with-subagent   inject a read-only ledger note when subagents are spawned
Next steps:
  1. In a work repo you want on the ledger, run the guided setup from inside Claude Code:
       /ledger-init
     It detects state, discovers sibling repos, writes the registry + marker, and shows a
     dry run of what future sessions will load. (Manual path: edit $DEST_LEDGER/groups.json
     and run $SCRIPT_DIR/bin/ledger-enable <group> [project].)
  2. Make sure the Slack MCP is enabled in Claude Code.
EOF
