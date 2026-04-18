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

### Sync Status (slots behind head)
```promql
# Should be 0 for all nodes
lodestar_sync_status{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Finalization Distance
```promql
# Finalized epoch distance — should be ≤ 2
lodestar_finalized_epoch_distance{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Reorgs
```promql
# Reorg count — rate should be 0 or near-zero
increase(lodestar_fork_choice_reorg_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Peer Count
```promql
# Current peer count — expect 150-250
lodestar_peer_count{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Block Processor Queue
```promql
lodestar_block_processor_queue_length{group=~"$RC_GROUP|$STABLE_GROUP"}
```

---

## 2. Attestation & Validator Performance

### Head Vote Accuracy (Prev Epoch)
```promql
# Correct head ratio — higher is better
lodestar_validator_monitor_prev_epoch_head_correct_total{group=~"$RC_GROUP|$STABLE_GROUP"}
/
lodestar_validator_monitor_prev_epoch_head_total{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Wrong Head Ratio
```promql
# Wrong head votes rate — lower is better
rate(lodestar_validator_monitor_prev_epoch_head_wrong_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Target Hit Rate
```promql
# Target correct ratio — should be ≥ 99.5%
lodestar_validator_monitor_prev_epoch_target_correct_total{group=~"$RC_GROUP|$STABLE_GROUP"}
/
lodestar_validator_monitor_prev_epoch_target_total{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Source Hit Rate
```promql
lodestar_validator_monitor_prev_epoch_source_correct_total{group=~"$RC_GROUP|$STABLE_GROUP"}
/
lodestar_validator_monitor_prev_epoch_source_total{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### ATTESTER Miss Ratio
```promql
rate(lodestar_validator_monitor_prev_epoch_attester_miss_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Inclusion Distance
```promql
# Average inclusion distance — target ≈ 1.0
lodestar_validator_monitor_prev_epoch_inclusion_distance_sum{group=~"$RC_GROUP|$STABLE_GROUP"}
/
lodestar_validator_monitor_prev_epoch_inclusion_distance_count{group=~"$RC_GROUP|$STABLE_GROUP"}
```

---

## 3. Block Processing

### Block Gossip to Head Time
```promql
# Time from gossip receive to set as head — compare avg
rate(lodestar_gossip_block_received_to_set_as_head_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_gossip_block_received_to_set_as_head_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Process Block Time
```promql
rate(lodestar_block_process_time_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_block_process_time_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Blocks Set as Head After 4s
```promql
# Rate of late head imports — lower is better
rate(lodestar_block_set_as_head_after_4s_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Process Block Count Per Slot
```promql
# Should be ≈ 1 — more means re-processing
rate(lodestar_block_process_total{group=~"$RC_GROUP|$STABLE_GROUP"}[1h]) * 12
```

### Epoch Transition Time
```promql
rate(lodestar_epoch_transition_time_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_epoch_transition_time_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Epoch Transition Count Per Epoch
```promql
# Should be ≈ 1
rate(lodestar_epoch_transition_count_total{group=~"$RC_GROUP|$STABLE_GROUP"}[1h]) * 384
```

---

## 4. Memory & Resources

### RSS Memory (bytes)
```promql
# Process resident memory — compare same node types
process_resident_memory_bytes{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### V8 Heap Used
```promql
nodejs_heap_size_used_bytes{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### V8 Heap Total
```promql
nodejs_heap_size_total_bytes{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### External Memory
```promql
nodejs_external_memory_bytes{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Process Heap Bytes
```promql
process_heap_bytes{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### GC Pause Rate
```promql
# GC pause as fraction of total time — should be < 0.20 (20%)
rate(nodejs_gc_duration_seconds_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[5m])
```

### CPU Usage (cores)
```promql
rate(process_cpu_seconds_total{group=~"$RC_GROUP|$STABLE_GROUP"}[5m])
```

### Event Loop Lag (p99)
```promql
nodejs_eventloop_lag_p99_seconds{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Disk Usage
```promql
# Disk usage percentage
1 - (node_filesystem_avail_bytes{mountpoint="/",group=~"$RC_GROUP|$STABLE_GROUP"}
/ node_filesystem_size_bytes{mountpoint="/",group=~"$RC_GROUP|$STABLE_GROUP"})
```

### Process Uptime (for normalization)
```promql
# Important: compare memory at similar uptimes
process_uptime_seconds{group=~"$RC_GROUP|$STABLE_GROUP"}
```

---

## 5. Networking

### Gossip Validation Queue — Job Time
```promql
rate(lodestar_gossip_validation_queue_job_time_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_gossip_validation_queue_job_time_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Gossip Validation Queue — Dropped Jobs
```promql
rate(lodestar_gossip_validation_queue_dropped_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Gossip Block Received Delay
```promql
rate(lodestar_gossip_block_received_delay_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_gossip_block_received_delay_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

### Average Mesh Peers (Attestation Subnets)
```promql
avg(lodestar_gossip_mesh_peers{topic=~".*beacon_attestation.*",group=~"$RC_GROUP|$STABLE_GROUP"}) by (instance)
```

### Peer Score Distribution (Negative Scores)
```promql
# Count of peers with negative gossip score
lodestar_gossip_peer_score_negative_count{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Req/Resp Errors
```promql
rate(lodestar_reqresp_error_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

---

## 6. DB & I/O

### Archive Blocks Duration
```promql
rate(lodestar_db_archive_blocks_duration_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_db_archive_blocks_duration_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
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
lodestar_peerdas_custody_group_count{group=~"$RC_GROUP|$STABLE_GROUP"}
```

### Missing Custody Columns (Total Counter)
```promql
# Rate matters more than absolute — accumulating counters
rate(lodestar_peerdas_missing_custody_columns_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Reconstructed Columns
```promql
# Should be 0 in steady state
rate(lodestar_peerdas_reconstructed_columns_total{group=~"$RC_GROUP|$STABLE_GROUP"}[6h])
```

### Data Column Sidecar Gossip Delay
```promql
rate(lodestar_gossip_data_column_sidecar_delay_sum{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
/
rate(lodestar_gossip_data_column_sidecar_delay_count{group=~"$RC_GROUP|$STABLE_GROUP"}[1h])
```

---

## Tips

- **Rate interval:** Use `[6h]` or `[12h]` for smooth comparisons, `[1h]` for recent trends
- **Filter by instance:** Add `instance=~"beta-super|stable-super"` for node-type comparisons
- **Metric names may vary:** Some metrics use `_seconds`, others `_time`. Check Grafana panels
  for exact metric names if a query returns empty
- **Group labels:** Available groups include: `beta`, `stable`, `unstable`, `feat1`–`feat4`,
  `chiado`, `gnosis`, `sepolia`, `hoodi_prod`, `lido_prod`, `lido_hoodi`, etc.
- **Instance naming:** Follows pattern `{group}-{type}` e.g., `beta-super`, `stable-mainnet-super`
