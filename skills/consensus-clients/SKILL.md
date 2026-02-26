---
name: consensus-clients
description: Use when comparing Ethereum consensus client implementations, looking up how a specific client implements a spec feature, checking client activity (PRs, issues, releases), or understanding architectural differences between Lodestar, Lighthouse, Prysm, Teku, Nimbus, and Grandine.
---

# Ethereum Consensus Client Cross-Reference

You have detailed maps of all 6 Ethereum consensus clients. Use this to find implementations, compare approaches, and track activity.

## Local Clone Strategy (Preferred)

**Clone client repos locally for fast code navigation.** Run the setup script from the plugin repo:

```bash
bash scripts/clone-repos.sh [base-dir]  # default: ~/ethereum-repos
```

Once cloned, use `grep`, `find`, and `cat` to navigate codebases directly:

```bash
# Find how each client implements a spec function
grep -rn "process_attestation\|processAttestation\|ProcessAttestation" \
  ~/ethereum-repos/lodestar/packages/ \
  ~/ethereum-repos/lighthouse/consensus/ \
  ~/ethereum-repos/prysm/beacon-chain/core/ \
  ~/ethereum-repos/teku/ethereum/spec/ \
  ~/ethereum-repos/nimbus-eth2/beacon_chain/spec/ \
  ~/ethereum-repos/grandine/transition_functions/ \
  --include="*.ts" --include="*.rs" --include="*.go" --include="*.java" --include="*.nim"

# Compare fork choice implementations
find ~/ethereum-repos/*/  -path "*/fork*choice*" -name "*.ts" -o -name "*.rs" -o -name "*.go" | head -20

# Search for a specific type across all clients
grep -rn "ExecutionPayloadEnvelope" ~/ethereum-repos/{lodestar,lighthouse,prysm,teku,nimbus-eth2,grandine}/ \
  --include="*.ts" --include="*.rs" --include="*.go" --include="*.java" --include="*.nim" | head -30
```

**Why local clones are better than WebFetch:**
- Cross-client grep finds implementations in seconds
- No URL guessing or 404s on wrong file paths
- Can search across all clients simultaneously
- Works offline, no rate limits

**Fallback:** If repos aren't cloned locally, use WebFetch with the raw GitHub URLs listed for each client below.

## Client Overview

| Client | Language | Repo | Build | Branch strategy |
|---|---|---|---|---|
| Lodestar | TypeScript | `ChainSafe/lodestar` | pnpm monorepo | `unstable` (dev), tags for releases |
| Lighthouse | Rust | `sigp/lighthouse` | Cargo workspace | `unstable` (dev), `stable` (releases) |
| Prysm | Go | `prysmaticlabs/prysm` | Bazel + Go modules | `develop` (dev), `master` (stable) |
| Teku | Java | `Consensys/teku` | Gradle | `master` (dev), tags for releases |
| Nimbus | Nim | `status-im/nimbus-eth2` | Nimble + Make | `unstable` (dev), `stable` (releases) |
| Grandine | Rust | `grandinetech/grandine` | Cargo workspace | `develop` (dev), tags for releases |

---

## Lodestar (TypeScript)

**Repo:** `ChainSafe/lodestar`

**Package structure** (`packages/`):

| Package | Purpose |
|---|---|
| `beacon-node` | Beacon chain client — block processing, sync, networking, API server |
| `validator` | Validator client — duties, signing, slashing protection |
| `state-transition` | Beacon state transition — epoch/block processing, per-fork logic |
| `fork-choice` | LMD-GHOST + Casper FFG fork choice |
| `types` | SSZ type definitions for all forks |
| `params` | Consensus parameters and constants |
| `config` | Network configuration (mainnet, testnet presets) |
| `api` | REST client for beacon API |
| `light-client` | Light client sync protocol |
| `db` | Database layer (LevelDB) |
| `reqresp` | libp2p req/resp protocol handlers |
| `cli` | Command-line interface |
| `logger` | Logging infrastructure |
| `utils` | Shared utilities |
| `prover` | Light client JSON-RPC proxy |
| `era` | ERA file handling (historical data) |
| `flare` | Debugging/testing tool |
| `spec-test-util` | Spec test runner utilities |
| `test-utils` | Shared test helpers |

