# Mitigation experiment #3 — 2×Teku + 2×Lodestar with supernode topology

- Enclave: `epbs-mitigation3-supernode2x2`
- Config: `notes/epbs-devnet-0/kurtosis-configs/epbs-devnet-0-teku-lodestar-mitigation3-supernode.yaml`
- Goal: test whether denser peering topology (`supernode: true` on all CLs, Lodestar `--targetPeers=20`) reduces Teku `No peers for message topics` behavior and restores finalization in 2×2 mixed topology.

## Monitor observations (`monitor.log`)
- Run progressed from slot ~3 to >170.
- Divergence worsened over time:
  - `cl-2-teku` (port 40108) stalled at slot 95 with peers dropping to 0.
  - `cl-1-teku` continued to advance but stayed at `justified=2/finalized=0`.
  - Lodestar nodes advanced similarly but also remained at `justified=2/finalized=0` due to broken network state.

Latest snapshot (2026-03-04T18:58Z):
- `40101` (cl-1-teku): slot 238, `justified=2/finalized=0`, peers=2
- `40108` (cl-2-teku): slot 95, `justified=0/finalized=0`, peers=0
- `40115` (cl-3-lodestar): slot 242, `justified=2/finalized=0`, peers=2
- `40122` (cl-4-lodestar): slot 242, `justified=2/finalized=0`, peers=2

## Log correlation
- Teku publication issues persisted (updated counts):
  - `cl-1-teku`: `No peers for message topics` = 488
    - `Failed to publish attestation(s)` = 98
    - `Failed to publish beacon_block` = 20
    - `Failed to publish payload_attestation_message(s)` = 87
  - `cl-2-teku`: `No peers for message topics` = 527
    - `Failed to publish attestation(s)` = 140
    - `Failed to publish beacon_block` = 2
    - `Failed to publish payload_attestation_message(s)` = 150
- Teku bid/import errors still present:
  - both Teku nodes include `State transition error while importing block` and `Bid is not for the right parent block`.
- Lodestar PTC regression stayed absent:
  - `Payload Timeliness Committee is not available for slot` = 0 on both Lodestar CLs.

## New side-effect signal
- `cl-4-lodestar` showed repeated `BLOCK_ERROR_PRESTATE_MISSING` from UnknownBlockSync on slot 71 root during network partitioning behavior (`cl-2-teku` peers=0/stall).

## Conclusion
Mitigation #3 did **not** restore finalization. Supernode/denser peering did not eliminate Teku no-peer publication failures in mixed 2×2 and appears to coincide with deeper partition/stall behavior (one Teku node isolated at peers=0).
