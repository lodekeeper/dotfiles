# SSF, Shorter Slots & Consensus Improvements — Research Findings

**Date:** 2026-02-28
**Context:** Post EIP-7782 (6s slots) implementation in Lodestar. What's the next exciting CL project?

---

## 🔥 BREAKING: The Strawmap (Released Feb 25, 2026)

Justin Drake just published the **"Strawmap"** — a strawman roadmap for Ethereum L1 through 2029. This is THE authoritative context for what comes next.

- **Source:** [strawmap.org](https://strawmap.org)
- **Maintained by:** EF Architecture team (adietrichs, barnabemonnot, fradamt, drakefjustin)
- **Structure:** 7 forks through 2029, ~6-month cadence
- **Five "north stars":**
  1. **Fast L1** — finality in seconds
  2. **Gigagas L1** — 1 gigagas/sec (10K TPS) via zkEVMs
  3. **Teragas L2** — 1 GB/sec via data availability sampling
  4. **Post-quantum L1** — hash-based cryptographic schemes
  5. **Private L1** — shielded ETH transfers

### Fork Timeline:
| Fork | Timing | CL Headliner | EL Headliner |
|------|--------|--------------|--------------|
| **Glamsterdam** | Mid-2026 | ePBS (EIP-7732) | BALs (Block Access Lists) |
| **Hegotá** | Late 2026 | FOCIL (EIP-7805) likely | TBD |
| **I*** | ~2027 | Shorter slots? / Lean consensus steps | TBD |
| **J*** | ~2027 | Further consensus changes | TBD |
| **...through L*** | ~2028-2029 | Lean consensus (big switch) | zkEVM |

### Vitalik's Comments on the Strawmap (Feb 25, 2026):
- **Slot time reduction:** "sqrt(2) at a time" formula: 12 → 8 → 6 → 4 → 3 → 2
- **Finality trajectory:** 16m (today) → 10m40s (8s slots) → 6m24s (one-epoch finality) → 1m12s (8-slot epochs, 6s slots) → 48s (4s slots) → 16s (Minimmit) → 8s (aggressive Minimmit)
- **Random attester sampling:** "~256-1024 randomly selected attesters sign on each slot" to remove aggregation phase
- **"Ship of Theseus"** approach: component-by-component replacement of consensus

---

## Research Ideas Ranked by Excitement & Feasibility

### 1. 🟢 One-Epoch Finality (Reduce EPOCHS_PER_ETH1_VOTING to 1)
**Description:** Change from 2-epoch (64-slot) finality to 1-epoch (32-slot) finality. This is the simplest step on Vitalik's finality trajectory.

**Motivation:** Cuts finality from ~16 min to ~6.4 min (or ~3.2 min with 6s slots). Directly on the Strawmap trajectory.

**Spec Status:** Not yet an EIP. On the Strawmap trajectory. Would require changes to Casper FFG justification/finalization logic.

**Technical Complexity:** 🟡 Medium — Modifying the epoch boundary logic for finality. Need to ensure FFG still has accountable safety with single-epoch finalization. The key change: finalize on checkpoint from the *current* epoch rather than waiting for the *next* epoch's supermajority link.

**Excitement/Impact:** ⭐⭐⭐⭐ — Direct step on the roadmap. Halves finality time. Clear spec-level change.

**Feasibility (1 dev + AI):** ✅ Very feasible. It's a well-scoped spec change. Could prototype in Lodestar and demonstrate on a local testnet.

---

### 2. 🟢 Random Attester Sampling (256-1024 attesters per slot)
**Description:** Instead of having all validators attest every epoch (split into committees of ~512 per slot), randomly select only 256-1024 validators per slot. No aggregation phase needed.

**Motivation:** Removes the aggregation subslot entirely, enabling 2-subslot architecture (propose + attest). This is the key enabler for sub-6s slots. Vitalik explicitly mentioned this in his Strawmap comments.

**Spec Status:** Research stage. Mentioned by Vitalik. Connects to Orbit SSF committee ideas. No EIP yet.

**Technical Complexity:** 🟡 Medium-High — Need to: (1) implement per-slot random sampling, (2) remove aggregation layer, (3) adjust fork choice to work with smaller committee, (4) adjust rewards/penalties. Fork choice still works since "for a fork choice (non-finalizing) function, this is totally sufficient" per Vitalik.

**Excitement/Impact:** ⭐⭐⭐⭐⭐ — This is HUGE. It's the key architectural change that enables everything else. Removes the 3-subslot constraint, enabling 2-subslot and thus faster slots.

**Feasibility (1 dev + AI):** ✅ Feasible as a PoC. The spec change is clear: replace committee assignment with per-slot random sampling. Could demonstrate on devnet.

---

### 3. 🟢 Minimmit Consensus PoC
**Description:** Implement the Minimmit one-round BFT consensus algorithm as an alternative to Gasper.

**Motivation:** Minimmit (by Commonware/Dankrad Feist) is the consensus algorithm the Strawmap targets for fast finality (6-16s). It achieves consensus in one round of voting instead of two, at the cost of requiring >80% honest (vs 2/3 in traditional BFT).

**Key Properties:**
- Single-round finalization (propose + vote = done)
- Requires n ≥ 5f+1 honest nodes (>80%)
- M-notarization at 40% enables chain progress even without finality
- Dynamic availability — chain can progress with 40% online
- Clean leader rotation, no complex view-change protocols
- Built-in "nullification" for malicious/absent proposers

**Spec Status:** Published Dec 31, 2025 by Dankrad Feist. Paper available. No EIP. On Strawmap as the endgame finality mechanism.

**Technical Complexity:** 🔴 High — This is a fundamental consensus replacement. Would need: new fork choice, new finality gadget, new attestation structure, new state transition. But the algorithm itself is simpler than Gasper.

**Excitement/Impact:** ⭐⭐⭐⭐⭐ — THE endgame consensus for Ethereum. Being the first client to prototype this would be incredibly impactful.

**Feasibility (1 dev + AI):** 🟡 Feasible as standalone PoC (not integrated into full Lodestar). Could build a Minimmit consensus engine that runs a simplified beacon chain. Very impressive demo.

---

### 4. 🟡 FOCIL Implementation (EIP-7805)
**Description:** Fork-Choice enforced Inclusion Lists. A committee of validators creates inclusion lists that force block proposers to include certain transactions.

**Motivation:** Censorship resistance. FOCIL is the likely CL headliner for Hegotá (late 2026). Already has strong community support.

**Spec Status:** ✅ EIP-7805 exists. Spec is relatively mature. Has been evaluated for Hegotá readiness.

**Technical Complexity:** 🟡 Medium-High — Cross-layer (CL + EL + Engine API). Needs: IL committee selection, IL gossip/validation, fork-choice enforcement, engine API changes.

**Excitement/Impact:** ⭐⭐⭐⭐ — Very important for Ethereum's censorship resistance. Likely to be in Hegotá.

**Feasibility (1 dev + AI):** 🟡 Feasible but large scope due to cross-layer nature. Could start with CL-only parts.

---

### 5. 🟡 3-Slot Finality (3SF)
**Description:** A protocol by Francesco D'Amato, Roberto Saltini, and Luca Zanolini that achieves finality in 3 slots instead of the current 64+ slots.

**Motivation:** "SSF is not about 'Single' Slot" — the name is misleading. What matters is fast finality, and 3 slots (36s at 12s, or 18s at 6s) is already transformative.

**Key Insight:** Decompose the SSF problem. Rather than one complex slot that does everything, use 3 slots with clear separation: propose → vote → finalize. This is more practical than true single-slot finality.

**Spec Status:** Research post on ethresear.ch (Nov 2024). No EIP. Active research.

**Technical Complexity:** 🔴 High — New consensus algorithm. But 3SF may be simpler than full SSF since it has more time budget per step.

**Excitement/Impact:** ⭐⭐⭐⭐ — With 6s slots, 3SF gives 18s finality. That's already 50x better than current 16min.

**Feasibility (1 dev + AI):** 🟡 Could prototype the core algorithm. The ethresear.ch post provides enough detail to start.

---

### 6. 🟡 Orbit SSF Committee Selection
**Description:** A validator set management mechanism that uses heterogeneous stake distribution to randomly select committees for SSF while preserving economic finality.

**Motivation:** After EIP-7251 (MaxEB), validators have different effective balances. Orbit exploits this: large validators always participate, small validators rotate in. This preserves ~$2.5B cost of attack while only needing ~8k-32k validators per slot.

**Spec Status:** Two research posts:
- [Orbit SSF](https://ethresear.ch/t/orbit-ssf-solo-staking-friendly-validator-set-management-for-ssf/19928) (June 2024)
- [Orbit SSF in Practice](https://ethresear.ch/t/orbit-ssf-in-practice/20943) (Nov 2024)
- [Vorbit SSF](https://ethresear.ch/t/vorbit-ssf-with-circular-and-spiral-finality-validator-selection-and-distribution/20464) (Sept 2024)
- No EIP yet.

**Technical Complexity:** 🟡 Medium — Committee selection algorithm itself is implementable. Integration with full SSF is harder.

**Excitement/Impact:** ⭐⭐⭐⭐ — Key enabler for SSF that preserves solo staking. Directly referenced by Vitalik.

**Feasibility (1 dev + AI):** ✅ Committee selection algorithm is very feasible to prototype. Could implement the Orbit selection function and demonstrate its economic finality properties with simulations.

---

### 7. 🟢 8-Slot Epochs (Shorter Epoch Duration)
**Description:** Reduce SLOTS_PER_EPOCH from 32 to 8, dramatically reducing finality time.

**Motivation:** On Vitalik's finality trajectory: with 6s slots and 8-slot epochs, finality drops to ~1m12s. This is a "parameter change" approach — much simpler than new consensus.

**Spec Status:** No EIP. Mentioned in Vitalik's trajectory. Would need analysis of security implications.

**Technical Complexity:** 🟢 Low-Medium — Changing SLOTS_PER_EPOCH affects: committee shuffling, sync committee periods, validator activation/exit queues, proposer lookahead. Many things reference epochs. But the change is parametric, not algorithmic.

**Excitement/Impact:** ⭐⭐⭐⭐ — Combined with 6s slots, gives ~1 minute finality with no consensus algorithm changes.

**Feasibility (1 dev + AI):** ✅ Very feasible. Can be prototyped by changing the constant and fixing all downstream references. Great demo: "look, 1-minute finality on Lodestar."

---

### 8. 🟡 Based Preconfirmations (CL Support)
**Description:** Add CL-level infrastructure for proposer commitments / preconfirmations. Proposers opt-in to additional slashing conditions and can offer sub-slot transaction inclusion guarantees.

**Motivation:** Enables ~100ms confirmation times for L1 and based rollups. Key for L2 UX. Requires: proposer slashing framework, commitment gossip, proposer lookahead (EIP-7917 helps).

**Spec Status:** 
- Research post by Justin Drake (Nov 2023)
- EIP-7917 (deterministic proposer lookahead) — now in Fusaka
- No complete preconf EIP yet

**Technical Complexity:** 🔴 High — Requires new slashing conditions, new gossip channels, new engine API extensions. Mostly out-of-protocol initially.

**Excitement/Impact:** ⭐⭐⭐⭐⭐ — Transformative for UX. But most work is out-of-protocol.

**Feasibility (1 dev + AI):** 🟡 CL-side support (e.g., proposer commitment gossip, preconf validation) is feasible. Full system requires builder/relay/EL coordination.

---

### 9. 🟡 RLMD-GHOST Fork Choice
**Description:** Replace LMD-GHOST with RLMD-GHOST (Recent Latest Message Driven GHOST), which expires old votes and has cleaner security properties.

**Motivation:** RLMD-GHOST is the fork choice algorithm used in SSF proposals. It's simpler than LMD-GHOST, removes the "balancing attack" surface, and works well with shorter slots. It's on the path to SSF.

**Spec Status:** Paper: [eprint.iacr.org/2023/280](https://eprint.iacr.org/2023/280). Used in the "Simple SSF Protocol" post by fradamt/Zanolini. No standalone EIP.

**Technical Complexity:** 🟡 Medium — Fork choice changes are not consensus-breaking and don't require simultaneous client activation (per eth2book). Implementation: track only recent votes (configurable window), remove old vote accumulation.

**Excitement/Impact:** ⭐⭐⭐ — Important foundational piece but not user-visible.

**Feasibility (1 dev + AI):** ✅ Very feasible. Fork choice is well-isolated in Lodestar. Could implement as opt-in experimental mode.

---

### 10. 🟢 Whisk SSLE (EIP-7441)
**Description:** Single Secret Leader Election — hide the identity of the next block proposer until they actually propose.

**Motivation:** Prevents DoS attacks on known future proposers. Important for validator safety.

**Spec Status:** ✅ EIP-7441 exists. Consensus spec drafted. Research phase (not finalized).

**Technical Complexity:** 🔴 High — Requires new cryptographic primitives (shuffle + ZK proofs), hundreds of lines of new spec code. Still needs post-quantum solution.

**Excitement/Impact:** ⭐⭐⭐ — Important but may be deprioritized if APS (execution tickets) makes it less critical.

**Feasibility (1 dev + AI):** 🟡 The crypto is complex. Could implement the spec but the spec itself is still evolving.

---

## The Logical Next Step After EIP-7782 (6s Slots)

Based on the Strawmap and Vitalik's comments, the clear progression is:

### Short-term (immediate, CL-only, high-impact):
1. **8-Slot Epochs** — Combined with 6s slots = ~1 minute finality. Parametric change.
2. **Random Attester Sampling (256-1024)** — Remove aggregation phase, enable even faster slots.

### Medium-term (next project, requires new spec work):
3. **One-Epoch Finality** — Change FFG to finalize in 1 epoch instead of 2.
4. **RLMD-GHOST** — Cleaner fork choice, foundational for SSF.
5. **Orbit Committee Selection** — Prototype the selection algorithm.

### Ambitious (impressive demo, longer timeline):
6. **Minimmit PoC** — Standalone consensus engine demo.
7. **3SF PoC** — 3-slot finality prototype.

---

## My Top Recommendation: Random Attester Sampling + 8-Slot Epochs

**Why this combination?**
- Directly on Vitalik's stated trajectory
- Both are CL-only changes
- Together they unlock: 6s slots × 8 epochs = 48s finality, AND enable sub-6s slots by removing aggregation
- High-impact demo: "Lodestar running with 48-second finality and no aggregation layer"
- Relatively clean spec changes (parametric + committee restructuring)
- Sets up the architecture for everything that follows (Minimmit, Orbit, etc.)
- Demonstrates Lodestar's ability to prototype consensus-layer future

---

## Key References

### Core Research:
- [Paths toward SSF (Vitalik, 2022)](https://notes.ethereum.org/@vbuterin/single_slot_finality)
- [Simple SSF Protocol (fradamt/Zanolini, 2023)](https://ethresear.ch/t/a-simple-single-slot-finality-protocol/14920)
- [SSF paper (eprint, 2023)](https://eprint.iacr.org/2023/280)
- [Orbit SSF (2024)](https://ethresear.ch/t/orbit-ssf-solo-staking-friendly-validator-set-management-for-ssf/19928)
- [Orbit SSF in Practice (2024)](https://ethresear.ch/t/orbit-ssf-in-practice/20943)
- [Vorbit SSF (Elowsson, 2024)](https://ethresear.ch/t/vorbit-ssf-with-circular-and-spiral-finality-validator-selection-and-distribution/20464)
- [3-Slot Finality (D'Amato et al, 2024)](https://ethresear.ch/t/3-slot-finality-ssf-is-not-about-single-slot/20927)
- [Minimmit (Dankrad Feist, Dec 2025)](https://dankradfeist.de/tempo/2025/12/31/minimmit-simple-fast-consensus.html)
- [Epochs and Slots All The Way Down (Vitalik, Jun 2024)](https://vitalik.eth.limo/general/2024/06/30/epochslot.html)
- [Possible Futures: The Merge (Vitalik, Oct 2024)](https://vitalik.eth.limo/general/2024/10/14/futures1.html)

### EIPs:
- [EIP-7251: Max Effective Balance (Pectra, done)](https://eips.ethereum.org/EIPS/eip-7251)
- [EIP-7782: 6-Second Slots (Draft)](https://eips.ethereum.org/EIPS/eip-7782)
- [EIP-7805: FOCIL (Draft)](https://eips.ethereum.org/EIPS/eip-7805)
- [EIP-7732: ePBS (Draft)](https://eips.ethereum.org/EIPS/eip-7732)
- [EIP-7441: Whisk SSLE (Draft)](https://eips.ethereum.org/EIPS/eip-7441)
- [EIP-7917: Deterministic Proposer Lookahead (Fusaka)](https://eips.ethereum.org/EIPS/eip-7917)

### Roadmap:
- [Strawmap (Feb 2026)](https://strawmap.org)
- [Vitalik's Strawmap Comments (Reddit)](https://www.reddit.com/r/ethereum/comments/1rera79/my_comments_on_ethereum_strawmap/)
- [EF Checkpoint #8 (Jan 2026)](https://blog.ethereum.org/en/2026/01/20/checkpoint-8)
- [PoS Evolution doc](https://github.com/ethereum/pos-evolution/blob/master/pos-evolution.md)

### Aggregation & Signatures:
- [Horn: Collecting Signatures for Faster Finality](https://ethresear.ch/t/horn-collecting-signatures-for-faster-finality/14219)
- [Signature Merging for Large-Scale Consensus](https://ethresear.ch/t/signature-merging-for-large-scale-consensus/17386)
- [STARK-based Signature Aggregation (Vitalik)](https://hackmd.io/@vbuterin/stark_aggregation)

### Preconfirmations:
- [Based Preconfirmations (Justin Drake, 2023)](https://ethresear.ch/t/based-preconfirmations/17353)
- [SoK: Preconfirmations (arxiv, 2025)](https://www.arxiv.org/pdf/2510.02947)
- [Preconfirmation Fair Exchange (Nethermind, 2025)](https://ethresear.ch/t/preconfirmation-fair-exchange/21891)

### Other:
- [Rainbow Staking](https://ethresear.ch/t/unbundling-staking-towards-rainbow-staking/18683)
- [View Merge](https://ethresear.ch/t/view-merge-as-a-replacement-for-proposer-boost/13739)
- [Ethereum Consensus in 2024 (Terence)](https://hackmd.io/@ttsao/SJCohUjCh)