**Key code paths:**
- State transition: `packages/state-transition/src/`
  - Per-fork logic: `packages/state-transition/src/slot/`
  - Epoch processing: `packages/state-transition/src/epoch/`
  - Block processing: `packages/state-transition/src/block/`
- Networking: `packages/beacon-node/src/network/`
- Sync: `packages/beacon-node/src/sync/`
- API server: `packages/beacon-node/src/api/`
- Fork choice: `packages/fork-choice/src/`
- SSZ types: `packages/types/src/`

**How to fetch code:**
```
https://raw.githubusercontent.com/ChainSafe/lodestar/unstable/packages/{package}/src/{path}.ts
```

**Key secondary repos:**

| Repo | What | How to fetch |
|---|---|---|
| `ChainSafe/lodestar-z` | Zig libraries for Lodestar — actively developed, integrated into main client for performance-critical paths | `https://raw.githubusercontent.com/ChainSafe/lodestar-z/main/{path}` |
| `ChainSafe/ssz` | SSZ TypeScript implementation (tree-backed persistent data structures) — `@chainsafe/ssz` on npm. Monorepo with packages: `ssz`, `persistent-merkle-tree`, `as-sha256`, `persistent-ts` | `https://raw.githubusercontent.com/ChainSafe/ssz/master/packages/ssz/src/{path}.ts` |
| `ChainSafe/discv5` | Discovery v5 TypeScript implementation — used by Lodestar for peer discovery. Monorepo with `@chainsafe/discv5` and `@chainsafe/enr` packages | `https://raw.githubusercontent.com/ChainSafe/discv5/master/packages/discv5/src/{path}.ts` |

---

## Lighthouse (Rust)

**Repo:** `sigp/lighthouse`

**Directory structure:**

| Directory | Purpose |
|---|---|
| `beacon_node/` | Beacon node — contains sub-crates for each component |
| `beacon_node/beacon_chain/` | Core chain logic — block processing, head tracking |
| `beacon_node/store/` | Database (hot + cold storage, LevelDB) |
| `beacon_node/network/` | libp2p networking, sync |
| `beacon_node/http_api/` | REST API server |
| `beacon_node/execution_layer/` | Engine API client (EL communication) |
| `beacon_node/eth1/` | Deposit contract interface |
| `consensus/` | Spec implementation crates |
| `consensus/types/` | SSZ types and containers |
| `consensus/state_processing/` | State transition logic |
| `consensus/fork_choice/` | Fork choice (proto-array) |
| `consensus/cached_tree_hash/` | Optimized tree hashing |
| `validator_client/` | Validator client |
| `crypto/` | BLS, KZG, and other crypto |
| `slasher/` | Slashing detection |
| `lcli/` | CLI development tools |
| `boot_node/` | Discovery bootstrap node |
| `common/` | Shared libraries (logging, filesystem, etc.) |
| `testing/` | Test utilities, simulator |

**Key code paths:**
- State transition: `consensus/state_processing/src/`
  - Per-slot: `consensus/state_processing/src/per_slot_processing.rs`
  - Per-block: `consensus/state_processing/src/per_block_processing/`
  - Per-epoch: `consensus/state_processing/src/per_epoch_processing/`
- Types: `consensus/types/src/`
- Fork choice: `consensus/fork_choice/src/`
- Networking: `beacon_node/network/src/`
- Sync: `beacon_node/network/src/sync/`
- REST API: `beacon_node/http_api/src/`

**How to fetch code:**
```
https://raw.githubusercontent.com/sigp/lighthouse/unstable/{path}.rs
```

**Key secondary repos:**

| Repo | What | How to fetch |
|---|---|---|
| `sigp/ethereum_ssz` | SSZ serialization crate, optimized for speed and security | `https://raw.githubusercontent.com/sigp/ethereum_ssz/main/ssz/src/{path}.rs` |
| `sigp/discv5` | Discovery v5 Rust implementation | `https://raw.githubusercontent.com/sigp/discv5/master/src/{path}.rs` |
| `sigp/milhouse` | Persistent binary merkle tree — used for efficient state storage | `https://raw.githubusercontent.com/sigp/milhouse/main/src/{path}.rs` |
| `sigp/enr` | Ethereum Node Records implementation | `https://raw.githubusercontent.com/sigp/enr/master/src/{path}.rs` |

