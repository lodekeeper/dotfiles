# Mitigation experiment #2 — topology variant (1×Teku + 3×Lodestar)

- Enclave: `epbs-mitigation2-teku1-ls3`
- Config: `notes/epbs-devnet-0/kurtosis-configs/epbs-devnet-0-teku1-lodestar3-mitigation2.yaml`
- Network params: `gloas_fork_epoch: 1`, `seconds_per_slot: 6`
- Purpose: test whether reducing Teku-side surface (from 2 Teku nodes to 1) restores finalization in mixed-client topology.

## Finality trajectory (monitor evidence)
From `monitor.log`:
- Early: all nodes progressed with peers=3 and `justified=0/finalized=0`
- Around slot ~99: all nodes reached `justified=2/finalized=0`
- Around slot ~130+: Lodestar nodes finalized:
  - `39108/39115/39122` reached `justified=3/finalized=2`
- Teku node (`39101`) lagged and stayed behind (`justified=2/finalized=0`) while Lodestar nodes continued advancing.

## Error/regression checks
- Lodestar CL logs (`cl-2/3/4-lodestar-geth.log`):
  - `Payload Timeliness Committee is not available for slot` = 0
  - `Error processing block from unknown parent sync` = 0
  - `BLOCK_ERROR_PRESTATE_MISSING` = 0
- Teku CL log (`cl-1-teku-geth.log`):
  - `No peers for message topics` = 360
  - `Bid is not for the right parent block` = 1
- Lodestar VC logs (`vc-2/3/4`): no `miss` markers; attestations and block publications present.

## Follow-up snapshot (2026-03-04T18:26Z)
Current heads/finality:
- Teku (`39101`): slot 167, `justified=2/finalized=0`
- Lodestar (`39108/39115/39122`): slot 171, `justified=4/finalized=3`

Teku continues to lag while Lodestar nodes finalize further.

## Follow-up snapshot (2026-03-04T18:28Z)
Current heads/finality:
- Teku (`39101`): slot 177, `justified=2/finalized=0`
- Lodestar (`39108/39115/39122`): slot 191, `justified=4/finalized=3`

Pattern persists over additional slots: Lodestar majority finalizes, Teku lags without reaching finalization.

## Interpretation
This topology variant indicates the PTC fix remains healthy and mixed-client liveness can finalize on the Lodestar-majority side even while Teku shows publication instability. This strengthens the hypothesis that the remaining 2×Teku+2×Lodestar stall is Teku-side/interoperability behavior rather than a Lodestar PTC regression.
