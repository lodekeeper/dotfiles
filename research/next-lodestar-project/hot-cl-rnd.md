# Hot Consensus Layer R&D — February 2026

*Research date: 2026-02-28*

This document captures what's currently exciting and actively moving in Ethereum consensus layer (CL) R&D, with an eye toward high-impact PoC/experimental features for Lodestar.

---

## Context: The Current Landscape

The Ethereum ecosystem is in an **extremely active CL R&D phase**:
- **Strawmap** published Feb 25, 2026 by Justin Drake (strawmap.org) — outlines 7 forks through 2029
- **Glamsterdam** (next fork, H1 2026): CL headliner = **ePBS** (EIP-7732), EL headliner = BALs (EIP-7928)
- **Hegotá** (H2 2026): CL headliner = **FOCIL** (EIP-7805), EL headliner = TBD (LUCID vs Frame Txs vs none)
- **Lean Consensus** (formerly "Beam Chain"): long-term redesign targeting post-quantum, faster finality, simpler CL
- Five "north stars": Fast L1, Gigagas L1, Teragas L2, Post-Quantum L1, Private L1

**Lodestar's current state**: Already has ePBS implementation (`feat: implement epbs block production #8838`), ePBS devnet-0 branches, 6s slot branch (`feat/eip7782-6s-slots`), FOCIL branch exists on fork. Interop testing for ePBS devnet-0 scheduled March 4 with Lodestar + Lighthouse.

---

## 🔥 Finding 1: FOCIL — Fork-Choice Enforced Inclusion Lists (EIP-7805)

### What it is
A committee-based mechanism to force transaction inclusion and prevent censorship. Each slot, a random committee of ~16 validators builds inclusion lists (ILs) from the public mempool. The proposer must include transactions from all collected ILs. Attesters only vote for blocks that satisfy IL conditions.

### Why it matters
- **THE Hegotá CL headliner** — confirmed at ACDC #175 (Feb 19, 2026)
- Directly addresses Ethereum's censorship resistance crisis (builder dominance, OFAC compliance filtering)
- Vitalik explicitly backing it: "Ethereum is going hard"
- Synergy with EIP-8141 (account abstraction) — together they guarantee rapid inclusion for ANY transaction type
- Critical for the "cypherpunk" Ethereum vision

### Spec/EIP status
- **EIP-7805** — DRAFT, full spec exists in consensus-specs (`specs/_features/eip7805/`)
- Authors: Thomas Thiery (soispoke), Francesco D'Amato, Julian Ma, Barnabé Monnot, Terence Tsao, Jacob Kaufmann, Jihoon Song
- Ethresear.ch posts with detailed design: FOCIL CL & EL workflow
- Already has spec in consensus-specs repo

### Feasibility for single implementer + Codex sub-agents
**HIGH** — Well-specified, clearly scoped CL change. Core pieces:
1. New IL committee selection logic (beacon state accessor)
2. New gossip topic for IL messages + P2P validation rules  
3. Modified fork-choice: blocks that don't satisfy ILs get filtered
4. Attester logic: verify IL satisfaction before voting
5. Builder/proposer: collect ILs and include transactions

A branch already exists in the Lodestar fork (`remotes/fork/focil`). This is the next thing to implement after ePBS lands.

### Excitement/Impact: ⭐⭐⭐⭐⭐ (10/10)
This is THE most important CL feature for 2026. Being ahead on FOCIL implementation would be a massive win for Lodestar. It's the direct follow-up to ePBS (which is landing in Glamsterdam).

---

## 🔥 Finding 2: Slot Time Reduction (12s → 8s → 6s → 4s → 2s)

### What it is
Incremental reduction of Ethereum's slot time from 12 seconds toward 2 seconds, following a "sqrt(2) at a time" formula proposed by Vitalik. The first step (12→8s) is the most impactful and most feasible near-term.

### Why it matters
- Core to the "Fast L1" north star
- Each reduction directly improves user experience (faster confirmations)
- 12→8s alone would be a ~33% improvement in block time
- Requires fundamental P2P layer improvements: erasure coding for block propagation
- Tightens timing constraints when combined with ePBS/FOCIL (safe latency window shrinks from 1/3 to 1/5 of slot)
- Lodestar already has a branch: `feat/eip7782-6s-slots` — so some work exists

