# TOOLS.md - Local Notes

Skills define *how* tools work. This file is for *your* specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:
- Camera names and locations
- SSH hosts and aliases  
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras
- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH
- home-server → 192.168.1.100, user: admin

### TTS
- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## GitHub
- **Username:** lodekeeper
- **Fork:** https://github.com/lodekeeper/lodestar
- **Workflow:** 
  1. Create branch from `unstable`
  2. Make changes, commit
  3. Push to `fork`
  4. Create PR via API

### PR Metadata Hygiene (MANDATORY)
- If PR scope changes after review feedback (or any follow-up commits), re-check that **PR title + description still match the actual diff**.
- If they drift, update both immediately (`gh pr edit <pr> --title "..." --body-file ...`).
- Do this before requesting re-review/merge.
- Example lesson: PR #8986 title/body said pin to `ethspecify 0.3.7` while code was updated to `0.3.9`.

## Lodestar Dev
- **Main repo:** ~/lodestar (always on `unstable`, kept clean)
- **Node:** v24 (use `source ~/.nvm/nvm.sh && nvm use 24`)
- **Build:** `pnpm build`
- **Test:** `pnpm test:unit`
- **Lint:** `pnpm lint` ⚠️ **MANDATORY before every commit/push — no exceptions!**
- **Lint autofix:** `pnpm lint --write`
- **Type check:** `pnpm check-types`
- **Benchmark:** `pnpm benchmark:files <file>`

### File Editing in Worktrees (IMPORTANT)
The `Write` and `Edit` tools are sandboxed to `~/.openclaw/workspace`. For ANY file outside that path (worktrees, ~/lodestar, ~/consensus-specs, etc.), use `exec` directly:
- **Create/overwrite:** `cat > path/to/file << 'EOF' ... EOF`
- **Patch:** `sed -i` for simple replacements
- **Never** attempt `Write`/`Edit` tools on worktree files — it just fails with a noisy error.

### Git Worktrees (IMPORTANT)
Use worktrees to work on multiple branches without cross-contamination:

**Current layout:**
```
~/lodestar                      → unstable (main repo, stays clean)
~/lodestar-6s-slots             → feat/eip7782-6s-slots
~/lodestar-eip8025              → feat/proof-driven-execution (EIP-8025, ON HOLD)
~/lodestar-epbs-devnet-0        → epbs-devnet-0
~/lodestar-lazy-slasher         → feat/lazy-slasher-clean
~/lodestar-proposer-preferences → feat/proposer-preferences
~/lodestar-ptr-compress         → feat/pointer-compression
```

**Commands:**
```bash
# List worktrees
git worktree list

# Create new worktree for a feature
cd ~/lodestar
git worktree add ~/lodestar-<feature> <branch-name>

# Remove worktree when PR is merged
git worktree remove ~/lodestar-<feature>
git branch -d <branch-name>  # optional: delete local branch
```

**Workflow:**
1. New features: branch from `~/lodestar` (always on clean `unstable`)
2. Existing PRs: work in their dedicated worktree
3. Never mix changes between worktrees

