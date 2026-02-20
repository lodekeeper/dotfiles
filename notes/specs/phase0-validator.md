# Phase0 — Honest Validator Notes

**Spec:** `consensus-specs/specs/phase0/validator.md`  
**Beacon API Flow:** `beacon-APIs/validator-flow.md`  
**Status:** Read ✅  
**Date:** 2026-02-16

## Overview

Describes expected behavior of an "honest validator" — the two primary duties (proposing blocks and attesting) plus aggregation, slashing avoidance, and security best practices.

## Timing (Phase0)

| Duty | Deadline | Notes |
|------|----------|-------|
| Block proposal | Slot start (0%) | Immediately at slot start |
| Attestation | `ATTESTATION_DUE_BPS = 3333` (~33%) | ~4s into 12s slot |
| Aggregation | `AGGREGATE_DUE_BPS = 6667` (~67%) | ~8s into 12s slot |

**Slot timeline (12s):**
```
0s          4s          8s          12s
|           |           |           |
Propose     Attest      Aggregate   Slot end
(0%)        (33%)       (67%)
```

## Becoming a Validator

1. **Generate keys:** BLS keypair (hot key for signing) + withdrawal credentials
2. **Submit deposit:** 32 ETH to deposit contract on execution layer
3. **Wait for inclusion:** ETH1_FOLLOW_DISTANCE (~8h) + voting period (~6.8h) minimum
4. **Activation queue:** Processed into state, then queued with `MAX_SEED_LOOKAHEAD` delay (25.6 min)
5. **Active:** Assigned duties, earns rewards/penalties

### Withdrawal Credentials
- `0x00` prefix: BLS withdrawal key (cold storage)
- `0x01` prefix: ETH1 address (direct withdrawals to EOA/contract)

## Validator Assignments

### Committee Assignment
`get_committee_assignment(state, epoch, validator_index)` returns:
- `committee` (validator indices), `index` (committee index), `slot`
- Stable for 1 epoch lookahead (call at epoch start for next epoch)

### Proposer Check
`is_proposer(state, validator_index)` — only stable within the current epoch, must check per-slot.

### Lookahead Workflow
At each epoch start:
1. Get committee assignment for `next_epoch`
2. Calculate subnet: `compute_subnet_for_attestation(committees_per_slot, slot, committee_index)`
3. Find peers on `beacon_attestation_{subnet_id}`
4. If aggregator for that slot, subscribe to the topic

## Block Proposal

### Sequence
1. Run fork choice → get `head_root = get_head(store)`
2. Optionally compute `parent_root = get_proposer_head(store, head_root, slot)` for reorgs
3. Construct `BeaconBlock` with parent, slot, proposer_index
4. Fill `BeaconBlockBody`: RANDAO, eth1_data, operations (slashings, attestations, deposits, exits)
5. Compute `state_root` by running state transition on unsigned block
6. Sign the complete block → `SignedBeaconBlock`
7. Broadcast

### Eth1 Data Voting (`get_eth1_vote`)
- Candidate blocks: eth1 blocks in range `[period_start - 2*follow, period_start - follow]`
- Vote for most popular `eth1_data` among valid votes, tiebreak by earliest appearance
- Default to latest candidate if no votes match

### Operation Ordering Constraint
Slashings processed before exits — including both in same block could invalidate the exit. Implementations must handle this.

## Attesting

### Attestation Data Construction
- `slot` = assigned attestation slot
- `index` = committee index
- `beacon_block_root` = LMD-GHOST head (fork choice result)
- `source` = `head_state.current_justified_checkpoint` (FFG source)
- `target` = `Checkpoint(epoch=current_epoch, root=epoch_boundary_block_root)` (FFG target)

### Broadcast
- Wait for block OR `ATTESTATION_DUE_BPS` (whichever first)
- Set single bit in `aggregation_bits` at validator's position in committee
- Sign with `DOMAIN_BEACON_ATTESTER` at `target.epoch`
- Broadcast to `beacon_attestation_{subnet_id}`

## Attestation Aggregation

