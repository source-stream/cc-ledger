"""Shared helpers for the cc-ledger hooks. Python 3 standard library only.

Kept deliberately small and side-effect-free so each hook stays robust and never blocks
a session. Hooks add this file's directory to sys.path and `import _ledger_common`.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

MAX_CONTEXT = 9500  # stay comfortably under Claude Code's 10k additionalContext cap


def warn(msg):
    sys.stderr.write("[cc-ledger] %s\n" % msg)


def sh(args):
    """Run a command, returning stripped stdout or '' on any failure."""
    try:
        return subprocess.check_output(
            args, text=True, stderr=subprocess.DEVNULL, timeout=5
        ).strip()
    except Exception:
        return ""


def repo_root():
    return sh(["git", "rev-parse", "--show-toplevel"]) or os.getcwd()


def marker_path(root=None):
    return Path(root or repo_root()) / ".ledger.json"


def is_opted_in():
    return marker_path().is_file()


def registry_path():
    return Path(
        os.environ.get("CC_LEDGER_REGISTRY")
        or (Path.home() / ".claude" / "ledger" / "groups.json")
    )


def protocol_path():
    return Path(
        os.environ.get("CC_LEDGER_PROTOCOL")
        or (Path.home() / ".claude" / "ledger" / "protocol.md")
    )


def infer_project(projects, remote, marker_project):
    """Explicit marker wins; else match the git remote against each project's `match`
    substrings. 0 or >1 matches -> 'unknown'."""
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


def load_context():
    """Resolve the current clone's ledger context.

    Returns a dict on success; None if the clone is not opted in (caller should be
    silent); False if something was wrong (a warning was already written to stderr).
    Callers exit 0 in every case.
    """
    root = repo_root()
    if not (Path(root) / ".ledger.json").is_file():
        return None

    try:
        m = json.loads((Path(root) / ".ledger.json").read_text(encoding="utf-8"))
        if not isinstance(m, dict):
            raise ValueError("marker is not a JSON object")
    except Exception as e:
        warn("invalid .ledger.json: %s" % e)
        return False

    group_key = m.get("group")
    if not group_key:
        warn(".ledger.json missing 'group'")
        return False

    try:
        registry = json.loads(registry_path().read_text(encoding="utf-8"))
    except Exception:
        warn("no readable registry at %s" % registry_path())
        return False

    group = registry.get("groups", {}).get(group_key)
    if not group:
        warn("group '%s' not in registry; skipping" % group_key)
        return False

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
    return {
        "root": root,
        "group_key": group_key,
        "channel": group.get("channel", "#unknown"),
        "project": project,
        "role": role,
        "branch": branch,
        "siblings_text": siblings_text,
    }


def emit(event, context_text):
    """Print the hook JSON for `event` with `additionalContext` (capped)."""
    if len(context_text) > MAX_CONTEXT:
        context_text = context_text[:MAX_CONTEXT] + "\n[cc-ledger] (truncated)"
    sys.stdout.write(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": context_text,
                }
            }
        )
    )
