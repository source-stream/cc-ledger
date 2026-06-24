# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

This repo is **greenfield**: only `project-brief.md` and `.gitignore` exist. There is
no code yet. `project-brief.md` is the authoritative implementation brief — read it in
full before building. The notes here summarize its load-bearing decisions; the brief
has the reference implementations, schemas, acceptance criteria, and the P1–P4 phased
plan.

## What this is

`cc-ledger` is a shareable toolkit that gives Claude Code sessions a shared **work
ledger** over Slack. Multiple clones/sessions working across a group of related repos
post terse milestone entries (STARTED / PLANNED / PR / JIRA / BLOCKER / DONE) to one
Slack channel, and read the channel on startup to surface cross-project impact before
planning.

## Core architecture (how the pieces fit)

The flow that requires reading several files to understand:

1. **Group registry** (`~/.claude/ledger/groups.json`) — machine-local data mapping a
   *group* → Slack channel + its *projects*. Each project has `match` substrings tested
   against the git remote URL, plus a human `role`. Adding a client = a registry entry,
   no code change.
2. **Per-clone marker** (`.ledger.json` at repo root) — opts a clone in, names its
   `group` (required) and optionally `project`. **Git-excluded via `.git/info/exclude`,
   never `.gitignore`** (gitignore would be committed/shared).
3. **`SessionStart` hook** (`hooks/ledger_session_start.py`) — on session start: finds
   repo root, reads the marker (absent → silent `exit 0`), looks up the group in the
   registry, infers `project` from the git remote `match` lists if the marker omits it,
   gathers sibling projects, renders the protocol template with placeholders, and prints
   hook JSON with `additionalContext` to stdout. The hook is shell/Python and **cannot
   call the Slack MCP itself** — it injects instructions that make *Claude* use the
   Slack MCP.
4. **Protocol template** (`~/.claude/ledger/protocol.md`) — the injected instruction
   block. Cross-project-first: read channel on start, weight sibling-project impact
   highest, brief the operator, then post milestones during work.

Key separation: the **toolkit repo** is distinct from any **work repo**. The installer
lays files into `~/.claude/`; the runtime never lives in a work repo. The only thing
that ever touches a work repo is the git-excluded marker.

## Non-negotiable constraints

- **Python 3 standard library only** — zero/minimal runtime deps, must run identically
  on macOS, Linux, Windows. No shell-isms that break on Windows; quote paths.
- **Never crash or block a session.** Missing/malformed marker, missing registry,
  unknown group → warn to stderr, `exit 0`. On success the hook prints *only* JSON to
  stdout. Must run well under a second.
- **Nothing is ever committed to a work repo** except the git-excluded marker.
- **Idempotent installer.** Back up `~/.claude/settings.json` before editing; do a safe
  *structural* JSON merge (Python or `jq`) — never string-concatenate JSON; never
  clobber unrelated hooks/settings; re-running is a no-op. Seed `groups.json` and
  `protocol.md` only if absent — never overwrite a real registry.
- **`additionalContext` is capped at ~10k chars** — keep the rendered protocol well
  under it.
- The protocol is a private trial: posts go only to the group channel, and it must not
  be surfaced to the client's human team.

## Before finalizing the hook

Verify the live Claude Code hook schema against the docs before settling the hook
output format: https://docs.anthropic.com/en/docs/claude-code/hooks

## Open decisions — ask the human, don't guess

The brief's "Open decisions" (hosting/name, real channel + `match` substrings,
machine-local vs shared registry, whether to build the optional PR-nudge, Python vs
bash+jq) are unresolved. Stop and ask rather than assuming.

## Planned layout & tooling (from the brief, not yet created)

`bin/` (ledger-enable/disable) · `hooks/` (session_start, optional pr_nudge) · `config/`
(groups.example.json) · `protocol/template.md` · `test/` (fixtures + `test_hook.py`) ·
`install.sh` / `uninstall.sh`. Tests are stdlib-based against fixture repos/markers/
registries. No build/lint/test commands exist yet — establish them as part of P1/P4.
