# Consensus-specs v1.7.0-alpha.3 Upgrade — Impact Analysis

## Summary

15 Gloas spec PRs + 3 cross-fork PRs to evaluate.
**10 require code changes**, 7 are spec-internal/docs-only.

---

## 🔴 CRITICAL — Code Changes Required

### 1. PayloadStatus reorder (#4948)
**Spec change:**
- OLD: `PENDING=0, EMPTY=1, FULL=2`
- NEW: `EMPTY=0, FULL=1, PENDING=2`

**Files:**
- `packages/fork-choice/src/protoArray/interface.ts` — enum values
- `packages/fork-choice/src/protoArray/protoArray.ts` — variant array indexing comments, `GloasVariantIndices` tuple interpretation
- `packages/fork-choice/test/unit/protoArray/gloas.test.ts` — test expectations

**Risk:** HIGH — this changes the meaning of array indices in `VariantIndices`. The `GloasVariantIndices` type is `[number, number] | [number, number, number]` where positions correspond to enum values. After reorder:
- Position 0 = EMPTY (was PENDING)
- Position 1 = FULL (was EMPTY)
- Position 2 = PENDING (was FULL)

Need to audit ALL code that accesses `variants[PayloadStatus.X]` — the enum change should auto-propagate but array creation order in `onBlock` must match.

### 2. New `payload_data_availability_vote` + `is_payload_data_available` (#4884)
**Spec change:**
- New constant: `DATA_AVAILABILITY_TIMELY_THRESHOLD = PTC_SIZE // 2` (= 256)
- Store gets: `payload_data_availability_vote: Dict[Root, Vector[boolean, PTC_SIZE]]`
- `ptc_vote` renamed to `payload_timeliness_vote`
- New function `is_payload_data_available(store, root)` — mirrors `is_payload_timely` but for blob data
- `should_extend_payload` condition 1 becomes: `is_payload_timely(root) AND is_payload_data_available(root)`
- `on_payload_attestation_message` now updates BOTH vote maps:
  - `payload_timeliness_vote[ptcIndex] = data.payload_present`
  - `payload_data_availability_vote[ptcIndex] = data.blob_data_available`
- `on_block` initializes both vote maps to `[False] * PTC_SIZE` for new blocks
- `get_forkchoice_store` initializes both to all-`True` for anchor

**Files:**
- `packages/fork-choice/src/protoArray/protoArray.ts`:
  - New `ptcDataAvailabilityVotes` map (or rename existing + add new)
  - Rename `ptcVotes` → `payloadTimelinessVotes`
  - `notifyPtcMessages()` signature: add `blobDataAvailable` param
  - New `isPayloadDataAvailable()` method
  - Update `shouldExtendPayload()` — AND both checks
  - Update `onBlock()` — initialize both vote maps
  - Update `onPrune()` — clean up both maps
- `packages/fork-choice/src/forkChoice/forkChoice.ts`:
  - `notifyPtcMessages()` interface + implementation updated
- `packages/fork-choice/src/forkChoice/interface.ts`:
  - `notifyPtcMessages()` signature updated
- All callers of `notifyPtcMessages` — need to pass `blobDataAvailable`

**Note:** `PayloadAttestationData` already has `blobDataAvailable` in our SSZ types (added in alpha.2), so the type change is already done.

### 3. `execution_payload_states` → `payload_states` rename (#4930)
**Lodestar impact:** Internal name `ptcVotes` doesn't match either spec name. Mostly spec comment/reference updates. Rename for clarity:
- `ptcVotes` → `payloadTimelinessVotes` (aligns with `payload_timeliness_vote`)

### 4. New `is_pending_validator` + updated `process_deposit_request` (#4897, #4916)
**Spec change:**
- New helper: `is_pending_validator(state, pubkey)` — iterates `state.pending_deposits`, checks for valid deposit signature match
- `process_deposit_request` condition updated:
  ```
  OLD: is_builder || (is_builder_prefix && !is_validator)
  NEW: is_builder || (is_builder_prefix && !is_validator && !is_pending_validator(state, pubkey))
  ```
- Note: spec says implementations SHOULD cache signature verification results

**Files:**
- `packages/state-transition/src/util/gloas.ts` — add `isPendingValidator` helper
- `packages/state-transition/src/block/processDepositRequest.ts` — update condition

### 5. Attestation validation: payload must be known for index=1 (#4918)
**Spec change:**
```python
# [New in Gloas:EIP7732]
if attestation.data.index == 1:
    assert attestation.data.beacon_block_root in store.payload_states
```

