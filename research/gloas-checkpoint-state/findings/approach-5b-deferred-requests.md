# Approach 5b: Deferred Execution Request Processing

**Proposal:** Quarantine execution request effects from epoch transition so that `block_states` and `payload_states` produce identical checkpoint states.

**Date:** 2026-04-07
**Status:** Sketch / discussion document
**Related:** consensus-specs#5074, consensus-specs#5073, beacon-APIs#572

---

## The Problem (Recap)

`store_target_checkpoint_state` computes checkpoint state by taking `block_states[target.root]` and advancing via `process_slots` to the epoch boundary. Under Gloas, `process_execution_payload` mutates CL state (execution requests → pending queues, builder payments), and `process_epoch` consumes those pending queues. For skipped epoch-boundary slots, the checkpoint state depends on whether the payload was FULL or EMPTY — but FFG only finalizes `{epoch, root}`, not payload status.

## Why This Approach Works

The root cause is a **coupling** between payload-dependent state mutations and epoch processing:

```
process_execution_payload
  ├── for_ops(requests.deposits, process_deposit_request)      → mutates pending_deposits
  ├── for_ops(requests.withdrawals, process_withdrawal_request) → mutates exit queues
  ├── for_ops(requests.consolidations, process_consolidation_request) → mutates pending_consolidations
  └── builder payment queueing                                  → mutates builder_pending_payments

process_epoch
  ├── process_pending_deposits      → reads/drains pending_deposits
  ├── process_pending_consolidations → reads/drains pending_consolidations
  ├── process_builder_pending_payments → reads/drains builder_pending_payments
  └── process_effective_balance_updates → reads balances (affected by above)
```

**If we break this coupling** — making `process_execution_payload` NOT write to queues that `process_epoch` reads — then the epoch-boundary state is identical regardless of payload status. The checkpoint state becomes unambiguous for any `{epoch, root}`.

## Spec Changes (Sketch)

### 1. New BeaconState field: execution request buffer

```python
class BeaconState(Container):
    # ... existing fields ...
    # [New] Buffer for execution requests awaiting epoch-boundary processing
    # Populated by process_execution_payload, drained in process_slot at epoch start
    buffered_execution_requests: List[ExecutionRequests, SLOTS_PER_EPOCH]
```

### 2. Modified `process_execution_payload`

Buffer requests instead of processing them immediately:

```python
def process_execution_payload(
    state: BeaconState,
    signed_envelope: SignedExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
    verify: bool = True,
) -> None:
    envelope = signed_envelope.message
    payload = envelope.payload

    # ... (signature, consistency, gas, hash, timestamp, EE verification — unchanged) ...

    requests = envelope.execution_requests
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=requests,
        )
    )

    # ---- CHANGED: buffer requests instead of processing immediately ----
    # OLD:
    #   for_ops(requests.deposits, process_deposit_request)
    #   for_ops(requests.withdrawals, process_withdrawal_request)
    #   for_ops(requests.consolidations, process_consolidation_request)
    # NEW:
    state.buffered_execution_requests.append(requests)

    # ---- CHANGED: defer builder payment queueing ----
    # OLD:
    #   payment = state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH]
    #   amount = payment.withdrawal.amount
    #   if amount > 0:
    #       state.builder_pending_withdrawals.append(payment.withdrawal)
    #   state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH] = (
    #       BuilderPendingPayment()
    #   )
    # NEW: leave builder_pending_payments untouched until epoch boundary
    # (builder payment resolution happens in process_epoch via process_builder_pending_payments,
    #  which already only processes the PREVIOUS epoch's payments)

    # ---- UNCHANGED ----
    state.execution_payload_availability[state.slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1
    state.latest_block_hash = payload.block_hash

    if verify:
        assert envelope.state_root == hash_tree_root(state)
```

### 3. New `process_buffered_execution_requests` (runs after epoch transition)

```python
def process_buffered_execution_requests(state: BeaconState) -> None:
    """
    Drain the execution request buffer into pending queues.
    Called AFTER process_epoch, so epoch-boundary state is payload-independent.
    """
    for requests in state.buffered_execution_requests:
        for_ops(requests.deposits, process_deposit_request)
        for_ops(requests.withdrawals, process_withdrawal_request)
        for_ops(requests.consolidations, process_consolidation_request)

    state.buffered_execution_requests = []
```

### 4. Modified `process_slot` (drain buffer at epoch boundary)

```python
def process_slot(state: BeaconState) -> None:
    # ... existing slot processing ...

    # [New in approach 5b]
    # At epoch boundary, drain buffered execution requests AFTER epoch transition
    # Note: process_slot is called before process_epoch in process_slots,
    # so this actually needs to go in process_slots AFTER process_epoch
```

