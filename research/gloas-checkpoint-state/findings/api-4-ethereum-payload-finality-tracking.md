# Ethereum Payload Finality Tracking

**Source:** ChatGPT Deep Research (API extraction)
**Conversation ID:** 69d4509f-bdd8-8325-a568-e41b981b5e27
**Assistant messages:** 4
**Model:** gpt-5-4-pro
**Status:** finished_successfully
**Total chars:** 8610

---

I’m checking the current EIP-7732/ePBS design notes, along with Engine API and checkpoint-sync behavior, to distinguish what the spec says today from any inferred “payload-finalized checkpoint.”

I’ve confirmed Gloas already splits beacon-only and post-payload state, while FFG finality still names only `{epoch, root}`. I’m now checking whether any official sync/Engine API text or research adds a second finality marker.

I found a near-direct research note: under ePBS, checkpoints could in principle include `payload_present`, but the apparent direction is still to keep checkpoints root-only and carry payload-settlement information separately.

Yes, in principle — but my take is that it is cleaner as a **derived payload-resolved / payload-finalized marker** than as a second Casper-style finality chain.

Your underlying problem is real. In current Gloas, processing a `SignedExecutionPayloadEnvelope` is a second state transition that mutates CL state, applies `execution_requests`, and verifies a post-payload `state_root`; deposit requests can append to `pending_deposits`, and epoch processing later consumes the pending deposit/consolidation queues. The fork-choice store already keeps both `block_states` and `payload_states`, while attestations and fork choice explicitly distinguish `EMPTY` vs `FULL`. Yet checkpoints remain plain `{epoch, root}` objects, and the closest research note says that, in principle, an ePBS checkpoint could need `(root, epoch, payload_present)`, but that it is “highly plausible” to keep `(root, epoch)` for simplicity. citeturn141344view1turn920199view0turn602527view2turn729943view1turn670194view0turn497339view0

1. On Engine API `safe` / `finalized`

The API shape would not change: EIP-7732 explicitly says “No changes needed” for the Engine API, and the Gloas validator flow still calls `notify_forkchoice_updated(head_block_hash, safe_block_hash, finalized_block_hash, ...)`. Separately, the Engine API itself defines `safeBlockHash` as a safe ancestor of head, and `finalizedBlockHash` as the most recent finalized block. So if you add a separate payload-finalized checkpoint, then yes, the EL `finalizedBlockHash` would have to lag the CL finalized checkpoint whenever the checkpoint block’s own FULL/EMPTY status is not yet settled. A natural mapping would be to keep `safe` at a more recent payload-resolved point and let `finalized` trail at the payload-finalized point. That mapping is my inference, not current spec text, but it preserves the existing safe-vs-finalized distinction better than redefining `finalized` to mean something weaker. citeturn701266view0turn105402view2turn497339view3turn497339view4

2. On checkpoint sync

You do not necessarily need two totally separate sync procedures, but you do need more than today’s single root-only anchor if you want deterministic **post-payload** state. Today the anchor store is built from one trusted `anchor_state`/`anchor_block`, `checkpoint_states` are keyed by plain checkpoints, and the inherited checkpoint-state helper populates a checkpoint state from `store.block_states[target.root]`. Meanwhile Gloas already creates two state updates per slot, and the Beacon API issue tracker has flagged that it is unclear which state a state endpoint should return once the payload is later revealed. So the choices are basically: checkpoint-sync to the lagging payload-finalized anchor; or keep the beacon-finalized anchor and also sync the payload-resolved/post-payload anchor data. The cleanest authenticated object for that second anchor is probably the envelope’s post-payload `state_root`, since the envelope already carries it and `process_execution_payload` verifies it. citeturn729943view1turn674959view2turn305920view0turn701266view2turn141344view1

3. On implementation complexity

