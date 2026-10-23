# Second independent run (topic:50 claude-cli run, started before this tracker existed)

- Build: /tmp/lodestar-10457 at 611e3f9956a (offline frozen install, `pnpm --filter "@chainsafe/lodestar..." build`)
- Command: `./lodestar beacon --network ephemery --execution.engineMock --dataDir /tmp/ephemery-165/run/data --rest.port 9777 --port 9277 --network.connectToDiscv5Bootnodes` (no supernode, no config/genesis/checkpoint override)
- Started 10:50:52 UTC from genesis; peers accepted status (Gloas fork digest) within ~20s; reached head ~10:58 UTC (~4700 slots in ~8 min, 1-4 peers)
- 11:10 UTC: head 4793 vs wall slot 4794, sync_distance 0, not optimistic, 4 peers; finalized epoch 147 root 0xaddc52b2...683c, identical to beaconstate-ephemery.chainsafe.dev and checkpoint-sync.ephemery.ethpandaops.io; 0 error lines in console log
- Config: resolved `getEphemeryChainConfig(now)` vs release ephemery-165 config.yaml: 91 fields equal, only CONFIG_NAME (ephemery vs testnet) differs, plus GAS_LIMIT_SCHEDULE `[]` formatting
- Node stopped 11:11 UTC to avoid duplicating the tracker's own node; logs in /tmp/ephemery-165/run/
