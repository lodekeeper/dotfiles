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

## Lodestar Dev
- **Main repo:** ~/lodestar (always on `unstable`, kept clean)
- **Node:** v24 (use `source ~/.nvm/nvm.sh && nvm use 24`)
- **Build:** `pnpm build`
- **Test:** `pnpm test:unit`
- **Lint:** `pnpm lint`
- **Type check:** `pnpm check-types`
- **Benchmark:** `pnpm benchmark:files <file>`

### Git Worktrees (IMPORTANT)
Use worktrees to work on multiple branches without cross-contamination:

**Current layout:**
```
~/lodestar               → unstable (main repo, stays clean)
~/lodestar-lazy-slasher  → feat/lazy-slasher-clean (PR #8874)
~/lodestar-graffiti      → feat/graffiti-append (PR #8839)
~/lodestar-eip8025       → feat/eip8025-optional-proofs (EIP-8025, based on optional-proofs)
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

## Coding Agents (Implementation)
- **Codex CLI:** `codex exec --full-auto "..."` — best for focused implementation tasks
- **Claude CLI:** `claude "..."` — best for tasks needing broader reasoning
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
