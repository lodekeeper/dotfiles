# Ethereum Gloas ePBS Discussion

**Source:** ChatGPT Deep Research (API extraction)
**Conversation ID:** 69d450ad-fe24-832a-92dd-95bec234f289
**Assistant messages:** 5
**Model:** gpt-5-4-pro
**Status:** finished_successfully
**Total chars:** 15283

---

I’m searching the specs repos, research threads, HackMD, beacon-APIs, and Lodestar/client discussions, then I’ll return exact links grouped by your seven topics and note any gaps in public discussion.

I’m searching the spec repos, research threads, HackMD, researcher blogs, beacon-APIs, and client implementation notes for 2025–2026 discussions, then I’ll organize direct links and concise summaries by your seven topics.

I’ve now pinned down a few concrete anchors: beacon-APIs issue #572 on Gloas state-API ambiguity, the current Gloas spec still lacking a `store_target_checkpoint_state` override, and PR #4655 proposing `AttestationData.index` → `payload_status`.

I’ve now confirmed the key state-ambiguity proposal too: Tuyen Nguyen’s HackMD uses `justified_checkpoint + get_ancestor()` to infer payload status for skipped-slot finalized checkpoints. I’m cross-checking that against Lodestar’s workaround and the API/spec threads to separate explicit proposals from client-only fixes.

I found a real gap, not just a scattered set of bugs: the published Gloas fork-choice spec is payload-aware, but it still does **not** publish a Gloas-specific replacement for `store_target_checkpoint_state`. That is why the most concrete 2026 discussion about finalized/justified state semantics shows up in HackMD, beacon-APIs, and client repos rather than in one consensus-specs PR. citeturn619260view0turn619260view3turn619260view4turn619260view8turn896733view0turn145159view1

1. `ethereum/consensus-specs`: what changed, and what did **not** change

- The current Gloas spec adds `payload_states`, makes `get_ancestor()` return a `ForkChoiceNode(root, payload_status)`, changes `get_checkpoint_block()` to use that payload-aware ancestor, and keeps `get_weight()` anchored on `store.checkpoint_states[store.justified_checkpoint]`. But the Gloas fork-choice page has **no** `store_target_checkpoint_state` section at all, while Phase0 still defines it as `copy(store.block_states[target.root])` followed by `process_slots(...)`. In other words, the published spec made fork choice payload-aware without yet publishing a payload-aware checkpoint-state helper. citeturn619260view0turn619260view2turn619260view3turn619260view4turn619260view5turn619260view8

- The most relevant recent consensus-specs PRs I found are:
  - **#4802, “Refactor `get_ancestor` in Gloas”**, merged **January 5, 2026**. Its key effect is that `get_ancestor()` returns both the ancestor root and payload status, with `PENDING` for future/missed-slot style cases. citeturn378035view0turn244992view6
  - **#4800, “Refactor `get_weight` and `is_supporting_vote`”**, merged **January 5, 2026**. This is part of the payload-aware fork-choice path, including payload-sensitive vote support logic. citeturn378035view1turn619260view8turn244992view7
  - **#4918, “Only allow attestations for known payload statuses”**, merged **February 23, 2026**. Potuz’s rationale was that requiring known payload status ensures an attestation counts for at least one of the empty/full branches below the pending node and avoids counting invalid-payload attestations. citeturn378035view2turn888863view0

- I did **not** find a recent consensus-specs PR that explicitly publishes a Gloas override of `store_target_checkpoint_state`; the current Gloas page still lacks one. The spec work I found is concentrated in payload-aware ancestry/weight/attestation logic, not checkpoint-state computation. citeturn619260view3turn619260view4turn153853search0

2. EthResearch and nearby research discussions

- The clearest **2025** EthResearch post in the same design space is **“Integrating 3SF with ePBS, FOCIL, and PeerDAS”** (August 12, 2025). It treats the justified checkpoint as **COMMITTED**, then splits it into **FULL** and **EMPTY** interpretations and walks whichever branch has higher weight from votes that preserve the same payload interpretation. That is effectively a payload-aware answer to checkpoint/state ambiguity, even though it does not redefine the `Checkpoint` container. citeturn158738view11turn158738view12

- Another **2025** EthResearch post, **“Slot Restructuring: Design Considerations and Trade-Offs”** (June 30, 2025), explicitly frames attesters as the availability oracle: if the beacon block is valid but payload is missing, the next proposer should build on the parent; if both are valid, build on that beacon block. The post calls out “payload availability bit for votes” and “3-choice fork-choice” as ePBS complexity. citeturn448090view2turn448090view3

