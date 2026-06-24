"""Acceptance tests for the cc-ledger SessionStart hook.

Each test maps to a numbered acceptance criterion from project-brief.md. Hermetic:
builds temp git repos, points the hook at the shipped example registry/protocol (or
fixtures) via env overrides, asserts on exit code + stdout/stderr contract.
"""
import json
import tempfile
import unittest
from pathlib import Path

from _util import EXAMPLE_REGISTRY, FIXTURES, make_repo, run_hook


def context_of(stdout):
    """Parse the hook's stdout and return the injected additionalContext."""
    obj = json.loads(stdout)
    hso = obj["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart", hso
    return hso["additionalContext"]


class HookContract(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    # C2 — clone with no marker injects nothing and prints nothing
    def test_no_marker_is_silent(self):
        repo = make_repo(self.tmp / "plain")
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertEqual(err, "")

    # C3 — enabled clone renders group / channel / project / siblings
    def test_enabled_clone_renders_protocol(self):
        repo = make_repo(
            self.tmp / "api", marker='{"group": "acme", "project": "api"}'
        )
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("acme", ctx)
        self.assertIn("#acme-ledger", ctx)
        self.assertIn("project: api", ctx)
        self.assertIn("Backend API service", ctx)  # the api role
        self.assertIn("- web:", ctx)  # siblings
        self.assertIn("- infra:", ctx)
        self.assertNotIn("{{", ctx)  # all placeholders substituted

    # C4 — marker omits project; it is inferred from the git remote
    def test_project_inferred_from_remote(self):
        repo = make_repo(
            self.tmp / "infer",
            remote="git@github.com:acme/acme-api.git",
            marker='{"group": "acme"}',
        )
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("project: api", ctx)

    # C6 — never blocks: malformed marker
    def test_malformed_marker_never_blocks(self):
        repo = make_repo(self.tmp / "bad", marker="{ not json")
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertIn("[cc-ledger]", err)

    # C6 — never blocks: missing registry
    def test_missing_registry_never_blocks(self):
        repo = make_repo(self.tmp / "noreg", marker='{"group": "acme"}')
        rc, out, err = run_hook(repo, registry=self.tmp / "does-not-exist.json")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertIn("[cc-ledger]", err)

    # C6 — never blocks: unparseable registry
    def test_malformed_registry_never_blocks(self):
        repo = make_repo(self.tmp / "badreg", marker='{"group": "acme"}')
        rc, out, err = run_hook(repo, registry=FIXTURES / "registry_malformed.json")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertIn("[cc-ledger]", err)

    # C6 — never blocks: unknown group
    def test_unknown_group_never_blocks(self):
        repo = make_repo(self.tmp / "unknown", marker='{"group": "nope"}')
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertIn("[cc-ledger]", err)

    # C6 — never blocks: marker missing 'group'
    def test_marker_without_group_never_blocks(self):
        repo = make_repo(self.tmp / "nogroup", marker='{"project": "api"}')
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertIn("[cc-ledger]", err)

    # C8 — single-project group renders graceful no-siblings text
    def test_single_project_group_no_siblings(self):
        repo = make_repo(
            self.tmp / "solo",
            marker='{"group": "example-single", "project": "app"}',
        )
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("(this group has no other projects)", ctx)
        self.assertNotIn("{{", ctx)

    # Ambiguous remote (no marker project, >1 match) -> 'unknown'
    def test_ambiguous_or_unmatched_remote_is_unknown(self):
        repo = make_repo(
            self.tmp / "amb",
            remote="git@github.com:acme/something-unrelated.git",
            marker='{"group": "acme"}',
        )
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("project: unknown", ctx)

    # The shipped example registry must be valid JSON with the documented shape
    def test_example_registry_is_valid(self):
        reg = json.loads(Path(EXAMPLE_REGISTRY).read_text(encoding="utf-8"))
        self.assertEqual(reg.get("version"), 1)
        self.assertIn("acme", reg["groups"])
        self.assertIn("example-single", reg["groups"])


if __name__ == "__main__":
    unittest.main()
