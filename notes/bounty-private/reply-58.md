> hmm our gloas type should not have a limit in the container

Right for the consensus type, but the report is about the Engine API codec, and that part still holds on unstable.

- `ssz.gloas.DepositRequests` is a `ProgressiveListCompositeType` with no limit. That matches the spec's `class DepositRequests(ProgressiveList[DepositRequest])` in `specs/gloas/beacon-chain.md`, which has no `LIMIT`.
- `deserializeExecutionRequestsFromBytes` decodes deposits with `ssz.electra.DepositRequests` for every fork, Gloas included: `packages/beacon-node/src/execution/engine/types.ts:631` on unstable (4671dbfa39), and `types.ts:519-521` at 0edec86. That type keeps the 8192 limit.
- With 8193 default deposit requests, both types serialize to the same bytes. `ssz.electra.DepositRequests.deserialize` throws `Invalid list length 8193 over limit 8192`, and `ssz.gloas.DepositRequests.deserialize` decodes all 8193.

So a Gloas `getPayload` response with more than 8192 deposits fails to decode, on both the JSON and the SSZ engine transports, since both go through that function. Withdrawal and consolidation requests are fine because the Gloas types keep the Electra limits.

Fix: https://github.com/ChainSafe/lodestar/pull/10515. It decodes deposits with the Gloas type from Gloas on and adds a test.
