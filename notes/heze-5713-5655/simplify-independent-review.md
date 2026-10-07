# Independent review: simplified EIP-8015 PR #10293

Verdict: APPROVE. No evidenced correctness problems and no compelling unnecessary remaining churn found in the reviewed changed files.

## Reviewed snapshot

- Original/current committed HEAD: `716dd88a5f62a15dc5a1c8504cdb7c50198b18c6`.
- Base origin/unstable: `fc618d94e9fc7db02c1d5ece53d897833ef7627b`.
- Reviewed actual tracked working diff against origin/unstable, including uncommitted simplification, not committed HEAD alone.
- SHA256 of `git diff origin/unstable`: `b15a631241aab1a954d0456cfcc902aa5f9b4102ab6c67cb37b11e6ae0f87f51`.
- Captured changed-file allowlist first; findings were restricted to that allowlist.
- Read repository AGENTS.md. No code edits, commits, pushes, or connector actions.

## Correctness and pattern checks

- Heze BeaconState removes exactly eth1Data, eth1DataVotes, eth1DepositIndex and depositRequestsStartIndex, preserving progressive field gaps 8,9,10,28. Body removes eth1Data and deposits with gaps 1,6. Surviving field order remains inherited from Gloas.
- Upgrade checks legacy deposit-index equality before mutation, drops only removed fields, and retains surviving fields and the existing EIP-7805 bid migration.
- Block processing, epoch vote reset, common-body production and logging guard removed-field access by fork. Pending-deposit bridge gating remains pre-Fulu only. Legacy helper casts retain existing public signatures and are reached from guarded runtime callers.
- Both state-view eth1Data accessors retain the nonoptional contract and throw after Heze, consistent with the existing latestExecutionPayloadHeader post-Gloas convention. No need for a widened optional interface or exported PreHeze aliases.
- Serialized bid extraction requires the actual post-Gloas fork and selects the Heze pointer after the 72-byte field and 4-byte deposits-pointer removal. The network processor supplies the fork; tests cover Gloas and Heze with a variable body operation present.
- Gloas operation ProgressiveListComposite types already carry operation limits, and Heze inherits them. The gossip topic deserializer translates SSZ exceptions to REJECT. Removing duplicated gossip operation checks is consistent with that architecture; no replacement runtime loop is needed.
- Public signed-block contents now describe actual Gloas/Heze blocks instead of Fulu blocks. API codecs use fork-selected SSZ types; pre-Gloas reconstruction and proposal types are narrowed to their existing supported fork scope. External block-signing input accepts actual Heze blocks and existing header-based serialization remains applicable.
- Root-index deletion hashes a view of the actual fork-specific message rather than accessing ContainerType-only fields, supporting progressive containers.
- Test fixture narrowings mostly recover the known fork of the existing fixture. Gossip spec imports choose fork-appropriate BlockInput classes, avoiding pre-Deneb assumptions for Gloas/Heze.

## Verification scope

This was an independent source/design review, not a rerun of the parent’s build, lint, unit, type-check, or generated-spec tests. Parent reports 159 targeted units and 92 generated Heze cases passed, build/lint passed, with additional post-build types/wire gossip/Gloas checks in progress. Those reports were not independently reproduced here. The temporary untracked operation-limits local harness is outside the tracked diff and must remain excluded from submission.

## Changed-file allowlist

```text
packages/api/src/beacon/routes/beacon/block.ts
packages/api/src/beacon/routes/lodestar.ts
packages/api/test/unit/beacon/hezeBlockCodec.test.ts
packages/beacon-node/src/api/impl/beacon/blocks/index.ts
packages/beacon-node/src/api/impl/validator/index.ts
packages/beacon-node/src/chain/blocks/blockInput/blockInput.ts
packages/beacon-node/src/chain/interface.ts
packages/beacon-node/src/chain/produceBlock/computeNewStateRoot.ts
packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts
packages/beacon-node/src/chain/seenCache/seenGossipBlockInput.ts
packages/beacon-node/src/db/repositories/blockArchiveIndex.ts
packages/beacon-node/src/network/processor/index.ts
packages/beacon-node/src/util/sszBytes.ts
packages/beacon-node/test/e2e/db/api/beacon/repositories/blockArchive.test.ts
packages/beacon-node/test/e2e/network/reqresp.test.ts
packages/beacon-node/test/perf/chain/verifyImportBlocks.test.ts
packages/beacon-node/test/spec/utils/gossipValidation.ts
packages/beacon-node/test/unit/chain/blocks/verifyBlocksSanityChecks.test.ts
packages/beacon-node/test/unit/chain/produceBlock/produceBlockBody.test.ts
packages/beacon-node/test/unit/db/api/repositories/blockArchive.test.ts
packages/beacon-node/test/unit/network/reqresp/collectSequentialBlocksInRange.test.ts
packages/beacon-node/test/unit/sync/range/batch.test.ts
packages/beacon-node/test/unit/sync/unknownBlock.test.ts
packages/beacon-node/test/unit/util/sszBytes.test.ts
packages/beacon-node/test/utils/state.ts
packages/cli/test/utils/crucible/utils/syncing.ts
packages/state-transition/src/block/index.ts
packages/state-transition/src/block/processDeposit.ts
packages/state-transition/src/block/processDepositRequest.ts
packages/state-transition/src/block/processEth1Data.ts
packages/state-transition/src/block/processOperations.ts
packages/state-transition/src/epoch/index.ts
packages/state-transition/src/epoch/processEth1DataReset.ts
packages/state-transition/src/epoch/processPendingDeposits.ts
packages/state-transition/src/slot/upgradeStateToHeze.ts
packages/state-transition/src/stateView/beaconStateView.ts
packages/state-transition/src/stateView/nativeBeaconStateView.ts
packages/state-transition/src/util/blindedBlock.ts
packages/state-transition/src/util/deposit.ts
packages/state-transition/src/util/electra.ts
packages/state-transition/src/util/genesis.ts
packages/state-transition/test/perf/block/processEth1Data.test.ts
packages/state-transition/test/perf/block/util.ts
packages/state-transition/test/unit-minimal/heze/eip8015.test.ts
packages/state-transition/test/unit/util/stateBytes.test.ts
packages/state-transition/test/utils/state.ts
packages/types/src/heze/sszTypes.ts
packages/types/src/types.ts
packages/types/src/utils/typeguards.ts
packages/types/test/unit/gloas/eip7688.test.ts
packages/types/test/unit/heze/eip8015.test.ts
packages/validator/src/services/block.ts
packages/validator/src/util/externalSignerClient.ts
packages/validator/test/unit/services/block.test.ts
packages/validator/test/unit/validatorStore.test.ts
```
