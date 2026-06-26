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
ARCH_MAX = 2500  # dedicated soft cap for the architecture-map block (kept terse)


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


def _project_desc(p):
    """Terse responsibility line for a project: `summary (kw, kw)` if a
    `responsibility` object is present, else the plain `role`."""
    resp = p.get("responsibility")
    if isinstance(resp, dict) and resp.get("summary"):
        desc = str(resp["summary"])
        kws = resp.get("keywords")
        if isinstance(kws, list) and kws:
            desc += " (%s)" % ", ".join(str(k) for k in kws)
        return desc
    return p.get("role", "") or "unspecified"


def render_archmap(projects, current):
    """One terse line per project (current marked), so a session routes new work to
    the repo that owns it. Sub-areas are listed by name only. Truncates to ARCH_MAX
    chars with an explicit `+N more` line so the map never crowds out the protocol."""
    items = list(projects.items())
    lines = []
    used = 0
    for i, (name, p) in enumerate(items):
        desc = _project_desc(p)
        areas = p.get("areas")
        if isinstance(areas, dict) and areas:
            desc += " · areas: %s" % ", ".join(areas.keys())
        marker = " ←you are here" if name == current else ""
        line = "- %s%s — %s" % (name, marker, desc)
        if lines and used + len(line) + 1 > ARCH_MAX:
            lines.append("… +%d more projects (see registry)" % (len(items) - i))
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines) if lines else "(no projects in this group)"


def render_own_areas(projects, current):
    """If the current project is a monorepo with `areas`, render a compact detail
    block (`name=desc · name=desc`) so the change lands in the right sub-area.
    Empty string otherwise."""
    areas = projects.get(current, {}).get("areas")
    if not isinstance(areas, dict) or not areas:
        return ""
    pairs = " · ".join("%s=%s" % (k, v) for k, v in areas.items())
    return "THIS REPO'S AREAS — place the change in the right sub-area:\n" + pairs


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
        "archmap_text": render_archmap(projects, project),
        "own_areas_text": render_own_areas(projects, project),
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
