# Review Findings — review-devils-advocate — 10263

Reviewer: review-devils-advocate
Reviewed commit: 2e9ac55d6dde395fceed1d4778f7939458471923
Generated at: 2026-10-05 09:11 UTC

## Devil's Advocate Review

### Overall Assessment
The fix is spec-faithful and removes the per-request multiplier: 80 scans become 1 index build. It still rebuilds an O(N) index on every block that carries any builder request, though. Under the PR's own 140k-builder threat model, that leaves a ~0.6–1 s per-block cost that one cheap request can trigger, and that cost is higher than what a single request cost before this PR. Merge it as a stopgap, but the root-cause fix is a persistent, verified pubkey→index cache, and #9513 should stay open for it.

What is sound, and I'm not challenging it:
- **Necessity:** the old code really is O(k·N). My microbenchmark of the old path with 80 misses at N=140k gives ~17.8 s, which is consistent with the >12 s bounty report.
- **Spec fidelity:** index reuse is settled in the spec. It is tested upstream (#5296, #5571, both in v1.7.0-beta.2) and clarified in #5705, which says: "Implementations that rely on caching should account for this behavior". Lodestar's `parent_execution_payload` operation runner exercises those batch vectors through `applyParentExecutionPayload` → `IndexedBuilderState`.
- **No spec churn:** EIP-8282 is in Review, but the reuse semantics have been stable since May.

Benchmark method: a synthetic `List[Builder]` with the gloas `Builder` schema, run with `@chainsafe/ssz` 1.6.1. Lodestar pins 1.8.0, so treat the absolute numbers as indicative. Medians on this host at N=140k:

| Operation | Cost |
|---|---|
| PR-style build: `commit` + `getAllReadonlyValues` + hex `Map` + candidate list | 0.61–0.98 s (min 0.56 s) |
| … of which `getAllReadonlyValues` alone | ~0.42 s |
| Old code, 1 miss-scan | 0.15 s (warm view) / 0.29 s (fresh view) |
| Old code, 80 miss-scans | 17.8 s |
| `new Map()` clone of 140k entries | 25 ms |

At N=2,000 the PR's build costs 6.9 ms versus 3.4 ms for one old scan. That is negligible at realistic registry sizes.

### Objections

#### 1. 🟡 Fixes the multiplier, not the O(N) root cause, and makes the 1-request case slower than before
**Anchors:**
- `packages/state-transition/src/block/indexedBuilderState.ts:21`: `    const builders = state.builders.getAllReadonlyValues();`
- `packages/state-transition/src/block/processParentExecutionPayload.ts:72`: `    const indexedState = new IndexedBuilderState(state);`

**Challenge:** The PR builds a full pubkey→index map and candidate list whenever `builderDeposits.length > 0 || builderExits.length > 0`. That includes a single exit request for an unknown pubkey. Per block, the cost goes from O(k·N) to O(N + k), with a larger constant than the old single scan:
- 1 request at N=140k: ~0.15–0.29 s before this PR, ~0.6–1.0 s after.
- 80 requests at N=140k: ~17.8 s before this PR, ~0.6–1.0 s after.

The cheapest trigger is now the expensive case:
- EIP-8282 exit requests stake nothing. They only pay the request fee: `MIN_REQUEST_FEE = 1` wei, and the fee only rises above `TARGET_EXIT_REQUESTS_PER_BLOCK = 2`.
- So one junk `BuilderExitRequest` per FULL payload forces the full index rebuild on every node.
- The rebuild also runs on the proposer path. `withParentPayloadApplied` uses `clone(true)` (cache not transferred) from `prepareNextSlot.ts:238` and `produceBlockBody.ts:266/308`.

Whether that rises to a DoS finding is the security reviewer's call. From a design standpoint, the PR leaves its own stated problem (140k registry → slow block processing) half-solved.

The reasoning in #9513 rejects two designs:
- a global cache, "because we mutate the registry per block";
- a per-epoch cache, because of competing blocks.

Both objections apply to a *single-valued* global map that is trusted on lookup. Neither applies to an append-only multi-valued map that is verified on lookup.

**Evidence:**
- **Lodestar precedent:** the validator `pubkey2index` is already global and shared by all states. Its "in this state?" guard is documented in `util/electra.ts`: "Since we share pubkey2index, pubkey maybe added by other epoch transition but we don't have that validator in this state".
- **Lodestar precedent:** `EpochCache` already carries an application-wide builder singleton, `builderDepositSignatureCache`, "shared by-reference across clones" (`epochCache.ts:573`).
- **Prysm:** keeps a per-state `builderIdxMap`. It is maintained in `AddBuilderFromDeposit`/`SetBuilder` (delete the old pubkey, set the new one), cloned in `Copy()` (`maps.Clone`), and used by `ProcessBuilderDepositRequests` via `st.BuilderIndexByPubkey`. Its reusable-slot search (`builderInsertionIndex`) is a linear scan, but it only runs on actual new registrations.
- **Lighthouse:** `get_index_for_new_builder` is a spec-literal scan (`beacon_state.rs:2108`).
- **Verification cost:** `ArrayCompositeTreeViewDU.getReadonly(i)` is `getNodeAtDepth`, i.e. O(log N). Checking a single candidate is cheap.

**Counter-proposal:** Add a global, append-only `builderPubkeyIndex: Map<PubkeyHex, BuilderIndex | BuilderIndex[]>` to `EpochCache`, next to `builderDepositSignatureCache`.
- Never delete entries. Add `(pk, idx)`:
  - in `createCachedBeaconState` for post-gloas states, at the same hook point as `syncPubkeys`;
  - in fork onboarding;
  - in `addBuilderToRegistry`.
- `findBuilderIndexByPubkey(state, pk)` returns the first candidate `i` where `i < builders.length && byteArrayEquals(builders.getReadonly(i).pubkey, pk)`, otherwise `null`.
  - Index reuse is handled by the pubkey equality check.
  - Competing branches are handled by multiple candidates per pubkey, with stale ones filtered out.
  - Memory is one shared map, about the size of `pubkey2index` at the same N, with no per-state copies.
- Keep the PR's monotonic candidate cursor, but compute it lazily on the first *valid* new registration in a block. Each such registration requires ≥1 ETH (`BUILDER_MIN_DEPOSIT`) plus a valid PoP.

Result: top-ups and exits become O(k·log N), and an O(N) scan only happens in blocks that actually onboard a builder.

Cost to be honest about: this adds one new invariant, that every state-creation path must populate the map. That is the same invariant `pubkey2index` already carries for `processDeposit`.

If that is too much for this PR: merge as is, keep #9513 open with these numbers, and add a `test/perf` benchmark for `new IndexedBuilderState(state)` at N≈140k so the per-block floor is tracked.

**Impact if ignored:** At large registries, every FULL block with even one builder request pays ~0.5–1 s, on import and again on proposer paths. The minimal trigger is cheaper to cause than before this PR. A second "optimize builder flows" PR will likely be needed once the remaining per-block cost is reported.

#### 2. 🟢 Spec has one `add_builder_to_registry(…, slot)`; Lodestar now has two insert paths and two pubkey maps
**Anchors:**
- `specrefs/functions.yml:4`: `      search: "addBuilderToRegistry(pubkey: Uint8Array,"`
- `packages/state-transition/src/util/gloas.ts:256`: `export function createBuilderView(`

**Challenge:** The spec's `add_builder_to_registry` takes a `slot` because it has two callers. Block processing passes `state.slot`. Fork onboarding (`onboard_builders_from_pending_deposits` in `fork.md`) passes `deposit.slot`.

This PR remaps the specref to `IndexedBuilderState.addBuilderToRegistry`, which drops `slot` and hard-codes `depositEpoch = currentEpoch`. So the mapped implementation can't serve the spec's second caller. The fork path keeps:
- `appendBuilderToRegistry(…, slot)`;
- its own ad-hoc `builderIndexByPubkey` Map in `upgradeStateToGloas.ts`.

`createBuilderView` is newly exported only so the two paths can share it, and `gloas.test.ts` now cross-checks one against the other. The result is two implementations of "pubkey lookup + registry insert" that must evolve in lockstep. `check-specrefs` only watches one of them.

**Counter-proposal:**
- Give `IndexedBuilderState.addBuilderToRegistry` a `slot` parameter, matching the spec signature.
- Use `new IndexedBuilderState(state)` in `onboardBuildersFromPendingDeposits`. This is equivalent at the fork:
  - The registry is empty, so the constructor is O(0) and there are no candidates, so every insert takes the `push` path.
  - `topUp`'s reset branch can't fire, because every builder at the fork has `withdrawableEpoch = FAR_FUTURE_EPOCH`.
- Then delete `appendBuilderToRegistry` and the local map, make `createBuilderView` module-private again, and drop the oracle test.

If objection 1's global index is adopted, onboarding has to populate that index anyway, which makes this consolidation necessary rather than cosmetic.

**Impact if ignored:** Small but compounding. A future spec change to `add_builder_to_registry`, or a new `Builder` field in heze, has to be applied in two places. The specref check passes even if the fork path drifts.

### Verdict
**RECONSIDER — viable alternatives exist.** The PR is a correct, well-tested stopgap and fine to merge as one. But the block-scoped rebuild keeps an O(N) floor on every builder-request block. A verified, append-only global builder pubkey index, following the existing `pubkey2index` pattern and Prysm's `builderIdxMap`, removes that floor. Don't close #9513 on the strength of this PR.
