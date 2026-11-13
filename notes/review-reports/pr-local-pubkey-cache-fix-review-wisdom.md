# Review Findings — review-wisdom — local-pubkey-cache-fix

Reviewer: review-wisdom
Reviewed commit: 4bce44fe3e338e581ce4a1fab1da4d154da26701
Generated at: 2026-11-13 10:18 UTC

# Review: Wise Senior Engineer (code quality) — local pubkey-cache-fix

Reviewer: review-wisdom
Reviewed commit: 4bce44fe3e338e581ce4a1fab1da4d154da26701

## Summary

The design is coherent, but the diff is larger than it needs to be. Most of the excess comes from three sources:

- The "dense cache, else state registry" fallback is duplicated: 5 copies in Zig, and in TS 3 inline union discriminations plus caller-side `resolveSignatureSet` maps.
- Old APIs are kept alongside their replacements.
- Unrelated test churn.

TS and Zig also disagree on the names and shapes of the same concepts. The worst case is an epoch-cache option with the same name and opposite behavior.

Findings are ordered by impact.

---

### 1. `skipSyncPubkeys` / `skip_sync_pubkeys` mean opposite things in TS and Zig
- **File:Line:** `src/state_transition/cache/epoch_cache.zig:219`, `packages/state-transition/src/cache/epochCache.ts:350`
- **Principle:** Consistent naming; explicit over implicit
- **Current:**
  - TS: `skipSyncPubkeys` false → `pubkeyCache.syncPubkeys(validators)` (trusted, dense). True → `addCandidate` for the suffix.
  - Zig: `skip_sync_pubkeys` false → `addCandidate` for the suffix. True → nothing.
  - Trusted dense sync in Zig moved to a separate `sync_pubkeys` arg on `BeaconStateView.createFromBytes`.
- **Suggested:** Give both one option that names the behavior. For example, TS `pubkeys?: "trustedAnchor" | "candidates"` and Zig `pubkeys: enum { trusted_anchor, candidates, skip }`. At minimum, rename the Zig field (e.g. `register_candidates`) so it stops claiming to skip a sync it never performs.
- **Why:** These are two implementations of the same EpochCache with the same option name and different trust semantics. Porting a call site from one to the other will silently pick the wrong trust level.

### 2. Zig: state-registry fallback copied 5×; dense-only twins kept alongside
- **File:Line:** `src/state_transition/cache/pubkey_cache.zig:246-310`
- **Principle:** DRY; avoid parallel APIs
- **Current:**
  - The `getReadonly(index)` → `getValue(undefined, "pubkey", &bytes)` sequence is repeated in `candidateMatches`, `getPubkeyForState`, `getPubkeyBytesForState`, `getPubkeysForState` and `aggregateForState`.
  - The last two also repeat "dense entry if `index < entries.count()`, else uncompress from state".
  - `getPubkeys`, `aggregate` and `getValidatorIndices` lost every production caller and are now exercised only by tests.
- **Suggested:**
  ```zig
  fn statePubkeyBytes(validators: anytype, index: u64) ![48]u8 {
      var validator = try validators.getReadonly(@intCast(index));
      var pubkey: [48]u8 = undefined;
      try validator.getValue(undefined, "pubkey", &pubkey);
      return pubkey;
  }

  /// Caller holds the shared lock.
  fn pubkeyForStateUnlocked(self: *const PubkeyCache, index: u64, validators: anytype) !bls.PublicKey {
      if (index < self.entries.count()) return self.entries.values()[@intCast(index)];
      return bls.PublicKey.uncompress(&try statePubkeyBytes(validators, index));
  }
  ```
  Then either delete `getPubkeys`/`aggregate`/`getValidatorIndices` (and their tests) or add the `validators` parameter to them, instead of adding `*ForState` twins.
- **Why:** There should be one place that defines how a registry pubkey is read. This removes ~30 lines and leaves one method family instead of two, where only one is correct for state transition.

### 3. TS: `PubkeyCacheState` union discriminated inline three times
- **File:Line:** `packages/state-transition/src/cache/pubkeyCache.ts:17`, `:28`, `:44`
- **Principle:** DRY; small single-purpose functions
- **Current:** `"validators" in state ? state.validators.length : state.validatorCount` appears once, and `"validators" in state ? state.validators.getReadonly(i).pubkey : state.getValidator(i).pubkey` appears twice.
- **Suggested:**
  ```ts
  function getStateValidatorCount(state: PubkeyCacheState): number {
    return "validators" in state ? state.validators.length : state.validatorCount;
  }

  function getStateValidatorPubkey(state: PubkeyCacheState, index: ValidatorIndex): Uint8Array {
    return "validators" in state ? state.validators.getReadonly(index).pubkey : state.getValidator(index).pubkey;
  }
  ```
