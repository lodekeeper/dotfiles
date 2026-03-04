# Minimal preset validation — PTC epoch-boundary safety

- Enclave: `epbs-minimal-ptc`
- Config: `notes/epbs-devnet-0/kurtosis-configs/epbs-devnet-0-minimal-lodestar-2node.yaml`
- Preset: `minimal`
- Topology: 2x Lodestar + 2x Geth
- Fork params: `gloas_fork_epoch: 1`, `seconds_per_slot: 6`

## Epoch-boundary progression evidence
From `monitor.log` (node `cl-1`):
- `17:37:10Z slot=10` (crossed first epoch boundary)
- `17:39:40Z slot=35 justified=3 finalized=2`
- `17:43:41Z slot=75 justified=8 finalized=7`

This run crossed multiple epoch boundaries and finalized.

## Regression check
Searched logs for:
`Payload Timeliness Committee is not available for slot`

Results:
- `cl-1-lodestar-geth.log`: **0**
- `cl-2-lodestar-geth.log`: **0**
- `vc-1-geth-lodestar.log`: **0**
- `vc-2-geth-lodestar.log`: **0**

No PTC lookup regression observed in minimal preset.
