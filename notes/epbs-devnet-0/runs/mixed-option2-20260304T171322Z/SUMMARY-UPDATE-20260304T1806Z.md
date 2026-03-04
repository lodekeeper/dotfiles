# Mixed Teku+Lodestar interop update (Option 2)

Run: `epbs-teku-lodestar-option2`  
Evidence dir: `notes/epbs-devnet-0/runs/mixed-option2-20260304T171322Z`

## 1) Long-run timeline confirms persistent liveness stall
From `timeline.jsonl` (54 samples, extended through slot >200):
- All nodes advanced to slot ~208
- All nodes remained at `justified=1`, `finalized=0`
- Peer counts stayed non-zero during timeline capture (typically 3)

=> Finalization did **not** recover despite long runtime.

## 2) PTC regression remains fixed (not reintroduced)
Lodestar CL logs:
- `cl-3-lodestar-geth.log`: `Payload Timeliness Committee is not available for slot` = 0
- `cl-4-lodestar-geth.log`: `Payload Timeliness Committee is not available for slot` = 0

Also 0 for prior known errors:
- `Error processing block from unknown parent sync` = 0
- `BLOCK_ERROR_PRESTATE_MISSING` = 0

## 3) Teku-side instability evidence in same run
`cl-1-teku-geth.log`:
- `No peers for message topics` = 786
- `Failed to publish beacon_block` = 42
- `Failed to publish payload_attestation_message` = 139
- Includes state transition failures with:
  - `BlockProcessingException: Bid is not for the right parent block`

`cl-2-teku-geth.log`:
- `No peers for message topics` = 0
- Also contains `Bid is not for the right parent block` (at least once)

## 4) Mitigation experiment #1 (in-place restart of cl-1 Teku)
Action:
- `kurtosis service stop epbs-teku-lodestar-option2 cl-1-teku-geth`
- `kurtosis service start epbs-teku-lodestar-option2 cl-1-teku-geth`

Post-restart monitor (`restart-mitigation-monitor.log`):
- Other nodes kept progressing in slot, but still `justified=1/finalized=0`
- `cl-1` HTTP endpoint repeatedly failed for head/finality (returned null/500)
- Later logs show repeated exceptions while processing gossip messages, including:
  - `Unable to produce state for block at slot 196`
  - `Bid is not for the right parent block`

=> Restart did **not** restore finalization; issue persists and appears Teku-side in this mixed setup.
