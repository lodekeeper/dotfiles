# Altair Light Client — Spec Notes

## Overview
The Altair light client protocol allows constrained environments (phones, cross-chain bridges) to track the beacon chain using sync committees. It consists of four spec documents:

1. **sync-protocol.md** — Core types, validation, and state machine
2. **full-node.md** — How full nodes derive light client data from blocks/states
3. **light-client.md** — How light clients consume data to stay synced
4. **p2p-interface.md** — Gossip topics and ReqResp messages for distribution

## Key Types

### Containers
- **`LightClientBootstrap`**: Initial trusted state (header + current sync committee + branch proof)
- **`LightClientUpdate`**: Full update with attested header, next sync committee, finalized header, and sync aggregate signature
- **`LightClientFinalityUpdate`**: Subset of Update (no next sync committee) — for tracking finalized head
- **`LightClientOptimisticUpdate`**: Minimal update — just attested header + sync aggregate
- **`LightClientStore`**: Client-side state tracking finalized/optimistic headers and known sync committees

### Constants
| Name | Value | Description |
|------|-------|-------------|
| `FINALIZED_ROOT_GINDEX` | 105 | Generalized index of `finalized_checkpoint.root` in BeaconState |
| `CURRENT_SYNC_COMMITTEE_GINDEX` | 54 | Generalized index of `current_sync_committee` |
| `NEXT_SYNC_COMMITTEE_GINDEX` | 55 | Generalized index of `next_sync_committee` |
| `MIN_SYNC_COMMITTEE_PARTICIPANTS` | 1 | Minimum signers for a valid update |
| `UPDATE_TIMEOUT` | 8192 slots (~27h) | Force-update timeout when sync appears stuck |

## Core Logic

### `is_better_update` — Ranking Updates
Priority order:
1. **Supermajority (>2/3)** participation — always beats non-supermajority
2. Without supermajority: **highest participation** wins
3. **Relevant sync committee** — signed in same period as attested header
4. **Finality indication** — updates with finality branch beat those without
5. **Sync committee finality** — finalized header in same period as attested
6. Tiebreaker 1: Higher participation beyond supermajority
7. Tiebreaker 2: Older attested header (more stable, fewer changes)
8. Tiebreaker 3: Earlier signature slot

### `validate_light_client_update` — Validation Checks
1. Sufficient participants (≥ MIN_SYNC_COMMITTEE_PARTICIPANTS)
2. Valid light client header
3. Slot ordering: `current_slot >= signature_slot > attested_slot >= finalized_slot`
4. Period constraint: signature must be in current or next period (if next SC known)
5. Relevance: attested slot must advance past finalized, or provide unknown next SC
6. Finality branch proof (if present)
7. Next sync committee branch proof (if present)
8. BLS aggregate signature verification using participating pubkeys

### `process_light_client_update` — State Machine
1. Validate the update
2. Track `best_valid_update` for force-update fallback
3. Track max active participants for safety threshold
4. Update optimistic header if participation > safety threshold
5. Update finalized header if supermajority AND (advances finalized slot OR provides next SC)
6. Apply via `apply_light_client_update` (rotates sync committees on period boundary)

### `process_light_client_store_force_update` — Stuck Recovery
If no finality for UPDATE_TIMEOUT slots, apply `best_valid_update` treating `attested_header` as `finalized_header`.

## Sync Committee Period Transitions
Key insight: sync committee rotation happens when `update_finalized_period == store_period + 1`:
- `current_sync_committee` ← `next_sync_committee`
- `next_sync_committee` ← from the update
- `previous_max_active_participants` ← `current_max_active_participants`

## Safety Threshold
`get_safety_threshold = max(previous_max, current_max) / 2`
Optimistic header only updates when participation exceeds this threshold — prevents low-participation header takeover.

## Full Node Responsibilities
- Derive `LightClientBootstrap` for all finalized epoch boundary blocks
- Derive best `LightClientUpdate` per sync committee period
- Serve `LightClientFinalityUpdate` with highest attested slot
- Serve `LightClientOptimisticUpdate` with highest attested slot
- Push updates via SSE when headers change

## P2P Interface
### Gossip Topics
- `light_client_finality_update` — latest finality update
- `light_client_optimistic_update` — latest optimistic update

