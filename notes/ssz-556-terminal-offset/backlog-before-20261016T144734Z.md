# BACKLOG




> **⚠️ DO NOT ACT ON ENTRIES BELOW WITHOUT VERIFYING FIRST.** This file is under recovery. Verify every entry against live ground truth (GitHub / Discord / code) before acting on it. **DO NOT ACT ON ENTRIES BELOW** that you have not independently re-confirmed this session.


## 📌 SSZ PR #556 terminal offset review [topic:50]
- 🟡 🔄 **Verify and address terminal-offset Uint32 overflow** — IN PROGRESS (source: routed GitHub review by chatgpt-codex-connector[bot], https://github.com/ChainSafe/ssz/pull/556#discussion_r4295698907; 2026-10-16 14:27 UTC). Verify exact head and 2^32 fixed-element claim, implement minimal fix if valid, run focused regression/checks, independent review, incremental signed push, in-thread reply, metadata/checklist update.
  - ⚠️ Coordination (Discord #security-issues session, 14:47 UTC): wemeetagain asked for a fixed-size fast path follow-up on #556 (`start + i * fixedSize`, no offsets array, in value_/tree_deserializeFromBytesArrayComposite + ProgressiveList tree). I'm building it in `/tmp/ssz-556-fastpath` and will commit on top of this fix's pushed head, keeping the size check. Please record the pushed sha here and don't touch the PR body bench section. `/tmp/ssz-556` still has an uncommitted copy of the size check + test from an earlier run; I'm leaving it alone.

## 🟡 feat4-mainnet-super stale validator service restart loop (no topic)
- Source: Nico requested fleet health in Discord #lodestar-private, 2026-10-07 15:11 UTC (message 1557410022131109949); discovered in live follow-up at 15:15 UTC.
- Status: ⏸ Awaiting deployment owner decision — read-only diagnosis complete, no service changes authorized by status question.
- Evidence: validator.service enabled; NRestarts 7,647,569→7,647,606 across ~105 seconds; logs reject network `holesky` as invalid. CL and EL remain synced on mainnet. This is newly discovered, not established to have newly started today.
- Next: owner determines whether the stale Holesky validator service should be retired or corrected. Do not guess a replacement network or touch validator keys/slashing data.
- Private evidence: ~/.config/devfleet/reports/health-2026-10-07-1511/feat4-mainnet-super-followup.txt.

## 📌 General (no topic)
- 🟡 **[PR open, awaiting review]** ChainSafe/ssz: make `readVariableOffsetsArrayComposite` always return n+1 offsets (trailing end entry) so the `withEndOffset` flag from ssz#555 isn't needed, and drop the last-element branch in value_/tree_deserializeFromBytesArrayComposite. Source: wemeetagain, Discord #security-issues (1533569045767393483) msg 1560649826616614984, 2026-10-16 13:45 UTC: "open a PR against unstable ... Please separately bench the affected operations." Repo default branch is `master`. Keep the PR body generic with no security context.
  - ✅ 2026-10-16 ~14:35 UTC: opened https://github.com/ChainSafe/ssz/pull/556 (branch `lodekeeper:refactor/array-composite-end-offset`, commit 8ac6df0). The title had to be `chore:` because the title check only allows fix/feat/chore/revert. Unit 1802 passed, spec-generic 5065 passed, spec-static-minimal 13284 passed, lint clean. Node checks, Bun and the title check are green in CI. CI spec tests were pending when I posted.
  - 🔄 2026-10-16 14:39 UTC: wemeetagain (msg 1560663338478862377) said go ahead: fold a fixed-size fast path (`start + i * fixedSize`, no offsets array) into #556 for arrayComposite value/tree deserialize + ProgressiveList tree deserialize, then rerun the A/B benches and refresh the PR body table.
- Bench (A/B interleaved, in PR body): all cases within noise except exactly-16-element lists, which are ~+0.4-0.7us. V8 keeps typed arrays of 64 bytes or less on-heap at ~33ns, and Uint32Array(17) goes off-heap at ~380ns. That hits withdrawals (16 per payload). I offered a follow-up that skips the offsets array for fixed-size elements, not building it unless asked. The reviewer subagent flagged only a wrap for inputs of 2^32 bytes or more (spec-invalid), which is noted in the PR.
- ✅ 2026-10-16 14:20 UTC CI alert was a superseded `Validate PR title` failure (check run 38914926971); subsequent title validations passed by 14:26 UTC and the latest test matrix completed green by 14:29 UTC. No fix needed.
  - Local spec-static-mainnet: 540 passed, added to PR body. CI at ~14:40 UTC: general/altair spec tests pass, phase0/bellatrix pending.
  - Local state: ~/ssz is back on `fix/proof-gindices-push-spread`. Untracked bench files remain at packages/ssz/test/perf/byType/arrayCompositeDeserialize*.test.ts (copies in /tmp/ssz-bench); don't `git add -A` there.
- 🟡 **[awaiting Nico]** #10329 twoeths review 5543029362 (2026-10-16 ~04:20 UTC): post-Gloas a failed getBlobs attempt is never retried. Verified at 5ceacecc319: the only triggers are processBlock (gossipHandlers L685) and unknown sync (L1176), the Gloas column branch never triggers, and #10366 only covers in-flight triggers. Replied https://github.com/ChainSafe/lodestar/pull/10329#issuecomment-6208094324 with a minimal auto-retry sketch (re-enter in retryPendingTrigger on failure, timing caveat vs the L681 TODO) and offered a follow-up to Nico. Not building it unless he says so.
- ✅ [topic:50] #10329 (nflaig) 2026-10-16 03:57 UTC: twoeths agreed in thread r4230927636 (r4290784370) that `callInNextEventLoop` in GetBlobsTracker belongs at the gossip handler level, which backs Nico's removal. The thread is wemeetagain/nflaig/twoeths, I'm not in it and nobody asked me, so no reply.
- ⏸ **[blocked: repo access]** philknows inline comment on ChainSafe/infraopic#102 (r4283285923, 2026-10-15 13:03 UTC). Since sometime after 13:42 UTC 10-15, ChainSafe/infraopic returns 404 for lodekeeper (token has `repo`, repo gone from my private list), so I can't read or reply. Reported in topic #347 (msg 14557) 2026-10-16 01:20 UTC, asking for access or the pasted comment. Checklist item marked done (`repo-access-revoked-404`) to stop reminders.

### 🟡 ChainSafe/lodestar#10412 review (markolazic01 docs CLI comparison)
- **Source:** nflaig on PR, 2026-10-15 22:40 UTC: "is this real?" (codex P2 on cliComparison.mjs:80) and "are we good with this one?"
- **Status:** ✅ Answered (verified live by 22:56 heartbeat): P2 confirmed real, replied in-thread r4289061582 + COMMENT review w/ suggestion 5540870000 (22:50 UTC, "No, not as is"). Head still 4f4b908; awaiting author (markolazic01) — passive watch.

### 🟡 glamsterdam-devnet-12: how Lodestar handled the Gloas fork with the deposit spray
- **Status:** Passive / completed analysis; full findings archived 2026-10-16.
- **Summary:** Deposit-spray analysis completed; detailed client comparison retained in archive.
- **Next:** Re-engage only on new evidence or reviewer/maintainer feedback.

### 🟡 glamsterdam-devnet-12: which CL survives the Gloas-fork builder onboarding with the deposit + invalid-sig spray
- **Source:** Nico, Discord #interop thread (1559954479686877189), 2026-10-15 11:27 UTC: "which client will survive this?" Barnabas added more invalid-sig deposits.
- **Status:** ✅ Answered in thread 2026-10-15 ~12:00 UTC (fork is 13:00 UTC). The queue has 32,151 deposits. 24,438 are builder deposits, 4,206 of them invalid. 7,710 of the 7,713 non-builder deposits are invalid and sit on 3 pubkeys that also have builder deposits, so the literal spec `is_pending_validator` would do 4.37M verifies. No client implements it literally; all memoize per pubkey. Teku has no cache, about 30k inline verifies per upgrade. Nimbus pays about 7.7k uncached 0x01 verifies. LH, Prysm, Grandine and Lodestar are sub-second when warm. Lodestar caveats: pre-verify blocks the main thread about 2.4s/slot for about 25 slots, and states loaded from bytes get a fresh cache, about 45s inline per run. Data and scripts are in `/tmp/dn12/`.

- ✅ [topic:50] PR #10379 (Marko builder) 2026-10-15 10:55 UTC: reviewed Marko's 3-epoch payment settlement reasoning (issuecomment-6180079709, reply to Kris). Mostly right, but qualifying payments move to builder_pending_withdrawals at the end of epoch+1 and the balance (builder uses the raw `builder.balance`) is only debited when a payload processes the withdrawal. Empty-payload runs can lag past the 3-epoch release, though bids only get rejected because can_builder_cover_bid subtracts pending. Commented suggesting the follow-up reconcile against pending payments + withdrawals (issuecomment-6190285666). Checklist item marked done.

### 🔴 Gateway main-process heap leak since 9.8 — OOM-aborts every ~25-32h; latest OOM-abort 2026-10-16 08:37:58 UTC (pid 2527001 → auto-restart pid 1584152 at 08:38:06, 31h52m uptime); prior deliberate restart 2026-10-13 17:46:54 UTC; next OOM projected ~09:40 – 16:40 UTC 10-17 [cron:882f5c1c]
- **Source:** `next-audit-priorities-reminder` cron; recurring main-process OOM, upstream issue #159373 updated with 9.8 data.
- **Status:** Awaiting Nico / upstream; restart reset memory but did not change the ~0.6 GiB/h growth rate.
- **Current blocker / next step:** Re-check hourly heap/RSS trend; continue upstream follow-up as appropriate. Do not restart gateway or change config from a session.
- **2026-10-08 09:30 UTC (`next-audit-priorities-reminder`) — ✅ re-checked, no action possible:** pid 2477401 (since 10-07 16:51:10Z) heap 9.55 GiB / RSS 12 GiB at 09:24Z (~0.75 GiB/h), no crash/restart since; OOM projected ~18:00–19:30Z today. Upstream openclaw#159373 has no maintainer reply; installed 2026.9.8 = latest stable, `v2026.10.1-beta.2` (10-08) notes show no leak fix. Cron-config item 1 (claude-cli fallbacks, 61 days) still Nico-only. Detail: `notes/autonomy-gaps.md` 2026-10-08 bullet.
- **2026-10-09 09:30 UTC (`next-audit-priorities-reminder`) — 🔄 in progress, no lever of mine left:** the 10-08 projection landed: pid 2477401 OOM-aborted at **10-08 20:09:31Z** (27h18m uptime, ~1–2h later than the slope projection), systemd auto-restarted pid 1633730 at 20:09:39Z (not a deliberate restart). Current process hourly heap floors 5.88 (05Z) → 6.38 → 7.03 → 7.52 → 8.31 GiB (09Z), ~0.6 GiB/h, RSS 10.9 GiB, so the next abort is projected ~21:30–23:30Z today. NEW: **v2026.9.9 stable** published 10-08 10:23Z (installed is 2026.9.8); its changelog (`CHANGELOG/2026.9.9.md`) has no heap/leak/RSS entry. Upstream openclaw#159373 still 3 comments, last is mine (10-06). Item 1 (claude-cli fallbacks, 62 days) unchanged. Restart cadence / upgrade to 9.9 / beta stay Nico's call.
- **2026-10-10 09:30 UTC (`next-audit-priorities-reminder`) — 🔄 in progress, no lever of mine left:** the 10-09 projection landed inside its window: pid 1633730 OOM-aborted at **10-09 22:04:31Z** (`FATAL … heap out of memory`, last Mark-Compact 15.8 GiB, `status=6/ABRT`) after 25h55m; systemd auto-restarted pid 656203 at 22:04:39Z (not Nico's restart). Abort series: 10-05 18:04Z, 10-07 14:42Z, 10-08 20:09Z, 10-09 22:04Z (uptimes ~27h/32h/27h18m/25h55m). Current pid hourly heap floors 5.82 (06Z) → 6.08 → 6.64 → 7.16 GiB (09Z), RSS ~9.9 GiB, `level=warning`; next abort projected ~00:00–06:00Z 10-11 (26-32h uptime band). Upstream openclaw#159373 unchanged (3 comments, last mine 10-06); latest stable still v2026.9.9 (no leak entry), latest beta v2026.10.1-beta.2. Item 1 (claude-cli fallbacks, 63 days): live `cron list` unchanged for all four jobs (no `fallbacks`, `delivery.mode: none`, nightly `timeoutSeconds: 900`), all `ok`/0 errors. A planned restart at ~20h uptime (instead of an OOM-abort that SIGKILLs live children) remains Nico's call.
- **2026-10-11 09:30 UTC (`next-audit-priorities-reminder`) — 🔄 in progress, no lever of mine left:** the 10-10 "00:00–06:00Z 10-11" projection never landed because the gateway was **deliberately restarted 10-10 11:25:49Z** (`SIGTERM: gateway.restart`, pid 656203→2347483, ~13.5h uptime, one child SIGKILLed); 0 heap-OOM aborts since 10-09 22:04Z. Current pid 2347483 (22h) hourly heap floors 5.87 (22Z) → 9.07 (04Z, critical) → 11.70 GiB (09Z), latest 12.6 GiB, RSS ~15 GB, slope ~0.53 GiB/h → next abort projected **~14:00–18:00Z today** (uptime ~28–31h); a planned restart/upgrade before then stays Nico's call. NEW: **v2026.10.1 stable** (10-10 23:54Z; installed 2026.9.8): changelog has no leak fix but adds main-isolate heap sampling (#163813/#164057/#164335/#163764) so the leak becomes locatable after an upgrade (first start also does a stopped-Gateway SQLite conversion, #163105). openclaw#159373 unchanged. Item 1 (claude-cli fallbacks, 64 days): `cron list` unchanged (no `fallbacks`, `delivery.mode: none`, nightly `timeoutSeconds: 900`), all four `ok`/0 errors; only red job `workspace-periodic-cleanup` ce=1 = known `publication was superseded` race. Detail: `notes/autonomy-gaps.md` 2026-10-11 bullet.
- **2026-10-11 16:5x UTC (heartbeat-checklist) — projection landed:** pid 2347483 hit `FATAL ERROR: Ineffective mark-compacts near heap limit … JavaScript heap out of memory` at **16:37:19Z** (last Mark-Compact 15.89 GB; 16:34:48 `memory pressure level=critical rss=18.3 GiB heap=15.5 GiB`), `status=6/ABRT` at 16:37:22, after ~29h11m uptime since the 10-10 11:25:49 deliberate restart. systemd auto-restarted it as pid 1726906 at 16:37:27 (`restart counter is at 1`, not a deliberate restart). Collateral: child processes SIGKILLed, several codex/claude children logged `remains running after unit stopped` (orphaned, not touched), and the 16:36:39 heartbeat-checklist run ended `cron: job interrupted by gateway restart` (ce=1). Abort series now 10-05 18:04Z, 10-07 14:42Z, 10-08 20:09Z, 10-09 22:04Z, 10-11 16:37Z. Next abort projected at 26–32h uptime: **~18:30Z 10-12 – 00:30Z 10-13**. Still Nico's call: planned restart cadence, or upgrade to v2026.10.1 (adds heap sampling so the leak can be located).
- **2026-10-12 09:30 UTC (`next-audit-priorities-reminder`) — 🔄 in progress, no lever of mine left:** no heap-OOM abort since the 10-11 16:37Z one above (journal since 10-11 09:31Z: the only `heap out of memory`/`status=6/ABRT` hit is that event). Current pid 1726906 (up ~17h since 10-11 16:37:27Z, no restart) hourly heap floors 5.46 (00Z) → 6.50 (03Z) → 8.49 (06Z) → 10.42 GiB (09Z), latest 10.57 GiB, RSS 13.3 GiB, `level=critical` (threshold 11.8 GiB), slope ~0.55 GiB/h → next abort projected **~18:30–21:30Z today** (26–29h uptime), same band as the heartbeat's. NEW: **v2026.10.2 stable** (10-12 05:34Z; installed 2026.9.8): release body (12 KB) has no heap/leak/OOM/RSS fix (only credential-redaction, Codex app-server client and worker-capacity leak fixes); `v2026.10.5-beta.1` (10-11) not reviewed. openclaw#159373 unchanged (3 comments, last mine 10-06). Item 1 (claude-cli fallbacks, 65 days): `cron list` (28 jobs) unchanged for all four (no `fallbacks`, `delivery.mode: none`, nightly `timeoutSeconds: 900`), all `ok`/0 errors; no job red. Planned restart/upgrade stays Nico's call; no topic post (heartbeat already tracks it). Detail: `notes/autonomy-gaps.md` 2026-10-12 bullet.
- **2026-10-12 22:27 UTC (heartbeat-checklist) — projection landed (slightly early):** pid 1726906 hit `FATAL ERROR: Ineffective mark-compacts near heap limit … JavaScript heap out of memory` at **18:14:26Z**, `status=6/ABRT` at 18:14:29, after ~25h37m uptime. systemd auto-restarted it as pid 707025 at 18:14:34 (`NRestarts=2`, not a deliberate restart). Abort series now 10-05 18:04Z, 10-07 14:42Z, 10-08 20:09Z, 10-09 22:04Z, 10-11 16:37Z, 10-12 18:14Z. Next abort projected at 25–32h uptime: **~19:15Z 10-13 – 02:15Z 10-14**. Still Nico's call: planned restart cadence, or upgrade (v2026.10.1+ adds heap sampling).
- **2026-10-13 09:30 UTC (`next-audit-priorities-reminder`) — 🔄 in progress, no lever of mine left:** the 10-12 projection landed (abort 10-12 18:14:26Z, 25h37m uptime, already logged above); journal since 10-12 09:31Z (4,809 lines) has no other `heap out of memory`/`status=6/ABRT` hit. Current pid 707025 (up ~15h16m since 10-12 18:14:34Z, no restart) hourly heap floors 4.72 (01Z) → 6.30 (04Z) → 7.84 (07Z) → 9.12 GiB (09Z), latest sample 9.31 GiB at 09:25Z, RSS 11.8 GiB, `level=warning/critical` flapping at the 11.8 GiB RSS threshold, slope ~0.55 GiB/h → next abort projected **~19:15Z 10-13 – 02:15Z 10-14** (25-32h uptime). Upstream openclaw#159373 unchanged (3 comments, last mine 10-06 11:17Z). Releases: stable v2026.10.2 (10-12) unchanged; NEW `v2026.10.5-beta.2` (10-12 12:10Z) body has no heap/leak/OOM fix (only update-child heap-limit inheritance), installed is still 2026.9.8. Item 1 (claude-cli fallbacks, 66 days): `cron list` (28 jobs) unchanged for all four (no `fallbacks`, `delivery.mode: none`, nightly `timeoutSeconds: 900`), all `ok`/0 errors; no job red. Planned restart/upgrade stays Nico's call; no topic post (heartbeat already tracks it). Detail: `notes/autonomy-gaps.md` 2026-10-13 bullet.
- **2026-10-13 19:40 UTC (heartbeat-checklist) — projection pre-empted by a deliberate restart:** pid 707025 got `SIGTERM: gateway.restart` at **17:46:54Z** after ~23h32m uptime, ahead of the 19:15Z OOM window. It drained cleanly, systemd logged Stopped and then Started at 17:48:26Z, and it came back as pid 3432219 with `NRestarts=0`. The journal 17:40–17:48:40Z has no `heap out of memory` or `ABRT`. At 17:43:34Z the log had shown `remote model catalog downloaded; restart the Gateway to apply it`, which may be the trigger, but that's unverified. Version still 2026.9.8. Next abort projected at 25–32h uptime: **~18:45Z 10-14 – 01:45Z 10-15**.
- **2026-10-14 09:30 UTC (`next-audit-priorities-reminder`) — 🔄 in progress, no lever of mine left:** no heap-OOM abort since the 10-12 18:14Z one (journal since 10-13 09:31Z, 3,678 lines: 0 `heap out of memory`/`status=6/ABRT`; the only stop is the deliberate 10-13 17:46:54Z restart above). Current pid 3432219 (up 15h42m, no restart) hourly heap floors 5.59 (04Z) → 6.01 (06Z) → 7.49 (08Z) → 7.94 GiB (09Z), latest 8.43 GiB at 09:26Z, RSS ~11.2 GB, `level=warning`, slope ~0.47 GiB/h → next abort projected **~20:30Z 10-14 – 01:30Z 10-15** by slope (uptime band 18:48Z – 01:48Z). Upstream openclaw#159373 unchanged (3 comments, last mine 10-06 11:17Z). NEW: **v2026.10.3 stable** (10-13 13:49Z; installed 2026.9.8) and `v2026.10.5-beta.3` (10-13 10:00Z): release bodies have no heap/leak/OOM/RSS fix. Item 1 (claude-cli fallbacks, 67 days): `cron list` (28 jobs) unchanged for all four (no `fallbacks`, `delivery.mode: none`, nightly `timeoutSeconds: 900`), all `ok`/0 errors; no job red. Planned restart/upgrade stays Nico's call; no topic post (heartbeat already tracks it). Detail: `notes/autonomy-gaps.md` 2026-10-14 bullet.
- **2026-10-15 09:30 UTC (`next-audit-priorities-reminder`) — 🔄 in progress, no lever of mine left:** the 10-14 projection landed: pid 3432219 (since the deliberate 10-13 17:48:26Z start) OOM-aborted at **10-15 00:45:40Z** (`FATAL … heap out of memory`, last Mark-Compact 15.9 GB, `status=6/ABRT`) after 30h57m; systemd auto-restarted it as pid 2527001 at 00:45:48Z (`NRestarts=1`, not a deliberate restart) and SIGKILLed the remaining children (several `codex`/`MainThread`). This abort had not been logged here by the heartbeat. Abort series: 10-05 18:04Z, 10-07 14:42Z, 10-08 20:09Z, 10-09 22:04Z, 10-11 16:37Z, 10-12 18:14Z, 10-15 00:45Z (uptime band 25-32h holds). Current pid 2527001 (up 8h45m): RSS 6.8 GiB, ~0.5 GiB/h from the 01:02Z sample (2.39 GiB RSS / 833 MiB heap); no hourly heap floors yet (the pressure diagnostic only emits above its threshold). Next abort projected **~01:45Z-08:45Z 10-16** by uptime band. Upstream openclaw#159373 unchanged (3 comments, last mine 10-06 11:17Z). NEW: `v2026.10.5-beta.4` (10-15 06:10Z): only worker heap limits (#166581), no main-process leak fix; stable v2026.10.3 still latest (installed 2026.9.8). Item 1 (claude-cli fallbacks, 68 days): `cron list` (28 jobs) unchanged for all four (no `fallbacks`, `delivery.mode: none`, nightly `timeoutSeconds: 900`), all `ok`/0 errors; no job red. Planned restart/upgrade stays Nico's call; no topic post (heartbeat already tracks it). Detail: `notes/autonomy-gaps.md` 2026-10-15 bullet.
- **2026-10-16 09:30 UTC (`next-audit-priorities-reminder`) — 🔄 in progress, no lever of mine left:** the 10-15 projection landed: pid 2527001 (since the 10-15 00:45:48Z auto-restart) OOM-aborted at **10-16 08:37:58Z** (`FATAL … heap out of memory`, last Mark-Compact 15.9 GB, event-loop delay p99 18.9s at 08:37:37Z, `status=6/ABRT`, systemd peak 28.6G) after 31h52m, the longest uptime in the series; systemd auto-restarted pid 1584152 at 08:38:06Z (`NRestarts=2`, not a deliberate restart). The heartbeat checklist had not logged it by 09:30Z, so this header was stale until now. Current pid 1584152 (up 53m, RSS 2.7 GiB), next abort projected ~09:40Z-16:40Z 10-17 by the 25-32h band, which would SIGKILL live child sessions. openclaw#159373 unchanged (3 comments, no maintainer reply). New stable v2026.10.4 (10-16 00:36Z) and v2026.10.10-beta.1 (10-15 18:03Z) have no leak fix (worker heap limits only; beta.1 adds CLI-child memory-pressure protection, not a heap-leak fix). Cron-config gaps (item 1) unchanged, 69 days pending, all 4 tracked jobs `ok`/`consecutiveErrors=0`. Upgrade / planned restart stay Nico's call. Archived the 10-11 bullet in `notes/autonomy-gaps.md`. No topic post (already-projected recurrence).

### 🟡 PR #9723 (lodekeeper) — "fix: avoid payload prep failures on gloas reorgs" — nflaig asked if still relevant [topic:50]
- **Source:** gh-notif sweep 2026-10-02 19:05 UTC; nflaig issue comment https://github.com/ChainSafe/lodestar/pull/9723#issuecomment-5959199605 — "@lodekeeper is this still relevant? otherwise we should close it". UNROUTED (no prior BACKLOG entry).
- **Context:** branch `fix/gloas-proposer-reorg-payload-rootcause`, base unstable, created 2026-07-28, OPEN but now CONFLICTING. Replaces closed #9721 retry workaround; root-cause fix for Gloas local proposer-boost-reorg selecting a weak late block's parent as FCU head while payload prep could still canonicalize the EL to the weak child. Adds `getSafeExecutionBlockHashForHead()`, splits local vs gossiped Gloas proposer preferences, uses local preferences in `importBlock` FCU suppression. Possible overlap with [[project_gloas_forkchoice_gaps_unstable]] (PR #9233 / issue #9764) — worth checking if absorbed there. Prior exchange 2026-08-01 (nflaig: "what is this?", I explained), then silence until today.
- **Status:** Awaiting nflaig design decision on the safe-hash reconciliation (see the ⏸️ line below). Prior investigation: topic:50 wedged on the 19:05 nudge → main-session takeover; verdict **STILL_RELEVANT** (not superseded by #9233). #9233 merged 2026-08-27 but only implemented `should_apply_proposer_boost` for Gloas (boost gating), not the FCU-head-vs-payload-prep root cause. On unstable: `getSafeExecutionBlockHashForHead` has 0 hits; `prepareNextSlot`/`produceBlockBody` still call `getSafeExecutionBlockHash` with no head; `proposerPreferencesPool` has no local-vs-gossip split (`markLocal`/`isKnownLocal`), so `importBlock` still gates FCU suppression on fee-recipient only. Caveat: `safeBlocks.ts` reworked for Gloas (`getSafeExecutionBlockHash` now returns bid `parent_block_hash` post-Gloas) → rebase must reconcile semantics. `mergeable=CONFLICTING/DIRTY`. Replied in-thread as lodekeeper (issuecomment-5959812152) confirming relevance + committing to rebase. No DM (nflaig-authored ask).
- **⏸️ AWAITING nflaig DESIGN DECISION (2026-10-02 20:58 UTC) — no longer actionable for me.** Detached `setsid` Codex attempted the merge of origin/unstable (@859c034d) and correctly **BLOCKED** (block-on-ambiguity guard worked): the rebase is NOT mechanical. 5 conflicts — the core 3 are semantic: `safeBlocks.ts` (unstable's reworked `getSafeExecutionBlockHash` now does Gloas `parentBlockHash` + finalized fallback + genesis exclusion via merged #9393/#9794/#10027 — VERIFIED against live unstable L25-62 — so the PR's independent `getSafeExecutionBlockHashForHead` now diverges), `prepareNextSlot.ts`/`produceBlockBody.ts` (PR's head-aware calc would shadow upstream's now-shared safe/finalized SSE↔EL hashes). `importBlock.ts` = imports-only (trivial); `proposerPreferencesPool.ts` = no conflict. Codex aborted cleanly, pushed/committed nothing, restored ~/lodestar to a3706584 (verified). **Surfaced the specific decision to nflaig in-thread** (issuecomment-5961409773): is head-aware ancestry filtering still required under the current safe-hash definition, and if so how should it compose with (not replace) upstream's fallback/genesis/parent-hash behavior? No DM (fails DM gate — not a blocker for Nico's own work). **Next step: await nflaig's call, then reconcile per his direction (or close if he deems head-aware obsolete).**

### 🔴 Known-root `execution_payload` envelope flood — severity/venue decision pending
- **Source:** bshastry interop-🌃 thread (2026-09-28) + Nico DM investigation 2026-09-28/29; tracker is private `ethereum-bounty/lodestar#36` (Medium/glamsterdam), sibling to #35.
- **Status:** Awaiting Nico/security-process decision on the #36 fix path; point-1 refinement posted as `issuecomment-5888171169`; no public action.
- **Current blocker / next-step:** if Nico wants action, draft the fix under bounty/security process: move `execution_payload` off main-thread verification and add a per-peer rejected-attempt budget as defense-in-depth. Local measurement optional; do not open a public issue.
- **Full investigation log:** archived 2026-09-30 (12 lines -> BACKLOG_ARCHIVE.md)

### 🔴 Ephemery iteration 164 Lodestar node stuck at head 0 [discord:1554019461097459762]
- **Source:** Matthew Keil/Hamid in Discord thread `#ephemery-node-stuck`, 2026-09-28; Lodestar v1.48.0/v1.47.0 + reth v2.6.0 on Ephemery iteration 164 stuck at genesis.
- **Status:** Awaiting Hamid/Matthew logs or REST outputs; local checks confirmed the node's head root matches current iteration-164 genesis, and `pk910/ephemery-lodestar:latest` is still Lodestar v1.48.0 with wrapper-only changes.
- **Current blocker / next-step:** do not repost; request for beacon/EL logs and REST outputs was already posted in-thread. Once data arrives, distinguish Fulu@epoch0/data-column custody peer scarcity from EL import failure or the wrapper `--dataDir` reset footgun.
- **Full investigation log:** archived 2026-09-30 (8 lines -> BACKLOG_ARCHIVE.md)

### 🟡 devnet-ax41-0/1 `execution_payload_envelopes_by_range` 100% error — `earliestAvailableSlot` re-inits to finalized anchor on restart, ignoring retained flat-file history (dedup-INDEPENDENT bug) [discord:1552311703402844210]
- **Source:** Discord devnet-ax41 thread, 2026-09-24.
- **Status:** Awaiting Nico/maintainer prioritization; root cause is independent of payload dedup and persists even when old flat-file payload history remains on disk.
- **Current blocker / next-step:** if prioritized, fix restart initialization so `earliestAvailableSlot` reflects retained flat-file history rather than the finalized anchor; include a restart regression test.
- **Full investigation log:** archived 2026-09-30 (8 lines -> BACKLOG_ARCHIVE.md)

### 🟡 `pruneHistory` per-finalization key scan takes ~30s on long-lived DBs (stable-sas) — `keys({gte:0})` rescans LevelDB tombstones every finalization [discord:1552311703402844210]
- **Source:** stable-sas v1.49.0 rollout analysis, 2026-09-24/29.
- **Status:** Awaiting Nico/maintainer prioritization; regression tied to #10106 widening the `stateArchive.keys()` scan upper bound, causing long-lived LevelDB tombstones to be rescanned every finalization.
- **Current blocker / next-step:** if prioritized, replace the broad per-finalization key scan with bounded metadata/indexed pruning and add a long-lived DB regression/benchmark.
- **Full investigation log:** archived 2026-09-30 (11 lines -> BACKLOG_ARCHIVE.md)

### 🟡 Aztec sequencer announces a stale P2P IP after the host's public IP changed — peers plateau ~81/100 [aztec-sequencer-health cron]
- **Source:** `aztec-sequencer-health` cron, 2026-09-25.
- **Status:** Awaiting Nico/ops decision; peer plateau appears tied to advertised P2P ENR/IP not updating after the host public IP changed.
- **Current blocker / next-step:** if asked, rotate/update the advertised IP/ENR or restart with corrected networking config, then watch peer count recover.
- **Full investigation log:** archived 2026-09-30 (7 lines -> BACKLOG_ARCHIVE.md)

### 🟡 Ephemery Glamsterdam (Gloas) fork scheduling — Oct 22 reset (iteration 165) [discord:1552392548939726858]
- **Status:** Awaiting Nico/upstream timing decision — researched; NOT needed in #10161 for Fulu-only iterations <=164.
- **Tracking issue:** https://github.com/ChainSafe/lodestar/issues/10162
- **Current blocker / next-step:** wait for ephemery-genesis PR #75 final values; follow up near 2026-10-22 19:10 UTC with either a timed epoch-0 base bump or iteration-aware fork schedule, and verify Gloas timing BPS params.

### 🟡 Cross-client forkchoice question: equivocation recording vs proposer boost — check Lodestar's proposerBoostRoot gate [eth-rnd-archive]
- **Source:** Eth R&D #consensus-dev thread 2026-09-10; potuz asked whether invalid early equivocations can consume proposer boost before a later valid equivocating block arrives.
- **Status:** Awaiting Nico — security-adjacent triage was DMed; no autonomous fix started.
- **Current blocker / next-step:** if Nico wants it, trace whether an EL-invalid block can reach `onBlock()` / `proposerBoostRoot` assignment before invalidation; watch for cross-client consensus or a test vector.

### 🟡 PR #9430 — wemeetagain asked if gossip data-column-sidecar spec tests are still needed / needs a refresh [topic:50]
- **Status:** Passive / watching PR checks — still-needed decision made, branch refreshed by merge commit `1dfcc2ca7d`, PR open with CI pending/unstable.
- **Source:** wemeetagain issue comment `issuecomment-5607250802` on 2026-09-09 asking whether the old data-column-sidecar gossip spec-test PR was still needed.
- **Current blocker / next-step:** watch #9430 CI; if spec presets fail, revisit the merge resolution. No heartbeat nudge unless concrete CI/review activity appears.

### 🟡 PR #10035 — nflaig asked to verify test coverage for the skipped-epoch-boundary-slot scenario [topic:50]
- **Status:** Passive / watching #10097 — follow-up implemented (PR #10097 opened 2026-09-15 with the fork-choice finalized-callback regression test); original #10035 is merged.
- **Source:** nflaig review comment `discussion_r3966712887` / follow-up `discussion_r3966993942` on 2026-09-09.
- **Current blocker / next-step:** passive watch for #10097 review/CI or new Nico feedback; otherwise closed.

### 🟡 Workspace repo has no remote; newest same-disk backup tarball is 2026-06-15 [cron:882f5c1c]
- **Source:** `next-audit-priorities-reminder` cron, 2026-09-25 09:3x UTC — found while committing `check_cron_health.py`: `git remote -v` is empty on `main`, last bulk sync commit 2026-03-21, newest `/home/openclaw/*-openclaw-backup.tar.gz` is 2026-06-15 (5.7 GB, same disk, 87% used).
- **Status:** Awaiting Nico — I found no second copy of work since mid-June (22 modified + 380 untracked entries, incl. `notes/autonomy-gaps.md` and this file). Only local signed commits this cycle (`346627c`, `c64749d`, `88304a8`, `2da4e96`); nothing pushed, no remote added.
- **Current blocker / next-step:** Nico's call: private remote vs a scheduled tolerant-tar to off-disk storage (`[[reference_openclaw_backup_tolerant_tar]]`: `backup create` fails on the live tree). No bulk commit from cron — much of the untracked set is `.tmp-*` scratch.

### 🟡 jtraglia asks CL clients (CC'd Nico directly) to confirm consensus-specs PR #5619 is a no-op today [eth-rnd-archive]
- **Status:** Awaiting Nico — not yet confirmed publicly because this was a personal CC and I do not have confirmed posting access to Eth R&D #consensus-dev.
- **Finding:** ethereum/consensus-specs#5619 is pyspec-pseudocode-only for Lodestar today: `NewPayloadRequest` becomes SSZ-hashable for EIP-8025; Engine API JSON-RPC wire serialization is unchanged.
- **Next:** await Nico's call; if asked, post a GitHub PR confirmation or Discord thread reply if access is confirmed.

### 🟡 ePBS: 2 unpatched bid-validation gaps found, 1 directly implicates Lodestar [eth-rnd-archive]
- **Source:** `eth-rnd-archive-hourly` cron, 2026-09-03 13:17 UTC; qu0b reported three Gloas/EIP-7732 builder-auction bugs on glamsterdam devnet-8.
- **Status:** Awaiting Nico — Bug 1 fixed upstream/Lodestar; Bug 2 (`fee_recipient`) and Bug 3 (`gas_limit`) remain unfiled/unpatched; direct proposer delivery still sets `strictFeeRecipientCheck: false`.
- **Current blocker / next-step:** await Nico's response on escalation and whether to make a Lodestar-side fix.

### 🟡 Research: push Lodestar images to Ethereum Swarm via Uncloud Registry [discord:1545046637175635978] [topic:50]
- **PRs:** PoC https://github.com/lodekeeper/lodestar-swarm-registry-poc/pull/1; Lodestar https://github.com/ChainSafe/lodestar/pull/9997 (`lodekeeper:feat/swarm-registry-publish`).
- **Status:** Awaiting infra/ops e2e — #9997 is code-complete, approved, green, clean/mergeable; no-op until `SWARM_REGISTRY` is configured.
- **Current blocker / next-step:** infra/ops owns e2e now: stand up funded Bee + registry endpoint, set CI vars/secrets, merge #9997, run one real publish, then decide ownership of the stale driver/distribution/Bee-fork stack vs V2.

### 🟡 PR #9927 blocked on native bindings update — forkSeq on IBeaconStateViewNative [topic:50]
- **PRs:** Lodestar TS side https://github.com/ChainSafe/lodestar/pull/9927; native side https://github.com/ChainSafe/lodestar-z/pull/635
- **Status:** Awaiting lodestar-z release/bindings bump — lodestar-z #635 merged with the native `.node` `forkSeq` getter.
- **Current blocker / next-step:** re-engage only if #9927 needs a bindings-version bump or gets further review.

### 🟡 PR #10099 test file cache reorg — merged; narrowed #10175 OPEN vs unstable [topic:50]
- **Source:** github-notifications sweep, 2026-09-17; #10099 review asks from spiral-ladder, chatgpt-codex-connector, and nflaig.
- **Status:** Awaiting Nico's answer — #10175 is now narrowed to the 3-file JSDoc + orphaned `@lodestar/api` devDep cleanup; #10099 merged and stacked #10174 auto-closed.
- **PR:** https://github.com/ChainSafe/lodestar/pull/10175 (head `e52d211a00`, review required)
- **Current blocker / next-step:** await Nico: merge the narrowed PR or close it. No DM/topic ping; this follows Nico's own comment.
- **Full comment/reply log:** archived 2026-09-25, 2026-09-26, and 2026-09-30 -> `BACKLOG_ARCHIVE.md`.

### 🟡 PR #10113 review comments need addressing — payload timing metric buckets [topic:50]
- **Source / PR:** github-notifications sweep, 2026-09-22; https://github.com/ChainSafe/lodestar/pull/10113 on `ChainSafe/lodestar:te/gloas_newPayload_metrics` with `maintainerCanModify=false`.
- **Status:** Awaiting PR author/maintainers — twoeths adopted the first bucket suggestion in `e02657e40d`; nflaig then asked for an 8s bucket and I replied in-thread with a one-click suggestion.
- **Current blocker / next-step:** await PR author/maintainers to apply `buckets: [0.05, 0.1, 0.25, 0.5, 1, 2, 3, 4, 6, 8]` or equivalent.
- **Full review log:** archived 2026-09-25 (5 lines -> `BACKLOG_ARCHIVE.md`)

### 🟡 Kris' PRs #9931 + #9932 review — Lodestar Builder BN block observer + Gate A tests [discord:1544088880792469647]
- **Source/PRs:** Marko L request in Discord #lodestar-builder, 2026-08-31; #9931 https://github.com/ChainSafe/lodestar/pull/9931 and #9932 https://github.com/ChainSafe/lodestar/pull/9932.
- **Status:** Awaiting Marko — review complete + verified; synthesis delivered in Discord, no GitHub review posted yet.
- **Current blocker / next-step:** await Marko's call: post inline on GitHub as lodekeeper, or let him relay to Kris.

### 🟡 Prepare 1.46 security advisories (GHSA) — requested by Nico in #security-issues 2026-08-15
- **Source:** Nico, Discord #security-issues, 2026-08-15 17:32 UTC: prepare advisories for the fixes shipped in 1.46.
- **Status:** Awaiting Nico — 2 optimistic-sync validator-safety GHSA drafts are in `advisories/1.46/` and shared in channel.
- **Current blocker / next-step:** confirm final advisory set and whether to include secondary hardening candidates; GitHub draft creation is held pending sign-off.
- **Full advisory context:** archived 2026-09-25 (5 lines -> `BACKLOG_ARCHIVE.md`)

### 🟡 PR #9821 review comments — fork-choice gwei weights [topic:50]
- **Status:** Passive / completed analysis; full findings archived 2026-10-16.
- **Summary:** Runtime metrics recheck is complete; awaiting maintainer merge or follow-up.
- **Next:** Re-engage only on new evidence or reviewer/maintainer feedback.


### CI auto-fix unstable — 2026-10-16 08:44 UTC
- **Source:** Nico, scheduled `ci-autofix-unstable` cron `573d18ec-602c-40ba-a01a-004841c0da1a`, 2026-10-16 08:44 UTC.
- **Priority:** 🟡
- **Status:** ✅ Done — GitHub guard coverage/access and detector prerequisites passed. Detector `--apply` exited 0: `status: clean`, `No new failures on unstable`. No fixes, PRs, or alerts required.

### 🟢 Devnet health monitor — 2026-10-16 10:13 UTC
- Source: unattended cron 51e7881e-3799-4581-a741-d19dc92d8c7a.
- Status: ✅ Done — no new noteworthy issue. Three reachable networks finalizing normally; known signals deduplicated. Devnet12 public endpoints HTTP404 on initial probes and recheck (coverage gap, not inferred non-finality). Evidence: memory/devnet-health/snapshots/2026-10-16-1013/. No Discord post or auth restart.

### 🟢 Devnet health monitor — 2026-10-16 12:13 UTC
- Source: scheduled cron 51e7881e-3799-4581-a741-d19dc92d8c7a.
- Status: ✅ done — three active networks finalizing; no new noteworthy issue. Devnet12 retired in discovery; prior coverage gap resolved. Evidence: `memory/devnet-health/snapshots/2026-10-16-1213/`.

### 🟢 Dotfiles sync — 2026-10-16 12:23 UTC
- **Source:** Nico, scheduled cron `d02eaff9-833e-4d02-acc3-cd5f8b4898b3`.
- **Priority:** 🟢
- **Status:** ✅ Done — script pushed commit `769eebf` to `lodekeeper/dotfiles` (3 files changed).

### 🟢 Devnet health monitor — 2026-10-16 14:13 UTC
- Source: scheduled cron 51e7881e-3799-4581-a741-d19dc92d8c7a.
- Status: ✅ Done — All three active networks FINALIZING distance2; completed participation Heze89/Bogota100/devnet8 97%. All22 Lodestar online at canonical head; previous Lodestar/Reth1 and Prysm/Geth2 Dora TLS failures recovered. Single Dora chain each. Known devnet8 Lighthouse/Besu canonical lag41597 dedup. Bogota Lighthouse/Besu1+2 canonical lag5032 outside Lodestar-focused threshold (no Lodestar, finality100%). Assertoor unchanged. No new noteworthy issue; no auth restart or Discord post.
- Evidence: memory/devnet-health/snapshots/2026-10-16-1413/.