### Spec/EIP status
- **EIP-7782** — draft for 6-second slots, exists as a Lodestar branch
- Strawmap outlines the progression but no single EIP covers the full path
- Requires p2p layer changes (erasure coding) — work by @raulvk
- Research by Roberto Saltini on timing game analysis

### Feasibility for single implementer + Codex sub-agents
**MEDIUM-HIGH** — The first step (12→8s) is mostly configuration + timing changes in the CL client, but needs extensive testing. The harder part is the P2P layer (erasure coding, gossip optimization). Could prototype the CL timing changes independently.

Key implementation tasks:
1. Parameterize SECONDS_PER_SLOT throughout the codebase
2. Adjust attester/proposer timing windows
3. Update fork-choice timing assumptions
4. Benchmark: can Lodestar process/validate blocks in <2-3s consistently?
5. P2P: implement erasure-coded block propagation

### Excitement/Impact: ⭐⭐⭐⭐⭐ (9/10)
Extremely high impact but requires coordination. A PoC showing Lodestar running at 8s slots on a devnet would be very impressive. Already have the 6s-slots branch as a starting point.

---

## 🔥 Finding 3: Minimmit — Fast Finality Algorithm

### What it is
A new Byzantine-fault-tolerant SMR protocol that decouples view progression from finality, using different quorum thresholds. Achieves 2-round finality (proposal + one voting round) under `5f+1 ≤ n` assumption. Targets reducing Ethereum finality from ~16 minutes to as low as 8 seconds.

### Why it matters
- Paper published Jan 2026 on arXiv (2508.10862) — extremely fresh research
- Central to the strawmap's "Fast L1" vision
- 23.1% reduction in view latency, 10.7% reduction in transaction latency vs state-of-the-art
- Would completely replace Gasper (current consensus) over time
- Vitalik's projected trajectory: 16min → 10m40s → 6m24s → 1m12s → 48s → 16s → 8s

### Spec/EIP status
- **Academic paper** on arXiv — NOT yet an EIP
- Being developed as part of Lean Consensus / leanSpec
- 3SF (3-Slot Finality) is the stepping stone — ethresear.ch post from Nov 2024
- leanSpec repository has 3SF-mini implementation in Python

### Feasibility for single implementer + Codex sub-agents
**LOW-MEDIUM** — This is a full consensus algorithm replacement. Very complex, but a PoC implementation of 3SF-mini (the simpler version used in Lean Consensus devnets) would be feasible. The leanSpec Python code could serve as reference.

Tasks for a PoC:
1. Implement 3SF-mini state transition in TypeScript
2. Create a standalone simulator/testnet
3. Benchmark finality times vs current Gasper
4. Could be a separate module/library, not integrated into Lodestar mainline

### Excitement/Impact: ⭐⭐⭐⭐⭐ (10/10 for impact, but 5/10 for near-term feasibility)
This is THE future of Ethereum consensus. Having a 3SF PoC in TypeScript would be groundbreaking for Lodestar. But it's a massive undertaking.

---

## 🔥 Finding 4: EIP-8025 — Stateless Validation via Execution Proofs

### What it is
Enables stateless validation of execution payloads through zk execution proofs. Validators can verify blocks without maintaining full EL state — they just verify a proof. Part of the zkEVM attester client initiative.

### Why it matters
- Directly reduces validator hardware requirements (no need to store full state)
- Key enabler for decentralization (more validators can participate)
- Already in consensus-specs! (`specs/_features/eip8025/`)
- Tests were just enabled: `Enable tests for EIP-8025 (#4911)` — very recent
- Ansgar Dietrichs leading this at EF as part of the Scale track
- First L1-zkEVM workshop was Feb 11, 2026

### Spec/EIP status
- **EIP-8025** — DRAFT, spec in consensus-specs (built on Fulu)
- New containers: `PublicInput`, `ExecutionProof`, `SignedExecutionProof`
- Modifies `process_block` and `process_execution_payload`
- New: `process_execution_proof` function
- Tests recently enabled in specs