- **Why:** The union is this file's new abstraction. Keeping its discrimination in one place keeps the lookup logic readable, and it mirrors the Zig `statePubkeyBytes` helper above.

### 4. TS/Zig API naming and argument order disagree for the same operations
- **File:Line:** `packages/state-transition/src/cache/pubkeyCache.ts:12`, `:37`, `:49`; `packages/state-transition/src/cache/epochCache.ts:934`, `:938`; `src/state_transition/cache/pubkey_cache.zig:231`, `:264`
- **Principle:** Consistent patterns
- **Current:**
  - Zig: `cache.getForState(io, pubkey, validators)`, `cache.getPubkeyBytesForState(io, index, validators)`.
  - TS free functions use three different shapes:
    - `getValidatorIndex(state, pubkey, cache)`.
    - `getValidatorPubkey(state, index, cache)`. It returns **bytes**, while the TS cache's own convention is `get` → PublicKey and `getPubkeyBytes` → bytes.
    - `promoteFinalizedPubkeys(cache, state, epoch)`, which puts the cache first.
  - The method `EpochCache.getValidatorIndex(pubkey, state)` puts the state last.
  - TS `EpochCache.addPubkey` now registers a *candidate*. Zig calls `pubkey_cache.addCandidate` directly at the same point (`process_deposit.zig:182`).
- **Suggested:**
  - Use one argument order for the TS helpers, e.g. `(pubkeyCache, state, key)` as `promoteFinalizedPubkeys` already does.
  - Rename `getValidatorPubkey` to `getValidatorPubkeyBytes`.
  - Rename `EpochCache.addPubkey` to `addPubkeyCandidate`, or have `processDeposit.ts` call `pubkeyCache.addCandidate` directly as Zig does.
- **Why:** Reviewers compare TS and Zig line by line. Matching names make real divergence visible, and the bytes-vs-PublicKey distinction stays clear.

### 5. TS: optional trailing `state?` threaded next to `validatorsLen` (Zig did the cleaner thing)
- **File:Line:** `packages/state-transition/src/block/isValidIndexedAttestation.ts:14-17`, `:32-35`; `packages/state-transition/src/block/processAttesterSlashing.ts:52-55`; `packages/state-transition/src/block/processProposerSlashing.ts:36`; `packages/state-transition/src/util/signatureSets.ts:124`
- **Principle:** Explicit over implicit; function design
- **Current:** TS keeps `validatorsLen: number` and appends `state?: PubkeyCacheState` after `verifySignatures`. The state is required exactly when `verifySignatures` is true, but nothing enforces it. Zig replaced `validators_count: usize` with a required `validators: anytype` (`is_valid_indexed_attestation.zig`, `process_attester_slashing.zig`).
- **Suggested:** Mirror Zig. Replace `validatorsLen` with a required `state: PubkeyCacheState` and derive the count from it. Every caller already has a state (`state.validatorCount` or `state.validators.length`).
- **Why:** When an optional parameter is mandatory under one flag value, the contract is hidden. This change also removes a parameter and gives TS and Zig the same signatures.

### 6. TS: `resolveSignatureSet` uses a hidden global and is applied by hand at each caller
- **File:Line:** `packages/state-transition/src/util/signatureSets.ts:3`, `:93`; `packages/beacon-node/src/chain/opPools/opPool.ts:108`; `packages/beacon-node/src/chain/validation/attesterSlashing.ts:66`; `packages/state-transition/src/signatureSets/index.ts:99`
- **Principle:** Explicit dependencies; DRY
- **Current:** `resolveSignatureSet` imports the `pubkeyCache` singleton, while the helpers it builds on (`getValidatorPubkey`, `getValidatorIndex`) take `pubkeyCache` as a parameter. Two beacon-node call sites repeat `getAttesterSlashingSignatureSets(...).map((set) => resolveSignatureSet(set, state))`.
- **Suggested:** Pass `pubkeyCache` explicitly, like its siblings do. Also let `getAttesterSlashingSignatureSets` take the state and return resolved sets, so callers can't forget the step.
- **Why:** A hidden global is inconsistent with the module it depends on and harder to test against a non-global cache. Doing the resolution where the sets are built removes the copy-paste.

