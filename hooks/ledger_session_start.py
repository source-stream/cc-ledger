#!/usr/bin/env python3
"""cc-ledger SessionStart hook.

In an opted-in clone (one with a `.ledger.json` marker), renders the protocol template
and injects it as `additionalContext`. Pure Python 3 standard library. Never blocks:
any problem warns to stderr and exits 0; on success stdout is exactly one JSON object.

Output schema verified against https://code.claude.com/docs/en/hooks
(SessionStart `hookSpecificOutput`/`additionalContext`, 10k cap, cannot block).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ledger_common as L  # noqa: E402


def main():
    ctx = L.load_context()
    if not ctx:  # None = not opted in, False = problem already warned
        return 0
    try:
        tmpl = L.protocol_path().read_text(encoding="utf-8")
    except Exception:
        L.warn("no readable protocol template at %s" % L.protocol_path())
        return 0
    rendered = (
        tmpl.replace("{{GROUP}}", ctx["group_key"])
        .replace("{{CHANNEL}}", ctx["channel"])
        .replace("{{PROJECT}}", ctx["project"])
        .replace("{{ROLE}}", ctx["role"])
        .replace("{{BRANCH}}", ctx["branch"])
        .replace("{{ARCHMAP}}", ctx["archmap_text"])
        .replace("{{OWN_AREAS}}", ctx["own_areas_text"])
        .replace("{{SIBLINGS}}", ctx["siblings_text"])
    )
    L.emit("SessionStart", rendered)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # absolute backstop: never crash a session
        L.warn("unexpected error: %s" % e)
        sys.exit(0)
