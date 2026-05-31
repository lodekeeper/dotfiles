# PR #8837 — Devil's Advocate Review

- **Reviewer:** review-devils-advocate
- **Reviewed commit:** 8066f6ba70496be6d7e1ac4cd80c7731ba7b1d04
- **PR:** ChainSafe/lodestar#8837 — `feat: fast confirmation rule`
- **Base:** unstable | **Author:** nazarhussain | **Size:** 4549 / -39, 44 files
- **Spec:** ethereum/consensus-specs#4747 (MERGED 2026-04-16)

## Context corrections to the brief

The brief stated spec PR #4747 is "DRAFT spec PR that has NOT been merged." That's stale. As of this review:

- `consensus-specs#4747` — **merged 2026-04-16**.
- `beacon-APIs#598` ("Add fast confirmation event") — **merged 2026-04-20**, standardizes a `fast_confirmation` SSE event on `/eth/v1/events` (fields: `block`, `slot`).
- `beacon-APIs#611` ("Clarify fast_confirmation event data") — **open since 2026-05-22**, refining same-slot dedup.
- **Nimbus**: ~30 small merged PRs Feb–May 2026, most recent `nimbus-eth2#8512` ("Ensure confirmed chain includes greatest unrealized checkpoint") merged **2026-05-26**, plus `#8479` ("Add fast confirmation event", merged 2026-05-20) implementing the standardized SSE event.
- **Lighthouse**: `sigp/lighthouse#8951` single-PR, **still WIP/open** (Mar–May 2026). Gated by `--enable-fast-confirmation`. Description: "I have implemented this without touching any production code."
- **Prysm**: `OffchainLabs/prysm#15164` open (older April 2025 entry, stale).
- **Teku**: no PRs found.

So the spec is merged but cross-client implementations are still settling — Nimbus is the most advanced and is still landing spec follow-ups 6 weeks after the spec merged.

## Overall Assessment

The algorithm itself is well-motivated — the spec is merged, FCR has real consumers (bridges/exchanges), and an opt-in implementation is a reasonable place to start. But three structural choices in this PR deserve pushback before merging.

## Objections

### 1. Wrong public API: ships a Lodestar-only polling endpoint while the cross-client standard is an SSE event

