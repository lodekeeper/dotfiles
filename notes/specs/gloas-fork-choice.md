# Gloas/EPBS — Fork Choice Spec Notes

*Source: `consensus-specs/specs/gloas/fork-choice.md`*
*Studied: 2026-02-15*

## Core Change: Payload-Aware Fork Choice

The fork choice now tracks **three payload states** per block:
- `PAYLOAD_STATUS_PENDING` (0) — payload not yet known
- `PAYLOAD_STATUS_EMPTY` (1) — block without payload (builder didn't deliver)
- `PAYLOAD_STATUS_FULL` (2) — block with payload delivered

Fork choice nodes are `ForkChoiceNode(root, payload_status)` — same block root can appear as both EMPTY and FULL children.

## Store Changes

New fields:
- **`execution_payload_states`**: `Dict[Root, BeaconState]` — post-payload states
- **`ptc_vote`**: `Dict[Root, Vector[boolean, PTC_SIZE]]` — PTC votes per block
- **`block_timeliness`**: Now a `Vector[boolean, 2]` — [attestation_timely, ptc_timely]

## Two-Phase State Selection in `on_block`

When processing a new block:
- If parent is **FULL** (parent has payload): use `execution_payload_states[parent_root]`
- If parent is **EMPTY** (no payload): use `block_states[parent_root]`
  - Must also verify `bid.parent_block_hash == parent_bid.parent_block_hash` (empty block preserves hash)

This is critical: the pre-state for a new block depends on whether the parent's payload was delivered.

## `on_execution_payload` Handler

New handler — called when `SignedExecutionPayloadEnvelope` arrives:
1. Verify beacon_block_root is known
2. Check blob data availability
3. Copy `block_states[beacon_block_root]`
4. Process execution payload on copied state
5. Store in `execution_payload_states[beacon_block_root]`

## PTC Voting

- `on_payload_attestation_message`: Updates `store.ptc_vote[root]` bitmap
- Works for both in-block attestations (signature skipped) and wire messages
- Validator must be in the PTC for that slot
- Wire messages must be for current slot
- **`is_payload_timely`**: `sum(ptc_vote[root]) > PAYLOAD_TIMELY_THRESHOLD` (>256 of 512 = majority)
  - Also requires payload to be locally available (`root in execution_payload_states`)

## Modified Fork Choice Head Selection

### `get_node_children`
For a given node:
- **PENDING** → children are EMPTY + FULL (if payload available)
- **EMPTY/FULL** → children are PENDING nodes for blocks whose parent matches this payload status

This creates a tree: ... → PENDING → EMPTY/FULL → PENDING → EMPTY/FULL → ...

### `get_head` 
LMD-GHOST traversal with three-way comparison:
1. `get_weight(store, child)` — attestation score
2. `child.root` — lexicographic tiebreak
3. `get_payload_status_tiebreaker` — payload preference

### `get_weight`
- For PENDING nodes or not-current-slot: returns attestation_score + proposer_boost (if applicable)
- For current-slot EMPTY/FULL nodes: returns 0 (weight comes from parent PENDING node)

### Payload Status Tiebreaker
For previous-slot blocks choosing between EMPTY and FULL:
- FULL gets priority 2 if `should_extend_payload` → PTC majority voted present
- EMPTY gets priority 1
- FULL without PTC support gets priority 0 (lowest)

### `should_extend_payload`
Prefer FULL (extend payload) if:
1. PTC says timely, OR
2. No proposer boost root set, OR
3. Proposer boost block doesn't build on this root, OR
4. Proposer boost block builds on FULL parent

## `is_supporting_vote` — Vote Counting

A vote supports a node if:
- **Same root, PENDING**: always supports
- **Same root, EMPTY/FULL**: vote must be from a later slot AND payload_present must match
- **Different root**: ancestor at the node's slot must match root AND payload status

## Modified Reorg Logic

### `is_head_weak`
Now also counts equivocating validator weight from head slot committees.
This makes the function monotonic: more attestations can only increase weight.

### `should_apply_proposer_boost`
Proposer boost applied unless:
- Parent is weak AND from previous slot AND there are early equivocations for same proposer

### `is_parent_strong`
Now uses `ForkChoiceNode` with parent's payload status for weight calculation.

## Timing Changes (Gloas)
All slot component timings are adjusted for Gloas epoch:
- `get_attestation_due_ms` → uses `ATTESTATION_DUE_BPS_GLOAS`
- `get_aggregate_due_ms` → uses `AGGREGATE_DUE_BPS_GLOAS`
- `get_sync_message_due_ms` → uses `SYNC_MESSAGE_DUE_BPS_GLOAS`
- `get_contribution_due_ms` → uses `CONTRIBUTION_DUE_BPS_GLOAS`
- NEW: `get_payload_attestation_due_ms` → uses `PAYLOAD_ATTESTATION_DUE_BPS`

## Attestation Validation Changes
- `data.index` must be 0 or 1 (payload availability flag)
- Same-slot attestations (`block_slot == attestation.data.slot`): `data.index` must be 0
- `LatestMessage` now tracks `slot` instead of `epoch`, plus `payload_present`

## Things to Check in Lodestar
- [ ] ForkChoiceNode with payload_status tracking
- [ ] Two-phase state selection in on_block (FULL parent → execution_payload_states)
- [ ] on_execution_payload handler
- [ ] PTC voting and is_payload_timely threshold
- [ ] get_node_children tree structure (PENDING → EMPTY/FULL → PENDING)
- [ ] get_weight returning 0 for current-slot non-PENDING nodes
- [ ] should_extend_payload logic
- [ ] is_supporting_vote for payload-aware vote counting
- [ ] Timing BPS values for Gloas
- [ ] Attestation data.index validation (0 or 1)

---
*Next: builder.md, then p2p-interface.md*
