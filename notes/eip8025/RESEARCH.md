# EIP-8025: Optional Execution Proofs — Research Notes

## Overview
EIP-8025 enables beacon nodes to verify execution payload validity without running an EL client, using ZK proofs instead of re-execution. This is a CL-only change, backwards compatible, no hardfork required.

**Authors:** Kevaundray Wedderburn (@kevaundray), Justin Drake
**Status:** Draft (consensus-specs merged as `_features/eip8025`)
**EIP:** https://eips.ethereum.org/EIPS/eip-8025
**Spec PR:** ethereum/consensus-specs#4591 (merged)
**Refactor PR:** ethereum/consensus-specs#4828 (Gloas rebase)

## Key Concepts

### Architecture
- **Provers**: Active validators who generate ZK proofs of execution payload validity (resource-intensive, needs GPUs)
- **Verifiers/Attesters**: Nodes that verify proofs instead of re-executing (lightweight verification)
- **ProofEngine**: Abstraction layer for proof verification (implementation-dependent)
- **Dummy EL**: Since proofs replace execution, a `dummy` EL client can be used instead of geth/reth etc.

### New Modes
1. **zkEVM Proof generating** — Prover mode, generates proofs
2. **Stateless validation** — Verifier mode, validates via proofs instead of EL

### Trade-offs
- Provers do MORE work (GPU-intensive proof generation)
- Attesters do LESS work (lightweight proof verification)
- Gas limit changes affect provers, not attesters

## Consensus Spec Files
All at `consensus-specs/specs/_features/eip8025/`:

### 1. beacon-chain.md
- **New Types:** `ProofType` (uint8)
- **Constants:** `MAX_PROOF_SIZE` = 307200 (300KiB), `DOMAIN_EXECUTION_PROOF` = 0x0D000000
- **New Containers:**
  - `PublicInput { new_payload_request_root: Root }`
  - `ExecutionProof { proof_data: ByteList[MAX_PROOF_SIZE], proof_type: ProofType, public_input: PublicInput }`
  - `SignedExecutionProof { message: ExecutionProof, validator_index: ValidatorIndex, signature: BLSSignature }`
- **Modified `process_block`:** Passes `PROOF_ENGINE` to `process_execution_payload`
- **New `NewPayloadRequestHeader`:** Lighter version with `execution_payload_header` instead of full payload
- **Modified `process_execution_payload`:** 
  - Still calls `execution_engine.verify_and_notify_new_payload()` (for non-stateless nodes)
  - NEW: Also calls `proof_engine.verify_new_payload_request_header()` (for stateless nodes)
- **New `process_execution_proof`:** Verifies signed proof from active validator

### 2. proof-engine.md
- **ProofEngine interface:**
  - `verify_execution_proof(proof)` → bool
  - `verify_new_payload_request_header(header)` → bool
  - `request_proofs(new_payload_request, proof_attributes)` → ProofGenId
- **ProofAttributes:** `{ proof_types: Sequence[ProofType] }`
- Implementation-dependent (could be Engine API-based or internal)

### 3. p2p-interface.md
- **Constants:** `MAX_EXECUTION_PROOFS_PER_PAYLOAD` = 4
- **Fork version:** `EIP8025_FORK_VERSION` = 0xe8025000
- **MetaData v4:** New field `execution_proof_aware: bool` (key: `eproof`)
- **Gossip topic:** `execution_proof` — propagates `SignedExecutionProof`
  - Validation rules: ignore duplicates per (request_root, proof_type), reject invalid signatures
- **Req/Resp:** `ExecutionProofsByRoot` (`/eth2/beacon_chain/req/execution_proofs_by_root/1/`)
  - Request: `{ block_root: Root }`
  - Response: `List[SignedExecutionProof, MAX_EXECUTION_PROOFS_PER_PAYLOAD]`
- **ENR:** New `eproof` key (uint8, non-zero = aware)
- **GetMetaData v4:** Extended with `execution_proof_aware`

### 4. fork.md
- Fork version: `0xe8025000`, epoch TBD
- `upgrade_to_eip8025(pre: fulu.BeaconState) → BeaconState` — straightforward copy with updated fork version
- State is identical to Fulu (no new state fields)

### 5. prover.md
- Provers are active validators, voluntary, no protocol compensation
- Steps: extract NewPayloadRequest → create ProofAttributes → call proof_engine.request_proofs() → receive async proofs via Beacon API → sign → broadcast
- **Beacon API endpoint:** `POST /eth/v1/prover/execution_proofs` (for proof delivery)
- **Prover relay:** Trusted intermediary that accepts unsigned proofs and signs them

## Other Client Implementations

### Lighthouse (most advanced)
- **Repo:** eth-act/lighthouse branch `optional-proofs`
- **Main PR:** sigp/lighthouse#8316 (full implementation with sync)
- **Earlier PR:** sigp/lighthouse#7755
- **Tracking issue:** sigp/lighthouse#8327
- **Key flags:** `--activate-zkvm`
- **Docker image:** `ethpandaops/lighthouse:eth-act-optional-proofs`

