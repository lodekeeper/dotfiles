# Proposal: Payload as Pre-State Transition

**Move all payload effects out of the current slot's state transition. The payload becomes a pure verification step with zero CL state mutations. Payload effects (execution requests, latest_block_hash, availability bit) are applied as a pre-state transition at the start of the next block's processing, at fork-choice level.**

**Date:** 2026-04-07
**Authors:** nflaig (concept direction), lodekeeper (spec sketch)
**Related:** consensus-specs#5074, consensus-specs#5073, beacon-APIs#572
**Prior art:** tbenr (Teku) independently proposed the same high-level approach

---

## Problem Statement

Under Gloas (ePBS), `process_execution_payload` mutates CL state: execution requests go into pending queues, builder payments are queued, availability bits are set. Since FFG only finalizes `{epoch, root}` (the beacon block), and the payload is a separate object whose availability is only justified (not finalized), any payload-dependent CL state mutation makes the finalized state ambiguous.

The core insight: **a payload cannot change the state of the current slot.** Instead, payload effects should be applied as a pre-state transition right before the next beacon block state transition. This eliminates `payload_states` entirely.

## Why Pure Verification Alone Is Insufficient

An earlier version of this proposal extended the withdrawal pattern to execution requests by adding `execution_requests` to `ExecutionPayloadBid` and processing them in `process_block`. This has a **fundamental flaw**:

- **Withdrawals (CL → EL):** CL pre-computes `payload_expected_withdrawals` deterministically from beacon state. CL is source of truth. **The CL can independently verify these.**
- **Execution requests (EL → CL):** Deposits, exits, and consolidations originate from smart contract calls. The CL CANNOT independently compute or verify them — it requires the execution engine. **Putting them in the bid means trusting unverified EL data.**

The solution: execution requests stay in the `ExecutionPayloadEnvelope`, are verified by the EE, and are buffered at fork-choice level for application in the next block.

## Design Principle

> **A payload cannot change `block_states` of its own slot.** All payload effects are applied as a pre-state transition at the start of the next `on_block`. `block_states[root]` is independent of `root`'s own payload status. Ancestor payload statuses DO affect `block_states` (through the pre-state transition), which is correct — ancestors are part of the selected chain.

The two categories of payload effects:

| Category | Direction | Examples | Pattern | Where processed |
|----------|-----------|----------|---------|----------------|
| CL-computable | CL → EL | Withdrawals, builder payments | Pure verification | `process_block` (bid) |
| EL-derived | EL → CL | Deposits, exits, consolidations | Verified buffer | `on_execution_payload` → `on_block` (fork-choice) |
| Bookkeeping | — | `latest_block_hash`, availability bit | Fork-choice metadata | `on_execution_payload` → `on_block` (fork-choice) |

---

## Spec Changes

### 1. `ExecutionPayloadBid` — unchanged

Execution requests are **NOT** added to the bid. They remain in `ExecutionPayloadEnvelope`. The bid only commits to `block_hash` (which transitively commits to the execution requests via the EL block).

```python
class ExecutionPayloadBid(Container):
    parent_block_hash: Hash32
    parent_block_root: Root
    block_hash: Hash32
    prev_randao: Bytes32
    fee_recipient: ExecutionAddress
    gas_limit: uint64
    builder_index: BuilderIndex
    slot: Slot
    value: Gwei
    execution_payment: Gwei
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # No changes — execution requests stay in the envelope
```

### 2. `process_execution_payload_bid` — builder payments only

Builder payments are queued here (CL-computable). Execution requests are NOT processed.

