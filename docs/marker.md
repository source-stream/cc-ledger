# The `.ledger.json` marker

A clone joins the ledger by dropping a small **marker** file at its repo root. The
marker is the *only* thing cc-ledger ever places inside a work repo, and it is kept
**local to that clone** — never committed, never shared.

## Schema

```json
{ "group": "acme", "project": "api" }
```

| Field     | Required | Meaning |
|-----------|----------|---------|
| `group`   | yes      | A group key that exists in your registry (`~/.claude/ledger/groups.json`). Selects the Slack channel and the set of sibling projects. |
| `project` | no       | This clone's project within the group. If omitted, the hook infers it by matching the git remote URL against each project's `match` substrings; if 0 or >1 match, it renders `unknown` and the protocol asks you to confirm. |

## It must be git-excluded — via `.git/info/exclude`, never `.gitignore`

The marker is excluded using the clone-local `.git/info/exclude`:

```sh
printf '{ "group": "acme", "project": "api" }\n' > .ledger.json
grep -qxF '.ledger.json' .git/info/exclude || echo '.ledger.json' >> .git/info/exclude
```

**Why not `.gitignore`?** `.gitignore` is itself committed and shared with everyone who
clones the work repo — adding the marker there would advertise the trial and could be
pushed. `.git/info/exclude` is local to your clone and never leaves your machine, so the
marker stays invisible to the client's team. After enabling, `git status` stays clean.

In P2 this is automated by `bin/ledger-enable <group> [project]` and reversed by
`bin/ledger-disable`. Until then, create the marker and exclude line by hand as above.
