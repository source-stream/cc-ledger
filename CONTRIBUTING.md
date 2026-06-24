# Contributing to cc-ledger

Thanks for helping improve cc-ledger. It's a tiny, dependency-free toolkit; the bar is
"obviously correct and impossible to mis-fire," because it runs inside other people's
Claude Code sessions and touches their `~/.claude/`.

## Hard rules

These are non-negotiable — PRs that break them won't merge:

1. **Python 3 standard library only.** No third-party runtime dependencies. Code must
   run identically on macOS, Linux and Windows (quote/join paths; no shell-isms in the
   Python; the `.sh`/`bin/` helpers target macOS/Linux).
2. **Hooks never block or crash a session.** Every failure path warns to stderr and
   exits 0; on success stdout is *only* the hook JSON. There is an absolute
   `try/except` backstop around each hook's `main()`.
3. **The installer is non-destructive and idempotent.** Back up `settings.json` before
   editing; do a structural JSON merge (never string-concatenate); never duplicate
   entries; seed the registry/protocol only if absent.
4. **Nothing client-identifying in the repo.** Examples use the neutral `acme` /
   `web`·`api`·`infra` group. Real channels and `match` substrings stay machine-local.
5. **Markers are excluded via `.git/info/exclude`, never `.gitignore`.**

## Workflow

- Branch per change; open a PR to `main`. CI (Linux/macOS/Windows × py3.9/3.12) must be
  green before merge.
- Keep commits atomic and messages descriptive.
- Add or update tests for any behaviour change. Tests are hermetic: they build temp git
  repos and point the hooks at fixtures via `CC_LEDGER_REGISTRY` / `CC_LEDGER_PROTOCOL`
  — never touch the real `~/.claude/` and never hit the network or the Slack MCP.

```sh
python3 -m unittest discover -s test -v
```

## Sharing & privacy

This repo is meant to be shared with trusted colleagues who opt in — not published into
client repos. When sharing:

- Share the toolkit, not your registry. Your `~/.claude/ledger/groups.json` (real
  channels + identifiers) is machine-local; only `config/groups.example.json` (neutral
  placeholders) ships.
- Don't add client names, channel IDs, or real `match` substrings to any committed file,
  issue, or PR.

See [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) for the acceptance criteria each change is
held to.