---

## Prysm (Go)

**Repo:** `prysmaticlabs/prysm`

**Directory structure:**

| Directory | Purpose |
|---|---|
| `beacon-chain/` | Beacon node implementation |
| `beacon-chain/core/` | Core spec logic (blocks, epoch, validators) |
| `beacon-chain/state/` | Beacon state management |
| `beacon-chain/blockchain/` | Chain processing, head tracking |
| `beacon-chain/sync/` | Sync protocols (initial, regular) |
| `beacon-chain/p2p/` | libp2p networking |
| `beacon-chain/rpc/` | gRPC + REST API |
| `beacon-chain/execution/` | Engine API client |
| `beacon-chain/forkchoice/` | Fork choice implementation |
| `beacon-chain/db/` | Database (BoltDB) |
| `validator/` | Validator client |
| `consensus-types/` | Shared consensus data types |
| `proto/` | Protobuf definitions |
| `encoding/` | SSZ encoding, bytesutil |
| `config/` | Network config, feature flags |
| `crypto/` | BLS, hash utilities |
| `network/` | High-level network utilities |
| `monitoring/` | Metrics, tracing |
| `contracts/deposit/` | Deposit contract bindings |
| `cmd/` | CLI entry points (beacon-chain, validator, etc.) |
| `tools/` | Development tools |

**Key code paths:**
- Block processing: `beacon-chain/core/blocks/`
- Epoch processing: `beacon-chain/core/epoch/`
- State transition: `beacon-chain/core/transition/`
- Validator logic: `beacon-chain/core/validators/`
- Fork choice: `beacon-chain/forkchoice/`
- Types: `consensus-types/`
- Networking: `beacon-chain/p2p/`
- Sync: `beacon-chain/sync/`

**How to fetch code:**
```
https://raw.githubusercontent.com/prysmaticlabs/prysm/develop/{path}.go
```

**Key secondary repos:**

| Repo | What | How to fetch |
|---|---|---|
| `prysmaticlabs/gohashtree` | SHA256 library optimized for Merkle trees (Go + Assembly) | `https://raw.githubusercontent.com/prysmaticlabs/gohashtree/main/{path}.go` |

Prysm is largely self-contained — most dependencies are vendored or in the main repo.

---

## Teku (Java)

**Repo:** `Consensys/teku`

**Directory structure:**

| Directory | Purpose |
|---|---|
| `beacon/` | Core beacon chain logic |
| `beacon/validator/` | Validator duties management |
| `ethereum/` | Ethereum protocol modules |
| `ethereum/spec/` | Spec types, logic, and milestones |
| `ethereum/statetransition/` | State transition implementation |
| `ethereum/executionlayer/` | Engine API client |
| `networking/` | libp2p and discovery |
| `networking/eth2/` | Eth2 gossip/reqresp protocols |
| `storage/` | Database layer (RocksDB) |
| `validator/` | Validator client modules |
| `services/` | Service layer modules |
| `infrastructure/` | Logging, metrics, async, IO |
| `data/` | Data serialization, API types |
| `eth-tests/` | Ethereum spec test integration |
| `eth-reference-tests/` | Reference test runners |
| `fork-choice-tests/` | Fork choice test vectors |
| `acceptance-tests/` | End-to-end integration tests |
| `teku/` | Main application entry point |

**Key code paths:**
- Spec logic: `ethereum/spec/src/main/java/tech/pegasys/teku/spec/`
  - Per-fork logic: `ethereum/spec/src/main/java/tech/pegasys/teku/spec/logic/versions/`
  - Types: `ethereum/spec/src/main/java/tech/pegasys/teku/spec/datastructures/`
- State transition: `ethereum/statetransition/src/main/java/`
- Fork choice: `ethereum/spec/src/main/java/tech/pegasys/teku/spec/logic/common/forkchoice/`
- Networking: `networking/eth2/src/main/java/`
- REST API: `beacon/validator/src/main/java/` and `data/`

**Code style:** Google Java conventions, enforced by Spotless. Requires Java 21+.

**How to fetch code:**
```
https://raw.githubusercontent.com/Consensys/teku/master/{path}.java
```

