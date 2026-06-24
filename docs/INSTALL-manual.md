# Manual install (P1)

The automated `install.sh` lands in P2. Until then, install cc-ledger by hand. Every
step is non-destructive and reversible.

> Prerequisites: `python3` on your PATH, and the Slack MCP already enabled in Claude
> Code (the hook injects instructions; Claude uses the Slack MCP to read/post).

## 1. Place the hook and data files

```sh
mkdir -p ~/.claude/hooks ~/.claude/ledger

# from a clone of this toolkit repo:
cp hooks/ledger_session_start.py ~/.claude/hooks/

# seed your registry + protocol ONLY if you don't already have them
[ -f ~/.claude/ledger/groups.json ] || cp config/groups.example.json ~/.claude/ledger/groups.json
[ -f ~/.claude/ledger/protocol.md ] || cp protocol/template.md        ~/.claude/ledger/protocol.md
```

Then edit `~/.claude/ledger/groups.json` to describe your real groups (channels +
per-project `match` substrings). This file stays machine-local — never commit it.

## 2. Register the SessionStart hook

Add this entry to `~/.claude/settings.json` (merge it into any existing `hooks` object;
omit `matcher` so it fires on startup, resume, clear, and re-arms after compaction):

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "python3 ~/.claude/hooks/ledger_session_start.py" } ] }
    ]
  }
}
```

## 3. Opt a clone in

In a work repo you want on the ledger:

```sh
printf '{ "group": "acme", "project": "api" }\n' > .ledger.json
grep -qxF '.ledger.json' .git/info/exclude || echo '.ledger.json' >> .git/info/exclude
```

(See [marker.md](marker.md). Use your real group/project; `project` is optional.)

## 4. Verify

Start Claude Code in that clone — you should get the rendered ledger protocol naming
your group, channel, project and siblings. In a clone *without* a marker, nothing is
injected. A malformed marker / missing registry / unknown group never blocks the
session (it warns to stderr and continues).

You can also dry-run the hook directly:

```sh
CC_LEDGER_REGISTRY=~/.claude/ledger/groups.json \
CC_LEDGER_PROTOCOL=~/.claude/ledger/protocol.md \
python3 ~/.claude/hooks/ledger_session_start.py
```