### 7. Zig call sites keep redundant checks and double lookups that the TS side dropped
- **File:Line:** `src/state_transition/block/process_deposit.zig:105-106`; `src/state_transition/block/process_withdrawal_request.zig:38-43`; `src/state_transition/block/process_consolidation_request.zig:35-38`; also `epoch/process_pending_deposits.zig:78`, `:135`, `slot/upgrade_state_to_gloas.zig:108`
- **Principle:** Simplicity; consistency between implementations
- **Current:** `getForState` already bounds its result by the state's validator count, yet:
  - `process_deposit.zig` still checks `cached_index.? >= try state.validatorsCount()`. TS simplified the same line to `cachedIndex === null`.
  - `process_withdrawal_request.zig` calls `state.validators()` twice, re-checks the length, and keeps the stale "6110 unfinalized vals" comment that the TS diff deleted.
  - `process_consolidation_request.zig` calls `state.validators()` twice and then re-checks `validator_count`.
  - Several sites wrap `(try ...getForState(...))` in parentheses with no `orelse`.
- **Suggested:** Hoist `var validators = try state.validators();` once and pass it to `getForState`. Then drop the post-lookup bounds checks, the stale comment and the extra parentheses.
- **Why:** The leftover guards suggest the new lookup is weaker than it is, and they make the TS and Zig versions of the same spec function diverge for no reason.

### 8. `isPubkeyKnown` is now dead but still edited
- **File:Line:** `packages/state-transition/src/util/electra.ts:59`
- **Principle:** Remove dead code; minimal diff
- **Current:** Its only caller (`processConsolidationRequest`) was rewritten to use `getValidatorIndex(..., state)` directly. The diff still changes its body and strips its doc comment.
- **Suggested:** Delete it.
- **Why:** An unused exported helper invites reuse of the pattern this PR moves away from.

### 9. `promoteFinalizedPubkeys`: a nested loop with `continue`/`break` hides a two-step algorithm
- **File:Line:** `packages/state-transition/src/cache/pubkeyCache.ts:49-65`
- **Principle:** Straightforward control flow
- **Current:** An outer backwards loop uses `continue`. On its first hit it runs an inner forward append loop, then `break`s.
- **Suggested:**
  ```ts
  const size = pubkeyCache.size;
  let lastIndex = state.validatorCount - 1;
  while (lastIndex >= size && state.getValidator(lastIndex).activationEligibilityEpoch > finalizedEpoch) {
    lastIndex--;
  }
  for (let index = size; index <= lastIndex; index++) {
    pubkeyCache.append(index, state.getValidator(index).pubkey);
  }
  pubkeyCache.pruneCandidates();
  ```
- **Why:** "Find the last finalized-eligible index, then append the prefix" can then be read straight off the code.

### 10. Zig `CandidateIndices` first/rest layout leaks into every caller; cleanup loop repeated 4×
- **File:Line:** `src/state_transition/cache/pubkey_cache.zig:84`, `:132`, `:162`, `:174-229`; `src/state_transition/cache/pkix.zig:260`
- **Principle:** Encapsulation; DRY
- **Current:**
  - `addCandidate`, `getCandidates`, `getForState` and `pruneCandidates` each special-case `first` vs `rest`.
  - `pruneCandidates` compacts in place with `retained - 1` index arithmetic.
  - `for (...values()) |*indices| indices.rest.deinit(allocator)` appears in `deinit`, `clear`, `pruneCandidates` and `pkix.install`.
- **Suggested:** Give `CandidateIndices` methods: `contains`, `add(allocator, index)`, `retainFrom(min) usize`, `deinit(allocator)`. Add a `PubkeyCache.deinitCandidates()` used by `deinit`, `clear` and `install`.
- **Why:** The small-vector optimization is fine, but its invariant should live in one type. Right now it is spread across four methods of another type and a second file.

### 11. Zig: named sync-committee tests folded into one anonymous `test {}` to drop a tidy allowlist entry
- **File:Line:** `src/state_transition/cache/sync_committee_cache.zig:137-221`; `test/tidy.zig` (removed allowlist entry, former lines 56-57)
- **Principle:** Don't refactor while fixing; descriptive test names
- **Current:** `test "initSyncCommittee - sanity"`, `test computeSyncCommitteeMap` and `test computeSyncCommitteeIndices` became three unnamed `{ }` blocks. Blocks 1 and 3 repeat the same ~20-line setup (pubkeys, committee, cache, node pool, validators view). The allowlist entry was then removed, because the stale-entry check fails once the file has only one test block.
- **Suggested:** Keep the three named tests and only add the `validators` argument. Leave `test/tidy.zig` untouched. If the validators-view setup is needed twice, extract a small fixture fn.
- **Why:** The file was already allowlisted, so this restructure is unrelated churn in a consensus-critical PR. A failure would now be reported against an anonymous test, and the tidy rule ("one inline test = usage example") is satisfied only in letter.

