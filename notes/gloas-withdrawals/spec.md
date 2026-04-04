# Gloas Withdrawals Fix — Updated Spec

## Root Cause (Two Parts)

### Part 1: `preparePayloadAttributes()` sends wrong withdrawals
**File:** `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts` (function `preparePayloadAttributes`)

When computing payload attributes for the next block, `preparePayloadAttributes()` calls
`getExpectedWithdrawals()` unconditionally. But for Gloas, if the parent block is NOT full
(`!isParentBlockFull(state)`), `processWithdrawals()` skips entirely — so the EL should
receive `withdrawals = []`. Currently it gets full withdrawals, causing EL/CL mismatch.

**Fix:** Before calling `getExpectedWithdrawals()`, check `isParentBlockFull()`.
If not full, return `withdrawals: []`.

### Part 2: `processWithdrawals()` leaves stale `payloadExpectedWithdrawals`
**File:** `packages/state-transition/src/block/processWithdrawals.ts`

When `!isParentBlockFull(state)`, the function returns early (line 36) WITHOUT clearing
`state.payloadExpectedWithdrawals`. This means the state carries stale withdrawals from
a prior full block. When `processExecutionPayloadEnvelope()` later checks
`hash(payload.withdrawals) == hash(state.payloadExpectedWithdrawals)`, it can fail
because the expected value is stale.

**Fix:** On the early-return path, set `state.payloadExpectedWithdrawals` to empty:
```typescript
if (fork >= ForkSeq.gloas && !isParentBlockFull(state as CachedBeaconStateGloas)) {
  // Clear expected withdrawals so envelope validation doesn't use stale data
  (state as CachedBeaconStateGloas).payloadExpectedWithdrawals =
    ssz.capella.Withdrawals.toViewDU([]);
  return;
}
```

## Affected Call Paths

1. `preparePayloadAttributes()` in `produceBlockBody.ts` — called by:
   - `prepareExecutionPayload()` (block production)
   - `getPayloadAttributesForSSE()` (SSE events)
   - `prepareNextSlot()` (pre-computation)

2. `processWithdrawals()` in state-transition — called during block processing

## Implementation Plan

### File 1: `packages/state-transition/src/block/processWithdrawals.ts`
- Modify the early return at line ~36 to clear `payloadExpectedWithdrawals`:
```typescript
if (fork >= ForkSeq.gloas && !isParentBlockFull(state as CachedBeaconStateGloas)) {
  (state as CachedBeaconStateGloas).payloadExpectedWithdrawals =
    ssz.capella.Withdrawals.toViewDU([]);
  return;
}
```

### File 2: `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts`
- In `preparePayloadAttributes()`, around the withdrawals computation:
```typescript
// For Gloas: if parent block was not full, withdrawals are skipped
let withdrawals: capella.Withdrawal[];
if (fork >= ForkSeq.gloas) {
  const {isParentBlockFull} = await import("@lodestar/state-transition");
  if (!isParentBlockFull(prepareState as CachedBeaconStateGloas)) {
    withdrawals = [];
  } else {
    withdrawals = getExpectedWithdrawals(fork, prepareState).expectedWithdrawals;
  }
} else {
  withdrawals = getExpectedWithdrawals(fork, prepareState).expectedWithdrawals;
}
```
Note: Use static import, not dynamic. Check existing import patterns.

### Tests
- Unit test in `packages/state-transition/test/unit/block/processWithdrawals.test.ts`:
  - Verify `payloadExpectedWithdrawals` is empty after early return
- Integration test or existing test update for `preparePayloadAttributes`

## Spec reference
- consensus-specs v1.7.0-alpha.4 `specs/gloas/beacon-chain.md`
- `process_withdrawals()` — early return on `!is_parent_block_full`
- `process_execution_payload()` — checks `state.payload_expected_withdrawals`
- Fork initialization: `payload_expected_withdrawals=[]` (specs/gloas/fork.md:187)
