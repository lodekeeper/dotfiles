# epbs-devnet-1 / PR #9148 — Tracker

Last updated: 2026-04-02 20:5x UTC

## Goal
Get PR #9148 to a genuinely resolved state where Lodestar handles the epbs-devnet-1 genesis / Gloas-from-genesis finalized-sync path without stalling, with deterministic local proof and a clean live repro.

## Phase Plan
- [x] Checkpoint-sync missing-FULL-parent recovery fix
- [x] Empty-epoch finalized by-range handling
- [x] Finalized boundary-block recovery / serving fixes
- [x] Surface bootstrap-required state from first-batch retries
- [~] Resolve remaining slot-0 Fulu first-batch bootstrap/custody-column stall
- [ ] Clean live repro proving forward progress from genesis on usable peer mix
- [ ] Quality gate / final targeted tests / PR-ready summary

## Completed Work
- `9315d81ae0` — recover missing FULL parent envelope on PRESTATE_MISSING in unknownBlock sync
- `094559df00` — gate envelope fetch on explicit FULL absence check
- `a55aca7d1c` — handle empty epoch responses in range sync
- `b97e077893` — sequential block-first download and transient timeout handling
- `81435b880e` — avoid processing partial post-Gloas batches after later fetch failure
- `b7713ba7fe` — recover missing finalized boundary parent by root during range sync
- `fd8c989d0c` — include finalized boundary block in beacon_blocks_by_range
- `c94da6a86d` — quarantine peers that omit finalized boundary blocks in range sync
- `e7bfa58540` — use peer head slot for finalized sync eligibility
- `f8f8bd151c` — regression proof for late low-range peer after target promotion
- local uncommitted patch stack after merge `b77873471c` — BootstrapRequired/state surfacing + additional diagnostics under active iteration

## Current Validated Signal
- Checkpoint sync appears fixed.
- Genesis / Gloas-from-genesis remains unresolved.
- Earlier live `discovery11` evidence showed a genuine **Advanced** erigon/caplin peer; with the classification-only patch enabled, Lodestar entered finalized range sync instead of staying on the fully-synced path.
- That same session then hit a **separate downstream req/resp failure**: outgoing `beacon_blocks_by_range` V2 `INVALID_REQUEST: SSZ_SNAPPY_ERROR_UNDER_SSZ_MIN_SIZE`.
- The later direct-host repro window is currently unstable: the stable host anchor `46.224.62.16:4401` first degraded to `AHo4o/Behind`, then to repeated peerless/refused windows, so the outgoing error path is not currently re-firing.
- Packaging state is now clear:
  - committed diff vs `origin/epbs-devnet-1` = only the narrow `unknownBlock.ts` missing-parent-envelope recovery fix
  - uncommitted experiments = (A) classification tweak, (B) V1 fallback experiment, (C) invalid-request instrumentation

## Next Immediate Steps
1. Decide PR packaging scope:
   - **Option 1:** absolute-safest PR = committed `unknownBlock.ts` fix only
   - **Option 2:** include `unknownBlock.ts` + pared-down classification patch (A) without temporary debug log
2. Keep B (V1 fallback) and C (invalid-request instrumentation) out of the PR for now.
3. If Option 2 is chosen, commit only the classification logic + regression test; do not include the debug log.
4. Draft the PR description with explicit caveat that the downstream req/resp `UNDER_SSZ_MIN_SIZE` failure is a separate unresolved follow-up.
5. Keep the low-frequency live monitor/resample path running in the background while packaging, but do not churn the host probe aggressively.

## Live Runtime Hygiene
- Kurtosis enclave currently running: `epbs-devnet-1-gloas-fcfix2-4nodes` (started 2026-04-01 19:49 UTC)
- Lingering local repro nodes observed at 06:19 UTC: `genesis16`, `21`, `22`, `24`, `25`, `26`, `27`
- Policy for next loop: keep at most one fresh live repro once the next patch is ready.

## Validation Target
- Focused tests green for changed sync logic.
- Fresh genesis repro imports past the slot-0 / first finalized-batch stall and shows genuine forward progress without getting trapped in `BootstrapRequired` or `No retry peer for first finalized batch` loops.

## Spec Compliance Artifacts
- N/A for now (debugging sync control flow / behavior investigation; generate if final patch touches spec-facing protocol logic in a stable way)
