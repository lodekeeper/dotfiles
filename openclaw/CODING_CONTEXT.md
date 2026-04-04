# CODING_CONTEXT.md — Current Task

## Task: Fix Gloas Withdrawals in Payload Attributes and State Transition

Two related bugs where Gloas withdrawals are computed/stored incorrectly when the parent block is not full.

### Fix 1: `packages/state-transition/src/block/processWithdrawals.ts`

The early-return path (line ~36) does NOT clear `state.payloadExpectedWithdrawals`, leaving stale data from a prior full block. This breaks envelope validation later.

**Current code (around line 34-37):**
```typescript
  if (fork >= ForkSeq.gloas && !isParentBlockFull(state as CachedBeaconStateGloas)) {
    return;
  }
```

**Change to:**
```typescript
  if (fork >= ForkSeq.gloas && !isParentBlockFull(state as CachedBeaconStateGloas)) {
    // Clear expected withdrawals so envelope validation doesn't use stale data from a prior full block
    (state as CachedBeaconStateGloas).payloadExpectedWithdrawals = ssz.capella.Withdrawals.toViewDU([]);
    return;
  }
```

`ssz` is already imported at top of file (`import {..., ssz} from "@lodestar/types"`).

### Fix 2: `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts`

In the `preparePayloadAttributes()` function (starts at line 744), the withdrawals computation at line ~777-778 is unconditional:

```typescript
    (payloadAttributes as capella.SSEPayloadAttributes["payloadAttributes"]).withdrawals =
      prepareState.getExpectedWithdrawals().expectedWithdrawals;
```

For Gloas, if the parent block is not full, withdrawals should be `[]` (the EL should not include them).

**Replace the withdrawals section (lines ~773-779) with:**
```typescript
    if (!isStatePostCapella(prepareState)) {
      throw new Error("Expected Capella state for withdrawals");
    }

    let withdrawals: capella.Withdrawal[];
    if (ForkSeq[fork] >= ForkSeq.gloas && isStatePostGloas(prepareState) && !isParentBlockFull(prepareState)) {
      // Gloas: parent block was not full → process_withdrawals returns early → no withdrawals
      withdrawals = [];
    } else {
      withdrawals = prepareState.getExpectedWithdrawals().expectedWithdrawals;
    }

    (payloadAttributes as capella.SSEPayloadAttributes["payloadAttributes"]).withdrawals = withdrawals;
```

**Add to the existing import from `@lodestar/state-transition` (line ~17-25):**
```typescript
  isParentBlockFull,
```

The import block already imports `isStatePostGloas` from `@lodestar/state-transition`. Just add `isParentBlockFull` to the same import statement.

Also add `CachedBeaconStateGloas` to the types import IF `isParentBlockFull` requires it — but check the type signature first. Actually, `isParentBlockFull` takes `CachedBeaconStateGloas` as parameter. Since we gate on `isStatePostGloas(prepareState)`, the type narrows correctly. But `isParentBlockFull` expects `CachedBeaconStateGloas` specifically, so you may need a cast. Check the actual `IBeaconStateViewBellatrix` interface — if `isStatePostGloas` narrows to a type that has `latestExecutionPayloadBid` and `latestBlockHash`, it should work.

If you need a cast, do:
```typescript
!isParentBlockFull(prepareState as unknown as CachedBeaconStateGloas)
```
But FIRST check if `isStatePostGloas` narrows enough. Prefer NO cast.

### DO NOT change:
- Any other functions in `produceBlockBody.ts`
- Anything in `processExecutionPayloadEnvelope.ts`
- Test fixtures or test infrastructure files

### Tests
Add a test in `packages/state-transition/test/unit/block/` if there is an existing `processWithdrawals.test.ts`. If not, create one with a minimal test:
- Create a mock Gloas state where `isParentBlockFull` returns false
- Run `processWithdrawals` on it
- Assert `payloadExpectedWithdrawals` is empty (length 0)

### Pre-push checklist
1. `pnpm lint` — must pass (run `pnpm lint --write` to autofix)
2. `pnpm check-types` — must pass
3. `pnpm build` — must succeed
4. Verify diff: only the 2-3 files above should be changed

### Project conventions
- Node v24: `source ~/.nvm/nvm.sh && nvm use 24`
- Build: `pnpm build`
- Lint: `pnpm lint` (MANDATORY before commit)
- All commits must be signed with GPG
