---
name: devnet-debug
description: "Debug hosted/remote Ethereum devnets (ethpandaops networks like glamsterdam-devnet-N) with a Lodestar lens. Builds on the panda `query` + `investigate` skills and the 'debug devnet' runbook for the data/procedure; adds the cross-client 'read the failing client's own logs' method and a ChainSafe infra POV (SSH to Lodestar nodes, ChainSafe Grafana Loki). Hosted devnets, not local Kurtosis."
---

# Devnet debugging (hosted / remote) — Lodestar lens

This skill **layers on panda's own debugging skills** — it does not replace them. For the data and the procedure, use panda:

- **`query` skill** — the panda data/query API. Discover datasources, tables, and worked queries *live* (`panda getting-started`, `panda schema`, `panda search examples "<topic>"`). **Don't hardcode datasource/table names** — they're owned by the proxy and change.
- **`investigate` skill** — routes local-vs-remote and loads the canonical runbook. For a hosted devnet, run `panda search runbooks "debug devnet"` and follow it: it owns the flow (Dora shape, `external.otel_logs`, ethnode RPC, debug-report output).

devnet-debug adds only what panda has no knowledge of: the **Lodestar interpretation**, the cross-client correlation **method**, and a **ChainSafe infra secondary POV**.

Not this skill: local Kurtosis → `kurtosis-devnet`; join with a local node → `join-devnet`; mainnet networking repro → `local-mainnet-debug`; Lodestar RC metrics → `release-metrics`; heap leaks → `lodestar-heapsnapshots`; bulk log triage → `log-reader`.

## Flow

1. **Preflight panda.** `skills/devnet-debug/scripts/ensure-panda-auth.sh` (re-auths if the 1h token lapsed → `scripts/panda/panda-reauth`). Then panda's own readiness check: `scripts/debug/check-devnet-routing-readiness.py <network>` (exit 2 = datasources not ready — fix auth first; `panda datasources --json` returning `{"datasources": null}` means *not ready*, not "network absent").
2. **Run the panda procedure.** `panda search runbooks "debug devnet"` → follow it. Use the `query` skill / `panda search examples` for query patterns; discover names live.
3. **Apply the Lodestar lens** (below).
4. **Drop to ChainSafe infra** (below) only when you need Lodestar internals panda doesn't ship.

## Triage — symptom → first look

Quick public snapshot (no auth/panda): `skills/devnet-debug/scripts/net-health.sh <network>` → finality, active forks, node→client topology. Then:

| Symptom | First look |
|---------|-----------|
| Not finalizing / low participation | `dora.get_network_overview` (or `/api/v1/epoch/latest`: `finalized`, participation) → per-client error signatures in `otel-logs` |
| A client stuck / on its own fork | Dora `/forks` (who diverged) → that client's **own** `otel-logs` → its live beacon API via the `bn-` gateway |
| ePBS / Gloas (glamsterdam) | payload-envelope / PTC / builder errors in the stuck client's logs (e.g. `payload envelope … not found in forkchoice`); confirm `GLOAS_FORK_EPOCH` (`cl/config.yaml`) is actually active |
| PeerDAS data columns missing | data-column-sidecar tables (discover via `panda schema` / `search`) + custody/sampling errors in CL logs |
| Peers dropping / low count | Lodestar `lodestar_peers_by_client_count` (`:5054` / Prometheus); peer/disconnect lines in `otel-logs`; pin the offending client |
| Lodestar block production failing | SSH `:5052` `/eth/v1/debug/fork_choice`; ChainSafe Loki debug logs; `scripts/debug/devnet-triage.sh <node>` |
| Did the network pass its tests? | Assertoor `/api/v1/test_runs` (failed runs) |

