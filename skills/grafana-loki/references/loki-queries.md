# Loki Queries Reference

Ready-to-use LogQL queries for common investigation scenarios.
Replace `$INSTANCE`, `$GROUP`, `$JOB` with actual values.

## Connection Info

- **Grafana:** `https://grafana-lodestar.chainsafe.io`
- **Loki datasource ID:** 4
- **Auth:** Bearer token (service account)

## Query Template

```bash
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "$GRAFANA_URL/api/datasources/proxy/4/loki/api/v1/query_range" \
  --data-urlencode 'query=<LOGQL>' \
  --data-urlencode "start=$(date -d '<TIME_AGO>' +%s)" \
  --data-urlencode "end=$(date +%s)" \
  --data-urlencode "limit=<N>" \
  --data-urlencode "direction=backward" | jq -r '.data.result[].values[][1]'
```

For cross-node queries (showing instance name):
```bash
... | jq -r '.data.result[] | "\(.stream.instance):", (.values[][1])'
```

---

## 1. Crash & Restart Investigation

### Fatal / Exit / OOM Messages
```logql
{instance="$INSTANCE"} |~ "(?i)(fatal|exit|kill|SIGTERM|SIGKILL|OOM|heap out|JavaScript heap|Allocation failed|abort|uncaught|unhandled)"
```

### Shutdown / Graceful Stop
```logql
{instance="$INSTANCE"} |~ "(?i)(shutdown|exiting|graceful|stopping|closed|terminated)"
```

### Last Logs Before Crash
Use `direction=backward` and set `end=` to the crash/restart timestamp:
```logql
{instance="$INSTANCE",job="beacon"}
```

---

## 2. Block Processing

### Block Errors (All Types)
```logql
{instance="$INSTANCE"} |~ "BLOCK_ERROR|Block error|Block verification"
```

### Execution Engine Errors
```logql
{instance="$INSTANCE"} |~ "EXECUTION_ERROR|execStatus=INVALID|links to previously rejected|execution payload"
```

### Engine API Results
```logql
{instance="$INSTANCE"} |~ "engine api newPayload|forkchoiceUpdate|status=INVALID|status=SYNCING"
```

### Block Import Timeline
```logql
{instance="$INSTANCE"} |~ "importBlock|block imported|set as head|gossip_block"
```

---

## 3. Sync Issues

### Finalized Sync Errors
```logql
{instance="$INSTANCE"} |~ "Batch process error|Batch download error|SyncChain Error|MAX_.*ATTEMPTS"
```

### Sync Progress
```logql
{instance="$INSTANCE"} |~ "Sync peer joined|sync.*startEpoch|targetSlot|Finalized.*synced"
```

### Range Sync Download Issues
```logql
{instance="$INSTANCE"} |~ "DOWNLOAD_BY_RANGE_ERROR|BLOCKS_BY_RANGE_ERROR|BAD_SEQUENCE"
```

### EL Sync Status Changes
```logql
{instance="$INSTANCE"} |~ "Execution client is syncing|oldState=|newState="
```

---

## 4. Networking

### Req/Resp Errors
```logql
{instance="$INSTANCE"} |~ "Req  error|REQUEST_ERROR" | line_format "{{__line__}}"
```

### Specific Req/Resp Method Errors
```logql
{instance="$INSTANCE"} |~ "method=beacon_blocks_by_range.*error|method=data_column_sidecars.*error"
```

### Peer Connection Issues
```logql
{instance="$INSTANCE"} |~ "DIAL_ERROR|ECONNREFUSED|connection.*close|unexpected end|TTFB_TIMEOUT|RESP_TIMEOUT"
```

### Gossip Errors
```logql
{instance="$INSTANCE"} |~ "gossip.*error|gossip.*invalid|gossip.*reject"
```

### Peer Score Issues
```logql
{instance="$INSTANCE"} |~ "peer score|peer.*banned|peer.*disconnected"
```

---

## 5. EL (Execution Layer) Logs

### All EL Errors for a Group
```logql
{group="$GROUP",job="execution"} |~ "(?i)(error|INVALID|rejected|failed)" | line_format "{{.instance}}: {{__line__}}"
```

### Receipt Root / State Root Mismatches
```logql
{group="$GROUP",job="execution"} |~ "invalid receipt root|invalid state root|mismatch"
```

### NewPayload Failures
```logql
{group="$GROUP",job="execution"} |~ "NewPayload.*failed|inserting block failed"
```

### EL Sync Progress
```logql
{instance="$INSTANCE",job="execution"} |~ "(?i)(syncing|synced|imported|downloading|header)"
```

---

## 6. Validator

### Missed Duties
```logql
{instance="$INSTANCE",job="validator"} |~ "(?i)(miss|skip|late|timeout|duty)"
```

### Attestation Issues
```logql
{instance="$INSTANCE"} |~ "attestation.*error|attestation.*fail|attester.*miss"
```

### Block Proposals
```logql
{instance="$INSTANCE"} |~ "proposal|produceBlock|publishBlock|block produced"
```

---

## 7. PeerDAS Specific

### Data Column Issues
```logql
{instance="$INSTANCE"} |~ "data_column|custody.*column|missing.*column|reconstruct"
```

### Column Download Errors
```logql
{instance="$INSTANCE"} |~ "data_column_sidecars_by_range.*error|column.*timeout"
```

---

## 8. Cross-Node Queries

### Compare Errors Across Group
```logql
{group="$GROUP",job="beacon"} |~ "error " | line_format "{{.instance}}: {{__line__}}"
```

### Find Which Nodes Have a Specific Error
```logql
{group="$GROUP"} |= "SPECIFIC_ERROR_TEXT" | line_format "{{.instance}}"
```

### List All Available Instances
```bash
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "$GRAFANA_URL/api/datasources/proxy/4/loki/api/v1/label/instance/values" | jq -r '.data[]' | grep "$GROUP"
```

### List All Available Jobs
```bash
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "$GRAFANA_URL/api/datasources/proxy/4/loki/api/v1/label/job/values" | jq -r '.data[]'
```

---

## 9. Warn/Error Only (Filtering Noise)

### CL Warn + Error Only
```logql
{instance="$INSTANCE",job="beacon"} |~ "\\[33mwarn|\\[31merror"
```

### Without ANSI (pattern-based)
```logql
{instance="$INSTANCE",job="beacon"} |~ "warn\\]|error\\]" !~ "verbose|debug"
```

---

## Tips

- **Time ranges:** Keep to 30min–6h for fast results. Loki queries over 24h+ can be very slow.
- **Use `direction=backward`** for most investigation work — you usually want the latest events first.
- **Label selectors first:** `{instance="X",job="beacon"}` narrows the search before expensive line matching.
- **Escape special chars:** In LogQL, `|`, `{`, `}`, `"` need escaping in some contexts. In curl, use single quotes around the query.
- **ANSI color codes:** Lodestar logs contain ANSI escape codes (`[33m` = yellow/warn, `[31m` = red/error, `[34m` = blue/debug, `[36m` = cyan/verbose, `[39m` = reset). Use these for level filtering if standard patterns don't work.
- **Rate limiting:** Loki/Grafana may rate-limit heavy queries. If you get 429s, narrow the time range.
