# Teku-only control run (`epbs-teku-only-control`)

- Config: `notes/epbs-devnet-0/kurtosis-configs/epbs-devnet-0-teku-only-control.yaml`
- Topology: 4x Teku + 4x Geth
- Fork params: `gloas_fork_epoch: 1`, `seconds_per_slot: 12`
- Monitoring endpoint: `cl-1` (`http://127.0.0.1:37101`)

## Results
- Monitoring window: 27 samples (15:39:36Z → 16:06:04Z)
- Max observed slot: **135**
- Justified epoch: **stayed 0**
- Finalized epoch: **stayed 0**
- Peer count: fluctuated **2-3** (never full outage)

## Log signals
- `No peers for message topics`: **0** occurrences across all 4 Teku CL logs in this capture
- Repeated `Failed to produce attestation` / `Failed to produce aggregate` errors still present

## Takeaway
Finalization failure in this environment reproduces even without Lodestar nodes, so the remaining acceptance-criteria blocker (justification/finalization) is **not caused by the Lodestar PTC fix**.
