**Motivation**

Closes #10162. Activate Gloas from genesis in the bundled Ephemery preset for iteration 165.

**Reset and upstream configuration**

[ephemery-genesis #75](https://github.com/ephemery-testnet/ephemery-genesis/pull/75) merged on October 22, 2026. The published [ephemery-165 release](https://github.com/ephemery-testnet/ephemery-genesis/releases/tag/ephemery-165) has minimum genesis time `1792695600` (19:00 UTC), genesis `1792696200` (19:10 UTC), and deposit chain/network IDs `39438165`.

The final release configuration has been rechecked against this PR, and LIVE_RESET_RESULT_PENDING. This remains a static iteration-165-and-later preset update, not an iteration-aware fork scheduler or automatic process rollover. It is not backward compatible with the Fulu iteration 164.

**Description**

- Bump the bundled iteration base to 165 and deposit chain/network IDs to `39438165`.
- Enable Gloas at epoch 0, retaining fork version `0x8000101b`.
- Start with the final BPO limit of 15 blobs per block at epoch 0, matching upstream's generated schedule.
- Match upstream's disabled Heze fork version, 12-second Eth1 block time and 30 ETH ejection threshold.
- Retain the inherited Gloas timing, builder-withdrawability and churn settings, which match upstream.
- Test Gloas selection, fork version and the blob limit from genesis across iteration 165 and subsequent resets; retain the earlier reported iteration's identity regression coverage.

**Validation**

- Config and workspace dependency builds, config type checking and full repository lint passed at submission. All 62 config unit tests across 6 files passed.
- Final published iteration-165 config: all 93 comparable supported fields match, excluding the intentional `CONFIG_NAME` difference (`ephemery` versus upstream `testnet`).
- The preset's default genesis download matches the published iteration-165 genesis byte-for-byte.
- Fresh exact-head CLI/dependency build, 10 network tests and targeted lint pass on October 23.
- LIVE_SYNC_RESULT_PENDING
- Current-head CI: CI_RESULT_PENDING

The live test uses `--network ephemery --execution.engineMock --supernode`, a fresh database and no config, genesis or checkpoint override. It validates CL sync with a mocked execution engine, not real-EL payload validation. No live genesis-generation or real-EL interoperability test was run.

References:
- [Final iteration-165 config](https://github.com/ephemery-testnet/ephemery-genesis/releases/download/ephemery-165/config.yaml)
- [Final iteration-165 genesis](https://github.com/ephemery-testnet/ephemery-genesis/releases/download/ephemery-165/genesis.ssz)
- [Merged upstream configuration](https://github.com/ephemery-testnet/ephemery-genesis/commit/9c2cac445414a12d8ed4f8bcec5f004bca70e898)

## Spec Compliance

- Artifact: N/A
- Reason: this is a network configuration update, not a state-transition implementation change. Validation compares the supported chain-config fields against the published upstream configuration and exercises fork/blob resolution locally.

**AI Assistance Disclosure**

- [x] I have read the contributor guidelines and disclosed AI assistance.

Lodekeeper generated the patch, regression tests and PR description with AI assistance, with independent AI design and code review.
