# Install

> Prerequisites: `python3` on your PATH, and the Slack MCP enabled in Claude Code.

## Automated install

From a clone of this toolkit repo:

```sh
./install.sh
```

This is **idempotent and non-destructive**. It:

- copies `hooks/ledger_session_start.py` → `~/.claude/hooks/`;
- creates `~/.claude/ledger/` and seeds `groups.json` + `protocol.md` **only if absent**
  (it never overwrites a registry/protocol you've already edited);
- merges the `SessionStart` hook entry into `~/.claude/settings.json` with a **structural
  JSON merge** that backs up the file first, preserves all unrelated settings/hooks, and
  never duplicates the entry on re-run.

Re-running `./install.sh` changes nothing.

## Enable a clone

In a work repo you want on the ledger:

```sh
/path/to/cc-ledger/bin/ledger-enable <group> [project]
```

This writes a `.ledger.json` marker at the repo root and excludes it via
`.git/info/exclude` (never `.gitignore`), so `git status` stays clean and the marker is
never shared. Reverse it with `bin/ledger-disable`. See [marker.md](marker.md).

## Uninstall

```sh
./uninstall.sh
```

Removes the hook entry (structural merge) and the hook file, and **leaves
`~/.claude/ledger/` intact** so your real registry/protocol survive a reinstall. Delete
that directory manually for a full wipe.

## Manual install

If you prefer to install by hand (or are on a system without the shell scripts), follow
[INSTALL-manual.md](INSTALL-manual.md).
