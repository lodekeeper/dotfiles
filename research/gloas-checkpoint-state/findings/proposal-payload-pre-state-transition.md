# Proposal: Deferred Payload Processing via Beacon Block

**Date:** 2026-04-07
**Authors:** nflaig, lodekeeper
**Related:** [consensus-specs#5074](https://github.com/ethereum/consensus-specs/issues/5074), [consensus-specs#5073](https://github.com/ethereum/consensus-specs/pull/5073), [beacon-APIs#572](https://github.com/ethereum/beacon-APIs/issues/572)

---

## Rationale

Under Gloas (ePBS), `process_execution_payload` mutates CL state: execution requests go into pending queues, the availability bit is set, and `latest_block_hash` is updated. Since FFG only finalizes `{epoch, root}` (the beacon block root, not the payload), any payload-dependent CL state mutation makes the finalized state ambiguous — different nodes may compute different states for the same checkpoint depending on whether they've seen the payload.

**Core design principle:** A payload cannot change `block_states` of its own slot.

The parent's EE-verified execution requests are carried forward in the **next beacon block's body** and processed as part of `process_block`. Since `process_block` runs after `process_slots` (which includes `process_epoch`), execution requests are naturally processed in the correct order — after epoch processing, not before. This eliminates `payload_states` entirely, preserves `state_transition` as a black box, and makes checkpoint states both deterministic and correct.

Payload effects fall into two categories:

| Category | Direction | Examples | Where processed |
|----------|-----------|---------|----------------|
| CL-computable | CL -> EL | Withdrawals | `process_block` (bid) — unchanged |
| EL-derived | EL -> CL | Deposits, exits, consolidations | Next block's `process_parent_execution_payload` |
| Payload-conditional | CL | Builder payment queueing | Next block's `process_parent_execution_payload` |
| Bookkeeping | -- | `latest_block_hash`, availability bit | Next block's `process_parent_execution_payload` |

CL-computable effects (withdrawals) are already deterministic from the beacon state and stay in `process_block` unchanged. EL-derived effects (execution requests) and payload-conditional effects (builder payment queueing, bookkeeping) require knowledge of the parent's payload status and are deferred to the next block's `process_parent_execution_payload`. Execution requests are buffered at fork-choice level after EE verification and included in the next beacon block body.

---

## Spec Changes

### 1. `BeaconBlockBody` -- new field for parent's execution requests

```python
class BeaconBlockBody(Container):
    # ... existing fields ...
    signed_execution_payload_bid: SignedExecutionPayloadBid
    payload_attestations: List[PayloadAttestation, MAX_PAYLOAD_ATTESTATIONS]
    # NEW: EE-verified execution requests from parent's payload (empty if parent was EMPTY)
    parent_execution_requests: ExecutionRequests
```

The proposer includes the parent's EE-verified execution requests. If the parent was EMPTY (no payload delivered), this field is empty.

### 2. `process_block` -- new `process_parent_execution_payload` step

`process_parent_execution_payload` must run **first** in `process_block`, before `process_block_header`. Two reasons:

1. **Parent slot**: `state.latest_block_header.slot` gives the exact parent slot. `process_block_header` overwrites this with the current block's header.
2. **Parent bid**: `state.latest_execution_payload_bid` holds the parent's committed bid. `process_execution_payload_bid` overwrites this with the current block's bid.

After `process_parent_execution_payload` updates `state.latest_block_hash`, the existing `is_parent_block_full(state)` check in `process_withdrawals` works correctly — it compares the (still-present) parent's `latest_execution_payload_bid.block_hash` against the (now-updated) `latest_block_hash`.

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    # [New in Gloas] Process parent's deferred execution requests FIRST
    # (uses state.latest_block_header.slot and state.latest_execution_payload_bid
    #  which are overwritten by process_block_header and process_execution_payload_bid)
    process_parent_execution_payload(state, block)
    process_block_header(state, block)
    # [Modified in Gloas:EIP7732]
    process_withdrawals(state)  # is_parent_block_full(state) works correctly here
    # [Modified in Gloas:EIP7732]
    process_execution_payload_bid(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    # [Modified in Gloas:EIP7732]
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)


def process_parent_execution_payload(state: BeaconState, block: BeaconBlock) -> None:
    """Process deferred effects from the parent's execution payload."""
    bid = block.body.signed_execution_payload_bid.message
    parent_bid = state.latest_execution_payload_bid  # parent's bid, before overwrite

    # Determine parent payload status from block data:
    # compare current bid's parent_block_hash with parent's committed block_hash
    is_parent_full = (bid.parent_block_hash == parent_bid.block_hash)

    if is_parent_full:
        parent_slot = state.latest_block_header.slot

        # Process deferred execution requests from parent's payload
        requests = block.body.parent_execution_requests
        for request in requests.deposits:
            process_deposit_request(state, request)
        for request in requests.withdrawals:
            process_withdrawal_request(state, request)
        for request in requests.consolidations:
            process_consolidation_request(state, request)

        # Queue the builder payment (moved from process_execution_payload)
        # Account for epoch rotation: same pattern as process_attestation
        parent_epoch = compute_epoch_at_slot(parent_slot)
        if parent_epoch == get_current_epoch(state):
            payment_index = SLOTS_PER_EPOCH + parent_slot % SLOTS_PER_EPOCH
        else:
            payment_index = parent_slot % SLOTS_PER_EPOCH
        payment = state.builder_pending_payments[payment_index]
        amount = payment.withdrawal.amount
        if amount > 0:
            state.builder_pending_withdrawals.append(payment.withdrawal)
        state.builder_pending_payments[payment_index] = BuilderPendingPayment()

        # Set availability bit using exact parent slot from header
        state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1

        # Update latest_block_hash to reflect parent's delivered payload
        state.latest_block_hash = bid.parent_block_hash
    else:
        # Parent was EMPTY — no execution requests expected
        assert block.body.parent_execution_requests == ExecutionRequests()
```

**Note on infallibility:** `process_deposit_request`, `process_withdrawal_request`, and `process_consolidation_request` are all infallible — they use early returns, not assertions. They cannot cause `state_transition` to fail. This is critical: if they could fail, a malicious builder could craft execution requests that cause assertion failures in `process_block`, potentially splitting the network. Since they are infallible, including them in `process_block` is always safe.

**Note on `process_execution_payload_bid` validation:** The existing assertion `bid.parent_block_hash == state.latest_block_hash` (line 1167 in the current spec) becomes tautological when the parent was FULL (we just set `latest_block_hash = bid.parent_block_hash`). When the parent was EMPTY, it remains a real validation — the builder must reference the last FULL payload's hash. The FULL case is validated at fork-choice level (`on_block` verifies `parent_execution_requests` match EE-verified data).

### 3. `process_execution_payload` -- pure verification, zero CL state mutations

```python
def process_execution_payload(
    state: BeaconState,
    signed_envelope: SignedExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
    verify: bool = True,
) -> ExecutionRequests:
    envelope = signed_envelope.message
    payload = envelope.payload

    if verify:
        assert verify_execution_payload_envelope_signature(state, signed_envelope)

    # Fill in deferred state root (standard pattern, not a payload effect)
    if state.latest_block_header.state_root == Root():
        state.latest_block_header.state_root = hash_tree_root(state)

    # Verify consistency with beacon block and committed bid
    assert envelope.beacon_block_root == hash_tree_root(state.latest_block_header)
    assert envelope.slot == state.slot
    committed_bid = state.latest_execution_payload_bid
    assert envelope.builder_index == committed_bid.builder_index
    assert committed_bid.prev_randao == payload.prev_randao

    # Verify withdrawals, gas_limit, block_hash, parent_hash, timestamp
    assert hash_tree_root(payload.withdrawals) == hash_tree_root(state.payload_expected_withdrawals)
    assert committed_bid.gas_limit == payload.gas_limit
    assert committed_bid.block_hash == payload.block_hash
    assert payload.parent_hash == state.latest_block_hash
    assert payload.timestamp == compute_time_at_slot(state, state.slot)

    # EE verification
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(c)
        for c in committed_bid.blob_kzg_commitments
    ]
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=envelope.execution_requests,
        )
    )

    # REMOVED: process_deposit_request, process_withdrawal_request, process_consolidation_request
    # REMOVED: builder payment queueing (builder_pending_payments → builder_pending_withdrawals)
    # REMOVED: state.execution_payload_availability mutation
    # REMOVED: state.latest_block_hash mutation
    # REMOVED: state_root verification (field removed from ExecutionPayloadEnvelope, see below)

    return envelope.execution_requests