Always read the **failing client's own** logs — don't infer its bug from Lodestar's side. Once root-caused, hand the mechanism + the exact log lines to that client's team (don't just say "looks like X").

## Network metadata & explorers

Every hosted devnet has a landing page `https://<network>.ethpandaops.io/` linking all services + machine-readable config — scope a network from there.

- **`config.<network>.ethpandaops.io`:** `/api/v1/nodes/inventory` (authoritative node→client map — client, image tag, ENR, peer_id, `bn-` beacon URI per node), `/api/v1/nodes/validator-ranges` (validator index → node), `/cl/config.yaml` (fork schedule, e.g. `GLOAS_FORK_EPOCH`; far-future `18446744073709551615` = not scheduled), `/cl/genesis.ssz`, `/el/genesis.json`. Client versions also in repo `ethpandaops/<network>s` (`…/images.yaml`).
- **Services:** `rpc.` (EL RPC), `beacon.` (public CL REST), `dora.`, `forkmon.`, `syncoor.` (sync tests), `assertoor.` (network test runner — `/api/v1/test_runs` & `/api/v1/tests` JSON for pass/fail), `checkpoint-sync.`, `faucet.`.
- **Dora — prefer the panda module:** `from ethpandaops import dora` → `dora.get_network_overview(net)` (epoch/slot/finality/participation/validator counts), `get_epoch`/`get_slot`/`get_validator(s)`, `link_*`. Quick raw curl (no auth): `/api/v1/epoch/latest` (finality + participation), `/api/v1/slot/<n>`, `/api/v1/slots`, `/api/v1/validators`, `/api/v1/validator/<idx>` (JSON); `/forks` is the HTML fork view (one row per fork = a split).

Full endpoint catalog + examples: `references/network-metadata.md`.

## Query discipline — prefer `panda execute`

panda's whole point is the **sandbox Python runtime**, not raw SQL dumps. A `panda clickhouse query` returning thousands of rows floods context ("context rot") — the exact thing panda was built to avoid (see the ethpandaops panda post). So:

- **Aggregate in the sandbox, return summaries.** `panda execute --code '...'` with the `ethpandaops` lib (`clickhouse`/`prometheus`/`loki`/`dora`/`specs`) → return `df.describe()`, group-by counts, or top-N — not raw rows.
- **Logs:** group by error signature, return the top distinct patterns + counts, then drill into a couple of examples. Don't dump hundreds of lines.
- **Raw `panda clickhouse query` only for tiny results** (a count, a handful of rows).
- **Sessions** for multi-step: `panda execute --session <id>` keeps the sandbox warm; cache an expensive pull to `/workspace/*.parquet` and reuse it next call.
- **Spec constants inline:** `from ethpandaops import specs; specs.get_constant("MAX_EFFECTIVE_BALANCE")`.

Execute-based otel-logs example: `references/panda-recipes.md`.

## Lodestar lens — is it us?

On an interop devnet the high-value move: when a client is stuck/forked, read **that client's own** logs — don't infer its bug from Lodestar's peer view. The runbook's `external.otel_logs` carries every client; key by network + `host.name` (`<cl>-<el>-<n>`, e.g. `prysm-nethermind-2`), split CL/EL via `log.file.name`, match severity on `Body`. Confirm current table/column names via `panda schema` / `panda search examples` before trusting any literal.

When Lodestar **is** implicated, cross-check head/finality/peers, then go to the secondary POV for internals.

Worked example (Prysm "every node a fork" on glam-devnet-5 → `Execution payload envelope … not found in forkchoice`) and the exact otel-logs query pattern: `references/panda-recipes.md`.

## Secondary POV — ChainSafe infra (panda has none of this)

Use when you need Lodestar internals panda doesn't carry: live fork-choice dump, debug-level logs, heap/CPU profiles, exact peer-by-client counts.

- **SSH (Lodestar nodes only):** `ssh devops@lodestar-<el>-<n>.srv.<network>.ethpandaops.io` (key `~/.ssh/id_ed25519` = the lodekeeper.keys entry). Beacon REST `localhost:5052`, metrics `localhost:5054/metrics`. Other-client nodes reject the key — read theirs via panda otel-logs (logs) or the `bn-` gateway below (live beacon API). Peer-by-client: `lodestar_peers_by_client_count{client="Prysm"}`.
- **Any-client beacon API (`bn-` gateway):** reaches **every** client's beacon API (Prysm/LH/Teku/Nimbus/Grandine/Lodestar), unlike the SSH key. `AUTH=$(awk -F': ' '/^<network>:/{print $NF}' ~/.config/ethpandaops/bn-basic-auth)` then `curl "https://$AUTH@bn-<cl>-<el>-<n>.srv.<network>.ethpandaops.io/<beacon-path>"` — HTTP basic auth (user `eth`). Use for live head/finality/peers/version/syncing of a stuck *non-Lodestar* node, and Lodestar debug routes (`/eth/v1/lodestar/...`) on ours. Password is per-devnet and **not in this repo** — stored `0600` at `~/.config/ethpandaops/bn-basic-auth`; get fresh per-devnet creds from Nico / the devnet config. (Bare `<node>.<network>` without `bn-` 404s.)
- **ChainSafe Grafana Loki:** ChainSafe's own Lodestar devnet nodes ship **debug-level** logs to Loki (datasource 4) under `group="beacon_devnet"`, `network="dev"`, instances `devnet-ax41-0..3`. Faster than panda for Lodestar peer/disconnect/sync digs, no OIDC. Token: `eval "$(grep '^export GRAFANA' ~/.bashrc)"`. See `grafana-loki` skill.
- **One-shot per-node snapshot:** `scripts/debug/devnet-triage.sh <node>` pulls that node's recent error logs (Loki) + key metrics (Prometheus) into a markdown report (needs `GRAFANA_TOKEN`).

Full commands + "which POV when": `references/chainsafe-infra.md`.

## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.

## Iteration Log

Track what works and what doesn't after each use:

| Date | Network / issue | What worked | What to improve |
|------|-----------------|-------------|-----------------|
| 2026-06-16 | glamsterdam-devnet-5 — Prysm "every node a fork" | Cross-client `otel-logs` surfaced Prysm's own `Execution payload envelope … not found in forkchoice` lines — named the mechanism, not just "looks like Prysm". `config/api/v1/nodes/inventory` + the `bn-` gateway gave topology/versions/live beacon API without SSH. | First pass dumped raw log rows into context (costly) → switched to `panda execute` aggregation. Confirm live table/datasource names via `panda schema` / `search examples` before querying — don't trust the literals here. |
