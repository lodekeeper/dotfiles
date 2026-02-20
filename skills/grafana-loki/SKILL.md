---
name: grafana-loki
description: >
  Query logs from Grafana Loki for Lodestar beacon nodes, execution clients, and validators.
  Use when investigating node crashes, errors, sync issues, or any log-level debugging.
  Covers CL (beacon), EL (execution), validator, and infrastructure logs.
  Requires Grafana access to the Lodestar monitoring stack.
---

# Grafana Loki Log Querying

Query structured logs from the Lodestar infrastructure via Grafana's Loki datasource.

## When to Use

- Investigating node crashes, restarts, or OOM kills
- Debugging sync issues (finalized sync, head sync, range sync)
- Checking EL ↔ CL communication errors (engine API, newPayload, forkchoiceUpdated)
- Finding error patterns across multiple nodes
- Investigating network/gossip issues
- Checking validator performance issues (missed duties, attestation errors)

## Quick Start

1. Read `references/loki-queries.md` — contains all LogQL queries organized by use case
2. Use `curl` with the Grafana Loki proxy to run queries
3. Parse results with `jq` for readable output

## Connection Info

- **Grafana:** `https://grafana-lodestar.chainsafe.io`
- **Loki datasource ID:** 4
- **API endpoint:** `GET /api/datasources/proxy/4/loki/api/v1/query_range`
- **Auth:** Bearer token (same Grafana service account as Prometheus)

## Query Patterns

```bash
# Basic log query
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "$GRAFANA_URL/api/datasources/proxy/4/loki/api/v1/query_range" \
  --data-urlencode 'query={instance="<INSTANCE>",job="<JOB>"} |~ "<PATTERN>"' \
  --data-urlencode "start=$(date -d '<TIME_AGO>' +%s)" \
  --data-urlencode "end=$(date +%s)" \
  --data-urlencode "limit=<N>" \
  --data-urlencode "direction=backward" | jq -r '.data.result[].values[][1]'
```

### Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `query` | LogQL query string | `{instance="unstable-super"} \|~ "error"` |
| `start` | Unix timestamp (start of range) | `$(date -d '6 hours ago' +%s)` |
| `end` | Unix timestamp (end of range) | `$(date +%s)` |
| `limit` | Max log lines to return | `50` |
| `direction` | `forward` (oldest first) or `backward` (newest first) | `backward` |

## Label Schema

### Jobs (log sources)

| Job | Description | Key instances |
|-----|-------------|---------------|
| `beacon` | Lodestar CL beacon node | `{group}-{type}` e.g. `unstable-super` |
| `execution` | EL client (Geth, Nethermind, etc.) | Same pattern, may differ |
| `validator` | Lodestar validator client | Per-node |
| `checkpointz` | Checkpoint sync server | |
| `cl_bootnode` | CL bootnode | |
| `commit-boost` | MEV commit-boost | |
| `validator-ejector` | Validator ejector service | |
| `validator-monitor` | Validator monitoring | |

### Common Labels

| Label | Values | Notes |
|-------|--------|-------|
| `instance` | `unstable-super`, `beta-sas`, etc. | Primary node identifier |
| `group` | `unstable`, `beta`, `stable`, `feat1`–`feat4`, `chiado`, `gnosis`, etc. | Node group |
| `job` | See above | Log source type |
| `network` | `holesky`, `mainnet`, `gnosis`, `chiado` | Network |
| `container` | `beacon`, `execution`, etc. | Docker container |
| `logstream` | `stdout`, `stderr` | Log stream |

### Instance Naming Convention

- **Testnet:** `{group}-{type}` → `unstable-super`, `beta-sas`, `stable-semi`
- **Mainnet:** `{group}-mainnet-{type}` → `unstable-mainnet-super`
- **Node types:** `solo` (4-8 custody), `semi` (64), `super` (128), `sas` (128+validator+EL), `arm64`

## LogQL Syntax Reference

### Stream Selectors
```logql
{instance="unstable-super"}                    # exact match
{instance=~"unstable-.*"}                      # regex match
{group="unstable",job="beacon"}                # multiple labels
{instance!="unstable-solo"}                    # negative match
```

### Line Filters
```logql
|= "error"                                     # contains (case-sensitive)
|~ "(?i)error"                                 # regex (case-insensitive)
!= "debug"                                     # does not contain
!~ "verbose|debug"                             # regex exclusion
```