### Selection (`is_aggregator`)
```
modulo = max(1, len(committee) // TARGET_AGGREGATORS_PER_COMMITTEE)
selected = bytes_to_uint64(hash(slot_signature)[:8]) % modulo == 0
```
- `TARGET_AGGREGATORS_PER_COMMITTEE = 16` — aims for ~16 aggregators per committee
- Selection proof: BLS signature of `slot` with `DOMAIN_SELECTION_PROOF`

### Aggregation Workflow
1. Determine if aggregator via `is_aggregator()`
2. Collect matching attestations from gossip during the slot
3. Merge `aggregation_bits` (OR them together)
4. Aggregate BLS signatures
5. Wrap in `AggregateAndProof` with `selection_proof`
6. Sign the whole thing → `SignedAggregateAndProof`
7. Broadcast to `beacon_aggregate_and_proof` at `AGGREGATE_DUE_BPS`

### Three Signatures Involved
1. **Selection proof:** Proves aggregator status (signed slot)
2. **Aggregate signature:** Combined attestation signatures
3. **Outer signature:** Signs the `AggregateAndProof` container

## Slashing Avoidance

### Proposer Slashing
- **Rule:** Never sign two different blocks for the same slot
- **Protection:** Write to disk BEFORE signing/broadcasting

### Attester Slashing
- **Double vote:** Same target epoch, different attestation data
- **Surround vote:** Attestation A's source/target "surrounds" attestation B's
- **Protection:** Record source+target epoch to disk BEFORE signing

### Best Practices
1. **Private key isolation** — VC treats BN as untrusted
2. **Local slashing DB** — check before every signature
3. **Import history on recovery** — EIP-3076 interchange format
4. **Reject far-future requests** — >6h gap from last signed epoch should require manual override (prevents locking validator out for extended period)

## Beacon API Flow (from `validator-flow.md`)

### Block Proposing (API)
1. Epoch start: `GET /eth/v1/validator/duties/proposer/{epoch}`
2. At slot: `GET /eth/v3/validator/blocks/{slot}` (produceBlockV3)
3. Sign block
4. `POST /eth/v2/beacon/blocks` (publishBlock)

### Attesting (API)
1. Epoch start: `GET /eth/v1/validator/duties/attester/{epoch}` for epoch+1
2. Check aggregator, call `POST /eth/v1/validator/beacon_committee_subscriptions`
3. Wait for block or deadline
4. `GET /eth/v1/validator/attestation_data?slot=X&committee_index=Y`
5. `POST /eth/v1/beacon/pool/attestations`
6. If aggregator: wait for aggregate deadline
   - `GET /eth/v1/validator/aggregate_attestation`
   - `POST /eth/v1/validator/aggregate_and_proofs`

### PTC Attesting (Gloas — from API flow)
1. Epoch start: `GET /eth/v1/validator/duties/ptc/{epoch}` for epoch+1
2. Wait for execution payload or `PAYLOAD_ATTESTATION_DUE_BPS`
3. `GET /eth/v1/validator/payload_attestation_data?slot=X`
4. Sign → `POST /eth/v1/beacon/pool/payload_attestation_messages`

## Design Observations

1. **Three-phase slot timing** (propose → attest → aggregate) is fundamental to the protocol's liveness. Each phase builds on the previous.

2. **Aggregation is probabilistic** — `TARGET_AGGREGATORS_PER_COMMITTEE = 16` means ~16 validators per committee aggregate, providing redundancy without flooding the network.

3. **Write-before-sign** for slashing protection is a strict ordering requirement. Violating this (e.g., crash between sign and write) could lead to slashable behavior on restart.

4. **VC-BN trust boundary** — the spec explicitly states the VC should treat the BN as untrusted. This is reflected in Lodestar's architecture with separate validator package.

5. **Eth1 voting mechanism** — a simple majority vote among proposers over a ~6.8h window. This is the bridge between execution and consensus layers (replaced by engine API post-merge, but the voting structure informed the design).

---
*Phase0 validator complete. Next: Phase0 weak-subjectivity*
