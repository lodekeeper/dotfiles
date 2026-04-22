# PR draft — Gloas envelope stateRoot fix

## Proposed title
fix: compute Gloas envelope stateRoot from postState

## Proposed body
## Summary
Fix Gloas self-build execution payload envelopes to use the correct envelope-specific `stateRoot`.

Previously `getExecutionPayloadEnvelope()` could return an invalid `stateRoot` for self-build Gloas envelopes:
- first as `ZERO_HASH`
- then, in an intermediate attempt, as the full block post-state root

Neither matches what envelope import validates against.

This patch caches an envelope-specific state root derived from the real `postState` returned by block production and returns that root from `getExecutionPayloadEnvelope()`.

## Root cause
The validator API constructs self-build Gloas envelopes after block production, but the original cached produce result did not retain the correct envelope-level post-state root.

That led to a mismatch between:
- the envelope `stateRoot` published by the validator API, and
- the post-envelope root recomputed during import-time `processExecutionPayloadEnvelope(...)`

## Fix
- extend cached post-Gloas produce result with `envelopeStateRoot`
- derive `envelopeStateRoot` from the real `postState` returned by `computeNewStateRoot()`
- compute it by running `processExecutionPayloadEnvelope(postState, signedEnvelope, {verifySignature: false, verifyStateRoot: false})`
- return `envelopeStateRoot` from `getExecutionPayloadEnvelope()`

## Tests
Added:
- `packages/beacon-node/test/unit/api/impl/validator/getExecutionPayloadEnvelope.test.ts`
  - proves the validator API returns the cached Gloas envelope state root
- `packages/beacon-node/test/e2e/chain/gloasEnvelopeSelfBuildImport.test.ts`
  - deterministic acceptance path:
    1. produce Gloas block through validator API
    2. import block into forkchoice
    3. fetch self-build envelope
    4. import envelope through `chain.processExecutionPayload(..., {validSignature: true})`
    5. succeeds without the old state-transition mismatch

## Validation run
- `pnpm test:unit packages/beacon-node/test/unit/api/impl/validator/getExecutionPayloadEnvelope.test.ts`
- `pnpm exec vitest run packages/beacon-node/test/e2e/chain/gloasEnvelopeSelfBuildImport.test.ts`

## Notes
This PR intentionally carries only the minimal fix and focused coverage, not the broader root-cause investigation / runtime repro history.