Yes, complexity would rise materially. Gloas already adds `ForkChoiceNode(root, payload_status)`, `LatestMessage.payload_present`, `block_states`, `payload_states`, and separate payload votes. The research note explicitly says omitting payload presence from checkpoints “simplifies greatly forkchoice specification and implementation,” and API discussions already show ambiguity because there are two state updates per slot. Adding a second finality marker would push that complexity into storage, sync, CL↔EL derivation, and public APIs. It is not a whole second consensus mechanism, but it is more than “just one extra pointer.” citeturn229778view5turn729943view1turn497339view1turn305920view0

4. Could the payload-finality gap grow unboundedly?

My read is: **not as a new, independent gap under normal liveness**.

In Gloas, a block’s FULL/EMPTY status is inferred from a child: `get_parent_payload_status` compares the child bid’s `parent_block_hash` to the parent bid’s `block_hash`, and vote support propagates that ancestor payload status through descendants. Also, the special tie-breaker is only for the **previous slot**. That strongly suggests the extra ambiguity is intended to be near-tip/local, not an ever-growing second unresolved history. citeturn729943view2turn729943view3turn729943view4

There is also a useful structural point here. Because payload status is determined by a later descendant, once checkpoint `C_e` is beacon-finalized, every block **strictly before** `C_e` already lies on a finalized ancestry that fixes its payload status. The systematically awkward case is the checkpoint block `C_e` itself: FFG finalizes its root, but not yet which child of `C_e` becomes canonical, and that child is what determines whether `C_e` was FULL or EMPTY. So in steady state I would expect a payload-finalized checkpoint to lag by roughly **one checkpoint**, not drift arbitrarily far. A much larger gap would mostly come from ordinary finality/liveness degrading, not from payload reveals creating a separate unbounded backlog. That conclusion is an inference from the published fork-choice rules, not something the spec states outright. citeturn769254view0turn729943view5turn497339view0

5. Is this discussed in research?

Yes, the adjacent issue definitely is. The clearest source is the ePBS design-constraints note: it says that under ePBS a checkpoint could in principle be `(R, E, payload_present)` because the beacon state differs with and without payload, but that keeping checkpoints as `(R, E)` is probably safe and much simpler. I also found active discussion about post-payload-state availability in the EVM, and Beacon API ambiguity because ePBS introduces two state updates per slot. What I did **not** find is a prominent, already-adopted proposal for a standalone second “payload-finalized checkpoint.” citeturn497339view0turn305920view2turn305920view0

6. Could you just wait for justified to resolve payload status?

I would not use justified to define **finalized**. In the official fork-choice store, `justified_checkpoint` is the starting point for LMD GHOST, while `finalized_checkpoint` is the hard no-conflict boundary. So a justified-resolved payload state fits much more naturally as a **safe** or “payload-resolved” notion than as a finalized one. citeturn769254view0turn497339view4

That said, as an implementation heuristic, your alternative is attractive. For the current beacon-finalized checkpoint block, waiting until the next justified chain resolves FULL vs EMPTY will often give the right post-payload state earlier than waiting for strict finality. On a healthy network that may be correct almost all the time. But it is still reorgable by construction, so I would not let that drive EL `finalized`; I would let it drive EL `safe` or a new internal “payload-resolved” marker. citeturn769254view0turn497339view3turn497339view4

My bottom line: I would **not** add a second Casper-style finality chain. The cleaner choices seem to be either:
- keep FFG unchanged and define a derived payload-finalized point that usually trails by about one checkpoint, while using `safe` for a more recent justified-resolved point; or
- if you want protocol-level precision, augment the checkpoint/sync anchor with payload status or post-payload state root, which is closer to the published research discussion than a separate lagging finality chain. The current Gloas drafts look much more like “root-only FFG + extra payload-resolution machinery” than “two finality chains.” citeturn497339view0turn701266view0turn729943view1

If useful, I can sketch a concrete state machine for `beacon_finalized`, `payload_resolved_safe`, and `payload_finalized` and show how it would map onto `engine_forkchoiceUpdated`.

