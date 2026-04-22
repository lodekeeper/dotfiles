# Withdrawals Mismatch — Runtime Reproducer Plan

Last updated: 2026-04-22 00:42 UTC

## Best current candidate surface
`packages/beacon-node/test/e2e/chain/proposerBoostReorg.test.ts`-style dev-node e2e with:
- `getDevBeaconNode()`
- `getAndInitDevValidators()`
- custom fork-choice constructor (`TimelinessForkChoice` or `ReorgedForkChoice`)
- built-in mock EL (`executionEngine.mode = "mock"`)

Why this surface:
- already exercises real validator-driven block production
- already models proposer boost / head evolution
- avoids external EL process setup
- should let us capture the exact runtime bundle with spies instead of production-code edits

## Runtime bundle to capture
For the slot where the relevant block is produced, capture/assert:
- canonical head root
- proposer head root
- proposer boost root
- `shouldExtendPayload()` input root
- `shouldExtendPayload()` output boolean
- selected `parentBlockHash`
- withdrawals source (fresh expected vs `payloadExpectedWithdrawals`)
- FCU payload sent to EL (`headBlockHash`, `safeBlockHash`, `finalizedBlockHash`, payload attrs)

## Likely instrumentation points
- `bn.chain.getProposerHead(slot)`
- `bn.chain.forkChoice.getProposerBoostRoot()`
- `bn.chain.forkChoice.shouldExtendPayload(blockRoot)`
- `bn.chain.executionEngine.notifyForkchoiceUpdate(...)`
- payload-attributes event from `bn.chain.emitter`

## Minimal harness shape
1. Start a dev beacon node with proposer-boost/reorg-capable fork choice.
2. Start local validators via `getAndInitDevValidators()`.
3. Force a weak-head / proposer-head divergence (similar to `proposerBoostReorg.test.ts`).
4. Spy on the instrumentation points above.
5. Wait for the target slot/block.
6. Assert the runtime bundle is self-consistent.

## First acceptance criterion
In the target runtime slot:
- the root passed into `shouldExtendPayload()` matches the proposer head root actually chosen by block production, and
- the `notifyForkchoiceUpdate(...)` head/parent payload data is consistent with that branch decision.

## Optional stronger acceptance criterion
If the runtime harness reaches Gloas payload production cleanly, additionally prove that:
- `shouldExtendPayload() === false` implies the producer path emits stale `payloadExpectedWithdrawals` into FCU payload attrs in the same runtime flow.

## Open question
Whether `TimelinessForkChoice` alone is enough, or whether `ReorgedForkChoice` gives a cleaner deterministic divergence for the exact mismatch shape.