```python
def process_execution_payload_bid(state: BeaconState, block: BeaconBlock) -> None:
    signed_bid = block.body.signed_execution_payload_bid
    bid = signed_bid.message
    builder_index = bid.builder_index
    amount = bid.value

    # ... (existing bid validation: active builder, funds, signature, commitments,
    #      slot, parent block, randao — all unchanged) ...

    # Record the pending payment if there is some payment
    if amount > 0:
        pending_payment = BuilderPendingPayment(
            weight=0,
            withdrawal=BuilderPendingWithdrawal(
                fee_recipient=bid.fee_recipient,
                amount=amount,
                builder_index=builder_index,
            ),
        )
        state.builder_pending_payments[SLOTS_PER_EPOCH + bid.slot % SLOTS_PER_EPOCH] = (
            pending_payment
        )

    # REMOVED: execution request processing (moved to fork-choice level after EE verification)

    # Cache the signed execution payload bid
    state.latest_execution_payload_bid = bid
```

### 3. `process_execution_payload` — pure verification, zero CL state mutations

```python
def process_execution_payload(
    state: BeaconState,
    signed_envelope: SignedExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
    verify: bool = True,
) -> ExecutionRequests:
    """
    Verify payload consistency and EE validity. Returns execution requests
    for the caller to store at fork-choice level. ZERO CL state mutations.
    """
    envelope = signed_envelope.message
    payload = envelope.payload

    # Verify signature
    if verify:
        assert verify_execution_payload_envelope_signature(state, signed_envelope)

    # Cache latest block header state root (standard deferred computation, not a payload effect)
    previous_state_root = hash_tree_root(state)
    if state.latest_block_header.state_root == Root():
        state.latest_block_header.state_root = previous_state_root

    # Verify consistency with the beacon block
    assert envelope.beacon_block_root == hash_tree_root(state.latest_block_header)
    assert envelope.slot == state.slot

    # Verify consistency with the committed bid
    committed_bid = state.latest_execution_payload_bid
    assert envelope.builder_index == committed_bid.builder_index
    assert committed_bid.prev_randao == payload.prev_randao

    # Verify consistency with expected withdrawals (CL-computed, same pattern as today)
    assert hash_tree_root(payload.withdrawals) == hash_tree_root(state.payload_expected_withdrawals)

    # Verify the gas_limit, block_hash, parent_hash, timestamp
    assert committed_bid.gas_limit == payload.gas_limit
    assert committed_bid.block_hash == payload.block_hash
    assert payload.parent_hash == state.latest_block_hash
    assert payload.timestamp == compute_time_at_slot(state, state.slot)

    # Verify the execution payload is valid (EE notification + verification)
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment)
        for commitment in committed_bid.blob_kzg_commitments
    ]
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=envelope.execution_requests,
        )
    )

    # ZERO CL STATE MUTATIONS:
    # REMOVED: for_ops(requests.deposits, process_deposit_request)
    # REMOVED: for_ops(requests.withdrawals, process_withdrawal_request)
    # REMOVED: for_ops(requests.consolidations, process_consolidation_request)
    # REMOVED: builder payment queueing (already done in process_execution_payload_bid)
    # REMOVED: state.execution_payload_availability mutation
    # REMOVED: state.latest_block_hash mutation

    # Verify the state root — state is unchanged from block_states
    if verify:
        assert envelope.state_root == hash_tree_root(state)

    # Return EE-verified execution requests for fork-choice-level storage
    return envelope.execution_requests
```

### 4. Remove `payload_states` from fork-choice `Store`, add payload metadata

```python
@dataclass
class Store(object):
    # ... existing fields ...
    blocks: Dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    # REMOVED: payload_states: Dict[Root, BeaconState]
    # [New] EE-verified execution requests, keyed by beacon block root
    verified_execution_requests: Dict[Root, ExecutionRequests] = field(default_factory=dict)
    # [New] Payload block hashes (replaces state.latest_block_hash for fork-choice)
    payload_block_hashes: Dict[Root, Hash32] = field(default_factory=dict)
```

**Key property:** `verified_execution_requests` is populated ONLY after the EE has verified the payload. Fraudulent execution requests are never stored (EE rejects them → slot is EMPTY). Pruning follows finalization, same GC as `store.block_states`.

