"""Tests for bin/ledger-enable / ledger-disable (criterion 7).

These drive real bash scripts and git, so they are skipped on Windows (the helpers
target macOS/Linux shells). The marker must land at the repo root, be excluded via
.git/info/exclude (not .gitignore), leave `git status` clean, and disable must reverse.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENABLE = REPO / "bin" / "ledger-enable"
DISABLE = REPO / "bin" / "ledger-disable"


@unittest.skipIf(sys.platform == "win32", "bin/ledger-* are bash scripts; tested on macOS/Linux")
class EnableDisable(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "work"
        self.repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        # isolate HOME so registry validation is harmless/non-fatal
        self.env = dict(os.environ, HOME=str(Path(self._tmp.name) / "home"))
        self.addCleanup(self._tmp.cleanup)

    def _run(self, script, *args):
        return subprocess.run(
            ["bash", str(script), *args],
            cwd=str(self.repo),
            env=self.env,
            capture_output=True,
            text=True,
        )

    def _status(self):
        return subprocess.run(
            ["git", "-C", str(self.repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
        ).stdout

    def test_enable_writes_marker_excludes_and_stays_clean(self):
        r = self._run(ENABLE, "acme", "api")
        self.assertEqual(r.returncode, 0, r.stderr)
        marker = self.repo / ".ledger.json"
        self.assertTrue(marker.is_file())
        self.assertIn('"group": "acme"', marker.read_text(encoding="utf-8"))
        exclude = self.repo / ".git" / "info" / "exclude"
        self.assertIn(".ledger.json", exclude.read_text(encoding="utf-8"))
        # criterion 7: clone is clean (marker is excluded, not shown as untracked)
        self.assertEqual(self._status().strip(), "")

    def test_disable_reverses(self):
        self._run(ENABLE, "acme", "api")
        r = self._run(DISABLE)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.repo / ".ledger.json").exists())
        exclude = self.repo / ".git" / "info" / "exclude"
        self.assertNotIn(".ledger.json", exclude.read_text(encoding="utf-8"))
        self.assertEqual(self._status().strip(), "")

    def test_enable_infers_when_project_omitted(self):
        r = self._run(ENABLE, "acme")
        self.assertEqual(r.returncode, 0, r.stderr)
        marker = (self.repo / ".ledger.json").read_text(encoding="utf-8")
        self.assertIn('"group": "acme"', marker)
        self.assertNotIn("project", marker)


if __name__ == "__main__":
    unittest.main()
