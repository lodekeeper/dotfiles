# Ethereum Community Wishlist — Consensus Layer Improvements

*Researched: 2026-02-28*
*Sources: ethresear.ch, r/ethstaker, conference talks, researcher blogs, EIPs, EF strawmap*

---

## Table of Contents
1. [FOCIL — Fork-Choice Enforced Inclusion Lists](#1-focil--fork-choice-enforced-inclusion-lists)
2. [ePBS — Enshrined Proposer-Builder Separation](#2-epbs--enshrined-proposer-builder-separation)
3. [Based Preconfirmations](#3-based-preconfirmations)
4. [Faster Finality (3SF / Minimmit)](#4-faster-finality-3sf--minimmit)
5. [Beam Chain / Lean Consensus (Full CL Redesign)](#5-beam-chain--lean-consensus-full-cl-redesign)
6. [Post-Quantum Cryptography](#6-post-quantum-cryptography)
7. [ZK-Related CL Improvements](#7-zk-related-cl-improvements)
8. [Light Client & Portal Network Improvements](#8-light-client--portal-network-improvements)
9. [Faster Slot Times](#9-faster-slot-times)
10. [Solo Staker & Validator UX Improvements](#10-solo-staker--validator-ux-improvements)
11. [Performance Improvements (Sync, Memory, State)](#11-performance-improvements-sync-memory-state)
12. [PeerDAS Optimization](#12-peerdas-optimization)
13. [Privacy (Shielded Transfers)](#13-privacy-shielded-transfers)

---

## 1. FOCIL — Fork-Choice Enforced Inclusion Lists

**EIP:** [EIP-7805](https://eips.ethereum.org/EIPS/eip-7805) (Draft)
**Status:** 🟢 **Scheduled for Inclusion** — Headline CL feature for **Hegotá upgrade (late 2026)**
**Authors:** Thomas Thiery (soispoke), Francesco D'Amato, Julian Ma, Barnabé Monnot, Terence Tsao, Jacob Kaufmann, Jihoon Song

### What It Is
A committee-based, fork-choice enforced inclusion list mechanism. Per slot, 16 randomly selected validators each build and broadcast an inclusion list (IL) of transactions from the public mempool (max 8 KiB each). The block proposer must include those transactions, and attesters only vote for blocks that satisfy all collected ILs. This is "wired into the fork-choice rule" — not a social norm.

### Why It Matters
- **Censorship resistance hardened at protocol level.** Today, a few sophisticated builders dominate block production; they can refuse to include certain transactions. FOCIL removes builder veto power.
- **Only requires 1-of-N honesty** among IL committee members for the mechanism to work.
- **Synergy with Account Abstraction (EIP-8141/7701)** — Vitalik highlighted that "with FOCIL and 8141 together, anything, including smart wallet txs, gas sponsored txs, and even privacy protocol txs, can be included onchain through one of 17 different actors."
- Bankless called it "one of [Ethereum's] most consequential protocol decisions yet."

### Spec Maturity
- Full EIP spec exists with CL and EL workflow defined
- Consensus specs PRs in progress
- Multiple resources: ethresear.ch post, FOCIL CL/EL workflow doc, resource design considerations
- Implementation tracker: [meetfocil.eth.limo](https://meetfocil.eth.limo/)

### Client Implementation Progress (from tracker)
- **Lodestar:** Started ✅ (milestone 1-2 of 6)
- Prysm, Teku, Lighthouse, Nimbus, Grandine: All started
- Geth, Nethermind, Reth, Besu, Erigon: All started
- Currently between "Started" and "Interop/Local Devnets" stage

### Feasibility for Lodestar
**HIGH.** Lodestar has already started implementation. This is the next CL hard fork feature — it's mandatory work. Heavy CL changes: new gossip topics, IL building/validation, fork-choice changes, Engine API modifications (engine_getInclusionListV1, modified forkchoiceUpdated).

### Excitement Level: 🔥🔥🔥🔥🔥 (Maximum — it's shipping)

---

## 2. ePBS — Enshrined Proposer-Builder Separation

**EIP:** [EIP-7732](https://eips.ethereum.org/EIPS/eip-7732)
**Status:** 🟢 **Scheduled for Inclusion** — Headline CL feature for **Glamsterdam upgrade (H1 2026)**
**Context:** Consensus layer-only upgrade

### What It Is
Formally embeds the separation of block proposal and block building into the consensus layer. Currently, PBS is handled "out of protocol" via MEV-boost relays. ePBS removes the dependency on trusted relays by enshrining the proposer-builder relationship in the protocol itself.

### Why It Matters
- **Eliminates relay trust assumption** — today relays are a single point of failure
- **Improves validator decentralization** — proposers don't need to trust external software
- **Reduces MEV centralization risks** at the protocol level
- **Foundation for FOCIL** — ePBS and FOCIL are complementary (ePBS for Glamsterdam, FOCIL for Hegotá)

### Spec Maturity
- Full EIP spec with consensus-specs PR (#3828)
- Selected as Glamsterdam headliner (August 2025)
- Academic analysis: SoK paper (June 2025)

### Feasibility for Lodestar
**HIGH (mandatory).** This is the headliner for the next upgrade after Fusaka. All CL clients must implement. Significant consensus layer changes: split block into consensus and execution parts, new proposer-builder negotiation mechanism.

### Excitement Level: 🔥🔥🔥🔥🔥 (Shipping in Glamsterdam)

---

## 3. Based Preconfirmations

**Origin:** [ethresear.ch post by Justin Drake](https://ethresear.ch/t/based-preconfirmations/17353) (Nov 2023)
**Status:** 🟡 Active research, some out-of-protocol implementations exist (Bolt, mev-commit)

### What It Is
Proposers (validators) make signed commitments to include specific transactions in their upcoming block, providing ~100ms confirmations for L2 (based rollup) transactions. Requires two pieces of infrastructure:
1. **Proposer slashing** — ability to penalize broken commitments
2. **Proposer lookahead** — knowing who proposes upcoming blocks (partially addressed by EIP-7917 in Fusaka)

### Why It Matters
- **Competitive UX for based rollups** — makes L2s built on L1 sequencing viable with fast confirmations
- **Revenue for validators** — preconf fees create new income for proposers
- **Reduces L2 fragmentation** — based rollups inherit L1 security without centralized sequencers
- Very hot topic in the ecosystem; multiple teams building (Bolt by Chainbound, mev-commit by Primev, Luban, etc.)

### Spec Maturity
- No formal EIP yet for the protocol-level changes
- EIP-7917 (deterministic proposer lookahead) shipped in Fusaka is a prerequisite
- Bolt has a constraints-API and sidecar implementation
- LimeChain has detailed research docs
- Still mostly out-of-protocol; protocol-level support is Beam Chain territory

### Feasibility for Lodestar
**MEDIUM.** Out-of-protocol preconfs (like Bolt sidecar) can work with any CL client today. Protocol-level preconf support is Beam Chain scope (2027+). Lodestar could:
- Support Bolt-style sidecar integration (near term)
- Implement proposer commitment APIs
- Be a testbed for preconf experimentation given TypeScript's flexibility

### Excitement Level: 🔥🔥🔥🔥 (Hot research topic, but protocol integration is years away)

---

## 4. Faster Finality (3SF / Minimmit)

**Status:** 🟡 Active research — targeted for ~2028-2029 in strawmap
**Key paper:** [3-Slot-Finality Protocol for Ethereum](https://arxiv.org/abs/2411.00558) (Nov 2024)

### What It Is
Reducing Ethereum's finality from ~16 minutes to seconds. Two approaches:
1. **3-Slot Finality (3SF):** Partially synchronous finality gadget reaching finality in 3 slots (~36 seconds at current pace)
2. **Minimmit:** One-round BFT-style consensus algorithm enabling finality in a single slot (target: 6-16 seconds)

### Why It Matters
- **Critical for UX** — 16 minutes is unacceptable for many use cases (bridges, exchanges, DeFi)
- **Reduces reorg risk** — faster finality = less opportunity for chain reorganizations
- **Strawmap "north star"** — listed as one of five core goals in the EF's Feb 2026 strawmap
- Vitalik: finality target is "seconds by 2029"

### Spec Maturity
- Academic papers published (3SF, SSF analysis)
- Lean Consensus roadmap shows "Faster Finality" at 50% progress
- Part of the Beam Chain / Lean Consensus redesign
- Not yet at EIP stage — still in research/specification phase

### Feasibility for Lodestar
**LOW (near-term), HIGH (long-term).** This is fundamental consensus redesign — part of Beam Chain. When it ships, every CL client must implement. Pre-work that Lodestar could do:
- Research and prototype 3SF finality gadgets
- Contribute to specification work
- Prepare for reduced slot times (networking, attestation aggregation)

### Excitement Level: 🔥🔥🔥🔥🔥 (Top priority per strawmap)

---

## 5. Beam Chain / Lean Consensus (Full CL Redesign)

**Status:** 🟡 Speccing phase (2025-2026 per timeline)
**Origin:** Justin Drake's Devcon SEA keynote (Nov 2024)
**Roadmap:** [leanroadmap.org](https://leanroadmap.org/)

### What It Is
A complete redesign of Ethereum's consensus layer, now called "Lean Consensus." Key changes:
1. **SNARKs for chain verification** — ZK proofs for consensus state transitions
2. **Post-quantum cryptography** — hash-based signatures replacing BLS
3. **Reduced staking requirement** — from 32 ETH down to potentially 1 ETH
4. **Faster finality** — seconds instead of minutes
5. **Improved MEV handling** — protocol-level solutions
6. **Post-quantum signature aggregation** using zkVMs
7. **Attester-Proposer Separation** — protocol-level role separation
8. **Modernized P2P networking** — Gossipsub v2.0, set reconciliation

### Key Research Tracks (from leanroadmap.org)
| Track | Progress | Notes |
|-------|----------|-------|
| Hash-Based Multi-Signatures | 70% | Winternitz XMSS as PQ replacement for BLS |
| Post-Quantum Sig Aggregation with zkVMs | 50% | Exploring minimal zkVMs for sig aggregation |
| Poseidon Cryptanalysis Initiative | 50% | Security testing of Poseidon hash |
| Formal Verification | 40% | Lean 4 framework proofs for FRI, STU, WHIR |
| P2P Networking | 30% | Gossipsub v2.0, 4-second block times support |
| Attester-Proposer Separation | 20% | Reducing centralization in block production |
| Faster Finality | 50% | 3SF research |

### Timeline
- **2025:** Specification development
- **2026:** Client implementation
- **2027:** Comprehensive testing
- Two teams committed: ZIM (Zig, India), Lambda Class (South America)

### Feasibility for Lodestar
**VERY HIGH relevance.** Lodestar-Z (the Zig implementation) is directly aligned with Beam Chain's vision. The Lodestar team is already building a Zig-based CL client. This positions Lodestar uniquely:
- Zig is one of the languages being used for Beam Chain clients (ZIM team)
- Lodestar could be an early implementer of Lean Consensus specs
- The TypeScript side could serve as a rapid prototyping environment

### Excitement Level: 🔥🔥🔥🔥🔥 (Existential-level importance for CL clients)

---

## 6. Post-Quantum Cryptography

**Status:** 🟡 Active research — Vitalik outlined detailed roadmap (Feb 26, 2026)
**Strawmap target:** One of five "north stars"

### What It Is
Replacing quantum-vulnerable cryptographic primitives across Ethereum:
1. **Consensus signatures:** BLS → hash-based (Winternitz XMSS) + STARK aggregation
2. **Data storage (KZG → STARKs):** Replace KZG commitments for blob verification
3. **User account signatures:** Support PQ-safe signing schemes
4. **ZK proofs:** Ensure proof systems remain secure against quantum

### Why It Matters
- **Existential threat mitigation** — quantum computers could break BLS and ECDSA
- **Proactive vs reactive** — better to prepare now than emergency-patch later
- **Signature size challenge** — hash-based signatures are much larger than BLS; aggregation via STARKs is key research

### Spec Maturity
- leanSig and leanMultisig benchmarks actively tracked on leanroadmap.org
- Cryptanalysis bounties running for Poseidon hash
- No EIP yet — part of Beam Chain scope
- Vitalik's Feb 2026 blog post provides detailed technical roadmap

### Feasibility for Lodestar
**MEDIUM-HIGH.** Near-term opportunities:
- Research and prototype hash-based signature verification
- Implement STARK-based signature aggregation proof-of-concept
- Help with specification work for PQ consensus signatures

### Excitement Level: 🔥🔥🔥🔥 (Growing urgency, Vitalik just published detailed plan)

---

## 7. ZK-Related CL Improvements

**Status:** 🟡 Various stages of research

### What It Is
Several ZK applications for the consensus layer:
1. **ZK proofs for light clients** — SNARK proofs of sync committee signatures (replacing direct sig verification)
2. **ZK-SNARKs for state transitions** — prove beacon state transitions without re-executing
3. **ZK-EVM verification** — enshrining ZK proofs for L1 block verification
4. **zkVM-based consensus** — Beam Chain's vision of validators choosing their zkVM

### Why It Matters
- **Light client security** — ZK proofs provide stronger guarantees than sync committee trust
- **Stateless validation** — nodes could verify blocks without maintaining full state
- **Reduced hardware requirements** — verify proofs instead of re-executing
- **Bridge security** — ZK proofs of CL state enable trustless cross-chain bridges

### Spec Maturity
- Beam Chain envisions zkVM-based consensus as core feature
- Helios (a]16z) already uses ZK for light client verification
- SP1/Succinct has Ethereum ZK proving work
- Still research-phase for protocol-level integration

### Feasibility for Lodestar
**MEDIUM.** Lodestar could:
- Implement ZK light client proofs (serve SNARK proofs alongside sync committee updates)
- Build tooling for ZK state transition verification
- TypeScript is good for prototyping ZK circuits and proof generation
- Lodestar-Z (Zig) could be optimized for proof generation/verification

### Excitement Level: 🔥🔥🔥 (Important but long timeline)

---

## 8. Light Client & Portal Network Improvements

**Status:** 🟡 Ongoing development
**Key resource:** [Portal Network blog on light clients](https://blog.ethportal.net/posts/light-clients)

### What It Is
Improving lightweight access to Ethereum:
1. **Consensus light client protocol** — already exists (sync committee based), serves block headers
2. **Portal Network** — P2P network for decentralized data access without trusting full nodes
3. **eth_getProof from Portal** — state proofs via decentralized P2P instead of trusted RPCs
4. **History expiry (EIP-4444)** — full nodes don't need to store all historical data

### Current State
- Consensus light client protocol works but only provides headers/sync committee data
- Still need full node for execution-layer queries (state, receipts, etc.)
- Portal Network is building DHT-based solutions for history, state, and beacon data
- Light clients rely on RPC today; Portal aims to decentralize this

### Why It Matters
- **Accessibility** — enables wallets, mobile apps, IoT, bridges to verify without full nodes
- **Decentralization** — reduces dependency on Infura/Alchemy for light access
- **EIP-4444 enabler** — Portal provides historical data so full nodes can expire it
- **Lodestar's strength** — Lodestar has historically emphasized light client support

### Feasibility for Lodestar
**HIGH.** This is a natural fit:
- Lodestar already has light client server support
- TypeScript enables browser-based light clients
- Could build Portal Network bridge/integration
- Could implement light client improvements ahead of other clients

### Excitement Level: 🔥🔥🔥 (Steady importance, not flashy)

---

## 9. Faster Slot Times

**Status:** 🟡 Strawmap priority — incremental rollout planned
**Vitalik's formula:** 12 → 8 → 6 → 4 → 3 → 2 seconds (sqrt(2) reductions)

### What It Is
Progressively reducing Ethereum's 12-second slot time. Requires:
- P2P networking upgrades (erasure-coded block propagation)
- Reduced attestation aggregation overhead
- Fewer attesters per slot (enabled by signature aggregation improvements)
- Tighter timing constraints for block building/validation

### Why It Matters
- **UX improvement** — faster confirmations for users
- **L2 latency** — based rollups benefit from faster L1 slots
- **Competitiveness** — Solana/other chains have sub-second blocks

### Spec Maturity
- Vitalik outlined the approach in detail (Feb 25, 2026)
- "sqrt(2) at a time" formula — each step gated by safety confidence
- First reduction (12→8s) could come in 1-2 years via hard fork
- Needs P2P networking research (erasure coding, Gossipsub v2.0)

### Feasibility for Lodestar
**HIGH.** Every CL client must handle faster slots. Lodestar challenges:
- Tighter timing budgets for attestation, block production
- Networking optimizations needed (TypeScript may face perf challenges)
- Lodestar-Z (Zig) would handle the performance-critical path

### Excitement Level: 🔥🔥🔥🔥 (Major UX win, clear roadmap)

---

## 10. Solo Staker & Validator UX Improvements

**Status:** 🟢 Partially addressed by Pectra (MaxEB), more wanted
**Community source:** r/ethstaker surveys, discussions

### What It Is
Making solo staking easier and more accessible:
1. **MaxEB (EIP-7251)** — shipped in Pectra, allows up to 2048 ETH per validator (consolidation)
2. **Lower staking minimum** — Beam Chain targets 1 ETH minimum (from 32 ETH)
3. **DVT (Distributed Validator Technology)** — split validator across multiple operators
4. **Better monitoring/dashboards** — many stakers want better native tooling
5. **Client diversity pressure** — stakers want switching to be easy and low-risk
6. **Reduced maintenance burden** — "set and forget" is the dream

### Community Sentiment (r/ethstaker)
- Yield concerns: 2.5-3% APY questioned vs. risk/effort
- "Is home staking worth it?" — common question, risk of losing ETH via slashing scares people
- Hardware requirements growing (2TB+ SSD, 32GB RAM recommended)
- Client switching is stressful — fear of double-signing/slashing
- SSV Network and DVT seen as risk reduction
- 2025 staking survey conducted — focus on client diversity and staker experience

### Feasibility for Lodestar
**HIGH.** Lodestar can differentiate by:
- Best-in-class validator UX (dashboard, monitoring, alerts)
- Easy client switching tooling
- TypeScript-based web dashboard (natural advantage)
- Lower memory footprint targets
- Documentation and onboarding improvements

### Excitement Level: 🔥🔥🔥 (Steady demand, not protocol-change level)

---

## 11. Performance Improvements (Sync, Memory, State)

**Status:** 🟢 Ongoing for all CL clients
**Sources:** Client comparison guides, Lodestar blog posts

### What It Is
Making CL clients faster and lighter:
1. **Sync speed** — checkpoint sync already helps, but range sync can be slow
2. **Memory footprint** — Lodestar historically uses more RAM than Lighthouse/Nimbus
3. **SSZ performance** — Lodestar's SSZ library has been heavily optimized (persistent Merkle trees)
4. **State management** — efficient beacon state caching and transitions
5. **Attestation processing** — needs to be fast, especially with more validators

### Why It Matters
- **Solo staker accessibility** — lower requirements = more solo stakers
- **Client diversity** — if Lodestar is "slow" or "heavy", people won't switch to it
- **Future-proofing** — faster slots, more blobs, PeerDAS all increase perf demands

### Lodestar-Specific Context
- Team has been reducing memory footprint via SSZ refactors (persistent Merkle trees)
- SSZ-over-HTTP (replacing JSON) improves BN↔VC communication
- Lodestar-Z (Zig) aims for native-speed performance
- BLST-Z integration for fast BLS verification
- Community perception: "solid stability and high attestation efficiency" but "seems to use more RAM than Lighthouse"

### Feasibility for Lodestar
**VERY HIGH.** This is bread-and-butter work:
- Ongoing Zig-based optimization (BLST-Z, SSZ persistent trees)
- Memory profiling and reduction
- Sync speed improvements
- These improvements compound over time

### Excitement Level: 🔥🔥🔥 (Essential but not glamorous)

---

## 12. PeerDAS Optimization

**Status:** 🟢 Shipped in Fusaka (Dec 2025), ongoing optimization
**EIP:** EIP-7594

### What It Is
Peer Data Availability Sampling — nodes no longer need to download all blob data. Blobs are distributed across the network using erasure coding. Theoretical 8x blob capacity increase.

### Why It Matters
- **Foundation for data scaling** — enables L2s to post much more data
- **Reduced node requirements** — nodes store less data
- **Prerequisite for Danksharding** — PeerDAS is step 1

### Feasibility for Lodestar
**HIGH.** Already shipped but optimization opportunities remain:
- Sampling efficiency
- Network overhead reduction
- Custody and reconstruction performance
- Interaction with increased blob count targets

### Excitement Level: 🔥🔥🔥 (Already live, optimization phase)

---

## 13. Privacy (Shielded Transfers)

**Status:** 🟡 Strawmap "north star" — early research
**Context:** Synergy with FOCIL for censorship-resistant private transactions

### What It Is
Built-in privacy for ETH transfers at the protocol level. Shielded transfers would hide sender, receiver, and amount from public view on-chain.

### Why It Matters
- **Privacy as a right** — all Ethereum transactions are currently fully transparent
- **Censorship resistance complement** — FOCIL ensures inclusion, privacy ensures you can't be targeted
- **Competitive necessity** — other chains (Zcash, Aztec on Ethereum L2) offer privacy

### Feasibility for Lodestar
**LOW (near-term).** Privacy is primarily an EL concern. CL involvement would be:
- Supporting inclusion of private transactions in blocks
- FOCIL integration with privacy protocols
- Longer-term protocol changes

### Excitement Level: 🔥🔥🔥🔥 (Strawmap north star, but early)

---

## Summary: Priority Matrix for Lodestar

### 🔴 Must-Do (Shipping in next 2 forks)
| Feature | Fork | Timeline | CL Impact |
|---------|------|----------|-----------|
| **ePBS (EIP-7732)** | Glamsterdam | H1 2026 | Major — consensus restructuring |
| **FOCIL (EIP-7805)** | Hegotá | Late 2026 | Major — new gossip, fork-choice, Engine API |

### 🟡 Should Invest In (1-3 year horizon)
| Feature | Why Lodestar Should Care |
|---------|------------------------|
| **Faster Slot Times** | Every client must adapt; Zig path critical for perf |
| **Performance / Memory** | Competitive necessity; Zig work ongoing |
| **Light Client Improvements** | Lodestar's historical strength; TypeScript advantage |
| **Based Preconf Support** | Sidecar integration possible now; proposer commitment APIs |
| **Beam Chain / Lean Consensus** | Lodestar-Z positioning; early implementation opportunity |

### 🟢 Research & Position (3+ year horizon)
| Feature | Notes |
|---------|-------|
| **Faster Finality (3SF/Minimmit)** | Fundamental research; contribute to specs |
| **Post-Quantum Cryptography** | Hash-based sig verification prototypes |
| **ZK CL Proofs** | ZK light clients, state transition proofs |
| **Privacy (Shielded Transfers)** | Mostly EL; support via FOCIL |

---

## The Strawmap Context (BREAKING — Feb 25, 2026)

Just 3 days ago, the Ethereum Foundation published the ["strawmap"](https://strawmap.org) — a comprehensive draft roadmap through 2029 covering seven hard forks. This is the most concrete long-range plan Ethereum has ever published.

### Five "North Stars"
1. **Fast L1** — finality in seconds, slot times down to 2s
2. **Gigagas L1** — ~10,000 TPS on base layer
3. **Teragas L2** — ~10M TPS for rollups
4. **Post-Quantum** — hash-based signatures, STARK aggregation
5. **Privacy** — shielded ETH transfers

### Three Strategic Tracks (for Glamsterdam and beyond)
1. **Scale** — increase throughput, reduce costs
2. **Improve UX** — developer and user experience
3. **Harden L1** — security, censorship resistance, decentralization

### Planned Fork Sequence
1. **Glamsterdam** (H1 2026) — ePBS headliner, gas limit increases, block-level access lists
2. **Hegotá** (Late 2026) — FOCIL headliner, deferred Glamsterdam items, state/history expiry
3. **[Fork 3-7]** (2027-2029) — Lean Consensus components, faster finality, PQ crypto, privacy

This strawmap fundamentally shapes what CL clients should prioritize. **Lodestar's immediate priority is ePBS (Glamsterdam) and FOCIL (Hegotá). Everything else feeds into either Lodestar-Z positioning or research contributions.**
