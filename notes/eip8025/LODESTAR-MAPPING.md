# EIP-8025 — Lodestar Implementation Mapping

Maps consensus spec changes to specific Lodestar packages and files.

## 1. `@lodestar/params` — Constants (NO NEW FORK)

**CRITICAL: Lighthouse/Prysm do NOT add a new fork. Use runtime `--activate-zkvm` flag.**

### Files to modify:
- `packages/params/src/index.ts` — Export new constants

### New constants:
```typescript
MAX_PROOF_DATA_BYTES = 1_048_576  // 1MB (matching Lighthouse devnet)
EXECUTION_PROOF_TYPE_COUNT = 8
DEFAULT_MIN_PROOFS_REQUIRED = 2
```

## 2. `@lodestar/types` — SSZ Types

### New directory: `packages/types/src/eip8025/`
- `sszTypes.ts` — SSZ type definitions
- `types.ts` — TypeScript interfaces
- `index.ts` — Exports

### New SSZ types:
```typescript
PublicInput = new ContainerType({
  newPayloadRequestRoot: Root,
})

ExecutionProof = new ContainerType({
  proofData: new ByteListType(MAX_PROOF_SIZE),
  proofType: UintNum64,  // ProofType = uint8
  publicInput: PublicInput,
})

SignedExecutionProof = new ContainerType({
  message: ExecutionProof,
  validatorIndex: UintNum64,
  signature: BLSSignature,
})

NewPayloadRequestHeader = {
  executionPayloadHeader: ExecutionPayloadHeader,
  versionedHashes: VersionedHash[],
  parentBeaconBlockRoot: Root,
  executionRequests: ExecutionRequests,
}
```

### Modified:
- `packages/types/src/allForks/` — Add eip8025 to fork union types

## 3. `@lodestar/state-transition` — State Transition

### Files to modify:
- `packages/state-transition/src/slot/upgradeState.ts` — Add `upgradeStateToEip8025()`
- `packages/state-transition/src/block/processExecutionPayload.ts` — Add ProofEngine parameter

### New files:
- `packages/state-transition/src/block/processExecutionProof.ts`

### Key changes:
- `processExecutionPayload()` signature adds `proofEngine` parameter
- ProofEngine.verifyNewPayloadRequestHeader() called after EL verification
- `processExecutionProof()` — verify BLS sig, verify via ProofEngine
- State upgrade: Fulu/Gloas → EIP8025 (new fork version, same state fields)

## 4. `@lodestar/beacon-node` — Core Changes

### 4a. Chain (`packages/beacon-node/src/chain/`)

**New files:**
- `chain/executionProof/index.ts` — Proof management
- `chain/executionProof/verification.ts` — Proof verification logic
- `chain/executionProof/observed.ts` — Track seen proofs (dedup by request_root + proof_type)

**Modified files:**
- `chain/blocks/blockInput/blockInput.ts` — Add proof data to BlockInput
- `chain/blocks/verifyBlocksDataAvailability.ts` — Add proof availability check
- `chain/blocks/importBlock.ts` — Check proof availability before import
- `chain/forkChoice/` — Block not importable until proofs received

### 4b. Network (`packages/beacon-node/src/network/`)

**Gossip (new):**
- `network/gossip/interface.ts` — Add `GossipType.execution_proof`
- `network/gossip/topic.ts` — Topic string for execution_proof
- `network/gossip/gossipsub.ts` — Subscribe to execution_proof topic
- `network/processor/` — Add gossip validation for execution_proof

**ReqResp (new):**
- `network/reqresp/handlers/executionProofsByRoot.ts` — New handler
- `network/reqresp/protocols.ts` — Add ExecutionProofsByRoot protocol
- `network/reqresp/types.ts` — Add method enum entry

**Metadata:**
- `network/metadata.ts` — MetaData v4 with `executionProofAware` field
- `network/reqresp/protocols.ts` — Add Metadata v4 protocol

**ENR:**
- Wherever ENR is configured — add `eproof` field

**Peer management:**
- Filter/discover proof-aware peers

### 4c. Execution (`packages/beacon-node/src/execution/`)

**New directory:** `packages/beacon-node/src/execution/proofEngine/`
- `interface.ts` — ProofEngine interface
- `dummy.ts` — Dummy implementation (always returns true, for testing)
- `index.ts` — Exports

### 4d. API (`packages/beacon-node/src/api/`)

**New:**
- `api/impl/prover/` — Prover API implementation
- Route: `POST /eth/v1/prover/execution_proofs`

### 4e. Sync (`packages/beacon-node/src/sync/`)

**Modified:**
- Sync logic to fetch proofs alongside blocks (similar to blob sync)
- Proof retention until finalization (~2 epochs)

## 5. `@lodestar/api` — API Types

### New:
- `packages/api/src/prover/` — Prover API route definitions
- Or extend `packages/api/src/beacon/routes/` with prover endpoints

## 6. `@lodestar/validator` — Validator Client

### New (optional, for prover mode):
- Prover logic if validator opts in
- Connect to ProofEngine for proof generation
- Sign and broadcast proofs

## 7. CLI

### Modified:
- `packages/cli/src/options/` — New flags:
  - `--enable-zkvm` / `--stateless-mode` — Enable stateless validation
  - `--proof-engine-url` — URL of external proof engine
  - `--prover` — Enable prover mode

## Complexity Estimate

| Area | New Files | Modified Files | Complexity |
|------|-----------|----------------|------------|
| params | 0 | 4 | Low |
| types | 3 | 5 | Medium |
| state-transition | 1 | 3 | Medium |
| chain | 3 | 5 | High |
| network/gossip | 0 | 5 | High |
| network/reqresp | 1 | 3 | Medium |
| network/metadata | 0 | 2 | Low |
| execution/proofEngine | 3 | 0 | Medium |
| api | 2 | 1 | Medium |
| sync | 0 | 3 | High |
| validator | 1 | 1 | Medium |
| cli | 0 | 2 | Low |

**Total: ~14 new files, ~34 modified files**

## Implementation Order (suggested)

1. **Phase 1: Foundation** — params, types, fork config
2. **Phase 2: State Transition** — process_execution_payload mod, process_execution_proof, upgrade
3. **Phase 3: ProofEngine** — interface, dummy impl
4. **Phase 4: Networking** — gossip topic, req/resp, metadata, ENR
5. **Phase 5: Chain** — proof availability, fork choice, block import
6. **Phase 6: API** — prover endpoint
7. **Phase 7: Sync** — proof syncing
8. **Phase 8: CLI** — flags and configuration
9. **Phase 9: Testing** — unit tests, Kurtosis devnet interop

## Lighthouse Reference Files → Lodestar Mapping

| Lighthouse File | Lodestar Equivalent |
|-----------------|---------------------|
| `execution_proof_verification.rs` | `chain/executionProof/verification.ts` |
| `observed_execution_proofs.rs` | `chain/executionProof/observed.ts` |
| `data_availability_checker.rs` | `chain/blocks/verifyBlocksDataAvailability.ts` |
| `canonical_head.rs` | `chain/forkChoice/` |
| `beacon_chain.rs` | `chain/chain.ts` |
| `builder.rs` | `chain/factory/` |
| `client/config.rs` | CLI options |
| `discovery/enr.rs` | `network/discv5/` ENR config |
| `peer_manager/peerdb/peer_info.rs` | `network/peers/` |
| `rpc/codec.rs` | `@lodestar/reqresp` |
| `rpc/methods.rs` | `network/reqresp/types.ts` |
| `rpc/protocol.rs` | `network/reqresp/protocols.ts` |
