---
name: consensus-clients
description: Use when comparing Ethereum consensus client implementations, looking up how a specific client implements a spec feature, checking client activity (PRs, issues, releases), or understanding architectural differences between Lodestar, Lighthouse, Prysm, Teku, Nimbus, and Grandine.
---

# Ethereum Consensus Client Cross-Reference

You have detailed maps of all 6 Ethereum consensus clients. Use this to find implementations, compare approaches, and track activity.

## Local-First Access (MANDATORY)

**All 6 client repos are shallow-cloned at `~/ethereum-repos/`, but never trust their working trees:** they can be months stale and on the wrong branch (lighthouse/nimbus-eth2 on `stable`, lodestar on a feature branch with local work). Never checkout/pull/merge/reset them. Fetch each dev branch into its remote-tracking ref, then read with `git grep` / `git show` / `git ls-tree` at `origin/<b>`. Never use WebFetch for GitHub-hosted content.

```bash
# 1. Fetch dev-branch tips (updates only refs/remotes/origin/<b>); quote the printed ref date in answers
for d in lodestar:unstable lighthouse:unstable prysm:develop teku:master nimbus-eth2:unstable grandine:develop; do r=${d%%:*}; b=${d##*:}; git -C ~/ethereum-repos/$r fetch -q --depth=1 origin +refs/heads/$b:refs/remotes/origin/$b; echo "$r origin/$b $(git -C ~/ethereum-repos/$r log -1 --format=%cs origin/$b)"; done

# 2. Find how each client implements a spec function or type (hits are prefixed origin/<b>:<path>)
for d in lodestar:unstable lighthouse:unstable prysm:develop teku:master nimbus-eth2:unstable grandine:develop; do r=${d%%:*}; b=${d##*:}; echo "== $r"; git -C ~/ethereum-repos/$r grep -n -I -E "process_attestation|processAttestation|ProcessAttestation" origin/$b -- '*.ts' '*.rs' '*.go' '*.java' '*.nim' | head -10; done

# Compare fork choice implementations (file listing)
for d in lodestar:unstable lighthouse:unstable prysm:develop teku:master nimbus-eth2:unstable grandine:develop; do r=${d%%:*}; b=${d##*:}; echo "== $r"; git -C ~/ethereum-repos/$r ls-tree -r --name-only origin/$b | grep -i -E "fork[-_]?choice" | head -5; done

# Read one file
git -C ~/ethereum-repos/teku show origin/master:<path>
```

`~/lodestar` is the Lodestar dev checkout and is often on an unrelated branch: `git -C ~/lodestar fetch -q origin unstable`, then read `origin/unstable` the same way.

**Why local-first:**
- Cross-client grep finds implementations in seconds
- No URL guessing or 404s on wrong file paths
- Can search across all clients simultaneously
- Works offline, no rate limits

**Fallback:** If the fetch fails or a repo isn't cloned (the secondary repos below are not), use the raw GitHub URLs below, via the web-scraping skill (`skills/web-scraping/SKILL.md`) if a plain fetch is blocked.

## Client Overview

| Client | Language | Repo | Build | Branch strategy |
|---|---|---|---|---|
| Lodestar | TypeScript | `ChainSafe/lodestar` | pnpm monorepo | `unstable` (dev), tags for releases |
| Lighthouse | Rust | `sigp/lighthouse` | Cargo workspace | `unstable` (dev), `stable` (releases, GitHub default) |
| Prysm | Go | `OffchainLabs/prysm` | Bazel + Go modules | `develop` (dev + default), releases via tags (`master` frozen since 2025-02) |
| Teku | Java | `Consensys-Incorporated/teku` | Gradle | `master` (dev), tags for releases |
| Nimbus | Nim | `status-im/nimbus-eth2` | Nimble + Make | `unstable` (dev), `stable` (releases, GitHub default) |
| Grandine | Rust | `grandinetech/grandine` | Cargo workspace | `develop` (dev), tags for releases |

Prysm moved from `prysmaticlabs/prysm`, Teku from `Consensys/teku` (Web3Signer from `Consensys/Web3Signer`). The old slugs still work for `gh pr list`, `gh release list` and raw URLs, but `gh search prs|issues --repo <old slug>` fails ("cannot be searched"), so always use the new slugs.

---

## Lodestar (TypeScript)

**Repo:** `ChainSafe/lodestar`

**Package structure** (17 packages in `packages/`, incl. `builder` = Gloas ePBS builder client): see `references/client-layouts.md#lodestar`.

