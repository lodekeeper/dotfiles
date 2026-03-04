# Mitigation #3 timeline correlation

## Timeline inflection points (from `monitor.log`)
- First major spread (`maxSlot-minSlot >= 10`):
  - `2026-03-04T18:44:12Z` -> slots `[95, 93, 106, 106]` for `[cl1_teku, cl2_teku, cl3_lodestar, cl4_lodestar]`
- First point where `cl-2-teku` reached slot 95:
  - `2026-03-04T18:44:42Z` (`slot=95`, `peers=3`)
- First point where `cl-2-teku` peers degraded to <=1:
  - `2026-03-04T18:46:12Z` (`slot=95`, `peers=1`)
- End snapshot:
  - `2026-03-04T18:51:15Z`
  - `cl-1-teku`: slot 173, justified 2, finalized 0, peers 2
  - `cl-2-teku`: slot 95, justified 0, finalized 0, peers 0
  - `cl-3-lodestar`: slot 176, justified 2, finalized 0, peers 2
  - `cl-4-lodestar`: slot 176, justified 2, finalized 0, peers 2

## Correlated log markers
- First Teku no-peer publish failures:
  - `cl-1-teku`: `2026-03-04 18:34:03` (slot 4, attestation publish)
  - `cl-2-teku`: `2026-03-04 18:39:56` (slot 63, payload attestation publish)
- Teku state transition/import errors:
  - `cl-2-teku`: `2026-03-04 18:44:54` (block 108)
  - `cl-1-teku`: `2026-03-04 18:45:24` (block 100)
  - both include `Bid is not for the right parent block`
- Lodestar side-effect signal:
  - `cl-4-lodestar`: first `BLOCK_ERROR_PRESTATE_MISSING` at `18:40:42` on slot 71 root, then repeated.

## Reading
Supernode topology did not remove Teku publication failures. The collapse around `cl-2-teku` (slot freeze + peers->0) temporally aligns with expanding slot spread and subsequent stalled finalization across the mixed network.
