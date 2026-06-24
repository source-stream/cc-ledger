# cc-ledger — Implementation Brief

A small, shareable toolkit that gives Claude Code sessions a shared **work ledger**
over Slack, so that multiple clones/sessions working on the same group of projects
can see each other's progress (tasks started, plans finalised, PRs raised, Jira
tickets created, blockers) and assess cross-project impact before starting work.

This document is an implementation brief. Load it into Claude Code, plan from it,
then build it. The code blocks below are **reference implementations** to anchor the
design — treat them as a starting point, not gospel, and improve on them.

---

## How to use this brief (instructions for Claude Code)

1. Read the whole brief first. Produce a short plan (milestones map to the phased
   delivery plan near the end) before writing code.
2. Build the toolkit as its own git repository, separate from any work repo.
3. Nothing this toolkit produces should ever be committed into a *work* repo. The
   only thing that touches a work repo is a local, git-excluded marker file.
4. Prefer zero/minimal runtime dependencies (Python 3 standard library) so it runs
   the same on macOS, Linux, and Windows for whoever installs it.
5. Verify the live Claude Code hook schema against the docs before finalising the
   hook output format: https://docs.anthropic.com/en/docs/claude-code/hooks
6. Stop and ask the human about the items under "Open decisions" rather than guessing.

---

## Background & goals

We run Claude Code (often with Agent Teams) across **multiple clones** of **several
projects**. Projects cluster into **groups**. For example a group might span three
repos:

| Project | Role (example)                                           |
|---------|---------------------------------------------------------|
| `web`   | Front-end / application code                             |
| `api`   | Backend API service                                     |
| `infra` | Cloud infrastructure (CDN, DNS, serverless, WAF, search) |

Other groups may have a single project, or many. The value of the ledger is highest
*across* projects in a group: a change in `infra` (e.g. a CDN function or a DNS
cutover) is exactly what the `web` and `api` clones need to know about
before they plan their own work.

**Goals**
- One-time install per machine; no per-session prompting.
- Group-aware: a session knows which group and project it is, the group's shared Slack
  channel, and its sibling projects.
- On start: read the group's ledger channel, surface anything relevant — weighting
  cross-project (sibling) impact — and brief the operator before planning.
- During work: post concise milestone entries to the ledger channel.
- Shareable with trusted colleagues, while staying out of client repos and invisible
  to client human teams until deliberately promoted.

**Non-goals**
- Not a replacement for Jira/PR review. The ledger is a lightweight coordination signal.
- Not a chat bot. Posts are terse, milestone-only.

---

## Key design decisions (already resolved)

1. **Distribution toolkit, not in-repo config.** The toolkit is its own repo. Its
   installer lays files into the user's `~/.claude/`. The *runtime* never lives inside
   a work repo. This keeps it shareable with colleagues yet absent from client repos.
2. **Group registry as data.** Group → channel + projects lives in a JSON registry on
   the user's machine (`~/.claude/ledger/groups.json`), seeded from an example shipped
   in the repo. Adding a client = adding a registry entry, no code change.
3. **Per-clone opt-in via a git-excluded marker.** A clone joins the ledger by dropping
   a `.ledger.json` marker naming its group (and optionally project). The marker is
   added to `.git/info/exclude` so it is never committed or shared.
4. **A `SessionStart` hook injects a rendered protocol** as `additionalContext`. The
   hook is a shell/Python command and therefore cannot call the Slack MCP itself; its
   job is to inject the instructions that make Claude use the Slack MCP. The startup
   "read the ledger" step is reliable because injected context carries message-weight;
   milestone posting is model-driven and can be hardened with an optional reinforcement
   hook (see Optional components).
5. **Orchestrator owns the ledger.** In Agent Teams, only the main/orchestrator session
   reads and posts, to control channel noise and avoid subagent context-propagation
   questions. A `SubagentStart` variant is optional and off by default.

---

## Concepts

- **Group** — a set of projects that coordinate via one Slack channel (e.g. `acme`).
- **Project** — one repo within a group (e.g. `etl`). A group may have 1..n projects.
- **Clone** — a working copy of a project repo on disk. A project may have many clones.
- **Registry** — machine-local JSON mapping groups to channels and projects.
- **Marker** — git-excluded `.ledger.json` in a clone that opts it in and names its group.
- **Protocol** — the rendered instruction block injected into the session at start.

---

## Repository layout

