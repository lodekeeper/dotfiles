# Unimplemented CL Spec Features & Pipeline EIPs for Lodestar

*Research date: 2026-02-28*
*Sources: consensus-specs repo, EIPs repo, strawmap.org, ethresear.ch, client repos*

---

## Table of Contents
1. [Features in `_features/` (Draft Specs)](#1-features-in-_features-draft-specs)
2. [Upcoming Fork: Heze (after Gloas)](#2-upcoming-fork-heze-after-gloas)
3. [Strawmap Roadmap Items](#3-strawmap-roadmap-items)
4. [Open consensus-specs PRs (Active)](#4-open-consensus-specs-prs-active)
5. [SSZ/Serialization Improvements](#5-sszserialization-improvements)
6. [Networking Improvements](#6-networking-improvements)
7. [Long-Horizon Research Items](#7-long-horizon-research-items)
8. [Summary & Recommendations](#8-summary--recommendations)

---

## 1. Features in `_features/` (Draft Specs)

These are specced in `consensus-specs/specs/_features/` but NOT part of any scheduled fork yet.

### EIP-6914: Validator Index Reuse
- **EIP:** [EIP-6914](https://github.com/ethereum/EIPs/pull/6914)
- **Spec status:** Draft (in `_features/eip6914/`)
- **Description:** Allows reassignment of validator indices from long-exited validators (balance == 0, past `SAFE_EPOCHS_TO_REUSE_INDEX` = 65,536 epochs) to new deposits. Prevents unbounded growth of the validator registry.
- **Spec files:** `beacon-chain.md`, `fork-choice.md`
- **Implementation complexity:** Medium. Modifies `get_index_for_new_validator` to scan for reusable slots. Fork-choice changes needed for validator index reuse awareness.
- **Impact:** High for long-term scalability. Validator set currently ~1M and growing. Without this, indices grow monotonically forever, increasing state size.
- **Lodestar status:** ❌ Not implemented (no references in codebase)
- **Other clients:** No known implementations yet
- **Timeline:** Not scheduled for any fork. May land in I* or later.

### EIP-7441: Whisk (Single Secret Leader Election / SSLE)
- **EIP:** [EIP-7441](https://eips.ethereum.org/EIPS/eip-7441)
- **Spec status:** Draft (in `_features/eip7441/`)
- **Description:** Uses curdleproofs (zero-knowledge shuffle proofs) to hide proposer identity until block proposal time. Prevents targeted DoS attacks on upcoming proposers.
- **Spec files:** `beacon-chain.md`, `fork.md`
- **Implementation complexity:** Very High. Requires new cryptographic primitives (curdleproofs), significant state changes (16K candidate trackers, 8K proposer trackers), and new BLS operations.
- **Impact:** High for validator privacy and network security.
- **Lodestar status:** ❌ Not implemented (only SSZ static test ignoring for eip7441)
- **Other clients:** No known implementations
- **Timeline:** Long-term. Very research-heavy. May be superseded by simpler approaches.

### EIP-7805: FOCIL (Fork-Choice Enforced Inclusion Lists)
- **EIP:** [EIP-7805](https://ethresear.ch/t/fork-choice-enforced-inclusion-lists-focil-a-simple-committee-based-inclusion-list-proposal/19870)
- **Spec status:** Draft → **Promoted to Heze fork** (merged PR #4942, 2026-02-20)
- **Description:** Committee-based inclusion lists forcing transaction inclusion. An `INCLUSION_LIST_COMMITTEE_SIZE=16` committee per slot publishes mandatory transaction lists that builders must include. Fork-choice enforced: blocks that don't satisfy IL requirements are not valid.
- **Spec files:** `beacon-chain.md`, `inclusion-list.md`, `validator.md`, `p2p-interface.md`, `fork.md`, `fork-choice.md`
- **Implementation complexity:** High. New gossip topics, new committee logic, IL store management, fork-choice integration, Engine API changes for `getInclusionListV1`.
- **Impact:** Very High. Core censorship resistance mechanism. Central to Ethereum's credible neutrality.
- **Lodestar status:** 🟡 Branch exists (`remotes/fork/focil`) but appears stale (based on pre-Gloas rebase)
- **Other clients:**
  - Lighthouse: Active tracking issue (#6660), partial implementation on `electra-focil` branch
  - Nimbus: Multiple PRs open (#7253, #7290, #7637)
  - Prysm: Unknown
- **Timeline:** **Heze fork** (next after Gloas, ~6 months out). HIGH PRIORITY.

### EIP-6800: Verkle Trees
- **EIP:** [EIP-6800](https://eips.ethereum.org/EIPS/eip-6800)
- **Spec status:** Draft (in `_features/eip6800/`)
- **Description:** Adds execution witness (Verkle proofs) to execution payloads, enabling stateless validation. Uses Banderwagon curve and IPA proofs.
- **Spec files:** `beacon-chain.md`, `p2p-interface.md`, `fork.md`
- **Implementation complexity:** Very High. New cryptographic primitives (IPA proofs, Banderwagon curve), new state types, major EL changes.
- **Impact:** Transformative. Enables stateless clients, dramatically reduces state storage requirements.
- **Lodestar status:** ❌ Not implemented
- **Other clients:** EL clients (Geth, Nethermind) have active Verkle branches. CL side is simpler (just carrying the witness).
- **Timeline:** Mid-to-long-term. Per strawmap, likely I* or J* fork (2027-2028). Note: Strawmap now favors zkEVM approach over Verkle for statelessness.

### EIP-7928: Block-Level Access Lists (BALs)
- **EIP:** [EIP-7928](https://eips.ethereum.org/EIPS/eip-7928)
- **Spec status:** Draft (in `_features/eip7928/`)
- **Description:** Enforced block access lists recording all accounts/storage locations accessed during execution, plus post-execution values. Enables parallel disk reads, parallel tx validation, parallel state root computation, and execution proofs without re-execution.
- **Spec files:** `beacon-chain.md`, `p2p-interface.md`, `fork.md`
- **Implementation complexity:** Medium (CL side). The CL changes are straightforward — new field in `ExecutionPayload` (`block_access_list: BlockAccessList`). Most complexity is on EL side.
- **Impact:** Very High. **Glamsterdam EL headliner** per strawmap. Enables massive parallelism and is a prerequisite for gigagas throughput.
- **Lodestar status:** ❌ Not implemented
- **Other clients:** Active research, likely starting implementation soon given strawmap timeline
- **Timeline:** **Glamsterdam** (= Gloas on CL). BAL is the EL headliner for the same fork window.

### EIP-8025: Stateless Validation via Execution Proofs
- **EIP:** [EIP-8025](https://eips.ethereum.org/EIPS/eip-8025)
- **Spec status:** Active development (in `_features/eip8025/`)
- **Description:** Enables stateless validation of execution payloads through ZK execution proofs. Validators can verify block validity without re-executing transactions.
- **Spec files:** `beacon-chain.md`, `prover.md`, `proof-engine.md`, `p2p-interface.md`, `fork.md`
- **Implementation complexity:** Very High. New proof types, proof verification, new P2P messages (ExecutionProofsByRoot), new Engine API endpoints.
- **Impact:** Transformative. Core building block for gigagas throughput and real-time proving.
- **Lodestar status:** 🟢 **Active worktree** at `~/lodestar-eip8025` with implementation progress (Phase A/B/C work)
- **Other clients:** Unknown
- **Timeline:** Post-Glamsterdam. Per strawmap, likely H* (Hegotá) or later.

---

## 2. Upcoming Fork: Heze (after Gloas)

Heze is the confirmed name for the fork after Gloas. Key evidence:
- PR #4942 merged 2026-02-20: "Promote EIP-7805 to Heze"
- PR #4926 has `heze` label: "Replace `SECONDS_PER_SLOT` with `SLOT_DURATION_MS`"
- `heze` is a recognized label in consensus-specs

### Confirmed Heze Features
1. **EIP-7805 (FOCIL)** — Fork-choice enforced inclusion lists (CL headliner)
2. **SLOT_DURATION_MS migration** — Moving from `SECONDS_PER_SLOT` to millisecond precision (groundwork for shorter slots)

### Likely Heze Features (based on strawmap + active PRs)
3. **Fast Confirmation Rule** (PR #4747) — Modified confirmation rule algorithm starting from safe checkpoint, reduces time to confirmed block. New `confirmed_root` in Store, new `on_slot_after_attestations_applied` handler.
4. **EIP-7843 (SLOTNUM opcode)** — New EVM opcode returning slot number (CL passes slot to EL). PR #4840 open.

---

## 3. Strawmap Roadmap Items

The [strawmap](https://strawmap.org) (published 2026-02-25 by EF) outlines ~7 forks through 2029:

### Fork Timeline (CL names)
| Fork | CL Name | Approximate Date | CL Headliner | EL Headliner |
|------|---------|-------------------|--------------|--------------|
| Current | Gloas (G*) | 2026 H1 | ePBS | BALs |
| Next | Heze (H*) / Hegotá | 2026 H2 | FOCIL | TBD |
| I* | TBD | 2027 H1 | TBD | TBD |
| J* | TBD | 2027 H2 | TBD | TBD |
| K* | TBD | 2028 H1 | TBD | TBD |
| L* | TBD | 2028 H2 | Lean Consensus (3SF/SSF) | TBD |
| M* | TBD | 2029 | TBD | TBD |

### Five North Stars
1. **Fast L1:** Transaction inclusion and chain finality in seconds (SSF → 3SF)
2. **Gigagas L1:** 1 gigagas/sec (~10K TPS) via zkEVMs and real-time proving
3. **Teragas L2:** 1 gigabyte/sec (~10M TPS) via data availability sampling
4. **Post Quantum L1:** Centuries-long cryptographic security via hash-based schemes
5. **Private L1:** Privacy as first-class citizen via L1 shielded transfers

### Key Strawmap Items Not Yet Specced

#### 3-Slot Finality (3SF) / Lean Consensus
- **Status:** Research phase (ethresear.ch posts, academic papers, beam chain calls)
- **Description:** Replaces Gasper with a new consensus protocol that finalizes blocks in 3 slots (~36 seconds with 12s slots, or ~24 seconds with 8s slots). Combines Head and FFG voting into single phase.
- **Complexity:** Transformative. Complete consensus rewrite.
- **Timeline:** Targeted for L* fork (~2028 H2)
- **Lodestar relevance:** Long-term but important to track. "Lean consensus" is the strawmap's term.

#### Shorter Slot Times (EIP-7782)
- **EIP:** [EIP-7782](https://eips.ethereum.org/EIPS/eip-7782)
- **Spec status:** Open PR #4484, WIP with many failing tests
- **Description:** Reduces slot time from 12s to 6s (or 8s). Requires `SLOT_DURATION_MS` migration, rewards adjustment, queue logic changes.
- **Lodestar status:** 🟡 Multiple branches exist (`feat/eip7782-6s-slots`, `feat/eip7782-fixes`, `nflaig/eip7782`)
- **Timeline:** Post-Heze, likely I* or J*

#### Post-Quantum Cryptography
- **Status:** Research phase
- **Description:** Replace BLS signatures and ECDSA with hash-based or lattice-based schemes
- **Complexity:** Extremely High. Touches every layer.
- **Timeline:** K* or later (~2028+)

#### Shielded ETH Transfers (Private L1)
- **Status:** Research phase
- **Description:** Protocol-level privacy for ETH transfers
- **Complexity:** Very High
- **Timeline:** Late roadmap (~2029)

---

## 4. Open consensus-specs PRs (Active)

### PR #4558: Cell Dissemination via Partial Messages
- **Labels:** fulu, gloas
- **Description:** Uses Gossipsub's Partial Messages extension for cell-level dissemination of data columns (rather than full columns). Reduces bandwidth by only sending previously unseen cells.
- **Related:** [ethresear.ch post](https://ethresear.ch/t/gossipsubs-partial-messages-extension-and-cell-level-dissemination/23017), libp2p specs PR #685, EIP PR #11176
- **Complexity:** High. Requires libp2p partial messages support.
- **Lodestar relevance:** js-libp2p would need to implement partial messages first.
- **Timeline:** Post-Gloas optimization

### PR #4747: Fast Confirmation Rule
- **Labels:** phase0, eip7805, gloas
- **Description:** Modified confirmation rule algorithm. Uses iterative approach starting from safe checkpoint. New `confirmed_root` in Store, `on_slot_after_attestations_applied` handler.
- **Complexity:** Medium-High. New fork-choice logic, committee shuffling dependencies.
- **Lodestar relevance:** Direct beacon node implementation. Would improve `safe` block determination.
- **Timeline:** Likely Heze or I*

### PR #4630: EIP-7688 Forward Compatible SSZ Types in Gloas
- **Labels:** ssz, lightclients, electra, gloas
- **Description:** Introduces `ProgressiveContainer` (EIP-7495) and `ProgressiveList` (EIP-7916) for forward-compatible Merkle tree structures. Stable generalized indices across forks.
- **Complexity:** High. Requires new SSZ types throughout the codebase.
- **Impact:** Very High for light clients, bridges, smart contracts verifying beacon state (e.g., EIP-4788 consumers). Requested by Lido and Rocketpool.
- **Lodestar status:** 🟡 Remote branches exist (`remotes/fork/eip-7688`, `remotes/fork/eip-7688-rebased`)
- **Note:** Co-authored by Cayman (@wemeetagain) who is a Lodestar maintainer. EIP-7495 is in Review status.

### PR #4950: Extend by_root reqresp serve range to match by_range
- **Labels:** phase0, gloas
- **Description:** Aligns the by_root request/response serving range with by_range for consistency
- **Complexity:** Low
- **Timeline:** Near-term

### PR #4840: EIP-7843 (SLOTNUM) Support in Gloas
- **Labels:** gloas, eip7843
- **Description:** Adds support for the SLOTNUM EVM opcode to Gloas specs
- **Complexity:** Low (CL side just passes slot number to EL via Engine API)
- **Timeline:** Could land in Gloas or Heze

### PR #3866: Deprecate mplex
- **Labels:** networking
- **Description:** Formal deprecation of mplex stream multiplexer in favor of yamux/QUIC.
- **Status table from PR:**
  - Lighthouse: ✅ mplex, ✅ yamux, ✅ QUIC
  - Prysm: ✅ mplex, ✅ yamux, ❓ QUIC
  - Nimbus: ✅ mplex, ❌ yamux, 🚧 QUIC
  - Teku: ✅ mplex, ❌ yamux, 🚧 QUIC
  - Grandine: ✅ mplex, ✅ yamux, ✅ QUIC
  - **Lodestar:** ⚠️ **Uses ONLY mplex** (known issue from EPBS interop investigation). No yamux support.
- **Complexity:** Medium. Requires js-libp2p yamux implementation/integration.
- **Impact:** Critical. mplex is deprecated and becoming a security vulnerability. **This is a blocking interop issue** — already caused problems in EPBS devnet interop (gossipsub subscription bug with rust-libp2p).
- **Lodestar status:** ❌ Not implemented. **HIGH PRIORITY** for networking reliability.

### PR #4926: Replace SECONDS_PER_SLOT with SLOT_DURATION_MS
- **Labels:** phase0, eip7805, gloas, heze
- **Description:** Groundwork for variable slot times. Removes `SECONDS_PER_SLOT` in favor of `SLOT_DURATION_MS`.
- **Complexity:** Medium. Lots of small changes throughout.
- **Lodestar relevance:** Will need corresponding migration.

---

## 5. SSZ/Serialization Improvements

### EIP-7495: SSZ ProgressiveContainer
- **Status:** Review (EIP in Review)
- **Description:** Forward-compatible containers where fields maintain stable generalized indices across forks. Uses `active_fields` bitvector.
- **Lodestar status:** ❌ Not implemented (no references in codebase)
- **Relevance:** Core requirement for EIP-7688. Co-authored by Cayman (Lodestar maintainer).

### EIP-7916: SSZ ProgressiveList
- **Status:** Draft
- **Description:** Efficient SSZ type for lists with large capacity but small current size. Uses progressive Merkle tree.
- **Lodestar status:** ❌ Not implemented
- **Relevance:** Required by EIP-7495 and EIP-7688.

### EIP-7688: Forward Compatible SSZ in Beacon Chain
- **Status:** Open PR #4630 against consensus-specs
- **Description:** Applies ProgressiveContainer/ProgressiveList to beacon chain structures for stable gindices.
- **Lodestar status:** 🟡 Branches exist but likely stale
- **Timeline:** Targeted for Gloas (PR title), but may slip to Heze or I*.

### EIP-7919: Pureth Meta
- **Status:** Draft
- **Description:** Meta-EIP bundling data structure improvements for verifiable Ethereum data without trusted RPCs. Includes EIP-6404, 6465, 6466, 7495, 7668, 7708, 7745, 7799, 7807, 7916.
- **Lodestar status:** ❌ Not implemented
- **Timeline:** Multi-fork effort

---

## 6. Networking Improvements

### Yamux / QUIC Transport
- **Urgency:** HIGH
- **Description:** Lodestar currently only supports mplex (deprecated). Needs yamux and ideally QUIC.
- **Impact:** Interoperability, performance, security
- **Lodestar status:** ❌ No yamux in codebase

### Cell-Level Dissemination (Partial Messages)
- **PR:** consensus-specs #4558, EIP PR #11176
- **Description:** Gossipsub partial messages for data column cells
- **Impact:** Significant bandwidth reduction for PeerDAS
- **Lodestar status:** ❌ Not implemented
- **Dependency:** Requires libp2p partial messages spec + js-libp2p implementation

---

## 7. Long-Horizon Research Items

### EIP-8148: Custom Sweep Threshold for Validators
- **Status:** Draft EIP, consensus-specs PR #4901 open
- **Description:** Allows validators with compounding credentials (0x02, 0x03) to set custom balance thresholds for sweep withdrawals. Min threshold 33 ETH, max 2048 ETH.
- **Complexity:** Medium. New BeaconState field (`validator_sweep_thresholds`), new EL→CL request type.
- **Timeline:** Not scheduled for any fork yet.

### Confirmation Rule (Original)
- **PR:** #3339 (2023, still open)
- **Description:** Original confirmation rule algorithm
- **Status:** Being superseded by Fast Confirmation Rule (#4747)

### Separate Type for On-chain Attestation Aggregates
- **PR:** #3787 (2024, still open)
- **Description:** Introduces a dedicated type for on-chain attestation aggregates
- **Status:** Long-running, low priority

---

## 8. Summary & Recommendations

### Immediate Priority (Next 3-6 months)
| Feature | Reason | Effort |
|---------|--------|--------|
| **FOCIL (EIP-7805)** | Confirmed for Heze fork, other clients already implementing | High |
| **Yamux transport** | Blocking interop issue, mplex deprecated | Medium |
| **EIP-7843 SLOTNUM** | Simple CL change, may land in Gloas or Heze | Low |

### Medium Priority (6-12 months)
| Feature | Reason | Effort |
|---------|--------|--------|
| **Fast Confirmation Rule** | Improves safe block UX, likely Heze/I* | Medium-High |
| **EIP-7688 (Forward SSZ)** | Requested by major staking protocols, improves light clients | High |
| **EIP-7928 BALs (CL side)** | Glamsterdam EL headliner, CL changes minimal | Low-Medium |
| **SLOT_DURATION_MS migration** | Groundwork for shorter slots | Medium |
| **EIP-7782 (6s slots)** | Already has Lodestar branches, complements SLOT_DURATION_MS | High |

### Long-Term / Research Track
| Feature | Reason | Effort |
|---------|--------|--------|
| **EIP-8025 (Execution Proofs)** | Already active in Lodestar (worktree exists) | Very High |
| **EIP-6914 (Index Reuse)** | Scalability, but not urgent yet | Medium |
| **3SF / Lean Consensus** | Complete consensus rewrite, ~2028+ | Transformative |
| **Cell Dissemination** | PeerDAS optimization, needs libp2p work | High |
| **Post-Quantum Crypto** | ~2028+, research phase | Extremely High |
| **EIP-7441 (Whisk/SSLE)** | Complex crypto, may be superseded | Very High |

### Top 3 Recommendations for Next Lodestar Project
1. **🔴 FOCIL (EIP-7805)**: This is the next fork's CL headliner. Lighthouse and Nimbus are already building. The existing `fork/focil` branch needs rebasing onto Gloas/Heze. Starting early gives time to shape the implementation.

2. **🔴 Yamux Transport**: Not a spec feature per se, but a critical infrastructure gap. Lodestar is the only major client without yamux. This caused real interop failures on EPBS devnet. Fix this before it blocks Heze devnets.

3. **🟡 EIP-7688 Forward Compatible SSZ**: Co-authored by Cayman. Lido and Rocketpool have explicitly requested this. Branches exist. Could be a differentiator for Lodestar if landed early.

---

*Note: Gloas (ePBS) is still being stabilized — multiple Gloas PRs merged in Feb 2026. Heze planning is just beginning. The strawmap was published 3 days ago (Feb 25, 2026) and represents the first unified long-term roadmap from EF.*