`light-client` and `prover` moved out of the monorepo (#9346; the light-client spec functions now live in `state-transition/src/lightClient/`); `flare` was removed (#9358).

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

**Directory structure:** see `references/client-layouts.md#lighthouse`.

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

**Repo:** `OffchainLabs/prysm` (formerly `prysmaticlabs/prysm`)

**Directory structure:** see `references/client-layouts.md#prysm`.

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
https://raw.githubusercontent.com/OffchainLabs/prysm/develop/{path}.go
```

**Key secondary repos:**

| Repo | What | How to fetch |
|---|---|---|
| `prysmaticlabs/gohashtree` | SHA256 library optimized for Merkle trees (Go + Assembly) | `https://raw.githubusercontent.com/prysmaticlabs/gohashtree/main/{path}.go` |

Prysm is largely self-contained — most dependencies are vendored or in the main repo.

---

## Teku (Java)

**Repo:** `Consensys-Incorporated/teku` (formerly `Consensys/teku`)

**Directory structure:** see `references/client-layouts.md#teku`.

**Key code paths:**
- Spec logic: `ethereum/spec/src/main/java/tech/pegasys/teku/spec/`
  - Per-fork logic: `ethereum/spec/src/main/java/tech/pegasys/teku/spec/logic/versions/`
  - Types: `ethereum/spec/src/main/java/tech/pegasys/teku/spec/datastructures/`
- State transition: `ethereum/statetransition/src/main/java/`
- Fork choice: `ethereum/statetransition/src/main/java/tech/pegasys/teku/statetransition/forkchoice/` (spec helpers: `ethereum/spec/.../spec/logic/common/util/ForkChoiceUtil.java` + per-fork `ForkChoiceUtil{Fork}`; types: `ethereum/spec/.../spec/datastructures/forkchoice/`)
- Networking: `networking/eth2/src/main/java/`
- REST API: `beacon/validator/src/main/java/` and `data/`

**Code style:** Google Java conventions, enforced by Spotless. Requires Java 25 (`targetJavaVersion` in `build.gradle`).

**How to fetch code:**
```
https://raw.githubusercontent.com/Consensys-Incorporated/teku/master/{path}.java
```

**Key secondary repos:**

| Repo | What | How to fetch |
|---|---|---|
| `Consensys-Incorporated/web3signer` | Remote signing service — used with Teku for enterprise key management | `https://raw.githubusercontent.com/Consensys-Incorporated/web3signer/master/{path}.java` |

---

## Nimbus (Nim)

**Repo:** `status-im/nimbus-eth2`

**Directory structure:** see `references/client-layouts.md#nimbus`.

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

**Crate structure** (70 crates in Cargo workspace): see `references/client-layouts.md#grandine`.

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
| **Fork choice** | `fork-choice/src/` | `consensus/fork_choice/src/` | `beacon-chain/forkchoice/` | `ethereum/statetransition/.../forkchoice/` | `beacon_chain/fork_choice/` | `fork_choice_control/src/` |
| **Types/SSZ** | `types/src/` | `consensus/types/src/` | `consensus-types/` + `proto/` | `ethereum/spec/.../datastructures/` | `beacon_chain/spec/datatypes/` | `types/src/` + `ssz/src/` |
| **Networking** | `beacon-node/src/network/` | `beacon_node/network/src/` | `beacon-chain/p2p/` | `networking/eth2/` | `beacon_chain/networking/` | `p2p/src/` |
| **Sync** | `beacon-node/src/sync/` | `beacon_node/network/src/sync/` | `beacon-chain/sync/` | `beacon/sync/` | `beacon_chain/sync/` | `p2p/src/` |
| **REST API** | `beacon-node/src/api/` | `beacon_node/http_api/src/` | `beacon-chain/rpc/` | `data/` + `beacon/validator/` | `beacon_chain/rpc/` | `http_api/src/` |
| **Validator** | `validator/src/` | `validator_client/src/` | `validator/` | `validator/` | `beacon_chain/validators/` | `validator/src/` |
| **Engine API** | `beacon-node/src/execution/` | `beacon_node/execution_layer/src/` | `beacon-chain/execution/` | `ethereum/executionlayer/` | `beacon_chain/el/` | `eth1_api/src/` |
| **Database** | `db/src/` | `beacon_node/store/src/` | `beacon-chain/db/` | `storage/` | `beacon_chain/beacon_chain_db*.nim`, `db_utils.nim` | `database/src/` |

---

## Checking Client Activity

Use `gh` CLI to check recent activity across clients:

**Recent PRs:**
```bash
gh pr list --repo ChainSafe/lodestar --limit 10
gh pr list --repo sigp/lighthouse --limit 10
gh pr list --repo OffchainLabs/prysm --limit 10
gh pr list --repo Consensys-Incorporated/teku --limit 10
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
gh release list --repo OffchainLabs/prysm --limit 5
gh release list --repo Consensys-Incorporated/teku --limit 5
gh release list --repo status-im/nimbus-eth2 --limit 5
gh release list --repo grandinetech/grandine --limit 5
```

**Recent issues:**
```bash
gh issue list --repo ChainSafe/lodestar --limit 10
gh search issues "keyword" --repo ChainSafe/lodestar
```

**Compare how clients implemented a specific feature:**
1. Fetch the dev branches and `git grep` all clients for the keyword (the two loops in Local-First Access); state each ref date
2. Search PRs across all clients for the feature name or EIP number:
   ```bash
   for r in ChainSafe/lodestar sigp/lighthouse OffchainLabs/prysm Consensys-Incorporated/teku status-im/nimbus-eth2 grandinetech/grandine; do echo "== $r"; gh search prs "EIP-7732" --repo $r --limit 5; done
   ```
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
- **Grandine** — Rust. Newest client. ~70 fine-grained crates. Focus on performance benchmarks and modularity.

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
