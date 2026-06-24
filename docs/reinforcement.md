# Reinforcement & teams (optional)

Milestone posting is model-driven and can drift over long sessions. These optional hooks
harden it. **Both are off by default** — enable them when you install:

```sh
./install.sh --with-pr-nudge --with-subagent
```

Re-running `install.sh` with a flag adds that hook idempotently; `uninstall.sh` removes
all of them.

## PR-nudge — `ledger_pr_nudge.py` (PostToolUse, matcher `Bash`)

The PR event is the one most worth guaranteeing. After a Bash command, if it contains
`gh pr create` (or `git push`), the hook injects an **advisory** reminder to post the PR
milestone (and `DONE` when it merges).

- **Advisory only** — it cannot and does not block; the tool has already run.
- **Quiet by default** — it only nudges inside an opted-in clone (one with a
  `.ledger.json` marker). Elsewhere it stays silent.

## Read-only subagent briefing — `ledger_subagent_start.py` (SubagentStart)

When a subagent is spawned in an opted-in clone, this injects a **read-only** note: be
aware of sibling activity, but **do not post** — only the main/orchestrator session
posts. This preserves the "orchestrator owns the ledger" model.

### Noise trade-off

Leaving the subagent briefing **off** (the default) is the quiet choice: only the
orchestrator's SessionStart briefing consults the ledger, and only the orchestrator
posts. Turn it **on** when your subagents do independent planning that should be informed
by sibling activity — at the cost of extra context injected per subagent. Because the
briefing is read-only, enabling it never adds channel posts, only context.
