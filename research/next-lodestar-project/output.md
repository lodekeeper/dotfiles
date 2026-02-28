# Top 3 High-Impact CL-Only Lodestar Projects (Ranked)

**Date:** 2026-02-28  
**Requested by:** Nico  
**Constraints applied:** CL-only, large scope, high ecosystem impact, start within days, spec-backed preferred

---

## 1) FOCIL implementation (EIP-7805) — **Best overall pick**

**Why #1:**
- It is the next major CL headliner (Heze/Hegotá track) and directly tied to Ethereum’s censorship-resistance goals.
- Fully CL-only; no EL implementation dependency to begin meaningful work.
- Spec exists and is mature enough to implement against now (`consensus-specs` feature set + active client work).
- High visibility and high strategic impact for Lodestar.

**Scope fit:** Large protocol feature (fork choice, gossip, validator behavior, inclusion list logic).  
**Can start in days:** Yes.

---

## 2) Fast Confirmation Rule (FCR) — **Highest near-term user impact**

**Why #2:**
- Major UX impact: confirmation experience improves from minutes-scale uncertainty toward seconds-scale confidence.
- CL-only fork-choice/confirmation logic work.
- Strong prior art from Nimbus/Teku and an existing Lodestar PR thread to accelerate implementation.
- Very practical “big project” that can ship incrementally.

**Scope fit:** Large, deep fork-choice and confirmation pipeline work.  
**Can start in days:** Yes (with existing references + Lodestar groundwork).

---

## 3) 3-Slot Finality / Minimmit PoC track — **Most exciting moonshot**

**Why #3:**
- This is the long-term “Fast L1” consensus direction from current R&D momentum (Strawmap + recent research).
- CL-only research/prototyping path with potentially massive upside.
- Not as spec-mature as #1/#2, but ideal for a high-leverage Lodestar innovation PoC.

**Scope fit:** Very large (new consensus/finality architecture PoC).  
**Can start in days:** Yes, as a staged PoC/simulator track.

---

## Why these three beat other candidates

- They are all **CL-only** and can be started immediately by one lead implementer + AI agents.
- They are **large-scope** enough to be strategic, not incremental tweaks.
- #1 and #2 are stronger on **spec maturity and shipability**.
- #3 provides a true **breakthrough/research upside** and future positioning.

---

## Suggested execution order

1. Start **FOCIL** immediately (main track).  
2. Run **FCR** in parallel as a second implementation stream.  
3. Keep **3SF/Minimmit** as a structured PoC/research stream feeding future architecture.
