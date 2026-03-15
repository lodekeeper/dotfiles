# Incident Bundle: epbs-devnet-0 incident

- Incident ID: `incident-epbs-devnet-0-20260315-093258Z`
- Generated: 2026-03-15 09:32:59 UTC
- Primary node: `epbs-devnet-0`
- Peer nodes: (none)

## Environment metadata

- Host: `server2`
- User: `openclaw`
- Kernel: `Linux 6.8.0-45-generic x86_64 GNU/Linux`
- Node.js: `v22.19.0`
- pnpm: `10.28.2`
- Repo: `/home/openclaw/lodestar`
- Repo branch/head: `unstable` @ `c11b797bd6` (clean)
- Grafana URL: `https://grafana-lodestar.chainsafe.io`
- Grafana token present: no

## Triage snapshot (logs + metrics + process health)

_Triage status: **ok**_

# Devnet Triage Report

- Node: epbs-devnet-0
- Generated: 2026-03-15 09:32:58 UTC
- Window: 30m (from 2026-03-15 09:02:58 UTC to 2026-03-15 09:32:58 UTC)
- Selector: instance=~".*epbs-devnet-0.*"

## 1) Process + uptime
- No local process matched: `epbs-devnet-0`

## 2) Port listener check (zombie/process conflicts)
- Port 9000: free
- Port 9596: free
- Port 5052: free

## 3) Recent error logs (Loki)
- GRAFANA_TOKEN not set; skipping Loki query

## 4) Peer/attestation health snapshot (Prometheus via Grafana)
- GRAFANA_TOKEN not set; skipping Prometheus metrics

## 5) Restart hints (from logs)
- GRAFANA_TOKEN not set; skipping restart hint query

## Triage summary
- No listener conflicts detected on requested ports
- If logs/metrics are empty, refine --selector or override --loki-query

## Correlated timeline

_Timeline status: **skipped** — Need at least two nodes (primary + one --peer)_

No cross-node timeline attached in this run.
- Add one or more `--peer` nodes for correlation.
- Ensure `GRAFANA_TOKEN` is set if timeline fetches are expected.

## Incident timeline notes

- [ ] First symptom observed (timestamp + source)
- [ ] Impact window (who/what affected)
- [ ] Candidate root cause(s)
- [ ] Confirmed root cause
- [ ] Mitigation / fix applied
- [ ] Follow-up actions (tests, alerts, docs)
