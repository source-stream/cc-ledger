#!/usr/bin/env python3
"""Safe, structural merge of Claude Code hook entries into ~/.claude/settings.json.

This is the highest-risk part of cc-ledger: it edits the user's real settings. It NEVER
string-concatenates JSON, ALWAYS backs up before writing, is idempotent (re-running adds
nothing), and preserves every unrelated key/hook exactly.

Library use:
    import settings_merge as sm
    settings = sm.load(path)
    changed = sm.add_command_hook(settings, "SessionStart",
                                  "python3 ~/.claude/hooks/ledger_session_start.py")
    if changed:
        sm.save(path, settings)            # writes a timestamped .bak first

CLI use (called by install.sh / uninstall.sh):
    python3 settings_merge.py add    --settings PATH --event SessionStart --command CMD [--matcher M]
    python3 settings_merge.py remove --settings PATH --event SessionStart --command CMD
Exit code 0 on success (whether or not a change was needed); 1 on hard error.
"""
import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path


def load(path):
    """Return the parsed settings object, or {} if the file is absent/empty."""
    p = Path(path)
    if not p.is_file():
        return {}
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("settings.json root is not a JSON object")
    return data


def _groups_for(settings, event):
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("settings 'hooks' is not an object")
    return hooks.setdefault(event, [])


def _has_command(group, command):
    return any(
        isinstance(h, dict) and h.get("command") == command
        for h in group.get("hooks", [])
    )


def add_command_hook(settings, event, command, matcher=None):
    """Ensure a command hook exists for `event` (optionally scoped to `matcher`).
    Returns True if the settings changed, False if it was already present."""
    groups = _groups_for(settings, event)

    # Already present anywhere for this event+matcher? -> no-op (idempotent).
    for group in groups:
        if not isinstance(group, dict):
            continue
        if group.get("matcher") == matcher and _has_command(group, command):
            return False

    # Reuse an existing group with the same matcher; otherwise create one.
    target = None
    for group in groups:
        if isinstance(group, dict) and group.get("matcher") == matcher:
            target = group
            break
    if target is None:
        target = {} if matcher is None else {"matcher": matcher}
        groups.append(target)
    target.setdefault("hooks", []).append({"type": "command", "command": command})
    return True


def remove_command_hook(settings, event, command):
    """Remove every command hook matching `command` under `event`. Prune empty groups
    and the empty event. Returns True if anything changed."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict) or event not in hooks:
        return False
    changed = False
    new_groups = []
    for group in hooks[event]:
        if not isinstance(group, dict):
            new_groups.append(group)
            continue
        kept = [h for h in group.get("hooks", []) if h.get("command") != command]
        if len(kept) != len(group.get("hooks", [])):
            changed = True
        if kept:
            group["hooks"] = kept
            new_groups.append(group)
        elif "hooks" not in group:
            new_groups.append(group)
    if new_groups:
        hooks[event] = new_groups
    else:
        del hooks[event]
        changed = True
    if not hooks:
        del settings["hooks"]
    return changed


def save(path, settings, backup=True):
    """Write settings as pretty JSON, backing up any existing file first."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if backup and p.is_file():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(p, p.with_suffix(p.suffix + ".bak." + stamp))
    p.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def _cli(argv=None):
    ap = argparse.ArgumentParser(description="Merge hook entries into settings.json")
    ap.add_argument("action", choices=["add", "remove"])
    ap.add_argument("--settings", required=True)
    ap.add_argument("--event", required=True)
    ap.add_argument("--command", required=True)
    ap.add_argument("--matcher", default=None)
    args = ap.parse_args(argv)
    try:
        settings = load(args.settings)
        if args.action == "add":
            changed = add_command_hook(
                settings, args.event, args.command, args.matcher
            )
        else:
            changed = remove_command_hook(settings, args.event, args.command)
        if changed:
            save(args.settings, settings)
            print("[cc-ledger] settings.json updated (%s %s)" % (args.action, args.event))
        else:
            print("[cc-ledger] settings.json already up to date; no change")
        return 0
    except Exception as e:
        sys.stderr.write("[cc-ledger] settings merge failed: %s\n" % e)
        return 1


if __name__ == "__main__":
    sys.exit(_cli())
