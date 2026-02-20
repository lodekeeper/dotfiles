# Phase0 — P2P Networking Notes

**Spec:** `consensus-specs/specs/phase0/p2p-interface.md`  
**Status:** Read ✅  
**Date:** 2026-02-16

## Overview

Defines the complete networking stack for beacon chain clients: transport, gossip, request/response, and discovery. Three interaction domains: gossipsub (pub/sub), req/resp (point-to-point), and discv5 (peer discovery).

## Network Fundamentals

### Transport Stack
- **Transport:** TCP required, QUIC optional (UDP)
- **Encryption:** libp2p-noise with secp256k1 identities, XX handshake pattern
- **Multiplexing:** mplex required, yamux optional (yamux preferred when both supported)
- **Protocol negotiation:** multistream-select 1.0 required

### Key Config Values
| Parameter | Value | Notes |
|-----------|-------|-------|
| `MAX_PAYLOAD_SIZE` | 10 MiB | Max uncompressed gossip/RPC payload |
| `MAX_REQUEST_BLOCKS` | 1024 | Max blocks per range request |
| `ATTESTATION_PROPAGATION_SLOT_RANGE` | 32 | How long attestations can propagate |
| `MAXIMUM_GOSSIP_CLOCK_DISPARITY` | 500ms | Clock skew tolerance |
| `SUBNETS_PER_NODE` | 2 | Long-lived subnet subscriptions |
| `ATTESTATION_SUBNET_COUNT` | 64 | Number of attestation subnets |
| `MAX_CONCURRENT_REQUESTS` | 2 | Per protocol ID per peer |
| `MIN_EPOCHS_FOR_BLOCK_REQUESTS` | 33,024 (~5 months) | Block serving range |
| `EPOCHS_PER_SUBNET_SUBSCRIPTION` | 256 (~27h) | Subnet rotation period |

## Gossipsub Domain

### Protocol
- gossipsub v1.0 + v1.1 extensions
- Protocol ID: `/meshsub/1.1.0`
- Mesh parameters: D=8, D_low=6, D_high=12, D_lazy=6
- Heartbeat: 0.7s
- Message cache: 6 windows retained, 3 gossipped
- Seen cache TTL: 2 epochs
- Signature policy: `StrictNoSign` (no author, no seqno)

### Topic Format
`/eth2/{ForkDigestHex}/{Name}/ssz_snappy`
- Fork digest provides chain/fork isolation
- SSZ encoding + Snappy block compression

### Message ID
```
if valid_snappy_decompress(data):
  SHA256(DOMAIN_VALID_SNAPPY + decompress(data))[:20]
else:
  SHA256(DOMAIN_INVALID_SNAPPY + data)[:20]
```
This handles: (1) multiple compressed forms of same data, (2) invalid snappy data.

### Global Topics

#### `beacon_block`
- Full `SignedBeaconBlock`
- Key validations: not future slot, first valid block from proposer for slot, valid signature, parent seen, correct proposer for shuffling, descendant of finalized

#### `beacon_aggregate_and_proof`  
- `SignedAggregateAndProof` (aggregated attestations)
- Key validations: correct committee index, within propagation range, has participants, valid aggregator selection proof, aggregator in committee, all signatures valid, LMD consistent with FFG target

#### `voluntary_exit` / `proposer_slashing` / `attester_slashing`
- Full objects, first-seen-per-validator dedup
- Must pass full `process_*` validation

### Attestation Subnets (`beacon_attestation_{subnet_id}`)
- 64 subnets for unaggregated attestations
- Mapped via `compute_subnet_for_attestation(committees_per_slot, slot, index)`
- Key validations: correct subnet, unaggregated (exactly 1 bit set), correct committee size, one attestation per validator per target epoch, valid signature

### Validation Actions
- **REJECT:** Message is invalid, penalize sender
- **IGNORE:** Message not invalid but not useful (duplicate, future, etc.)
- **ACCEPT:** Forward to mesh

## Req/Resp Domain

### Protocol ID Format
`/eth2/beacon_chain/req/{MessageName}/{Version}/{Encoding}`

### Stream Model
- One stream per request/response interaction
- Request → half-close → response chunks → full close
- Response chunks: `result_byte | header | payload`
- Result codes: 0=Success, 1=InvalidRequest, 2=ServerError, 3=ResourceUnavailable