**Key secondary repos:**

| Repo | What | How to fetch |
|---|---|---|
| `Consensys/Web3Signer` | Remote signing service — used with Teku for enterprise key management | `https://raw.githubusercontent.com/Consensys/Web3Signer/master/{path}.java` |

---

## Nimbus (Nim)

**Repo:** `status-im/nimbus-eth2`

**Directory structure:**

| Directory | Purpose |
|---|---|
| `beacon_chain/` | Core implementation (all-in-one) |
| `beacon_chain/spec/` | Spec types, datatypes, state transition |
| `beacon_chain/consensus_object_pools/` | Attestation, block, sync committee pools |
| `beacon_chain/gossip_processing/` | Gossip validation |
| `beacon_chain/networking/` | libp2p networking |
| `beacon_chain/sync/` | Sync manager, request manager |
| `beacon_chain/validators/` | Validator client, keystores |
| `beacon_chain/el/` | Execution layer communication |
| `beacon_chain/rpc/` | REST API server |
| `beacon_chain/fork_choice/` | Fork choice implementation |
| `ncli/` | CLI tools for data structure inspection |
| `research/` | Research and experimental code |
| `tests/` | Test suite, simulation framework |
| `wasm/` | WebAssembly bindings |
| `grafana/` | Monitoring dashboards |
| `scripts/` | Build and CI scripts |
| `vendor/` | Vendored dependencies |

**Key code paths:**
- State transition: `beacon_chain/spec/`
  - Datatypes: `beacon_chain/spec/datatypes/`
  - State transition: `beacon_chain/spec/state_transition.nim`
  - Block processing: `beacon_chain/spec/beaconstate.nim`
- Fork choice: `beacon_chain/fork_choice/`
- Networking: `beacon_chain/networking/`
- Sync: `beacon_chain/sync/`
- Validator: `beacon_chain/validators/`

**How to fetch code:**
```
https://raw.githubusercontent.com/status-im/nimbus-eth2/unstable/{path}.nim
```

**Key secondary repos:**

| Repo | What | How to fetch |
|---|---|---|
| `status-im/nimbus-eth3` | Lean consensus client (next-gen Nimbus). Default branch: `stable` | `https://raw.githubusercontent.com/status-im/nimbus-eth3/stable/{path}.nim` |
| `status-im/nim-ssz-serialization` | SSZ serialization + merkleization. Flat repo — key file: `ssz_serialization.nim` | `https://raw.githubusercontent.com/status-im/nim-ssz-serialization/master/ssz_serialization/{path}.nim` |
| `status-im/nim-blscurve` | BLS12-381 signature library. Key file: `blscurve.nim` | `https://raw.githubusercontent.com/status-im/nim-blscurve/master/blscurve/{path}.nim` |
| `status-im/nim-eth` | Common Ethereum utilities (RLP, trie, keys) | `https://raw.githubusercontent.com/status-im/nim-eth/master/eth/{path}.nim` |

---

## Grandine (Rust)

**Repo:** `grandinetech/grandine`

**Crate structure** (~90 crates in Cargo workspace):

| Crate | Purpose |
|---|---|
| `transition_functions` | State transition (per-slot, per-block, per-epoch) |
| `fork_choice_control` | Fork choice orchestration |
| `fork_choice_store` | Fork choice data store |
| `attestation_verifier` | Attestation validation |
| `validator` | Validator client |
| `slasher` | Slashing detection |
| `slashing_protection` | Slashing protection DB |
| `doppelganger_protection` | Doppelganger detection |
| `p2p` | libp2p networking |
| `eth2_libp2p` | Eth2-specific libp2p (git submodule) |
| `http_api` | REST API server |
| `builder_api` | Builder API (MEV) client |
| `eth1_api` | Execution layer communication |
| `ssz` | SSZ serialization |
| `types` | Consensus types |
| `helper_functions` | Spec helper functions |
| `database` | Persistence layer |
| `state_cache` | State caching |
| `deposit_tree` | Deposit contract tree |
| `bls` | BLS cryptography |
| `kzg_utils` | KZG commitment utilities |
| `hashing` | Hash utilities |
| `runtime` | Async runtime |
| `metrics` | Prometheus metrics |
| `logging` | Structured logging |
| `factory` | Object construction |

