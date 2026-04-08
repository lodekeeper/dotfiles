# Gloas Checkpoint State Proposal — Acceptance Criteria

**Date:** 2026-04-07
**Authors:** nflaig, lodekeeper

---

## Core Acceptance Criteria

### 1. Only 1 state transition per slot

There is only 1 persistent state transition per slot, based on the beacon block. No second state transition from the payload (`payload_states` is eliminated).

### 2. Checkpoint sync works with skipped slots

Dialing state to epoch boundary via `store_target_checkpoint_state` works correctly, even when slots are skipped, and is irrespective of payload status.

### 3. No malicious builder gaps

There are no gaps that allow a malicious builder to corrupt the chain. Execution requests must be EE-verified before entering CL state.

### 4. No CL spec gaps

Nothing in the CL spec makes this solution impossible to implement.

### 5. No hard blockers

No impossible-to-solve problems exist.

## Critical Requirements

### 6. Checkpoint state = chain state at epoch boundary

`store_target_checkpoint_state` must produce the **same** `process_epoch` result as the chain state (via `on_block`). The checkpoint state must not be missing payload effects that the chain includes during epoch processing, and vice versa.

### 7. Checkpoint state is deterministic

`block_states[root]` must be independent of `root`'s own payload status. All nodes compute the same checkpoint state for a given `{epoch, root}`, regardless of whether they have seen the payload.

## Additional Constraints

### 8. Execution requests must be EE-verified

Only EE-verified execution requests enter CL state. Unverified EL data must not be trusted (e.g., execution requests must NOT be placed in the bid).

### 9. Child block commits to parent payload status

The FULL/EMPTY distinction must be determined from the child block's bid (via `is_parent_node_full` — comparing `bid.parent_block_hash` with `parent.bid.block_hash`), not just from store presence of verified data.

### 10. No `payload_states`

The solution eliminates `payload_states` from the fork-choice `Store` entirely. There is only `block_states` — one state per beacon block root.

---

## Validation Notes

- Criterion 6 requires execution requests to be applied **AFTER** `process_slots` (which includes `process_epoch`), not before. The ordering must be: `process_slots → execution_requests → process_block`.
- Criterion 7 means `block_states[root]` may depend on **ancestor** payload statuses (which are committed to by the block chain), but never on root's **own** payload status.
- Criterion 9 was identified after finding a bug where the proposal unconditionally applied parent payload effects based on store presence, without checking what the child block expected.
