# panda recipes for devnet debugging

> These **complement** the panda `query` skill and the "debug devnet" runbook — they don't replace them. Datasource/cluster/table names below (`clickhouse-raw`, `external.otel_logs`, `beacon_api_eth_v1_events_block`, …) are illustrative of what's typically present; **confirm the live names** with `panda datasources` / `panda schema` / `panda search examples` before relying on them, since the proxy owns them and they change. The value here is the cross-client *patterns* + the Lodestar worked example, not the literal identifiers.

All SQL runs via `panda clickhouse query <datasource> "<SQL>"`. Raw devnet data + logs are usually under the `clickhouse-raw` datasource.

## Discover hosts / clients on a network

```sql
SELECT DISTINCT ResourceAttributes['host.name'] AS host
FROM external.otel_logs
WHERE ResourceAttributes['network'] = 'glamsterdam-devnet-5'
  AND Timestamp >= now() - INTERVAL 2 HOUR
ORDER BY host
```
Hosts follow `<cl>-<el>-<n>`: `lodestar-erigon-1`, `prysm-nethermind-2`, `grandine-ethrex-1`, `teku-…`, `nimbus-…`, `lighthouse-…`, plus `bootnode-1`, `buildoor-*`. To see the containers on one node:

```sql
SELECT DISTINCT LogAttributes['log.file.name'] AS container
FROM external.otel_logs
WHERE ResourceAttributes['network']='glamsterdam-devnet-5'
  AND ResourceAttributes['host.name']='prysm-nethermind-2'
  AND Timestamp >= now() - INTERVAL 1 HOUR
```

## otel-logs tips

- Table `external.otel_logs` (database `external` = tracked devnet/testnet node logs). Internal/k8s infra logs are `internal.otel_logs` (Core only).
- **Always** filter `Timestamp` (partition column) — unfiltered scans time out.
- `SeverityText` is usually empty for raw docker logs → match severity on `Body`: `match(Body,'(?i)(crit|err|error|fatal|warn)')`.
- Strip ANSI colour for readable output: `replaceRegexpAll(Body,'\x1b\\[[0-9;]*m','')`.
- A node VM mixes CL/EL/validator/sidecar — separate with `LogAttributes['log.file.name']`.
- Narrow a known incident window with explicit bounds: `Timestamp >= '2026-06-15 10:30:00' AND Timestamp < '2026-06-15 11:30:00'`.
- Local Kurtosis enclaves instead use `EnclaveName` + `ServiceName LIKE 'cl-%'/'el-%'` (see `panda search examples --dataset otel-logs`).

## Prefer `panda execute` for breadth (aggregate in-sandbox)

Raw `panda clickhouse query` returns every row into context — costly and context-rotting. For anything beyond a tiny result, aggregate in the sandbox and return only a summary. The Python (run via `panda execute`):

```python
from ethpandaops import clickhouse
df = clickhouse.query("clickhouse-raw", """
  SELECT ResourceAttributes['host.name'] AS host,
         substring(replaceRegexpAll(Body, '\x1b\\[[0-9;]*m', ''), 1, 80) AS sig,
         count() AS n
  FROM external.otel_logs
  WHERE ResourceAttributes['network'] = 'glamsterdam-devnet-5'
    AND ResourceAttributes['host.name'] LIKE 'prysm-%'
    AND Timestamp >= now() - INTERVAL 1 HOUR
    AND match(Body, '(?i)(err|fatal|warn)')
  GROUP BY host, sig ORDER BY n DESC LIMIT 25
""")
print(df.to_string())   # ranked error signatures, not thousands of raw lines
```
Pass with `panda execute --code '<above>'` (mind shell quoting — for gnarly SQL keep the code in a heredoc, `--code "$(cat <<'PY' … PY)"`). Then drill into one signature with a small raw `LIMIT 5` query. Multi-step: cache a big pull with `df.to_parquet("/workspace/x.parquet")` in one `panda execute --session <id>` call and `pd.read_parquet(...)` it back in the next. The `ethpandaops` lib also exposes `prometheus`, `loki`, `dora`, and `specs` (`specs.get_constant("…")`), so cross-source correlation (metrics → logs → chain data) runs in one analysis.

## Xatu block / chain data (clickhouse-raw, `default.*`)

- Latest head seen + event volume:
  ```sql
  SELECT max(slot) AS head, max(slot_start_date_time) AS latest, count() AS events
  FROM beacon_api_eth_v1_events_block
  WHERE slot_start_date_time > now() - INTERVAL 30 MINUTE
  ```
- Other useful raw tables: `beacon_api_eth_v1_events_head`, `*_events_blob_sidecar`, `*_events_data_column_sidecar` (PeerDAS), `*_events_chain_reorg`, `beacon_api_eth_v2_beacon_block`, attestation/`single_attestation` tables. Use `panda schema` / `panda search examples` to confirm exact names per deployment.
- For finalized/aggregated analytics use the **xatu-cbt** dataset (`{network}.fct_*` tables, one DB per network). `_canonical` = finalized (no reorgs); `_head` = live (may reorg). Use `FINAL`. Check coverage first — CBT only has what the pipeline processed: `cbt.get_transformation_coverage(network, "{network}.<table>")`.

## Direct-access subcommands (no SQL)

- `panda block-archive …` — raw beacon blocks from the archive.
- `panda cbt …` — CBT pipeline status / coverage / table bounds.
- `panda benchmarkoor …` — EL benchmark results.
- Dora explorer + Prometheus are reachable through panda too (`panda datasources`, `panda search examples`).

## Worked example — Prysm "every node a fork" on glamsterdam-devnet-5 (2026-06-15)

Symptom (from outside): Dora `/forks` showed each Prysm node (erigon/ethrex-1/nethermind-1/2) on its own fork, all "Synchronizing", finality lost; Lodestar + LH/Nimbus/Teku stayed canonical. SSH only reaches Lodestar, so the cause had to come from Prysm's own logs → panda otel-logs.

```sql
SELECT Timestamp, ResourceAttributes['host.name'] AS host,
       replaceRegexpAll(Body,'\x1b\\[[0-9;]*m','') AS clean
FROM external.otel_logs
WHERE ResourceAttributes['network']='glamsterdam-devnet-5'
  AND ResourceAttributes['host.name'] LIKE 'prysm-%'
  AND Timestamp >= '2026-06-15 10:30:00' AND Timestamp < '2026-06-15 11:30:00'
  AND match(Body,'(?i)payload envelope processing failure')
ORDER BY Timestamp DESC LIMIT 20
```
Found, repeated across the stuck Prysm nodes:
```
WARN initial-sync: Execution payload envelope processing failure
  error=beacon block root 0x57754bf1… not found in forkchoice  firstSlot=67729
```
Reading: during initial-sync the ePBS execution-payload-envelope arrives for a beacon block **not yet in Prysm's fork-choice store** → envelope rejected → that block never gets its execution payload → fork-choice can't advance → node stuck on its own fork; the paired EL logs "Not receiving ForkChoices from the consensus client". One node (`prysm-ethrex-2`) stayed canonical. Conclusion: Prysm-side envelope/block ordering bug in initial-sync, not Lodestar — and the actual mechanism, not just the symptom.

Lesson: panda lets you read the *failing client's* internal logs directly. Don't stop at "looks like client X" inferred from Lodestar's peer view — pull X's own lines and name the failure.
