# PR #19 Staged Implementation Review

Last updated: 2026-04-22 UTC

## Current staged state in `/home/openclaw/lodestar-notifier-prev-slot`

Staged files:
- `packages/beacon-node/src/node/notifier.ts`
- `packages/beacon-node/test/unit/node/notifier.test.ts`
- `packages/beacon-node/test/unit/api/impl/beacon/blocks/publishExecutionPayloadEnvelope.test.ts`
- `packages/beacon-node/test/unit/chain/blocks/importExecutionPayload.test.ts`
- `packages/beacon-node/test/unit/chain/produceBlock/getPayloadAttributesForSSE.test.ts`
- `packages/beacon-node/test/unit/chain/validation/executionPayloadEnvelope.test.ts`
- `packages/beacon-node/test/unit/network/processor/gossipHandlers.executionPayload.test.ts`

## What is good
- `notifier.ts` now models `exec-block` as the primary row and removes `prev-payload:`.
- It already resolves inherited execution anchors for non-FULL Gloas heads.
- It already has an explicit degraded fallback: `exec-block: unresolved(<hash>)`.
- `notifier.test.ts` was expanded with focused cases for pre-Gloas, FULL, PENDING, EMPTY, unresolved fallback, and "no prev-payload".

## What is still wrong / stale

### 1. Display wording is one revision behind
The current staged patch still emits:
- `payload: pending`
- `payload: empty`

But the final UX/display conclusion is:
- `payload-outcome: pending`
- `payload-outcome: empty`

So both `notifier.ts` and `notifier.test.ts` need that wording update.

### 2. Collateral staged files need review / likely cleanup
There are five additional staged test files outside `test/unit/node/notifier.test.ts`. Those may be branch residue or unrelated collateral from the Codex run. They are not part of the notifier-only implementation plan and should not ride along unless they are explicitly relevant.

## Cleanup plan
1. Keep reviewing only two intended files first:
   - `packages/beacon-node/src/node/notifier.ts`
   - `packages/beacon-node/test/unit/node/notifier.test.ts`
2. Update wording from `payload:` to `payload-outcome:` in both files.
3. Review the five collateral staged test files and drop them from the patch unless they are genuinely required by the notifier change.
4. Re-run notifier-focused validation after cleanup.

## Conclusion
The current staged implementation is a good semantic near-miss, not the final patch. The next concrete step is cleanup/alignment, not another design pass.
