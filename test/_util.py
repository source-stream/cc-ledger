"""Shared helpers for cc-ledger tests. Standard library only, fully hermetic."""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "hooks" / "ledger_session_start.py"
EXAMPLE_REGISTRY = REPO / "config" / "groups.example.json"
EXAMPLE_PROTOCOL = REPO / "protocol" / "template.md"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def make_repo(path, remote=None, marker=None):
    """Create a throwaway git repo at `path`. Optionally set an `origin` remote and
    write a `.ledger.json` marker (string contents)."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if remote:
        subprocess.run(
            ["git", "-C", str(path), "remote", "add", "origin", remote], check=True
        )
    if marker is not None:
        (path / ".ledger.json").write_text(marker, encoding="utf-8")
    return path


def run_hook(cwd, registry=EXAMPLE_REGISTRY, protocol=EXAMPLE_PROTOCOL, extra_env=None):
    """Run the SessionStart hook in `cwd`. Returns (returncode, stdout, stderr)."""
    env = dict(os.environ)
    env["CC_LEDGER_REGISTRY"] = str(registry)
    env["CC_LEDGER_PROTOCOL"] = str(protocol)
    if extra_env:
        env.update(extra_env)
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )
    return p.returncode, p.stdout, p.stderr
