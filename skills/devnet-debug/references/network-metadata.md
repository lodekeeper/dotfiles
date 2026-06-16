# Network metadata & Dora API (hosted devnets)

Landing page `https://<network>.ethpandaops.io/` links every service + config. Replace `<network>` (e.g. `glamsterdam-devnet-5`). All endpoints below are public (no auth).

## config.<network>.ethpandaops.io — machine-readable metadata

- **`/api/v1/nodes/inventory`** — JSON `{ethereum_pairs: {<node>: {consensus:{client,image,enr,peer_id,beacon_uri}, execution:{client,image,enode,…}}}}`. Authoritative **node→client+version** map; gives each node's ENR, libp2p `peer_id`, and `bn-<node>.srv…` beacon URI. Best first stop for topology + exact client image tags (e.g. `ethpandaops/prysm-beacon-chain:glamsterdam-devnet-5`).
- **`/api/v1/nodes/validator-ranges`** — which validator indices each node runs (validator→node attribution; pairs with Dora's per-validator data).
- **`/cl/config.yaml`** — CL config: `PRESET_BASE`, fork versions + epochs (`*_FORK_EPOCH`). Far-future `18446744073709551615` = not scheduled. e.g. glam-5: everything ≤ Fulu at epoch 0, `GLOAS_FORK_EPOCH: 30`, Heze unscheduled. This is the authoritative fork schedule — check it before assuming a fork is active.
- **`/cl/genesis.ssz`** — CL genesis state (ssz; for genesis/checkpoint sync).
- **`/el/genesis.json`**, **`/el/chainspec.json`**, **`/el/besu.json`** — EL genesis/chainspec per client.
- **`/cl/deposit_contract.txt`**, **`/cl/deposit_contract_block.txt`**, **`…_block_hash.txt`**.
- Image tags + spec also on GitHub: `ethpandaops/<network>s` → `ansible/inventories/<devnet>/group_vars/all/images.yaml` (versions) and `network-configs/<devnet>/metadata` (spec).

## Services (linked from the landing page)

- `rpc.<network>` — EL JSON-RPC. `beacon.<network>` — one public CL REST node (any client's beacon API per-node via the `bn-` gateway → see `chainsafe-infra.md`).
- `dora.<network>` — explorer (API below). `forkmon.<network>` — fork monitor. `syncoor.<network>` — sync status. `assertoor.<network>` — assertion/test runner. `checkpoint-sync.<network>` — checkpointz. `faucet.<network>`. HackMD notes: `notes.ethereum.org/@ethpandaops/<network>`.

## Dora — panda module (preferred, inside `panda execute`)

`from ethpandaops import dora`:
- `dora.get_network_overview(net)` → current + finalized epoch/slot, `finalizing` status, validator counts, participation. The one-call health snapshot.
- `dora.get_epoch(net, epoch)`, `dora.get_slot(net, slot_or_hash)`, `dora.get_validator(net, idx_or_pubkey)`, `dora.get_validators(net, status=None, limit=100)`.
- `dora.link_slot/link_epoch/link_block/link_validator/link_address(net, …)`, `dora.list_networks()`, `dora.get_base_url(net)`.

## Dora — raw REST API (quick curl, no auth)

Base `https://dora.<network>.ethpandaops.io`:
- **`GET /api/v1/epoch/latest`** (or `/api/v1/epoch/<epoch>`) → epoch summary: `epoch, finalized, globalparticipationrate, validatorscount, missedblocks, orphanedblocks, proposedblocks, scheduledblocks, averagevalidatorbalance, votedether, eligibleether, withdrawalcount, …`. Finality + participation at a glance.
- **`GET /api/v1/slot/<n>`**, **`GET /api/v1/slots`** → slot detail / recent slots.
- **`GET /api/v1/validators`**, **`GET /api/v1/validator/<idx-or-pubkey>`** → validator info.
- **`/forks`** (HTML, not JSON) — per-node fork view: one row per fork = a split; "Synchronizing" rows = stuck nodes. The fastest visual "who diverged".
- `/clients`, `/api/docs` → 404 (don't exist).

Quick checks:
```bash
N=glamsterdam-devnet-5
# finality + participation
curl -s "https://dora.$N.ethpandaops.io/api/v1/epoch/latest" | jq '{epoch,finalized,participation:.globalparticipationrate,validators:.validatorscount,missed:.missedblocks,orphaned:.orphanedblocks}'
# topology: every node's client + image + bn- URI
curl -s "https://config.$N.ethpandaops.io/api/v1/nodes/inventory" | jq '.ethereum_pairs | to_entries[] | {node:.key, cl:.value.consensus.client, cl_image:.value.consensus.image, el:.value.execution.client}'
# fork schedule
curl -s "https://config.$N.ethpandaops.io/cl/config.yaml" | grep -E "FORK_EPOCH|PRESET_BASE"
```
Inside panda, prefer `dora.get_network_overview(net)` over curling `/api/v1/epoch/latest` — same data, stays in the sandbox.