```

### 4. `ExecutionPayloadEnvelope` -- remove `state_root` field

Since `process_execution_payload` no longer mutates CL state, `envelope.state_root` would equal the block's post-state root — already derivable from `envelope.beacon_block_root` (the block header contains `state_root`). No consumer needs a separate copy:
- CL validation uses `beacon_block_root`
- Light clients use `BeaconBlockHeader.state_root`
- EL has its own execution state root
- Relays/snap-sync use block header state roots

```python
class ExecutionPayloadEnvelope(Container):
    payload: ExecutionPayload
    execution_requests: ExecutionRequests
    builder_index: BuilderIndex
    beacon_block_root: Root
    slot: Slot
    # REMOVED: state_root: Root
```

### 5. Fork-choice `Store` -- remove `payload_states`, add verification buffer

```python
@dataclass
class Store(object):
    # ... existing fields ...
    blocks: Dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    # REMOVED: payload_states: Dict[Root, BeaconState]
    # NEW: EE-verified execution requests, keyed by beacon block root (for on_block verification)
    verified_execution_requests: Dict[Root, ExecutionRequests] = field(default_factory=dict)
```

`verified_execution_requests` is used by `on_block` to verify that the next block's `parent_execution_requests` field matches the EE-verified data. Bounded by fork-choice tree size, pruned on finalization.

### 6. `on_execution_payload` -- verify and buffer, no state persisted

```python
def on_execution_payload(store: Store, signed_envelope: SignedExecutionPayloadEnvelope) -> None:
    envelope = signed_envelope.message
    assert envelope.beacon_block_root in store.block_states
    assert is_data_available(envelope.beacon_block_root)

    # Pure verification on a temporary copy (discarded after)
    state = copy(store.block_states[envelope.beacon_block_root])
    verified_requests = process_execution_payload(state, signed_envelope, EXECUTION_ENGINE)

    # Store at fork-choice level for next block verification
    store.verified_execution_requests[envelope.beacon_block_root] = verified_requests
