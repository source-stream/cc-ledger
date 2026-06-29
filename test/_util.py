"""Shared helpers for cc-ledger tests. Standard library only, fully hermetic."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "hooks" / "ledger_session_start.py"
INIT = REPO / "bin" / "ledger-init"
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


def commit_all(path, msg="init"):
    """Stage and commit everything in a repo so it has a HEAD/branch."""
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(path),
         "-c", "user.email=t@example.com", "-c", "user.name=test",
         "commit", "-q", "-m", msg],
        check=True,
    )


def make_bare_remote(path):
    """Create a bare repo seeded with one commit, usable as a `git clone` source."""
    path = Path(path)
    subprocess.run(["git", "init", "-q", "--bare", str(path)], check=True)
    seed = path.parent / (path.name + "-seed")
    subprocess.run(["git", "init", "-q", str(seed)], check=True)
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    commit_all(seed)
    # default branch name varies; push whatever HEAD is to main
    subprocess.run(
        ["git", "-C", str(seed), "push", "-q", str(path), "HEAD:main"], check=True
    )
    return path


def run_init(args, registry=None, protocol=EXAMPLE_PROTOCOL, home=None, stdin=None):
    """Run `bin/ledger-init <args...>` hermetically. Returns (returncode, parsed_json,
    stderr). HOME is isolated so the `installed` flag and Path.home() are controllable;
    the registry/protocol are pointed via env so no real config is touched."""
    env = dict(os.environ)
    if home is not None:
        env["HOME"] = str(home)
        env.pop("USERPROFILE", None)
    if registry is not None:
        env["CC_LEDGER_REGISTRY"] = str(registry)
    if protocol is not None:
        env["CC_LEDGER_PROTOCOL"] = str(protocol)
    p = subprocess.run(
        [sys.executable, str(INIT)] + list(args),
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(p.stdout) if p.stdout.strip() else None
    except Exception:
        data = None
    return p.returncode, data, p.stderr
