# Checkpoint State in ePBS

**Source:** ChatGPT Deep Research (API extraction)
**Conversation ID:** 69d45091-9680-8331-99ae-93e8df06c331
**Assistant messages:** 4
**Model:** gpt-5-4-pro
**Status:** finished_successfully
**Total chars:** 6954

---

I’m checking the current spec and related discussions first, because this is subtle and the details around EIP-7732 and checkpoint-state semantics matter here. Then I’ll map your proposed slot shifts against committee computation, weak subjectivity, and attestation validation.

I’ve confirmed the current Gloas spec still derives checkpoint states phase0-style from `block_states[target.root]` advanced to the epoch boundary, even though fork choice now tracks payload status and `payload_states` separately.

Moving the checkpoint back by one or two slots does not look like a clean fix: current attestation and weak-subjectivity machinery assume a boundary-state convention. I’m now pinning down which invariants break and whether the spec repo discusses an alternative redesign.

Not by itself. The real bug is not “the checkpoint is at the boundary” so much as “the checkpoint state lookup is collapsing a branch-aware object into a branch-unaware one.” In Gloas fork choice, ancestors are already modeled as `ForkChoiceNode(root, payload_status)`, and child import explicitly chooses either `block_states[parent_root]` or `payload_states[parent_root]` depending on whether the parent is EMPTY or FULL. But `get_checkpoint_block(...)` returns only the ancestor’s `root`, dropping the `payload_status`. So a bare `{epoch, root}` no longer identifies a unique post-state, and moving the slot to `N-1` or `N-2` does not remove that loss of information; it just moves where it shows up. citeturn476737view1turn571261view1turn571261view2

Your `N-2` intuition also runs into a second issue: in the spec, “payload known” is stronger than “payload revealed and PTC-voted.” Gloas now requires that a FULL attestation (`index == 1`) is only valid if the payload is actually present in `store.payload_states`, and the “timely/data-available” checks similarly require local payload availability in addition to votes. So even two slots back, the consensus-relevant distinction is not just reveal/vote timing; it is whether the FULL state has actually been imported and validated. citeturn571261view0turn476737view1turn444948view1

The boundary is special because that is where the ambiguity becomes state-critical. `process_execution_payload` imports execution-layer deposit/withdrawal/consolidation requests into consensus state, while epoch processing later runs `process_pending_deposits`, `process_pending_consolidations`, and `process_builder_pending_payments`. So the canonical state at slot `epoch*32` genuinely depends on whether the last block of the previous epoch was followed on its EMPTY branch or its FULL branch. That is exactly why “derive checkpoint state by taking `block_states[target.root]` and advancing to the epoch start” becomes under-specified under ePBS. citeturn111575view1turn312294view0turn699819view0

That is also why defining the checkpoint state at `epoch*32 - 1` or `epoch*32 - 2` is not a clean fix for committee computation. Attestation verification still needs a target state from which to derive committees and indexed attestations. In phase0/Gloas, `on_attestation` stores the target checkpoint state and uses it to build the indexed attestation, while committee computation depends on the active validator set and seed for that epoch. Gloas epoch processing also updates registry state, effective balances, sync committees, proposer lookahead, and the PTC window. A pre-boundary state has not run those updates yet, so it is not, in general, the canonical “epoch e committee state.” citeturn699819view0turn903085view0turn903085view2turn312294view0

So for your two concrete variants:

1. **Boundary checkpoint state, but always CL-only (`block_states`) and make epoch transition ignore payload-derived pending queues.**  
This can work only as a real protocol redesign. If the epoch-start state is intentionally made payload-independent, then a `{epoch, root}` checkpoint becomes unambiguous again. But that means EL-derived requests no longer affect the boundary state at the point they do today, so you are changing activation/exit/consolidation timing and queue semantics, not just fixing a cache key. In other words, this is a coherent design direction, but it is much bigger than a checkpoint-definition tweak. citeturn111575view1turn312294view0turn756800view0

2. **Redefine the checkpoint to one slot before the boundary.**  
This is worse. First, the `N-1` block still has the same FULL/EMPTY ambiguity for its own root, so `{epoch, root}` is still under-specified unless you also choose a synthetic CL-only meaning. Second, attestation logic currently enforces `target.epoch == compute_epoch_at_slot(attestation.data.slot)` and derives the checkpoint block at the epoch’s first slot. If you move the checkpoint off the boundary, you either validate epoch-`e` attestations against the wrong state, or you create two notions of “checkpoint state”: a synthetic one for committee validation and the real canonical one. That is likely to be brittle for slashing, interop, and client simplicity. citeturn571261view0turn476737view1turn699819view0

For weak subjectivity, moving the checkpoint slot is also costly. The current WS checkpoint format is `block_root:epoch_number`, and the stale-check logic assumes the WS state satisfies both `compute_epoch_at_slot(ws_state.slot) == ws_checkpoint.epoch` and `get_block_root(ws_state, ws_checkpoint.epoch) == ws_checkpoint.root`. If `{epoch, root}` can map to two different states, or if the checkpoint state is no longer at the epoch boundary, those assumptions stop being self-contained. WS/checkpoint sync would need an extra discriminator. Since the FULL branch already commits to a post-payload `state_root`, one natural discriminator is “state root” (or equivalently a branch/status bit plus the block root), not a shifted slot. citeturn330172search1turn111575view1turn571261view1

So my bottom line is:

- **No, defining checkpoint states as `epoch*32 - 2` or `epoch*32 - 1` does not really solve the ePBS ambiguity.**
- The root problem is that Gloas branch identity is `(root, payload_status)`, but checkpoint-state lookup is still effectively keyed by just `(epoch, root)`.
- The clean fixes are either:
  - make the **canonical boundary state payload-independent** by moving payload-derived effects out of epoch processing, or
  - keep boundary semantics, but make **checkpoint-state derivation branch-aware**—for example by carrying payload status, deriving the target state from the attested branch rather than from `checkpoint.root` alone, or anchoring WS/checkpoint-sync with a state root in addition to the block root. Fork choice already has the extra bit; the checkpoint path is where it gets dropped. citeturn476737view1turn571261view1turn111575view1

If useful, I can sketch what a branch-aware `store_target_checkpoint_state(...)` would look like under Gloas without changing the FFG checkpoint object itself.

