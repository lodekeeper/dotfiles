# Cross-Client PoCs, Experimental Features & Innovations

*Researched: 2026-02-28*

This document catalogs experimental implementations, PoCs, and innovative features from other Ethereum consensus clients that Lodestar could adopt or build upon.

---

## 🔥 Tier 1: High-Impact, Feasible for One Dev

### 1. Fast Confirmation Rule (FCR)
**Client:** Nimbus (leading), Teku (started)
**What:** Reduces perceived finality from 13-19 minutes to ~15-30 seconds by implementing an assumption-based confirmation rule within fork choice. The spec is at [consensus-specs#4747](https://github.com/ethereum/consensus-specs/pull/4747).
**Status:**
- **Nimbus:** ~10 PRs merged in Feb 2026, actively implementing. Tracks slot assignments, equivocation scores, balance sources per epoch, confirmed block tracking in fork choice.
  - [Track slot instead of epoch in proto array](https://github.com/status-im/nimbus-eth2/pull/7914)
  - [Move block confirmation out of proto array](https://github.com/status-im/nimbus-eth2/pull/7969)
  - [Track slashed validators in EpochRef](https://github.com/status-im/nimbus-eth2/pull/7944)
  - [Add get_current_target_score](https://github.com/status-im/nimbus-eth2/pull/8031)
  - [Track support from empty slots and equivocating validators](https://github.com/status-im/nimbus-eth2/pull/8026)
  - [Switch FCR balance source on epoch start](https://github.com/status-im/nimbus-eth2/pull/8029)
  - [Track shuffling for current_epoch - 2](https://github.com/status-im/nimbus-eth2/pull/8039)
- **Teku:** Has prerequisite fork choice changes ([#7873](https://github.com/Consensys/teku/pull/7873), [#7903](https://github.com/Consensys/teku/pull/7903))
- **Lodestar:** PR opened by nazarhussain: [#8837](https://github.com/ChainSafe/lodestar/pull/8837) — early stage

**Feasibility for Lodestar:** HIGH — Already started. Can study Nimbus's approach closely (they're furthest along). CL-only, modifies fork choice. The spec is well-defined.
**Impact:** 🔴 VERY HIGH — This is likely to be a Hegotá upgrade feature. Early implementation = competitive advantage. Reduces finality from minutes to seconds.

---

### 2. Eager Attestation via SSE Head Events
**Client:** Lighthouse
**What:** Instead of always waiting 4 seconds into the slot to attest, the validator client subscribes to SSE head events and attests as soon as it receives a valid block from the expected proposer — whichever comes first (block received or 4s timeout). This is actually spec-compliant behavior that most clients skip.
**Links:**
- [Issue #7820](https://github.com/sigp/lighthouse/issues/7820) — Design
- [PR #7892](https://github.com/sigp/lighthouse/pull/7892) — Implementation (merged)
- [PR #8718](https://github.com/sigp/lighthouse/pull/8718) — Emit NewHead SSE event earlier in block import (merged)

**Feasibility for Lodestar:** HIGH — Straightforward VC change. Subscribe to head events, race against 4s timer.
**Impact:** 🟡 MEDIUM — Better attestation timeliness, spreads load across slot instead of bursty traffic at 4s. Improves validator rewards.

---

### 3. Late Block Reorg & Block Preparation
**Client:** Teku (enabled by default), Lighthouse (implemented)
**What:** When a block arrives late in the slot, the client can prepare to propose a competing block that re-orgs the late one. Teku recently enabled this by default on mainnet ([#10214](https://github.com/Consensys/teku/pull/10214)). Lighthouse has had it since 2021 ([#2860](https://github.com/sigp/lighthouse/pull/2860)).
**Links:**
- [Teku #10214](https://github.com/Consensys/teku/pull/10214) — Enable late block reorg and block preparation (merged Dec 2025)
- [Teku #10379](https://github.com/Consensys/teku/pull/10379) — is_proposer_equivocation check
- [Lighthouse #2860](https://github.com/sigp/lighthouse/pull/2860) — Enable proposer boost re-orging (merged 2021)
- [Lighthouse #4151](https://github.com/sigp/lighthouse/pull/4151) — Make re-org strategy more cautious

**Feasibility for Lodestar:** MEDIUM — Requires fork choice changes and careful timing. Teku's implementation is well-documented with clear defaults.
**Impact:** 🟡 MEDIUM — Better validator rewards for proposers. Important for competitive block production.

---

### 4. Batch Slashing Protection Checks
**Client:** Lighthouse
**What:** Instead of checking attestations against the slashing protection DB sequentially, sign them first and then batch-check against the DB. Eliminates sequential bottleneck.
**Links:**
- [PR #8516](https://github.com/sigp/lighthouse/pull/8516) — Check slashability of attestations in batches (merged)
- Based on rework of [#6219](https://github.com/sigp/lighthouse/pull/6219)

**Feasibility for Lodestar:** HIGH — CL-only, validator client change. Well-scoped.
**Impact:** 🟡 MEDIUM — Reduces attestation latency, especially for nodes with many validators.

---

### 5. ERA File Support
**Client:** Nimbus (native, polished), others have varying support
**What:** ERA files (`.e2s`) for storing and redistributing beacon chain history and state. Nimbus recently simplified era-based node startup ([#7888](https://github.com/status-im/nimbus-eth2/pull/7888)) — bootstrap directly from era files without needing a checkpoint server.
**Links:**
- [Nimbus #7888](https://github.com/status-im/nimbus-eth2/pull/7888) — Simplify era-based node startup (merged)
- [Nimbus #5882](https://github.com/status-im/nimbus-eth2/pull/5882) — Blob sidecar era/erb proposal
- [Lodestar #7048](https://github.com/ChainSafe/lodestar/issues/7048) — ERA file support (open issue)

**Feasibility for Lodestar:** MEDIUM — Well-understood format, clear spec. Lodestar already has an open issue for it.
**Impact:** 🟡 MEDIUM — Better UX for archive nodes, historical state access, and node bootstrapping.

---

## 🔬 Tier 2: Research/Experimental — Higher Effort, Very High Impact

### 6. zkVM Consensus State Transition Verification
**Client:** Grandine
**What:** Grandine is integrating zkVM (both Pico and Zisk backends) to generate zero-knowledge proofs of consensus state transitions. This enables stateless validation — nodes can verify blocks with a cryptographic proof instead of re-executing the full state transition.
**Links:**
- [PR #386](https://github.com/grandinetech/grandine/pull/386) — zkvm-pico host and guest programs (merged Sep 2025)
- [PR #475](https://github.com/grandinetech/grandine/pull/475) — zkVM Zisk integration (merged Nov 2025)
- [PR #470](https://github.com/grandinetech/grandine/pull/470) — Fix SSZ maximum length issue in zkvms (merged)
- [Lighthouse #7755](https://github.com/sigp/lighthouse/pull/7755) — Rough prototype for execution proofs architectural changes (open, by kevaundray)

**Feasibility for Lodestar:** LOW-MEDIUM — Requires significant crypto/zkVM expertise. Could potentially use a WASM-based zkVM from TypeScript. Long-term research project.
**Impact:** 🔴 VERY HIGH — Enables stateless validation, a key part of Ethereum's long-term roadmap. First-mover advantage is massive.

---

### 7. Delta Encoding for Beacon State Storage
**Client:** Grandine, Lighthouse
**What:** Store only the differences between consecutive states rather than full states, massively reducing disk usage.
- **Grandine:** [PR #523](https://github.com/grandinetech/grandine/pull/523) — Delta encoding, claims ~80% disk reduction, >70% faster state reads/writes (open)
- **Lighthouse:** [PR #6750](https://github.com/sigp/lighthouse/pull/6750) — Hierarchical state diffs in hot DB (merged Jan 2025, by dapplion)

**Feasibility for Lodestar:** MEDIUM — Requires state management rework. Lighthouse's approach (hierarchical diffs) is well-tested and merged.
**Impact:** 🔴 HIGH — Massive disk savings, better I/O performance. Critical for Lodestar's competitiveness as state grows.

---

### 8. "Fullhouse": CL + EL Single Binary
**Client:** Lighthouse (PoC with Reth)
**What:** Run CL (Lighthouse) and EL (Reth) in a single binary with direct function calls instead of HTTP JSON-RPC. Benefits: better UX, lower resource usage, reduced latency, end-to-end observability.
**Links:**
- [Blog post](https://blog.sigmaprime.io/fullhouse.html)
- Built with Claude as a time-boxed experiment
- Replaced `HttpJsonRpc` with `RethEngineApi` using Reth's `EngineApi` struct

**Feasibility for Lodestar:** LOW — TypeScript CL + Rust EL integration is much harder than Rust+Rust. Could explore Lodestar + ethereumjs EVM (both JS/TS).
**Impact:** 🟢 MEDIUM — Cool experiment but TypeScript EL performance would be limited.

---

### 9. Safe Non-Finalized Checkpoint Sync
**Client:** Lighthouse
**What:** Allows bootstrapping into a state for a checkpoint that is NOT yet finalized. Critical for network recovery during long periods of non-finality — "could save Ethereum Mainnet when shit hits the fan."
**Links:**
- [PR #8382](https://github.com/sigp/lighthouse/pull/8382) — by dapplion (open)
- Introduces `ForkChoiceCheckpoint` with `Local` vs `OnChain` variants

**Feasibility for Lodestar:** MEDIUM-HIGH — CL-only, fork choice changes. Well-documented PR to reference.
**Impact:** 🔴 HIGH — Network resilience feature. Could be the difference in a non-finality crisis.

---

### 10. Distributed Blob Building (PeerDAS Optimization)
**Client:** Lighthouse
**What:** Instead of the block proposer computing all KZG cell proofs and distributing all data, distribute the computation and data across "super nodes." Fetches blobs from EL mempool and uses gradual publication optimizations.
**Links:**
- [Blog: Scaling Ethereum with PeerDAS and Distributed Blob Building](https://blog.sigmaprime.io/peerdas-distributed-blob-building.html)
- Implemented on Lighthouse's peerdas-rangesync branch

**Feasibility for Lodestar:** MEDIUM — Requires deep PeerDAS understanding. Well-documented in the blog.
**Impact:** 🟡 MEDIUM — Important for scaling but more relevant when blob counts increase significantly.

---

## 📊 Tier 3: Performance Optimizations Worth Porting

### 11. SSZ Hashing Optimization for Epoch Transition
**Client:** Teku
**What:** Reduced `ArrayWrappingBytes32` allocations in SSZ tree hashing. 37% reduction in GC allocation rate, 3.7% throughput improvement for epoch transitions.
**Links:**
- [PR #10387](https://github.com/Consensys/teku/pull/10387) — Hashing optimization (merged)

**Feasibility for Lodestar:** MEDIUM — Lodestar uses `@chainsafe/ssz` which has different architecture, but similar optimization principles apply.
**Impact:** 🟡 MEDIUM — Epoch transitions are a known bottleneck.

---

### 12. SSZ Decoding Optimization
**Client:** Grandine
**What:** 5x faster `SignedBeaconBlock` decoding, 20x faster `BlobSidecar` decoding by optimizing byte collection implementations.
**Links:**
- [PR #167](https://github.com/grandinetech/grandine/pull/167) — Optimize SSZ decoding (merged)
- Motivated by [ghiliweld/ssz-arena](https://github.com/ghiliweld/ssz-arena) benchmarks

**Feasibility for Lodestar:** HIGH — Can benchmark Lodestar's SSZ and identify similar hotspots. The ssz-arena repo provides benchmarks.
**Impact:** 🟡 MEDIUM — Better block processing performance.

---

### 13. Cached Target State for Attestation Aggregation
**Client:** Grandine
**What:** Use cached target state when converting attestations for aggregation in the attestation pool, avoiding expensive state lookups.
**Links:**
- [PR #510](https://github.com/grandinetech/grandine/pull/510) — Use cached target state (merged)

**Feasibility for Lodestar:** HIGH — Direct optimization, can be applied to Lodestar's attestation pool.
**Impact:** 🟢 LOW-MEDIUM — Reduces CPU usage during attestation processing.

---

### 14. Replace INTERVALS_PER_SLOT with Explicit Slot Component Times
**Client:** Lighthouse
**What:** Instead of dividing slots into equal intervals, use explicit timing for each slot component (block, attestation, aggregation). More precise control over slot timing.
**Links:**
- [PR #7944](https://github.com/sigp/lighthouse/pull/7944) — Merged, based on [consensus-specs#4476](https://github.com/ethereum/consensus-specs/pull/4476)

**Feasibility for Lodestar:** HIGH — Spec change, should be implemented for compliance.
**Impact:** 🟢 LOW — Spec compliance, enables better timing control.

---

### 15. jemalloc in Docker Images
**Client:** Teku
**What:** Install jemalloc allocator in Docker images for better memory management.
**Links:**
- [PR #10360](https://github.com/Consensys/teku/pull/10360) — Install jemalloc (merged)

**Feasibility for Lodestar:** N/A — Node.js has its own V8 memory management. Not directly applicable but could explore `--max-old-space-size` tuning or alternative allocators for native addons.
**Impact:** 🟢 LOW

---

## 🔮 Forward-Looking / Upcoming Fork Features

### 16. FOCIL (Fork-Choice Inclusion Lists) — EIP-7805
**Client:** Multiple (confirmed for Hegotá upgrade, late 2026)
**What:** Anti-censorship mechanism. A committee of validators provides inclusion lists that block builders must respect.
**Status:** Locked for Hegotá. Client teams at milestone 2 of 6.
**Links:**
- [EIP-7805](https://eips.ethereum.org/EIPS/eip-7805)
- [Lighthouse blog on Glamsterdam preferences](https://blog.sigmaprime.io/glamsterdam-eip-preferences.html)

**Feasibility for Lodestar:** MEDIUM — Will need to implement eventually. Starting early = competitive advantage.
**Impact:** 🔴 HIGH — Required fork feature.

---

### 17. EIP-7495 / EIP-7688: StableContainer / Forward-Compatible Data Structures
**Client:** Nimbus (leading)
**What:** Forward-compatible SSZ containers that avoid breaking changes across forks. Nimbus has implemented `ProgressiveContainer` SSZ tests.
**Links:**
- [Nimbus #7417](https://github.com/status-im/nimbus-eth2/pull/7417) — ProgressiveContainer SSZ tests
- [Nimbus #7425](https://github.com/status-im/nimbus-eth2/pull/7425) — EIP-7495 SSZ ProgressiveContainer impl
- Nimbus branches: `feat/eip-7495`, `eip-7688`, `feat/eip-6493`

**Feasibility for Lodestar:** MEDIUM — SSZ library changes needed. @chainsafe/ssz would need StableContainer support.
**Impact:** 🟡 MEDIUM — Future-proofing, reduces fork complexity long-term.

---

### 18. Trustless Payments (ePBS Extension)
**Client:** Lighthouse (opinion published), multiple clients discussing
**What:** Enshrined mechanism for validator-to-builder trustless block building payments. Introduces builder-validators who can build blocks altruistically for other validators.
**Links:**
- [Lighthouse blog](https://blog.sigmaprime.io/lighthouse-trustless-payments.html) — Majority supports inclusion in Glamsterdam

**Feasibility for Lodestar:** MEDIUM — Will be part of ePBS or next fork. Lodestar already implementing ePBS.
**Impact:** 🔴 HIGH — Core protocol feature for censorship resistance.

---

### 19. Nimbus New Syncing Algorithm
**Client:** Nimbus
**What:** Complete rework of the sync algorithm with adaptive behavior based on finalization distance and wall sync distance. Different strategies for forward sync, head tracking, and backfill.
**Links:**
- [PR #7578](https://github.com/status-im/nimbus-eth2/pull/7578) — New syncing algorithm (merged Oct 2025)
- Detailed algorithm: Status updates per sync phase, by-root requests when close to head, by-range when far behind

**Feasibility for Lodestar:** MEDIUM — Significant but well-documented. Could improve Lodestar's sync which has known issues.
**Impact:** 🟡 MEDIUM — Better sync performance and reliability.

---

## 📋 Summary: Top Recommendations for Lodestar

| # | Feature | Impact | Feasibility | One Dev? | Priority |
|---|---------|--------|-------------|----------|----------|
| 1 | **Fast Confirmation Rule** | 🔴 Very High | High (already started) | ✅ Yes | **P0** |
| 2 | **Eager Attestation via SSE** | 🟡 Medium | High | ✅ Yes | **P1** |
| 3 | **Late Block Reorg** | 🟡 Medium | Medium | ✅ Yes | **P1** |
| 4 | **Batch Slashing Checks** | 🟡 Medium | High | ✅ Yes | **P1** |
| 5 | **ERA File Support** | 🟡 Medium | Medium | ✅ Yes | **P2** |
| 6 | **zkVM State Verification** | 🔴 Very High | Low | ❌ No | **Research** |
| 7 | **State Delta Encoding** | 🔴 High | Medium | ⚠️ Maybe | **P1** |
| 8 | **Safe Non-Finalized Checkpoint Sync** | 🔴 High | Medium-High | ✅ Yes | **P1** |
| 9 | **SSZ Decode Optimization** | 🟡 Medium | High | ✅ Yes | **P2** |
| 16 | **FOCIL (EIP-7805)** | 🔴 High | Medium | ⚠️ Maybe | **P1 (future)** |

### Top Pick for "One Developer with AI Assistance":
**Fast Confirmation Rule** — Already started in Lodestar, Nimbus has ~10 PRs to reference, well-specced, CL-only, massive user impact. This should be the priority project.

**Runner-up:** **Eager Attestation via SSE Head Events** — Quick win, high impact per effort, improves validator performance with minimal risk.
