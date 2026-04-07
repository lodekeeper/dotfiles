# Gloas Checkpoint State Problem — Consolidated Research Synthesis

**Date:** 2026-04-07
**Sources:** 8 ChatGPT Deep Research conversations (GPT-5.4 Pro, 41+ min thinking each), spec PRs/issues, beacon-APIs discussion, Lodestar PRs
**Confidence:** HIGH for problem characterization, MEDIUM for solution direction

---

## Executive Summary

The Gloas (ePBS) checkpoint state ambiguity is **formally recognized as of today** at the spec level. Two new items were opened on April 7, 2026:

- **ethereum/consensus-specs#5074** (dapplion): "Fork-choice justified balances in underspecified post-Gloas" — formally identifies the bug
- **ethereum/consensus-specs#5073** (twoeths): "feat: add finalized_checkpoint_payload_status to fc store" — first spec-level fix attempt

No merged fix exists. The published Gloas fork-choice spec is payload-aware in tree traversal but still computes weights from `store.checkpoint_states[store.justified_checkpoint]` using the inherited Phase0 `store_target_checkpoint_state` which reads from `block_states[target.root]` — ambiguous under ePBS.

---

## The Core Problem

In Gloas, each slot produces two possible post-states:
- **post-beacon-block** (`block_states[root]`): CL-only, no payload effects
- **post-payload** (`payload_states[root]`): includes execution payload effects

`store_target_checkpoint_state` takes `block_states[target.root]` and advances via `process_slots` to the epoch boundary. Under ePBS:
- `process_execution_payload` applies `execution_requests` (deposits, exits, withdrawals, consolidations)
- `process_epoch` later consumes pending queues (`process_pending_deposits`, `process_pending_consolidations`, `process_builder_pending_payments`)
- A pre-boundary checkpoint block + skipped epoch-boundary slot → the epoch-start state depends on payload processing

Neither `block_states` nor `payload_states` alone gives a safe epoch-boundary state for skipped-slot cases.

---

## Spec Activity (as of April 7, 2026)

### Active Items
| Item | Author | Status | Description |
|------|--------|--------|-------------|
| consensus-specs#5074 | dapplion | Open (issue) | Formally identifies checkpoint-state ambiguity |
| consensus-specs#5073 | twoeths | Open (PR) | Adds `finalized_checkpoint_payload_status` to Store |
| consensus-specs#4960 | unnawut | Open (PR) | Gloas fork choice test for deposits with epoch transitions |
| beacon-APIs#572 | nflaig | Open (issue) | Update state v2 API for Gloas |

### Key Merged PRs
| PR | Author | Date | Effect |
|----|--------|------|--------|
| #4802 | — | 2026-01-05 | Refactored `get_ancestor` to return `ForkChoiceNode(root, payload_status)` |
| #4800 | — | 2026-01-05 | Refactored `get_weight` and `is_supporting_vote` for payload awareness |
| #4918 | potuz | 2026-02-23 | Only allow attestations for known payload statuses |
| #4939 | — | — | Ignore unseen `index==1` attestations, request missing envelope |

### Rejected
| PR | Date | Reason |
|----|------|--------|
| #4655 | 2025-10-24 | `payload_status` in `AttestationData` — deemed too complex in EIP-7732 Breakout Call #26 |

---

## Analysis of PR #5073 (twoeths)

### What it does:
1. Adds `finalized_checkpoint_payload_status: PayloadStatus` to `Store`
2. In `get_forkchoice_store`: derives initial status from `anchor_state.execution_payload_availability`
3. In `update_checkpoints`: when finalized checkpoint advances, uses `get_ancestor(store, justified_checkpoint.root, finalized_slot).payload_status`
4. In `on_block`: asserts incoming block's ancestor at finalized slot has matching payload status

### Critical concern (ensi321, immediate review):
> "finalized_checkpoint_payload_status is not really finalized. It is a payload status for the finalized checkpoint derived from justified checkpoint. So the payload status itself is only justified."

This is the same concern we identified: the justified checkpoint can reorg (only requires 2/3 attestation support), so different justified checkpoints could walk through different children → different payload status → the "finalized" payload status inherits justified-level reorgability.

