# HEARTBEAT.md

## 📣 Output Routing (single source of truth)
Use this routing for **all heartbeat / routine-status flows**.

### Destinations
- **Routine updates** (heartbeat/backlog/status, non-urgent) → send to Lodestar WG **topic #347** via `sessions_send`:
  - `agent:main:telegram:group:-1003764039429:topic:347`
- **Urgent/blocker/critical deliverable** → send to Nico DM via `sessions_send`:
  - `agent:main:telegram:direct:5774760693`

### Hard guards
- Never post routine heartbeat output in Nico DM.
- Never post heartbeat output in Lodestar WG topic #1 (General/control thread).
- In DM or topic #1 heartbeat contexts, final local output must be exactly `NO_REPLY`.
- Do **not** use `message action=send` from DM heartbeat flows; use `sessions_send` routing only.

### DM send gate (mandatory)
Before sending anything to Nico DM from a heartbeat flow, all of these must be checked:
1. Is this a blocker?
2. Is this an urgent decision request?
3. Is this a critical deliverable Nico explicitly needs in DM?
- If **all answers are no** → output `NO_REPLY`.

## ⚠️ STEP 1: BACKLOG — DO THIS FIRST, BEFORE ANYTHING ELSE
1. Read `BACKLOG.md` right now
2. Look for any task that is NOT marked ✅ and is NOT a passive "monitor/watch" item
3. **If an actionable task exists:**
   - **If task is tagged `[topic:ID]`** → do NOT work on it here. Instead:
     1. Check the task status in BACKLOG.md — is it blocked/awaiting input, or ready for more work?
     2. If ready for work: nudge the topic session via `sessions_send` with sessionKey `agent:main:telegram:group:-1003764039429:topic:<ID>` and a message like "Continue working on <task>. Current status: <status from backlog>. Next step: <next subtask>. IMPORTANT: Update BACKLOG.md (~/.openclaw/workspace/BACKLOG.md) with your progress — mark subtasks ✅ as you complete them, add new subtasks as discovered."
     3. **Anti-spam guard:** if you already nudged the same topic in the last ~30 minutes and there is no status change/new blocker/new decision point, skip repeat nudges.
     4. If blocked/awaiting: skip it, just note it's blocked.
     5. Report briefly what you nudged (or why you skipped). NOT HEARTBEAT_OK.
   - **If task is NOT topic-tagged** → WORK ON IT in this session.
   - Set it to "in progress" in BACKLOG.md immediately
   - Update dashboard: `~/lodekeeper-dash/scripts/update-status.sh working "<task>"`
   - Do the work. Reply with what you did. NOT HEARTBEAT_OK.
   
   **Topic session keys:** `agent:main:telegram:group:-1003764039429:topic:<ID>` (Lodekeeper WG forum)
4. If the only remaining items are passive monitoring (awaiting review, watching threads) → proceed to Step 2
5. Add any new tasks discovered from notifications/Discord
6. If a newly discovered task is a **bigger development task**, create a dedicated Lodestar WG topic automatically (`message action=topic-create`) and tag backlog with `[topic:ID]`. If the scope is borderline, ask Nico.

**The failure mode to avoid:** Running all the monitoring checks below, seeing "nothing new", and replying HEARTBEAT_OK while an actionable task sits untouched in the backlog. Monitoring is Step 2. Backlog work is Step 1.

## Keep dashboard status fresh
- Working on a task → `~/lodekeeper-dash/scripts/update-status.sh working "<task>"`
- Genuinely idle (only monitoring) → leave it, auto-idle is correct
- **Never** set "working" for heartbeat polling itself

## STEP 2: Monitoring (only after confirming no actionable backlog tasks)

**Automation ownership:**
- GitHub notifications: cron `github-notifications` (every 3 min)
- Open PR CI watch: cron `monitor-open-pr-ci` (every 30 min)
- Unstable CI autofix: cron `ci-autofix-unstable`
- Dotfiles sync: cron `Sync dotfiles repo` (every 6h)
- Weekly autonomy audit: cron `self-improvement-audit-weekly`
- Identity-file review: cron `review-identity-files` (every 3 days)
- Periodic cleanup: cron `workspace-periodic-cleanup` (every 6h)

Heartbeat should not duplicate these cron-owned checks unless Nico asks or a cron is failing.

## Monitor my Discord threads / mentions
Discord mentions are push-based (instant delivery) and remain monitored through normal incoming events.
Use `memory/discord-threads.json` for tracked thread context when needed.

## 🧹 Periodic cleanup (every ~6 hours)
- Automated by dedicated cron job: `workspace-periodic-cleanup` (id `92fa6d55-4abe-47d4-b0a6-3b9af366b444`).
- Heartbeat should not run this cleanup loop manually anymore unless cron is failing or Nico asks explicitly.
