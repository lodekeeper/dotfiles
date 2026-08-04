# Review Findings — review-bugs — 9505

Reviewer: review-bugs
Reviewed commit: 350d13c7c384b379eab3934d0de7b8cd494f5a4d
Generated at: 2026-08-04 09:46 UTC

Reviewer: review-bugs
Reviewed commit: 350d13c7c384b379eab3934d0de7b8cd494f5a4d

## Findings

### 1. Heze nodes never subscribe to the required inclusion_list gossip topic

File: packages/beacon-node/src/network/gossip/topic.ts:292

`getCoreTopicsAtFork()` adds the Gloas-only topics for every post-Gloas fork, but it never adds Heze's new `inclusion_list` global topic. With Heze scheduled, `getAllowedTopics()` will not include `/eth2/<heze-digest>/inclusion_list/ssz_snappy`, so the node will neither subscribe to nor accept signed inclusion lists from peers. That breaks Heze/FOCIL operation before block production can build useful `inclusion_list_bits`.

The Heze p2p spec adds `inclusion_list` with message type `SignedInclusionList`; this needs a Heze-only topic entry, SSZ type, and max size using `MAX_SIGNED_INCLUSION_LIST_SIZE`.

### 2. Heze payload attributes are populated but not sent to the execution engine

File: packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts:939

`preparePayloadAttributes()` sets `inclusionListTransactions` for Heze, but the same object is passed as execution `PayloadAttributes` to `notifyForkchoiceUpdate()` at line 764. The execution payload-attributes RPC path only serializes the pre-Heze fields, so this new field is dropped before `engine_forkchoiceUpdated`. A Heze execution client will receive a Gloas-shaped payload attributes object instead of the required Heze object with `inclusionListTransactions`.

Even while the IL pool is not wired and the value is `[]`, the field must make it onto the RPC payload for Heze block production to interoperate with a Heze EL.

## Checks run

- `pnpm --filter @lodestar/types check-types`
- `pnpm --filter @lodestar/state-transition check-types`
- `pnpm --filter @lodestar/beacon-node check-types`
- `SPEC_FILTER_FORK=heze pnpm vitest run --project spec-minimal test/spec/presets/ssz_static.test.ts`
- `SPEC_FILTER_FORK=heze pnpm vitest run --project spec-minimal test/spec/presets/fork.test.ts test/spec/presets/operations.test.ts test/spec/presets/transition.test.ts`
- `SPEC_FILTER_FORK=heze pnpm vitest run --project spec-minimal test/spec/presets/fast_confirmation.test.ts test/spec/presets/finality.test.ts test/spec/presets/sanity.test.ts test/spec/presets/epoch_processing.test.ts test/spec/presets/rewards.test.ts`
- `SPEC_FILTER_FORK=heze pnpm vitest run --project spec-minimal test/spec/presets/fork_choice.test.ts`
- `pnpm vitest run --project e2e packages/config/test/e2e/ensure-config-is-synced.test.ts`
- `pnpm vitest run --project unit packages/state-transition/test/unit/upgradeState.test.ts packages/beacon-node/test/unit/network/gossip/topic.test.ts packages/beacon-node/test/unit/network/fork.test.ts packages/beacon-node/test/unit/chain/lightclient/upgradeLightClientHeader.test.ts packages/beacon-node/test/unit/chain/blocks/blockInput.test.ts`
- `pnpm vitest run --project unit packages/params/test/unit/forkName.test.ts`