### Does NOT address:
- `store_target_checkpoint_state` (the actual checkpoint state derivation)
- Justified checkpoint state ambiguity (dapplion's #5074 concern about justified balances)
- Beacon API endpoint semantics

---

## Approaches Analysis (Updated with Deep Research Findings)

### Approach 1: Don't advance, return raw post-beacon-block state (Potuz)
**Status:** Potuz actively advocates this for API endpoints
**Assessment:** Breaks `is_within_weak_subjectivity_period`, `on_attestation` committee computation, fork choice weight calculation. All downstream consumers expect epoch-boundary states.

### Approach 2: Infer payload status from justified via `get_ancestor()` (Tuyen/twoeths)
**Status:** Active spec PR #5073 (for finalized only, not justified)
**Assessment:** Justified-derived, not truly finalized. Non-deterministic: the finalized state becomes `f(finalized_checkpoint, justified_checkpoint)`. Checkpoint sync can't verify without knowing which justified checkpoint was used. Lodestar already has infrastructure (`CheckpointWithPayloadStatus` in fork choice).

### Approach 3: Checkpoint triple `{epoch, root, payloadStatus}` 
**Status:** Rejected at spec level (PR #4655 closed Oct 2025)
**Assessment:** Timing issue at epoch boundary (attesters at 3000ms, PTC at 9000ms, `data.index=0` enforced for same-slot). Clean semantics but massively invasive. The research confirmed: same-slot ordinary attestations **intentionally** do not vote FULL vs EMPTY.

### Approach 4: Always advance from block_states (CL-only)
**Status:** Not viable
**Assessment:** Loses execution requests → wrong active validators after epoch transition for skipped-slot cases.

### NEW: Approach 5 family — Make CL-relevant payload effects deterministic before reveal
**Sources:** consensus-specs#3856, "Paths to hardening PBS" (D'Amato), Potuz's "ePBS design constraints"
**Variants:**
- **Requests-on-bid**: Put execution requests on the signed bid (visible before reveal)
- **Carry-forward**: If current payload is missed, force next payload to include same requests
- **Richer blinded object**: Keep withdrawals/exits/deposits visible without full payload

**Assessment:** Most promising conceptual direction. Gloas already partially adopted this pattern: `process_block` calls `process_withdrawals(state)` before bid processing, `payload_expected_withdrawals` stored in `BeaconState`. But `execution_requests` are still only consumed in `process_execution_payload`.

### NEW: Approach 6 — 3SF/COMMITTED-FULL-EMPTY split
**Source:** "Integrating 3SF with ePBS, FOCIL, and PeerDAS" (Aug 2025)
**Mechanism:** Finality operates on `COMMITTED` chain (the block independently of payload), then fork choice splits into FULL/EMPTY interpretations using availability-committee votes.
**Assessment:** Conceptually cleanest — makes finality cover blocks, not payloads. But it's a different finality protocol, not a patch to current Gloas.

### NEW: Approach 7 — Change attestation/PTC timing
**Source:** "Slot Restructuring: Design Considerations" (Jun 2025)
**Mechanism:** Delay attestations until after payload/PTC, or make attesters the availability oracle.
**Assessment:** Redesign that avoids the ambiguity entirely. But cuts against Gloas's core design of keeping execution off the pre-attestation hot path.

---

## Key Timing Analysis

Confirmed from deep research (Gloas spec analysis):

| Event | Deadline | 
|-------|----------|
| Ordinary attestation | 3,000ms (2500 bp) |
| Aggregate | 6,000ms (5000 bp) |
| PTC (payload attestation) | 9,000ms (7500 bp) |

- Same-slot attestations MUST set `data.index = 0` — protocol intentionally keeps attesters blind to current-slot payload
- PTC votes are slot-specific (`data.slot == state.slot`) — previous PTC can't certify current slot
- `record_block_timeliness` uses strict `< threshold` — "timely" means seen BEFORE deadline
- Fork choice delays attestation effect until next slot (`current_slot >= attestation.slot + 1`)

**Implication:** Epoch-boundary attesters cannot know the boundary block's payload status. The protocol treats it as PENDING and resolves it later via payload reveal + PTC.

---

## Historical Precedent

This is **genuinely novel**. No BFT system has had two valid post-states behind one finalized root:
- **Bellatrix**: `execution_payload` inside `BeaconBlockBody` → root commits to unique payload
- **Phase0/Altair**: One state per root, no ambiguity
- **CometBFT**: Header carries definite `AppHash` 
- **DiemBFT**: Closest — votes carry `exec_state_id`, QC certifies `commit_state_id`. But it resolves ambiguity by explicitly certifying, not leaving two variants

---

## Payload Finality Gap

The gap is **bounded under normal liveness** (~1 checkpoint):
- Once checkpoint `C_e` is beacon-finalized, every block strictly BEFORE `C_e` lies on finalized ancestry with fixed payload status
- The ambiguous case is always the checkpoint block `C_e` itself: FFG finalizes root, but not which child is canonical
- Larger gaps only from ordinary finality/liveness degrading, not from payload-specific backlog

---

## p2p Spec — No Inconsistency (Corrected)

~~Initially flagged as a bug~~ — the p2p `_[REJECT]_` convention states what must be TRUE (reject if NOT true), not what triggers rejection. So `_[REJECT]_ attestation.data.index == 0 if block.slot == attestation.data.slot` means "index must be 0 for same-slot, reject otherwise." This is **consistent** with validator.md, fork-choice.md, and beacon-chain.md.

---

## Beacon-APIs #572 Discussion Summary

| Participant | Position |
|-------------|----------|
| **potuz** | Return consensus post-state (block_states) for all identifiers. Simple, deterministic. Payload state separate or behind optional selector. |
| **twoeths** | Head = node's head state. Finalized/justified = comes with payload status in Lodestar. Slot queries = optional `payloadStatus` param. Finalized = trace back from justified via HackMD approach. |
| **michaelsproul** | Finalized/justified = "probably the empty states" (finality justifies block root, not payload envelope). Slot = canonical state. Lighthouse plans to keep canonically full or empty states older than finalized. |
| **rolfyone** | Return "best state" — consult fork choice for payload status. |
| **ensi321** | Consult fork choice for current chain's payload status at that slot. |

No consensus reached. Issue still open with 9 comments.

---

## Lodestar's Position (Furthest Ahead)

Lodestar has the most mature implementation-side handling:
- `CheckpointWithPayloadStatus` type in fork-choice store
- `forkChoice:justified` and `forkChoice:finalized` events carry `CheckpointWithPayloadStatus`
- Archival path takes `finalizedCheckpoint: CheckpointWithPayloadStatus`
- Key PRs: #8982 (attestation index→payload status), #8996 (explicit payload status in ancestor APIs), #9119 (PayloadExecutionStatus tracking), #9005/#9028 (normalize finalized/justified to EMPTY variant for serving)

---

## Open Questions

1. Should `store_target_checkpoint_state` be overridden in the Gloas spec to use `payload_states` when payload is FULL? (Requires spec PR)
2. Is the justified→finalized payload status derivation in #5073 acceptable despite being only justified-level secure?
3. Should Approach 5 (make execution requests visible before reveal) be pursued as a cleaner long-term fix?
4. What is the Beacon API semantics for finalized/justified endpoints? (beacon-APIs#572 unresolved)
6. Should there be a new checkpoint sync flow for Gloas that includes payload status?

---

## Recommendation

**Short-term (Lodestar implementation):** Continue with `CheckpointWithPayloadStatus` approach. For finalized/justified API endpoints, normalize to EMPTY variant (consensus post-state) as #9005/#9028 do. This matches potuz's and michaelsproul's preferences and is deterministic.

**Medium-term (spec level):** Support twoeths' PR #5073 direction but push for also addressing the justified checkpoint state computation (dapplion's #5074). The PR currently only pins finalized payload status — the justified balances issue needs a separate `store_target_checkpoint_state` override.

**Long-term (protocol level):** Monitor the "make execution requests visible before reveal" family (Approach 5). This removes the ambiguity at the source. The staged execution requests variant — storing requests in a staging area and processing in epoch transition — deserves formal evaluation.
