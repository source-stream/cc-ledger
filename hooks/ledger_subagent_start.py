#!/usr/bin/env python3
"""cc-ledger SubagentStart hook (OPTIONAL, default off).

Injects a READ-ONLY ledger note when a subagent is spawned in an opted-in clone, so the
subagent is aware of sibling activity but does NOT post — only the main/orchestrator
session posts, which keeps channel noise down. Off by default; enable with
`install.sh --with-subagent`. Never blocks: warns to stderr and exits 0 on any problem.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ledger_common as L  # noqa: E402


def main():
    ctx = L.load_context()
    if not ctx:
        return 0
    note = (
        "[cc-ledger] READ-ONLY ledger note — group %s, project %s. Sibling activity in "
        "%s may affect this work; the orchestrator already read the full briefing. "
        "Factor in anything relevant, but do NOT post to the ledger — only the "
        "main/orchestrator session posts." % (ctx["group_key"], ctx["project"], ctx["channel"])
    )
    L.emit("SubagentStart", note)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        L.warn("unexpected error: %s" % e)
        sys.exit(0)
