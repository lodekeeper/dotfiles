# Lighthouse EIP-8025 Deep Dive

Source: `eth-act/lighthouse` branch `optional-proofs` (54 files changed, +3613/-393)

## Key Architectural Decisions

### 1. ExecutionProof Type (DIFFERENT from consensus spec!)
Lighthouse's `ExecutionProof` is **simpler** than the consensus spec:
```rust
struct ExecutionProof {
    proof_id: ExecutionProofId,     // u8 (0-7, maps to zkVM+EL combo)
    slot: Slot,                      // Added field (not in spec)
    block_hash: ExecutionBlockHash,  // Added field
    block_root: Hash256,            // Added field (replaces PublicInput.new_payload_request_root)
    proof_data: VariableList<u8, U1048576>,  // 1MB max (spec says 300KB)
}
```

**Missing from consensus spec**: No `validator_index`, no `BLSSignature`, no `PublicInput` container.
Lighthouse proofs are **unsigned/anonymous** — they don't require validator identity.

### 2. ExecutionProofId
- Maps to zkVM+EL combination: 0=SP1+Reth, 1=Risc0+Geth, 2=SP1+Geth, etc.
- `EXECUTION_PROOF_TYPE_COUNT = 8` max proof types
- This is their `proof_type` equivalent

### 3. min_proofs_required
- `DEFAULT_MIN_PROOFS_REQUIRED = 2`
- Node waits for proofs from K different proof_ids before considering payload available
- Configurable per node
- In proof/zkvm mode: blocks require min_proofs_required proofs
- In normal mode: proofs are optional/observed only

### 4. Data Availability Checker Integration
- Proofs integrated into the existing DA checker (alongside blobs/columns)
- `put_rpc_execution_proofs()` — store from req/resp
- `is_execution_proof_cached()` — check if proof already in cache
- `verify_execution_proof_for_gossip()` — verify zkVM proof
- Proofs cached by `block_root` and `proof_id`
- Can arrive before blocks (queued in DA checker)
- Block hash check deferred if block not yet available

### 5. Gossip Verification Pipeline
1. Future slot check
2. Past finalized slot check
3. Dedup (observed_execution_proofs by slot+block_root+proof_id)
4. DA cache check (if already cached from RPC, return PriorKnownUnpublished)
5. Proof size limits (MAX_PROOF_DATA_BYTES = 1MB)
6. **No BLS signature verification** (proofs are anonymous)
7. zkVM proof verification (expensive, delegated to DA checker)
8. Mark as observed

### 6. Req/Resp Protocols
- `ExecutionProofsByRoot` (V1) — per spec
- `ExecutionProofsByRange` (V1) — **Lighthouse extension, NOT in spec**
  - Request: `{start_slot, count}`
  - Response: stream of `ExecutionProof`
  - Used for range sync and backfill

### 7. Sync Integration
- Proofs synced alongside blocks in range sync
- `execution_proofs_by_range.rs` — range sync requests
- `execution_proofs_by_root.rs` — root-based requests
- Block-sidecar coupling extended for proofs
- Network context extended with 518 lines of proof sync logic

### 8. Store/Persistence
- Proofs persisted in hot/cold store (`hot_cold_store.rs` +377 lines)
- Schema stability tests updated
- Metadata updated for proof storage

### 9. CLI Flags
- `--activate-zkvm` — enable zkvm/proof mode
- `--target-peers=N` — standard libp2p config
- `spec.is_zkvm_enabled()` — runtime check

### 10. Dummy EL + Dummy Prover
- `dummy_el` — wraps geth, returns SYNCING for all engine calls
- `dummy-prover` binary — generates/submits dummy proofs
  - Listens for block gossip events
  - Fetches block → generates dummy proof → submits via API
  - Supports backfill for missed slots
  - `POST /eth/v1/beacon/pool/execution_proofs` endpoint

### 11. HTTP API
- `POST /eth/v1/beacon/pool/execution_proofs` — submit proof
- `GET /eth/v1/beacon/execution_proofs/{block_id}` — get proofs for block
- Pool endpoint at `/beacon/pool/` (not `/prover/` as in spec)

### 12. Kurtosis Configs
- `network_params_simple.yaml` — 2 Lighthouse+Reth nodes
- `network_params_mixed_proof_gen_verify.yaml` — 3 normal + 3 zkvm nodes
  - Normal: Lighthouse + Reth
  - ZKvm: Lighthouse + dummy_el (geth wrapper), `--activate-zkvm`
  - Fulu fork at epoch 1, 2s slots
  - Additional services: dora, prometheus_grafana

## Key Differences: Lighthouse vs Consensus Spec

| Feature | Consensus Spec | Lighthouse |
|---------|---------------|------------|
| Proof signing | BLS-signed by active validator | Unsigned/anonymous |
| validator_index | Required in SignedExecutionProof | Not present |
| PublicInput | Container with new_payload_request_root | Replaced by block_root field |
| MAX_PROOF_SIZE | 307,200 (300KB) | 1,048,576 (1MB) |
| proof_type | uint8 (ProofType) | ExecutionProofId (u8, 0-7) |
| slot field | Not in ExecutionProof | Added |
| block_hash field | Not in ExecutionProof | Added |
| Gossip topic | execution_proof | execution_proof (subnet per proof_id) |
| API endpoint | POST /eth/v1/prover/execution_proofs | POST /eth/v1/beacon/pool/execution_proofs |
| ExecutionProofsByRange | NOT in spec | Implemented |
| Min proofs required | Not specified (3-of-5 discussed) | DEFAULT_MIN_PROOFS_REQUIRED = 2 |
| Fork dependency | Built on Fulu | Fulu fork epoch |

## Prysm Interop Config (kurtosis/interop.yaml)
```yaml
# 3 proof-generating nodes (2 Prysm + 1 Lighthouse) + 1 verify-only node
# CLI flags: --activate-zkvm, --zkvm-generation-proof-types=0,1
# EL: geth for generators, dummy for verify-only
# 2s slots, dora + prometheus
```

Prysm implements: gossip validation (#6), proof generation check (#7), RPC (#9), proof service + pruning (#10), dummy EL (#11).

## Critical Insight: Spec vs Implementation Divergence

The Lighthouse implementation **diverges significantly** from the consensus spec:
- No BLS signatures on proofs
- Different SSZ types
- Additional fields (slot, block_hash, block_root)
- Extra req/resp protocol (by range)
- Different API endpoint path

This suggests the consensus spec and the actual devnet implementation may not be fully aligned yet. For interop, **match Lighthouse's implementation**, not just the spec.

## Files Changed Summary

| Area | Key Files | Lines Changed |
|------|-----------|--------------|
| Types | execution_proof.rs, execution_proof_id.rs | ~350 |
| DA Checker | data_availability_checker.rs, overflow_lru_cache.rs | ~130 |
| Gossip | execution_proof_verification.rs, gossip_methods.rs | ~450 |
| Req/Resp | methods.rs, protocol.rs, codec.rs, config.rs | ~200 |
| Sync | network_context.rs, range_sync/chain.rs, block_sidecar_coupling.rs | ~1400 |
| Store | hot_cold_store.rs, metadata.rs | ~400 |
| HTTP API | lib.rs, block_id.rs, pool.rs | ~350 |
| Tests | range.rs, lookups.rs, execution_proof_tests.rs | ~850 |
| Prover | dummy-prover.rs, start_dummy_prover.sh | ~370 |