### 5. `on_execution_payload` — verify, extract, buffer (no state persisted)

```python
def on_execution_payload(store: Store, signed_envelope: SignedExecutionPayloadEnvelope) -> None:
    """
    Verify execution payload. Store EE-verified execution requests and block hash
    in fork-choice metadata. No block_states mutation.
    """
    envelope = signed_envelope.message

    assert envelope.beacon_block_root in store.block_states
    assert is_data_available(envelope.beacon_block_root)

    # Pure verification on a temporary copy (discarded after)
    state = copy(store.block_states[envelope.beacon_block_root])
    verified_requests = process_execution_payload(state, signed_envelope, EXECUTION_ENGINE)

    # Store at fork-choice level for application in the next on_block
    store.verified_execution_requests[envelope.beacon_block_root] = verified_requests
    store.payload_block_hashes[envelope.beacon_block_root] = envelope.payload.block_hash

    # NO state persisted — the temporary copy is discarded
```

### 6. `on_block` — the pre-state transition (consolidated)

This is the critical change. All parent payload effects are applied as a **pre-state transition** before `state_transition` runs. This is the single, complete `on_block` flow:

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    block = signed_block.message

    # ... (existing parent/finalized checks) ...

    # Start from parent's block_states
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
        # Set parent's availability bit so process_attestation can read it
        parent_slot = store.blocks[parent_root].slot
        state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1

    # (b) Set latest_block_hash from fork-choice (for bid.parent_block_hash validation)
    state.latest_block_hash = get_latest_block_hash(store, parent_root)

    # === STATE TRANSITION ===
    block_root = hash_tree_root(block)
    state_transition(state, signed_block)

    # Store the result
    store.block_states[block_root] = state

    # REMOVED:
    #   if is_parent_block_full(block):
    #       state = copy(store.payload_states[block.parent_root])
    #   else:
    #       state = copy(store.block_states[block.parent_root])

    # ... (rest of on_block unchanged) ...


def get_latest_block_hash(store: Store, root: Root) -> Hash32:
    """Return the EL block hash for this node, considering payload status."""
    if root in store.payload_block_hashes:
        return store.payload_block_hashes[root]
    else:
        # Walk back to find the last FULL ancestor's block hash
        return get_latest_full_block_hash(store, root)