**Key code paths:**
- State transition: `transition_functions/src/`
- Types: `types/src/`
- Fork choice: `fork_choice_control/src/`, `fork_choice_store/src/`
- Networking: `p2p/src/`
- API: `http_api/src/`
- Helpers: `helper_functions/src/`

**How to fetch code:**
```
https://raw.githubusercontent.com/grandinetech/grandine/develop/{crate}/src/{path}.rs
```

**Key secondary repos:**

| Repo | What | How to fetch |
|---|---|---|
| `grandinetech/eth2_libp2p` | Eth2-specific libp2p networking (git submodule in main repo). Re-exports rust-libp2p with beacon chain specifics | `https://raw.githubusercontent.com/grandinetech/eth2_libp2p/main/src/{path}.rs` |
| `grandinetech/rust-kzg` | Parallelized multi-backend KZG library for data sharding. Supports arkworks, BLST, constantine, mcl backends | `https://raw.githubusercontent.com/grandinetech/rust-kzg/main/kzg/src/{path}.rs` |

---

## Cross-Reference: Spec Concept → Code Location

Use this table to find where each client implements a given spec concept.

| Spec concept | Lodestar | Lighthouse | Prysm | Teku | Nimbus | Grandine |
|---|---|---|---|---|---|---|
| **State transition** | `state-transition/src/` | `consensus/state_processing/src/` | `beacon-chain/core/transition/` | `ethereum/statetransition/` | `beacon_chain/spec/state_transition.nim` | `transition_functions/src/` |
| **Block processing** | `state-transition/src/block/` | `consensus/state_processing/src/per_block_processing/` | `beacon-chain/core/blocks/` | `ethereum/spec/.../logic/versions/` | `beacon_chain/spec/beaconstate.nim` | `transition_functions/src/` |
| **Epoch processing** | `state-transition/src/epoch/` | `consensus/state_processing/src/per_epoch_processing/` | `beacon-chain/core/epoch/` | `ethereum/spec/.../logic/versions/` | `beacon_chain/spec/` | `transition_functions/src/` |
| **Fork choice** | `fork-choice/src/` | `consensus/fork_choice/src/` | `beacon-chain/forkchoice/` | `ethereum/spec/.../forkchoice/` | `beacon_chain/fork_choice/` | `fork_choice_control/src/` |
| **Types/SSZ** | `types/src/` | `consensus/types/src/` | `consensus-types/` + `proto/` | `ethereum/spec/.../datastructures/` | `beacon_chain/spec/datatypes/` | `types/src/` + `ssz/src/` |
| **Networking** | `beacon-node/src/network/` | `beacon_node/network/src/` | `beacon-chain/p2p/` | `networking/eth2/` | `beacon_chain/networking/` | `p2p/src/` |
| **Sync** | `beacon-node/src/sync/` | `beacon_node/network/src/sync/` | `beacon-chain/sync/` | `beacon/sync/` | `beacon_chain/sync/` | `p2p/src/` |
| **REST API** | `beacon-node/src/api/` | `beacon_node/http_api/src/` | `beacon-chain/rpc/` | `data/` + `beacon/validator/` | `beacon_chain/rpc/` | `http_api/src/` |
| **Validator** | `validator/src/` | `validator_client/src/` | `validator/` | `validator/` | `beacon_chain/validators/` | `validator/src/` |
| **Engine API** | `beacon-node/src/execution/` | `beacon_node/execution_layer/src/` | `beacon-chain/execution/` | `ethereum/executionlayer/` | `beacon_chain/el/` | `eth1_api/src/` |
| **Database** | `db/src/` | `beacon_node/store/src/` | `beacon-chain/db/` | `storage/` | `beacon_chain/db/` | `database/src/` |

---

## Checking Client Activity

Use `gh` CLI to check recent activity across clients:

**Recent PRs:**
```bash
gh pr list --repo ChainSafe/lodestar --limit 10
gh pr list --repo sigp/lighthouse --limit 10
gh pr list --repo prysmaticlabs/prysm --limit 10
gh pr list --repo Consensys/teku --limit 10
gh pr list --repo status-im/nimbus-eth2 --limit 10
gh pr list --repo grandinetech/grandine --limit 10  # note: default branch is 'develop'
```

