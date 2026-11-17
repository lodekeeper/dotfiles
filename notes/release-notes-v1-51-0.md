# v1.51.0 Release Notes (draft)

## GitHub Release Header

Good day Lodestar operators! We've just released v1.51.0, a **recommended** upgrade for all users. It is **required for Ephemery**, which runs Gloas from genesis since iteration 165, and strongly recommended for Sepolia and other Gloas networks, which get a batch of ePBS fixes.

**Upgrade note:** long-running supernodes that still hold legacy data column entries compact that part of the database once on first start. This can take several minutes (about 8 minutes on one of our Hoodi supernodes). Later startups and archive jobs are much faster. (#10447, #10460)

### Highlights

- **Gloas (ePBS) fixes**: correct PTC duties dependent root at the fork epoch, payload data availability wait capped at the slot duration, parent payload checked before importing a repeat proposal, unrealized checkpoints recomputed for blocks with slashings, and archive pruning no longer deletes light client data of canonical blocks. (#10468, #10433, #10424, #10467, #10022)
- **Faster startup and archiving on supernodes**: no more slow LevelDB scans over long-deleted legacy data column entries. On one Hoodi supernode the startup stall went from 20 minutes to milliseconds. (#10447, #10460)
- **Validator client hardening**: attestation slashing protection checks are serialized per validator, doppelganger safety only considers messages that count toward liveness, a failing selection proof no longer affects other validators, and shutdown is cleaner. (#10303, #10396, #10387, #10441)
- **Builder bidding**: `lodestar builder` can now build, bid and reveal on Gloas networks. A hidden `--api.disableBidValidation` flag lets a trusted local builder skip validation of bids it publishes through the beacon API. (#10379, #10429)
- **Experimental native state transition**: the hidden `--chain.nativeStateTransition` flag now also works when Gloas is scheduled. (#10345, #10471)

Engine API metrics: `lodestar_execution_engine_http_client_stream_time_seconds` no longer includes JSON parsing, which has its own `lodestar_execution_engine_http_client_response_parse_time_seconds` metric now. (#10349)

[Full Changelog](https://github.com/ChainSafe/lodestar/compare/v1.50.1...v1.51.0)

## Discord Announcement

Good day Lodestar operators! We've just released v1.51.0 and **recommend** all users upgrade. It is **required for Ephemery** (Gloas from genesis since iteration 165) and strongly recommended for Sepolia and other Gloas networks.

Upgrade note: long-running supernodes compact legacy data column entries once on first start, which can take several minutes. Later startups and archive jobs are much faster.

Key highlights:
🛡️ Gloas (ePBS) fixes: PTC duties at the fork epoch, payload data availability wait, repeat proposals, slashings in fork choice, archive pruning
⚡ Faster startup and archiving on supernodes: no more slow LevelDB scans over deleted legacy column data
🔧 Validator client hardening: per-validator slashing protection checks, doppelganger and selection proof fixes, cleaner shutdown
🏗️ `lodestar builder` can now bid and reveal on Gloas networks
🧪 Experimental native state transition (`--chain.nativeStateTransition`) now works with Gloas scheduled

For the full changelog: https://github.com/ChainSafe/lodestar/releases/v1.51.0