More precisely, in `process_slots`:

```python
def process_slots(state: BeaconState, slot: Slot) -> None:
    assert state.slot < slot
    while state.slot < slot:
        process_slot(state)
        if (state.slot + 1) % SLOTS_PER_EPOCH == 0:
            process_epoch(state)
            # [New] Drain buffered requests AFTER epoch transition
            process_buffered_execution_requests(state)
        state.slot = Slot(state.slot + 1)
```

### 5. Builder payment: already mostly safe

Looking at the current spec more carefully:

```python
def process_builder_pending_payments(state: BeaconState) -> None:
    """Processes the builder pending payments from the previous epoch."""
    quorum = get_builder_payment_quorum_threshold(state)
    for payment in state.builder_pending_payments[:SLOTS_PER_EPOCH]:
        if payment.weight >= quorum:
            state.builder_pending_withdrawals.append(payment.withdrawal)
    old_payments = state.builder_pending_payments[SLOTS_PER_EPOCH:]
    new_payments = [BuilderPendingPayment() for _ in range(SLOTS_PER_EPOCH)]
    state.builder_pending_payments = old_payments + new_payments
```

This processes `builder_pending_payments[:SLOTS_PER_EPOCH]` — the **previous** epoch's payments. The current epoch's payments are in `builder_pending_payments[SLOTS_PER_EPOCH:]`.

In `process_execution_payload`, the builder payment is queued at index `SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH` — i.e., in the current epoch's half. So `process_builder_pending_payments` during THIS epoch's transition only reads the PREVIOUS epoch's half, which was already settled.

**However**, the builder payment queueing in `process_execution_payload` also does:
```python
state.builder_pending_withdrawals.append(payment.withdrawal)
```
This appends to `builder_pending_withdrawals` which could be read during epoch processing. This line needs to be deferred too — or the conditional append should move to epoch processing.

The simplest fix: don't append to `builder_pending_withdrawals` in `process_execution_payload`. Let `process_builder_pending_payments` handle all payment resolution during epoch transition (it already does this for the previous epoch's payments). The current-epoch payments just wait.

---

## Why This Is Viable

### 1. Removes the ambiguity at the source

Other approaches try to **resolve** the FULL/EMPTY ambiguity downstream (infer from justified, add to checkpoint, etc.). This approach **eliminates** it: both paths produce identical epoch-boundary states. No inference, no extra checkpoint fields, no justified-level security concerns.

### 2. Minimal protocol surface change

- No changes to `Checkpoint` container (stays `{epoch, root}`)
- No changes to `AttestationData` (no payload status field)
- No changes to FFG, fork choice tree structure, or attestation validation
- No changes to checkpoint sync protocol
- One new BeaconState field (`buffered_execution_requests`)
- One new processing step (`process_buffered_execution_requests`)
- One modified function (`process_execution_payload`)

### 3. Follows an existing Gloas pattern

Gloas already defers withdrawals: `process_block` calls `process_withdrawals(state)` using pre-cached `payload_expected_withdrawals` before the payload is revealed. The payload then just verifies consistency. This proposal extends the same "process deterministically early, verify later" philosophy to execution requests.

### 4. Preserves all existing invariants

- Checkpoint state is at epoch boundary: **preserved**
- `state.slot % SLOTS_PER_EPOCH == 0` for checkpoint states: **preserved**
- `store_target_checkpoint_state` produces unique result per `{epoch, root}`: **restored**
- Checkpoint sync: **unchanged** (no new fields, no new protocol)
- Weak subjectivity checks: **unchanged**
- Fork choice FULL/EMPTY distinction: **preserved** (fork choice still tracks payload status)

### 5. Resolves both #5074 and #5073's concern

- #5074 (justified balances underspecified): epoch-boundary state is now unique → justified balances are deterministic
- #5073's weakness (payload status only justified): no longer needed — checkpoint state doesn't depend on payload status at all

---

## Tradeoffs and Considerations

### 1. Execution request processing delayed by up to 1 epoch (~6.4 min)

Deposits, exits, and consolidations take effect one epoch later than today.

**Mitigation:** These already have multi-epoch delays:
- Deposit activation: `MAX_PENDING_DEPOSITS_PER_EPOCH` rate limit + activation queue (can be many epochs)
- Validator exits: `exit_balance_to_consume` rate limit + exit queue + `MIN_VALIDATOR_WITHDRAWABILITY_DELAY` (256 epochs)
- Consolidations: `consolidation_balance_to_consume` rate limit + pending queue

One additional epoch is marginal relative to existing delays. No security properties depend on sub-epoch execution request processing.

### 2. New BeaconState field increases state size

