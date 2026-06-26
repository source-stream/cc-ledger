---
name: ledger-init
description: Guided setup wizard for the cc-ledger work ledger. Detects the current state of this clone and walks you through creating/repairing a group, discovering sibling repos, cloning missing ones, and writing the registry + marker. Invoke directly with /ledger-init.
argument-hint: "[group] [project]"
disable-model-invocation: true
allowed-tools: Bash, Read, AskUserQuestion
---

# cc-ledger setup wizard

You are running the `/ledger-init` setup wizard. Drive it as a calm, concise conversation.
Every file/git mutation goes through the bundled helper — **never hand-edit `groups.json`,
the marker, or `.git/info/exclude` yourself.** The helper is idempotent, backs up before
writing, and prints JSON; read its `ok`/`state`/`error` fields, not its exit code.

Helper: `python3 ${CLAUDE_SKILL_DIR}/ledger-init <subcommand>` (run with the Bash tool).
Any arguments the user passed are in `$ARGUMENTS` (optional `group [project]` to pre-seed).

## Current state (auto-detected at load)

The line below runs the helper and inlines this clone's current state as JSON:

!`python3 ${CLAUDE_SKILL_DIR}/ledger-init detect`

## How to proceed, by `state`

Read the `state` field above and follow the matching branch. Confirm before any write.

- **S0_fresh** — this repo isn't in any group. Run the full flow:
  1. Ask for the Slack **channel** and a short **group key** (default the key from the repo name).
  2. `discover` siblings in the parent dir; present them and ask which to include. Ask if any
     other projects exist (by git URL or path) that weren't found.
  3. For each project run `derive --path <path>` to draft `role` / `responsibility` /
     `keywords` / `areas`; show each draft and let the user accept or edit. For projects given
     only by URL (not on disk), draft from the name and say you couldn't inspect it.
  4. For any project **not** checked out, offer to `clone --url <U> --dest <parent>/<name>`.
     Show the exact destination and confirm first. On a clone failure, keep the project in the
     registry anyway and tell the user plainly what failed (auth / network / occupied dest).
  5. Show a summary of everything to be written and get a final yes.
  6. `apply-registry` with the assembled group, then `enable` this repo. Offer (default yes) to
     `enable` the sibling clones too — list them and confirm.
  7. `dry-run` and show the rendered context so they see exactly what future sessions load.

- **S1_registry_only** — group already in the registry, no marker here. Skip group creation.
  Confirm the inferred `project` (the `detect` output names it); if `unknown`, ask which one.
  `enable` this repo, then `dry-run`.

- **S2_group_missing** — the marker names a group absent from the registry. Don't invent it.
  Ask: create that group now (→ run the S0 flow for it), or fix a mistyped group name.

- **S3_project_unresolved** — marker is valid but the project is `unknown` (e.g. a monorepo, or
  the remote matched 0/>1 projects). Show `candidate_projects`, ask the user to pick, and
  `enable --root <root> --group <g> --project <chosen>` to rewrite the marker. Then `dry-run`.

- **S4_configured** — already set up. State the group, project, channel, and registry path from
  the `detect` output. Offer: (1) re-configure, (2) add/refresh siblings, (3) disable here
  (`bin/ledger-disable`), (4) nothing. **Write nothing unless they pick an action.**

- **S5_malformed_marker** — show `marker_raw` / `marker_error`, then offer to rewrite a clean
  marker via `enable`. (The runtime hook already tolerates this, so no session is blocked.)

- **S6_malformed_registry** — do **not** edit it. Show `registry_error` and the registry path,
  and offer to open it for manual repair. Refuse to merge until it parses.

- If `installed` is `false` — tell the user to run `install.sh` first (the `dry-run` preview and
  the SessionStart hook need the installed hook). Offer to continue writing config regardless.

## Assembling the group for `apply-registry`

`apply-registry` reads one group spec as JSON (via `--group-json <file>` or stdin):

```json
{ "group": "<key>", "body": {
    "channel": "#channel", "description": "...",
    "projects": {
      "<project-key>": {
        "match": ["<substring>"], "role": "...",
        "responsibility": { "summary": "...", "keywords": ["..."] },
        "areas": { "<area>": "<desc>" }
      }
    }
  },
  "remotes": { "<project-key>": "<git remote URL>" }
}
```

Build it from the confirmed per-project drafts. Include the optional top-level `remotes` map
(project key → the remote URL you saw in `detect`/`discover`/`derive`) — the helper uses it to
disambiguate `match` tokens correctly when one repo name is a prefix of another (e.g.
`globex` vs `globex-cdk`); it only anchors a token with `.git` when that still matches
the project's own remote, so resolution is never silently broken. The helper deep-merges onto
any existing group (never dropping projects the user already has) and backs up `groups.json`
first. Use a temp file for `--group-json` (write it, then pass the path).

## Rules

- Confirm before every mutation; show destinations and summaries.
- Never touch `.gitignore` (the helper excludes the marker via `.git/info/exclude`).
- This is a private trial — don't surface it to the client's human team or post anywhere yet.
- Keep it terse. End with the `dry-run` preview and a one-line "done" summary.
