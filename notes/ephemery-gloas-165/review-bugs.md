# Functional review: Ephemery iteration 165 Gloas

Verdict: Approved for the scoped draft PR. No functional bugs found.

- Base SHA: `9cb14e3381b08b7eb399b37c9b9e48e66eb2c791`
- SHA256 of exact two-file `git diff --` reviewed: `e9afb1427ad8b7335bf86043f0b07d127a99043496b31369f3811f41b8ae191b`
- Upstream generated config: PR #75 head `eb975f8f37a8605d517d3766fd9a7f8703085e75`
- Iteration 165 metadata: master `382421b4cb53abe2ad6a105bbbce4d2111a0edd0`

## Checks

- Gloas at epoch 0 selects Gloas types/version `0x8000101b` at slot 0. The fork ordering and epoch-0 BPO boundary resolve to Gloas, not Fulu or disabled Heze.
- The epoch-0 blob schedule consistently provides 15 blobs, including former schedule epochs 2048 and 4096.
- Disabled Heze inherits `HEZE_FORK_EPOCH: Infinity`; its version now matches upstream `0x9000101b`.
- `SECONDS_PER_ETH1_BLOCK: 12` and `EJECTION_BALANCE: 30000000000` match the generated config, rather than inherited mainnet defaults.
- Updated iteration metadata preserves derivation for iteration 163, staged iteration 164, and future iterations. Genesis delay remains 600 seconds; iteration 165 genesis is 1792696200.
- Existing within-iteration identity tests remain present; added tests cover Gloas/version/blob schedule at iterations 165, 166, and 170.
- Read the recorded targeted config tests: 62/62 passed across 6 files. `git diff --check` also passed. Did not rerun passing tests without a new concern.

## Scope boundary

The static fork/BPO configuration is intentionally not backward compatible with pre-165 iterations. The PR remains a draft and must not merge until upstream configuration is finalized and the reset is due. This review does not approve early deployment or assert live-network interoperability.
