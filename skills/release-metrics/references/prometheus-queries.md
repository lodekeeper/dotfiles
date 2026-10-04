# Prometheus Queries for Release Metrics

All queries use the Grafana Prometheus datasource. Replace `$RC_GROUP` and `$STABLE_GROUP`
with actual group labels (e.g., `beta`, `stable`, `feat1`).

## Connection Info

- **Grafana:** `https://grafana-lodestar.chainsafe.io`
- **Prometheus datasource ID:** 1 (default), 10 (backup)
- **API endpoint:** `GET /api/ds/query` or `GET /api/datasources/proxy/1/api/v1/query`
- **Auth:** Bearer token (service account)

## Query Patterns

Use `curl` with the Grafana proxy for Prometheus queries:

```bash
# Load creds (plain `source ~/.bashrc` returns early in non-interactive shells)
eval "$(grep -E '^export (GRAFANA_TOKEN|GRAFANA_URL)=' ~/.bashrc)"

# Instant query
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "$GRAFANA_URL/api/datasources/proxy/1/api/v1/query" \
  --data-urlencode "query=<PROMQL>" | jq '.data.result'

# Range query (for trends)
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "$GRAFANA_URL/api/datasources/proxy/1/api/v1/query_range" \
  --data-urlencode "query=<PROMQL>" \
  --data-urlencode "start=$(date -d '7 days ago' +%s)" \
  --data-urlencode "end=$(date +%s)" \
  --data-urlencode "step=3600" | jq '.data.result'
```

---

## 1. Node Health

