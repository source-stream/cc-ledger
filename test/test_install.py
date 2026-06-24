"""Tests for the settings-merge helper and install.sh (criteria 1, 5).

The merge logic (the risky part) is tested in pure Python on every OS. The install.sh
integration test runs a real shell and is skipped on Windows, where bash/$HOME path
semantics differ from the supported macOS/Linux install target.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))
import settings_merge as sm  # noqa: E402

CMD = "python3 ~/.claude/hooks/ledger_session_start.py"


class MergeUnit(unittest.TestCase):
    def test_add_is_idempotent(self):
        s = {}
        self.assertTrue(sm.add_command_hook(s, "SessionStart", CMD))
        self.assertFalse(sm.add_command_hook(s, "SessionStart", CMD))  # criterion 5
        groups = s["hooks"]["SessionStart"]
        cmds = [h["command"] for g in groups for h in g["hooks"]]
        self.assertEqual(cmds.count(CMD), 1)

    def test_preserves_unrelated_config(self):
        s = {
            "model": "claude-opus-4-8",
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "echo other"}]}
                ]
            },
        }
        self.assertTrue(sm.add_command_hook(s, "SessionStart", CMD))
        self.assertEqual(s["model"], "claude-opus-4-8")  # unrelated key survives
        cmds = [h["command"] for g in s["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertIn("echo other", cmds)  # unrelated hook survives
        self.assertIn(CMD, cmds)

    def test_matcher_scoped_hook_idempotent(self):
        s = {}
        self.assertTrue(sm.add_command_hook(s, "PostToolUse", CMD, matcher="Bash"))
        self.assertFalse(sm.add_command_hook(s, "PostToolUse", CMD, matcher="Bash"))
        group = s["hooks"]["PostToolUse"][0]
        self.assertEqual(group["matcher"], "Bash")

    def test_remove_round_trip(self):
        s = {}
        sm.add_command_hook(s, "SessionStart", CMD)
        self.assertTrue(sm.remove_command_hook(s, "SessionStart", CMD))
        self.assertNotIn("hooks", s)  # pruned empty event + empty hooks
        self.assertFalse(sm.remove_command_hook(s, "SessionStart", CMD))

    def test_save_creates_backup(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text('{"model":"x"}', encoding="utf-8")
            s = sm.load(p)
            sm.add_command_hook(s, "SessionStart", CMD)
            sm.save(p, s)
            baks = list(Path(d).glob("settings.json.bak.*"))
            self.assertEqual(len(baks), 1)
            # backup is a byte-for-byte copy of the pre-edit file
            self.assertEqual(baks[0].read_text(encoding="utf-8"), '{"model":"x"}')

    def test_load_missing_is_empty(self):
        self.assertEqual(sm.load(Path("/no/such/file.json")), {})


@unittest.skipIf(sys.platform == "win32", "install.sh is a bash script; tested on macOS/Linux")
class InstallScript(unittest.TestCase):
    def _run(self, home):
        env = dict(os.environ, HOME=str(home))
        return subprocess.run(
            ["bash", str(REPO / "install.sh")],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_install_is_nondestructive_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            settings = home / ".claude" / "settings.json"
            settings.parent.mkdir(parents=True)
            # pre-existing, unrelated config that must survive (criterion 1)
            settings.write_text(
                json.dumps(
                    {
                        "model": "keep-me",
                        "hooks": {
                            "SessionStart": [
                                {"hooks": [{"type": "command", "command": "echo other"}]}
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            r1 = self._run(home)
            self.assertEqual(r1.returncode, 0, r1.stderr)
            self.assertTrue((home / ".claude/hooks/ledger_session_start.py").is_file())
            self.assertTrue((home / ".claude/ledger/groups.json").is_file())
            self.assertTrue((home / ".claude/ledger/protocol.md").is_file())

            data = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(data["model"], "keep-me")
            cmds = [h["command"] for g in data["hooks"]["SessionStart"] for h in g["hooks"]]
            self.assertIn("echo other", cmds)
            self.assertIn(CMD, cmds)

            # second run = no-op (criterion 5): no duplicate ledger entry
            r2 = self._run(home)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            data2 = json.loads(settings.read_text(encoding="utf-8"))
            cmds2 = [h["command"] for g in data2["hooks"]["SessionStart"] for h in g["hooks"]]
            self.assertEqual(cmds2.count(CMD), 1)

    def test_install_does_not_overwrite_existing_registry(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            ledger = home / ".claude" / "ledger"
            ledger.mkdir(parents=True)
            (ledger / "groups.json").write_text('{"version":1,"groups":{"mine":{}}}', encoding="utf-8")
            r = self._run(home)
            self.assertEqual(r.returncode, 0, r.stderr)
            # untouched
            self.assertIn("mine", (ledger / "groups.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
