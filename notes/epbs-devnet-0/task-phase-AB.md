# Task: EPBS Devnet-0 — Phase A & B

Read `~/.openclaw/workspace/CODING_CONTEXT.md` for project conventions.

## Context
You are working on the `nflaig/epbs-devnet-0` branch in `~/lodestar-epbs-devnet-0`.
This branch already has: state transition, fork choice, SSZ types, gossip topics, gossip validation, op pools, basic block production for ePBS (Gloas fork).

The main missing piece is the **execution payload envelope import pipeline** — when an envelope arrives via gossip or API, we need to run state transition, notify EL, update fork choice, store it, and emit events.

## What to implement

### Phase A: Fix BlockInput for Gloas

**File:** `packages/beacon-node/src/chain/seenCache/seenGossipBlockInput.ts`

At line ~182, there's a `throw Error("Not implemented")` for Gloas blocks. Replace it:

```typescript
// Post-Gloas: beacon blocks are imported immediately without waiting for the execution payload envelope
// The envelope arrives and is processed separately via importExecutionPayloadEnvelope
if (isForkPostGloas(forkName)) {
  blockInput = BlockInputPreData.createFromBlock({
    block,
    blockRootHex,
    daOutOfRange,
    forkName,
    source,
    seenTimestampSec,
    peerIdStr,
  });
}
```

The rationale: post-Gloas, the beacon block doesn't contain the execution payload (it only has a bid). The block can be imported into fork choice immediately with PENDING payload status. The envelope arrives separately.

### Phase B: Execution Payload Envelope Import Pipeline

Create a new method on BeaconChain that processes a signed execution payload envelope. This is the critical missing piece.

**New file:** `packages/beacon-node/src/chain/blocks/importExecutionPayloadEnvelope.ts`

The method signature should be:
```typescript
export async function importExecutionPayloadEnvelope(
  this: BeaconChain,
  signedEnvelope: gloas.SignedExecutionPayloadEnvelope
): Promise<void>
```

**Steps to implement:**

1. **Extract data from envelope:**
   ```typescript
   const envelope = signedEnvelope.message;
   const slot = envelope.slot;
   const blockRootHex = toRootHex(envelope.beaconBlockRoot);
   const executionPayload = envelope.payload;
   ```

2. **Check block is known in fork choice:**
   ```typescript
   const block = this.forkChoice.getBlockHex(blockRootHex);
   if (!block) {
     throw new EnvelopeError({code: EnvelopeErrorCode.BLOCK_UNKNOWN, blockRoot: blockRootHex});
   }
   ```

3. **Check if payload already processed (idempotent):**
   ```typescript
   if (block.payloadStatus === PayloadStatus.FULL) {
     this.logger.debug("Execution payload envelope already processed", {slot, blockRoot: blockRootHex});
     return;
   }
   ```

4. **Load the post-block state (before envelope processing):**
   ```typescript
   const blockStateRoot = block.stateRoot;
   const state = this.regen.getBlockSlotState(blockStateRoot);
   // or use the state cache
   ```
   
   The state must be the state after the beacon block was applied but before envelope processing.

5. **Run state transition:**
   ```typescript
   import {processExecutionPayloadEnvelope} from "@lodestar/state-transition/block";
   const postState = state.clone();
   processExecutionPayloadEnvelope(postState, signedEnvelope, true); // verify signature
   ```

6. **Notify EL with newPayload:**
   ```typescript
   const executionEngine = this.executionEngine;
   const payloadResult = await executionEngine.notifyNewPayload(
     this.config.getForkName(slot),
     executionPayload,
     // ... versioned hashes, parent beacon block root, execution requests
   );
   ```

7. **Update fork choice:**
   ```typescript
   this.forkChoice.onExecutionPayload(
     blockRootHex,
     toRootHex(executionPayload.blockHash),
     executionPayload.blockNumber,
     toRootHex(envelope.stateRoot)
   );
   ```

8. **Cache the payload state:**
   ```typescript
   this.regen.processPayloadState(postState);
   ```

9. **Store envelope in DB:**
   ```typescript
   await this.db.executionPayloadEnvelope.add(signedEnvelope);
   ```

10. **Emit SSE event:**
    ```typescript
    this.emitter.emit(routes.events.EventType.executionPayloadAvailable, {
      slot,
      blockRoot: blockRootHex,
    });
    ```

### Phase B2: Wire up gossip handler

**File:** `packages/beacon-node/src/network/processor/gossipHandlers.ts`

In the `execution_payload` handler (around line 835), replace the TODO:
```typescript
// After validation, import the envelope
try {
  await chain.importExecutionPayloadEnvelope(executionPayloadEnvelope);
} catch (e) {
  logger.error("Error importing execution payload envelope", {slot}, e as Error);
}
```

### Phase B3: Wire up API handler

**File:** `packages/beacon-node/src/api/impl/beacon/blocks/index.ts`

In `publishExecutionPayloadEnvelope` (around line 692-703), replace the TODO blocks:
```typescript
// Import the envelope (validates signature, runs STF, notifies EL, updates fork choice)
await chain.importExecutionPayloadEnvelope(signedExecutionPayloadEnvelope);
```

## Important notes

1. **Check existing patterns**: Look at how `importBlock` works in `importBlock.ts` for the general pattern. The envelope import is simpler — no attestation processing needed.

2. **The `processExecutionPayloadEnvelope` function already exists** in `@lodestar/state-transition/block`. Check `packages/state-transition/src/block/processExecutionPayloadEnvelope.ts` for its signature.

3. **The `onExecutionPayload` method already exists** on the fork choice. See `packages/fork-choice/src/forkChoice/forkChoice.ts` line ~973.

4. **The `processPayloadState` method already exists** on the regen module. See `packages/beacon-node/src/chain/regen/queued.ts` line ~190.

5. **Error handling**: Create proper error types. See existing `packages/beacon-node/src/chain/errors/executionPayloadEnvelope.ts`.

6. **EL notification**: Look at how `notifyNewPayload` is called in the existing block import for the exact parameters needed. Check `packages/beacon-node/src/execution/engine/interface.ts`.

7. **Events**: The `executionPayloadAvailable` event type needs to be added to `packages/api/src/beacon/routes/events.ts` first. Add it to the EventType enum, the eventTypes object, and the EventData type.

8. **Add the method to BeaconChain**: In `packages/beacon-node/src/chain/chain.ts`, bind the new function:
   ```typescript
   importExecutionPayloadEnvelope = importExecutionPayloadEnvelope;
   ```
   And add it to the IBeaconChain interface in `packages/beacon-node/src/chain/interface.ts`.

## Build & Verify
After changes:
```bash
pnpm build
pnpm lint
pnpm check-types
```

## Acceptance criteria
- [ ] Gloas blocks import without throwing "Not implemented"
- [ ] Execution payload envelopes from gossip are fully imported (STF + fork choice + DB)
- [ ] publishExecutionPayloadEnvelope API imports the envelope
- [ ] executionPayloadAvailable SSE event emitted after successful import
- [ ] Build passes
- [ ] Lint passes
- [ ] Type check passes
