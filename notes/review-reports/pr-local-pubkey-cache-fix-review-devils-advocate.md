# Review Findings — review-devils-advocate — local-pubkey-cache-fix

Reviewer: review-devils-advocate
Reviewed commit: 4bce44fe3e338e581ce4a1fab1da4d154da26701
Generated at: 2026-11-13 10:22 UTC

## Devil's Advocate Review

Reviewer: review-devils-advocate
Reviewed commit: 4bce44fe3e338e581ce4a1fab1da4d154da26701

### Overall Assessment

The core of the change is necessary and fixes the root cause. The bug was global, branch-blind writes to a shared index map. The new design keeps a dense cache of finalized validators only, checks candidates against the requesting state, promotes on finality, and truncates the pubkeys file. That matches the bug class Lighthouse fixed in sigp/lighthouse#10569. LH's per-state STF maps aren't available in Lodestar, so the candidate map is a fair replacement. I have no objection to the approved design.

The problem is scope. About 25 of the 88 files (roughly 290 changed lines, about 18% of the diff) exist to give every signature builder a state-backed key fallback. The spec requires that fallback only for attester slashings. The spread is mostly self-inflicted: a Zig default flip empties the dense cache in every native fixture and spec vector. Promotion also carries an async lifecycle that LH does without.

### Objections

#### 1. A fallback in every builder goes beyond what the spec needs, and the robustness it buys is incomplete

**Challenge.** In the spec, a key outside the finalized prefix can only be required by `is_valid_indexed_attestation` inside `process_attester_slashing`. Every other signer must first be active or slashable. That requires `activation_eligibility_epoch <= state.finalized_checkpoint.epoch`, and activation then waits `1 + MAX_SEED_LOOKAHEAD` epochs. That gives at least 4 epochs of imports and promotion ticks before any such validator can sign.

**Evidence.**

Spec (phase0):

- Attester slashing, no activity check:
  - `pubkeys = [state.validators[index].pubkey for index in indices]` (`is_valid_indexed_attestation`)
  - `if is_slashable_validator(...)` … `assert slashed_any`. Only the intersection has to be slashable.
- Proposer slashing: `assert is_slashable_validator(proposer, get_current_epoch(state))` before `bls.Verify`.
- Voluntary exit: `assert is_active_validator(...)` and `assert get_current_epoch(state) >= validator.activation_epoch + SHARD_COMMITTEE_PERIOD` before `bls.Verify`.
- Activation queue: `is_eligible_for_activation`: `validator.activation_eligibility_epoch <= state.finalized_checkpoint.epoch`.
- Activation epoch (electra `process_registry_updates`): `activation_epoch = compute_activation_exit_epoch(current_epoch)` = `epoch + 1 + MAX_SEED_LOOKAHEAD`.
- Gloas PTC and Heze IL signers are committee members, so they are active.

Production reachability of the per-builder fallback:

- Zig in-STF signature verification is off by default:
  - `verifySignatures: !useBlsBatchVerify && !validSignatures` (`verifyBlocksStateTransitionOnly.ts:62-63`).
  - regen and historical callers pass `verifySignatures: false`.
- Block signatures are verified in TS `getBlockSignatureSets`, which already has a single choke point: `signatureSets.map(resolveSignatureSet)` (`signatureSets/index.ts:99`).
- The only production native signature check is `getVoluntaryExitValidity`. It checks activity and `SHARD_COMMITTEE_PERIOD` before the signature (`process_voluntary_exit.zig:76-108`), so its new fallback can never fire.

Gossip coverage is uneven:

- Gossip attestation, aggregate, sync message, PTC and block-proposer checks are still dense-only. `resolveSignatureSet` is used in `beacon-node/src` only for attester slashings (`validation/attesterSlashing.ts`, `opPool.ts`).
- LH #10569 put its fallback exactly there:
  - `HeadPubkeys` in about 8 gossip verifiers;
  - one `get_for_state` closure in the block verifier.
- So this diff is wider than the spec needs, yet still not as robust as LH's approach.

**Counter-proposal.**

- **Zig:** pass `validators` only along the attester-slashing chain:
  - `process_attester_slashing → is_valid_indexed_attestation → indexed_attestation.zig`;
  - plus the two `process_attestation_*` pass-throughs, which share that builder;
  - keep `getPubkeysForState`.
- **Zig, revert:**
  - the fallback in the proposer, randao, exit, proposer-slashing, payload-attestation and sync-committee builders, plus `state_transition.zig`;
  - `getPubkeyForState`, `getPubkeyBytesForState` and `aggregateForState` (`pubkey_cache.zig:255-310`).
- **TS:** keep the cheap `resolveSignatureSet` choke point.
- **Observability:** add a `pubkey_cache_dense_miss_total{path}` metric, so a promotion stall shows up instead of being silently papered over.
- **If the real goal is surviving a promotion stall:** do it the LH way at choke points. Pass the head state into the `chain.bls` gossip verification wrapper instead of adding a parameter to each Zig builder.
- **Savings:** about 25 files (10 TS, 15 Zig) and about 140 logic lines. Another ~150 lines of unrelated test consolidation in `sync_committee_cache.zig` and `test/tidy.zig` also go. That brings the PR from 88 files to about 62.

**Impact if ignored.**

