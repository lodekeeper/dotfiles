# Adversarial Critique: Proposed Top-3 Lodestar Project Ranking

**Date:** 2026-02-28
**Constraints recap:** CL-only · high impact · large scope · start within days · one lead implementer + AI agents · spec-backed preferred

---

## Proposed Ranking Under Review

| # | Project | Spec Status |
|---|---------|-------------|
| 1 | FOCIL (EIP-7805) | Draft EIP, consensus-specs `_features/eip7805/` |
| 2 | Fast Confirmation Rule | consensus-specs PR #4747 |
| 3 | 3-Slot Finality / Minimmit PoC | Academic paper (arXiv 2508.10862) |

---

## Challenge #1: FOCIL Is Not Purely CL-Only

**Claim:** FOCIL is the perfect #1 project.
**Counter:** FOCIL is a **cross-layer feature** that violates the CL-only constraint.

The spec explicitly requires:
- **Engine API changes:** `engine_getInclusionListV1` (new endpoint), modified `forkchoiceUpdatedV4`
- **EL-side transaction pool logic:** builders must select and include transactions from ILs
- **EL validation:** the execution layer must verify IL satisfaction conditions

Without a cooperating EL client, a FOCIL implementation can't be meaningfully tested end-to-end. The community-wishlist research rates implementation complexity as "Medium-High" precisely because of these cross-layer dependencies. The existing `fork/focil` branch is also **stale** (pre-Gloas rebase needed per the findings).

**Verdict:** FOCIL is mandatory work (Heze headliner) but suboptimal as a "start within days, one dev + AI" project. The EL dependency means you'll hit blockers quickly. Better suited as a team-wide effort once ePBS stabilizes.

---

## Challenge #2: Fast Confirmation Rule Should Be #1

**Claim:** FCR is a good #2 runner-up.
**Counter:** FCR is the **objectively superior** choice for #1 under every stated constraint.

| Criterion | FCR | FOCIL |
|-----------|-----|-------|
| CL-only? | ✅ Pure fork-choice change | ❌ Cross-layer (Engine API, EL tx pool) |
| Spec-backed? | ✅ PR #4747, well-defined | ✅ EIP-7805 |
| Start within days? | ✅ PR #8837 already opened by nazarhussain; Nimbus has ~10 merged PRs as reference | ⚠️ Stale branch needs rebase; EL client needed |
| One implementer + AI? | ✅ Self-contained in fork choice | ⚠️ Needs EL coordination |
| High impact? | ✅ Finality perception: 16 min → ~15-30 sec | ✅ Censorship resistance |
| Large scope? | ✅ New proto-array tracking, committee shuffling, equivocation scoring, confirmed block tracking | ✅ New gossip, committee, fork-choice |

The cross-client-pocs.md research explicitly identifies FCR as:
> **"Top Pick for One Developer with AI Assistance"** — Already started in Lodestar, Nimbus has ~10 PRs to reference, well-specced, CL-only, massive user impact.

