# Task: Fix 2 failing bellatrix networking gossip spec tests

## Context
We have bellatrix gossip validation spec test vectors overlaid into `packages/beacon-node/spec-tests/tests/`.
Running `pnpm vitest run packages/beacon-node/test/spec/presets/networking.test.ts --project spec-minimal` shows 115/117 passing.

The 2 failures are:
1. `gossip_beacon_block__ignore_parent_consensus_failed_execution_known` — expected "ignore", got "reject"
2. `gossip_beacon_block__ignore_parent_execution_verified_invalid` — expected "ignore", got "valid"

## Root Cause
The test harness in `packages/beacon-node/test/spec/utils/gossipValidation.ts` does not model the `payload_status` and `failed` metadata from `meta.yaml` for setup blocks. These test vectors have setup blocks that need to be:
- Imported into forkchoice with specific execution status
- Marked as failed or invalidated

Additionally, Lodestar's `validateGossipBlock` in `packages/beacon-node/src/chain/validation/block.ts` does not currently check if a parent block's execution status is `Invalid` — it should IGNORE such blocks per the bellatrix p2p-interface spec.

## What to fix

### 1. `packages/beacon-node/src/chain/errors/blockError.ts`
Add a new error code `PARENT_EXECUTION_INVALID` with field `parentRoot: RootHex`.

### 2. `packages/beacon-node/src/chain/validation/block.ts`
After the existing `PARENT_UNKNOWN` check (around line 90), add:
```typescript
import {ExecutionStatus} from "@lodestar/fork-choice";
// ...
// Bellatrix p2p-interface: If parent execution verification is complete,
// the block's parent must pass validation including execution verification; otherwise IGNORE.
if (isForkPostBellatrix(fork) && parentBlock.executionStatus === ExecutionStatus.Invalid) {
  throw new BlockGossipError(GossipAction.IGNORE, {
    code: BlockErrorCode.PARENT_EXECUTION_INVALID,
    parentRoot,
  });
}
```

### 3. `packages/beacon-node/test/spec/utils/gossipValidation.ts`
This is the main harness file. Changes needed:

**a) Add imports:**
- `chainConfigFromJson`, `chainConfigTypes` from `@lodestar/config`
- `ExecutionStatus` from `@lodestar/fork-choice`
- `DataAvailabilityStatus`, `ExecutionPayloadStatus`, `IBeaconStateView` from `@lodestar/state-transition`
- `SignedBeaconBlock` from `@lodestar/types`
- `validateGossipBlsToExecutionChange` from validation (not strictly needed for bellatrix, but good to have)

**b) Add `MetaPayloadStatus` type:**
```typescript
type MetaPayloadStatus = "VALID" | "NOT_VALIDATED" | "INVALIDATED";
```

**c) Update `MetaYaml` interface:**
The `blocks` array entries should have optional `payload_status?: MetaPayloadStatus`.

**d) Add `loadTestCaseChainConfig` function:**
Load per-case `config.yaml` if present, merge with `getConfig(fork)`. Parse lines manually, skip comments, only include keys in `chainConfigTypes`. Keep hex fork-version fields from `getConfig(fork)` (don't overwrite with parsed values that start with `0x`... actually just merge normally, `chainConfigFromJson` handles hex).

**e) Add helper functions:**
- `getDataAvailabilityStatusForFork(fork)` — returns `Available` for deneb+, `PreData` otherwise
- `computePostState(parentState, signedBlock, fork)` — runs `parentState.stateTransition(signedBlock, {verifyStateRoot: true, verifyProposer: true, executionPayloadStatus: valid, dataAvailabilityStatus: ...}, {})`
- `invalidateImportedBlock(chain, blockRootHex, parentRootHex)` — gets parent's executionPayloadBlockHash and calls `chain.forkChoice.validateLatestHash({executionStatus: Invalid, latestValidExecHash: parentHash, invalidateFromParentBlockRoot: blockRootHex})`

**f) Rewrite the block loop:**
Currently the block loop just skips `failed` blocks and imports the rest via `processBlock`. It needs to:
1. Track `blockStatesByRoot: Map<RootHex, IBeaconStateView>` and `rejectedFailedBlockRoots: Set<RootHex>`
2. First block (index 0) → just store state mapping to anchorStateView, continue
3. For subsequent blocks: look up parent state from `blockStatesByRoot`, compute post-state via `computePostState`
4. If `blockEntry.failed`:
   - If `payload_status === "VALID"`: import into forkchoice via `onBlock` with `ExecutionStatus.Valid`, store state
   - Else: add to `rejectedFailedBlockRoots`, continue
5. If `blockEntry.payload_status === "INVALIDATED"`: import via `onBlock` with `ExecutionStatus.Syncing`, store state, then call `invalidateImportedBlock` to set it to Invalid
6. Normal blocks: import via `processBlock` as before, store state

**g) Thread `rejectedFailedBlockRoots`:**
Pass it to `validateMessageForTopic`. In the block validation case, use `rejectedFailedBlockRoots.has(parentRootHex)` instead of `failedBlockRoots.has(parentRootHex)` for the parent-failed check.

**h) Use per-case config:**
Replace `getConfig(fork)` with `loadTestCaseChainConfig(testCaseDir, fork)` for the beaconConfig creation.

## Important notes
- YAML integers from `loadYaml` are BigInt — wrap with `Number()` where needed
- `MaybeValidExecutionStatus` excludes `ExecutionStatus.Invalid` — blocks can only be imported as `PreMerge`, `Valid`, `Syncing`, or `PayloadSeparated`
- `invalidateNodeByIndex` in protoArray throws if node is `Valid` — must import as `Syncing` first
- Run `pnpm lint --write` on changed files before committing
- Run both `--project spec-minimal` and `--project spec-mainnet` to verify

## Verification
```bash
pnpm vitest run packages/beacon-node/test/spec/presets/networking.test.ts --project spec-minimal
pnpm vitest run packages/beacon-node/test/spec/presets/networking.test.ts --project spec-mainnet
```
All tests should pass (117 minimal, ~118 mainnet).

## Files to read for reference
- `packages/beacon-node/test/spec/utils/gossipValidation.ts` (main harness)
- `packages/beacon-node/src/chain/validation/block.ts` (gossip block validation)
- `packages/beacon-node/src/chain/errors/blockError.ts` (error codes)
- `packages/fork-choice/src/forkChoice/forkChoice.ts` (onBlock, validateLatestHash)
- `packages/beacon-node/spec-tests/tests/minimal/bellatrix/networking/gossip_beacon_block/pyspec_tests/gossip_beacon_block__ignore_parent_execution_verified_invalid/meta.yaml`
