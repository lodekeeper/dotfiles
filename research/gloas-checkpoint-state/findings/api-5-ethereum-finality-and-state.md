# Ethereum Finality and State

**Source:** ChatGPT Deep Research (API extraction)
**Conversation ID:** 69d45057-c514-8333-ac2d-dcbe2484a672
**Assistant messages:** 4
**Model:** gpt-5-4-pro
**Status:** finished_successfully
**Total chars:** 10134

---

I’m checking the Ethereum specs and research history, then comparing that pattern to ePBS/Gloas and a couple of BFT designs; if you mean a specific Gloas proposal or draft, I’ll anchor to that rather than guess.

I’ve confirmed the key distinction: Bellatrix never had this ambiguity because the beacon block root already commits to a single execution payload, while Gloas explicitly models two post-states per root via `block_states` and `payload_states`. The current ePBS notes even say `(root, epoch)` is insufficient in principle, yet the spec appears to keep checkpoints unchanged and push FULL/EMPTY into fork-choice state instead.

The closest precedent seems to be the general pattern of finalizing a commitment and deriving extra state separately, not any older Ethereum case with two valid post-states behind one checkpoint. I’m now pinning down exact spec language and checking whether any major BFT protocol has a true analogue here.

As of the current published Gloas fork-choice draft, which is explicitly marked work-in-progress, the best answer is: Ethereum has prior precedents for **deriving** a more concrete state from a sparse checkpoint, but not for a case where one finalized checkpoint root leaves **two distinct post-states** live. That specific ambiguity looks new to ePBS/Gloas. citeturn827900view0turn894618view2turn117109view2

**1. Bellatrix is a partial precedent, but not the same problem.**

There is a useful correction to the Bellatrix framing: after Bellatrix, the checkpoint tuple `{epoch, root}` does not separately list an execution block hash, but the `root` is a **beacon block root**, and Bellatrix puts `execution_payload` inside `BeaconBlockBody`; that payload itself contains `block_hash`. So a finalized beacon block root already commits, indirectly but unambiguously, to a unique execution payload. Bellatrix’s `process_execution_payload` then checks `payload.parent_hash` against `state.latest_execution_payload_header.block_hash` and caches the new `latest_execution_payload_header`, making the CL→EL state mapping unique once the block is fixed. citeturn336946view1turn336946view0

That is **not** the same as ePBS. In EIP-7732/Gloas, `execution_payload` is removed from `BeaconBlockBody` and replaced by `signed_execution_payload_bid` plus payload attestations; payload execution becomes a separate step, and the state now separately tracks `execution_payload_availability` and `latest_block_hash`. The current Gloas fork-choice reflects this by introducing `ForkChoiceNode(root, payload_status)` and a separate `payload_states` map, while `on_block` explicitly chooses the parent pre-state from either `store.payload_states[parent_root]` or `store.block_states[parent_root]` depending on whether the parent is FULL or EMPTY. That is exactly the 1:2 ambiguity you are worried about. citeturn365570view1turn365570view2turn365570view3turn117109view0turn117109view2turn117109view4turn117109view5turn152765view1turn152765view2

**2. I do not see an analogous ambiguity in Phase0 or Altair.**

In Phase0, `Checkpoint` is just `{epoch, root}`. Altair’s fork-choice says that, unless modified, Phase0 functionality is inherited. The Phase0 checkpoint-state machinery assumes a unique state behind a given block root: `store_target_checkpoint_state` copies `store.block_states[target.root]` and only then advances that state to the epoch boundary if needed. So in the official Phase0/Altair design, the checkpoint tuple is sparse, but it is not ambiguous. citeturn894618view2turn894618view5turn486963view5

A helpful distinction is between “the tuple is not a full state commitment” and “the tuple is underdetermined.” Ethereum has **always** needed local chain data beyond the bare `{epoch, root}` tuple to reconstruct the checkpoint state. What it did **not** have before ePBS was a situation where that reconstruction had two equally live candidates for the same root. citeturn486963view5turn170826view0

**3. The skip-slot case today is deterministic for exactly the reason you described: one base state.**

Today, Phase0 fork-choice computes the checkpoint block as the ancestor at the epoch’s first slot via `get_checkpoint_block(store, root, epoch)`. If that checkpoint block root corresponds to a block before the boundary, `store_target_checkpoint_state` takes the unique `store.block_states[target.root]` and runs `process_slots` up to `compute_start_slot_at_epoch(target.epoch)`. `process_slot` writes the current `latest_block_header` root into `state.block_roots`, so if the epoch boundary slot is empty the previous block root is deterministically reused for that slot. This is why skip slots never introduced ambiguity in the checkpoint-state derivation path. citeturn486963view4turn486963view5turn486963view2turn486963view3turn486963view0turn486963view1

