#!/usr/bin/env python3
"""cc-ledger PR-nudge hook (PostToolUse, matcher `Bash`).

Milestone posting is model-driven and drifts over long sessions; the PR event is the one
most worth guaranteeing. After a Bash tool call, if the command raised/updated a PR
(`gh pr create`) or pushed (`git push`), inject an advisory reminder to post the PR
milestone. Advisory only — it NEVER blocks (the tool has already run). Only nudges in
opted-in clones, to keep the channel quiet elsewhere.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ledger_common as L  # noqa: E402


def main():
    if not L.is_opted_in():
        return 0  # not an opted-in clone: stay quiet

    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0

    tool_input = data.get("tool_input")
    cmd = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(cmd, str) or not cmd:
        return 0

    raised_pr = "gh pr create" in cmd
    pushed = bool(re.search(r"\bgit\s+push\b", cmd))
    if not (raised_pr or pushed):
        return 0

    what = "raised/updated a pull request" if raised_pr else "pushed a branch"
    note = (
        "[cc-ledger] That Bash command %s. If it raised or updated a PR, post a PR "
        "milestone to your ledger channel now (and DONE when it merges), per the ledger "
        "protocol — one concise line. Skip if not ledger-worthy." % what
    )
    L.emit("PostToolUse", note)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # advisory hook: never interfere with the session
        L.warn("unexpected error: %s" % e)
        sys.exit(0)