### ReqResp Messages
- `GetLightClientBootstrap` — bootstrap for a given block root
- `LightClientUpdatesByRange` — updates for sync committee periods (max 128 per request)
- `GetLightClientFinalityUpdate` — latest finality update
- `GetLightClientOptimisticUpdate` — latest optimistic update

## Lodestar Implementation

### Package: `packages/light-client/`
Client-side implementation for consuming light client data.

| Spec Function | Lodestar File | Notes |
|---------------|---------------|-------|
| `is_better_update` | `spec/isBetterUpdate.ts` | Uses `LightClientUpdateSummary` wrapper for efficiency |
| `validate_light_client_update` | `spec/validateLightClientUpdate.ts` | Includes Electra depth changes |
| `process_light_client_update` | `spec/processLightClientUpdate.ts` | See deviations below |
| `LightClientStore` | `spec/store.ts` | Different structure from spec |
| `initialize_light_client_store` | `spec/validateLightClientBootstrap.ts` | Bootstrap validation |
| Main loop | `index.ts` (Lightclient class) | Full sync loop implementation |

### Package: `packages/beacon-node/src/chain/lightClient/`
Server-side: deriving and serving light client data.

| Spec Function | Lodestar File | Notes |
|---------------|---------------|-------|
| `create_light_client_*` | `chain/lightClient/index.ts` | `LightClientServer` class |
| Merkle proofs | `chain/lightClient/proofs.ts` | State tree proofs |
| Gossip validation | `chain/validation/lightClient*.ts` | Forwarding rules |
| ReqResp handlers | `network/reqresp/handlers/lightClient*.ts` | P2P serving |
| DB persistence | `db/repositories/lightclient*.ts` | Best updates, SC witnesses |

### Notable Design Decisions

#### 1. Store Structure Deviation
**Spec**: `current_sync_committee` + `next_sync_committee` as direct fields
**Lodestar**: `syncCommittees: Map<SyncPeriod, SyncCommitteeFast>` (max 2 entries)

This is more flexible — period-indexed lookup rather than current/next distinction. The rotation logic is handled lazily in `getSyncCommitteeAtPeriod()`.

#### 2. Best Valid Update Per Period
**Spec**: Single `best_valid_update: Optional[LightClientUpdate]`
**Lodestar**: `bestValidUpdates: Map<SyncPeriod, LightClientUpdateWithSummary>` (per period)

This allows tracking best updates for multiple periods simultaneously, which is needed when syncing across period boundaries.

#### 3. Lazy Sync Committee Rotation
**Spec**: `apply_light_client_update()` rotates committees immediately
**Lodestar**: Defers to `getSyncCommitteeAtPeriod()` — extracts next SC from `bestValidUpdate` on demand

This also handles force-update logic (spec's `process_light_client_store_force_update`) via `opts.allowForcedUpdates`.

#### 4. bestValidUpdate Only for Sync Committee Updates
In `processLightClientUpdate.ts`, Lodestar only tracks `bestValidUpdate` when `isSyncCommitteeUpdate(update)` is true. The spec tracks it for all updates. This is correct because `bestValidUpdate` is only used for sync committee advancement — non-SC updates can't provide the next sync committee anyway.

#### 5. Electra Support
Electra changes merkle branch depths (BeaconState gets new fields, shifting gindexes):
- `FINALIZED_ROOT_DEPTH_ELECTRA` vs `FINALIZED_ROOT_DEPTH`
- `NEXT_SYNC_COMMITTEE_DEPTH_ELECTRA` vs `NEXT_SYNC_COMMITTEE_DEPTH`

Both validation and creation code handle this fork-aware branching.

#### 6. Gloas TODO
`blockToLightClientHeader` has a `TODO GLOAS` comment — light client spec for Gloas (EPBS) is pending. The function is typed `ForkPreGloas` to make this explicit.

## Altair Fork Choice
Minimal changes — adds timing helpers for sync committee messages:
- `get_sync_message_due_ms()` — when sync messages are due in the slot
- `get_contribution_due_ms()` — when contributions are due

These are used for gossip validation timing in the P2P layer.

## Cross-References
- Sync committees defined in `altair/beacon-chain.md` (see `altair-beacon-chain.md` notes)
- Phase0 fork choice inherited (see `phase0-fork-choice.md` notes)
- Electra changes branch depths (see future `electra-beacon-chain.md` notes)
