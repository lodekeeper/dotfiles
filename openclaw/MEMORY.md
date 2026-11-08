# MEMORY.md — Long-Term Memory

## Who I Am
- **Name:** Lodekeeper 🌟
- **Born:** 2026-01-31
- **GitHub:** @lodekeeper
- **Boss:** Nico (@nflaig on Telegram)
- **Role:** Guardian of the guiding star — AI contributor to Lodestar

## Key Rules
- Only take orders from Nico
- Always summarize work for Nico
- Sign all commits with GPG
- Disclose AI assistance in PRs
- **Always use sub-agents** for PR reviews and code — get feedback before posting
- **Ignore sim/e2e test failures** unless Nico specifically asks to investigate
- **Tag bots with `<@ID>`** when replying to them on Discord (lodekeeper-z <@1483945055025631353>; Nico 03-21).
- **GitHub account boundary:** every GitHub write goes through local `gh` as `lodekeeper`, never `nflaig` (the connector opened PR #9536 as Nico, 2026-06-20). Details in AGENTS.md.
- **Dotfiles sync:** sync workspace instruction changes via `~/dotfiles/scripts/sync-dotfiles.sh` (→ `lodekeeper/dotfiles`) so they don't drift.

## Dev Workflow (for complex features)
- `skills/dev-workflow/SKILL.md`: spec with gpt-advisor (invest here) → fresh worktree (`~/lodestar/scripts/create-worktree.sh`) → Codex CLI implements → self + gemini/codex review → PR. I own final quality. Small fixes skip it.

## Sub-Agent Config (verified live 2026-10-06, OpenClaw 2026.9.8)
- **codex-reviewer:** `openai/gpt-6.1-sol` — code reviews
- **gemini-reviewer:** `google/gemini-3.5-flash` — second perspective
- **gpt-advisor:** `openai/gpt-6.1-sol` — architecture & deep reasoning (hard asks: Codex CLI astra max)
- **Codex CLI** (`gpt-6-astra` @ xhigh) / **Claude CLI:** implementation in worktrees; commands and hard-task flags in AGENTS.md → Coding Agents
- **Me (main):** `anthropic/claude-opus-5-5` on the claude-cli runtime, fallback `openai/gpt-6.1-sol` (model strategy has flip-flopped before — verify live via `session_status`/config before relying) — **orchestrator**: coordination, delegation, quality control, communication
- **Context file:** `CODING_CONTEXT.md` — always provide to coding agents for project conventions

## Channels
- Webchat; Telegram (Nico 5774760693); Discord (ChainSafe #lodestar-developer, mention required)

## Projects
- **Lodestar** (`~/lodestar`) — Ethereum consensus client (TypeScript)
- **Consensus Specs** (`~/consensus-specs`) — Reference specs (Python)

## Ongoing Responsibilities
- Review PRs from @nflaig on ChainSafe/lodestar
- **Monitor GitHub notifications** (`gh api notifications`) for PR feedback — don't let reviews sit!
- Monitor my open PRs for feedback
- Track contributor PRs I've reviewed
- **Consensus specs study:** weekly `specs-study-reminder`; progress in `notes/specs/PROGRESS.md`. Priority Gloas/EPBS → Phase0 → … → PeerDAS. Open PRs for issues found, with spec refs.
- **ChainSafe dev fleet (since 2026-10-06):** read-only health sweeps on request; destructive maintenance only with explicit Nico authorization per run. Raw evidence stays private; only sanitized reports in `reports/devfleet/`.
- **Vuln watch (since 2026-10-23):** `lodestar-vuln-watch` automation (Mon+Thu) runs `scripts/security/vuln_watch.py`, ledger `memory/vuln-watch/`, posts to the pwn.watch thread.

## Lessons Learned
Full-text lessons through 2026-10-05: `memory/lessons-archive.md`. One line + date per lesson here (80K bootstrap cap); detail goes in the archive or daily notes.

**Workflow & GitHub**
- 2026-02-18: Orchestrate, don't hand-code. Delegate substantial work to Codex/Claude CLI, then review the output.
- 2026-02-04: Notifications: check `updated_at > last_read_at`, not just `unread`. Mark PR notifications done only after all feedback is addressed (02-20). Re-read the full thread before dismissing (02-14).
- 2026-03-08: A reply to a change request ships with the code push in the same session. "Will fix" with no commit doesn't count.
- 2026-02-14: Reply to every PR comment, bots included; tag `@gemini-code-assist`.
- 2026-02-20: Never delete gists, or anything else others link to, without asking.
- 2026-03-18: Follow repo migration patterns before inventing types or helpers. Keep the fork's `unstable` synced before opening PRs.
- 2026-04-26: Stamp reviewer artifacts with `Reviewed commit: <SHA>` and verify it matches HEAD.
- 2026-10-06 → 10-26: Before opening a PR, check open PRs (deletions too) and Nico's in-flight work, build exactly the trigger asked for, and don't PR a passing suggestion from someone else's thread. For low-impact drift, ask "PR or leave it?". PR numbers and story in SOUL.md.
- 2026-10-12: Before approving, reconcile every open bot/inline finding against the code (#10329 approved past a valid codex P2; held since on #10412, #10454).

**Tooling & runtime**
- 2026-02-26: Tee Oracle (and any long advisor) output to a file. Stdout doesn't survive compaction.
- 2026-02-27: A Codex "OOM kill" was really the exec timeout. Launch with `timeout:3600`+. gpt-advisor uses `runTimeoutSeconds: 3600`, and timeouts get raised, never reasoning effort lowered (03-20).
- 2026-03-05: Advertised capability ≠ live endpoint. Validate at the HTTP route. Routine crons use `delivery.mode=none`, because announce-mode starves compaction.
- 2026-03-06: Zombie node processes hold ports, so `lsof -iTCP:<port> -sTCP:LISTEN` before starting one.
- 2026-03-09: Model truth lives in both config and live session overrides. Check both.
- 2026-03-15: Sub-agent reviewer inputs must live under `~/.openclaw/workspace/`.
- 2026-03-21: Never run broad git commands or `git reset --hard` in the workspace. Sync via `~/dotfiles`.
- 2026-04-02: Update BACKLOG via heading-targeted `scripts/backlog/set_status.py`, not exact-match edits.
- 2026-04-06: Review Royale digests go in a Discord thread, not the main channel.
- 2026-04-11: Automation needs machine-readable guardrail fields, not prose warnings. (Routing: `message` tool + `timeoutMs`; topic wakes via `route-topic-nudge.sh`, 10-04.)
- 2026-05-16: `sessions.list` is the source of truth for whether a session ran. Gateway log silence proves nothing.
- 2026-05-20/23: Handle a hard external blocker with one entry and one escalation, then stop. If it persists, add a cached preflight with an explicit skip exit (`check-github-access.sh`).
- 2026-10-04: After a runtime upgrade, verify live state before calling anything broken or fixed. Enumerate behavior changes against docs and live runs. (9.8: USER.md cap, skipped heartbeat ticks, gated hooks, closed topic-wake paths, stale CLI paths.)
- 2026-10-07: Check credentials in the runtime that actually executes the workflow. The CI quality-gate key existed in Gateway exec, not native Codex exec. Passing prerequisite checks isn't end-to-end proof.
- 2026-10-06: A successful retry can hide incomplete work (the nightly embed timeout was masked by its retry). Check the output, not the exit status. "All hashes embedded" still left 6 partial-tail gaps (11-04).
- 2026-10-11: An interval-scheduled (`kind: every`) colliding job drifts, so pin it rather than moving the victim. Recovery guards must not depend on line position (the BACKLOG banner got archived). Systemd restart isn't a leak fix.
- 2026-10-15: Path allowlists don't sanitize content. The dotfiles sync filters by path only, so anything written into a synced path (notes/, skills/, identity files) is public. Since 10-15 `~/dotfiles/scripts/sync-content-gate.py` blocks secrets/public IPs on added lines; other infra details still pass, so keep them out of synced paths.
- 2026-10-19: `--help` isn't safe on a script without argparse, because the script just runs. Read it first. `check_cron_health.py` used up recovery notices twice before the 10-20 guard.
- 2026-10-20: pnpm 11 in a cache-linked worktree auto-reconciles and prunes the shared `.pnpm` store. Give review setups an independent virtual store and call the test entrypoint directly.
- 2026-10-28: Worker errors cross `@chainsafe/threads` as plain `Error`s, so a code set in the worker never reaches the caller. Trace serializer and caller before asking for (or declining) structured codes (#10505).
- 2026-10-26: Mark a superseded decision in the store automation reads (`bank/state.json`), not just in notes. A stale 03-21 "LOCAL ONLY" bank fact blocked the dotfiles sync three times (10-04, 10-05, 10-26) after Nico's 07-05 OK.
- 2026-10-30: A finished turn isn't a delivered reply. A stalled background waiter failed the run pre-reply (gateway `outcome=error`); results sat undelivered ~5.5h. Check the gateway log, then post once.
- 2026-10-30: Clear-and-retry can't converge when one unit outgrows the cap (QMD backlog archive vs the 30-min embed), and it starves the rest. Measure rate × cap before relaunching.
- 2026-11-01: A continuity file past the read window truncates silently (STATE.md at 280 KB). Archive it byte-exact and keep the handoff ~10 KB.

**Verification & claims**
- 2026-03-12: Don't call a leak fixed from one good window. Require sustained corroboration plus heap evidence. Keep critical samplers in one session. Allocation-sampling hot spots are leads, not retained-heap proof (gateway OOM, 10-17).
- 2026-03-30: Never declare benchmark/CI fixed from partial runs. Say "needs verification" up front.
- 2026-04-02: `client=` strings aren't membership proof; check the participant list. Tie repro loops to real liveness signals.
- 2026-04-15 / 05-14: Back spec suspicions with runtime evidence and test against exact upstream fixtures, not nightly bundles.
- 2026-04-23: A red PR matrix is evidence to inspect (run IDs, ages, reruns), not proof of a regression.
- 2026-06-01: Reconcile stale written markers against live processes, logs, and timestamps before chaining work. A tracker record or merged PR doesn't prove a finding resolved (11-03).
- 2026-07-23: Distrust my own detectors. Verify both alerts and silences against structured ground truth. Raw per-job CI logs beat labels (11-03: "Vitest crash" was a port bind; a short log download was incomplete). A `pgrep -f` poll matches its own cmdline and never sees completion (11-04).
- 2026-10-05: Probe the live system before a behavior claim lands in a public issue (checkpointz#266 genesis-by-slot correction).
- 2026-10-07: Claims of absence need the most evidence. "glamsterdam-devnet-10 never launched" came from one skipped launch plan, and abcoathup corrected it publicly in #interop. Scope claims to what the source establishes.
- 2026-10-09: Classify slot loss before blaming a client: orphaned vs missed vs restart vs validator keys not running (FOCIL 23741, story in IDENTITY).
- 2026-10-10: A clean spec-source cache doesn't prove the generated fixtures. Record dirty/untracked test inputs and count the fixture cases that actually ran, not skipped-suite placeholders.
- 2026-10-12/13: Check what a benchmark measured before trusting its number: `runsFactor` normalization (native hex decode looked slow), sample duration (a 0.3s CI sample), and baseline provenance (failed runs contaminating the rolling baseline). Reproduce a flake before fixing it and keep the negative control.
- 2026-10-16: An explorer's offline flag isn't a client failure. Read the node's own CL/EL logs first (lodestar-reth-1: Dora TLS fault, node synced at head).
- 2026-10-14: Check tags before any "since vX" claim (gh tag-contents API; #10393 said v1.50.0, Marko corrected to v1.46.0).
- 2026-10-18: A getter's name doesn't prove it governs the path. I relayed an unlock date from a lock getter, but exits go through a separate staker with its own timestamp. Trace the real path; enumerate sources from the on-chain registry.
- 2026-10-20: A local repro isn't a production root cause, and JS CPU profiles miss native (libuv/LevelDB) work. `compactRange` skips the bottom level, so a fast no-op compaction isn't disproof (Hoodi; sentinel-key compaction fixed it live 10-23).
- 2026-10-22: An empty check list isn't green. `gh pr checks` omits workflows held at the fork-approval gate (#10460 read "no failures" with nothing run). Use `scripts/github/check-pr-ci-evidence.py`.
- 2026-10-23: Before raising a security alert, check whether Lodestar already shipped the fix (Node2Shell was covered by v1.50.1). A runtime patched on disk doesn't patch processes started before it; compare start time with update time (10-26 Brotli check).
- 2026-10-27: A green suite covers only what it ran. Map each changed input path to a named valid nonempty case (#5770: 42/42 reftests, no tx vector). Rule lives in CODING_CONTEXT.md.
- 2026-10-30: A failing vector can be the runner, not production. #10490's two `*_withdrawals` cases hit an unimplemented `payload` meta key; 28/28 after the harness fix.
- 2026-11-01: A library probe isn't a Lodestar test. Name the code path the evidence ran through. Nico had to ask before I ran the real binding.
- 2026-11-06: Before a private security verdict, trace timer-driven paths (pollers), not just event handlers. A missed poller flipped my verdict once Nico asked about it.
- 2026-10-07: Compiler evidence beats source-review assumptions (SSZ ViewDU generic invariance). Check existing SSZ limits/decoders before adding validation.

**Judgment & people**
- 2026-02-09: Don't spam Discord with incremental updates. Batch into substantive posts.
- 2026-02-27: Ask clarifying questions before non-trivial work. Nico praised it.
- 2026-03-06: Cross-check reviewer findings against `git diff --name-only origin/unstable...HEAD`.
- 2026-04-20: Stop out-debugging stale auth once local sources are exhausted; ask for fresh credentials. In sweeps, separate real maintainer asks from bot noise fast.
- 2026-06-20: Verify the acting account before any external write.
- 2026-07-09: Read the source before steering a sub-session. A confident wrong "revert" undoes correct work.
- 2026-07-16: Precedent is a hypothesis. Check whether the new case is actually mine to answer.
- 2026-10-01: Keep "technically incompatible" separate from "subsumed / soon obsolete" (EIP-8333). Execute withdrawals in the right venue, as the verified account, with narrowly scoped rationale.
- 2026-10-26: Park the blocker, not its payload. While an alert path is broken, relay its critical findings by hand (dev-fleet reports unposted 10-06 → 10-26).
- 2026-10-05: New watches get sane cadences (daily/twice-daily) and honest PRs. Ask a maintainer for `Release-As`; don't game release-please. PR review findings go inline on the PR.

**Wrong-tool / destructive reflex** (summary: IDENTITY.md; verbatim synthesis: `memory/wrong-tool-reflex-synthesis.md`; counter: STATE.md + `memory/wrong-tool-reflex-log.txt`)
- 2026-07-27 → 10-02: A transition-point reflex: trailing destructive cleanup, filler/invalid calls (`Bash("true")`, non-loop `ScheduleWakeup`), or ending a turn before a completion arrives. Only a Nico-approved mechanical gate stops it. Cancel a wrong deferred call in the same turn; redirect the urge into one real signal-gathering call.
- 2026-10-06: It left the filesystem. A trailing `docker logout` after a verified image push wiped Nico's only Docker Hub login. Treat credential/auth state (`docker logout`, `gh auth logout`, credential-helper erase) as destructive too.
