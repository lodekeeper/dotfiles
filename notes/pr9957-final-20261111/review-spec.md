# PR #9957 — focused Fulu-genesis spec follow-up

Reviewer: review-devils-advocate
Reviewed commit: 4161c5d563c59241460c8a86c22b6609fcf7c953

## Devil's Advocate Review

### Overall Assessment

The approach is fundamentally sound: initialize the consensus-state proposer lookahead after genesis deposits and activations, using the existing proposer-selection implementation for every epoch in the required window.

### Scope and evidence boundaries

- Changed-file scope: `packages/state-transition/src/util/genesis.ts` and `packages/beacon-node/test/e2e/interop/genesisState.test.ts`, exclusively the 35 added lines in commit `4161c5d563c59241460c8a86c22b6609fcf7c953`.
- Read the closest existing Fulu upgrade/helper, genesis deposit/activation code, seed/proposer helpers, and Electra/Fulu epoch-cache construction as supporting context. Did not re-review the prior blob-removal changes.
- Comparison: #10600 commit `93d239ae9ab73845c12640dbf1e4e8c55ac5339c`, read from the same Lodestar repository.
- Primary spec references read with `git show` from `/home/openclaw/consensus-specs`: Fulu release tag `v1.6.1`, resolved to `5fa6edcca8ab4cf548653e6680b17b9d3e04d225`; corroborated against the existing checkout's HEAD `fc64cec037058aa763d81e9f9698fe448d2abf97` (2026-10-06). No fetch, checkout, or other mutation of the spec repository. These are pinned-source checks, not a claim to have checked the latest upstream master.

### Necessity and spec interpretation

