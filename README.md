# cc-ledger

A small, shareable toolkit that gives Claude Code sessions a shared **work ledger** over
Slack. Multiple clones/sessions working across a group of related repos post terse
milestone entries to one Slack channel — and read that channel on startup — so they can
see each other's progress (tasks started, plans finalised, PRs raised, tickets created,
blockers) and assess cross-project impact **before** starting work.

It is project-agnostic: you describe your own *groups* of repos in a machine-local
registry. The toolkit runtime never lives inside a work repo; the only thing it ever
places in a work repo is a single git-excluded marker.

## How it works

```
SessionStart hook ──reads──► .ledger.json (marker, git-excluded)
        │                         │ names the group (+ optional project)
        │                         ▼
        │                 ~/.claude/ledger/groups.json (registry)
        │                         │ group → Slack channel + sibling projects
        ▼                         ▼
   renders ~/.claude/ledger/protocol.md  ──injects──►  Claude Code session
        │
        ▼
   Claude uses the Slack MCP to read the channel on start, brief you on
   cross-project impact, and post milestones during the work.
```

- **Group** — a set of projects coordinating via one Slack channel.
- **Project** — one repo within a group (a group may have 1..n).
- **Registry** — machine-local JSON mapping groups → channels + projects
  (`~/.claude/ledger/groups.json`).
- **Marker** — git-excluded `.ledger.json` in a clone that opts it in and names its group.
- **Protocol** — the instruction block the hook renders and injects at session start.

The hook is shell/Python and cannot call the Slack MCP itself; it injects the
instructions that make *Claude* use the Slack MCP. Startup "read the ledger" is reliable
because injected context carries message-weight; milestone posting is model-driven and
can be hardened with the optional [reinforcement hooks](docs/reinforcement.md).

## Install

```sh
git clone git@github.com:source-stream/cc-ledger.git
cd cc-ledger
./install.sh           # idempotent, non-destructive
```

See [docs/INSTALL.md](docs/INSTALL.md) (and the [manual steps](docs/INSTALL-manual.md)).
Requires `python3` and the Slack MCP enabled in Claude Code.

## Edit your registry

`install.sh` seeds `~/.claude/ledger/groups.json` from
[`config/groups.example.json`](config/groups.example.json) **only if absent**. Edit it to
describe your real groups:

```json
{
  "version": 1,
  "groups": {
    "acme": {
      "channel": "#acme-ledger",
      "projects": {
        "web":   { "match": ["acme-web"],   "role": "Front-end / application code" },
        "api":   { "match": ["acme-api"],   "role": "Backend API service" },
        "infra": { "match": ["acme-infra"], "role": "Cloud infrastructure" }
      }
    }
  }
}
```

`match` substrings are tested against a clone's git remote URL to auto-detect the project
when the marker omits it. **This file is machine-local — never commit it.**

## Enable a clone

```sh
/path/to/cc-ledger/bin/ledger-enable <group> [project]
# e.g.
/path/to/cc-ledger/bin/ledger-enable acme api
```

Writes `.ledger.json` and excludes it via `.git/info/exclude` (never `.gitignore`), so
`git status` stays clean and the marker is never shared. Reverse with `ledger-disable`.
See [docs/marker.md](docs/marker.md).

## Privacy model

- The toolkit repo is shareable with trusted colleagues (e.g. a private repo in your
  team's org) — not published into client repos.
- The registry holds client-identifying channel names and project identifiers; the
  **real** registry stays machine-local (seeded from the example, never committed back).
- A clone joins only via a **git-excluded marker**. Nothing is ever committed to a work
  repo.
- The protocol states explicitly: trial-only, channel-only, do not surface to the human
  team.

## Promotion path

To graduate the ledger from a personal trial to a team, move the hook entry into a work
repo's committed `.claude/settings.json` and ship the registry deliberately — a conscious
step, not an accident.

## Development

- Tests: `python3 -m unittest discover -s test` (standard library only).
- CI runs the suite on Linux, macOS and Windows × Python 3.9 & 3.12.
- See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md).

## Troubleshooting

- **Nothing is injected** — the clone has no `.ledger.json`, or its `group` isn't in your
  registry. The hook is silent when not opted in, and warns to stderr (never blocks)
  when a marker/registry/group is missing or malformed. Dry-run it:
  ```sh
  CC_LEDGER_REGISTRY=~/.claude/ledger/groups.json \
  CC_LEDGER_PROTOCOL=~/.claude/ledger/protocol.md \
  python3 ~/.claude/hooks/ledger_session_start.py
  ```
- **Wrong/`unknown` project** — set `project` explicitly in the marker, or fix the
  group's `match` substrings (an ambiguous remote that matches >1 project renders
  `unknown`).
- **No posts appear** — posting is model-driven; enable the
  [PR-nudge](docs/reinforcement.md) for the milestone most worth guaranteeing.
