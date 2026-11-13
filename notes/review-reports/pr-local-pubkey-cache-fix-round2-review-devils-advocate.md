# Round-2 Devil's Advocate Review

Reviewer: review-devils-advocate
Reviewed commit: c45c978f0cc34ad211b89725effb0757362e5435
Generated at: 2026-11-13 12:06 UTC

## Overall Assessment

**SOUND.** The approved finalized dense prefix plus state-checked candidate map addresses the actual branch-divergent registry problem without making every signature builder state-dependent. The follow-up resolves my three earlier objections. Its checkpoint extension is necessary: my earlier import-only counter-proposal did not cover activation during skipped epochs.

## Objections

None. I found no evidenced fundamental objection requiring a counter-proposal in the changed files.

## Reconciliation of the prior review

### 1. Narrow signature fallback

The native fallback is now confined to indexed attestations and their attestation/slashing callers. `src/state_transition/signature_sets/indexed_attestation.zig:41` bounds every signer by the requesting registry and uses its actual key when the dense entry is absent. Proposer, RANDAO, voluntary exit, proposer-slashing and sync-committee builders remain dense-only. TS retains one resolution choke point in `packages/state-transition/src/signatureSets/index.ts:102` and explicit standalone slashing resolution.

This is the necessary exception, not a promotion-stall workaround. In pinned consensus-specs `v1.7.0-beta.4` (`aa16bb4c156184e9548a997d53efaf2a228a6304`), `phase0/beacon-chain.md:is_valid_indexed_attestation` resolves every indexed participant from the registry; `process_attester_slashing` separately requires at least one slashable validator in the intersection. It does not require every signature participant to be active or slashable. Ordinary valid signing duties still have the activation/finality margin.

### 2. Trusted versus candidate loading

`packages/state-transition/src/cache/epochCache.ts:350` and `src/state_transition/cache/epoch_cache.zig:218` now agree: false/default performs trusted dense synchronization and candidate pruning; true registers only candidates beyond the dense prefix. The public native binding defaults to candidate mode. `packages/state-transition/src/stateView/stateViewFactory.ts:25` explicitly chooses trusted mode for startup and candidate mode for historical regeneration. `loadCachedBeaconState` and `loadOtherState` retain candidate-only behavior.

Consequently, native fixture construction is no longer forced to manufacture an empty dense cache. The follow-up report records native STF spec runs in both presets. I inspected the corrected loading path and relevant tests, but did not rerun those suites or independently certify their reported counts.

### 3. Synchronous promotion, including the gap in my previous proposal

`packages/beacon-node/src/chain/blocks/importBlock.ts:160` promotes only after successful `forkChoice.onBlock`, using the imported post-state. `packages/beacon-node/src/chain/chain.ts:670` shares that synchronous operation with the existing checkpoint listener at line 1982. The async head lookup, clock retry and single-flight machinery are gone.

Import alone is insufficient. Already accepted participation can advance finality during empty-slot processing, schedule activation, and reach that activation without another import. The added checkpoint call handles this before a later dense-only native committee or proposer consumer needs the key. It adds no asynchronous failure lifecycle. `packages/beacon-node/test/unit/chain/regen/regen.test.ts` exercises successive actual epoch transitions and the real checkpoint listener for TS and native views, including promotion before activation, candidate pruning, committee membership and proposer-key availability.

## Independent checkpoint provenance audit

I did not treat the follow-up report's trust assertion as proof. I traced the following production paths in the exact clean reviewed tree:

- There are two production `ChainEvent.checkpoint` emit sites: accepted `importBlock`, and `processSlotsToNearestCheckpoint` in regeneration. The former is downstream of block verification and successful fork-choice insertion.
- For an incoming block, `StateRegenerator.getPreState` first resolves its parent from fork choice. Regeneration receives the accepted parent and requested slot, not the incoming block's operations. Its checkpoint states are empty-slot descendants of that parent.
- Regeneration's exact-state cache misses traverse fork-choice-known ancestry and replay previously imported blocks, checking each computed state root. Main block-state cache population comes from the startup anchor, accepted imports and those replays.
- Checkpoint-cache insertion comes from the trusted startup anchor, accepted epoch-boundary imports and empty-slot regeneration. Regeneration inserts then synchronously emits the checkpoint before progressing to the next epoch. A later cache hit therefore does not skip an otherwise unperformed promotion. Startup is separately covered by trusted full-anchor synchronization.
- `QueuedStateRegenerator.init` invokes `PersistentCheckpointStateCache.init`, which removes previous-process persisted checkpoint keys. Later disk reloads use this process's checkpoint population, rather than silently trusting old orphan state files.