**Search PRs by topic:**
```bash
gh search prs "blob sidecar" --repo ChainSafe/lodestar
gh search prs "blob sidecar" --repo sigp/lighthouse
```

**Recent releases:**
```bash
gh release list --repo ChainSafe/lodestar --limit 5
gh release list --repo sigp/lighthouse --limit 5
gh release list --repo prysmaticlabs/prysm --limit 5
gh release list --repo Consensys/teku --limit 5
gh release list --repo status-im/nimbus-eth2 --limit 5
gh release list --repo grandinetech/grandine --limit 5
```

**Recent issues:**
```bash
gh issue list --repo ChainSafe/lodestar --limit 10
gh search issues "keyword" --repo ChainSafe/lodestar
```

**Compare how clients implemented a specific feature:**
1. If repos are cloned locally, grep across all clients simultaneously:
   ```bash
   grep -rn "feature_keyword" ~/ethereum-repos/{lodestar,lighthouse,prysm,teku,nimbus-eth2,grandine}/ \
     --include="*.ts" --include="*.rs" --include="*.go" --include="*.java" --include="*.nim" | head -30
   ```
2. Search PRs across all clients for the feature name or EIP number
3. Read the PR descriptions and key changed files
4. If not cloned, fetch the actual implementation files using raw GitHub URLs above

---

## Architectural Comparison

### Language & performance philosophy
- **Lodestar** — TypeScript. Prioritizes accessibility, developer onboarding, spec conformance. Easier to read and prototype. Uses SSZ for performance-critical paths.
- **Lighthouse** — Rust. Strong safety guarantees, memory safety without GC. Well-structured crate hierarchy. Known for reliability.
- **Prysm** — Go. Simple concurrency model (goroutines). Uses protobuf for internal types alongside SSZ. Large contributor base.
- **Teku** — Java. Enterprise-grade (ConsenSys). JVM ecosystem, Gradle build. Follows Google Java style strictly.
- **Nimbus** — Nim. Optimized for resource-constrained devices (RPi). Compiles to C. Smallest memory footprint.
- **Grandine** — Rust. Newest client. ~90 fine-grained crates. Focus on performance benchmarks and modularity.

### How fork-specific logic is organized
- **Lodestar** — Fork logic mixed into state-transition with conditional branches and per-fork directories
- **Lighthouse** — Separate modules per fork under `per_epoch_processing/` and `per_block_processing/`
- **Prysm** — Fork-specific logic in `beacon-chain/core/` subdirectories
- **Teku** — Explicit versioned logic classes under `spec/logic/versions/{fork}/`
- **Nimbus** — Fork-specific datatypes in `beacon_chain/spec/datatypes/{fork}.nim`
- **Grandine** — Handled within `transition_functions` using Rust generics and traits

### Database choices
- **Lodestar** — LevelDB
- **Lighthouse** — LevelDB (hot + cold DB split)
- **Prysm** — BoltDB
- **Teku** — RocksDB
- **Nimbus** — SQLite + RocksDB
- **Grandine** — Custom persistence layer

### SSZ implementation
- **Lodestar** — `ChainSafe/ssz` (TypeScript, tree-backed)
- **Lighthouse** — `sigp/ethereum_ssz` (Rust)
- **Prysm** — `fastssz` + protobuf (Go)
- **Teku** — Teku SSZ library (Java)
- **Nimbus** — `status-im/nim-ssz-serialization` (Nim)
- **Grandine** — Custom `ssz` crate (Rust)

---

## Shared Cross-Client Dependencies

| Dependency | Repo | What | Used by |
|---|---|---|---|
| BLST | `supranational/blst` | BLS12-381 signatures (C/assembly). High-performance, formally verified. | All clients via language-specific wrappers |
| rust-libp2p | `libp2p/rust-libp2p` | libp2p networking stack in Rust | Lighthouse, Grandine |
| js-libp2p | `libp2p/js-libp2p` | libp2p networking stack in JavaScript | Lodestar |
| c-kzg-4844 | `ethereum/c-kzg-4844` | KZG commitment library for EIP-4844 blobs | Most clients via bindings |