```

### 7. `on_block` -- verify parent execution requests, then unmodified `state_transition`

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    block = signed_block.message
    assert block.parent_root in store.block_states

    # Verify parent execution requests match EE-verified data
    parent_root = block.parent_root
    if is_parent_node_full(store, block):
        assert parent_root in store.verified_execution_requests
        assert block.body.parent_execution_requests == store.verified_execution_requests[parent_root]
    else:
        assert block.body.parent_execution_requests == ExecutionRequests()

    # Standard state transition — UNCHANGED from current pattern
    state = copy(store.block_states[block.parent_root])
    state_transition(state, signed_block)

    block_root = hash_tree_root(block)
    store.block_states[block_root] = state

    # ... (rest of on_block unchanged) ...
```

`state_transition` remains a black box: `process_slots` (including `process_epoch`) runs first, then `process_block`. Within `process_block`, `process_parent_execution_payload` runs first (before `process_block_header`), ensuring access to the parent's header slot and committed bid. No splitting of `state_transition`, no pre-state mutations.

### Summary of changes

| Component | Current Gloas spec | This proposal |
|-----------|-------------------|---------------|
| `BeaconBlockBody` | No parent requests field | `parent_execution_requests: ExecutionRequests` |
| `process_execution_payload` | Mutates CL state | Pure verification, zero mutations |
| `ExecutionPayloadEnvelope` | Contains `state_root` field | `state_root` removed (redundant with `beacon_block_root`) |
| `process_block` | No parent request processing | `process_parent_execution_payload` runs **first** (before `process_block_header`) |
| `on_execution_payload` | Persists `payload_states[root]` | Buffers verified requests (for verification only) |
| `on_block` | Branches on parent FULL/EMPTY | Verifies `parent_execution_requests`, calls `state_transition` |
| `Store` | `block_states` + `payload_states` | `block_states` + `verified_execution_requests` |
| `state_transition` | Unchanged | Unchanged (process_slots -> process_block) |
| States per slot | 2 (`block_states` + `payload_states`) | 1 (`block_states` only) |

---

## Why This Ordering Is Correct