### Sync Status (state enum)
```promql
# [Stalled, SyncingFinalized, SyncingHead, Synced] = 0..3 — should be 3 (Synced) for all nodes; 0 = Stalled
lodestar_sync_status{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Head Lag (slots behind clock)
```promql
# ≈ 0 (Summary dashboard "head drift"); empty slots cause brief 1–4 slot spikes on stable too
beacon_clock_slot{group=~"$RC_GROUP|$STABLE_GROUP"} - beacon_head_slot{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Finalization Distance
```promql
# Epochs since finalized checkpoint — should be ≤ 2
beacon_clock_epoch{group=~"$RC_GROUP|$STABLE_GROUP"} - beacon_finalized_epoch{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Reorgs
```promql
# Reorg count — should match stable: network reorgs hit both groups equally (healthy hoodi nodes
# see several per 6h, mainnet ≈ 0). Gauge that only increments.
increase(beacon_fork_choice_reorg_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Peer Count
```promql
# Current peer count — expect 150-250 (Summary dashboard uses sum(lodestar_peers_by_direction_count))
libp2p_peers{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Block Processor Queue
```promql
lodestar_block_processor_queue_length{group=~"$RC_GROUP|$STABLE_GROUP"}
```

---

## 2. Attestation & Validator Performance

Validator monitor metrics have NO `lodestar_` prefix. Ratios use `rate(...[6h])` so RC and stable
cover the same window regardless of uptime.

### Head Vote Accuracy (Prev Epoch)
```promql
# Correct head ratio = hit / (hit + miss) — higher is better
rate(validator_monitor_prev_epoch_on_chain_head_attester_hit_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
/
(rate(validator_monitor_prev_epoch_on_chain_head_attester_hit_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
 + rate(validator_monitor_prev_epoch_on_chain_head_attester_miss_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h]))
```

### Wrong Head Ratio
```promql
# Wrong head votes / included attestations — lower is better (validator monitor "Wrong head ratio")
rate(validator_monitor_prev_epoch_on_chain_attester_incorrect_head_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
/
rate(validator_monitor_prev_epoch_on_chain_attester_hit_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Target Hit Rate
```promql
# Target correct ratio — should be ≥ 99.5%
rate(validator_monitor_prev_epoch_on_chain_target_attester_hit_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
/
(rate(validator_monitor_prev_epoch_on_chain_target_attester_hit_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
 + rate(validator_monitor_prev_epoch_on_chain_target_attester_miss_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h]))
```

### Source Hit Rate
```promql
rate(validator_monitor_prev_epoch_on_chain_source_attester_hit_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
/
(rate(validator_monitor_prev_epoch_on_chain_source_attester_hit_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
 + rate(validator_monitor_prev_epoch_on_chain_source_attester_miss_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h]))
```

### ATTESTER Miss Ratio
```promql
rate(validator_monitor_prev_epoch_on_chain_attester_miss_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
/
(rate(validator_monitor_prev_epoch_on_chain_attester_hit_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
 + rate(validator_monitor_prev_epoch_on_chain_attester_miss_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h]))
```

### Inclusion Distance
```promql
# Average inclusion distance — target ≈ 1.0
rate(validator_monitor_prev_epoch_on_chain_inclusion_distance_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
/
rate(validator_monitor_prev_epoch_on_chain_inclusion_distance_count{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

---

## 3. Block Processing

### Block Gossip to Head Time
```promql
# Time from slot start to set as head — compare avg
# (receipt → import only: lodestar_gossip_block_received_to_block_import_{sum,count})
rate(lodestar_gossip_block_elapsed_time_till_become_head_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_gossip_block_elapsed_time_till_become_head_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Process Block Time
```promql
rate(lodestar_stfn_process_block_seconds_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_stfn_process_block_seconds_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Blocks Set as Head After Attestation Cutoff
```promql
# Rate of late head imports — lower is better
# Cutoff = ATTESTATION_DUE_BPS of the slot (4s; 3s from Gloas). Gauge that only increments.
rate(lodestar_import_block_set_head_after_cutoff_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Process Block Count Per Slot
```promql
# Should be ≈ 1 — more means re-processing
rate(lodestar_stfn_process_block_seconds_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h]) * 12
```

### Epoch Transition Time
```promql
rate(lodestar_stfn_epoch_transition_seconds_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_stfn_epoch_transition_seconds_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Epoch Transition Count Per Epoch
```promql
# Should be ≈ 1. Breakdown by regen caller: rate(lodestar_epoch_transition_by_caller_total[1h]) * 384
rate(lodestar_stfn_epoch_transition_seconds_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h]) * 384
```

---

## 4. Memory & Resources

`process_*` / `nodejs_*` series exist per job (`beacon`, `validator`, `node_exporter`) on the same
instance — keep `job="beacon"` to compare beacon nodes only.

### RSS Memory (bytes)
```promql
# Process resident memory — compare same node types
process_resident_memory_bytes{job="beacon",group=~"$RC_GROUP|$STABLE_GROUP"}
```

### V8 Heap Used
```promql
nodejs_heap_size_used_bytes{job="beacon",group=~"$RC_GROUP|$STABLE_GROUP"}
```

### V8 Heap Total
```promql
nodejs_heap_size_total_bytes{job="beacon",group=~"$RC_GROUP|$STABLE_GROUP"}
```

### External Memory
```promql
nodejs_external_memory_bytes{job="beacon",group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Process Heap Bytes
```promql
process_heap_bytes{job="beacon",group=~"$RC_GROUP|$STABLE_GROUP"}
```

### GC Pause Rate
```promql
# GC pause as fraction of total time — should be < 0.20 (20%)
rate(nodejs_gc_duration_seconds_sum{job="beacon",group=~"$RC_GROUP|$STABLE_GROUP"}[5m])
```

### CPU Usage (cores)
```promql
rate(process_cpu_seconds_total{job="beacon",group=~"$RC_GROUP|$STABLE_GROUP"}[5m])
```

### Event Loop Lag (p99)
```promql
nodejs_eventloop_lag_p99_seconds{job="beacon",group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Disk Usage
```promql
# Disk usage percentage
1 - (node_filesystem_avail_bytes{mountpoint="/",group=~"$RC_GROUP|$STABLE_GROUP"}
/ node_filesystem_size_bytes{mountpoint="/",group=~"$RC_GROUP|$STABLE_GROUP"})
```

### Process Uptime (step 0 + normalization)
```promql
# Seconds since beacon process start — run FIRST (see SKILL.md Quick Start step 0);
# compare memory at similar uptimes. job="beacon": node_exporter series = host uptime
time() - process_start_time_seconds{job="beacon",group=~"$RC_GROUP|$STABLE_GROUP"}
```

---

## 5. Networking

### Gossip Validation Queue — Job Time
```promql
rate(lodestar_gossip_validation_queue_job_time_seconds_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_gossip_validation_queue_job_time_seconds_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Gossip Validation Queue — Dropped Jobs
```promql
# Per-topic gauge, only created on the first drop — no series means 0 drops
rate(lodestar_gossip_validation_queue_dropped_jobs_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Gossip Block Received Delay
```promql
# Time from slot start to block received via gossip
rate(lodestar_gossip_block_elapsed_time_till_received_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_gossip_block_elapsed_time_till_received_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Average Mesh Peers (Attestation Subnets)
```promql
avg(lodestar_gossip_mesh_peers_by_beacon_attestation_subnet_count{group=~"$RC_GROUP|$STABLE_GROUP"}) by (instance)
```

### Peer Score Distribution (Negative Scores)
```promql
# Buckets count peers with score ≥ threshold (graylist < publish < gossip < mesh=0)
# Negative-score (not yet graylisted) peers = graylist − mesh
lodestar_gossip_peer_score_by_threshold_count{threshold="graylist",group=~"$RC_GROUP|$STABLE_GROUP"}
- ignoring(threshold)
lodestar_gossip_peer_score_by_threshold_count{threshold="mesh",group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Req/Resp Errors
```promql
# Outgoing; also beacon_reqresp_outgoing_requests_error_reason_total, beacon_reqresp_incoming_requests_error_total
rate(beacon_reqresp_outgoing_requests_error_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

---

## 6. DB & I/O

### Archive Blocks Duration
```promql
rate(lodestar_process_finalized_checkpoint_seconds_sum{source="archive_blocks",group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_process_finalized_checkpoint_seconds_count{source="archive_blocks",group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Unfinalized Block Writes Queue
```promql
lodestar_unfinalized_block_writes_queue_length{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Prometheus Scrape Duration
```promql
scrape_duration_seconds{group=~"$RC_GROUP|$STABLE_GROUP"}
```

---

## 7. PeerDAS

### Custody Groups
```promql
beacon_custody_groups{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Missing Custody Columns (Total Counter)
```promql
# Rate matters more than absolute — accumulating counter (despite the _count suffix)
rate(lodestar_data_columns_missing_custody_columns_count{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Reconstructed Columns
```promql
# Non-supernodes ≈ 0; supernodes (super/sas/mainnet-super) reconstruct routinely — compare to stable
rate(beacon_data_availability_reconstructed_columns_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Data Column Sidecar Gossip Delay
```promql
# Time from slot start to column received, per receivedOrder label
rate(lodestar_data_column_elapsed_time_till_received_seconds_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_data_column_elapsed_time_till_received_seconds_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

---

## Tips

- **Rate interval:** Use `[6h]` or `[12h]` for smooth comparisons, `[1h]` for recent trends
- **Filter by instance:** Add `instance=~"beta-super|stable-super"` for node-type comparisons
- **Metric names may vary:** Some metrics use `_seconds`, others `_time`. Check Grafana panels
  for exact metric names if a query returns empty
- **Group labels:** Available groups include: `beta`, `stable`, `unstable`, `feat1`–`feat4`,
  `chiado`, `gnosis`, `gnosis_prod`, `sepolia`, `hoodi_prod`, `lido_prod`, `lido_hoodi_cmv2`,
  `beacon_devnet`, etc.
- **Instance naming:** Follows pattern `{group}-{type}` e.g., `beta-super`, `stable-mainnet-super`