- Every future Zig signature builder (Heze IL, Gloas proposer preferences, the next fork) must remember `validators: anytype` and the `*ForState` variant. The dense-only `getPubkey` stays public and still compiles.
- Each builder now has two key-resolution paths to keep in step across TS and Zig.
- Gossip still rejects valid messages if promotion stalls, so the protection is only partial.

#### 2. The Zig `EpochCache` default flip is why the fallback spread, and it leaves the production dense path untested by native spec vectors

**Challenge.** In Zig, `skip_sync_pubkeys=false` now registers candidates only (`epoch_cache.zig:218-225`), and `skip_sync_pubkeys=true` registers nothing. TS keeps the opposite meaning: `!skipSyncPubkeys` runs a trusted `syncPubkeys`, otherwise candidates (`epochCache.ts:350`). As a result, no native test fixture ever has a populated dense cache.

**Evidence.**

- The native spec runner (`test/spec/test_case.zig:101,123`) goes through `generate_state.zig:216-239`. That creates a fresh `PubkeyCache` and calls with `.skip_sync_pubkeys = false`.
- Nothing in the native STF appends any more. Dense size is therefore 0 for every native spec vector and Zig STF unit test.
- So every native vector exercises only the decompress-from-state branch. The TS spec runner, which syncs trusted pre-states, exercises only the dense branch. Same logic, two runtimes, no overlap in what is tested.
- Around 15 existing binding tests call `createFromBytes(bytes, config)` and are now candidate-only.
- This is also why fallbacks had to go into every Zig builder: a dense-only builder would fail every vector with `PubkeyNotFound`.
- `IMPL_REPORT.md` says the full spec vectors were not run.

**Counter-proposal.**

- Make Zig match TS:
  - `skip_sync_pubkeys=false` → trusted `syncPubkeys` (fixtures, startup anchor);
  - `skip_sync_pubkeys=true` → register candidates beyond the dense size.
- `BeaconStateView.createFromBytes` passes `skip_sync_pubkeys = !syncPubkeys`, which keeps candidate-only as the production default. The special anchor block (`syncPubkeys` + `pruneCandidates`) then folds into the option. About 6 lines in `epoch_cache.zig` and `bindings/napi/BeaconStateView.zig`.
- Then run the full native spec suite once. Any vector that signs with a validator created in that same vector (which needs finality plus 5 epochs within one vector) should be handled in the runner: promote from the post-state's finalized checkpoint after each block, about 10 lines, mirroring production.

**Impact if ignored.**

- Regressions on the production hot path (dense append, `getPubkeys` and `aggregate` on dense entries) go undetected by thousands of native vectors.
- TS and Zig are validated on different code paths.
- One option name means opposite things in the two runtimes during the Gloas→Heze native port.

#### 3. Promotion uses an async lifecycle that LH shows isn't needed

**Challenge.** `updateFinalizedPubkeys` adds:

- two fields (`chain.ts:238-239`);
- a clock-tick hook (`chain.ts:1897`);
- async head-state regen with single-flight and retry (`chain.ts:1407-1432`);
- a mock entry and three lifecycle tests.

All of this is driven by fork-choice finality plus the head state. LH promotes synchronously during import, from the imported state's own `finalized_checkpoint`, in about 20 lines with no regen.

**Evidence.**

- `postState` is already in scope in `importBlock` (`importBlock.ts:99`).
- Every imported block descends from the store's finalized checkpoint, and the post-state's own finalized checkpoint is an ancestor of it.
- So the prefix up to the last validator with `activation_eligibility_epoch <= postState.finalizedCheckpoint.epoch` is identical on every viable branch. This is the same soundness argument the diff relies on for the head state.
- The only latency difference is at most one block after a tick-time checkpoint pull-up. The activation margin (`1 + MAX_SEED_LOOKAHEAD`) absorbs that, and the existing TS `resolveSignatureSet` already covers block verification.

**Counter-proposal.** In `importBlock`:

```ts
const finalizedEpoch = postState.finalizedCheckpoint.epoch;
if (finalizedEpoch > this.pubkeyCacheFinalizedEpoch) {
  promoteFinalizedPubkeys(this.pubkeyCache, postState, finalizedEpoch);
  this.pubkeyCacheFinalizedEpoch = finalizedEpoch;
}
```

Drop:

- the clock hook;
- the regen path;
- `pubkeyCachePromotion`;
- the mocked method;
- the three regen/clock lifecycle tests (about 110 test lines).

**Impact if ignored.**

- A consensus-critical cache gets a new async failure mode: regen fails, promotion is deferred, and the only trace is a log line.
- `RegenCaller.onForkChoiceFinalized` gets reused for something other than finalization.
- More lifecycle surface to maintain on every fork-choice or regen refactor.

### Verdict

**RECONSIDER.** Keep the approved design and its necessary call sites:

- finalized dense cache;
- state-checked candidates;
- state-aware pubkey→index lookups;
- pkix truncation;
- the attester-slashing fallback, which the spec requires.

Trim the rest:

- limit the fallback to the attester-slashing path (Objection 1);
- restore Zig/TS default parity so the native fixtures keep a dense cache (Objection 2);
- promote synchronously from `postState` (Objection 3).

Expected result: about 60 files instead of 88, with the same correctness guarantees.
