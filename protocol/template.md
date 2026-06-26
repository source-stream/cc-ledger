LEDGER PROTOCOL — group: {{GROUP}} · project: {{PROJECT}} ({{ROLE}}) · branch: {{BRANCH}}

My Claude Code sessions and clones across the {{GROUP}} group share a work ledger
in the Slack channel {{CHANNEL}} via the Slack MCP.

ARCHITECTURE MAP — route new work to the repo that owns it (← marks this repo):
{{ARCHMAP}}
{{OWN_AREAS}}
WHEN PLANNING OR IMPLEMENTING NEW FUNCTIONALITY:
Consult the ARCHITECTURE MAP above and place each change in the repo whose
responsibility matches it. If the work belongs in a SIBLING repo, do NOT build it
here — say so plainly in your briefing, and post a STARTED/BLOCKER to {{CHANNEL}}
noting the cross-repo handoff so the owning clone can pick it up.

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
