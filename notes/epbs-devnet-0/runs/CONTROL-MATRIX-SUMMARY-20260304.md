# EPBS devnet-0 control matrix (2026-03-04)

## Goal
Determine whether remaining acceptance-criteria failure (no finalization / unstable peering in mixed Teku+Lodestar run) is caused by the Lodestar PTC fix or by broader client/topology behavior.

## Runs compared

### 1) Mixed Teku+Lodestar (fixed image)
- Run dir: `teku-interop-fixed-extended/`
- Topology: 2x Teku + 2x Lodestar
- Key observations:
  - ✅ PTC error gone in Lodestar (`Payload Timeliness Committee is not available for slot` = 0)
  - ✅ Lodestar VC logs show no missed/warn/error
  - ❌ Finalized epoch stayed 0
  - ❌ Teku showed repeated `No peers for message topics` and failed attestation/aggregate production

### 2) Teku-only control
- Run dir: `teku-only-control-20260304T153936Z/`
- Topology: 4x Teku + 4x Geth
- Key observations:
  - Chain progressed to slot 135
  - ❌ Justified stayed 0, finalized stayed 0
  - Peer count remained 2-3 (not complete disconnect)
  - `No peers for message topics` not present in this capture, but attestation/aggregate production failures remained

### 3) Lodestar-only control (PTC-fix image)
- Run dir: `lodestar-only-control-20260304T160850Z/`
- Topology: 4x Lodestar + 4x Geth
- Key observations:
  - Chain progressed to slot 130
  - ✅ Justified reached 3
  - ✅ Finalized reached 2
  - ✅ Peers stable at 3
  - ✅ No PTC errors, no CL warn/error, no VC misses

## Conclusion
The previous-epoch PTC fix is correct and liveness-safe in Lodestar topology.
The remaining finalization failure in mixed Teku+Lodestar runs is not attributable to this PTC patch; control evidence points to broader Teku/mixed-topology behavior in this devnet setup.

## Implication for PR scope
Open PR for the PTC fix with:
- root cause + patch explanation
- unit tests
- mixed-run evidence showing original error is resolved
- explicit note that remaining finalization/peering instability is a separate interop issue (outside this patch scope), supported by control matrix above.