**Challenge.** The PR adds `GET /eth/v1/lodestar/fast_confirmation_info` returning `{confirmed, head, justifiedCheckpoint, finalizedCheckpoint}` and adds docs for it as the "consumer-facing API" for bridges/exchanges. But the merged cross-client standard (beacon-APIs#598, merged 2026-04-20) is a `fast_confirmation` Server-Sent Event on `/eth/v1/events` with fields `{block, slot}`. Nimbus implemented the standard event in `nimbus-eth2#8479` (merged 2026-05-20). This PR ships zero event support and instead ships a non-standard polling endpoint under the Lodestar namespace. The PR's own user docs concede the divergence: "Consumers should not assume that every Ethereum client exposes the same signal or the same API."

**Evidence.**
- `beacon-APIs#598` merged with event name `fast_confirmation`, fields `{block, slot}`, triggered "after each execution of the Fast confirmation rule which should happen once per slot."
- This PR `packages/api/src/beacon/routes/lodestar.ts:416` registers `getFastConfirmationInfo` under `/eth/v1/lodestar/...`, no event support.
- This PR `docs/.../fast-confirmation.md:50–64` positions the polling endpoint as the consumer API for bridges/exchanges/custodians, then disclaims cross-client compatibility.
- The 4 fields the polling endpoint returns are already independently available: `head` via `/eth/v1/beacon/headers/head`, `justifiedCheckpoint`/`finalizedCheckpoint` via `/eth/v1/beacon/states/{state_id}/finality_checkpoints`. The only new field is `confirmed`.

**Counter-proposal.** Implement the standardized `fast_confirmation` SSE event on `/eth/v1/events` matching beacon-APIs#598 (track #611's clarification). That is the surface bridges/exchanges will actually integrate against — they will not write Lodestar-specific polling clients when Nimbus/Lighthouse/Teku will only emit the event. If a debug/observability polling endpoint is still desired internally, keep it but (a) namespace it explicitly as Lodestar-internal in docs, (b) don't position it as the consumer API, and (c) consider deferring it to a follow-up PR — it's not load-bearing on the algorithm.

**Impact if ignored.** Consumers either (a) ignore Lodestar's API and only target the cross-client event, making this code dead weight, or (b) build Lodestar-specific integrations that we then have to maintain in lockstep with the cross-client event as it evolves (#611 is already adjusting same-slot dedup). The endpoint also lies to operators: when the flag is off, `getConfirmedRoot()` returns the justified rootHex, so the `confirmed` field in the JSON response is just renamed-justified — silently misleading anyone who hits it on a node that didn't opt in.

---

### 2. "Opt-in / experimental" claim is half-true — schema, init, and engine API surface are unconditional

**Challenge.** The PR is framed as opt-in (`--chain.fastConfirmation`, disabled by default, hidden CLI flag, "experimental" in docs). In practice the gate only stops the `FastConfirmationRule` instance from being constructed and `runFastConfirmation()` from executing. The supporting surface is unconditional:

| Surface | Gated by `fastConfirmation` flag? |
|---|---|
| `IForkChoiceStore extends IFastConfirmationStore` (9 new fields) | No — schema change for every store |
| `ForkChoiceStore` constructor reads finalized state and initializes 9 FCR fields | No — runs unconditionally |
| `stateGetter` required-parameter on every ForkChoice construction | No — caller always wires it |
| `/eth/v1/lodestar/fast_confirmation_info` endpoint registration | No — endpoint always responds |
| `safeBlocks.ts::getSafeBeaconBlockRoot` / `getSafeExecutionBlockHash` routing | No — both now read `getConfirmedRoot()` first |

This is the worst-of-both: we pay the architectural surface cost of always-on while keeping the "experimental, may have bugs" disclaimer.

**Evidence.**
- `packages/fork-choice/src/forkChoice/store.ts:36–39` — `interface IForkChoiceStore extends IFastConfirmationStore` (schema change is unconditional).
- `packages/fork-choice/src/forkChoice/store.ts:90–105` — constructor runs `stateGetter({checkpoint: finalizedCheckpointWithHex})` and initializes all FCR fields whether or not the flag is on.
- `packages/beacon-node/src/chain/chain.ts:382–388` — `forkChoiceStateGetter` is always constructed and always passed.
- `packages/api/src/beacon/routes/lodestar.ts:416` and `packages/beacon-node/src/api/impl/lodestar/index.ts:280–310` — endpoint is part of the route table, always registered.
- `packages/fork-choice/src/forkChoice/safeBlocks.ts:11–32` — both safe-block helpers now route through `getConfirmedRoot()` first, even when the flag is off (it falls back to justified, but the code path differs from baseline). Compare to Lighthouse `#8951` description: "I have implemented this without touching any production code… function fires after recomputing the head."

**Counter-proposal.** Pick a side, don't straddle:
- *Option A — commit fully:* drop the flag, ship FCR on by default. The supporting surface is already always-on; only the runtime cost is being delayed. If the algorithm is spec-correct, the only thing the flag saves us from is the ~130ms/slot CPU (per Lighthouse's reviewer measurement) and the perf-overhead of the once-per-slot rebuild.
- *Option B — actually isolate (recommended):* keep the flag and make every checked row above gated. Concretely: (i) put `IFastConfirmationStore` behind a separate optional sub-store and only construct it when the flag is on; (ii) make `stateGetter` an optional parameter passed only when constructing FCR; (iii) register the API route conditionally (or 503/410 when disabled); (iv) revert `safeBlocks.ts` for the disabled case to keep the engine-API path bit-identical to today.

**Impact if ignored.** If a bug shows up post-merge and operators flip the flag off, they're not getting a clean fallback — the store still allocates and initializes FCR fields every restart from finalized state, the safe-block path still differs from baseline, and the endpoint still responds with semantically-confused data (`confirmed === justified`). Rollback is messier than the disabled-by-default framing suggests.

---

### 3. Single 4549-line PR vs. the Nimbus-style stack — spec churn risk

**Challenge.** Nimbus shipped FCR as ~30 incremental PRs over 4 months (Feb–May 2026) and is *still* merging spec-driven fixes — `#8512` ("Ensure confirmed chain includes greatest unrealized checkpoint") merged **2026-05-26**, ten days after the spec was merged. Lighthouse went single-PR and has been WIP for 3 months. This PR follows the Lighthouse shape (1 PR, ~4.5k lines, 44 files) and will pay the same costs:

- **Review depth.** Each of the 4 rules in `packages/fork-choice/src/forkChoice/fastConfirmation/rules.ts` (`resetIfConfirmedUnavailable`, `resetIfBehindOrNotAncestorOrUnsafe`, `advanceIfObservedJustified`, `advanceToLatestConfirmedDescendant`) is consensus-critical and gates `safe_block_hash` in engine API. Reviewing each thoroughly inside a 4549-line diff is hard.
- **Rebase cost.** 44 files touched including shared interfaces (`IForkChoiceStore`, `IBeaconStateView`). Every conflict with `unstable` blocks the whole feature.
- **Spec-sync cost.** Nimbus #8512 has not been picked up here. When the next spec-driven fix lands (say, a follow-up clarifying same-slot dedup, mirroring beacon-APIs#611), the equivalent Lodestar change has to thread through this same 4549-line diff context.
- **Bisect cost.** If a consensus bug surfaces on a Lodestar testnet after merge, "git blame the FCR commit" identifies a 4549-line change, not a 200-line slice.

**Counter-proposal.** Restructure as a stack of 4–5 PRs (against `unstable` or a feature branch with squash-merge per stack PR):

1. **Config + types + spec test runner** (~600 lines): `CONFIRMATION_BYZANTINE_THRESHOLD` config, `IFastConfirmationStore` types, `packages/beacon-node/test/spec/presets/fast_confirmation.test.ts` skeleton wired to EF spec tests. Pass-through, no algorithm logic. Establishes the spec-correctness gate immediately.
2. **Pure helpers** (~1000 lines): `fastConfirmation/utils.ts` minus the rule glue, with unit tests. Pure functions, no fork-choice coupling — reviewable in isolation against the spec.
3. **Snapshot + rules** (~500 lines): `fastConfirmation/{data,rules,fastConfirmationRule}.ts` and `fastConfirmation/test/unit/...` — the algorithm itself.
4. **ForkChoice wiring** (~300 lines): `runFastConfirmation`, store-schema additions (ideally as the optional sub-store from Objection 2), opts plumbing.
5. **Public surface** (~200 lines + dashboard JSON): the `fast_confirmation` SSE event (per Objection 1), docs, dashboard. Lands after the API question is settled.

Each layer testable independently, each PR small enough for line-by-line review, and each compatible with cherry-picking Nimbus follow-up fixes onto the partially-landed stack.

**Impact if ignored.** Reviewers will either skim and approve (consensus-bug risk on a feature that gates `safe_block_hash`) or block on details for weeks while the diff grows stale against `unstable`. Lighthouse's PR has been open 3 months for exactly this reason. Spec follow-ups will land as fix-up commits inside this PR rather than as separate, bisectable PRs.

## Verdict

**RECONSIDER** — The algorithm work is solid and the spec is merged; this isn't "don't do this." But (1) the public API doesn't match the merged cross-client standard, (2) the "opt-in" claim doesn't match what the code actually conditionally enables, and (3) the single-PR shape will fight us as spec follow-ups continue to land elsewhere. None of these require throwing the work away — they require restructuring before merge.
