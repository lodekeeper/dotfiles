# Bellatrix Fork Choice — Spec Study Notes

*Spec: `consensus-specs/specs/bellatrix/fork-choice.md`*
*Studied: 2026-02-17*

## Overview

Bellatrix fork choice introduces the PoS transition mechanics — the bridge from Proof-of-Work to Proof-of-Stake. Key additions:

1. **`notify_forkchoice_updated`** — Engine API call to keep EL in sync with CL fork choice
2. **Terminal PoW block validation** — `validate_merge_block` ensures the transition block references a valid terminal PoW block
3. **`should_override_forkchoice_update`** — Proposer boost re-org logic (suppress FCU if block is weak)
4. **`on_block` modification** — Merge transition check added before storing block

## Key Concepts

### Terminal PoW Block
The last PoW block before the merge. Must satisfy:
- `block.total_difficulty >= TERMINAL_TOTAL_DIFFICULTY`
- `parent.total_difficulty < TERMINAL_TOTAL_DIFFICULTY`

Or if `TERMINAL_BLOCK_HASH` is set as override, the execution payload's parent hash must match it (used for controlled transitions on testnets).

### `notify_forkchoice_updated`
Three atomic actions:
1. Re-org EL chain to make `head_block_hash` the head
2. Update safe block hash
3. Apply finality up to `finalized_block_hash`

Plus optionally initiates payload building if `payload_attributes` provided.

### Safe Block Hash
Spec: `get_safe_execution_block_hash()` returns the justified checkpoint's execution block hash.

### Proposer Boost Re-org (`should_override_forkchoice_update`)
If enabled, checks 8 conditions before suppressing FCU:
1. Head arrived late (past attestation deadline)
2. Shuffling is stable (not crossing epoch boundary)
3. FFG competitive (parent's FFG info is as good as head's)
4. Finalization OK (chain is finalizing at acceptable rate)
5. Proposer is connected (we know we'll propose next slot)
6. Single slot re-org only (parent is one slot before head)
7. Head is weak (low weight from attestations)
8. Parent is strong (sufficient weight to serve as re-org base)

## Lodestar Implementation

### `notify_forkchoice_updated`

**Interface:** `packages/beacon-node/src/execution/engine/interface.ts:135`
```typescript
notifyForkchoiceUpdate(
  fork: ForkName,
  headBlockHash: RootHex,
  safeBlockHash: RootHex,
  finalizedBlockHash: RootHex,
  payloadAttributes?: PayloadAttributes
): Promise<PayloadId | null>;
```

**HTTP impl:** `packages/beacon-node/src/execution/engine/http.ts:339`
- Selects Engine API version based on fork: v1 (Bellatrix), v2 (Capella+), v3 (Deneb+)
- Handles response statuses: VALID, SYNCING, INVALID
- Caches `payloadId` for later `getPayload` calls
- If no payload attributes, sets `retries: 0` (non-critical, next FCU will follow soon)

**Called from:**
1. `importBlock.ts:404` — After importing block (main trigger)
2. `prepareNextSlot.ts:165` — 4s before next slot for early payload building
3. `produceBlockBody.ts:523` — During block production

### `isExecutionEnabled` / `isMergeTransitionComplete`

**Location:** `packages/state-transition/src/util/execution.ts`

- `isMergeTransitionComplete(state)`: Returns `true` if state's `latestExecutionPayloadHeader` is non-empty, or if state is post-Capella (all post-Capella states are post-merge by definition)
- `isExecutionEnabled(state, block)`: Returns `true` if merge is complete OR if the block's execution payload is non-default (transition block detection)

### `validate_merge_block`

**Location:** `packages/beacon-node/src/chain/blocks/verifyBlocksExecutionPayloads.ts`

The merge transition validation is handled implicitly — Lodestar delegates to the EL via `notifyNewPayload()`. The EL validates that the execution payload references a valid terminal block. Lodestar checks `isExecutionEnabled` to decide whether to verify execution payloads at all.

Key flow:
1. `isExecutionEnabled(preState, block)` — if false, return `ExecutionStatus.PreMerge`
2. Send `notifyNewPayload()` to EL
3. EL returns VALID/INVALID/SYNCING
4. On INVALID, throw `BlockError` with execution status

### `should_override_forkchoice_update`

**Location:** `packages/fork-choice/src/forkChoice/forkChoice.ts:239`

Called from `importBlock.ts:347` when:
- Block is in the current slot
- State is post-execution (post-Bellatrix)
- We know the next slot's proposer and have their fee recipient

Returns `{shouldOverrideFcu: true, parentBlock}` or `{shouldOverrideFcu: false, reason}`.

Conditions checked (matching spec):
1. Proposer boost + reorg flags enabled
2. Parent block available
3. Preliminary proposer head check (`getPreliminaryProposerHead`) — checks shuffling stable, FFG competitive, finalization OK, head late, head weak, parent strong
4. Current time OK (single slot re-org, proposing on time)

If FCU is suppressed, the node builds a payload on the parent block instead (proposer boost re-org).

### `getSafeExecutionBlockHash`

**Location:** `packages/fork-choice/src/forkChoice/safeBlocks.ts:25`
- Returns justified block's execution payload block hash (or zero hash)
- Simple and correct per spec

### FCU Gating

**Location:** `importBlock.ts:385-412`

Before calling `notifyForkchoiceUpdate`:
1. Check `!disableImportExecutionFcU` config
2. Check head changed OR finalized epoch changed
3. Check `!shouldOverrideFcu`
4. Check `headBlockHash !== ZERO_HASH_HEX` (pre-TTD guard)

## Observations

1. **Merge transition is historical** — All networks have long since completed the merge. The `isMergeTransitionComplete` function has a fast path for post-Capella states (always returns true), which is a good optimization.

2. **Terminal PoW validation delegated to EL** — Unlike the spec which describes `get_pow_block` and `is_valid_terminal_pow_block` on the CL side, Lodestar delegates this validation to the EL's `newPayload` call. This is a valid approach since the EL has direct access to PoW chain data.

3. **Proposer boost re-org is well-implemented** — The `shouldOverrideForkChoiceUpdate` logic follows the spec closely. Good use of the `NotReorgedReason` enum for observability/debugging.

4. **Engine API versioning** — Clean fork-based version selection (v1/v2/v3) with proper handling of all response statuses.

5. **No issues found** — Implementation is clean and spec-compliant. The merge transition code is essentially frozen infrastructure at this point.

## Cross-references
- Engine API: [EIP-3675](https://eips.ethereum.org/EIPS/eip-3675) (PoS transition)
- Safe block: `consensus-specs/fork_choice/safe-block.md`
- Phase0 fork choice: `notes/specs/phase0-fork-choice.md`
