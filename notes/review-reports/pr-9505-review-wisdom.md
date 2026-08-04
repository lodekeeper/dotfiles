# Reviewer: review-wisdom
# PR: #9505
# Reviewed commit: 350d13c7c384b379eab3934d0de7b8cd494f5a4d
# Result: Findings

## Findings

### Medium: `upgrade_to_heze` is wired but the matching fork spec test is still globally skipped

The PR adds Heze fork-test dispatch in `packages/beacon-node/test/spec/presets/fork.test.ts:48`, so the spec runner can call `upgradeStateToHeze`. However, `packages/beacon-node/test/spec/utils/specTestIterator.ts:101-104` still globally skips any test whose name ends in `/heze_fork`. That skip is not scoped to light-client tests, despite the adjacent TODO saying it is for Gloas light-client coverage. As a result, the most direct consensus-spec coverage for the new `packages/state-transition/src/slot/upgradeStateToHeze.ts:9` implementation remains disabled.

The implementation appears to match the local `specrefs/functions.yml:13595-13667` mapping, including rebuilding `latestExecutionPayloadBid` with default zero `inclusionListBits`, but that is exactly the path that should be protected by the generated fork tests. I would either unskip the Heze fork state-upgrade suite or add a focused unit/spec test that checks all copied fields and the zeroed `inclusionListBits` initialization.

## Risk Notes

- I did not find a merge-blocking issue in the Heze SSZ boilerplate. `ExecutionPayloadBid`, `BeaconState`, `BeaconBlockBody`, `PayloadAttributes`, and the Heze type exports line up with the specrefs snippets I checked.
- The remaining specrefs exceptions look intentional for unimplemented FOCIL behavior: inclusion-list store/fork-choice functions stay in `.ethspecify.yml`, while implemented Heze configs, presets, constants, and containers are now mapped.
- The zeroed FOCIL placeholders in block production are consensus-incomplete if `HEZE_FORK_EPOCH` is scheduled. `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts:359-361` always emits zero `inclusionListBits`, and `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts:937-939` always sends empty `inclusionListTransactions`. Given this PR is boilerplate, Heze is disabled by default, and the FOCIL suites are explicitly skipped until the inclusion-list pool/fork-choice work lands, I would not block this boilerplate PR solely on those placeholders. I would block any PR that enables Heze on a network before those TODOs are replaced.

## Verification

- Ran `pnpm vitest run packages/state-transition/test/unit/upgradeState.test.ts packages/beacon-node/test/unit/network/gossip/topic.test.ts packages/types/test/unit/gloas/eip7688.test.ts`.
- Result: 3 files passed, 60 tests passed, type errors: none.
- Environment warning: repo wants Node `^24.13.0`; this run used Node `v22.19.0`.