**Files:**
- `packages/fork-choice/src/forkChoice/forkChoice.ts` — `validateAttestationData()`:
  After the existing Gloas index check, when `index == 1`, verify that the FULL variant exists in proto-array (FULL variant = payload locally available = `payload_states` entry exists)

### 6. Ignore beacon block if parent payload unknown (#4923)
**Spec change:**
New gossip validation for beacon blocks:
```
[IGNORE] The block's parent execution payload (defined by bid.parent_block_hash)
has been seen (via gossip or non-gossip sources)
(a client MAY queue blocks for processing once the parent payload is retrieved).
```

**Files:**
- `packages/beacon-node/src/chain/validation/block.ts` — add IGNORE check
- Need to check if we can query fork-choice for parent payload availability

### 7. `parent_block_root` added to bid filtering key (#5001)
**Spec change:**
- OLD: highest bid per `(slot, parent_block_hash)`
- NEW: highest bid per `(slot, parent_block_hash, parent_block_root)`

**Files:**
- `packages/beacon-node/src/chain/validation/executionPayloadBid.ts` — already passes `parentBlockRootHex` to `getBestBid()`, verify the pool indexes correctly
- Check `executionPayloadBidPool` implementation

### 8. Anchor state initialization changes (#4884)
**Spec change:**
- `payload_timeliness_vote` for anchor: all-`True` (not all-`False`!)
- `payload_data_availability_vote` for anchor: all-`True`

**Files:**
- Proto-array anchor block initialization

### 9. `get_forkchoice_store` time computation (#4926 in Gloas context)
**Spec change:**
```python
# OLD
time=uint64(anchor_state.genesis_time + SECONDS_PER_SLOT * anchor_state.slot)
# NEW
time=uint64(anchor_state.genesis_time + SLOT_DURATION_MS * anchor_state.slot // 1000)
```

**Lodestar impact:** Check how fork-choice store time is computed. Likely already using `SECONDS_PER_SLOT` from config (which is the integer seconds value). This should be fine since `SLOT_DURATION_MS / 1000 = SECONDS_PER_SLOT`.

---

## 🟡 MODERATE — Verify/Minor Changes

### 10. `SECONDS_PER_SLOT` deprecation (#4926)
**Status:** Nico says "should already be done." Lodestar keeps `SECONDS_PER_SLOT` in config for backward compat, derives `SLOT_DURATION_MS` from it. ✅ No change needed.

### 11. `MIN_EPOCHS_FOR_BLOCK_REQUESTS` → `compute_min_epochs_for_block_requests()` (#4814)
**Status:** Same computed value, still a config constant in Lodestar. ✅ No change needed.

### 12. ByRoot serve range alignment (#4950)
**Spec change:** `BlocksByRoot` explicit epoch range requirement. Lodestar already stores blocks for the required range.
**Status:** Check handlers. Likely already compliant. Gloas `execution_payload_envelopes_by_root` serve range also updated.

### 13. Pre-fork subscription for `proposer_preferences` topic (#4947)
**Spec note:** "Nodes SHOULD subscribe at least one epoch before fork activation."
**Status:** Recommendation. Low priority for now.

### 14. Signature verification wording for payload envelope (#5002)
**Status:** Already verifying correctly. Wording clarification only. ✅ No change needed.

---

## 🟢 NO CODE CHANGE — Spec-Internal

- #4917: BNF fix (markdown)
- #4972: Python dep update
- #4910: Standardize fork versions (spec build)
- #4920: "Constructing the XYZ" section restructure (validator.md)
- #4922: Missing fork comment in Store (spec comment)
- #4924: Duration annotations removed (spec doc)
- #4927: Capitalize "Note" (spec doc)
- Testing/CI PRs: spec-internal

---

## 📦 VERSION UPDATES
- `spec-tests-version.json`: `v1.7.0-alpha.2` → `v1.7.0-alpha.3`
- All spec URL references in code comments
- ethspecify version bump

## Implementation Order (recommended)
1. PayloadStatus reorder (#4948) — foundational, everything depends on this
2. payload_data_availability_vote + renamed maps (#4884, #4930) — next biggest change
3. is_pending_validator + process_deposit_request (#4897, #4916)
4. Attestation validation for index=1 (#4918)
5. Ignore block if parent payload unknown (#4923)
6. Bid filtering key update (#5001)
7. Anchor state initialization (#4884)
8. Version bumps + spec reference updates
9. Run spec tests, lint, check-types, build
