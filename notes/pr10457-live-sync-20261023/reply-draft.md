Yes, tested on live Ephemery iteration 165 and ready to merge from my side.

Ran the exact head `611e3f9956a` with `--network ephemery --execution.engineMock --supernode`, fresh DB, no config, genesis or checkpoint override.

- Genesis downloaded automatically and matches the [ephemery-165 release](https://github.com/ephemery-testnet/ephemery-genesis/releases/tag/ephemery-165) byte-for-byte
- Range synced from genesis to head in about 7 minutes, then followed head: slot 4848 = wall slot at 11:19 UTC, `is_syncing: false`, fork `0x8000101b` (Gloas)
- Finalized epoch 149 `0x6cf16c…0a42`, same as beaconstate-ephemery.chainsafe.dev and ephemery.beaconstate.ethstaker.cc
- Peers were Lighthouse and Teku over TCP and QUIC. No error logs, and no warnings beyond the low-heap and low-peer-count notices at startup
- A second run without `--supernode` also synced to head and matched the public finalized checkpoint at epoch 147

[ephemery-genesis#75](https://github.com/ephemery-testnet/ephemery-genesis/pull/75) is merged and the preset matches all comparable fields of the final 165 config. CI is green.

The open Codex P1 only applied before the 10-22 reset. Any node started now resolves iteration 165, so it no longer applies.

The engine mock covers CL sync only. Execution payloads are not validated against a real EL.