```

**Why this preserves execution request timing:** Under the current spec, execution requests are processed in `process_execution_payload(N)`, which runs between `process_block(N)` and `process_block(N+1)`. Under the hybrid, they're applied at the start of `on_block(N+1)` — BEFORE `state_transition(state, block_N+1)` runs. The result is identical: by the time `process_epoch` runs, the same pending queues have the same contents.

**Concrete trace for epoch boundary (slot 63 → 64, epoch 2 boundary):**

| Step | Current spec | This proposal |
|------|-------------|---------------|
| `on_block(63)` | Start from `payload_states[R62]` or `block_states[R62]` | Start from `block_states[R62]` + apply slot 62's payload effects |
| `process_execution_payload(63)` | Execution requests → pending queues, set availability, update hash | Pure verification; requests → `store.verified_execution_requests[R63]` |
| Checkpoint state at epoch 2 | **Ambiguous** (depends on `block_states` vs `payload_states` for slot 63) | **Deterministic** (`block_states[R63]` same regardless of slot 63's FULL/EMPTY) |
| `on_block(64)` | Start from `payload_states[R63]` (FULL) or `block_states[R63]` (EMPTY) | Start from `block_states[R63]` + apply slot 63's payload effects if FULL |

---

## What This Achieves

### Checkpoint state is unambiguous

`store_target_checkpoint_state` takes `block_states[target.root]` and advances to epoch boundary. `block_states[root]` is independent of `root`'s own payload status — all payload effects for that slot are deferred to the next `on_block`. Therefore the checkpoint state is deterministic for any `{epoch, root}`.

Note: `block_states` DOES reflect ancestor payload statuses (through the pre-state transition in `on_block`). This is correct — ancestors are part of the selected chain and their payload status is determined.

### Finalized state is truly finalized

FFG finalizes `{epoch, root}`. The `block_states[root]` derives from the beacon block chain plus ancestor payload effects (which are determined by the finalized chain). The target's own payload status is irrelevant. No "justified payload status" problem.

### No `payload_states`

`store.payload_states` is eliminated. The FULL/EMPTY distinction is preserved in `ForkChoiceNode(root, payload_status)` for chain selection and in `store.verified_execution_requests` for the pre-state transition.

### Execution requests are never unverified

Execution requests are only stored in `store.verified_execution_requests` after the EE has verified the payload. Fraudulent requests are rejected by the EE and never enter the CL state.

### Beacon API endpoints become unambiguous

- `finalized` / `justified`: return `block_states[checkpoint.root]` advanced to epoch boundary — always deterministic
- `head`: return head state with pre-state transition applied (execution requests + latest_block_hash)
- Payload status is metadata, not a state query parameter

---

## Tradeoffs

### 1. Pre-state transition is a new fork-choice responsibility

`on_block` must apply `store.verified_execution_requests[parent_root]`, set `latest_block_hash`, and set the availability bit before `state_transition`. This replaces the `block_states` vs `payload_states` branching — arguably simpler.

### 2. `latest_block_hash` becomes a fork-choice concern

`latest_block_hash` depends on payload delivery (FULL/EMPTY). It must be derived from `store.payload_block_hashes` at fork-choice level. This is a moderate refactor affecting Engine API integration and `notify_forkchoice_updated`.

### 3. `process_execution_payload` still needs a temporary state copy

For consistency checks (state_root verification, signature, EE notification). The copy is discarded after verification. Implementations could optimize this.

### 4. Fork-choice store gains new maps

`store.verified_execution_requests` and `store.payload_block_hashes`. Both bounded by fork-choice tree size, pruned on finalization.

### 5. No bid changes, no bandwidth increase

Unlike earlier versions of this proposal, execution requests are NOT added to the bid.

---

## Comparison with Other Approaches

| Property | #5073 (get_ancestor) | 5c v1 (pure verification) | **This proposal** |
|----------|---------------------|--------------------------|---------------------|
| Finalized state deterministic | No (justified-level) | Yes (but trusts unverified EL data) | **Yes (fully, no trust issue)** |
| Checkpoint state unambiguous | Partially | Yes | **Yes** |
| `payload_states` needed | Yes | No | **No** |
| Execution requests verified by EE | Yes | No (bid commitment only) | **Yes** |
| Bid container changes | No | Yes | **No** |
| Fork-choice changes | New store field | Remove `payload_states` | **Remove `payload_states`, add verified buffer** |
| `process_execution_payload` | Unchanged | Pure verification | **Pure verification + extraction** |
| `on_block` changes | Minor | Remove FULL/EMPTY branching | **Replace branching with pre-state transition** |
| Beacon API ambiguity | Partially resolved | Fully resolved | **Fully resolved** |
| Resolves #5074 | No | Yes | **Yes** |
| Makes #5073 unnecessary | No | Yes | **Yes** |
| Simplifies beacon-APIs#572 | No | Yes | **Yes** |

---

## Acceptance Criteria Verification

### 1. Only 1 state transition per slot ✅

Current Gloas: 2 state transitions per slot (`on_block` → `block_states`, `on_execution_payload` → `payload_states`).

This proposal: 1 persistent state transition per slot (`on_block` → `block_states`). `on_execution_payload` runs pure verification on a throwaway copy and stores only fork-choice metadata.

### 2. Checkpoint sync works with skipped slots, irrespective of payload status ✅

`store_target_checkpoint_state` uses `block_states[target.root]` which is independent of the target's own payload status. Advancing to epoch boundary via `process_slots` is deterministic:

- **No skips (target at boundary):** payload comes after `process_epoch` → no impact
- **Skipped slots (target before boundary):** `process_epoch` drains pending queues from ancestor payloads (applied in pre-state transitions). Target's own payload effects are deferred to next `on_block` → not in `block_states`
- **Many skips:** target's payload effects delayed — same gap exists in the current spec's `block_states`. Not introduced by this proposal.

All scenarios produce the same checkpoint state regardless of the target's FULL/EMPTY status.

### 3. No gaps for malicious builder to corrupt the chain ✅

- Execution requests only enter `store.verified_execution_requests` AFTER EE verification
- Fraudulent requests → EE rejects → payload fails → slot EMPTY → builder forfeits bid
- Builder can't stuff fork-choice maps — entries require valid blocks in `store.block_states` + EE verification

### 4. No CL spec gaps that make this impossible ✅

- `process_execution_payload` can be zero-mutation (all effects moved to fork-choice level)
- `state_root` semantics change is a deliberate spec change (builder + verifier agree on new rules)
- `execution_payload_availability` set in `on_block` pre-state transition (parent's bit) — `process_attestation` reads it correctly
- `payload.parent_hash == state.latest_block_hash` verification works (state has fork-choice-derived `latest_block_hash`)
- `process_epoch` doesn't read any payload-specific state fields

### 5. No hard blockers ✅

| Item | Status |
|------|--------|
| `latest_block_hash` refactor | Moderate work, follows existing patterns |
| Equivalence proof | Equivalent by construction, needs test vectors |
| `state_root` semantic change | Deliberate, simpler than current |
| Justified balance divergence (#5074) | Resolved — `block_states` is payload-independent, no divergence |
| Optimistic sync | Improved — CL independent of EE |

---

## Alignment with Existing Discussion

This proposal formalizes the approach independently described by tbenr (Teku) and nflaig (Lodestar):

| Discussion point | Proposal alignment |
|---|---|
| tbenr: "second state transition in same slot causes issues" | Only 1 persistent state per slot |
| tbenr: "payload state transition as pre-state transition before next beacon block" | Step 6: pre-state transition in `on_block` |
| tbenr: "payload cannot change state of current slot" | Zero CL mutations in `process_execution_payload` |
| tbenr: "no concept of payload states" | `payload_states` removed from Store |
| tbenr: "1-1 relationship between beaconBlockRoot and state is a big deal" | `block_states[root]` = exactly one state per root |
| nflaig: "execution_requests likely need to go in the bid" | **Solved without bid changes** — verified buffer at fork-choice level |

### Why execution requests don't need to be in the bid

The earlier approach (v1) put execution requests in the bid so `process_block` could process them. This was flawed because execution requests are EL-derived — the CL can't verify them independently (unlike withdrawals, which the CL computes).

Under this proposal, execution requests don't need to be in the bid because:

1. **They're not processed during `process_block`** — all execution request processing is deferred to the next `on_block`
2. **The bid already transitively commits to them** — `bid.block_hash` is the EL block hash, which determines the execution requests
3. **The EE verifies them** — `process_execution_payload` sends them to the EE for verification before they're stored
4. **The envelope carries them** — they arrive with the payload in `ExecutionPayloadEnvelope`, same as today

Withdrawals ARE processed in `process_block` (via `payload_expected_withdrawals`) because the CL is the source of truth for those. Execution requests are fundamentally different — the EL is the source of truth.

### On the justified balance gap (Potuz vs dapplion)

**Potuz claims** this is "just an API thing" with no consensus issues. **Dapplion (consensus-specs#5074)** argues justified balances can diverge between nodes depending on whether they've seen the payload.

**Analysis:** Dapplion's core concern is **divergence** — under the current Gloas spec, nodes that have seen a payload compute different `block_states` from nodes that haven't, because `process_execution_payload` mutates CL state (execution requests → pending queues). This means `store_target_checkpoint_state` produces different justified states for different nodes, affecting `get_weight` fork choice scoring.

**Our proposal resolves this.** Since all payload effects are deferred to the next `on_block`, `block_states[root]` is independent of `root`'s own payload status. All nodes compute the **same** `block_states[justified_root]` regardless of whether they've seen that slot's payload. There is no divergence in justified balances.

The execution requests from the justified slot's payload are "pending" — they become effective when the next proposer builds on that block, at which point `on_block` applies them as a pre-state transition. This is the same deferred-processing pattern that pending queues already use in Ethereum consensus. It's not a gap — it's by design.

Potuz is correct that there's no consensus split. Under our proposal, there's also no justified balance divergence — the concern dapplion raised is fully addressed.

**Sproul's suggestion** to change the Checkpoint type to `{epoch, root, payload_status}` is a more invasive alternative that could close the gap by making FFG finalize payload status. Under our proposal this is unnecessary — the gap doesn't exist because `block_states` is already payload-independent.

---

## Open Questions

1. **`latest_block_hash` refactor scope:** Moving to fork-choice affects Engine API integration, `notify_forkchoice_updated`, safe/finalized block hash derivation. Needs careful mapping.

2. **Equivalence proof:** Formal proof or test vectors confirming the pre-state transition in `on_block` produces equivalent results to the current `payload_states` approach across all edge cases (multiple skipped slots, epoch boundaries, reorgs).

3. **`state_root` semantics in `ExecutionPayloadEnvelope`:** Under this proposal, `state_root` = `hash_tree_root(block_states[root] with latest_block_header.state_root filled in)`. No payload-specific effects. This is simpler but changes what `state_root` represents. Is the field even needed? The builder already proves knowledge of the block state via `beacon_block_root`.

4. **Optimistic sync:** Optimistic nodes don't have `verified_execution_requests` for unverified payloads. They effectively treat all payloads as EMPTY until EE verification completes. This is actually BETTER — CL validation proceeds independently of EE state.

---

## Reviews (GPT-5.4 Pro)

### v2 Adversarial Review (Devil's Advocate)

| Issue | Severity | Assessment |
|-------|----------|-----------|
| Verified buffer + reorgs | LOW | Buffer keyed by root, immutable. Reorgs change which entries are used, not the entries themselves. Same model as `store.block_states`. |
| `on_block` equivalence with `payload_states` | HIGH | Equivalent by construction: both produce `block_states[parent] + execution_requests + state_transition(block)`. Needs formal proof. |
| Epoch boundary + EMPTY | LOW | No race condition. Single-threaded fork choice. EMPTY = no buffer entry = nothing applied. |
| `state_root` semantics change | MEDIUM | Deliberate spec change. Simpler — just `block_states` with header filled in. Builder and verifier agree. |
| Memory/DoS | LOW | Bounded by fork-choice tree. Entries only created for blocks in `store.block_states`. Same GC. |
| Initial/checkpoint sync | LOW | Checkpoint state is payload-independent. No verified buffer needed for checkpoint itself. |
| Pruning | LOW | Prune on finalization, same as `store.block_states`. |
| `latest_block_hash` refactor | MEDIUM | Moderate complexity. Follows existing fork-choice ancestor-walking patterns. |

### v2 Defender Review (Advocate)

| Claim | Confidence |
|-------|-----------|
| Execution request timing preserved | HIGH — buffer application in `on_block` before `state_transition` is equivalent to starting from `payload_states` |
| `block_states[root]` independent of root's own payload | HIGH — all payload effects deferred to next `on_block` |
| `payload_states` removal safe for fork choice | HIGH — FULL/EMPTY preserved in `ForkChoiceNode` + verified buffer |
| Stronger trust model than v1 | HIGH — only EE-verified requests enter CL state |
| No bid size increase | HIGH — execution requests not in bid |
| Checkpoint determinism in edge cases | MEDIUM — needs formal proof across skipped slots, reorgs, multiple EMPTY |
