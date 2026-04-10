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

### Diff Verification (MANDATORY)
**Always double-check the diff before pushing AND after the PR is open:**
1. **Before push:** `git diff main...HEAD` (or `unstable...HEAD`) — verify only intended files/changes, no stray files (TASK.md, CODING_CONTEXT.md, etc.)
2. **After push / PR open:** Check the GitHub diff in the browser or via `gh pr diff <number>` — confirm it matches what you expect
3. **No "it looks fine" assumptions** — actually read the diff each time
- Lesson: PR #3416 had a stray `TASK.md` and an overly aggressive guard that broke the close() flush path. Both caught by Nico asking "does the diff look good?" — I should have caught them myself.

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
  - ⚠️ **Timeout: always use `runTimeoutSeconds: 3600` (1h).** Nico's directive (2026-03-20): use 1h timeout for all gpt-advisor runs. xhigh thinking on complex tasks can take 5-10+ minutes, and 600s still timed out on the fork-narrowing spec (2026-03-20). Never reduce thinking level to work around timeouts — increase the timeout instead.

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

## Codex CLI Sandbox Fix
- **Issue:** `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`
- **Root cause:** bwrap 0.9.0 (Ubuntu 24.04) non-setuid doesn't write `uid_map` in unprivileged mode → child has no capabilities in user namespace → can't configure loopback in network namespace
- **Fix:** `use_legacy_landlock = true` in `~/.codex/config.toml` under `[features]` — uses Landlock LSM instead of bwrap for sandboxing
- **Date fixed:** 2026-03-27

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
- ⚠️ **Exec session gotcha:** `GRAFANA_TOKEN` is NOT auto-loaded in `exec` shells — must run `eval "$(grep '^export GRAFANA' ~/.bashrc)"` before queries
- ⚠️ **Heredoc scripts blocked** by obfuscation detector in exec — use individual `curl` calls instead

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

## Oracle / ChatGPT on this server
- **Direct working path:** `scripts/oracle/chatgpt-direct`
  - Camoufox-based ChatGPT automation
  - Best choice when I want ChatGPT Pro/browser access on this headless server
- **Oracle-style wrapper:** `scripts/oracle/oracle-browser-camoufox`
  - Simpler alias: `scripts/oracle/oracle-browser`
  - Uses `oracle --render --render-plain` for prompt+file bundling, then sends the rendered bundle through the working Camoufox path
  - Supports the common workflow plus a few Oracle-ish compatibility flags: `--auth-only`, `--cookies`, `--engine browser`, `--wait`, `--slug`, `--browser-model-strategy`, `--browser-inline-files`
  - Use this instead of `oracle --engine browser` when I want Oracle-like browser workflow without fighting Chromium/CDP + Cloudflare
- **Docs:** `scripts/oracle/README.md`
- **Verification:** `scripts/oracle/check-wrapper.sh` (use `--live` for auth/pro + browser smoke checks)
- **Current caveat:** stock Oracle browser mode is still unreliable here because the Chromium/CDP path hits launch quirks and/or Cloudflare anti-bot; prefer the wrapper unless explicitly testing Oracle-native browser behavior

## Backlog inspection
- **Safe helper:** `scripts/backlog/list_statuses.py`
  - Use this to inspect `BACKLOG.md` headings/status lines instead of ad-hoc inline `python3 -` snippets.
  - Example: `python3 ~/.openclaw/workspace/scripts/backlog/list_statuses.py --active-only`
- **Why:** two separate runaway `python3 -` processes (2026-04-08, 2026-04-10) were caused by brittle inline loops that only advanced on `### ` headings and spun forever on `## ` section headers.

## Review Royale
- **API:** http://127.0.0.1:3456 (public: https://review-royale.nflaig.dev)
- **Repos:** ChainSafe/lodestar, ChainSafe/lodestar-z
- **Useful endpoints:**
  - `GET /api/leaderboard?period=week|month|all&limit=10` — global leaderboard
  - `GET /api/repos/:owner/:name/leaderboard?period=week|month|all&limit=10` — per-repo
  - `GET /api/users/:username` — user profile
  - `GET /api/users/:username/stats` — detailed stats
  - `GET /api/achievements` — achievement catalog
  - `POST /api/recalculate` — recalculate all XP
  - `POST /api/categorize` — categorize uncategorized comments
- **When someone asks about leaderboard, stats, reviews, XP, achievements, or roasts:** query the API and respond naturally. No special commands needed — just understand the intent and fetch the data.
- **Docker:** `review-royale-api-1` (port 3456→3000), `review-royale-rr-postgres-1`, `review-royale-rr-redis-1`
- **Crons:** weekly-digest (Tue 05:00), achievements (every 6h), post-sync-pipeline (every 6h offset)
- **Config:** `~/review-royale/docker-compose.yml`, `~/review-royale/docker-compose.override.yml`
