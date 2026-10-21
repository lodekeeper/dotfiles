**Motivation**

Closes #10162.

Prepare the bundled Ephemery configuration for Gloas from genesis on iteration 165.

**Merge timing**

Merge and deployment remain blocked pending finalization of [ephemery-genesis #75](https://github.com/ephemery-testnet/ephemery-genesis/pull/75) and coordination with the iteration-165 reset on October 22, 2026:
- `MIN_GENESIS_TIME`: 19:00 UTC (`1792695600`)
- Genesis / slot 0: 19:10 UTC (`1792696200`)

Do not merge until upstream PR #75 is finalized, the final iteration-165 configuration has been rechecked, and the October 22 reset has occurred. Do not deploy this configuration to iteration 164. The fork and blob schedules are static, even though genesis time and deposit IDs resolve to the current iteration. This patch deliberately does not add iteration-aware fork scheduling or automatic process rollover.

**Description**

- Bump the bundled iteration base to 165 and deposit chain/network IDs to `39438165`.
- Enable Gloas at epoch 0, retaining fork version `0x8000101b`.
- Start with the final BPO limit of 15 blobs per block at epoch 0, matching upstream's normalized generated schedule. This replaces the old epoch-2048/4096 schedule.
- Match upstream's disabled Heze fork version, 12-second Eth1 block time and 30 ETH ejection threshold.
- Retain the inherited Gloas timing, builder-withdrawability and churn settings, which already match upstream.
- Test Gloas selection, fork version and the blob limit from genesis across iteration 165 and subsequent resets; retain the earlier reported iteration's identity regression coverage.

References:
- [Iteration-165 metadata](https://github.com/ephemery-testnet/ephemery-genesis/blob/382421b4cb53abe2ad6a105bbbce4d2111a0edd0/values.env)
- [Proposed Gloas configuration](https://github.com/ephemery-testnet/ephemery-genesis/tree/eb975f8f37a8605d517d3766fd9a7f8703085e75)
- [Generated upstream config artifact](https://github.com/ephemery-testnet/ephemery-genesis/actions/runs/35631680108/artifacts/10655100581)

The PR branch's upstream artifact still contains iteration-164 identity values. Validation used its fork/runtime parameters with the separately pinned iteration-165 genesis time and deposit IDs.

**Validation**

- Config and its workspace dependency builds pass.
- All 62 config unit tests across 6 files pass.
- Config type checking passes.
- Full repository lint passes (1,891 files).
- All 94 supported fields present in the generated upstream config match after normalizing `CONFIG_NAME` and applying iteration-165 identity metadata.
- Independent design and functional review completed before submission.

No live Ephemery sync, genesis-generation or cross-client interop test was run. Recheck against the final iteration-165 release configuration before merging or deploying.

## Spec Compliance

- Artifact: N/A
- Reason: this is a network configuration update, not a state-transition implementation change. Validation compares the supported chain-config fields against the pinned upstream generated configuration and exercises fork/blob resolution locally.

**AI Assistance Disclosure**

- [x] I have read the contributor guidelines and disclosed AI assistance.

Lodekeeper generated the patch, regression tests and PR description with AI assistance, with independent AI design and code review.
