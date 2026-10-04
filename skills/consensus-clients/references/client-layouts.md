# Consensus client directory layouts

Per-client package/directory maps, moved out of `../SKILL.md` (2026-10-04) to keep it short. Paths are relative to each repo root at its dev branch (lodestar `unstable`, lighthouse `unstable`, prysm `develop`, teku `master`, nimbus-eth2 `unstable`, grandine `develop`); verified against those tips on 2026-10-04. Re-check with `git -C ~/ethereum-repos/<r> ls-tree --name-only origin/<b> <dir>/` after fetching (see SKILL.md "Local-First Access").

## Lodestar

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
| `builder` | Gloas (ePBS) builder client: execution payload bids and envelopes (`@lodestar/builder`) |
| `db` | Database layer (LevelDB) |
| `reqresp` | libp2p req/resp protocol handlers |
| `cli` | Command-line interface |
| `logger` | Logging infrastructure |
| `utils` | Shared utilities |
| `era` | ERA file handling (historical data) |
| `spec-test-util` | Spec test runner utilities |
| `test-utils` | Shared test helpers |

## Lighthouse

**Directory structure:**

| Directory | Purpose |
|---|---|
| `beacon_node/` | Beacon node — contains sub-crates for each component |
| `beacon_node/beacon_chain/` | Core chain logic — block processing, head tracking |
| `beacon_node/store/` | Database (hot + cold storage, LevelDB) |
| `beacon_node/network/` | libp2p networking, sync |
| `beacon_node/http_api/` | REST API server |
| `beacon_node/execution_layer/` | Engine API client (EL communication) |
| `consensus/` | Spec implementation crates |
| `consensus/types/` | SSZ types and containers |
| `consensus/state_processing/` | State transition logic |
| `consensus/fork_choice/` | Fork choice (proto-array) |
| `validator_client/` | Validator client |
| `crypto/` | BLS, KZG, and other crypto |
| `slasher/` | Slashing detection |
| `lcli/` | CLI development tools |
| `boot_node/` | Discovery bootstrap node |
| `common/` | Shared libraries (logging, filesystem, etc.) |
| `testing/` | Test utilities, simulator |

## Prysm

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

## Teku

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

## Nimbus

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

## Grandine

**Crate structure** (70 crates in Cargo workspace):

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