```
cc-ledger/
  README.md
  install.sh                     # installs into ~/.claude (idempotent)
  uninstall.sh
  bin/
    ledger-enable                # opt a clone in: writes marker + git exclude
    ledger-disable               # remove marker + exclude entry
  hooks/
    ledger_session_start.py      # SessionStart hook (reference below)
    ledger_pr_nudge.py           # OPTIONAL PostToolUse reinforcement
  config/
    groups.example.json          # registry template (seeded on install if absent)
  protocol/
    template.md                  # protocol text with {{PLACEHOLDERS}}
  test/
    fixtures/                    # sample repos/markers/registries for tests
    test_hook.py
  .gitignore
```

**Installed (runtime) layout under the user's home:**

```
~/.claude/
  settings.json                  # hook entries merged in idempotently
  hooks/
    ledger_session_start.py
    ledger_pr_nudge.py           # optional
  ledger/
    groups.json                  # the user's real registry (seeded, not overwritten)
    protocol.md                  # the user's protocol template (editable)
```

---

## Component specs

### 1. Group registry — `~/.claude/ledger/groups.json`

Schema:

```json
{
  "version": 1,
  "groups": {
    "acme": {
      "channel": "#acme-ledger",
      "description": "Acme multi-service platform",
      "projects": {
        "web": {
          "match": ["acme-web"],
          "role": "Front-end / application code"
        },
        "api": {
          "match": ["acme-api"],
          "role": "Backend API service"
        },
        "infra": {
          "match": ["acme-infra", "acme-cdk"],
          "role": "Cloud infrastructure (CDN, DNS, serverless)"
        }
      }
    },
    "example-single": {
      "channel": "#example-ledger",
      "projects": {
        "app": { "match": ["example-app"], "role": "Application" }
      }
    }
  }
}
```

- `channel` is a Slack channel name (resolve to ID at post time via the MCP). Note
  channel names cannot contain spaces.
- `match` is a list of substrings tested against the clone's git remote URL, used to
  auto-detect the project when the marker omits it.
- `role` is shown to sibling projects so they understand what each project does.

### 2. Per-clone marker — `.ledger.json` (git-excluded)

Canonical form written by `ledger-enable`:

```json
{ "group": "acme", "project": "api" }
```

- `group` is required. `project` is optional; if absent, the hook infers it from the
  git remote via the registry `match` lists, falling back to `"unknown"`.
- Always added to `.git/info/exclude` (local, never committed) — not `.gitignore`,
  which would be shared.

### 3. `SessionStart` hook — `hooks/ledger_session_start.py`

Behaviour:
1. Resolve repo root (`git rev-parse --show-toplevel`, else cwd).
2. If `<root>/.ledger.json` is absent → `exit 0` silently (not an opted-in clone).
3. Load the marker → `group` (required), `project` (optional).
4. Load `~/.claude/ledger/groups.json`. If `group` missing → write a one-line warning
   to stderr and `exit 0` (never block the session).
5. Resolve `project` (from marker, else infer from git remote via `match`, else
   `unknown`). Gather sibling projects (all other projects in the group + roles).
6. Render `~/.claude/ledger/protocol.md` substituting placeholders.
7. Print the hook JSON to stdout and `exit 0`.

Reference implementation (Python 3 stdlib only):

