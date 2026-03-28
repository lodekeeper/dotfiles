# Task: Full Fork Chain for IBeaconStateView

## Context
PR #9085 on branch `feat/fork-aware-state-view` (worktree `~/lodestar-fork-narrowing`) currently splits `IBeaconStateView` into:
- `IBeaconStateView` (base — has ALL fields from phase0 through capella)
- `IBeaconStateViewElectra` (electra+ fields)
- `IBeaconStateViewFulu` (fulu+ fields)
- `IBeaconStateViewGloas` (gloas/ePBS fields)

Nico wants the **full fork chain**: phase0 → altair → bellatrix → capella → deneb → electra → fulu → gloas, each interface only containing fields introduced at that fork.

## Target Interface Hierarchy

```
IBeaconStateView (base/phase0)
  └─ IBeaconStateViewAltair
       └─ IBeaconStateViewBellatrix
            └─ IBeaconStateViewCapella
                 └─ IBeaconStateViewDeneb
                      └─ IBeaconStateViewElectra (already exists)
                           └─ IBeaconStateViewFulu (already exists)
                                └─ IBeaconStateViewGloas (already exists)
```

## Field Distribution

### IBeaconStateView (base / phase0 only)
Keep these on the base interface — they exist since phase0 or are cross-fork utilities:
- `forkName`, `slot`, `fork`, `epoch`, `genesisTime`, `genesisValidatorsRoot`
- `eth1Data`, `latestBlockHeader`
- `previousJustifiedCheckpoint`, `currentJustifiedCheckpoint`, `finalizedCheckpoint`
- `getBlockRootAtSlot`, `getBlockRootAtEpoch`, `getStateRootAtSlot`, `getRandaoMix`
- All shuffling/committee methods: `getShufflingAtEpoch`, decision roots, `getPreviousShuffling`, etc.
- All proposer methods: `previousProposers`, `currentProposers`, `nextProposers`, `getBeaconProposer`
- All validator/balance methods: `effectiveBalanceIncrements`, `getBalance`, `getValidator`, etc.
- Fork choice: `computeUnrealizedCheckpoints`, `computeAnchorCheckpoint`
- Backward compat: `clonedCount`, `clonedCountWithTransferCache`, etc.
- Serialization: `loadOtherState`, `toValue`, `serialize`, `hashTreeRoot`, etc.
- State transition: `stateTransition`, `processSlots`
- Validation: `getVoluntaryExitValidity`, `isValidVoluntaryExit`
- Proofs: `getFinalizedRootProof`, `getSingleProof`, `createMultiProof`
- API: `proposerRewards`, `computeBlockRewards`, `computeAttestationsRewards`, `getLatestWeakSubjectivityCheckpointEpoch`

### IBeaconStateViewAltair (extends IBeaconStateView)
Move these from base:
- `previousEpochParticipation: Uint8Array`
- `currentEpochParticipation: Uint8Array`
- `getPreviousEpochParticipation(validatorIndex): number`
- `getCurrentEpochParticipation(validatorIndex): number`
- `currentSyncCommittee: altair.SyncCommittee`
- `nextSyncCommittee: altair.SyncCommittee`
- `currentSyncCommitteeIndexed: SyncCommitteeCache`
- `syncProposerReward: number`
- `getIndexedSyncCommitteeAtEpoch(epoch): SyncCommitteeCache`
- `getIndexedSyncCommittee(slot): SyncCommitteeCache`
- `getSyncCommitteesWitness(): SyncCommitteeWitness`
- `computeSyncCommitteeRewards(...): Promise<rewards.SyncCommitteeRewards>`
- `forkName: ForkPostAltair` (narrowed)

### IBeaconStateViewBellatrix (extends IBeaconStateViewAltair)
Move these from base:
- `latestExecutionPayloadHeader: ExecutionPayloadHeader`
- `latestBlockHash: Bytes32`
- `payloadBlockNumber: number`
- `isExecutionStateType: boolean`
- `isMergeTransitionComplete: boolean`
- `isExecutionEnabled(block): boolean`
- `forkName: ForkPostBellatrix` (narrowed)