### 12. TS test helpers duplicate each other
- **File:Line:** `packages/state-transition/test/unit-minimal/cache/pubkeyCache.test.ts:137-164`; `packages/state-transition/test/unit/stateView/pubkeyCache.test.ts:58-115`; `packages/state-transition/test/utils/pubkeyCache.ts:17`; `packages/beacon-node/test/unit/api/impl/beacon/state/utils.test.ts:82`, `:104`; `packages/beacon-node/test/unit/api/impl/validator/registerValidator.test.ts:17`
- **Principle:** DRY in tests; meaningful names
- **Current:**
  - The "side first / canonical first" ordering switch and the ~10 branch-index assertions exist as `processBranches`/`expectBranchIndices` in one file and again inline in the stateView test. `getValidatorIndex` already accepts both state shapes, so one `expectBranchIndices` could serve both.
  - In beacon-node, `[0, 1, 2].map((index) => interopSecretKey(index).toPublicKey().toBytes())` appears three times, and there are four ad-hoc fake-state builders (`branch`, `state`, `view`, and the inline one in registerValidator).
  - `pubkeyCacheWithdrawalCredentials` is exported but only used inside its own module.
  - Every helper carries a `pubkeyCache` prefix that the module path already supplies. `slashPubkeyCacheFirstValidator` reads as slashing the cache.
- **Suggested:**
  - Move `expectBranchIndices` (typed on `PubkeyCacheState`) and an `orderBranches(order, side, canonical)` helper into `test/utils/pubkeyCache.ts`.
  - Add one `fakeStateView(pubkeys)` and an `interopPubkeys(n)` helper for the beacon-node tests.
  - Un-export the credentials helper and drop the redundant prefixes (`slashFirstValidator`, `forkEpoch`, `keyA`, `keyB`).
- **Why:** The TS and native suites are meant to prove the same property. A shared assertion keeps them provably aligned, and this saves ~60 lines.

### 13. beacon-node `chain/pubkeyCache.test.ts` mixes layers and couples to `onClockSlot` internals
- **File:Line:** `packages/beacon-node/test/unit/chain/pubkeyCache.test.ts:26-74`, `:76-123`
- **Principle:** Testability; tests live with the unit under test
- **Current:** The first three tests exercise `promoteFinalizedPubkeys`, a state-transition function, from beacon-node. The clock-tick test hand-builds ~20 chain members, including every pool pruned per slot, so it can invoke the private `BeaconChain.prototype["onClockSlot"]`.
- **Suggested:**
  - Move the `promoteFinalizedPubkeys` cases to `packages/state-transition/test/unit/cache/`.
  - Test `updateFinalizedPubkeys` directly, as the later tests in this file already do.
  - Drop the `onClockSlot` test or reduce it to the ordering assertion.
- **Why:** Any per-slot prune later added to `onClockSlot` would break this test for reasons unrelated to pubkeys.

### 14. Comments narrower than the code they document
- **File:Line:** `packages/state-transition/src/util/signatureSets.ts:92`; `src/state_transition/cache/pubkey_cache.zig:254`
- **Principle:** Comments state invariants, not one use case
- **Current:** Both say "Indexed slashings can include inactive validators outside the finalized cache/prefix." That is too narrow:
  - `resolveSignatureSet` is applied to *every* block signature set.
  - `getPubkeyForState` also serves proposer, randao and voluntary-exit sets.
  - The new tests cover active unfinalized sync-committee members and attesters.
- **Suggested:** "Indices at or beyond the finalized cache size are read from the state's registry." Or drop the comment.
- **Why:** As written, a reader will assume the fallback only matters for slashings and may remove it elsewhere.

### 15. Minor
- `packages/state-transition/src/stateView/stateViewFactory.ts:27`, `:64`: `createNativeBeaconStateView(opts.config, opts.stateBytes, true)` passes a positional boolean flag. Prefer an options object (`{syncPubkeys: true}`) so the call site says what `true` means.
- `packages/beacon-node/src/chain/chain.ts:1407-1432`: the sync and async branches of `updateFinalizedPubkeys` both run `promoteFinalizedPubkeys(this.pubkeyCache, state, finalizedEpoch); this.pubkeyCacheFinalizedEpoch = finalizedEpoch;`. A local `promote(state)` closure would serve both branches.