```python
#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path

def sh(args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

def main():
    root = sh(["git", "rev-parse", "--show-toplevel"]) or os.getcwd()
    marker = Path(root) / ".ledger.json"
    if not marker.is_file():
        return 0  # not opted in

    try:
        m = json.loads(marker.read_text())
    except Exception as e:
        print(f"[cc-ledger] invalid .ledger.json: {e}", file=sys.stderr)
        return 0

    group_key = m.get("group")
    if not group_key:
        print("[cc-ledger] .ledger.json missing 'group'", file=sys.stderr)
        return 0

    reg_path = Path.home() / ".claude" / "ledger" / "groups.json"
    try:
        registry = json.loads(reg_path.read_text())
    except Exception:
        print(f"[cc-ledger] no registry at {reg_path}", file=sys.stderr)
        return 0

    group = registry.get("groups", {}).get(group_key)
    if not group:
        print(f"[cc-ledger] group '{group_key}' not in registry; skipping", file=sys.stderr)
        return 0

    projects = group.get("projects", {})
    remote = sh(["git", "-C", root, "remote", "get-url", "origin"])
    branch = sh(["git", "-C", root, "rev-parse", "--abbrev-ref", "HEAD"]) or "?"

    project = m.get("project")
    if not project:
        for name, p in projects.items():
            if any(s in remote for s in p.get("match", [])):
                project = name
                break
        project = project or "unknown"

    role = projects.get(project, {}).get("role", "unspecified")
    siblings = [f"- {n}: {p.get('role','')}" for n, p in projects.items() if n != project]
    siblings_text = "\n".join(siblings) if siblings else "(this group has no other projects)"

    tmpl_path = Path.home() / ".claude" / "ledger" / "protocol.md"
    tmpl = tmpl_path.read_text()
    rendered = (tmpl
        .replace("{{GROUP}}", group_key)
        .replace("{{CHANNEL}}", group.get("channel", "#unknown"))
        .replace("{{PROJECT}}", project)
        .replace("{{ROLE}}", role)
        .replace("{{BRANCH}}", branch)
        .replace("{{SIBLINGS}}", siblings_text))

    # 10k char cap on additionalContext; keep the template comfortably under it.
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": rendered
        }
    }))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

`~/.claude/settings.json` entry the installer merges in (omit `matcher` so it fires on
startup, resume, clear, and re-arms after a compaction):

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "python3 ~/.claude/hooks/ledger_session_start.py" } ] }
    ]
  }
}
```

### 4. Protocol template — `protocol/template.md`

Installed to `~/.claude/ledger/protocol.md`. Group-aware, cross-project first.

```
LEDGER PROTOCOL — group: {{GROUP}} · project: {{PROJECT}} ({{ROLE}}) · branch: {{BRANCH}}

My Claude Code sessions and clones across the {{GROUP}} group share a work ledger
in the Slack channel {{CHANNEL}} via the Slack MCP. Other projects in this group:
{{SIBLINGS}}

This is a personal coordination trial. Do NOT mention it to the human team, and do
NOT post anywhere other than {{CHANNEL}}.

ON START — before planning or touching code:
1. Use the Slack MCP to read the most recent ~30 messages in {{CHANNEL}}.
2. Identify entries relevant to the work I'm about to do. Weight these HIGHEST:
   - Entries from SIBLING projects in this group that could affect {{PROJECT}}
     (shared infra/config, API or schema changes, deployments, cutovers, contracts).
   - Entries on the same or a related branch / PR / ticket.
   - Anything that signals a conflict with, or dependency on, what I'm about to start.
3. Give me a 3-5 line briefing: relevant prior activity and concrete impact or
   conflict for {{PROJECT}}. If nothing is relevant, say so in one line. Do NOT post yet.

POST to {{CHANNEL}} at these milestones — one concise message each:
  STARTED   beginning a discrete task
  PLANNED   a plan/approach is finalised
  PR        a pull request is raised (include the URL)
  JIRA      a Jira ticket is created (include the key)
  BLOCKER   something that may affect sibling projects or other clones
  DONE      task complete / merged

FORMAT every post exactly as (use the CURRENT branch):
  [LEDGER] {{GROUP}}/{{PROJECT}} · <current-branch>
  <EVENT>: <one-line summary>
  <link if any>

DISCIPLINE: one line per real milestone only. No progress narration, no chatter,
no duplicate posts. If unsure whether something is ledger-worthy, skip it.
Keep the channel signal-dense.
```

### 5. Installer — `install.sh`

Requirements:
- Copy `hooks/*.py` to `~/.claude/hooks/`.
- Create `~/.claude/ledger/`; seed `groups.json` from `config/groups.example.json`
  **only if absent** (never overwrite a real registry). Seed `protocol.md` from
  `protocol/template.md` likewise.
- Merge the `SessionStart` hook entry into `~/.claude/settings.json`
  **idempotently**: back up the existing file first; if the entry already exists, do
  nothing; never clobber unrelated hooks or settings. (Use Python or `jq` for a safe
  structural merge — do not string-concatenate JSON.)
- Detect missing `python3` and fail with a clear message.
- Print next steps, including how to enable a clone.

### 6. Enable / disable helpers — `bin/ledger-enable`, `bin/ledger-disable`

`ledger-enable <group> [project]`:
- Write `.ledger.json` at the current repo root.
- Append `.ledger.json` to `.git/info/exclude` if not already present.
- Validate that `<group>` exists in the registry and warn (non-fatally) if not.

