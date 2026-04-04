# Feature: Gloas Same-Slot Attestation Index Enforcement

## Problem
The consensus spec (v1.7.0-alpha.4) requires two validations in `validate_on_attestation` that unstable is missing:
1. Same-slot attestations MUST use `data.index = 0`
2. Attestations with `data.index = 1` (claiming FULL payload) require the payload to be known

## Spec Reference
`specs/gloas/fork-choice.md` — Modified `validate_on_attestation`:
```python
# [New in Gloas:EIP7732]
assert attestation.data.index in [0, 1]          # ← already on unstable ✅
if block_slot == attestation.data.slot:
    assert attestation.data.index == 0            # ← MISSING ❌
# If attesting for a full node, the payload must be known
if attestation.data.index == 1:
    assert attestation.data.beacon_block_root in store.payload_states  # ← MISSING ❌
```

## Current State on Unstable

### Already implemented:
- `validateAttestationData()` (line ~1669): validates `index in [0, 1]` for Gloas blocks
- `onAttestation()` (line ~907-924): maps `index` to `PayloadStatus`:
  - `slot > block.slot`: `0→EMPTY`, `1→FULL`
  - `slot == block.slot`: `→PENDING` (correctly maps to PENDING)

### Missing:
1. **No rejection of `index != 0` when `slot == block.slot`** — silent acceptance
2. **No payload-known check** — `index == 1` accepted even if FULL variant doesn't exist, causing raw `Error` later in `addLatestMessage()` when the proto-array node lookup fails

## Approach

### Placement: `validateAttestationData()` (NOT `onAttestation()`)
Per advisor review: all validity checks belong in `validateAttestationData()` alongside the existing `index in [0,1]` check. `onAttestation()` does vote→PayloadStatus mapping, not validity checking.

### Change 1: Same-slot index enforcement
In `validateAttestationData()`, after the existing `index in [0,1]` check and block lookup:
```typescript
// [New in Gloas:EIP7732] Same-slot attestation must always use index 0
if (block.slot === slot && attestationData.index !== 0) {
  throw new ForkChoiceError({
    code: ForkChoiceErrorCode.INVALID_ATTESTATION,
    err: {
      code: InvalidAttestationCode.INVALID_DATA_INDEX,
      index: attestationData.index,
    },
  });
}
```

### Change 2: Payload-known enforcement for index=1
```typescript
// [New in Gloas:EIP7732] Attesting FULL requires payload to be known
if (attestationData.index === 1 &&
    this.protoArray.getNodeIndexByRootAndStatus(beaconBlockRootHex, PayloadStatus.FULL) === undefined) {
  throw new ForkChoiceError({
    code: ForkChoiceErrorCode.INVALID_ATTESTATION,
    err: {
      code: InvalidAttestationCode.PAYLOAD_NOT_KNOWN,
      root: beaconBlockRootHex,
    },
  });
}
```

### Change 3: New error code
Add `PAYLOAD_NOT_KNOWN` to `InvalidAttestationCode` enum in `errors.ts`.

## Files to Modify
1. `packages/fork-choice/src/forkChoice/forkChoice.ts` — `validateAttestationData()` only
2. `packages/fork-choice/src/forkChoice/errors.ts` — add `PAYLOAD_NOT_KNOWN`
3. `packages/fork-choice/test/unit/forkChoice/forkChoice.test.ts` — test coverage

## Edge Cases (from advisor review)
- **Queued attestation with index=1, no FULL variant:** Must reject immediately, not queue and fail later
- **Same-slot with FULL known:** Even if FULL variant exists, `slot == block.slot && index == 1` must reject
- **Retry after payload arrives:** Failed `PAYLOAD_NOT_KNOWN` should succeed later once FULL exists (cache behavior: only successful validations cached ✅)
- **Pre-Gloas blocks:** Not affected — bypasses Gloas branch entirely
- **`onAttestation()` mapping unchanged:** same-slot valid votes stay mapped to PENDING (correct)

## Test Plan
- Unit test: same-slot Gloas attestation with `index=0` → succeeds, maps to PENDING
- Unit test: same-slot Gloas attestation with `index=1` → throws INVALID_DATA_INDEX
- Unit test: same-slot with `index=1` and FULL known → still throws INVALID_DATA_INDEX
- Unit test: later-slot attestation with `index=1` without FULL variant → throws PAYLOAD_NOT_KNOWN
- Unit test: later-slot attestation with `index=1` with FULL variant → succeeds, maps to FULL
- Verify existing tests pass unchanged

## Acceptance Criteria
- [ ] Same-slot Gloas attestations with `index != 0` are rejected in `validateAttestationData()`
- [ ] Attestations claiming FULL (`index=1`) for blocks without known payload are rejected
- [ ] `onAttestation()` mapping logic unchanged
- [ ] All existing fork-choice tests pass
- [ ] New error code `PAYLOAD_NOT_KNOWN` added
- [ ] Spec compliance with v1.7.0-alpha.4 `validate_on_attestation`