The promotion helper at `packages/state-transition/src/cache/pubkeyCache.ts:49` finds the last validator eligible by the state's finalized epoch and appends the entire preceding prefix. Earlier ineligible entries must be included to preserve density, but their registry placement is fixed by the later eligible entry's finalized placement. Remaining suffix entries stay candidates. Pinned phase0 activation eligibility requires finalized queue placement, and activation is delayed by `1 + MAX_SEED_LOOKAHEAD`; the per-epoch synchronous checkpoint hook closes the skipped-import gap before ordinary signing duties begin.

Under the existing trusted-anchor and consensus-finality assumptions, this does not make unverified block operations authoritative merely because a gossip caller requested a pre-state. No extra broad state-backed proposer/gossip fallback is justified by the traced paths.

## Exceptional epoch-batch sequencing

I accept `BATCH_BASELINE_REVIEW.md`'s correction: the earlier failure was introduced, not wholly pre-existing. Identical use of `preState0` does not imply identical behavior when baseline defers dense-key lookup and the signature loop yields after eight blocks. I checked that scheduling and key-resolution explanation against the source; I did not rerun its historical reproductions.

The follow-up fixes that dependency at the right boundary:

- `packages/beacon-node/src/chain/blocks/verifyBlock.ts:180` detects attester-slashing proofs referencing indices absent from the initial registry. Only those exceptional batches wait for ordered transitions before extracting signature sets. Trusted-signature mode bypasses the unnecessary detection-dependent wait.
- `packages/beacon-node/src/chain/blocks/verifyBlocksSignatures.ts:50` supplies the first block's original pre-state and each later block's preceding post-state as the key registry. It retains the original epoch context for domains, shuffling, sync committees and PTCs.
- Because a batch is constrained to one epoch and the first pre-state is already dialed into that epoch, there is no intervening epoch registry mutation between a preceding post-state and the next block. Attester slashings precede deposits within a block, so using a later block's post-state instead would be the wrong simplification.
- Ordinary batches still submit signature work before transitions. The correction neither promotes speculative keys densely nor trusts a branch-blind candidate. Narrowing the dependency further to per-proof scheduling could regain overlap only for exceptional traffic while adding more ordering machinery; I found no concrete reason that complexity is necessary.

The committed regression constructs real signed phase0/Electra deposits and mixed active/inactive slashing proofs, resets the generation cache, then invokes `verifyBlocksInEpoch` with the real single-thread verifier. It also covers conflicting-candidate signatures, missing indices, trusted signatures and the non-batch-STF option. This is meaningful caller coverage, not an end-to-end network/engine test. The parent and other reviewers own additional current-head worker-pool verification.

## Startup snapshot validation

`packages/cli/src/cmds/beacon/pubkeysFile.ts:27` now compares the complete retained registry prefix through native `matchesValidators`, resets on any mismatch, and truncates only the suffix beyond the startup anchor. The native comparator checks each retained compressed key against the corresponding serialized validator record under a shared lock. This closes the interior-swap hole; endpoint comparison cannot establish the required invariant. The existing trust requirement for the snapshot file itself remains explicit in the native cache API.

## PR-body sanity check

The technical summary in `/home/openclaw/scratch/pubkey-poison/review2/PR_BODY_DRAFT.md` is consistent with the reviewed implementation except for one causal wording correction, sent to the parent:

> Replace “exceptional batches containing slashings of newly added validators” with “exceptional batches whose attester-slashing proofs reference validators added earlier in the batch.”

The newly added inactive validator can be a signature participant without itself being slashable; the regression slashes existing validator 0. This is a PR-copy correction, not a code objection. The pending Validation section remains intentionally unpublished and must be replaced with the parent's observed results.

## Executed scope and limits

Read-only source/diff/persona/report review, local pinned-spec inspection and git revision/cleanliness checks only. HEAD was confirmed as the exact commit above, with no tracked staged or unstaged changes at the final check. No tests, builds, installs, commits, external writes or source edits were performed by this reviewer. Only this review artifact and its workspace backlog status were written.

## Verdict

**SOUND.** No remaining fundamental objection. This is an approach review for the exact recorded commit, not a substitute for the parent's outstanding exact-head verification gates.