- I did **not** locate a new **2025–2026** EthResearch post that explicitly says “make `Checkpoint = (root, epoch, payload_status)`.” The clearest public checkpoint-container discussion I found is still Potuz’s older **Feb. 20, 2024** EthResearch post **“ePBS design constraints”**, which says that **in principle** a checkpoint should be `(R, E, payload_present)` because FULL vs EMPTY lead to different beacon states, but then argues it is probably acceptable and much simpler to keep checkpoints as just `(R, E)`. citeturn158738view13

- For “payload status in attestations,” the closest explicit design writeup I found is Francesco D’Amato’s **Feb. 13, 2024** EthResearch post **“Paths to hardening PBS”**, which proposes augmenting attestations with `execution_payload_root`, while **“Minimal ePBS - Beacon Chain Changes”** keeps checkpoint as the usual `(epoch, root)` pair. These are older than your 2025–2026 window, but they are still the load-bearing public design references behind later discussions. citeturn158738view14turn158738view15turn158738view16

- One relevant **non-EthResearch** 2025 discussion: the **October 10, 2025** EIP-7732 breakout call explicitly put **“Attestation container refactoring”** on the agenda, saying reusing the same container “adds complexity & confusion.” The summary says Mehdi raised that `index` was no longer hardcoded to zero, and the action item was to create a PR for the Gloas attestation-container issue where `index` is used to signal payload status. citeturn647955view0turn647955view1

3. Potuz / researcher blogs on the finalized-state problem

- Potuz’s two January 2026 blog posts are the clearest public blog-form explanations I found:
  - **“Gloas Annotated: Beacon-Chain”** (January 27, 2026)
  - **“Gloas Annotated: Forkchoice”** (January 30, 2026) citeturn839772search0turn839772search1

- In the beacon-chain post, Potuz explains the core ambiguity very cleanly: one CL block root can imply **two possible EL heads**—payload present, or payload absent with the parent payload still the EL head. He also notes that each slot effectively introduces two state-transition outcomes: full vs empty. citeturn635633view0turn635633view1

- In the fork-choice post, Potuz shows exactly how the spec resolves this at fork-choice level: `get_parent_payload_status()`, payload-aware `get_ancestor()` returning `ForkChoiceNode(root, payload_status)`, `get_checkpoint_block()` using that new ancestor function, and head search starting from the justified checkpoint with `PENDING`, then exploring EMPTY/FULL descendants. citeturn952739view0turn952739view1

- The strongest public blog discussion I found of the **finalized-state / finalized-payload** problem is Potuz’s “Implementation perks” section: he says the engine needs the finalized payload hash, but if the finalized checkpoint block is actually EMPTY, you cannot safely use the committed bid’s payload hash; you need to remember the latest payload hash that actually made it on-chain before the finalized checkpoint. That is extremely close to the “finalized state problem” you’re asking about. citeturn952739view2

- For Francesco D’Amato specifically, the clearest directly relevant public material I found was still the older EthResearch design discussion, not a separate 2025–2026 blog post on finalized-state semantics. citeturn158738view14

4. The HackMD you linked (`get_ancestor()` from justified checkpoint)

- The HackMD makes the ambiguity explicit: when the finalized checkpoint boundary falls on a **skipped slot**, the correct base state depends on whether the preceding block should be interpreted as **EMPTY** (`block_states[B]`) or **FULL** (`payload_states[B]`). It argues that the current “use post-block state of previous slot” approach means the finalized state is **not** one of `store.checkpoint_states` and breaks the old epoch-start-slot invariant used by checkpoint sync. citeturn158738view8turn158738view10turn274183view2turn274183view3

- Its proposed solution is exactly what you described: start from `justified_checkpoint`, call `get_ancestor(store, justified_root, finalized_start_slot)`, recover the ancestor’s payload status, choose `block_states[B]` or `payload_states[B]`, then `process_slots()` to the epoch boundary. The post argues this restores `finalized_state.slot == epoch * SLOTS_PER_EPOCH` and preserves checkpoint-sync compatibility. citeturn158738view9turn274183view2turn274183view3

- In effect, this HackMD functions like a payload-aware replacement for the missing Gloas `store_target_checkpoint_state` behavior. That is an inference on my part, but it is strongly supported by the fact that the published Gloas spec lacks such a helper while the HackMD supplies exactly the missing “choose the correct base state, then `process_slots`” logic. citeturn619260view3turn619260view4turn274183view2turn274183view3

5. Any proposals to “override `store_target_checkpoint_state`”?

- In the **published spec**, I found **no** override. The only published helper remains the inherited Phase0 version, which reads from `store.block_states[target.root]` and then processes slots to the epoch boundary. citeturn619260view4turn619260view5turn619260view6

