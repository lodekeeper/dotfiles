# Implementation Spec: PTC Window Caching in Lodestar

## Problem
PTC (Payload Timeliness Committee) computation uses effective balances that can change at epoch boundaries. When validating payload attestations for the last slot of the previous epoch from the first slot of the new epoch, the recomputed PTC may differ from what was originally assigned. The fix: cache PTC assignments in the beacon state as a sliding window.

## Reference
- Consensus-specs PR #4979 (potuz): "Add cached PTC window to the state"
- Analysis: `~/.openclaw/workspace/notes/ptc-window-pr4979/ANALYSIS.md`

## Design (follow proposer lookahead pattern)

### 1. SSZ Types — `packages/types/src/gloas/sszTypes.ts`

Add new type and state field:
```typescript
// New: PTC window stores (2 + MIN_SEED_LOOKAHEAD) epochs of PTC assignments
// Each entry is a Vector of PTC_SIZE validator indices for one slot
export const PtcWindow = new VectorCompositeType(
  new VectorBasicType(ValidatorIndex, PTC_SIZE),
  (2 + MIN_SEED_LOOKAHEAD) * SLOTS_PER_EPOCH
);
```

Add to `BeaconState` container in gloas sszTypes:
```typescript
ptcWindow: PtcWindow,  // [New in Gloas:EIP7732]
```

Also carry forward in heze sszTypes (same as proposerLookahead pattern).

### 2. Epoch Processing — new `packages/state-transition/src/epoch/processPtcWindow.ts`

Follow `processProposerLookahead.ts` pattern exactly:
```typescript
export function processPtcWindow(state: CachedBeaconStateGloas): void {
  // Shift all epochs forward by one (drop first SLOTS_PER_EPOCH entries)
  const window = state.ptcWindow.getAll();  // Get all nested vectors
  const remaining = window.slice(SLOTS_PER_EPOCH);
  
  // Compute new last epoch
  const epoch = state.epochCtx.epoch + MIN_SEED_LOOKAHEAD + 1;
  const startSlot = computeStartSlotAtEpoch(epoch);
  const newEpochPtcs = [];
  for (let i = 0; i < SLOTS_PER_EPOCH; i++) {
    newEpochPtcs.push(computePayloadTimelinessCommittee(state, startSlot + i));
  }
  
  // Write back to state
  state.ptcWindow = ssz.gloas.PtcWindow.toViewDU([...remaining, ...newEpochPtcs]);
}
```

Call this LAST in `processEpoch` (after `processProposerLookahead`), gated on `fork >= GLOAS`.

### 3. Fork Upgrade — `packages/state-transition/src/slot/upgradeStateToGloas.ts`

Add `initializePtcWindow(state)` call, similar to how proposerLookahead is initialized in upgradeToFulu:
```typescript
export function initializePtcWindow(state: CachedBeaconStateElectra | CachedBeaconStateFulu): Uint32Array[][] {
  const currentEpoch = state.epochCtx.epoch;
  
  // Empty previous epoch (zeros)
  const emptyPrevEpoch = Array.from({length: SLOTS_PER_EPOCH}, () => new Uint32Array(PTC_SIZE));
  
  // Current epoch + next epoch(s) based on MIN_SEED_LOOKAHEAD
  const ptcs: Uint32Array[] = [];
  for (let e = 0; e <= MIN_SEED_LOOKAHEAD; e++) {
    const epoch = currentEpoch + e;
    const startSlot = computeStartSlotAtEpoch(epoch);
    for (let i = 0; i < SLOTS_PER_EPOCH; i++) {
      ptcs.push(computePayloadTimelinessCommittee(state, startSlot + i));
    }
  }
  
  return [...emptyPrevEpoch, ...ptcs];
}
```

Set on the state: `stateGloasView.ptcWindow = ssz.gloas.PtcWindow.toViewDU(initializePtcWindow(pre));`

Also carry forward in `upgradeStateToHeze.ts` (just copy: `stateHeze.ptcWindow = stateGloas.ptcWindow`).

### 4. EpochCache — `packages/state-transition/src/cache/epochCache.ts`

**Key change:** Instead of computing PTC from scratch in `createEpochCache`, read from `state.ptcWindow`.