### Pipeline Stages
```logql
| line_format "{{.instance}}: {{__line__}}"    # format output
| json                                          # parse JSON logs
| logfmt                                        # parse logfmt
| label_format level=`{{ToUpper .level}}`      # transform labels
```

### Metric Queries (Log-based metrics)
```logql
# Count errors per minute
count_over_time({instance="unstable-super"} |= "error" [5m])

# Rate of specific events
rate({instance="unstable-super"} |~ "BLOCK_ERROR" [1h])
```

## Investigation Playbook

### 1. Node Crash Investigation

```bash
# Step 1: Check restart history via Prometheus
# (See release-metrics skill for process_start_time_seconds)

# Step 2: Find fatal/exit messages
{instance="<NODE>"} |~ "(?i)(fatal|exit|kill|SIGTERM|SIGKILL|OOM|heap out|JavaScript heap|Allocation failed)"

# Step 3: Get last logs before a specific restart time
{instance="<NODE>"} | direction=backward
# Set end= to the restart timestamp, limit=50

# Step 4: Check for warn/error level logs
{instance="<NODE>",job="beacon"} |~ "warn |error "

# Step 5: Check EL errors if block processing issues
{instance="<NODE>",job="execution"} |~ "(?i)(INVALID|rejected|error|failed)"

# Step 6: Check CL↔EL engine API communication
{instance="<NODE>",job="beacon"} |~ "(?i)(engine|newPayload|forkchoiceUpdate|EXECUTION_ERROR)"
```

### 2. Sync Issue Investigation

```bash
# Finalized sync errors
{instance="<NODE>"} |~ "Batch process error|Batch download error|SyncChain Error"

# Sync progress
{instance="<NODE>"} |~ "Sync peer joined|sync.*startEpoch|targetSlot"

# EL sync status
{instance="<NODE>"} |~ "Execution client is syncing|execution.*SYNCED|SYNCING"

# Block import failures
{instance="<NODE>"} |~ "BLOCK_ERROR|Block error|Block verification"
```

### 3. Network Issue Investigation

```bash
# Req/resp errors
{instance="<NODE>"} |~ "Req  error|Resp error|REQUEST_ERROR"

# Peer connection issues
{instance="<NODE>"} |~ "DIAL_ERROR|ECONNREFUSED|connection.*close|unexpected end"

# Gossip issues
{instance="<NODE>"} |~ "gossip.*error|gossip.*dropped|gossip.*invalid"
```

### 4. Validator Performance Investigation

```bash
# Missed duties
{instance="<NODE>",job="validator"} |~ "(?i)(miss|skip|late|timeout)"

# Attestation issues
{instance="<NODE>"} |~ "attestation.*error|attestation.*fail"

# Block proposal issues
{instance="<NODE>"} |~ "proposal.*error|propose.*fail|produceBlock"
```

### 5. Cross-Node Comparison

```bash
# Compare errors across a group
{group="unstable",job="execution"} |~ "(?i)(error|INVALID)" | line_format "{{.instance}}: {{__line__}}"

# Find which nodes have a specific error
{group="unstable"} |~ "SPECIFIC_ERROR_MESSAGE" | line_format "{{.instance}}"
```

## Tips

- **Direction matters:** Use `backward` to see the most recent logs first (default for investigation)
- **Time ranges:** Keep queries narrow (30min–6h) for fast results; Loki can be slow on wide ranges
- **Limit wisely:** Start with `limit=30-50`; increase only if needed
- **Label filtering first:** Always filter by `instance` and/or `group` before applying line filters
- **EL instance names may differ:** Some EL instances use host-level names (e.g., `hetzner-gnosis-prod-bn-rescue-0`), not the same as CL instance names. Use `group` label to match.
- **No EL logs?** Not all nodes have EL log collection configured. Check available instances first.
- **ANSI codes:** Loki logs contain ANSI color codes (e.g., `[36m`, `[39m`). These are cosmetic; ignore them.
- **Lodestar log levels in brackets:** `[info]`, `[debug]`, `[verbose]`, `[warn]`, `[error]` — filter with `|~ "warn |error "` (trailing space important to avoid false matches).

## References

- `references/loki-queries.md` — Ready-to-use LogQL queries for common scenarios
- Related: `../release-metrics/` — Prometheus metrics (complements log analysis)