### Teku
- **Branch:** `optional-proofs` on Consensys/teku
- **Only 1 commit:** PR #10097 — execution proof availability checker (Nov 2025, gfukushima)
- Early stage

### Nimbus
- **Branch:** `optional-proofs` on status-im/nimbus-eth2
- Need to investigate depth

### Prysm
- **Branch:** `poc/optional-proofs` on developeruche/prysm (fork)
- POC stage

## Kurtosis Devnet Config
From ethpandaops/ethereum-package `.github/tests/ews.yaml`:
```yaml
participants:
  - count: 3
  - el_type: dummy
    cl_type: lighthouse
    cl_image: ethpandaops/lighthouse:eth-act-optional-proofs
    cl_extra_params:
      - --activate-zkvm

additional_services:
  - ews
  - dora
mev_type: flashbots
```

Key observations:
- Uses `dummy` EL (no real execution engine)
- `ews` = Execution Witness Service (proof generation service)
- `dora` = block explorer for monitoring
- Lighthouse with `--activate-zkvm` flag

## Lodestar Context
- **Existing branch:** `fork/optional-proofs` — VERY OLD (v1.38.0 era), essentially same as unstable from months ago
- **Need:** Fresh branch from current `unstable`
- **Target:** PR against `optional-proofs` branch on ChainSafe/lodestar
- **Built on:** Fulu fork

## Implementation Plan (High-Level)

### 1. Fork/Types
- New fork config (EIP8025_FORK_VERSION, EIP8025_FORK_EPOCH)
- New SSZ types (PublicInput, ExecutionProof, SignedExecutionProof)
- State upgrade function
- Fork choice modifications

### 2. State Transition
- Modified process_execution_payload with ProofEngine
- New process_execution_proof
- NewPayloadRequestHeader type

### 3. Networking
- New gossip topic: execution_proof
- New req/resp: ExecutionProofsByRoot
- MetaData v4 with execution_proof_aware
- ENR eproof field

### 4. ProofEngine Interface
- Abstract proof verification
- Integration with external proof engines via API

### 5. Prover Logic
- Beacon API: POST /eth/v1/prover/execution_proofs
- Proof signing and broadcasting
- Prover relay support

### 6. CLI
- Flag to enable zkVM/stateless mode
- Flag to enable prover mode
- Configuration for proof engine endpoint

### 7. Testing
- Kurtosis devnet with dummy EL + Lighthouse interop
- Multi-client combinations
- Assertor for chain health verification
- Proof generation, propagation, and verification testing

## Open Questions
1. What is the `ews` service exactly? Need to find its repo/config
2. Does the ethereum-package support Lodestar for optional-proofs yet?
3. What specific Beacon API changes are needed beyond POST /eth/v1/prover/execution_proofs?
4. How does fork choice handle proof availability? (blocks not imported until proofs received)
5. How is the ProofEngine actually implemented in Lighthouse? (dummy verifier for testing?)

## References from Nico (2026-02-16)

### Kurtosis Config: ethpandaops/ethereum-package#1311
- Adds `prover_type` and `prover_image` per participant
- Dummy prover: https://github.com/nalepae/dummy-prover
- Example config: geth+prysm, `prover_type: dummy`, `prover_image: dummy-prover:latest`
- `fulu_fork_epoch: 0`, `seconds_per_slot: 4`, `preset: mainnet`

### Frisitano Presentation (L1-zkEVM Breakout #01)
https://frisitano.github.io/slides/presentations/optional-proofs/index.html

**Spec-level data types** (differ from Lighthouse devnet wire format):
- `ExecutionProof { proof_data: ByteList, proof_type: uint8, public_input: PublicInput }`
- `PublicInput { new_payload_request_root: Root }`
- `SignedExecutionProof { message: ExecutionProof, validator_index: ValidatorIndex, signature: BLSSignature }`
- `NewPayloadRequest { execution_payload, versioned_hashes, parent_beacon_block_root, execution_requests }`
- `NewPayloadRequestHeader { execution_payload_header, versioned_hashes, parent_beacon_block_root, execution_requests }`

**Proof Engine interface:**
- `verify_execution_proof(proof) -> bool`
- `notify_new_payload_header(header)` — cache in forkchoice store
- `request_proofs(new_payload_request, proof_attributes) -> ProofGenId`

**Flows:**
1. Process Block: BN receives block → extract NewPayloadRequestHeader → notify_new_payload_header() → import optimistically
2. Process Execution Proof: gossip → verify BLS sig → verify_execution_proof → mark valid in forkchoice → re-broadcast
3. Request Proofs: validator observes block → request_proofs() → async → POST /eth/v1/validator/execution_proofs → sign → broadcast on execution_proof topic

**Gossip:** execution_proof topic, ban peers/validators sending invalid proofs

**Key insight:** Spec uses SignedExecutionProof (with BLS + validator_index), but Lighthouse devnet uses unsigned format with extra fields (slot, block_hash, block_root). Our implementation targets devnet format first.

**References from slides:**
- Specs: https://github.com/ethereum/consensus-specs/tree/master/specs/_features/eip8025
- Lighthouse: https://github.com/eth-act/lighthouse/tree/feat/eip8025
