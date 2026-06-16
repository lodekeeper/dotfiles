# ChainSafe / ethpandaops infra — secondary debugging POV

Use when panda lacks Lodestar internals: live fork-choice dump, debug-level logs, heap/CPU profiles, exact peer-by-client counts. panda otel-logs covers most cross-client needs first.

## SSH to ethpandaops Lodestar nodes (Lodestar ONLY)

```bash
ssh devops@lodestar-<el>-<n>.srv.<network>.ethpandaops.io      # key ~/.ssh/id_ed25519
# e.g. lodestar-ethrex-1.srv.glamsterdam-devnet-5.ethpandaops.io  (resolves IPv6 / Hetzner)
```
- Access is provisioned from `https://github.com/lodekeeper.keys` (ethpandaops ansible pulls `<user>.keys`). So the lodekeeper GitHub SSH key *is* the devnet access — don't remove/rotate it there or you lose devnet SSH. (Same account whose cookies drive panda auth.)
- **Key authorized on Lodestar nodes only** — Prysm/other-client boxes reject it (`Permission denied (publickey)`). Identify foreign clients from the Lodestar side, or read their logs via panda otel-logs.
- No `hc-`/`-super` prefix on glam-5 (older `bal-devnet-2` used `hc-lodestar-geth-super-1`).

On the node:
- Containers: `beacon`, `execution`, `validator`, `xatu-sentry`, `ethereum-metrics-exporter`.
- Beacon REST: `localhost:5052`. Lodestar metrics: `localhost:5054/metrics`.

```bash
# over SSH (or curl through a tunnel)
curl -s localhost:5052/eth/v1/node/syncing | jq
curl -s localhost:5052/eth/v1/debug/fork_choice | jq '.fork_choice_nodes | length'   # fork-choice dump panda can't give
curl -s localhost:5054/metrics | grep -E 'lodestar_peers_by_client_count|lodestar_sync'
docker logs --tail 200 beacon 2>&1 | tail -50
```
- Peer-by-client (authoritative): `lodestar_peers_by_client_count{client="Prysm"}`. Gossip mesh (catches flapping peers): `lodestar_gossip_mesh_peers_by_client_count{client=...}`. Reqresp history: `lodestar_sync_*_error_total{client="Prysm",...}`.
- Heap/CPU profiling on a live node → `lodestar-heapsnapshots` / `memory-profiling` skills (REST `write_heapdump`).
- Node list per network: public Dora `https://dora.<network>.ethpandaops.io/forks` (no auth). `beacon.<network>.ethpandaops.io` serves one public node.

## ChainSafe Grafana Loki (Lodestar debug logs)

ChainSafe runs its own Lodestar nodes for hosted devnets; their **debug-level** logs ship to ChainSafe Grafana Loki (datasource id 4, `grafana-lodestar.chainsafe.io`) — richer than otel for Lodestar internals.

- Selector: `group="beacon_devnet"`, `network="dev"`, `job="beacon"`, instances `devnet-ax41-0` … `devnet-ax41-3` (Hetzner AX41). Log level `debug`.
- The `grafana-loki` skill doc historically lists only holesky/mainnet/gnosis/chiado — devnet nodes ARE present under `group="beacon_devnet"`.
- Token: `eval "$(grep '^export GRAFANA' ~/.bashrc)"` (plain `source ~/.bashrc` early-returns under the non-interactive guard). Read-only Viewer.

Example LogQL (via the `grafana-loki` skill's query helper):
```
{group="beacon_devnet", instance="devnet-ax41-0"} |= "error"
{group="beacon_devnet"} |~ "(?i)(reorg|fork|unknown block|payload)"
```

## Which POV when

- Cross-client / "why is client X broken" → **panda otel-logs** (sees all clients).
- Network shape / finality / forks → **Dora /forks** + xatu.
- Lodestar fork-choice dump / live REST state → **SSH :5052**.
- Lodestar debug-level log digs (peers, disconnects, sync) → **ChainSafe Loki** (fast, no OIDC) or SSH `docker logs`.
- Lodestar peer-by-client counts → **SSH :5054 metrics**.
- Lodestar memory leak → **lodestar-heapsnapshots**.
