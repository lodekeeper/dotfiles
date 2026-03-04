# Root-cause hypothesis (current)

## Observed facts
1. PTC fix is healthy:
   - minimal preset finalizes and has 0 `Payload Timeliness Committee is not available for slot`
   - mixed run Lodestar logs show 0 PTC/unknown-parent/prestate errors
2. Mixed run still fails to finalize (`justified=1`, `finalized=0`) past slot 200.
3. Teku logs show repeated publication/pathology signals:
   - persistent `No peers for message topics` (at least on one Teku node)
   - state transition/import failures: `Bid is not for the right parent block`
4. Restarting the affected Teku node did not recover finalization.

## Current hypothesis
The remaining liveness failure in mixed Teku+Lodestar is **not** caused by Lodestar PTC cache logic. It is likely driven by Teku-side handling of gossip/publication and/or Gloas bid-parent validation under this topology, causing chain instability that prevents checkpoint progression beyond epoch 1.

## Minimal repro recipe
- Use mixed config (2x Teku + 2x Lodestar, Geth, `gloas_fork_epoch=1`, 6s slots)
- Run until slot >200
- Observe:
  - all nodes stuck at `current_justified=1`, `finalized=0`
  - Teku logs contain `No peers for message topics` and `Bid is not for the right parent block`
  - Lodestar logs contain no PTC regression errors
