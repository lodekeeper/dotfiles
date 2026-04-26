# Glamsterdam Genesis Envelope Bug — Tracker

Last updated: 2026-04-25 23:43 UTC

## Goal
Identify why Lodestar enqueues impossible execution-payload-envelope sync for the genesis root, patch it, reproduce before/after locally, and open a PR against unstable.

## Phase Plan
- [x] Reproduce mixed-client issue locally
- [x] Narrow failing runtime symptom and likely enqueue path
- [x] Patch candidate + local before/after verification
- [x] Review / quality gate
- [x] Unstable-based PR

## Completed Work
- Mixed-client repro `glamsterdam-mixed-nethermind` shows healthy chain but repeated `pendingPayloads` loop for genesis root on `cl-3-lodestar-nethermind`
- Identified likely enqueue site: `network/processor/index.ts` calling `searchUnknownEnvelope()` too eagerly for attestation/payload-attestation/data-column-sidecar gossip when `!forkChoice.hasPayloadHexUnsafe(root)`

## Next Immediate Steps
1. Finish reviewer pass and incorporate any feedback
2. Commit/push the unstable worktree and open the PR
3. Shut down the verification enclave once the PR is open

## Interop/Validation Target
- Mixed-client config from Nico (2 Prysm + 2 Lodestar over Nethermind)
- No repeated `downloadPayload()` loop for genesis root
- Chain still finalizes / peers stable / no missed slots

## Spec Compliance Artifacts
- N/A (network preprocessor guard / implementation bug, not spec pseudocode)

## Current Verification State
- Local mixed-client repro before fix: genesis root `0x68c61835...` entered `pendingPayloads` at slot 1 and looped forever on `execution_payload_envelopes_by_root`.
- Local mixed-client repro after fix: zero genesis-root `pendingPayloads` entries on either Lodestar node, `lodestar_sync_unknown_block_pending_payloads_size 0` on both, chain finalizing (slot ~80+, finalized epoch 8, peers=3 on all nodes, no missing slots on Lodestar through slot 85).
- Unit test added: `packages/beacon-node/test/unit/network/processor.executionPayloadEnvelopeEligibility.test.ts`

## Completed Work
- `e3baa6ff9b` — unstable-based fix: skip impossible payload envelope sync targets
- PR `#9281` — https://github.com/ChainSafe/lodestar/pull/9281
