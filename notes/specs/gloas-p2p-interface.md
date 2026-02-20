# Gloas/EPBS — P2P Networking Spec Notes

*Source: `consensus-specs/specs/gloas/p2p-interface.md`*
*Studied: 2026-02-15*

## New Gossip Topics

| Topic | Message Type | Purpose |
|-------|-------------|---------|
| `execution_payload_bid` | `SignedExecutionPayloadBid` | Builder bids |
| `execution_payload` | `SignedExecutionPayloadEnvelope` | Execution payloads |
| `payload_attestation_message` | `PayloadAttestationMessage` | PTC attestations |
| `proposer_preferences` | `SignedProposerPreferences` | Proposer fee_recipient + gas_limit |

## New Containers

### ProposerPreferences
- `proposal_slot`, `validator_index`, `fee_recipient`, `gas_limit`
- Signed by proposer, broadcast in advance (next epoch)
- Builders must match `fee_recipient` and `gas_limit` in their bids

### DataColumnSidecar (Modified)
- **Removed**: `signed_block_header`, `kzg_commitments`, `kzg_commitments_inclusion_proof`
- **Added**: `slot`, `beacon_block_root`
- KZG commitments now from `block.body.signed_execution_payload_bid.message.blob_kzg_commitments`
- Verification functions take `kzg_commitments` as separate parameter

## Gossip Validation Rules

### `beacon_block`
- Removed all `execution_payload` validations
- Added: KZG commitment length check on `bid.blob_kzg_commitments`
- Added: `bid.parent_block_root == block.parent_root`
- Added: EL verification of `bid.parent_block_hash` (if available)

### `execution_payload`
- IGNORE: block root must be known (can queue)
- IGNORE: first valid envelope from this builder for this block
- IGNORE: slot >= finalized slot
- REJECT: block passes validation
- REJECT: slot, builder_index, block_hash match bid
- REJECT: valid signature

### `payload_attestation_message`
- IGNORE: current slot (with clock disparity)
- IGNORE: first valid message from this validator
- IGNORE: block root known (can queue)
- REJECT: validator in PTC for the slot
- REJECT: valid signature

### `execution_payload_bid`
- IGNORE: current or next slot
- IGNORE: proposer preferences seen for this slot
- REJECT: active builder, zero execution_payment, matching fee_recipient/gas_limit
- IGNORE: first valid bid from builder, highest value bid
- IGNORE: builder can cover bid
- REJECT: valid signature
- **DoS note**: Implementations should prevent bid spam (min increment threshold or interval-based forwarding)

### `proposer_preferences`
- IGNORE: proposal_slot in next epoch
- REJECT: validator is proposer for that slot (via `proposer_lookahead`)
- IGNORE: first valid message from this validator for this slot
- REJECT: valid signature

### Attestation Changes
- `data.index` now 0 or 1 (was always 0 before)
- Same-slot attestations: `data.index == 0` required
- Cross-slot: `data.index` can be 0 (empty) or 1 (full) → signals payload availability

### `data_column_sidecar_{subnet_id}`
- IGNORE: valid block for slot seen (queue if not)
- REJECT: sidecar slot matches block slot
- REJECT: sidecar valid via `verify_data_column_sidecar(sidecar, bid.blob_kzg_commitments)`
- REJECT: correct subnet
- REJECT: KZG proofs valid
- IGNORE: first sidecar for (root, index) with valid proof

## New Req/Resp Methods

### ExecutionPayloadEnvelopesByRange v1
- Protocol: `/eth2/beacon_chain/req/execution_payload_envelopes_by_range/1/`
- Request: `(start_slot, count)`
- Response: `List[SignedExecutionPayloadEnvelope, MAX_REQUEST_BLOCKS_DENEB]`
- Only for Gloas fork

### ExecutionPayloadEnvelopesByRoot v1
- Protocol: `/eth2/beacon_chain/req/execution_payload_envelopes_by_root/1/`
- Request: `List[Root, MAX_REQUEST_PAYLOADS]` (beacon block roots)
- Response: `List[SignedExecutionPayloadEnvelope, MAX_REQUEST_PAYLOADS]`
- MAX_REQUEST_PAYLOADS = 128
- Used to recover payloads (e.g., PTC voted present but payload not received)
- Must support since latest finalized epoch

### BeaconBlocksByRange/Root v2
- Updated fork version table to include `GLOAS_FORK_VERSION` → `gloas.SignedBeaconBlock`

## Key Implementation Notes
- Blocks and payloads are separate gossip topics → need separate sync pipelines
- Envelope verification references the bid from the block → block must be known first
- Data column sidecars now verified against bid's commitments (not block body)
- Proposer preferences are a new coordination mechanism between proposers and builders
- Bid spam is a concern → implementations need DoS mitigation

## Things to Check in Lodestar
- [ ] New gossip topic handlers (4 new topics)
- [ ] Gossip validation for each topic
- [ ] ProposerPreferences gossip + storage
- [ ] Bid validation: fee_recipient/gas_limit must match proposer preferences
- [ ] ExecutionPayloadEnvelopesByRange/Root req/resp handlers
- [ ] DataColumnSidecar verification with external kzg_commitments parameter
- [ ] Attestation data.index validation on gossip (0 or 1)
- [ ] Separate sync pipelines for blocks and payloads

---
*Next: validator.md*
