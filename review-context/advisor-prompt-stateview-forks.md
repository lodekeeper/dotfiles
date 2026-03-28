# Advisory: Extend IBeaconStateView fork-specific type narrowing to all forks

## Context

PR #9085 on ChainSafe/lodestar adds fork-specific sub-interfaces to `IBeaconStateView`:
- `IBeaconStateViewElectra` (pendingDeposits, pendingConsolidations, etc.)
- `IBeaconStateViewFulu` (proposerLookahead)
- `IBeaconStateViewGloas` (builders, PTC, execution envelope processing)

Plus type guards: `isStatePostElectra()`, `isStatePostFulu()`, `isStatePostGloas()`.

Nico's feedback: **Why only from Electra? What about earlier forks?**

## Current state of the interface

The base `IBeaconStateView` currently contains ALL fields from phase0 through capella flattened into one interface. This means a Phase0 state view exposes `currentSyncCommittee` (Altair), `latestExecutionPayloadHeader` (Bellatrix), and `historicalSummaries` (Capella) at the type level — even though those fields don't exist pre-fork.

### Fork-specific fields currently on the base interface:

**Altair added:**
- `previousEpochParticipation`, `currentEpochParticipation` (replaced Phase0 attestation fields)
- `inactivityScores`
- `currentSyncCommittee`, `nextSyncCommittee`
- `currentSyncCommitteeIndexed`, `syncProposerReward`
- `getIndexedSyncCommitteeAtEpoch()`

**Bellatrix added:**
- `latestExecutionPayloadHeader` (and derived: `latestBlockHash`, `payloadBlockNumber`)

**Capella added:**
- `historicalSummaries`

**Deneb:** No new state fields (blob changes were block-level)

### Existing `as CachedBeaconState*` casts in beacon-node/src (pre-Electra)

These are on the raw CachedBeaconState types, NOT on IBeaconStateView — but they show where fork-specific access happens:

```
# Altair casts (6 sites)
api/impl/beacon/state/index.ts:251    state as CachedBeaconStateAltair
api/impl/beacon/state/index.ts:318    state as CachedBeaconStateAltair
chain/opPools/aggregatedAttestationPool.ts:756  state as CachedBeaconStateAltair
chain/blocks/importBlock.ts:378       postState as CachedBeaconStateAltair
chain/validation/syncCommitteeContributionAndProof.ts:56,88  headState as CachedBeaconStateAltair
chain/validatorMonitor.ts:742         headState as CachedBeaconStateAltair

# Bellatrix casts (3 sites)
chain/produceBlock/produceBlockBody.ts:339,354  currentState as CachedBeaconStateBellatrix
chain/produceBlock/produceBlockBody.ts:391      currentState as CachedBeaconStateBellatrix

# Capella casts (1 site)
chain/produceBlock/produceBlockBody.ts:782      prepareState as CachedBeaconStateCapella

# Executions (Bellatrix+) casts (4 sites)
chain/prepareNextSlot.ts:126,149                prepareState as CachedBeaconStateExecutions
chain/produceBlock/produceBlockBody.ts:452,622,723,739  state/prepareState as CachedBeaconStateExecutions
```

## Question for advisor

1. **Should we split IBeaconStateView into a full fork chain?** e.g.:
   - `IBeaconStateView` (phase0 only)
   - `IBeaconStateViewAltair extends IBeaconStateView` (adds sync committee, participation)
   - `IBeaconStateViewBellatrix extends IBeaconStateViewAltair` (adds execution payload header)
   - `IBeaconStateViewCapella extends IBeaconStateViewBellatrix` (adds historical summaries)
   - `IBeaconStateViewDeneb extends IBeaconStateViewCapella` (no new fields, but type narrowing)
   - `IBeaconStateViewElectra extends IBeaconStateViewDeneb` (pending deposits, etc.)
   - `IBeaconStateViewFulu extends IBeaconStateViewElectra` (proposer lookahead)
   - `IBeaconStateViewGloas extends IBeaconStateViewFulu` (builders, PTC, etc.)

2. **Or is a pragmatic cutoff appropriate?** Arguments:
   - Lodestar only supports post-Deneb on mainnet (no Phase0/Altair/Bellatrix/Capella-only states in practice)
   - The pre-Electra fields have been on the base interface since it was created — changing them is higher churn
   - The Altair/Bellatrix casts in beacon-node are on `CachedBeaconState*`, not on `IBeaconStateView`

3. **Impact assessment:** If we do the full split, how many callers of `IBeaconStateView` need updating? Are there places that pass `IBeaconStateView` but access Altair+ fields without guards?

4. **Recommendation:** Full split, partial split (e.g., Bellatrix+ since that's the earliest practical fork), or keep Electra+ only?

## Files for reference

- `review-context/stateview-interface.ts` — current interface after PR #9085
- `review-context/stateview-impl.ts` — current implementation (beaconStateView.ts)
- `review-context/pre-electra-casts.txt` — grep of pre-Electra unsafe casts

## Constraints

- Don't make the types so strict that every caller needs 8 levels of narrowing for basic operations
- The `createBeaconStateView` factory returns `IBeaconStateView` — the return type needs to work with the split
- `@lodestar/params` already has `ForkPostAltair`, `ForkPostBellatrix`, `isForkPostAltair()`, etc. — they're ready to use
- Minimize churn on code that already works correctly
