# Fork-Aware IBeaconStateView — Implementation Spec

## Goal
Make IBeaconStateView fork-aware so that accessing fork-specific fields (e.g. `pendingDepositsCount` for electra+) requires a type guard, providing compile-time safety.

## Approach: Discriminated Capability Interfaces

### Step 1: Add `forkName` to IBeaconStateView

In `packages/state-transition/src/stateView/interface.ts`, add to base `IBeaconStateView`:
```ts
forkName: ForkName;
```

In `packages/state-transition/src/stateView/beaconStateView.ts`, implement:
```ts
get forkName(): ForkName {
  return this.config.getForkName(this.cachedState.slot);
}
```

### Step 2: Create fork-specific interfaces

REMOVE the electra/fulu/gloas-specific fields from base `IBeaconStateView` and put them in new interfaces IN THE SAME FILE (interface.ts):

```ts
/** Electra+ state fields — use isStatePostElectra() guard */
export interface IBeaconStateViewElectra extends IBeaconStateView {
  forkName: ForkPostElectra;
  pendingDeposits: electra.PendingDeposits;
  pendingDepositsCount: number;
  pendingPartialWithdrawals: electra.PendingPartialWithdrawals;
  pendingPartialWithdrawalsCount: number;
  pendingConsolidations: electra.PendingConsolidations;
  pendingConsolidationsCount: number;
}

/** Fulu+ state fields — use isStatePostFulu() guard */
export interface IBeaconStateViewFulu extends IBeaconStateViewElectra {
  forkName: ForkPostFulu;
  proposerLookahead: fulu.ProposerLookahead;
}

/** Gloas+ state fields — use isStatePostGloas() guard */
export interface IBeaconStateViewGloas extends IBeaconStateViewFulu {
  forkName: ForkPostGloas;
  executionPayloadAvailability: BitArray;
  latestExecutionPayloadBid: ExecutionPayloadBid;
  getBuilder(index: BuilderIndex): gloas.Builder;
  canBuilderCoverBid(builderIndex: BuilderIndex, bidAmount: number): boolean;
  validatorPTCCommitteeIndex(validatorIndex: ValidatorIndex, slot: Slot): number;
  processExecutionPayloadEnvelope(
    signedEnvelope: gloas.SignedExecutionPayloadEnvelope,
    opts?: ProcessExecutionPayloadEnvelopeOpts
  ): IBeaconStateView;
}
```

### Step 3: Type guard functions

Add to interface.ts (or a guards.ts, but same file is fine for now):
```ts
export function isStatePostElectra(state: IBeaconStateView): state is IBeaconStateViewElectra {
  return isForkPostElectra(state.forkName);
}

export function isStatePostFulu(state: IBeaconStateView): state is IBeaconStateViewFulu {
  return isForkPostFulu(state.forkName);
}

export function isStatePostGloas(state: IBeaconStateView): state is IBeaconStateViewGloas {
  return isForkPostGloas(state.forkName);
}
```

### Step 4: Update BeaconStateView class

The class already implements all these methods. Since TypeScript is structurally typed, after narrowing, the fields are accessible. No class changes needed beyond adding the `forkName` getter.

### Step 5: Export from index

In `packages/state-transition/src/index.ts`, export the new interfaces and guard functions:
```ts
export {
  IBeaconStateView,
  IBeaconStateViewElectra,
  IBeaconStateViewFulu,
  IBeaconStateViewGloas,
  isStatePostElectra,
  isStatePostFulu,
  isStatePostGloas,
} from "./stateView/interface.js";
```

### Step 6: Fix callers

After removing fields from IBeaconStateView, `pnpm check-types` will flag all callers. Fix each one:

#### 6a. chain.ts:1349-1355 (metrics)
Already has `if (isForkPostElectra(fork))` guard. Change to use state guard:
```ts
if (isStatePostElectra(headState)) {
  metrics.pendingDeposits.set(headState.pendingDepositsCount);
  // etc.
}
```

#### 6b. api/beacon/state/index.ts (getPendingDeposits, etc.)
Already has fork check + throw. After the guard, use the narrowed state:
```ts
// Option A: Use state guard directly
if (!isStatePostElectra(state)) {
  throw new ApiError(400, `Cannot retrieve pending deposits for pre-electra state fork`);
}
const pendingDeposits = state.pendingDeposits; // now typed
```

#### 6c. api/beacon/state/index.ts (getProposerLookahead)
Same pattern, use `isStatePostFulu(state)`.

#### 6d. chain/opPools/aggregatedAttestationPool.ts:362
Uses `ForkSeq[fork] >= ForkSeq.gloas ? state.executionPayloadAvailability : null`. 
Change to: `isStatePostGloas(state) ? state.executionPayloadAvailability : null`
The `state` parameter type stays as `IBeaconStateView` — the ternary handles narrowing.
Actually, since this is an inline ternary, TS won't narrow inside the ternary branch.
Better: extract to a variable or use a local helper:
```ts
const executionPayloadAvailability = isStatePostGloas(state) ? state.executionPayloadAvailability : null;
```

#### 6e. Gloas-only validation functions (executionPayloadBid, payloadAttestationMessage)
These get state from `chain.getHeadStateAtCurrentEpoch()` which returns `IBeaconStateView`.
They are only called from gloas gossip handlers, so at runtime the state is always gloas.
Add an assertion at the top:
```ts
const state = await chain.getHeadStateAtCurrentEpoch(RegenCaller.validateGossip...);
if (!isStatePostGloas(state)) {
  throw new Error("Expected gloas+ state for payload bid/attestation validation");
}
// Now state is IBeaconStateViewGloas
```

#### 6f. computeNewStateRoot.ts
Parameter is `postBlockState: IBeaconStateView`. This function is only called in gloas context.
Change signature to `postBlockState: IBeaconStateViewGloas` OR add assertion inside.
Prefer: change signature since the caller knows it's gloas.

#### 6g. importExecutionPayload.ts
Similar: `blockState` calls `processExecutionPayloadEnvelope`. Only in gloas context.
Add assertion or change parameter type.

## Files to modify
1. `packages/state-transition/src/stateView/interface.ts` — main changes
2. `packages/state-transition/src/stateView/beaconStateView.ts` — add forkName getter
3. `packages/state-transition/src/index.ts` — exports
4. `packages/beacon-node/src/chain/chain.ts` — metrics guard
5. `packages/beacon-node/src/api/impl/beacon/state/index.ts` — API endpoints
6. `packages/beacon-node/src/chain/opPools/aggregatedAttestationPool.ts` — inline guard
7. `packages/beacon-node/src/chain/validation/executionPayloadBid.ts` — assertion
8. `packages/beacon-node/src/chain/validation/payloadAttestationMessage.ts` — assertion
9. `packages/beacon-node/src/chain/produceBlock/computeNewStateRoot.ts` — param type or assertion
10. `packages/beacon-node/src/chain/blocks/importExecutionPayload.ts` — assertion

## Important constraints
- Target branch: `te/consume_beacon_state_view` (PR #8857's branch)
- PR base: `te/consume_beacon_state_view` on `ChainSafe/lodestar`
- Must build, lint, and typecheck clean
- Lint: `pnpm lint` (uses biome)
- Build: `pnpm build`
- Typecheck: `pnpm check-types`
- Use `.js` extensions in all imports (ESM)
- CODING_CONTEXT.md has full project conventions

## Non-goals (DO NOT change)
- Do NOT split bellatrix/capella/altair fields yet — scope to electra/fulu/gloas only
- Do NOT change `getHeadState()` return type
- Do NOT change `BeaconStateView` class implements clause
