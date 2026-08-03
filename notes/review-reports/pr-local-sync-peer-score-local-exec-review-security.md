# Security Review: sync peer score local execution errors

Reviewer: review-security
Reviewed commit: aa562e67935b01d71a593c3dd770f16265927d01

Files reviewed:
- `packages/beacon-node/src/sync/range/batch.ts`
- `packages/beacon-node/test/unit/sync/range/batch.test.ts`

## Findings

No security vulnerabilities identified in the reviewed diff.

The change narrowly reclassifies `BlockErrorCode.BEACON_CHAIN_ERROR` wrapping
`PayloadErrorCode.EXECUTION_ENGINE_ERROR` as a local execution-engine failure in
range sync batch processing and validation error handling. The helper preserves
peer-attributable behavior for wrapped payload invalidity, envelope verification
failures, and signature failures because only the execution-engine error payload
code is exempted from `failedProcessingAttempts`.

This matches the intended peer-scoring behavior: local EL unavailability or EL
errors now exhaust `MAX_EXECUTION_ENGINE_ERROR_ATTEMPTS` and avoid
`SyncChainMaxProcessingAttempts` peer downscoring. I did not find an introduced
DoS, eclipsing, peer-manipulation, or validation-bypass risk in the changed
files.