`buffered_execution_requests: List[ExecutionRequests, SLOTS_PER_EPOCH]` adds up to 32 slots worth of execution requests to state.

**Mitigation:** The buffer is drained every epoch, so it's bounded by one epoch's worth of requests. In practice, most slots produce modest request lists. The `pending_deposits`, `pending_consolidations`, and `pending_partial_withdrawals` lists are already larger.

### 3. Builder payment timing subtlety

The current `process_execution_payload` appends to `builder_pending_withdrawals` immediately for the current epoch. Deferring this changes when the builder receives payment.

**Mitigation:** `process_builder_pending_payments` already processes the previous epoch's payments during epoch transition. The current epoch's payments are already delayed until the next epoch boundary. The only change is that the conditional `builder_pending_withdrawals.append()` in `process_execution_payload` is also deferred to epoch processing. Builder payment timing shifts by at most 1 epoch.

### 4. Interaction with `process_effective_balance_updates`

If deposits/exits/consolidations are deferred, the effective balance updates during epoch transition won't reflect this epoch's execution requests.

**Impact:** Minimal. Effective balances already use hysteresis (`EFFECTIVE_BALANCE_INCREMENT` thresholds), so individual epoch-level delays don't meaningfully shift validator weights. The active validator set changes that matter (activations, exits) are already rate-limited across many epochs.

### 5. `execution_payload_availability` and `latest_block_hash` still differ between FULL/EMPTY

These fields ARE still different in `block_states` vs `payload_states`. But `process_epoch` doesn't read them:
- `execution_payload_availability`: read by fork choice and attestation validation, not epoch processing
- `latest_block_hash`: read by Engine API and payload verification, not epoch processing

So they don't affect checkpoint state computation.

### 6. `envelope.state_root` verification changes

The `state_root` in `SignedExecutionPayloadEnvelope` commits to post-payload state. With this change, the post-payload state now has requests in a buffer instead of in pending queues. This is a different state root than the current spec produces.

**Impact:** This is a consensus-breaking change (like any spec modification). All clients must implement the same behavior. The state root is still deterministic and verifiable — it just commits to a different (buffer-based) state layout.

### 7. Cross-epoch request ordering

Requests from the last slot of epoch N are buffered and processed at the epoch N→N+1 boundary. Requests from the first slot of epoch N+1 are processed immediately in `process_execution_payload` (they won't be buffered because the next epoch boundary is a full epoch away).

Wait — actually, ALL requests are buffered regardless of position in epoch. They're all drained at the next epoch boundary. So:
- Epoch N requests: drained at N→N+1 boundary
- Epoch N+1 requests: drained at N+1→N+2 boundary

Ordering within the buffer preserves slot order. Cross-epoch ordering is preserved because each epoch's buffer is fully drained before the next epoch's buffer starts filling.

---

## Comparison to Other Approaches

| Property | Approach 2 (get_ancestor) | Approach 3 (triple) | **Approach 5b (defer)** |
|----------|---------------------------|---------------------|-------------------------|
| Checkpoint container changes | No | Yes (massive) | No |
| Attestation changes | No | Yes (massive) | No |
| Fork choice changes | Yes (new store field) | Yes | No |
| Beacon chain changes | No | Yes | Yes (moderate) |
| BeaconState changes | No | Yes | Yes (1 new field) |
| Checkpoint sync changes | Maybe | Yes | No |
| Finalized state deterministic | No (justified-level) | Yes | **Yes** |
| Additional delay | None | None | ~1 epoch for requests |
| Spec invasiveness | Low | Very high | **Low-moderate** |
| Resolves #5074 | Partially | Yes | **Yes** |
| Resolves #5073 concern | No | Yes | **Yes (makes #5073 unnecessary)** |

---

## Open Questions

1. **Is 1-epoch delay acceptable for deposits?** Specifically: does any DeFi/staking protocol depend on sub-epoch deposit activation? (Likely no, given existing multi-epoch delays.)

2. **Builder payment timing:** Does deferring the `builder_pending_withdrawals.append()` affect builder incentives or MEV dynamics?

3. **Buffer size bounds:** What's the maximum realistic size of `buffered_execution_requests` for one epoch? Need to verify it fits within SSZ limits comfortably.

4. **Interaction with delayed execution (EIP-7886):** If delayed execution is adopted, it already separates validation from execution. Does approach 5b compose cleanly with it, or does it become redundant?

5. **Consensus on deferral timing:** Should the buffer drain happen:
   - (a) In `process_slots` right after `process_epoch` (cleanest for checkpoint state)
   - (b) In `process_slot` at the start of epoch+1 slot 0
   - (c) In a new processing phase between epoch transition and first block

   Option (a) is sketched above. Options (b) and (c) are equivalent but differ in spec organization.
