# Lodestar-only control run (`epbs-lodestar-only-control`)

- Config: `notes/epbs-devnet-0/kurtosis-configs/epbs-devnet-0-lodestar-only-control.yaml`
- Topology: 4x Lodestar + 4x Geth
- Lodestar image: `lodestar:epbs-devnet-0-teku-ptc-fix`
- Fork params: `gloas_fork_epoch: 1`, `seconds_per_slot: 12`
- Monitoring endpoint: `cl-1` (`http://127.0.0.1:37501`)

## Results
- Monitoring window: 27 samples (16:08:50Z → 16:34:58Z)
- Max observed slot: **130**
- Justified epoch progressed to **3**
- Finalized epoch progressed to **2**
- Peer count remained stable at **3**

## Log signals
- `Payload Timeliness Committee is not available for slot`: **0** on all Lodestar CLs
- `Error processing block from unknown parent sync`: **0**
- VC logs: no warn/error lines, no `miss` markers; steady attestations and block publications

## Takeaway
With the same Lodestar image containing the previous-epoch PTC fix, a Lodestar-only network reaches justification/finalization and maintains stable peering.
This indicates the PTC patch itself is healthy and does not regress chain liveness in homogeneous Lodestar topology.