This repairs missing consensus state, rather than masking a simulator symptom. The [Fulu fork specification](https://github.com/ethereum/consensus-specs/blob/5fa6edcca8ab4cf548653e6680b17b9d3e04d225/specs/fulu/fork.md#new-initialize_proposer_lookahead) describes its helper as: “Used to initialize the ``proposer_lookahead`` field in the beacon state at genesis and after forks.” Its loop concatenates proposer indices for `current_epoch + i`, with `i` ranging from zero through `MIN_SEED_LOOKAHEAD` inclusive. The same file's pure-Fulu-network note applies `upgrade_to_fulu` to genesis, and that upgrade initializes the field from the Electra state.

The [Fulu accessor and proposer helpers](https://github.com/ethereum/consensus-specs/blob/5fa6edcca8ab4cf548653e6680b17b9d3e04d225/specs/fulu/beacon-chain.md#modified-get_beacon_proposer_index) read this vector directly; they do not treat its default zero entries as an uninitialized sentinel. Lodestar likewise copies it into current/next-epoch proposer caches in `packages/state-transition/src/cache/epochCache.ts:427`. Omitting initialization therefore makes the serialized genesis state and subsequent proposer-cache construction wrong. Waiting for epoch processing does not initialize the missing current window correctly.

`genesis.ts:357` matches that required window: epoch zero through `GENESIS_EPOCH + MIN_SEED_LOOKAHEAD`, inclusive. `MIN_SEED_LOOKAHEAD` is one in both current presets, so the result covers epochs zero and one and has exactly `2 * SLOTS_PER_EPOCH` entries. Placement is correct: `applyDeposits` has applied pending-deposit balances, set effective balances and genesis activations, and populated `effectiveBalanceIncrements`; the validator tree was committed before the active-index reads. Eth1 entropy has also populated `randaoMixes` before any selection.

### Proposer/seed equivalence and the closest upgrade pattern

The spec's `get_beacon_proposer_indices` obtains active validator indices and `get_seed(state, epoch, DOMAIN_BEACON_PROPOSER)`, then hashes that epoch seed with each absolute slot before effective-balance-weighted proposer selection. Lodestar's `computeProposerIndices` in `packages/state-transition/src/util/seed.ts:145` does those same operations. Its `getSeed` uses the same historical-vector offset as [the pinned Phase0 seed helper](https://github.com/ethereum/consensus-specs/blob/5fa6edcca8ab4cf548653e6680b17b9d3e04d225/specs/phase0/beacon-chain.md#get_seed). Passing `ForkSeq.fulu` selects the Electra-and-later proposer sampling branch, as required.

The closest existing implementation is `packages/state-transition/src/slot/upgradeStateToFulu.ts:23`, which calls `initializeProposerLookahead` from `packages/state-transition/src/util/fulu.ts:12`. It concatenates the same per-epoch `computeProposerIndices` results. That helper relies on the pre-upgrade state's populated current/next shuffling caches. It is not safe to call it unchanged on this genesis builder's temporary cache: the cache is constructed before deposits, when its active-index shufflings are empty. The inline implementation appropriately reads the finalized genesis validator registry instead. Rebuilding all epoch caches merely to reuse the upgrade helper would not be a simpler fix.

### Comparison with #10600

The two implementations are equivalent for valid deposit-built genesis states:

- #10600 passes the already computed genesis `activeValidatorIndices` into a private helper and reuses it for every lookahead epoch.
- #9957 performs `getActiveValidatorIndices(state, epoch)` inside the same epoch loop, then calls the identical `computeProposerIndices(fork, state, {activeIndices}, epoch)` and uses the identical SSZ vector type.
- Newly deposited validators start with activation/exit epochs at `FAR_FUTURE_EPOCH` and `slashed: false` (`packages/state-transition/src/block/processDeposit.ts:120`). Genesis activation changes qualifying validators' activation epoch to zero (`genesis.ts:206`), without scheduling exits or intermediate future activations. Thus the active validator set is identical for epochs zero and one; no registry transition is performed between the two helper calls. The finalized effective-balance cache and all seed inputs are also identical.

#9957 incurs two additional registry scans relative to reusing the list already computed at `genesis.ts:291`. This is a small one-time cost in an explicitly slow genesis builder, not a demonstrated operational or correctness problem. Extracting a second helper or demanding #10600's shape is not warranted as a review objection. No extra protocol state or ongoing maintenance mechanism is introduced.

### Is the new Electra-versus-Fulu test meaningful?

Yes. `genesisState.test.ts:76` constructs states from the same 64 validators and entropy, with only the Fulu activation schedule changed. The Electra side is re-cached after genesis construction, so its shufflings and effective balances reflect the deposited validators. With the imported defaults, Fulu is not active during either Electra-oracle epoch (mainnet default epoch 411392; minimal default Infinity).

The Electra oracle follows `epochCache.ts:437` and `getBeaconProposersNextEpoch()` at line 878: it computes current and next proposer schedules from seeds and active-index shufflings rather than reading `proposerLookahead`. The Fulu side reads the newly initialized state field. Comparing the whole concatenated array checks all slots in both epochs, their ordering, and the complete vector length. Both paths intentionally share the already-existing low-level sampling primitive; this is not the new initializer being used to compute its own expected result. Identical fork-version bytes are unnecessary because proposer seeds use the proposer domain type, epoch and RANDAO mix, not the state fork version.

This is an appropriate regression test for missing genesis lookahead initialization. It is not an independent cryptographic/reference-vector test of the shared sampling primitive, nor exhaustive coverage of unusual balances or later fork-specific proposal eligibility. Those are not introduced by these 35 lines, and no additional test requirement is justified by this follow-up.

### Verification performed versus reported

- **Performed locally:** exact-head/source inspection and comparison, pinned-spec reads, and `git diff 4161c5d563^ 4161c5d563 --check -- packages/state-transition/src/util/genesis.ts packages/beacon-node/test/e2e/interop/genesisState.test.ts` (exit zero). Worktree `git status --short` was empty. No runtime tests, dependency installs, or mutation-based negative control were run by this reviewer.
- **Reported by the parent reviewer, not independently rerun here:** Tests run `43067490726` succeeded for PR head `4161c5d563c59241460c8a86c22b6609fcf7c953`, executed on synthetic merge `3b5a1b6` into `ab8f3f6`. Its E2E log records all three tests in `genesisState.test.ts` passing, including the new proposer-lookahead case (255 ms); aggregate E2E result: 282 passed, 32 skipped, two todo. Mixed clients and Multifork sims both ran and passed in run `43067490810` on this same PR head. This is head-bound CI integration evidence, not an exact-tree local test claim.

### Objections

None. No concrete necessity, simpler-alternative, root-cause, or spec-interpretation objection remains within the assigned scope.

### Signoff QA

The proposed statement that the inline fix is equivalent to #10600 and the new regression test plus Mixed clients/Multifork sims passed head-bound CI is supported by the source analysis and parent-reported CI evidence above. This genesis follow-up supplies no reason to retain the approval hold; the parent should reconcile its other scoped review surfaces before making the final approval decision. Updating the PR body's stale pre-Fulu publishing description is a separate metadata task, not an objection to this genesis fix.

### Verdict

**SOUND — no fundamental issues.**
