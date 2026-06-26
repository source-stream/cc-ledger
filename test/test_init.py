"""Tests for bin/ledger-init — the deterministic helpers behind the /ledger-init wizard.

Hermetic: isolated HOME, a temp parent dir of throwaway git repos, and a local bare repo
as the `git clone` source (no network). Covers the state model (S0–S6, S8), discovery,
arch-field derivation, the structural registry merge (backup + preserve + disambiguate),
the shared enable path, cloning branches, and the dry run.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _util import (  # noqa: E402
    EXAMPLE_PROTOCOL,
    REPO,
    commit_all,
    make_bare_remote,
    make_repo,
    run_init,
)

ENABLE = REPO / "bin" / "ledger-enable"


def write_registry(path, groups):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 2, "groups": groups}) + "\n", encoding="utf-8")


@unittest.skipIf(sys.platform == "win32", "drives git/bash helpers; tested on macOS/Linux")
class LedgerInit(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.work = self.root / "work"
        self.work.mkdir()
        self.registry = self.home / ".claude" / "ledger" / "groups.json"
        self.addCleanup(self._tmp.cleanup)

    def init(self, *args, stdin=None):
        rc, data, err = run_init(
            args, registry=self.registry, protocol=EXAMPLE_PROTOCOL,
            home=self.home, stdin=stdin,
        )
        self.assertIsNotNone(data, "no JSON on stdout; stderr=%s" % err)
        return data

    def repo(self, name, remote=None, marker=None):
        return make_repo(self.work / name, remote=remote, marker=marker)

    # ---- state model -------------------------------------------------------------
    def test_S0_fresh(self):
        write_registry(self.registry, {})
        self.repo("globex-cdk", remote="git@github.com:acme/globex-cdk.git")
        d = self.init("detect", "--cwd", str(self.work / "globex-cdk"))
        self.assertEqual(d["state"], "S0_fresh")
        self.assertEqual(d["installed"], False)  # no hook under this HOME

    def test_S1_registry_only(self):
        write_registry(self.registry, {
            "globex": {"channel": "#n", "projects": {
                "cdk": {"match": ["globex-cdk"], "role": "Infra"}}}})
        self.repo("globex-cdk", remote="git@github.com:acme/globex-cdk.git")
        d = self.init("detect", "--cwd", str(self.work / "globex-cdk"))
        self.assertEqual(d["state"], "S1_registry_only")
        self.assertEqual(d["group"], "globex")
        self.assertEqual(d["project"], "cdk")

    def test_S2_group_missing(self):
        write_registry(self.registry, {})
        self.repo("app", remote="git@github.com:acme/app.git",
                  marker='{ "group": "ghost" }\n')
        d = self.init("detect", "--cwd", str(self.work / "app"))
        self.assertEqual(d["state"], "S2_group_missing")
        self.assertEqual(d["group"], "ghost")

    def test_S3_project_unresolved(self):
        # monorepo: two projects share one remote, marker omits project -> unknown
        write_registry(self.registry, {
            "mono": {"channel": "#m", "projects": {
                "fe": {"match": ["mono.git"], "role": "FE"},
                "be": {"match": ["mono.git"], "role": "BE"}}}})
        self.repo("mono", remote="git@github.com:acme/mono.git",
                  marker='{ "group": "mono" }\n')
        d = self.init("detect", "--cwd", str(self.work / "mono"))
        self.assertEqual(d["state"], "S3_project_unresolved")
        self.assertIn("fe", d["candidate_projects"])

    def test_S4_configured(self):
        write_registry(self.registry, {
            "globex": {"channel": "#n", "projects": {
                "cdk": {"match": ["globex-cdk"], "role": "Infra"}}}})
        self.repo("globex-cdk", remote="git@github.com:acme/globex-cdk.git",
                  marker='{ "group": "globex", "project": "cdk" }\n')
        d = self.init("detect", "--cwd", str(self.work / "globex-cdk"))
        self.assertEqual(d["state"], "S4_configured")
        self.assertEqual(d["project"], "cdk")
        self.assertEqual(d["channel"], "#n")

    def test_S5_malformed_marker(self):
        write_registry(self.registry, {})
        self.repo("bad", remote="x", marker="{ this is not json")
        d = self.init("detect", "--cwd", str(self.work / "bad"))
        self.assertEqual(d["state"], "S5_malformed_marker")
        self.assertIn("marker_error", d)

    def test_S6_malformed_registry_detect_and_refuse_merge(self):
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        self.registry.write_text("{ broken", encoding="utf-8")
        self.repo("app", remote="x")
        d = self.init("detect", "--cwd", str(self.work / "app"))
        self.assertEqual(d["state"], "S6_malformed_registry")
        # apply-registry must refuse and leave the file byte-for-byte unchanged
        before = self.registry.read_text(encoding="utf-8")
        spec = self.root / "g.json"
        spec.write_text(json.dumps({"group": "g", "body": {"channel": "#g", "projects": {}}}))
        d2 = self.init("apply-registry", "--group-json", str(spec))
        self.assertFalse(d2["ok"])
        self.assertEqual(self.registry.read_text(encoding="utf-8"), before)

    def test_S8_installed_flag_true_when_hook_present(self):
        write_registry(self.registry, {})
        (self.home / ".claude" / "hooks").mkdir(parents=True)
        (self.home / ".claude" / "hooks" / "ledger_session_start.py").write_text("#", "utf-8")
        self.repo("app", remote="x")
        d = self.init("detect", "--cwd", str(self.work / "app"))
        self.assertTrue(d["installed"])

    # ---- discovery & derivation --------------------------------------------------
    def test_discover_lists_sibling_with_match(self):
        write_registry(self.registry, {})
        self.repo("globex-cdk", remote="git@github.com:acme/globex-cdk.git")
        self.repo("globex", remote="git@github.com:acme/globex.git")
        d = self.init("discover", "--cwd", str(self.work / "globex-cdk"))
        names = {s["name"] for s in d["siblings"]}
        self.assertEqual(names, {"globex"})  # excludes the current repo
        sib = d["siblings"][0]
        self.assertEqual(sib["match"], ["globex"])

    def test_derive_monorepo_emits_areas(self):
        r = self.repo("globex", remote="git@github.com:acme/globex.git")
        (r / "apps" / "web").mkdir(parents=True)
        (r / "packages" / "storybook").mkdir(parents=True)
        d = self.init("derive", "--path", str(r))
        self.assertTrue(d["monorepo"])
        self.assertIn("web", d["areas"])
        self.assertIn("storybook", d["areas"])

    def test_derive_single_app_no_areas(self):
        r = self.repo("svc", remote="git@github.com:acme/svc.git")
        (r / "main.py").write_text("print(1)\n", encoding="utf-8")
        d = self.init("derive", "--path", str(r))
        self.assertFalse(d["monorepo"])
        self.assertNotIn("areas", d)
        self.assertIn("summary", d["responsibility"])

    # ---- registry merge ----------------------------------------------------------
    def test_apply_registry_preserves_backup_and_disambiguates(self):
        write_registry(self.registry, {
            "acme": {"channel": "#acme", "projects": {
                "web": {"match": ["acme-web"], "role": "FE"}}}})
        spec = self.root / "g.json"
        spec.write_text(json.dumps({"group": "globex", "body": {
            "channel": "#n", "projects": {
                "globex-cdk": {"match": ["globex-cdk"], "role": "Infra"},
                "globex": {"match": ["globex"], "role": "Mono"}}}}))
        d = self.init("apply-registry", "--group-json", str(spec))
        self.assertTrue(d["ok"] and d["changed"])
        self.assertIsNotNone(d["backup"])
        self.assertTrue(Path(d["backup"]).is_file())
        reg = json.loads(self.registry.read_text(encoding="utf-8"))
        self.assertIn("acme", reg["groups"])  # unrelated group preserved
        # 'globex' collides with 'globex-cdk' as a substring -> gets .git
        self.assertEqual(
            reg["groups"]["globex"]["projects"]["globex"]["match"],
            ["globex.git"])

    def test_apply_registry_remote_aware_disambiguation(self):
        # With real remotes provided, a token is anchored with .git ONLY when that still
        # matches the project's own remote. A remote without a .git suffix is left alone
        # (anchoring would break its own resolution).
        write_registry(self.registry, {})
        spec = self.root / "g.json"
        spec.write_text(json.dumps({
            "group": "g",
            "body": {"channel": "#g", "projects": {
                "api": {"match": ["api"], "role": "API"},
                "api-gw": {"match": ["api-gw"], "role": "GW"}}},
            "remotes": {
                "api": "https://github.com/acme/api",        # no .git suffix
                "api-gw": "https://github.com/acme/api-gw"}}))
        self.init("apply-registry", "--group-json", str(spec))
        reg = json.loads(self.registry.read_text(encoding="utf-8"))
        # 'api' collides with api-gw's remote, but 'api.git' is NOT in '.../api' -> left as-is
        self.assertEqual(reg["groups"]["g"]["projects"]["api"]["match"], ["api"])

    def test_apply_registry_idempotent_no_change_on_rerun(self):
        write_registry(self.registry, {})
        spec = self.root / "g.json"
        spec.write_text(json.dumps({"group": "g", "body": {
            "channel": "#g", "projects": {"a": {"match": ["a"], "role": "A"}}}}))
        self.init("apply-registry", "--group-json", str(spec))
        d2 = self.init("apply-registry", "--group-json", str(spec))
        self.assertFalse(d2["changed"])

    def test_apply_registry_merge_preserves_existing_projects(self):
        write_registry(self.registry, {
            "g": {"channel": "#g", "projects": {
                "old": {"match": ["old"], "role": "Old"}}}})
        spec = self.root / "g.json"
        spec.write_text(json.dumps({"group": "g", "body": {
            "channel": "#g", "projects": {"new": {"match": ["new"], "role": "New"}}}}))
        self.init("apply-registry", "--group-json", str(spec))
        reg = json.loads(self.registry.read_text(encoding="utf-8"))
        self.assertEqual(set(reg["groups"]["g"]["projects"]), {"old", "new"})

    # ---- enable (shared marker + exclude path) -----------------------------------
    def test_enable_matches_ledger_enable_bytes_and_excludes(self):
        r = self.repo("app", remote="git@github.com:acme/app.git")
        d = self.init("enable", "--root", str(r), "--group", "acme", "--project", "api")
        self.assertTrue(d["excluded"])
        marker = (r / ".ledger.json").read_text(encoding="utf-8")
        self.assertEqual(marker, '{ "group": "acme", "project": "api" }\n')
        excl = (r / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertIn(".ledger.json", excl)
        status = subprocess.run(["git", "-C", str(r), "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.assertEqual(status.strip(), "")

    def test_enable_rejects_keys_with_quotes(self):
        r = self.repo("app", remote="x")
        d = self.init("enable", "--root", str(r), "--group", 'a","x":"y')
        self.assertFalse(d["ok"])
        self.assertFalse((r / ".ledger.json").exists())

    def test_enable_exclude_idempotent(self):
        r = self.repo("app", remote="x")
        self.init("enable", "--root", str(r), "--group", "g", "--project", "p")
        self.init("enable", "--root", str(r), "--group", "g", "--project", "p")
        excl = (r / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
        self.assertEqual(excl.count(".ledger.json"), 1)

    # ---- cloning -----------------------------------------------------------------
    def test_clone_happy(self):
        bare = make_bare_remote(self.root / "remotes" / "etl.git")
        dest = self.work / "etl"
        d = self.init("clone", "--url", str(bare), "--dest", str(dest))
        self.assertTrue(d["ok"])
        self.assertEqual(d["action"], "cloned")
        self.assertTrue((dest / ".git").exists())

    def test_clone_adopts_matching_existing(self):
        bare = make_bare_remote(self.root / "remotes" / "etl.git")
        dest = self.work / "etl"
        subprocess.run(["git", "clone", "-q", str(bare), str(dest)], check=True)
        d = self.init("clone", "--url", str(bare), "--dest", str(dest))
        self.assertTrue(d["ok"])
        self.assertEqual(d["action"], "adopted")

    def test_clone_conflict_on_different_repo(self):
        bare = make_bare_remote(self.root / "remotes" / "etl.git")
        dest = self.work / "etl"
        make_repo(dest, remote="git@github.com:acme/somethingelse.git")
        d = self.init("clone", "--url", str(bare), "--dest", str(dest))
        self.assertFalse(d["ok"])
        self.assertEqual(d["action"], "conflict")

    def test_clone_failed_registers_nothing_and_classifies(self):
        dest = self.work / "nope"
        d = self.init("clone", "--url", str(self.root / "does-not-exist.git"),
                      "--dest", str(dest))
        self.assertFalse(d["ok"])
        self.assertEqual(d["action"], "clone_failed")

    # ---- dry run -----------------------------------------------------------------
    def test_dry_run_renders_protocol(self):
        write_registry(self.registry, {
            "g": {"channel": "#g", "projects": {
                "cdk": {"match": ["cdk-repo"], "role": "Infra"}}}})
        r = self.repo("cdk-repo", remote="git@github.com:acme/cdk-repo.git",
                      marker='{ "group": "g", "project": "cdk" }\n')
        d = self.init("dry-run", "--root", str(r))
        self.assertTrue(d["ok"])
        self.assertTrue(d["injects"])
        self.assertIn("LEDGER PROTOCOL", d["context"])
        self.assertIn("#g", d["context"])


if __name__ == "__main__":
    unittest.main()
