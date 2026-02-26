# HEARTBEAT.md

## ⚠️ STEP 1: BACKLOG — DO THIS FIRST, BEFORE ANYTHING ELSE
1. Read `BACKLOG.md` right now
2. Look for any task that is NOT marked ✅ and is NOT a passive "monitor/watch" item
3. **If an actionable task exists → WORK ON IT. Do not proceed to monitoring.**
   - Set it to "in progress" in BACKLOG.md immediately
   - Update dashboard: `~/lodekeeper-dash/scripts/update-status.sh working "<task>"`
   - Do the work. Reply with what you did. NOT HEARTBEAT_OK.
4. If the only remaining items are passive monitoring (awaiting review, watching threads) → proceed to Step 2
5. Add any new tasks discovered from notifications/Discord

**The failure mode to avoid:** Running all the monitoring checks below, seeing "nothing new", and replying HEARTBEAT_OK while an actionable task sits untouched in the backlog. Monitoring is Step 2. Backlog work is Step 1.

## Keep dashboard status fresh
- Working on a task → `~/lodekeeper-dash/scripts/update-status.sh working "<task>"`
- Genuinely idle (only monitoring) → leave it, auto-idle is correct
- **Never** set "working" for heartbeat polling itself

## STEP 2: Monitoring (only after confirming no actionable backlog tasks)

**Note:** GitHub notification polling is handled by a dedicated cron (every 3 min, Codex/GPT-5.3). It will alert the main session when action is needed. Do NOT duplicate that check here.

- Discord @mentions arrive instantly (no polling needed), but do a search backup check:
  ```
  message action=search channel=discord query="lodekeeper" guildId=593655374469660673 limit=5
  ```

## Monitor my open PRs CI status
Check CI on all open lodekeeper PRs. If any fail, investigate immediately:
```
for pr in $(gh pr list --repo ChainSafe/lodestar --author lodekeeper --state open --json number --jq '.[].number'); do
  sha=$(gh api repos/ChainSafe/lodestar/pulls/$pr --jq '.head.sha')
  fails=$(gh api "repos/ChainSafe/lodestar/commits/$sha/check-runs" --jq '[.check_runs[] | select(.conclusion == "failure")] | length')
  if [ "$fails" -gt 0 ]; then echo "PR #$pr has $fails failures"; fi
done
```

## Monitor my Discord threads
Check for new messages in threads I created or where I'm mentioned.
Track thread IDs in `memory/discord-threads.json`.

## Monitor unstable branch CI (CONTINUOUS TASK from Nico)
Check latest CI runs on the `unstable` branch. If any failed, investigate and open a PR to fix.
```
gh run list --repo ChainSafe/lodestar --branch unstable --limit 10 --json databaseId,name,conclusion,status,createdAt --jq '.[] | select(.conclusion == "failure") | {id: .databaseId, name, created: .createdAt}'
```
- If failures found: check logs with `gh run view <id> --repo ChainSafe/lodestar --log-failed`
- Investigate root cause, open a fix PR
- Track investigated failures in `memory/unstable-ci-tracker.json` to avoid re-investigating

## 🔄 Sync dotfiles repo (every ~6 hours)
Run `~/dotfiles/scripts/sync-dotfiles.sh` to push local changes to https://github.com/lodekeeper/dotfiles.
Only needed if local files changed (skills, notes, scripts, codex config, lodestar AGENTS.md).

## 🔄 Review identity files (every few days)
- Re-read SOUL.md, IDENTITY.md, MEMORY.md — are they still accurate?
- Add new lessons, update strengths/weaknesses, refine personality notes
- Sync updates to dotfiles/openclaw/ and push

## 🧹 Periodic cleanup (every ~6 hours)
- Remove completed/merged items from this file and BACKLOG.md
- Move done tasks to the "Completed" section in BACKLOG.md
- Clean up stale daily notes older than 7 days (archive key info to MEMORY.md first)
- Keep this file lean — only active/relevant items
