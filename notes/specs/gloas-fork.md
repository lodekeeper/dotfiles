# Gloas/EPBS — Fork Logic Notes

**Spec:** `consensus-specs/specs/gloas/fork.md`  
**Status:** Read ✅  
**Date:** 2026-02-16

## Overview

Short spec covering the state upgrade from Fulu → Gloas at `GLOAS_FORK_EPOCH`.

## Key State Changes in `upgrade_to_gloas`

### Removed
- `latest_execution_payload_header` — no longer needed; ePBS separates beacon block from payload

### Added (new fields)
| Field | Initial Value | Purpose |
|-------|--------------|---------|
| `latest_execution_payload_bid` | `ExecutionPayloadBid(block_hash=pre.latest_execution_payload_header.block_hash)` | Replaces payload header — stores the winning bid |
| `builders` | `[]` | Builder registry (like validators but for ePBS builders) |
| `next_withdrawal_builder_index` | `0` | Builder withdrawal sweep pointer |
| `execution_payload_availability` | `[0b1] * SLOTS_PER_HISTORICAL_ROOT` | Bitfield tracking which slots had payloads (initialized all-present) |
| `builder_pending_payments` | `[BuilderPendingPayment()] * (2 * SLOTS_PER_EPOCH)` | Ring buffer for deferred builder payments |
| `builder_pending_withdrawals` | `[]` | Builder withdrawal queue |
| `latest_block_hash` | `pre.latest_execution_payload_header.block_hash` | Extracted from removed header — used by fork-choice and proposer |
| `payload_expected_withdrawals` | `[]` | Expected withdrawals that the payload must include |

### `onboard_builders_from_pending_deposits`

At fork time, processes `pending_deposits` to bootstrap the builder registry:
- Existing validator deposits → stay in pending queue
- Builder-credential deposits or existing builder deposits → `apply_deposit_for_builder()`
- New valid validator deposits → stay in pending queue, pubkey tracked to prevent accidental builder creation
- Invalid signature deposits → dropped (would fail in `apply_pending_deposit` anyway)

**Interesting edge case handling:** The function re-computes `builder_pubkeys` each iteration because `apply_deposit_for_builder` can mutate the state by adding new builders. This prevents a deposit from accidentally creating a duplicate builder if a previous deposit in the same batch already created one.

## Observations

1. **`execution_payload_availability` initialized to all-1s** — optimistic assumption that all historical slots had payloads. This makes sense since pre-ePBS all blocks contained execution payloads.

2. **`builder_pending_payments` ring buffer** — sized at `2 * SLOTS_PER_EPOCH` suggesting builder payments are settled within ~2 epochs.

3. **Clean separation** — the fork logic clearly shows the ePBS design philosophy: the beacon state no longer holds the full payload header, just the bid and the block hash.

---
*Completes Gloas/EPBS fork logic review*
