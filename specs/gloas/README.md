# Gloas Fork — Learning Notes

## Overview
Gloas is the next consensus-layer fork. Main feature: **EPBS (EIP-7732)** — Enshrined Proposer-Builder Separation.

## EIP-7732: Enshrined Proposer-Builder Separation

### What is PBS?
Currently, proposer-builder separation exists via MEV-Boost (out-of-protocol). EPBS brings it into the protocol itself.

**Why enshrine it?**
- Removes trust assumptions on relays
- Protocol-level guarantees for builders
- Better censorship resistance properties
- Simplifies the MEV supply chain

### Key New Concepts

#### Builder Registry
Builders become first-class beacon chain entities (like validators):
```
Builder {
  pubkey: BLSPubkey
  execution_address: ExecutionAddress
  balance: Gwei
  deposit_epoch: Epoch
  withdrawable_epoch: Epoch
}
```

- `BuilderIndex` separate from `ValidatorIndex` (uses `BUILDER_INDEX_FLAG = 2^40` bit)
- Builders have their own registry limit: `BUILDER_REGISTRY_LIMIT = 2^40`
- Withdrawal prefix: `0x03` (vs `0x01` for validators)

#### Payload Timeliness Committee (PTC)
- **Size:** 512 members (`PTC_SIZE`)
- **Purpose:** Attest to whether the payload was seen on time
- New attestation type: `PayloadAttestation`

#### Execution Payload Bidding
New containers:
- `ExecutionPayloadBid` — Builder's bid for a slot
- `SignedExecutionPayloadBid` — Signed version
- `ExecutionPayloadEnvelope` — The actual payload delivery
- `SignedExecutionPayloadEnvelope` — Signed version

#### Builder Payments
- `BuilderPendingPayment` — Tracks pending payments to proposers
- Payment threshold: 60% (`6/10`) of PTC must attest for payment
- Builders must cover their bid from their balance

### New Domains
- `DOMAIN_BEACON_BUILDER` (0x0B)
- `DOMAIN_PTC_ATTESTER` (0x0C)
- `DOMAIN_PROPOSER_PREFERENCES` (0x0D)

## Modified Beacon Block Body
Adds:
- `signed_execution_payload_bid: SignedExecutionPayloadBid`
- `payload_attestations: List[PayloadAttestation, MAX_PAYLOAD_ATTESTATIONS]`

## Fork Choice Changes (fork-choice.md)

### PayloadStatus (new type)
```
PAYLOAD_STATUS_PENDING = 0  // Waiting for payload
PAYLOAD_STATUS_EMPTY = 1    // Block without payload (builder didn't deliver)
PAYLOAD_STATUS_FULL = 2     // Block with payload delivered
```

### Key Constants
- `PAYLOAD_TIMELY_THRESHOLD = 256` (half of PTC_SIZE)

### Store Changes
- `execution_payload_states: Dict[Root, BeaconState]` — States after payload applied
- `ptc_vote: Dict[Root, Vector[boolean, PTC_SIZE]]` — PTC votes per block

### Modified LMD-GHOST
- `get_head()` now returns `ForkChoiceNode(root, payload_status)`
- `get_weight()` considers payload status when comparing branches
- New tiebreaker: `get_payload_status_tiebreaker()` for equal-weight branches
- Dual timeliness tracking: attestation deadline + PTC deadline

### Key Functions
- `is_payload_timely(root)` — True if PTC votes > 256 AND payload locally available
- `get_parent_payload_status(block)` — FULL if parent block hash matches bid
- `is_supporting_vote(node, message)` — Complex logic for vote attribution with payload status

## Builder Lifecycle (builder.md)

### Registration
1. Submit deposit with `0x03` (BUILDER_WITHDRAWAL_PREFIX) credential
2. Assigned `builder_index` in registry
3. Active after deposit epoch finalized (~2 epochs)

### Bidding Flow
1. Builder constructs `ExecutionPayloadBid` with payment value
2. Builder MUST have balance to cover bid + pending payments
3. Sign and broadcast on `execution_payload_bid` gossip topic
4. Proposer includes winning bid in `BeaconBlockBody`

### Payload Delivery
1. Builder sees block with their bid
2. Constructs `SignedExecutionPayloadEnvelope`
3. Broadcasts on `execution_payload` gossip topic
4. PTC attests to timeliness

### Economic Security
**Key insight:** "Builder pays the proposer what it promised WHETHER IT SUBMITS THE PAYLOAD OR NOT"

This is the crucial incentive — builders are economically penalized for non-delivery.

### Honest Payload Withheld
If beacon block with bid wasn't timely (not head of chain), builder may legitimately withhold payload. This prevents revealing MEV to help an orphaned block.

## Answered Questions
- ✅ How does proposer-builder handoff work? → Bid in block, payload separate
- ✅ What if builder fails? → Still pays, block becomes EMPTY
- ✅ How do builders register? → Deposit with 0x03 prefix
- ✅ Timing? → Bid broadcast for current/next slot, payload after block published

## Lodestar Implementation Status

### Already Implemented ✅
- `ExecutionPayloadBidPool` — Stores best bid per slot/parent, value-based selection
- `PayloadAttestationPool` — Aggregates PTC attestations, picks top by vote count
- `seenExecutionPayloadBids` — Dedup cache for gossip
- Validation logic for bids and envelopes
- Fork choice modifications for EPBS

### Key Implementation Details
- Bid pool indexed by: `slot -> parentBlockRoot -> parentBlockHash`
- Only highest-value bid kept per parent
- Attestation pool aggregates signatures across PTC members
- Both pools retain 2 slots (`SLOTS_RETAINED = 2`)

### Files to Study
- `chain/opPools/executionPayloadBidPool.ts`
- `chain/opPools/payloadAttestationPool.ts`
- `chain/validation/executionPayloadBid.ts`
- `chain/validation/executionPayloadEnvelope.ts`
- `fork-choice/src/forkChoice/forkChoice.ts` (EPBS changes)

### Key PRs
- **#8739** — `feat: implement epbs fork choice` (ensi321) — Core implementation
  - Multi-variant node storage (PENDING, EMPTY, FULL per block)
  - Indices changed: `Map<RootHex, number>` → `Map<RootHex, number[]>`
  - Vote tracking: epoch → slot based
  - Attestation interpretation: same-slot=PENDING, later+idx0=EMPTY, later+idx1=FULL
  - Tree traversal filters to default variants
- **#8869** — refactor getParentPayloadStatus()
- **#8838** — EPBS block production (Nico's WIP)

---
*Last updated: 2026-02-07*