Your diagnosis of what changes under ePBS is consistent with the current Gloas draft: `on_block` no longer has a single canonical parent state for a given parent root, because it may extend either `block_states[parent_root]` or `payload_states[parent_root]` depending on payload status. So the old “copy block state, then `process_slots`” pattern no longer gives a unique answer unless the protocol also tells you which of those two base states is canonical for that checkpoint root. citeturn117109view4turn117109view5turn117109view2

**4. Other BFT protocols have related patterns, but the closest analogies split in two directions.**

Tendermint/CometBFT is only a **loose** precedent. CometBFT commits a block header and includes an `AppHash` that is returned by the application after executing and committing the **previous** block; CometBFT explicitly says that this hash is application-determined and not validated by the consensus engine. So there is a “finality covers consensus object, fuller application state is summarized or inferred elsewhere” flavor there. But the header still carries one definite `AppHash`, so it does not create an EMPTY-vs-FULL ambiguity for the same committed block root. citeturn602797view0turn602797view1turn602797view2

A closer HotStuff-family precedent is DiemBFT. Its votes carry both block identity and a speculated execution-state identifier (`exec_state_id`), and its quorum certificates carry `LedgerCommitInfo.commit_state_id`. The paper is explicit that this is done to guarantee deterministic execution outcomes, and that when a QC causes a parent to commit, the same quorum also certifies the committed ledger state. That is a real precedent for “finality certificate plus separately authenticated state identifier.” But notice the difference from ePBS: DiemBFT resolves the ambiguity by **explicitly certifying the state id**, not by leaving two state variants to be inferred from the same finalized root. citeturn663142view0

**5. A separate derivation function is the closest Ethereum-native pattern.**

Ethereum already has a CL→EL derivation pattern in Bellatrix. The “safe block” doc derives a safe beacon-block root from the consensus store, then derives the safe execution block hash from that beacon block’s execution payload. Bellatrix validator logic also passes a separate `finalized_block_hash`, described as the hash of the latest finalized execution payload, into `notify_forkchoice_updated`, and the engine API applies finality to execution state up to that hash. So architecturally, “consensus finalizes one object; another finalized object is derived from it” is already an Ethereum pattern. citeturn522990view0turn441574view2turn625229view0turn625229view1

That is also the direction the ePBS research discussion appears to lean. Potuz’s design-constraints post says that, in principle, ePBS checkpoints might need `(R, E, payload_present)`, because the actual beacon state differs depending on whether the payload transition happened; but it then argues it is plausible to keep checkpoints as just `(R, E)` because checkpoints are mainly a consensus/fork-choice object. The current Gloas material matches that shape: `BeaconState` still has `previous_justified_checkpoint`, `current_justified_checkpoint`, and `finalized_checkpoint` as `Checkpoint`, while fork-choice adds `ForkChoiceNode(root, payload_status)`, `LatestMessage(..., payload_present)`, and `payload_states`. Attestation validation in the draft still checks FFG target consistency with the root-only `get_checkpoint_block(...)`, while separately enforcing payload-status constraints. citeturn170826view0turn241384view1turn117109view0turn117109view2turn522521view0

So my synthesis is:

Ethereum has already solved two nearby problems:  
(1) deriving a checkpoint state from `{epoch, root}` plus deterministic slot processing, and  
(2) deriving EL safe/finalized objects from CL anchors when the CL root uniquely commits to the EL payload.

What it has **not** previously had to solve, in the official specs, is your exact case: a finalized checkpoint root that still leaves **two valid candidate post-states** behind that same root. In that sense, ePBS/Gloas is new. The closest historical design patterns are either Bellatrix-style **separate derivation** or DiemBFT-style **explicit certification of an extra state identifier**. Tendermint/CometBFT is a weaker analogy because it still commits one definite application hash in the header. citeturn486963view5turn336946view0turn117109view2turn170826view0turn663142view0turn602797view1

The crisp answer to your question is: `{epoch, root}` by itself is no longer enough to name a unique “finalized executed state” in ePBS unless the protocol adds a unique FULL/EMPTY resolution rule. Current Ethereum research appears to be treating that as a **separate derivation / fork-choice-status problem**, not as something Casper FFG itself necessarily has to encode inside the checkpoint tuple. citeturn170826view0turn117109view0turn117109view2turn522521view0

If useful, I can turn this into a more formal design memo with candidate definitions like `finalized_consensus_checkpoint`, `finalized_payload_status(root)`, and `derive_finalized_executed_state(...)`.

