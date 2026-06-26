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
        self.assertIn("ARCHITECTURE MAP", ctx)
        self.assertIn("- web —", ctx)  # siblings in the architecture map
        self.assertIn("- infra —", ctx)
        self.assertIn("api ←you are here", ctx)  # current project marked
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

    # C8 — single-project group renders gracefully (map has just the current repo)
    def test_single_project_group_no_siblings(self):
        repo = make_repo(
            self.tmp / "solo",
            marker='{"group": "example-single", "project": "app"}',
        )
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("- app ←you are here", ctx)  # the only project, marked
        self.assertEqual(ctx.count("←you are here"), 1)  # no siblings
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
        self.assertEqual(reg.get("version"), 2)
        self.assertIn("acme", reg["groups"])
        self.assertIn("example-single", reg["groups"])
        self.assertIn("nomadfoods", reg["groups"])


class ArchitectureMap(unittest.TestCase):
    """P5 — the injected architecture map routes new work to the right repo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    # C9 — map lists every project, marks the current one, carries routing instruction
    def test_map_present_marks_current_and_lists_siblings(self):
        repo = make_repo(
            self.tmp / "cdk",
            marker='{"group": "nomadfoods", "project": "nomadfoods-cdk"}',
        )
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("nomadfoods-cdk ←you are here", ctx)  # current marked
        self.assertIn("Data import & load pipelines", ctx)  # sibling summary
        self.assertIn("ETL", ctx)  # sibling routing keyword
        self.assertIn("WHEN PLANNING OR IMPLEMENTING NEW FUNCTIONALITY", ctx)
        # a sibling monorepo's sub-areas appear as names only, not as detail
        self.assertIn("areas: web, storybook", ctx)
        self.assertNotIn("web=Next.js", ctx)
        self.assertNotIn("THIS REPO'S AREAS", ctx)  # current repo has no areas
        self.assertNotIn("{{", ctx)

    # C11 — missing responsibility falls back to role; never blocks
    def test_map_falls_back_to_role(self):
        repo = make_repo(
            self.tmp / "mono",
            marker='{"group": "example-monorepo", "project": "monorepo-frontend"}',
        )
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("Frontend (monorepo: apps/frontend)", ctx)  # the role
        self.assertNotIn("{{", ctx)

    # C10 — the current monorepo gets sub-area detail
    def test_monorepo_current_shows_area_detail(self):
        repo = make_repo(
            self.tmp / "nf",
            marker='{"group": "nomadfoods", "project": "nomadfoods"}',
        )
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("THIS REPO'S AREAS", ctx)
        self.assertIn("web=Next.js storefront & pages", ctx)
        self.assertNotIn("{{", ctx)

    # C11 — oversized group is truncated with `+N more` and stays under the cap
    def test_oversized_map_is_budgeted(self):
        projects = {
            "proj%03d" % i: {
                "match": ["proj%03d" % i],
                "responsibility": {
                    "summary": "Service number %d doing something useful" % i,
                    "keywords": ["alpha", "beta", "gamma", "delta"],
                },
            }
            for i in range(100)
        }
        registry = {
            "version": 2,
            "groups": {"big": {"channel": "#big", "projects": projects}},
        }
        reg_path = self.tmp / "big.json"
        reg_path.write_text(json.dumps(registry), encoding="utf-8")
        repo = make_repo(self.tmp / "big", marker='{"group": "big", "project": "proj000"}')
        rc, out, err = run_hook(repo, registry=reg_path)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("more projects (see registry)", ctx)
        self.assertLess(len(ctx), 9500)  # under MAX_CONTEXT
        self.assertNotIn("{{", ctx)

    # C11 — unknown project: all projects listed, none marked, no own-areas
    def test_unknown_project_has_no_marker(self):
        repo = make_repo(
            self.tmp / "amb",
            remote="git@github.com:nomad/something-unrelated.git",
            marker='{"group": "nomadfoods"}',
        )
        rc, out, err = run_hook(repo)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("project: unknown", ctx)
        self.assertNotIn("←you are here", ctx)
        self.assertNotIn("THIS REPO'S AREAS", ctx)
        self.assertNotIn("{{", ctx)

    # Back-compat: an old protocol that only uses {{SIBLINGS}} still renders
    def test_legacy_siblings_protocol_still_renders(self):
        legacy = self.tmp / "legacy_protocol.md"
        legacy.write_text(
            "group: {{GROUP}}\nOther projects:\n{{SIBLINGS}}\n", encoding="utf-8"
        )
        repo = make_repo(
            self.tmp / "api", marker='{"group": "acme", "project": "api"}'
        )
        rc, out, err = run_hook(repo, protocol=legacy)
        self.assertEqual(rc, 0, err)
        ctx = context_of(out)
        self.assertIn("- web:", ctx)  # legacy sibling format still substituted
        self.assertNotIn("{{", ctx)


if __name__ == "__main__":
    unittest.main()
