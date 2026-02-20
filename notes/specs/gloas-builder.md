# Gloas/EPBS — Honest Builder Spec Notes

*Source: `consensus-specs/specs/gloas/builder.md`*
*Studied: 2026-02-15*

## Builder Lifecycle

### Registration
1. Submit deposit to deposit contract with `BUILDER_WITHDRAWAL_PREFIX` (`0x03`)
2. Withdrawal credentials: `0x03 || 00*11 || execution_address`
3. Minimum amount: `MIN_DEPOSIT_AMOUNT`
4. Assigned `builder_index` in builder registry when deposit processed

### Activation
- Active once deposit epoch is **finalized** (typically ~2 epochs after deposit)
- At fork: pending deposits with builder prefix applied immediately; if their deposit_epoch is already finalized, builder is instantly active

### Key Difference from Validators
- Builders are NOT validators — no attesting, no proposing, no yield on stake
- Only activity: submit bids + deliver payloads
- Separate registry (`state.builders`) from validator registry

## Bid Construction (SignedExecutionPayloadBid)

12-step process:
1. `parent_block_hash` ← `state.latest_block_hash`
2. `parent_block_root` ← `hash_tree_root(state.latest_block_header)` (must be compatible with parent_block_hash)
3. Construct execution payload via `engine_getPayloadV5`
4. `block_hash` ← `payload.block_hash`
5. `prev_randao` ← `payload.prev_randao`
6. `fee_recipient` ← builder's address (can use proposer's preferred from `SignedProposerPreferences`)
7. `gas_limit` ← from payload (can use proposer's preferred)
8. `builder_index` ← builder's own index
9. `slot` ← current or next slot
10. `value` ← payment to proposer (must have sufficient excess balance)
11. `execution_payment` ← 0 for gossip bids (non-zero = trusted EL payment, must NOT gossip)
12. `blob_kzg_commitments` ← from `engine_getPayloadV5`

Signed with `DOMAIN_BEACON_BUILDER`, broadcast on `execution_payload_bid` gossip topic.

## Envelope Construction (SignedExecutionPayloadEnvelope)

After proposer publishes block containing builder's bid:
1. `payload` ← same payload used for bid (block_hash must match)
2. `execution_requests` ← associated with payload
3. `builder_index` ← must match bid
4. `beacon_block_root` ← `hash_tree_root(block)`
5. `slot` ← `block.slot`
6. Verify with `process_execution_payload(state, envelope, engine, verify=False)` — no exception
7. `state_root` ← `hash_tree_root(state)` (post-processing)

Signed with `DOMAIN_BEACON_BUILDER`, broadcast on `execution_payload` gossip topic.

## DataColumnSidecar Changes

Major simplification for ePBS:
- **Removed**: `signed_block_header`, `kzg_commitments`, `kzg_commitments_inclusion_proof`
- **Added**: `beacon_block_root`, `slot`
- No more inclusion proofs needed — KZG commitments are in the bid (separate from block body)
- Sidecars reference `beacon_block_root` directly instead of block header

## Honest Payload Withholding

Builder can withhold payload if the beacon block referencing their bid was **not timely** (not head of builder's chain). In this case, builder simply doesn't broadcast — acts as if no block was produced.

This is the "conditional payment" aspect: builder pays regardless (bid amount), but can choose not to deliver if the block isn't canonical.

## Things to Check in Lodestar
- [ ] Builder deposit routing with `0x03` prefix
- [ ] Builder activation: finalized deposit epoch check
- [ ] Bid construction flow: compatibility of parent_block_hash and parent_block_root
- [ ] execution_payment field handling (zero for gossip, non-zero for trusted)
- [ ] DataColumnSidecar simplified format (no inclusion proofs)
- [ ] Envelope state_root calculation (process with verify=False, then set state_root)
- [ ] Payload withholding logic (non-timely block)

---
*Next: p2p-interface.md*