### Feasibility for single implementer + Codex sub-agents
**MEDIUM** — The CL side (accepting and validating proofs, modified block processing) is well-defined in the spec. The hard part is generating the proofs (that's the EL/prover side). But implementing the CL consumer of proofs is very doable.

**WE ARE ALREADY WORKING ON THIS** — the `feat/eip8025-optional-proofs` branch exists in our Lodestar worktree (`~/lodestar-eip8025`). This is actively being developed.

Tasks:
1. Implement `process_execution_proof` in beacon chain state transition
2. New p2p gossip topic for execution proofs
3. Modified attestation logic (can attest without full EL validation if proof is available)
4. Integration with proof-engine types

### Excitement/Impact: ⭐⭐⭐⭐ (8/10)
Very exciting and we're already on it. Being the first CL client with working EIP-8025 support would be a huge differentiator.

---

## 🔥 Finding 5: Lean Consensus / Post-Quantum Signatures

### What it is
A complete redesign of Ethereum's consensus layer for post-quantum security. Uses XMSS (eXtended Merkle Signature Scheme) hash-based signatures instead of BLS. Includes leanSig, leanMultisig for signature aggregation. Currently on pq-devnet-2 with multiple clients (ethlambda, etc.)

### Why it matters
- Quantum computing is treated as a concrete engineering problem, not hypothetical
- Strawmap includes PQ as one of 5 north stars
- Multiple clients already running on devnets (LambdaClass's ethlambda, others)
- Slot-level quantum resistance could arrive before finality-level protection
- Hash function options: Poseidon2, Poseidon1, or BLAKE3
- XMSS signatures are 3112 bytes (vs 96 bytes BLS) — aggregation is critical

### Spec/EIP status
- **leanSpec** — full Python spec at github.com/leanEthereum/leanSpec
- leanSig, leanMultisig — separate crypto libraries
- Active devnet progression: pq-devnet-0 through pq-devnet-4
- Not yet an EIP — part of Lean Consensus parallel track

### Feasibility for single implementer + Codex sub-agents
**LOW** — Building a full Lean Consensus client is a massive undertaking. But contributing specific components (like a TypeScript XMSS implementation or leanMultisig port) could be very valuable.

### Excitement/Impact: ⭐⭐⭐⭐ (8/10 for impact, 3/10 for near-term Lodestar feasibility)
Foundational long-term work. A TypeScript leanSig/leanMultisig library would be valuable for the ecosystem but may not directly benefit Lodestar's current position.

---

## 🔥 Finding 6: P2P Erasure Coding for Block Propagation

### What it is
Redesigning Ethereum's P2P gossip layer to use erasure coding — splitting blocks into 8 pieces where any 4 can reconstruct the full block. This dramatically reduces 95th percentile block propagation latency.

### Why it matters
- **Critical prerequisite** for shorter slots (12→8→6→4→2s)
- Without faster propagation, shorter slots compromise safety
- Work by @raulvk — active research
- Also enables PeerDAS improvements (same erasure coding principles)
- Part of the Lean Consensus P2P networking track (30% progress)
- Gossipsub v2.0 and set reconciliation also being researched

### Spec/EIP status
- Research-stage — no formal EIP yet
- Part of the Lean Consensus networking work
- Gossipsub v2.0 spec being developed

### Feasibility for single implementer + Codex sub-agents
**MEDIUM-HIGH** — Erasure coding libraries exist. The challenge is integrating into libp2p gossipsub. Lodestar just upgraded to libp2p v3 (`feat: libp2p v3 #8890`), which is a great foundation.

Tasks:
1. Implement Reed-Solomon erasure coding for beacon blocks
2. New gossip topic for block fragments
3. Block reconstruction from partial fragments
4. Benchmark: propagation latency improvement

### Excitement/Impact: ⭐⭐⭐⭐ (8/10)
Very high impact, relatively well-scoped. Being the first client with erasure-coded block propagation would be a significant innovation showcase.

---

## 🔥 Finding 7: EIP-6914 — Validator Index Reuse

### What it is
Allows new deposits to be assigned to existing validator records that have been fully withdrawn and are no longer active, instead of always growing the validator set.

### Why it matters
- Prevents unbounded growth of the validator registry
- Critical for long-term sustainability of the beacon state
- Simple, clean, well-defined change
- Good "low-hanging fruit" for client implementation

### Spec/EIP status
- **EIP-6914** — spec exists in consensus-specs (`specs/_features/eip6914/`)
- Very clean, minimal spec: `is_reusable_validator` predicate + modified `get_index_for_new_validator`
- Built on Capella (but could be rebased)

### Feasibility for single implementer + Codex sub-agents
**VERY HIGH** — Tiny, well-defined change. Could be implemented in a day.

### Excitement/Impact: ⭐⭐ (4/10)
Important but not exciting. Good for a quick PR but not a showcase project.

---

## 🔥 Finding 8: Attester-Proposer Separation (APS)

### What it is
Separates the roles of block proposers and attesters in consensus to reduce centralization pressures and enable more efficient MEV handling.

### Why it matters
- Complementary to ePBS — further decentralizes block production
- Part of Lean Consensus roadmap (20% progress)
- Reduces the computational burden on attesters (don't need to build blocks)
- Enables 256-1024 randomly selected attesters per slot (vs current ~thousands)
- Key enabler for shorter slots (less aggregation overhead)

### Spec/EIP status
- Research-stage, part of Lean Consensus
- No formal EIP yet
- Conceptually related to ePBS but goes further

### Feasibility for single implementer + Codex sub-agents
**LOW-MEDIUM** — This is a fundamental architectural change. A simulation/PoC could be built.

### Excitement/Impact: ⭐⭐⭐ (6/10)
Important for the long-term but not well-specified enough for immediate implementation.

---

## Summary & Recommendations

### Tier 1: Do This Now (High impact, high feasibility)
1. **FOCIL (EIP-7805)** — THE next CL headliner. Spec exists. Branch exists. Must be ahead on this.
2. **EIP-8025 (execution proofs)** — Already in progress. Finish it. First-mover advantage.

### Tier 2: Exciting PoC Projects (High impact, medium feasibility)
3. **8-second slots** — Build on existing 6s-slots branch. Demonstrate Lodestar can handle it.
4. **P2P erasure coding** — Independent module, great showcase. Enables shorter slots.

### Tier 3: Moonshot Research (Massive impact, lower feasibility)
5. **3SF-mini / Minimmit PoC** — TypeScript implementation of 3-slot finality. Would be incredible.
6. **Lean Consensus components** — TypeScript leanSig/leanMultisig crypto library.

### Fork Timeline (from strawmap.org)
| Fork | When | CL Headliner | EL Headliner |
|------|------|--------------|--------------|
| Glamsterdam (Gloas) | H1 2026 | ePBS (EIP-7732) | BALs (EIP-7928) |
| Hegotá | H2 2026 | FOCIL (EIP-7805) | TBD |
| I* | H1 2027 | TBD | TBD |
| J* | H2 2027 | TBD | TBD |
| K* | H1 2028 | TBD | TBD |
| L* | H2 2028 | Lean Consensus? | TBD |
| M* | 2029 | TBD | TBD |

### Key Sources
- [strawmap.org](https://strawmap.org) — The master roadmap
- [Minimmit paper](https://arxiv.org/abs/2508.10862) — Fast finality algorithm
- [3SF ethresear.ch](https://ethresear.ch/t/3-slot-finality-ssf-is-not-about-single-slot/20927) — 3-slot finality design
- [leanroadmap.org](https://leanroadmap.org) — Lean Consensus progress tracker
- [ACDC #175 notes](https://christinedkim.substack.com/p/acdc-175) — FOCIL confirmed for Hegotá
- [EIP-7805 FOCIL](https://eips.ethereum.org/EIPS/eip-7805) — Full spec
- [EIP-7732 ePBS](https://eips.ethereum.org/EIPS/eip-7732) — Full spec
- [EF 2026 Protocol Priorities](https://www.banklesstimes.com/articles/2026/02/19/ethereum-foundation-unveils-2026-protocol-priorities-update-outlining-three-tracks/) — Three-track framework