### Encoding: SSZ-Snappy
- SSZ serialization → Snappy frames compression
- Length-prefixed with protobuf varint (raw SSZ length)
- List responses send each item as separate response_chunk

### Messages

#### Status (v1)
```
fork_digest, finalized_root, finalized_epoch, head_root, head_slot
```
- **Handshake protocol** — must send upon connection
- Disconnect if: fork_digest mismatch, or finalized checkpoint inconsistent
- Lower-synced peer should initiate BlocksByRange

#### Goodbye (v1)
- Single uint64 reason code (1=shutdown, 2=irrelevant network, 3=fault)

#### BeaconBlocksByRange (v1)
- Request: `start_slot, count, step` (step deprecated, must be 1)
- Response: `List[SignedBeaconBlock]` — blocks in range, skipping empty slots
- Must serve at least `MIN_EPOCHS_FOR_BLOCK_REQUESTS` epoch range
- Blocks must be from consistent fork choice chain
- **v1 deprecated** — may respond empty during transition

#### BeaconBlocksByRoot (v1)
- Request: `List[Root]` — block roots to fetch
- Response: matching `SignedBeaconBlock`s
- Primarily for recovering recent blocks (unknown parent)
- **v1 deprecated** — may respond empty during transition

#### Ping (v1)
- Exchange MetaData sequence numbers
- Triggers GetMetaData if remote seq > local record

#### GetMetaData (v1)
- No request body, returns full `MetaData` (seq_number, attnets)

## Discovery Domain (discv5)

### Protocol
- Discovery v5.1 on dedicated UDP port
- Integrated into libp2p via adaptor (service discovery + peer routing)

### ENR Structure
Required:
- `secp256k1` compressed pubkey (33 bytes)

Optional:
- `ip`/`ip6` — addresses
- `tcp`/`tcp6` — libp2p TCP ports
- `quic`/`quic6` — libp2p QUIC ports
- `udp`/`udp6` — discv5 ports
- `attnets` — attestation subnet bitfield (Bitvector[64])
- `eth2` — ENRForkID (fork_digest + next_fork_version + next_fork_epoch)

### Attestation Subnet Subscription
Each node:
- Subscribes to `SUBNETS_PER_NODE` (2) subnets for `EPOCHS_PER_SUBNET_SUBSCRIPTION` (256) epochs
- Subnet selection based on `node_id` via `compute_subscribed_subnet`
- Uses shuffled prefix of node_id, rotated every ~27 hours
- Provides stable backbone for attestation propagation

## Size Limits

### Gossip
- RPCMsg frame: ≤ `max_message_size()` (≈ max_compressed_len(10MB) + 1024)
- Compressed payload: ≤ `max_compressed_len(MAX_PAYLOAD_SIZE)`
- Uncompressed payload: ≤ `MAX_PAYLOAD_SIZE` or type-specific SSZ bound (whichever lower)

### Snappy Compression
- `max_compressed_len(n) = 32 + n + n/6` (worst case)
- Gossip uses block compression; req/resp uses frame compression

## Design Observations

1. **One stream per interaction** in req/resp — simple but potentially high connection overhead. Multiplexing (mplex/yamux) amortizes this over a single TCP connection.

2. **64 attestation subnets** spread load across the network. Each node only subscribes to 2 long-lived + duty-specific subnets, not all 64.

3. **ATTESTATION_PROPAGATION_SLOT_RANGE = 32** (one epoch) — attestations don't propagate beyond one epoch, matching the epoch-based reward system.

4. **`MIN_EPOCHS_FOR_BLOCK_REQUESTS` ≈ 5 months** — substantial block serving requirement. Nodes bootstrapping from weak subjectivity must backfill to this range.

5. **Fork digest in topics** — automatic network partitioning across forks. Clients on different forks simply don't receive each other's messages.

6. **StrictNoSign policy** — gossip messages have no libp2p-level signatures (the application layer handles signing). This saves bandwidth and avoids redundant signature verification.

7. **`MAX_CONCURRENT_REQUESTS = 2`** per protocol per peer — prevents request flooding while allowing parallel sync operations.

---
*Next: Phase0 validator spec, then weak-subjectivity*
