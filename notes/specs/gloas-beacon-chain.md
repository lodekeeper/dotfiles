# Gloas/EPBS — Beacon Chain Spec Notes

*Source: `consensus-specs/specs/gloas/beacon-chain.md`*
*Studied: 2026-02-15*

## Core Concept: Two-Phase State Transition

The fundamental change in ePBS. State transition is split:
1. **Block import** — `state_transition(state, signed_block)` — processes the beacon block with the builder's bid
2. **Payload import** — `process_execution_payload(state, signed_envelope, execution_engine)` — processes the execution payload separately

This separation allows the execution payload to arrive independently from the beacon block.

## Key New Types & Containers

### Builder Registry
- **`Builder`**: pubkey, version (withdrawal prefix), execution_address, balance, deposit_epoch, withdrawable_epoch
- **`BuilderIndex`**: uint64, similar to ValidatorIndex
- **`BUILDER_INDEX_FLAG`**: `2^40` — bitwise flag to encode BuilderIndex as ValidatorIndex
  - `convert_builder_index_to_validator_index`: `index | BUILDER_INDEX_FLAG`
  - `convert_validator_index_to_builder_index`: `index & ~BUILDER_INDEX_FLAG`
  - Used in withdrawals to share the Withdrawal container between validators and builders

### Execution Payload Bid (in beacon block)
- **`ExecutionPayloadBid`**: parent_block_hash, parent_block_root, block_hash, prev_randao, fee_recipient, gas_limit, builder_index, slot, value, execution_payment, blob_kzg_commitments
- Included in `BeaconBlockBody.signed_execution_payload_bid`
- Proposer commits to a builder's bid in the block

### Execution Payload Envelope (separate from block)
- **`ExecutionPayloadEnvelope`**: payload, execution_requests, builder_index, beacon_block_root, slot, state_root
- Builder signs and publishes separately
- Contains actual execution payload + requests (deposits, withdrawals, consolidations)

### Self-Builds
- `BUILDER_INDEX_SELF_BUILD = UINT64_MAX` — proposer builds their own payload
- Amount must be 0, signature is `G2_POINT_AT_INFINITY` (no builder to pay)

## Payload Timeliness Committee (PTC)
- **PTC_SIZE**: 512 validators per slot
- Selected via `compute_balance_weighted_selection` from all slot committees
- `shuffle_indices=False` (order matters — taken from concatenated committees)
- Domain: `DOMAIN_PTC_ATTESTER`
- PTC members attest to payload availability via `PayloadAttestationMessage`

## Builder Payment System
- **Two-epoch delayed**: Payments queued in `builder_pending_payments` (vector of 2*SLOTS_PER_EPOCH)
- **Quorum threshold**: 60% of per-slot total active balance (`6/10 * total_balance / SLOTS_PER_EPOCH`)
- **Same-slot attestations** accumulate weight for builder payment
- **`process_builder_pending_payments`** (epoch processing): checks if quorum met, moves to `builder_pending_withdrawals`
- **If proposer is slashed**: pending payment for that slot is zeroed out

## Modified Block Processing Order
```
process_block:
  1. process_block_header
  2. process_withdrawals (state only — no payload param!)
  3. process_execution_payload_bid (NEW)
  4. process_randao
  5. process_eth1_data
  6. process_operations (includes payload_attestations)
  7. process_sync_aggregate
```

Key: `process_withdrawals` BEFORE `process_execution_payload_bid` (bid affects balances).

## Modified Withdrawals
Order: builder pending → partial → builder sweep → validator sweep
- All must fit in `MAX_WITHDRAWALS_PER_PAYLOAD - 1` (one slot reserved?)
- Builder withdrawals use `convert_builder_index_to_validator_index` for the Withdrawal.validator_index field
- Builder sweep: iterates builders with `withdrawable_epoch <= current_epoch && balance > 0`
- `process_withdrawals` returns early if parent block was empty (`!is_parent_block_full`)

## Attestation Changes
- `data.index` repurposed: 0 or 1, signals payload availability (no longer committee index)
- `is_attestation_same_slot`: checks if attestation is for the block proposed at that slot
- Same-slot attestations with new flags → add validator's effective_balance to builder payment weight
- `payload_matches` check for head matching uses `execution_payload_availability` bitvector

## Deposit Routing
- `BUILDER_WITHDRAWAL_PREFIX = 0x03`
- Deposits with builder prefix → `apply_deposit_for_builder` (immediate, not queued)
- Deposits to existing builder pubkeys → balance increase (regardless of prefix)
- New builder deposits → signature verification (proof of possession)
- Builder indices are **reusable** — exited builder slots can be filled by new builders

## State Changes
New fields in `BeaconState`:
- `latest_execution_payload_bid` (replaces `latest_execution_payload_header`)
- `builders` — builder registry
- `next_withdrawal_builder_index` — sweep cursor
- `execution_payload_availability` — bitvector[SLOTS_PER_HISTORICAL_ROOT]
- `builder_pending_payments` — vector[2*SLOTS_PER_EPOCH]
- `builder_pending_withdrawals` — list
- `latest_block_hash` — Hash32
- `payload_expected_withdrawals` — cached for envelope verification

Removed from `BeaconBlockBody`:
- `execution_payload` → now in `ExecutionPayloadEnvelope`
- `blob_kzg_commitments` → now in `ExecutionPayloadBid`
- `execution_requests` → now in `ExecutionPayloadEnvelope`

## Execution Payload Processing (process_execution_payload)
1. Verify envelope signature (builder or proposer for self-builds)
2. Cache latest block header state root
3. Verify envelope.beacon_block_root matches state's latest_block_header
4. Verify consistency with committed bid (builder_index, prev_randao, gas_limit, block_hash)
5. Verify withdrawals match `state.payload_expected_withdrawals`
6. Verify payload parent_hash = state.latest_block_hash
7. Verify timestamp
8. Execute payload via execution engine
9. Process execution requests (deposits, withdrawals, consolidations)
10. Queue builder payment to pending_withdrawals (if quorum met) OR clear pending payment
11. Update `execution_payload_availability` and `latest_block_hash`
12. Verify state_root (if verify=True)

## Things to Check in Lodestar
- [ ] Builder index flag encoding/decoding correctness
- [ ] Two-phase state transition implementation
- [ ] PTC selection: balance-weighted, shuffle_indices=False
- [ ] Builder payment quorum calculation
- [ ] Attestation data.index handling (0/1 for payload availability)
- [ ] Withdrawal ordering (builder → partial → builder sweep → validator sweep)
- [ ] Self-build handling (UINT64_MAX, zero amount, infinity signature)
- [ ] Deposit routing logic (builder prefix vs validator)
- [ ] Proposer slashing clearing pending payments
- [ ] is_parent_block_full check in process_withdrawals

---
*Next: fork-choice.md, then compare against Lodestar implementation*
