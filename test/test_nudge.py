"""Tests for the optional reinforcement hooks: PR-nudge (PostToolUse/Bash) and the
read-only SubagentStart briefing. Hermetic; assert advisory/non-blocking behaviour."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _util import EXAMPLE_PROTOCOL, EXAMPLE_REGISTRY, make_repo

REPO = Path(__file__).resolve().parent.parent
NUDGE = REPO / "hooks" / "ledger_pr_nudge.py"
SUBAGENT = REPO / "hooks" / "ledger_subagent_start.py"


def run(hook, cwd, stdin="", registry=EXAMPLE_REGISTRY, protocol=EXAMPLE_PROTOCOL):
    env = dict(os.environ)
    env["CC_LEDGER_REGISTRY"] = str(registry)
    env["CC_LEDGER_PROTOCOL"] = str(protocol)
    p = subprocess.run(
        [sys.executable, str(hook)],
        cwd=str(cwd),
        input=stdin,
        env=env,
        capture_output=True,
        text=True,
    )
    return p.returncode, p.stdout, p.stderr


def context_of(stdout, event):
    hso = json.loads(stdout)["hookSpecificOutput"]
    assert hso["hookEventName"] == event, hso
    return hso["additionalContext"]


def bash_event(command):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


class PrNudge(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_nudges_on_gh_pr_create(self):
        repo = make_repo(self.tmp / "r", marker='{"group": "acme", "project": "api"}')
        rc, out, err = run(NUDGE, repo, stdin=bash_event("gh pr create --fill"))
        self.assertEqual(rc, 0, err)
        ctx = context_of(out, "PostToolUse")
        self.assertIn("[cc-ledger]", ctx)
        self.assertIn("PR", ctx)

    def test_nudges_on_git_push(self):
        repo = make_repo(self.tmp / "r", marker='{"group": "acme"}')
        rc, out, err = run(NUDGE, repo, stdin=bash_event("git push -u origin feature"))
        self.assertEqual(rc, 0, err)
        self.assertIn("[cc-ledger]", context_of(out, "PostToolUse"))

    def test_silent_on_unrelated_command(self):
        repo = make_repo(self.tmp / "r", marker='{"group": "acme"}')
        rc, out, err = run(NUDGE, repo, stdin=bash_event("ls -la"))
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_silent_when_not_opted_in(self):
        repo = make_repo(self.tmp / "r")  # no marker
        rc, out, err = run(NUDGE, repo, stdin=bash_event("gh pr create"))
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_never_blocks_on_garbage_stdin(self):
        repo = make_repo(self.tmp / "r", marker='{"group": "acme"}')
        rc, out, err = run(NUDGE, repo, stdin="not json at all")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")


class SubagentBriefing(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_injects_read_only_note(self):
        repo = make_repo(self.tmp / "r", marker='{"group": "acme", "project": "api"}')
        rc, out, err = run(SUBAGENT, repo)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out, "SubagentStart")
        self.assertIn("#acme-ledger", ctx)
        self.assertIn("do NOT post", ctx)

    def test_silent_when_not_opted_in(self):
        repo = make_repo(self.tmp / "r")
        rc, out, err = run(SUBAGENT, repo)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