Nimbus's implementation provides a complete roadmap:
1. Track slot instead of epoch in proto array (#7914)
2. Track slashed validators in EpochRef (#7944)
3. Move block confirmation out of proto array (#7969)
4. Add `get_current_target_score` (#8031)
5. Track support from empty slots and equivocating validators (#8026)
6. Switch FCR balance source on epoch start (#8029)
7. Track shuffling for `current_epoch - 2` (#8039)

This is a **paint-by-numbers** implementation path. You can literally follow Nimbus's PR sequence with the spec PR open alongside.

**Verdict:** FCR dominates FOCIL on every constraint dimension. Promote to #1.

---

## Challenge #3: Minimmit PoC Fails Multiple Constraints

**Claim:** Minimmit / 3SF PoC is a worthy #3.
**Counter:** It fails 3 of 6 constraints.

| Constraint | Pass? | Why |
|------------|-------|-----|
| CL-only | ✅ | Yes, consensus algorithm |
| High impact | ✅ | THE future of Ethereum consensus |
| Large scope | ✅ | Full consensus replacement |
| Start within days | ❌ | **No actionable spec.** Paper describes a BFT protocol; translating that to a working PoC requires significant research/design before code. "Days" is optimistic — "weeks to orient" is realistic. |
| One implementer + AI | ⚠️ | AI agents struggle with novel consensus algorithms where correctness = safety. Research-heavy work requires human judgment at every step. |
| Spec-backed | ❌ | **Academic paper only.** No EIP, no consensus-spec PR, no test vectors, no reference implementation in the specs repo. The leanSpec Python code exists but covers 3SF-mini, not Minimmit itself. |

The findings rate Minimmit feasibility at **"LOW-MEDIUM"** and note it's targeted for the **L\* fork (~2028 H2)** — two years away. The excitement rating is "10/10 for impact, but 5/10 for near-term feasibility."

A standalone Minimmit simulator is intellectually exciting but produces no reusable production code, no interop capability, and no competitive advantage for Lodestar's positioning in the next 2 forks (Glamsterdam, Heze).

**Verdict:** Drop Minimmit. Replace with a project that's spec-backed, startable in days, and produces production-adjacent code.

---

## Challenge #4: What Should Be #3?

Two strong contenders emerge from the research:

### Option A: FOCIL (demoted from #1 to #3)
With FCR at #1 and acknowledging FOCIL's cross-layer nature, FOCIL becomes a strong #3 because:
- It's the confirmed Heze headliner — must be done regardless
- The CL-side work (IL committee selection, gossip topics, fork-choice filtering) can begin independently
- Other clients are at milestone 1-2 of 6 — starting now is not late
- A branch exists (needs rebase but that's tractable)

### Option B: P2P Erasure-Coded Block Propagation
- Pure CL/networking layer — no EL dependency
- Independent module, great showcase
- Critical prerequisite for shorter slots (12→8→6s)
- Lodestar just upgraded to libp2p v3 — excellent foundation
- Reed-Solomon libraries exist; integration is the novel work
- Feasibility: MEDIUM-HIGH per findings
- **But:** No formal spec/EIP yet (research-stage), violating spec-backed preference

### Option C: EIP-7688 Forward-Compatible SSZ (StableContainer)
- Co-authored by Cayman (Lodestar maintainer) — domain expertise available
- Requested by Lido and Rocketpool (real ecosystem demand)
- Spec in Review status (EIP-7495), consensus-specs PR #4630 open
- Branches exist in Lodestar fork
- Pure CL/SSZ layer
- **But:** Scope may be "medium" rather than "large" — depends on depth of SSZ library changes needed

**Recommendation for #3:** FOCIL (Option A). Despite the cross-layer concern, it's the most strategically important. The CL-only portions are substantial enough for a meaningful start, and beginning early positions Lodestar well for Heze devnets.

---

## Revised Ranking

| # | Project | Rationale |
|---|---------|-----------|
| **1** | **Fast Confirmation Rule** (PR #4747) | Perfect constraint fit. Pure CL, spec-backed, PR already open, Nimbus provides implementation roadmap, massive UX impact (16 min → 15-30 sec perceived finality). Can literally start today. |
| **2** | **FOCIL** (EIP-7805) | Strategic necessity (Heze headliner). CL portions are large and independent. Start CL-side work (committee selection, gossip, fork-choice) while ePBS stabilizes. Cross-layer parts can follow. |
| **3** | **FOCIL** stays at #2; for a true #3 research/moonshot slot: **8-Slot Epochs + Random Attester Sampling PoC** | Directly on Vitalik's stated finality trajectory. Parametric changes (SLOTS_PER_EPOCH 32→8) + committee restructuring (256-1024 random attesters). Produces a demo: "Lodestar with 48-second finality and no aggregation layer." CL-only, feasible, on-roadmap. More actionable than Minimmit because the changes are parametric/architectural rather than novel consensus algorithm design. |

---

## Summary Verdict

The proposed ranking overweights strategic importance and underweights the stated constraints. FOCIL is the most important project but not the best *first* project for one dev + AI starting in days. FCR is.

Minimmit is a moonshot that sounds impressive in a slide deck but fails the "start within days" and "spec-backed" constraints. Replace it with something that produces usable code on the roadmap's trajectory.

**Key principle:** Pick the project where constraints and impact intersect, not the one with the highest abstract importance.

| Change | From → To | Reason |
|--------|-----------|--------|
| FOCIL | #1 → #2 | Cross-layer; can't fully test CL-only |
| FCR | #2 → #1 | Perfect constraint fit; clear impl path |
| Minimmit | #3 → dropped | No spec, no test vectors, can't start in days |
| 8-Slot Epochs + Attester Sampling | (new) → #3 | On-roadmap, parametric, CL-only, demo-worthy |