In `createEpochCache` (the `if (currentEpoch >= config.GLOAS_FORK_EPOCH)` block):
```typescript
// Post-PTC-window: read from state instead of computing
payloadTimelinessCommittees = [];
const ptcWindowAll = (state as CachedBeaconStateGloas).ptcWindow;
// Current epoch is at offset SLOTS_PER_EPOCH in the window
for (let i = 0; i < SLOTS_PER_EPOCH; i++) {
  payloadTimelinessCommittees.push(ptcWindowAll.get(SLOTS_PER_EPOCH + i).getAll());
}

// Previous epoch is at offset 0
if (!isGenesis && previousEpoch >= config.GLOAS_FORK_EPOCH) {
  previousPayloadTimelinessCommittees = [];
  for (let i = 0; i < SLOTS_PER_EPOCH; i++) {
    previousPayloadTimelinessCommittees.push(ptcWindowAll.get(i).getAll());
  }
}
```

In `afterProcessEpoch`, instead of recomputing PTC, read from the (already updated) state:
```typescript
// PTC was updated by processPtcWindow — read from state
this.previousPayloadTimelinessCommittees = this.payloadTimelinessCommittees;
// Current epoch PTC is at offset SLOTS_PER_EPOCH in the window
this.payloadTimelinessCommittees = [];
for (let i = 0; i < SLOTS_PER_EPOCH; i++) {
  this.payloadTimelinessCommittees.push(state.ptcWindow.get(SLOTS_PER_EPOCH + i).getAll());
}
```

The `getPayloadTimelinessCommittee(slot)` method stays the same — it already reads from epochCtx cache.

### 5. `computePayloadTimelinessCommittee` — existing function in `packages/state-transition/src/util/seed.ts`

This already exists as `computePayloadTimelinessCommitteesForEpoch`. We need a single-slot version or reuse the per-epoch function. The existing function `computePayloadTimelinessCommitteesForEpoch` returns all slots for one epoch — we can use it directly in `processPtcWindow` and `initializePtcWindow`.

### 6. Genesis state — `packages/beacon-node/src/node/genesis/` or test helpers

For `GLOAS_FORK_EPOCH=0`, the genesis state generator must call `initializePtcWindow`.

### 7. stateTransition.ts — `finalProcessEpoch`

The existing comment says `payloadTimelinessCommittees` is computed in `finalProcessEpoch`. After this change, it's populated from state (which was updated by `processPtcWindow`). Update the comment.

### 8. BeaconStateView

Check `packages/state-transition/src/stateView/beaconStateView.ts` — the `ptc()` accessor currently delegates to `epochCtx.getPayloadTimelinessCommittee(slot)`. This should remain the same (epochCtx serves as cache, state is the source of truth at initialization).

## Files to modify (summary)
1. `packages/types/src/gloas/sszTypes.ts` — add PtcWindow type + state field
2. `packages/types/src/heze/sszTypes.ts` — carry forward ptcWindow field  
3. `packages/state-transition/src/epoch/processPtcWindow.ts` — NEW file
4. `packages/state-transition/src/epoch/index.ts` — add processPtcWindow step
5. `packages/state-transition/src/slot/upgradeStateToGloas.ts` — initialize ptcWindow
6. `packages/state-transition/src/slot/upgradeStateToHeze.ts` — copy ptcWindow
7. `packages/state-transition/src/cache/epochCache.ts` — read PTC from state instead of computing
8. `packages/state-transition/src/stateTransition.ts` — update comment
9. `packages/state-transition/src/util/gloas.ts` or `seed.ts` — add initializePtcWindow helper
10. Test helpers (genesis) — initialize ptcWindow for GLOAS_FORK_EPOCH=0

## Commit message format
```
feat: add PTC window caching to beacon state

🤖 Generated with AI assistance
```

Do NOT reference consensus-specs PRs in the commit message.

## Acceptance criteria
- [ ] `pnpm check-types` passes
- [ ] `pnpm lint` passes
- [ ] `pnpm build` passes
- [ ] PtcWindow SSZ type defined correctly
- [ ] processPtcWindow runs last in processEpoch
- [ ] initializePtcWindow called during fork upgrade
- [ ] epochCtx reads PTC from state (not recomputed)
- [ ] heze state carries forward ptcWindow
- [ ] Unit test for processPtcWindow (shift + fill)