Under `state_transition`, `process_slots` (including `process_epoch`) runs before `process_block`. Since execution requests are processed inside `process_block`, they are applied **after** epoch processing. This ensures:

1. **`store_target_checkpoint_state`** advances `block_states[target]` via `process_slots` → `process_epoch` runs without the target's payload effects
2. **`on_block` chain state** runs `state_transition` → `process_slots` → `process_epoch` runs without the parent's payload effects, then `process_block` applies them

Both produce identical `process_epoch` results. The checkpoint state matches the chain state at epoch boundaries.

**Concrete trace (slot 31, epoch boundary at 32, slot 32 skipped, block at 33):**

| Step | `store_target_checkpoint_state(R31)` | `on_block(33)` chain state |
|------|--------------------------------------|----------------------------|
| Start | `block_states[R31]` (slot 31, no slot 31 payload effects) | `block_states[R31]` (same) |
| `process_slots` to boundary | `process_epoch` at 31→32 — **no slot 31 requests** | `process_epoch` at 31→32 — **no slot 31 requests** |
| After boundary | Checkpoint state at slot 32 | State at slot 33 |
| `process_block` | N/A | `process_parent_execution_payload` → `process_block_header` → ... (slot 31's requests applied first) |

`process_epoch` results are **identical**. Slot 31's execution requests are processed in `process_block(33)`, after the epoch boundary.

---

## Tradeoffs

1. **`BeaconBlockBody` container change.** Adds `parent_execution_requests` field. Increases beacon block size by the execution requests from the parent's payload. Typically small (a few deposits/exits). Bounded by `MAX_DEPOSIT_REQUESTS_PER_PAYLOAD` + `MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD` + `MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD`.

2. **Data duplication.** Execution requests exist in both the `ExecutionPayloadEnvelope` (for EE verification) and the next `BeaconBlock` body (for CL processing). This duplication could be eliminated by modifying the Engine API to have `engine_newPayload` *return* the verified execution requests instead of receiving them as input — removing `execution_requests` from `ExecutionPayloadEnvelope` entirely. This is out of scope for this CL-only proposal but worth considering as a follow-up.

3. **Temporary state copy still needed.** `on_execution_payload` copies `block_states[root]` for EE verification, then discards it.

4. **Execution requests at epoch boundaries are delayed by one epoch.** Requests from the last slot's payload miss the current epoch's `process_epoch` — they're processed in `process_block` of the next block, which runs after `process_epoch`. They enter pending queues after the epoch boundary and are processed at the next epoch's `process_epoch`. This is negligible given existing multi-epoch activation/exit queue delays.

---

## Resolved Design Decisions

1. **`latest_block_hash` derivation.** `process_parent_execution_payload` updates `state.latest_block_hash = bid.parent_block_hash` only when the parent was FULL (determined by `bid.parent_block_hash == state.latest_execution_payload_bid.block_hash`). When the parent was EMPTY, `latest_block_hash` is unchanged. The subsequent `process_execution_payload_bid` assertion (`bid.parent_block_hash == state.latest_block_hash`) is tautological in the FULL case but provides real validation in the EMPTY case. FULL case validation happens at fork-choice level in `on_block`.

2. **`execution_payload_availability` bit.** Exact parent slot is derived from `state.latest_block_header.slot`, which holds the parent block's header because `process_parent_execution_payload` runs before `process_block_header`. Works correctly with any number of skipped slots.

3. **Builder payment epoch rotation.** In the current spec, `process_execution_payload` reads the payment from a frozen state copy at the block's slot — no epoch rotation concern. In this proposal, `process_parent_execution_payload` runs after `process_slots`/`process_epoch`, so the `builder_pending_payments` array may have been rotated. The epoch-aware index pattern from `process_attestation` is used: `SLOTS_PER_EPOCH + parent_slot % SLOTS_PER_EPOCH` for same-epoch, `parent_slot % SLOTS_PER_EPOCH` for previous-epoch.

4. **`is_parent_block_full(state)` compatibility.** The existing `is_parent_block_full` function (used by `process_withdrawals`) checks `state.latest_execution_payload_bid.block_hash == state.latest_block_hash`. This works correctly because `process_parent_execution_payload` updates `latest_block_hash` before `process_withdrawals` runs, and `state.latest_execution_payload_bid` still holds the parent's bid (overwritten later by `process_execution_payload_bid`).