### IBeaconStateViewCapella (extends IBeaconStateViewBellatrix)
Move these from base:
- `historicalSummaries: capella.HistoricalSummaries`
- `getExpectedWithdrawals(): {...}`
- `forkName: ForkPostCapella` (narrowed)

### IBeaconStateViewDeneb (extends IBeaconStateViewCapella)
- No new state fields (deneb adds blob sidecars to blocks, not state)
- `forkName: ForkPostDeneb` (narrowed)

### IBeaconStateViewElectra (extends IBeaconStateViewDeneb) — UPDATE existing
Change base from `IBeaconStateView` to `IBeaconStateViewDeneb`:
- `pendingDeposits`, `pendingDepositsCount`
- `pendingPartialWithdrawals`, `pendingPartialWithdrawalsCount`
- `pendingConsolidations`, `pendingConsolidationsCount`

### IBeaconStateViewFulu, IBeaconStateViewGloas — already correct, just update base chain

## Type Guards to Add

```ts
import {
  ForkPostAltair, ForkPostBellatrix, ForkPostCapella, ForkPostDeneb,
  isForkPostAltair, isForkPostBellatrix, isForkPostCapella, isForkPostDeneb,
} from "@lodestar/params";

export function isStatePostAltair(state: IBeaconStateView): state is IBeaconStateViewAltair {
  return isForkPostAltair(state.forkName);
}

export function isStatePostBellatrix(state: IBeaconStateView): state is IBeaconStateViewBellatrix {
  return isForkPostBellatrix(state.forkName);
}

export function isStatePostCapella(state: IBeaconStateView): state is IBeaconStateViewCapella {
  return isForkPostCapella(state.forkName);
}

export function isStatePostDeneb(state: IBeaconStateView): state is IBeaconStateViewDeneb {
  return isForkPostDeneb(state.forkName);
}
```

## Caller Update Strategy

When a caller accesses fork-specific fields on `IBeaconStateView`:

1. **If the function already operates in a known fork context** (e.g., it's called only for altair+ states), change the parameter type to the appropriate fork-specific interface (e.g., `IBeaconStateViewAltair`).

2. **If the function handles multiple forks**, add a type guard before accessing fork-specific fields:
   ```ts
   if (isStatePostAltair(state)) {
     state.currentSyncCommittee; // OK
   }
   ```

3. **If the field is already guarded by an `isForkPost*()` check on a string fork name**, replace it with the state type guard:
   ```ts
   // Before:
   if (isForkPostAltair(config.getForkName(state.slot))) {
     (state as any).currentSyncCommittee;
   }
   // After:
   if (isStatePostAltair(state)) {
     state.currentSyncCommittee;
   }
   ```

## Implementation Class (BeaconStateView)
- **No changes needed to the class implementation** — it already has all fork-specific getters with runtime checks
- Keep `implements IBeaconStateView` (the base) — structural typing handles the rest
- Type guards narrow `IBeaconStateView` to fork-specific interfaces at call sites

## Exports (index.ts)
Add new type exports and guard function exports:
```ts
export {
  type IBeaconStateView,
  type IBeaconStateViewAltair,
  type IBeaconStateViewBellatrix,
  type IBeaconStateViewCapella,
  type IBeaconStateViewDeneb,
  type IBeaconStateViewElectra,
  type IBeaconStateViewFulu,
  type IBeaconStateViewGloas,
  isStatePostAltair,
  isStatePostBellatrix,
  isStatePostCapella,
  isStatePostDeneb,
  isStatePostElectra,
  isStatePostFulu,
  isStatePostGloas,
} from "./stateView/interface.js";
```

## Validation
Must pass before committing:
1. `pnpm check-types` ✅
2. `pnpm lint` ✅ (run `pnpm lint --write` to auto-fix)
3. `pnpm build` ✅

## Git
- Single commit on branch `feat/fork-aware-state-view`
- Commit message: `feat: full fork chain for IBeaconStateView type narrowing`
- Sign: `git commit -S`
- Push: `git push fork feat/fork-aware-state-view`
