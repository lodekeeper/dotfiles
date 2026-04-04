# Gloas executionPayloadBid SSE Event

## Spec Reference
beacon-APIs v5.0.0-alpha.1 `apis/eventstream/index.yaml`

Event type: `execution_payload_bid`
Description: The node has received a `SignedExecutionPayloadBid` that passes gossip validation on the `execution_payload_bid` topic.
Data format: versioned `{version: "gloas", data: SignedExecutionPayloadBid}`

## Implementation Plan

### File 1: `packages/api/src/beacon/routes/events.ts`

1. Add to `EventType` enum:
```typescript
  /** The node has received a valid SignedExecutionPayloadBid (from P2P or API) that passes gossip validation */
  executionPayloadBid = "execution_payload_bid",
```

2. Add to `eventTypes` constant:
```typescript
  [EventType.executionPayloadBid]: EventType.executionPayloadBid,
```

3. Add to `EventData` type:
```typescript
  [EventType.executionPayloadBid]: {version: ForkName; data: gloas.SignedExecutionPayloadBid};
```

4. Add to `getTypeByEvent()` return:
```typescript
  [EventType.executionPayloadBid]: WithVersion((fork) => ssz[fork as ForkName & "gloas"]?.SignedExecutionPayloadBid ?? ssz.gloas.SignedExecutionPayloadBid),
```
Actually, since this is Gloas-only, check how `executionPayload` type is defined — use the same pattern.

### File 2: `packages/beacon-node/src/network/processor/gossipHandlers.ts`

In the `execution_payload_bid` gossip handler (around line 1147), after successful pool insertion, emit the SSE event:

```typescript
chain.emitter.emit(routes.events.EventType.executionPayloadBid, {
  version: config.getForkName(executionPayloadBid.message.slot) as ForkName,
  data: executionPayloadBid,
});
```

### File 3: `packages/beacon-node/src/api/impl/beacon/blocks/index.ts` (if bid is also submitted via API)

Check if there's an API endpoint `publishExecutionPayloadBid` or similar that also receives bids. If so, add the same emitter call there.

## Patterns to Follow
- `executionPayloadGossip` event — closest pattern (emits in gossip handler)
- `executionPayload` event — for versioned data pattern
- The `WithVersion` codec pattern used for `payloadAttributes` and `lightClientOptimisticUpdate`