- The closest public replacements/workarounds I found are:
  - the HackMD’s justified-checkpoint + `get_ancestor()` method, which chooses `block_states` vs `payload_states` before `process_slots()`; citeturn274183view2turn274183view3
  - twoeths’ April 6, 2026 beacon-APIs comment, which explicitly links that HackMD and argues finalized state can trace back from justified checkpoint to recover the exact EMPTY/FULL variant; citeturn461188view1turn461188view2
  - Lodestar’s March 2026 client fixes, which normalize finalized/justified checkpoint serving to the block-state / consensus-post-state variant for API and archival compatibility while still keeping payload status in fork-choice structures. citeturn145159view1turn626099view3

6. `ethereum/beacon-APIs` issue **#572** (`state v2 api for gloas`)

- The issue, opened **January 27, 2026**, states the core ambiguity directly: under ePBS there are **two state updates per slot**—one when the block is processed and another when the payload is processed—and `/eth/v2/debug/beacon/states/{state_id}` did not specify which one should be returned. citeturn896733view0turn896733view3

- Early in the thread, **ensi321** suggested a fork-choice-driven answer: consult fork choice, and if the currently tracked chain has payload at that slot, return the post-payload state. **rolfyone** reformulated that as returning the **“best state”** at that slot and extended the same idea to `/finalized`, `/justified`, and `/head`. citeturn513597view4turn513597view0turn513597view1

- **potuz** pushed back on that and argued for a simpler rule: return the **consensus post-state** for blockroot, slot, finalized, justified, and even head; if post-payload state is needed, expose it separately or behind an optional payload-status selector. citeturn434164view0turn434164view1turn434164view2turn926547view5turn461188view0

- **twoeths** then laid out the Lodestar view: head should be the node’s head state; finalized/justified in Lodestar already come with payload status; `{slot}` and debug queries benefit from an optional `payloadStatus` parameter; and for `finalized`, you can trace back from the justified checkpoint to determine the exact EMPTY/FULL variant, explicitly linking the HackMD you gave. citeturn434164view2turn434164view3turn434164view4turn461188view1turn461188view2

- **michaelsproul** mostly agreed with twoeths but added Lighthouse’s storage perspective: older than finalized, Lighthouse plans to keep the canonically full or empty/pending states; `{slot}` should return the canonical state at that slot; but `justified` and `finalized` “probably need to be the empty states” because finality justifies the block root, not necessarily its payload envelope. citeturn461188view0turn461188view1turn461188view2

7. Lodestar’s `CheckpointWithPayloadStatus` approach

- Lodestar has gone furthest, publicly, in treating “checkpoint + payload variant” as a real internal object. Its chain event types `forkChoice:justified` and `forkChoice:finalized` both carry `CheckpointWithPayloadStatus`, not a plain Phase0 checkpoint. citeturn872117search2

- Its archival path also takes `finalizedCheckpoint: CheckpointWithPayloadStatus` and uses both `rootHex` and `payloadStatus` when selecting ancestor/non-ancestor blocks. That is strong evidence that Lodestar’s fork choice really does treat payload status as part of checkpoint identity for internal traversal and pruning. citeturn643231view0turn872117search1turn872117search3

- The most relevant Lodestar PRs are:
  - **#8982**, merged **March 6, 2026**: attestation `data.index` encodes payload status (`0 = EMPTY`, `1 = FULL`) for previous-slot votes. citeturn378035view4
  - **#8996**, merged **March 9, 2026**: make `payloadStatus` explicit in ancestor-traversal APIs. citeturn626099view4
  - **#9119**, merged **March 30, 2026**: track `PayloadExecutionStatus` for `onExecutionPayload()`, so the FULL node is not hardcoded to `Valid` and can also be `Syncing` in optimistic paths. citeturn626099view6turn626099view7
  - **#9005** and **#9028** are the client-side manifestation of the finalized-state problem: #9005 says `finalized`/`justified` should normalize to the EMPTY checkpoint variant (consensus post-state) for serving semantics, and #9028 says finalized checkpoint API serving and archival had been incorrectly using the post-envelope variant and needed to be corrected to the canonical block-state variant for cross-client checkpoint-sync compatibility. citeturn145159view1turn145159view2turn626099view3

The main synthesis is this: the ecosystem has **not** converged on a single public spec-level answer yet. The spec trail made fork choice payload-aware; the HackMD / twoeths line argues finalized checkpoint state can recover the exact FULL/EMPTY semantics from justified ancestry; potuz and several API/client discussions prefer exposing the **consensus post-state** for stable public endpoints; and Lodestar appears to split the difference by carrying `CheckpointWithPayloadStatus` internally while normalizing some finalized-state APIs and archival to the block-state variant for compatibility. citeturn619260view0turn619260view3turn274183view2turn461188view2turn434164view1turn145159view1turn626099view3

If you want, I can turn this into a compact matrix of **“source / proposed semantics / EMPTY vs FULL rule / impact on checkpoint sync”** next.

