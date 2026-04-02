# epbs-devnet-1 / PR #9148 — Tracker

Last updated: 2026-04-02 06:19 UTC

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
- First finalized batch is already `fork=fulu`, `startSlot=0`, `columnsRequest=true`.
- Two live blockers are currently separated:
  1. `earliestAvailableSlot > startSlot` history-floor gap
  2. no connected peer covers the requested custody columns for the slot-0 Fulu batch
- Local review suspects follow-up bugs in `notWhileSyncing()`, `throwIfAnchorBatchIsUncovered()` retry semantics, premature `bootstrapRequiredState` clearing, and peer re-admission after `NO_PEER_COVERS_ANCHOR`.

## Next Immediate Steps
1. Incorporate fresh `gpt-advisor` guidance on fix ordering.
2. Inspect / patch the highest-value control-flow bug first (likely retry anchor coverage / bootstrapRequired recovery semantics).
3. Add the minimal targeted regression test for that path.
4. Re-run focused sync tests.
5. Run one fresh live repro only (after cleaning stale repro nodes) to validate the intended failure mode is gone or narrowed.

## Live Runtime Hygiene
- Kurtosis enclave currently running: `epbs-devnet-1-gloas-fcfix2-4nodes` (started 2026-04-01 19:49 UTC)
- Lingering local repro nodes observed at 06:19 UTC: `genesis16`, `21`, `22`, `24`, `25`, `26`, `27`
- Policy for next loop: keep at most one fresh live repro once the next patch is ready.

## Validation Target
- Focused tests green for changed sync logic.
- Fresh genesis repro imports past the slot-0 / first finalized-batch stall and shows genuine forward progress without getting trapped in `BootstrapRequired` or `No retry peer for first finalized batch` loops.

## Spec Compliance Artifacts
- N/A for now (debugging sync control flow / behavior investigation; generate if final patch touches spec-facing protocol logic in a stable way)
