# Proposal: Payload as Pre-State Transition

**Date:** 2026-04-07
**Authors:** nflaig, lodekeeper
**Related:** [consensus-specs#5074](https://github.com/ethereum/consensus-specs/issues/5074), [consensus-specs#5073](https://github.com/ethereum/consensus-specs/pull/5073), [beacon-APIs#572](https://github.com/ethereum/beacon-APIs/issues/572)

---

## Rationale

Under Gloas (ePBS), `process_execution_payload` mutates CL state: execution requests go into pending queues, the availability bit is set, and `latest_block_hash` is updated. Since FFG only finalizes `{epoch, root}` (the beacon block root, not the payload), any payload-dependent CL state mutation makes the finalized state ambiguous — different nodes may compute different states for the same checkpoint depending on whether they've seen the payload.

**Core design principle:** A payload cannot change `block_states` of its own slot.

All payload effects are instead applied as a **pre-state transition** at the start of the next `on_block`. This eliminates `payload_states` entirely and makes `block_states[root]` deterministic regardless of the slot's own payload status.

Payload effects fall into two categories:

| Category | Direction | Examples | Where processed |
|----------|-----------|---------|----------------|
| CL-computable | CL -> EL | Withdrawals, builder payments | `process_block` (bid) — unchanged |
| EL-derived | EL -> CL | Deposits, exits, consolidations | `on_execution_payload` -> next `on_block` |
| Bookkeeping | -- | `latest_block_hash`, availability bit | `on_execution_payload` -> next `on_block` |

CL-computable effects (withdrawals, builder payments) are already deterministic from the beacon state and stay in `process_block`. EL-derived effects (execution requests) require EE verification and cannot be placed in the bid — the CL cannot independently verify them. They are buffered at fork-choice level after EE verification and applied in the next block's pre-state transition.

---

## Spec Changes

### 1. `process_execution_payload` -- zero CL state mutations

The function becomes pure verification. It returns EE-verified execution requests for the caller to store at fork-choice level.

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
    # REMOVED: state.execution_payload_availability mutation
    # REMOVED: state.latest_block_hash mutation
    # REMOVED: builder payment queueing (already in process_execution_payload_bid)

    # State is unchanged — verify state_root
    if verify:
        assert envelope.state_root == hash_tree_root(state)

    return envelope.execution_requests
```

### 2. Fork-choice `Store` -- remove `payload_states`, add payload metadata

```python
@dataclass
class Store(object):
    # ... existing fields ...
    blocks: Dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    # REMOVED: payload_states: Dict[Root, BeaconState]
    # NEW: EE-verified execution requests, keyed by beacon block root
    verified_execution_requests: Dict[Root, ExecutionRequests] = field(default_factory=dict)
    # NEW: payload block hashes (replaces state.latest_block_hash for fork-choice)
    payload_block_hashes: Dict[Root, Hash32] = field(default_factory=dict)
```

Both new maps are bounded by fork-choice tree size and pruned on finalization. Entries in `verified_execution_requests` only exist after the EE has verified the payload — fraudulent requests are never stored.

### 3. `on_execution_payload` -- verify and buffer, no state persisted

```python
def on_execution_payload(store: Store, signed_envelope: SignedExecutionPayloadEnvelope) -> None:
    envelope = signed_envelope.message
    assert envelope.beacon_block_root in store.block_states
    assert is_data_available(envelope.beacon_block_root)

    # Pure verification on a temporary copy (discarded after)
    state = copy(store.block_states[envelope.beacon_block_root])
    verified_requests = process_execution_payload(state, signed_envelope, EXECUTION_ENGINE)

    # Store at fork-choice level
    store.verified_execution_requests[envelope.beacon_block_root] = verified_requests
    store.payload_block_hashes[envelope.beacon_block_root] = envelope.payload.block_hash
```

### 4. `on_block` -- pre-state transition

The critical change. Parent payload effects are applied **before** `state_transition` runs:

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    block = signed_block.message

    # ... (existing parent/finalized checks) ...

    state = copy(store.block_states[block.parent_root])

    # === PRE-STATE TRANSITION: apply parent's payload effects ===
    parent_root = block.parent_root

    # (a) If parent payload was FULL, apply EE-verified execution requests
    if parent_root in store.verified_execution_requests:
        requests = store.verified_execution_requests[parent_root]
        for request in requests.deposits:
            process_deposit_request(state, request)
        for request in requests.withdrawals:
            process_withdrawal_request(state, request)
        for request in requests.consolidations:
            process_consolidation_request(state, request)
        parent_slot = store.blocks[parent_root].slot
        state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1

    # (b) Set latest_block_hash from fork-choice
    state.latest_block_hash = get_latest_block_hash(store, parent_root)

    # === STATE TRANSITION ===
    state_transition(state, signed_block)
    store.block_states[hash_tree_root(block)] = state

    # REMOVED: block_states vs payload_states branching

    # ... (rest of on_block unchanged) ...


def get_latest_block_hash(store: Store, root: Root) -> Hash32:
    if root in store.payload_block_hashes:
        return store.payload_block_hashes[root]
    return get_latest_full_block_hash(store, root)  # walk back ancestors
```

**Timing equivalence:** Under the current spec, execution requests are processed in `process_execution_payload(N)`, which runs between `process_block(N)` and `process_block(N+1)`. Under this proposal, they're applied at the start of `on_block(N+1)` before `state_transition` runs. By the time `process_epoch` runs, the same pending queues have the same contents.

### Summary of changes

| Component | Current Gloas spec | This proposal |
|-----------|-------------------|---------------|
| `process_execution_payload` | Mutates CL state (requests, availability, hash) | Pure verification, zero mutations |
| `on_execution_payload` | Persists `payload_states[root]` | Buffers verified requests + block hash |
| `on_block` | Branches on parent FULL/EMPTY | Pre-state transition applies parent effects |
| `Store` | `block_states` + `payload_states` | `block_states` + `verified_execution_requests` + `payload_block_hashes` |
| `ExecutionPayloadBid` | Unchanged | Unchanged |
| States per slot | 2 (`block_states` + `payload_states`) | 1 (`block_states` only) |

---

## Tradeoffs

1. **Pre-state transition is a new fork-choice responsibility.** `on_block` must apply parent payload effects before `state_transition`. This replaces the `block_states` vs `payload_states` branching — arguably simpler.

2. **`latest_block_hash` becomes a fork-choice concern.** Must be derived from `store.payload_block_hashes`. Affects Engine API integration and `notify_forkchoice_updated`.

3. **Temporary state copy still needed.** `on_execution_payload` copies `block_states[root]` for verification (state_root, signature, EE), then discards it. Implementations could optimize this.

4. **`state_root` semantics change.** `envelope.state_root` now equals `hash_tree_root(block_states[root])` with no payload effects. Simpler, but changes what the field represents. May not even be needed — `beacon_block_root` already proves knowledge of the block state.

---

## Open Questions

1. **`latest_block_hash` refactor scope.** Moving to fork-choice affects `notify_forkchoice_updated`, safe/finalized block hash derivation. Needs careful mapping.

2. **Equivalence proof.** Test vectors confirming the pre-state transition produces equivalent results to the current `payload_states` approach across edge cases (skipped slots, epoch boundaries, reorgs).

3. **`state_root` field necessity.** Under this proposal, `state_root` in the envelope contains no payload-specific effects. The builder already proves block knowledge via `beacon_block_root`. Is `state_root` still needed?

4. **Optimistic sync.** Optimistic nodes don't have `verified_execution_requests` for unverified payloads — they treat all payloads as EMPTY until EE verification. This is actually an improvement: CL validation proceeds independently of EE state.
