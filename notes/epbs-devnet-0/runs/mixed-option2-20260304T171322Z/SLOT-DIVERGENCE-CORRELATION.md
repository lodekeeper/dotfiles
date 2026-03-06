# Slot-by-slot divergence + correlation (mixed 2×Teku + 2×Lodestar)

Run context:
- Enclave: `epbs-teku-lodestar-option2`
- Timeline source: `timeline.jsonl` (54 samples)
- Logs: `cl-1-teku-geth.log`, `cl-2-teku-geth.log`, `cl-3-lodestar-geth.log`, `cl-4-lodestar-geth.log`

## Timeline checkpoints
- `2026-03-04T17:13:22Z` (i=0): all nodes at slot ~3, `justified=0/finalized=0`, peers=3
- `2026-03-04T17:29:10Z`: first notable slot spread (`max-min >= 5`)
  - cl1_teku=82, cl2_teku=77, cl3_lodestar=80, cl4_lodestar=80
- `2026-03-04T17:32:39Z`: first/only justification increase (`justified=1` for all nodes)
  - slots near 97–99
- Extended samples through slot >200: all nodes remained `justified=1/finalized=0`

## First liveness-break correlation markers (logs)
- `cl-1-teku-geth` starts showing topic-publish failures immediately:
  - first seen at `2026-03-04 17:13:02Z` on slot 1:
    - `Failed to publish attestation(s)... No peers for message topics`
- Teku state transition/import errors appear around the first slot-spread widening:
  - `cl-1-teku-geth` at `2026-03-04 17:28:12Z`:
    - `State transition error while importing block 76`
    - `Bid is not for the right parent block`
  - `cl-2-teku-geth` at `2026-03-04 17:28:33Z`:
    - `State transition error while importing block 79`
    - `Bid is not for the right parent block`

## Aggregate signal counts (same run)
- `cl-1-teku-geth`:
  - `No peers for message topics`: 786
  - `Failed to publish attestation(s)`: 142
  - `Failed to publish payload_attestation_message(s)`: 139
  - `Failed to publish beacon_block`: 42
- `cl-2-teku-geth`:
  - `Bid is not for the right parent block`: 1
  - `State transition error while importing block`: 1
- `cl-3/4-lodestar-geth`:
  - `Payload Timeliness Committee is not available for slot`: 0
  - `Error processing block from unknown parent sync`: 0
  - `BLOCK_ERROR_PRESTATE_MISSING`: 0

## Interpretation
The first persistent instability markers are Teku-side publication/import errors, beginning before and around the first major slot divergence window. Lodestar logs remain clean of the PTC regression and related sync/prestate errors. This supports the current hypothesis: remaining mixed-run liveness failure is interop/Teku-side, not a reintroduced Lodestar PTC-cache bug.