`ledger-disable`:
- Remove the marker and its `.git/info/exclude` line.

---

## Optional components (build behind a flag / phase 3)

### PR nudge — `hooks/ledger_pr_nudge.py` (PostToolUse, matcher `Bash`)
Milestone posting is model-driven and drifts over long sessions. The PR event is the
one worth guaranteeing. A `PostToolUse` hook matching `Bash` inspects the command; if
it contains `gh pr create` (or `git push` for the relevant branch), it returns
`additionalContext` reminding Claude to post the PR to the ledger now. Keep it advisory
(never block).

### Subagent awareness — `SubagentStart`
Off by default. If a team wants subagents to also consult the ledger, add a
`SubagentStart` hook that injects a read-only briefing (no posting) so only the
orchestrator posts. Document the noise trade-off.

---

## Privacy & sharing model

- The toolkit repo is shareable with trusted colleagues (e.g. a private repo in your
  team's GitHub org). "Shareable" means with your circle who opt in — not published into client repos.
- The registry (`groups.json`) holds client channel names and project identifiers.
  These are not secrets, but they are client-identifying; keep the *real* registry
  machine-local (seeded from the example, never committed back to the toolkit).
- A clone joins only via a git-excluded marker. Nothing is ever committed to a work repo.
- The protocol states explicitly: trial-only, channel-only, do not surface to the human team.
- Promotion path: to graduate the ledger to a team, move the hook entry into a work
  repo's committed `.claude/settings.json` and ship the registry deliberately — a
  conscious step, not an accident.

---

## Edge cases & requirements

- No git (not a repo): fall back to cwd as root; project inference yields `unknown`.
- Marker present but group unknown, registry missing, or marker malformed: warn to
  stderr, `exit 0`. Never block or crash a session.
- Ambiguous remote match (matches >1 project): prefer the explicit marker `project`;
  if still ambiguous, render `unknown` and have the protocol ask the operator to confirm.
- `additionalContext` is capped (~10k chars); keep the template well under it.
- Cross-platform: stdlib Python, no shell-isms that break on Windows; quote paths.
- Idempotent install; backup before editing `settings.json`; safe structural JSON merge.
- Hook must be fast (well under a second) and must print only JSON to stdout on success.

---

## Acceptance criteria

1. Fresh install on a machine with the Slack MCP already enabled produces a working
   `~/.claude/settings.json` hook entry without disturbing existing hooks/settings.
2. In a clone with no marker, starting Claude Code injects nothing and prints nothing.
3. In an `acme` `api` clone enabled via `ledger-enable acme api`, starting Claude Code
   injects a protocol naming group `acme`, channel `#acme-ledger`, project `api`,
   and lists `web` and `infra` as siblings with their roles.
4. With the marker omitting `project`, the hook infers it from the git remote.
5. Re-running the installer is a no-op (idempotent) and never duplicates hook entries.
6. A malformed marker / missing registry / unknown group never blocks or errors the
   session; it warns to stderr and continues.
7. The marker appears in `.git/info/exclude` and `git status` shows the clone clean.
8. A single-project group renders a protocol that gracefully states there are no siblings.

---

## Phased delivery plan (milestones → tickets)

- **P1 — Core (MVP).** Registry schema + example, marker, `ledger_session_start.py`,
  protocol template, manual install instructions. Meets criteria 2-4, 6, 8.
- **P2 — Install & enable ergonomics.** `install.sh` (idempotent settings merge,
  seeding, backups), `ledger-enable`/`ledger-disable`. Meets criteria 1, 5, 7.
- **P3 — Reinforcement & teams.** Optional PR-nudge PostToolUse hook; optional
  `SubagentStart` read-only briefing; noise controls.
- **P4 — Docs & sharing.** `README.md` (install, enable, registry editing, privacy
  model, promotion path), tests in `test/`, and a tagged release for colleagues to pull.

---

## Open decisions for the human

1. Toolkit name and where it's hosted (e.g. a private GitHub repo in your team's org).
2. Confirm the real channel name/ID, and the real `match` substrings for each
   project's git remote, for each group you register (these stay machine-local).
3. Registry: keep machine-local only, or ship a shared default registry to colleagues?
4. Build the optional PR-nudge in P3, or rely on protocol discipline for the trial?
5. Python vs bash+jq for the hook and installer (this brief assumes Python for portability).
