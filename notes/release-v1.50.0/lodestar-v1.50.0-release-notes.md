## GitHub Release Header

Good day Lodestar operators! We've just released v1.50.0. It is **mandatory** for Hoodi operators and **recommended** for mainnet users.

This release schedules the Glamsterdam (Gloas) fork on Hoodi:
- **Epoch:** `132352`
- **Time:** Mon, 26 Oct 2026, 17:42:48 UTC
- **Gas limit:** raised to 200M at the fork

Hoodi operators must also upgrade their execution client to a Glamsterdam-ready release before the fork.

### Highlights

- **Hoodi Glamsterdam fork scheduled.** Adds the fork epoch and the 200M gas limit schedule. (#10313)
- **Validator clients from Gloas.** Fee recipient and gas limit come from signed proposer preferences. From the fork on, the beacon node rejects `prepare_beacon_proposer` and `register_validator` with `410`. Upgrade the Lodestar beacon node and validator client together. If you run another validator client against a Lodestar beacon node, make sure it supports proposer preferences. (#10336, #10337, #10341)
- **Builders from Gloas.** Builder bids also arrive in-protocol over p2p. External builders are configured on the validator client (`--builder.urls`, or per key in the proposer config) instead of through relays on the beacon node. Pre-Gloas builder settings keep working until the fork. Setup guides:
  - [Configure external builders (Gloas)](https://chainsafe.github.io/lodestar/run/validator-management/vc-configuration/#configure-external-builders-gloas)
  - [Builder selection and boost factor](https://chainsafe.github.io/lodestar/run/validator-management/vc-configuration/#configure-your-builder-selection-andor-builder-boost-factor)
  - [Per-key builder settings from Gloas](https://chainsafe.github.io/lodestar/run/validator-management/proposer-config/#builder-settings-from-gloas)
- **SSZ engine API.** When the execution client advertises the REST/SSZ engine API, Lodestar uses it automatically, otherwise it keeps using JSON-RPC. Override with `--execution.engineApi`. (#10204)
- **Metrics note.** The `notifyNewPayload` engine timing metric now reflects execution client time more accurately. Previously it included part of Lodestar's own block processing, so values will read lower after upgrading. This is a measurement change, not a change in block import time.

[Full Changelog](https://github.com/ChainSafe/lodestar/compare/v1.49.0...v1.50.0)

## Discord Announcement

Good day Lodestar operators! We've just released v1.50.0. It is **mandatory** for Hoodi operators and **recommended** for mainnet users.

🗓️ Glamsterdam (Gloas) activates on Hoodi at epoch 132352, Mon 26 Oct 2026, 17:42:48 UTC. The gas limit rises to 200M at the fork. Upgrade your execution client to a Glamsterdam-ready release too.
🛡️ From Gloas, fee recipient and gas limit come from signed proposer preferences, and `prepare_beacon_proposer` / `register_validator` return 410. Upgrade the Lodestar beacon node and validator client together.
🏗️ From Gloas, builders are configured on the validator client (`--builder.urls`), and p2p builder bids are used too. Setup: <https://chainsafe.github.io/lodestar/run/validator-management/vc-configuration/#configure-external-builders-gloas>
⚡ The SSZ engine API is used automatically when your execution client supports it.
📊 The newPayload engine timing metric now reads lower. This is a more accurate measurement, not a behaviour change.

Full changelog: https://github.com/ChainSafe/lodestar/releases/v1.50.0
