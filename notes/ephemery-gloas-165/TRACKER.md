# Ephemery iteration-165 activation

Goal: Open a reset-timed draft PR for #10162, without deployment or merge.

- [x] Nico authorization recorded in BACKLOG, Discord1562457011369811979.
- [x] Existing open PRs checked; #10278 is unrelated genesis metadata work.
- [x] Upstream master382421b4 stages165; Gloas PR75 pinned to eb975f8f, generated config artifact10655100581 saved.
- [x] Independent design approval before implementation.
- [x] Two-file patch: iteration165, Gloas0, max15-at0, disabled Heze version, Eth1 time12s, ejection30ETH.
- [x] Build config/dependencies; config types;62tests/6files; full lint1891files;94-field supported-config parity all pass.
- [x] Both final independent reviews approve exact diff e9afb1427ad8b7335bf86043f0b07d127a99043496b31369f3811f41b8ae191b.
- [x] Opened draft https://github.com/ChainSafe/lodestar/pull/10457 as lodekeeper, head611e3f9956a. Live exact metadata/body verified, publication QA incorporated. CI not yet complete. No merge/deployment.

## Spec Compliance Artifacts
N/A (network parameter update; no consensus pseudocode altered or spec vectors required). Supported fields are checked against actual generated upstream config in config-comparison.json; local tests cover fork selection/blob schedule and iteration identity derivation.

## Merge/deployment conditions
Upstream PR75 finalized; verify final165 config; coordinate with Oct22 reset. Static Gloas0/BPO15 not safe for iteration164. No deployment or merge authorized by this task.
