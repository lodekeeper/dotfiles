**Motivation**

`initializeBeaconStateFromEth1` never sets `proposer_lookahead`, so a state that starts at fulu or later keeps it all zeros. The epoch cache reads fulu proposers from that field, so validator 0 becomes the proposer of every slot in the first two epochs. The pyspec genesis helper (`create_genesis_state`) initializes it with `initialize_proposer_lookahead`, and other clients compute the real proposers.

This showed up when #9957 moved the mixed-client sim to fulu at genesis: Lighthouse rejects the Lodestar blocks with `IncorrectBlockProposer { block: 0, local_shuffling: 23 }`, and the nodes split from slot 2. It affects genesis states that Lodestar builds itself, such as `dev` and the sims.

**Description**

- Fill `proposer_lookahead` at fulu+ genesis with the proposers of epochs 0 to `MIN_SEED_LOOKAHEAD`, computed from the genesis active validators
- Test that a fulu genesis lookahead matches the proposers an electra genesis of the same validators computes for those epochs

The test fails without the fix (all zeros). My local setup can't build `@lodestar/native`, so I couldn't run it against this change and am relying on CI for the passing run.

**AI Assistance Disclosure**

Written with AI assistance (Claude), including the investigation, implementation, test and description.