### Git Workflow (IMPORTANT)
- **Bringing in upstream changes:** `git checkout feature-branch && git merge unstable`
- **DO NOT force push** - it breaks reviewer history tracking
- Force push = last resort only (when merge truly doesn't work)
- Keep local `unstable` in sync: `git fetch origin && git checkout unstable && git pull`

## Beacon APIs
- **Repo:** ~/beacon-APIs (ethereum/beacon-APIs)
- **Key file:** `validator-flow.md` — validator client ↔ beacon node interaction reference
- **API spec:** `beacon-node-oapi.yaml` (OpenAPI)

## Consensus Specs
- **Repo:** ~/consensus-specs
- **Python env:** `uv run python`
- **Test:** `make test`

## Code Review Workflow
- **Skill:** `skills/lodestar-review/SKILL.md` — full instructions, Lodestar-specific persona prompts
- **Before opening PRs:** Run diff through persona-based reviewers
- **⚠️ WAIT for all sub-agents to finish before posting PR reviews!**
- **Persona prompts:** `skills/lodestar-review/references/<agent-id>.md` — Lodestar-tailored
- See skill SKILL.md for reviewer selection matrix and workflow

### Legacy Reviewers (still available)
- **codex-reviewer:** GPT-5.3-Codex — general code review
- **gemini-reviewer:** Gemini 2.5 Pro — second perspective
- **gpt-advisor:** GPT-5.3-Codex, **thinking: "xhigh"** — architecture & deep reasoning
  - ⚠️ `thinking` is NOT a valid agent config key — MUST pass `thinking: "xhigh"` at spawn time via `sessions_spawn`
  - ⚠️ **Timeout: always use `runTimeoutSeconds: 600` (10min) minimum.** xhigh thinking on complex tasks routinely takes 5-8 minutes. 300s is too tight — caused timeouts on devil's advocate research (2026-03-19), PTC spec review, and multiple earlier sessions. For deep research tasks, use 900s.

## Coding Agents (Implementation)
- **Codex CLI:** `codex exec --full-auto "..."` — best for focused implementation tasks
- **Claude CLI:** `claude "..."` — best for tasks needing broader reasoning
- **lodeloop:** `~/lodeloop/lodeloop.sh` — autonomous loop for multi-story features
  - Repo: https://github.com/lodekeeper/lodeloop
  - Default to Codex (`-a codex`)
  - Creates task.json → loops agent → verification gates → circuit breaker
  - Use for features with 2+ stories; use direct CLI for single tasks
- **Context file:** Always point them to `~/.openclaw/workspace/CODING_CONTEXT.md`
- **Always use PTY:** `exec pty:true workdir:~/lodestar-<feature> command:"codex ..."`
- **Parallel OK:** Spawn multiple in separate worktrees

## GitHub Notifications
- **Check for NEW activity:** `gh api notifications?participating=true --jq '.[] | select(.unread or (.updated_at > .last_read_at))'`
  - IMPORTANT: Just checking `.unread` misses new comments on already-read threads!
- **Mark as DONE (not just read):** `gh api -X DELETE notifications/threads/{thread_id}`
- Always mark notifications as done after addressing them

## GitHub Review Comments
- **Reply to review comments in-thread** (not as separate PR comment!)
- **Get all comments:** `gh api repos/{owner}/{repo}/pulls/{pr_number}/comments --jq '.[] | {id, path, author: .user.login, body}'`
- **Reply in-thread:** `gh api -X POST repos/{owner}/{repo}/pulls/{pr_number}/comments -f body="..." -F in_reply_to={comment_id}`
- DON'T use `gh pr comment` for review responses - that creates a standalone comment
- DON'T use `/pulls/comments/{id}/replies` - that endpoint doesn't exist!
- **Read ALL comments** when checking PR feedback, not just the last one!

---

Add whatever helps you do your job. This is your cheat sheet.

## CI Auto-Fix Pipeline
- **Cron ID:** `573d18ec` (hourly, Codex GPT-5.3)
- **Detector:** `scripts/ci/auto_fix_flaky.py` — scans unstable CI for flaky sim/e2e failures
- **Prompt:** `scripts/ci/CRON_PROMPT.md` — instructions for the cron agent
- **Tracker:** `memory/unstable-ci-tracker.json` — avoids re-investigating known failures
- **Scope:** Tests (E2E, Browser), Sim tests, Kurtosis sim tests on `unstable` only
- **Auto-fixable patterns:** shutdown-race, peer-count-flaky, timeout, vitest-crash
- **Flow:** detect → classify → Codex fixes → PR against unstable → announce

## Grafana (Lodestar Monitoring)
- **URL:** https://grafana-lodestar.chainsafe.io
- **Token:** stored in `$GRAFANA_TOKEN` (set in `~/.bashrc`)
- **Role:** Read-only Viewer
- **Prometheus datasource ID:** 1
- **Loki datasource ID:** 4
- **Skills:** `skills/release-metrics/` (Prometheus), `skills/grafana-loki/` (Loki logs)

## Discord
- **Bot:** @lodekeeper (ID: 1467247836117860547)
- **Server:** ChainSafe (593655374469660673)
- **Channel:** #🖥-lodestar-developer (1197575814494035968)
- **Mode:** Mention required (@lodekeeper)

### Discord Mentions (IMPORTANT)
Plain text `@username` does NOT ping users on Discord. Use proper Discord mention format:
- **Nico:** `<@586161934425128960>` (not `@nflaig`)
- **Matthew Keil:** `<@931591385545584640>` (not `@matthewkeil`)
- **MEK (bot):** `<@1484133729092763808>`
- **lodekeeper-z (bot):** look up ID from channel reads
Always use `<@USER_ID>` format in message sends to actually ping someone.
