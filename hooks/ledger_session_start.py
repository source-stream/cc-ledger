#!/usr/bin/env python3
"""cc-ledger SessionStart hook.

Injects a group-aware ledger protocol as `additionalContext` when the current repo is
an opted-in clone (has a `.ledger.json` marker). Pure Python 3 standard library.

Contract (verified against https://code.claude.com/docs/en/hooks):
- On success: print exactly one JSON object to stdout and exit 0:
      {"hookSpecificOutput": {"hookEventName": "SessionStart",
                              "additionalContext": "<rendered protocol>"}}
- On ANY problem (no git, missing/malformed marker, missing/unparseable registry,
  unknown group, missing protocol template): write one `[cc-ledger] ...` line to stderr
  and exit 0. Never block, never crash, never write partial output to stdout.
- `additionalContext` is capped at 10,000 chars by Claude Code; we keep well under.

Registry/protocol locations default to ~/.claude/ledger/{groups.json,protocol.md} and
can be overridden (mainly for tests) with the env vars CC_LEDGER_REGISTRY and
CC_LEDGER_PROTOCOL.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

MAX_CONTEXT = 9500  # stay comfortably under Claude Code's 10k cap


def warn(msg):
    sys.stderr.write("[cc-ledger] %s\n" % msg)


def sh(args):
    """Run a git command, returning stripped stdout or '' on any failure."""
    try:
        out = subprocess.check_output(
            args, text=True, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.strip()
    except Exception:
        return ""


def registry_path():
    env = os.environ.get("CC_LEDGER_REGISTRY")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "ledger" / "groups.json"


def protocol_path():
    env = os.environ.get("CC_LEDGER_PROTOCOL")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "ledger" / "protocol.md"


def infer_project(projects, remote, marker_project):
    """Resolve the project name. Explicit marker wins; else match the git remote against
    each project's `match` substrings. 0 or >1 matches -> 'unknown'."""
    if marker_project:
        return marker_project
    if not remote:
        return "unknown"
    matched = [
        name
        for name, p in projects.items()
        if any(s and s in remote for s in p.get("match", []))
    ]
    return matched[0] if len(matched) == 1 else "unknown"


def main():
    root = sh(["git", "rev-parse", "--show-toplevel"]) or os.getcwd()
    marker = Path(root) / ".ledger.json"
    if not marker.is_file():
        return 0  # not an opted-in clone: silent

    try:
        m = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(m, dict):
            raise ValueError("marker is not a JSON object")
    except Exception as e:
        warn("invalid .ledger.json: %s" % e)
        return 0

    group_key = m.get("group")
    if not group_key:
        warn(".ledger.json missing 'group'")
        return 0

    reg_path = registry_path()
    try:
        registry = json.loads(reg_path.read_text(encoding="utf-8"))
    except Exception:
        warn("no readable registry at %s" % reg_path)
        return 0

    group = registry.get("groups", {}).get(group_key)
    if not group:
        warn("group '%s' not in registry; skipping" % group_key)
        return 0

    projects = group.get("projects", {})
    remote = sh(["git", "-C", root, "remote", "get-url", "origin"])
    branch = sh(["git", "-C", root, "rev-parse", "--abbrev-ref", "HEAD"]) or "?"

    project = infer_project(projects, remote, m.get("project"))
    role = projects.get(project, {}).get("role", "unspecified")

    siblings = [
        "- %s: %s" % (n, p.get("role", "")) for n, p in projects.items() if n != project
    ]
    siblings_text = (
        "\n".join(siblings) if siblings else "(this group has no other projects)"
    )

    try:
        tmpl = protocol_path().read_text(encoding="utf-8")
    except Exception:
        warn("no readable protocol template at %s" % protocol_path())
        return 0

    rendered = (
        tmpl.replace("{{GROUP}}", group_key)
        .replace("{{CHANNEL}}", group.get("channel", "#unknown"))
        .replace("{{PROJECT}}", project)
        .replace("{{ROLE}}", role)
        .replace("{{BRANCH}}", branch)
        .replace("{{SIBLINGS}}", siblings_text)
    )

    if len(rendered) > MAX_CONTEXT:
        rendered = rendered[:MAX_CONTEXT] + "\n[cc-ledger] (protocol truncated)"

    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": rendered,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # absolute backstop: never crash a session
        warn("unexpected error: %s" % e)
        sys.exit(0)
