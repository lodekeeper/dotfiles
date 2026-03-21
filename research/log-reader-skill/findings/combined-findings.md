# Log Analysis Tools & Patterns: Web Survey
**Date:** 2026-03-21  
**Purpose:** Research for log-reader-skill design — tools and patterns for AI-assisted blockchain node log analysis

---

## 1. Existing Log Analysis Tools for Ethereum Nodes

### 1.1 Native Client Log Formats

Ethereum clients emit logs in two main formats: **human-readable text** (default) and **JSON** (opt-in). JSON is strongly preferred for any automated processing.

#### Geth (Go Ethereum) — EL
- **Text format:** `MESSAGE_TYPE [MONTH-DAY][TIME] MESSAGE VALUE`
- **JSON format:** Enable with `--log.json`
- **Verbosity levels:** `0=silent, 1=error, 2=warn, 3=info, 4=debug, 5=detail` (default: 3)
- **Per-module verbosity:** `--vmodule <pattern>=<level>` (very useful for targeted debugging)
- **Sample JSON entry:**
  ```json
  {"blocks":1,"elapsed":"294.7µs","lvl":"info","msg":"Unindexed transactions","t":"2022-12-25T07:51:48Z","tail":5846871,"txs":19}
  ```
- **Shutdown log pattern:**
  ```json
  {"lvl":"info","msg":"Got interrupt, shutting down...","t":"2022-12-25T07:52:47Z"}
  ```

#### Erigon — EL
- **JSON format:** `--log.console.json --log.console.verbosity info`
- **Separate file logging:** `--log.dir.path` with `--log.dir.verbosity dbug` (more verbose on disk)
- **Sample JSON entry:**
  ```json
  {"eth66":"75","eth67":"33","lvl":"info","msg":"[p2p] GoodPeers","t":"2023-01-09T11:16:47Z"}
  ```

#### Besu — EL (Java/log4j)
- **No simple JSON flag** — requires custom log4j config or Logstash parsing
- **Default text format:** `2022-12-23 14:26:36.900+00:00 | vert.x-worker-thread-0 | INFO | EngineNewPayload | Imported #8,186,943`
- **Challenge:** Java stack traces produce multiline output that breaks naive line-by-line parsing

#### Nethermind — EL
- **No native JSON** — parse via Logstash or similar
- **Multiline** Java-style stack traces

#### Lodestar — CL (TypeScript/Winston)
- **Library:** Winston with custom formatters
- **Log levels:** `error, warn, info, verbose, debug, trace`
- **Two formats:** `human` (default, colorized) and `json`
- **Human format:**
  ```
  Mar-21 20:00:01.123 [chain]              info: Imported block slot=1234567 parent=0xabc... validatorsCount=500000
  ```
- **JSON format:**
  ```json
  {"level":"info","message":"Imported block","module":"chain","timestamp":"2026-03-21T20:00:01.123Z","context":{"slot":1234567,"parent":"0xabc...","validatorsCount":500000}}
  ```
- **Timestamp modes:**
  - `DateRegular`: `MMM-DD HH:mm:ss.SSS`
  - `EpochSlot`: shows current epoch/slot relative to genesis (very useful for CL debugging)
  - `Hidden`: suppressed
- **Per-module log levels:** `--logLevelModule chain=debug,sync=verbose`
- **File rotation:** Daily rotate supported via `--logFileDailyRotate`

#### Lighthouse — CL (Rust/slog)
- **Log format:** structured key=value pairs
- **Example debug log:**
  ```
  DEBG Delayed head block, set_as_head_time_ms: 37, imported_time_ms: 1824, attestable_delay_ms: 3660, 
       slot: 11429888, proposer_index: 778696, block_root: 0x34cc..., service: beacon, 
       module: beacon_chain::canonical_head:1440
  ```
- **Debug logs** go to `$datadir/beacon/logs` separately from console
- **Real-world error log pattern:**
  ```
  ERRO Failure verifying attestation for gossip, attestation_slot: 7342319, committee_index: 12, 
       error: UnknownHeadBlock { beacon_block_root: 0x847d... }
  ```

### 1.2 Observability Infrastructure (Standard Stack)

Teams running Ethereum nodes typically use this stack:

| Layer | Tool | Role |
|-------|------|------|
| Collection | Docker logging driver / Filebeat / Promtail | Scrape stdout/files |
| Storage | **Grafana Loki** (preferred) or Elasticsearch | Store & index |
| Query | **LogQL** (Loki) or KQL (Elastic) | Filter/search |
| Visualization | Grafana dashboards | Panels + alerts |
| Metrics complement | Prometheus + ethereum-metrics-exporter | Numeric metrics |

**Why Loki over Elastic for node operators:** Loki is label-based (lightweight index), stores raw log lines, lower ops burden. Elastic is heavier but more powerful for full-text search and analytics.

### 1.3 LogQL Patterns for Beacon Node Analysis

Loki's LogQL allows building a "schema at query time":

```logql
# Filter by client and level
{job="beacon-node", client="lodestar"} |= "error"

# Extract JSON fields and filter by slot range
{job="beacon-node"} | json | slot > 1000000 | slot < 1100000

# Rate of errors over time
rate({job="beacon-node"} |= "error" [5m])

# Find peer drops
{job="beacon-node"} |= "peers" | json | peers < 10
```

### 1.4 Ethpandaops Tooling

**ethereum-metrics-exporter** (ethpandaops): Exposes EL/CL metrics via JSON-RPC calls to Prometheus, bridging logs/metrics. Key metrics include peer count, sync status, head slot/block.

**assertoor**: Test orchestration framework for devnets that checks node behavior via API assertions — *not* log-based but complements log analysis for devnet debugging.

---

## 2. AI-Assisted Log Analysis

### 2.1 General LLM Log Analysis Approaches

The industry has converged on a few practical patterns (per Splunk, IBM, LogAI research):

**Core LLM capabilities for logs:**
1. **Natural language querying** — "show me all database errors from the last hour"
2. **Anomaly detection** — identify unusual sequences or outliers
3. **Root cause analysis (RCA)** — correlate errors and infer probable causes
4. **Summarization** — compress large log volumes into readable insights
5. **Structured extraction** — convert unstructured logs to JSON without regex

**Example prompt: Convert logs to JSON**
```python
prompt = f"""
Parse the following log entries into JSON with keys: timestamp, level, message, and module.
Return valid JSON only.

{logs[:4000]}
"""
```

Output:
```json
[
  {"timestamp":"2025-11-11T08:23:12Z","level":"ERROR","message":"Database connection timeout after 30s","module":"db_connection"},
  {"timestamp":"2025-11-11T08:23:14Z","level":"WARN","message":"Retrying query execution...","module":"query_executor"}
]
```

### 2.2 Open-Source Tools

#### LogAI (Salesforce, Python)
- **GitHub:** https://github.com/salesforce/logai
- **Capabilities:** Log clustering, summarization, anomaly detection
- **Pipeline:** parse → vectorize → cluster → detect anomalies
- **Supports:** Multiple log formats, multiple ML backends (BERT, isolation forest, etc.)
- **GUI portal** with interactive clustering (k-means, DBSCAN)

#### llm-log-analyzer (Stratosphere IPS, Python)
- **GitHub:** https://github.com/stratosphereips/llm-log-analyzer
- **Approach:** Simple — reads file + YAML prompt config → sends to local Ollama LLM
- **Use case:** Security log analysis (auth.log, syslog)
- **Usage:** `python log-analyzer.py -f auth.log -c prompt.yaml`
- **Good model:** Works with local models (Ollama), no cloud dependency

#### LogSentinelAI
- **GitHub:** https://github.com/call518/LogSentinelAI
- **Approach:** Declarative, chunk-based analysis → ES/Kibana output
- **Output metadata:** Includes token counts, chunk timestamps, processing mode
- **Sample output:**
  ```json
  {"total_events":8,"auth_failures":8,"@token_size_input":1834,"@token_size_output":618,"@log_type":"linux_system"}
  ```

#### LogPAI (Microsoft Research / Academic ecosystem)
- **Website:** https://logpai.com/
- **Tools:** `logparser` (16 parsing algorithms), `Drain3` (streaming)
- **Key insight:** Log parsing is a prerequisite for any AI analysis

---

## 3. Structured Log Processing Patterns

### 3.1 The Standard Pipeline

```
Raw logs → Collection → Parsing → Storage → Analysis → Action
```

**Best practices from the field:**
1. **JSON-first**: Use JSON-formatted logs across all services. Eliminates brittle regex.
2. **Correlation IDs**: Propagate trace/correlation IDs through log entries (critical for distributed systems). In CL context: `slot` and `epoch` serve this role.
3. **Consistent field naming**: Document a shared schema — e.g., `lvl` vs `level` vs `severity` causes tooling headaches.
4. **Log rotation**: Daily rotate with max retention (e.g., 14 days) prevents disk exhaustion.
5. **Log level discipline:**
   - `ERROR` → something broke, needs attention
   - `WARN` → degraded but still functioning
   - `INFO` → normal operational events
   - `DEBUG` → developer context, not production by default
   - `VERBOSE/TRACE` → very granular, only for specific debugging sessions

### 3.2 Handling Verbose Debug Logs

For blockchain nodes running at `debug` verbosity, log volume can be enormous (GBs/hour). Practical patterns:

**Pre-filter before storage:**
```bash
# Only store warn+ to Loki, keep full debug locally
lodestar beacon --logLevel debug | \
  tee /var/log/lodestar/full.log | \
  grep -E '"level":"(error|warn)"' | \
  promtail --stdin
```

**Per-module verbosity (Lodestar):**
```bash
--logLevelModule chain=debug,sync=verbose,network=info
# Debug only what you're investigating, keep rest quiet
```

**Geth per-module:**
```bash
--vmodule eth/handler.go=4,p2p/*.go=3
```

### 3.3 Drain Algorithm — Key Building Block

The **Drain** algorithm (He et al., 2017) is the de facto standard for log template extraction:

- **How it works:** Fixed-depth parse tree; groups log messages into templates by matching token positions
- **Output:** `"Unindexed transactions tail=<*> txs=<*> blocks=<*>"` → template with variable slots
- **Libraries:**
  - Python: `drain3` (logpai/Drain3) — production-grade, streaming
  - Go: `go-drain3` (Jaeyo/go-drain3) or `faceair/drain`
- **Use case for our skill:** Pre-process Lodestar/Geth logs to extract unique message templates, then summarize template frequencies instead of raw lines — massive token reduction.

**Drain3 example:**
```python
from drain3 import TemplateMiner

miner = TemplateMiner()
for line in log_lines:
    result = miner.add_log_message(line)
    # result.cluster_template = "Imported block slot=<*> validatorsCount=<*>"
```

---

## 4. Log Summarization Techniques

### 4.1 Frequency-Based Summarization (Classical)

Before LLMs, the go-to approach:

```bash
# Top error messages (deduped by message text)
grep '"level":"error"' lodestar.json.log | jq '.message' | sort | uniq -c | sort -rn | head -20

# Slot-range activity summary
grep '"level":"warn"' lodestar.json.log | jq '{slot: .context.slot, msg: .message}' | sort -k2 -t: | uniq -c

# Error rate per minute
grep '"level":"error"' lodestar.json.log | jq '.timestamp[:16]' | sort | uniq -c
```

**Useful Linux tools for log summarization:**
- `awk` — field extraction and aggregation
- `uniq -c` — count consecutive duplicate lines
- `sort | uniq -c | sort -rn` — frequency distribution
- `jq` — JSON parsing and projection

### 4.2 LLM Summarization Strategies

Three main approaches for long log files:

#### Strategy 1: Stuff (Fits in Context)
Simple — dump all logs into context. Works for:
- Small time windows (< 30 min at INFO level)
- Pre-filtered logs (only errors)
- Claude/GPT-4 with 200k context
```python
response = llm.complete(f"Analyze these beacon node logs:\n{logs}")
```

#### Strategy 2: Map-Reduce (Large Files)
```
[chunk1] → summary1 ─┐
[chunk2] → summary2 ─┤→ final synthesis
[chunk3] → summary3 ─┘
```

**LangChain MapReduce example:**
```python
from langchain.chains.summarize import load_summarize_chain
chain = load_summarize_chain(llm, chain_type="map_reduce", 
                              map_prompt=map_prompt, combine_prompt=combine_prompt)
result = chain({"input_documents": split_docs})
```

**Key insight for logs:** Map step should extract key events per chunk (errors, state changes, anomalies). Reduce step synthesizes timeline and root cause.

#### Strategy 3: Iterative Refinement
```
[chunk1] → summary ─┐
                     ├→ [chunk2] → updated summary ─┐
                                                     ├→ ... → final
```
Better for causal chain analysis (each chunk builds on previous context). Slower but preserves temporal ordering.

#### Strategy 4: Semantic Clustering + Representative Sampling
1. Embed each log line with a lightweight model (e.g., BERT or `all-MiniLM`)
2. Cluster into N groups (k-means or DBSCAN)
3. Pick representative samples from each cluster
4. Send only representatives to LLM

**This is what LogLLM and LLMLogAnalyzer do** — dramatically reduces token usage.

### 4.3 The Lost-in-the-Middle Problem

Key limitation: LLMs tend to **miss information buried in the middle** of long contexts. For log analysis, this means:
- Put the most important context at the **beginning** (system state, recent errors)
- Put the query/instructions at the **end** (or both ends — repeat key framing)
- Don't just dump 100k tokens of logs and hope for the best

---

## 5. Token-Budget Log Ingestion Patterns

### 5.1 Pre-Filtering Pipeline (Most Practical)

```
Raw logs (100k lines)
    → Level filter (keep warn/error) → ~5k lines
    → Time window filter (last N slots) → ~1k lines  
    → Field projection (drop redundant fields) → ~500 tokens
    → Dedup (unique messages) → ~200 tokens
    → LLM analysis → result
```

**For Lodestar specifically:**
```bash
# Extract just errors + warnings from last 32 slots
cat lodestar.json.log | jq -c 'select(.level == "error" or .level == "warn")' \
  | jq -c 'select(.context.slot > (env.HEAD_SLOT | tonumber - 32))' \
  | jq '{level, message, slot: .context.slot, epoch: .context.epoch}'
```

### 5.2 Chunking Strategies

| Strategy | Chunk Size | Best For |
|----------|-----------|---------|
| Fixed token chunks | 2000-4000 tokens | Simple map-reduce |
| Time-window chunks | 1 epoch / 10 min | Temporal analysis |
| Log-level chunks | All errors as one chunk | RCA focus |
| Template-based | 1 chunk per unique template | Dedup-heavy logs |

**Rule of thumb from practice:** 512-1024 token chunks for map step, 4000-8000 token synthesis window.

### 5.3 Token Estimation for Ethereum Logs

Rough estimates for planning token budgets:

| Log type | Volume | Tokens/line | Lines/hour |
|----------|--------|-------------|-----------|
| Lodestar INFO JSON | ~200 bytes/line | ~50 tokens | ~1800/hr (1 per 2s) |
| Lodestar DEBUG JSON | ~300 bytes/line | ~75 tokens | ~100k+/hr |
| Geth INFO JSON | ~150 bytes/line | ~40 tokens | ~3600/hr |
| Beacon slot notifications | ~500 bytes/line | ~125 tokens | ~450/hr |

**For a 1-hour debug session at INFO:** ~90k tokens — fits in 200k context with room for analysis  
**For a 1-hour debug session at DEBUG:** ~7.5M tokens — impossible to fit; must pre-filter

### 5.4 The Drain Pre-Processing Pattern

Most token-efficient approach for large logs:

```
Step 1: Run Drain on raw logs
    → Extract N unique templates (e.g., 50 templates from 10k lines)
    → Track frequency per template
    → Track first/last seen per template

Step 2: Feed LLM only the template report:
    Template #1 (seen 8,432 times): "Imported block slot=<*> validatorsCount=<*>"
    Template #2 (seen 127 times): "Slow block processing slot=<*> elapsed=<*>"
    Template #3 (seen 3 times): "Failed to produce block slot=<*> error=<*>"
    ... (N=50 templates, ~5k tokens total)

Step 3: LLM identifies anomalous templates, requests raw lines for specific ones
    → "Show me all lines matching Template #3"
    → Fetch from storage, feed back 3 raw lines (~300 tokens)
```

**This is essentially what LogSage (CI/CD failure detection) does:**
- Drain deduplication in offline phase
- Key log filtering + token pruning in online phase
- LLM only sees "critical log blocks"

### 5.5 Practical Splunk/Loki Pre-Processing Recommendations

Before sending to LLM, always:

1. **Level filter:** Drop INFO/DEBUG unless specifically investigating those
2. **Time filter:** Bound to relevant window (e.g., ±5 minutes around incident)
3. **Field projection:** Keep only: `timestamp, level, message, module, slot, epoch` (drop large blobs)
4. **Dedup:** Remove exact duplicate lines (`sort | uniq`)
5. **Template compression:** Group by message template, show count + examples
6. **Error prioritization:** Put errors first in the context

---

## 6. Summary: Recommended Approach for a Log-Reader Skill

Based on this survey, the most practical architecture for an AI log-reader skill for Lodestar:

### Architecture

```
┌─────────────────────────────────────────────┐
│  INPUT: Loki query / log file / journald    │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │  Pre-processor     │
         │  - Level filter    │
         │  - Time window     │
         │  - JSON parse      │
         │  - Field project   │
         └─────────┬─────────┘
                   │
         ┌─────────▼─────────┐
         │  Template miner    │  ← Drain3 or simple groupby(message)
         │  - Group by msg    │
         │  - Count freqs     │
         │  - Pick examples   │
         └─────────┬─────────┘
                   │
         ┌─────────▼─────────┐
         │  Token budget mgr  │
         │  - Estimate tokens │
         │  - Truncate/sample │
         │  - Priority sort   │
         └─────────┬─────────┘
                   │
         ┌─────────▼─────────┐
         │  LLM Analysis      │
         │  - RCA prompt      │
         │  - Anomaly prompt  │
         │  - Summary prompt  │
         └─────────┬─────────┘
                   │
         ┌─────────▼─────────┐
         │  Structured Output │
         │  - Key issues list │
         │  - Timeline        │
         │  - Action items    │
         └─────────────────────┘
```

### Key Design Choices

1. **Always use JSON log format** — configure Lodestar with `--logFormat json`
2. **Loki is the natural source** — we already have Loki access; use LogQL for pre-filtering
3. **Drain or simple groupby** — for Lodestar logs, groupby(message) is often enough since messages are already templated
4. **Two-pass analysis:**
   - Pass 1: Template report → identify anomalous patterns
   - Pass 2: Raw lines for flagged templates → deep analysis
5. **Token guard:** Always estimate token count before sending; truncate with priority ordering (errors > warnings > info)
6. **Epoch/slot context:** Include genesis time + current head slot so LLM can reason about timing

### Tools to Integrate

| Tool | Why |
|------|-----|
| `jq` | JSON parsing/filtering in shell |
| `drain3` (Python) or simple message groupby | Template dedup |
| Loki API (`/loki/api/v1/query_range`) | Primary log source |
| `tiktoken` or similar | Token budget estimation |
| Claude / GPT-4 | LLM analysis |

---

## 7. References

- [Geth Logs Documentation](https://geth.ethereum.org/docs/fundamentals/logs)
- [SlingNode: Ethereum Execution Client Logging](https://slingnode.com/2023/01/09/ethereum-execution-client-logging/)
- [Splunk: How to Use LLMs for Log File Analysis](https://www.splunk.com/en_us/blog/learn/log-file-analysis-llms.html)
- [Salesforce LogAI](https://github.com/salesforce/logai)
- [logpai/Drain3](https://github.com/logpai/Drain3)
- [stratosphereips/llm-log-analyzer](https://github.com/stratosphereips/llm-log-analyzer)
- [LogSage: LLM-Based CI/CD Failure Detection](https://arxiv.org/html/2506.03691v2)
- [Grafana Loki LogQL](https://grafana.com/docs/loki/latest/query/log_queries/)
- [Lighthouse FAQ: Debug Logs](https://lighthouse-book.sigmaprime.io/faq.html)
- Lodestar source: `packages/logger/src/utils/format.ts` (Winston + JSON/human formats)
# Log Format Catalog — Lodestar & EL Clients

**Date:** 2026-03-21  
**Author:** Subagent (log-research-format-catalog)  
**Purpose:** Catalog Lodestar beacon node log formats, module names, verbosity levels, structured fields, and EL client formats for the log-reader skill design.

---

## 1. Logger Implementation

Lodestar uses **Winston** as its logging backend (`packages/logger/src/winston.ts`). The logger is a custom `WinstonLogger` class wrapping Winston with per-module level filtering via a custom `ConsoleDynamicLevel` transport.

### Key architecture points

- `WinstonLogger` is the base class; `WinstonLoggerNode` extends it for CLI (node) usage.
- Child loggers are created with `.child({module: "subname"})`, which **concatenates** module names: `parent/child` (e.g. `network/peers`).
- **Per-module log level filtering** is supported via `--logLevelModule chain=debug,network=debug`. This uses a `Map<module, level>` checked in the custom transport's `_write` before emitting.
- Log level is controlled **per transport**, not globally — allows console at `info` while file at `debug`.
- Default log level on startup: `info` (console), `debug` (log file).

---

## 2. Log Formats

Two formats are supported: **human** (default) and **json** (via `--logFormat json`).

### 2a. Human-Readable Format (default)

```
MMM-DD HH:mm:ss.SSS [MODULE]              LEVEL: message key1=value1, key2=value2
```

**Full example:**
```
Mar-21 14:23:11.042 [chain]                 info: Checkpoint finalized epoch=123456, root=0x1234…5678
Mar-21 14:23:11.042 [network]              debug: Discovered peer via discv5 peer=16…a3b4f2, status=connected, cgc=8
Mar-21 14:23:11.042 [network]              debug: Req  dialing peer method=beacon_blocks_by_range, version=1, encoding=ssz_snappy, peer=16…a3b4f2, requestId=42
Mar-21 14:23:11.042 [chain]                warn: Head state not available, triggering regen
Mar-21 14:23:11.042 [chain]                warn: foo bar meta=data, code=SAMPLE_ERROR, data=foo=bar
                                                  ^stack trace on next line for errors^
```

**Template function (from source):**
```
{timestamp} [{module}] {level (right-padded to ~30)}: {message} {context_kv_pairs} [- error_message]
```

- **Timestamp:** `MMM-DD HH:mm:ss.SSS` by default (e.g. `Mar-21 14:23:11.042`)  
- **Timestamp alt — EpochSlot mode:** `Eph EPOCH/SLOT_INDEX SLOT_SECONDS` (e.g. `Eph 312/3 5.123`) — enabled with `--logFormatGenesisTime`  
- **Module field:** padded so level column aligns at character 30  
- **Level field:** right-padded within the padding zone  
- **Context:** appended as `key=value, key=value` pairs  
- **Errors:** appended as ` - error_message\nstack` (plain Error) or `, key=value` (LodestarError with code metadata)  
- **Colors:** ANSI color codes in console output (warn=yellow, error=red, etc.)  

### 2b. JSON Format (`--logFormat json`)

```json
{"timestamp":"2026-03-21T14:23:11.042Z","level":"info","message":"Checkpoint finalized","module":"chain","context":{"epoch":123456,"root":"0x1234…5678"}}
{"timestamp":"2026-03-21T14:23:11.042Z","level":"warn","message":"foo bar","module":"test","context":{"meta":"data"},"error":{"code":"SAMPLE_ERROR","data":{"foo":"bar"},"stack":"..."}}
```

**JSON fields:**
- `timestamp` — ISO 8601
- `level` — `error|warn|info|verbose|debug|trace`
- `message` — string
- `module` — module/context name (may be empty string)
- `context` — object with structured key-value pairs (may be absent)
- `error` — object with `message` + `stack` (plain Error) or `code` + metadata (LodestarError)

**BigInt values** are serialized to strings in JSON format.  
**Uint8Array values** are serialized as hex strings (`0x...`).

---

## 3. Log Levels

Levels in priority order (lowest number = highest priority):

| Level   | Numeric | Description |
|---------|---------|-------------|
| `error` | 0       | Fatal/critical failures requiring attention |
| `warn`  | 1       | Non-fatal issues, degraded operation |
| `info`  | 2       | Normal operational status |
| `verbose` | 3    | Detailed lifecycle events (entry/exit of operations) |
| `debug` | 4       | High-frequency internal state, per-message events |
| `trace` | 5       | Exists in interface, **zero actual callsites** in codebase |

### Volume counts (production code, non-test files):

| Level   | Call count |
|---------|-----------|
| error   | 126 |
| warn    | 70  |
| info    | 142 |
| verbose | 157 |
| debug   | 218 |
| trace   | 0   |

**Volume ratio at debug vs info:** roughly **2.5× more call sites** at debug/verbose than info/warn. In practice, debug is far more voluminous because many debug callsites fire **per slot, per peer, per message** (gossip validators, reqresp, peer discovery heartbeat, sync batches).

### By package:

| Package | Total log callsites |
|---------|-------------------|
| beacon-node | 461 |
| validator | 97 |
| cli | 89 |
| prover | 49 |
| reqresp | 9 |
| light-client | 7 |
| db | 1 |

### Within beacon-node:

| Sub-package | Callsites |
|-------------|-----------|
| chain | 178 |
| network | 125 |
| sync | 78 |
| api | 51 |
| execution | 11 |
| node | 10 |
| monitoring | 5 |
| metrics | 3 |

---

## 4. Module Names

Top-level modules (from `LoggerModule` enum in `packages/beacon-node/src/node/nodejs.ts`):

| Module name | Description |
|------------|-------------|
| `api` | REST API server |
| `backfill` | Backfill sync |
| `chain` | Fork choice, state transitions, block import |
| `execution` | Engine API / EL connection |
| `metrics` | Prometheus metrics |
| `monitoring` | Remote monitoring service |
| `network` | libp2p, gossipsub, peer manager |
| `vmon` | Validator monitor |
| `rest` | REST transport layer |
| `sync` | Range sync, unknown block sync |

Child loggers append `/subname`:
- `network` → internal classes may use `network/peers`, `network/gossip`, etc. (child module naming)
- `chain/blocks`, `chain/regen`, etc. (implied by code structure, some use the parent logger directly)

**No separate `reqresp` module at top level** — reqresp logs go to `network` (it receives the parent logger).

**Validator client** (`packages/validator/`) uses its own logger instance, not a child of beacon-node's logger.

---

## 5. Structured Data in Logs

Logs use rich structured context objects. Key field patterns by module:

### Block/chain fields:
```js
{slot, blockRoot, timeCreatedSec}                    // LogMetaBasic
{slot, blockRoot, timeCreatedSec, expectedBlobs, receivedBlobs}  // LogMetaBlobs (EIP-4844)
{slot, blockRoot, timeCreatedSec, expectedColumns, receivedColumns}  // LogMetaColumns (PeerDAS)
```

### Network/peer fields:
```js
{peer: "16…a3b4f2"}   // prettyPrintPeerId: first 2 + last 6 chars
{peerId: "16Uiu2..."}  // full peer ID sometimes
{status, cgc: 8}       // connection status, custody group count
{addresses: [...]}
```

### ReqResp fields:
```js
{method: "beacon_blocks_by_range", version: 1, encoding: "ssz_snappy", 
 client: "lighthouse", peer: "16…a3b4f2", requestId: 42}
```

### Sync fields:
```js
{id: "SyncChainId", localFinalizedEpoch, targetSlot, peer}
{epoch: startEpoch, ...batch.getMetadata()}
```

### Execution fields:
```js
{oldState: "syncing", newState: "synced"}
{urls: "http://localhost:8551"}
```

### Block root formatting:
- `prettyBytes()`: `0x1234…5678` — 4 hex chars prefix + ellipsis + 4 chars suffix  
- `prettyBytesShort()`: `0x1234…` — prefix only  
- `truncBytes()`: `0x123456789abc` — 12-char hex (6 bytes, no ellipsis)

### Peer ID formatting:
- `prettyPrintPeerId()`: `16…a3b4f2` — first 2 + last 6 chars of the base58-encoded peer ID

---

## 6. Common Error and Warning Messages

### Most common errors (from `logger.error()` callsites):
- `"Error starting REST api server"`
- `"Gossip validations failed while publishing the block"`
- `"Consensus checks failed while publishing the block"`
- `"Error pushing notifyForkchoiceUpdate()"` 
- `"Error on head state regen"`
- `"Builder disabled as the check status api failed"`
- `"BlsMultiThreadWorkerPool error"`
- `"Execution client authentication failed. Verify if the JWT secret matches on both clients"`
- `"Network worker thread error"`
- `"PeerDiscovery: discv5 has no boot enr"`
- `"Error on discv5.findNode()"`
- `"Error onDiscovered"`
- `"Error on ReqResp.unregisterProtocol"` / `"Error on ReqResp.registerProtocol"`

### Most common warnings (from `logger.warn()` callsites):
- `"Low peer count"` (when peers ≤ 1)
- `"Execution client is offline"`
- `"Execution client is syncing"`
- `"Engine failed to produce the block within cutoff time"`
- `"Builder failed to produce the block within cutoff time"`
- `"REST API server is exposed, ensure untrusted traffic cannot reach this API"`
- `"Checkpoint sync recommended, please use --help to see checkpoint sync options"`
- `"Proposer duties re-org. This may happen from time to time"`
- `"Multiple block proposers"` 
- `"Node is syncing"` (from validator client)
- `"Primary beacon node is unhealthy"` (from validator)
- `"Skipped slot due to task taking more than one slot to run"` (from validator)
- `"Published data columns to 0 peers, increased risk of reorg"` (PeerDAS)

### Notifier (regular `info` status line):
Every ~half-slot, a status line like:
```
info: Syncing 4d 2h left - 3.42 slots/s - slot: 1234567 - head: (slot -15) 0x1234…5678 - exec: 0x4567… - finalized: 0xabcd…ef12:123450 - peers: 35
```
or when synced:
```
info: Synced - slot: 1234567 - head: 0x1234…5678 - exec: 0x4567… - finalized: 0xabcd…ef12:123450 - peers: 67
```

---

## 7. Debug Log Verbosity — Key Sources

The most verbose modules at debug/verbose level and why:

### Network (125 callsites total, ~84 debug/verbose)
- **Peer discovery** (`network/peers/discover.ts`): fires per discovered ENR, per dial attempt, per discv5 query result
- **PeerManager** heartbeat: fires every ~12s with peer connect/disconnect events, score updates, goodbye messages
- **GossipHandlers** (`network/processor/gossipHandlers.ts`): fires for **every received gossip message** — blocks, blobs, data columns, attestations. At 1-second slots with PeerDAS this can be very high (hundreds of messages/slot)
- **GossipValidatorFn**: fires per message validation result (accept/reject/ignore)

### Sync (78 callsites, ~60 debug/verbose)
- **Range sync** (`sync/range/chain.ts`): per batch download/processing — fires continuously during initial sync
- **Unknown block sync** (`sync/unknownBlock.ts`): 19 debug callsites — per unknown block root download attempt
- **Backfill sync**: per batch

### ReqResp (`packages/reqresp/`): 9 callsites total
- Fires per request/response stream: dial → send → sent → received → done/error
- With many peers, this multiplies quickly

### Chain (178 callsites, but mostly verbose/debug per-block)
- `blocks/` directory: 19 debug callsites — fires per block import (verified signatures, state transition, persisted to DB)
- `stateCache/`: 9 debug callsites — cache hits/misses per slot
- `regen/`: 3 debug callsites

**At debug level during sync:** expect hundreds to thousands of lines per minute. Network gossip alone at mainnet rates can produce 50-200 debug lines per second (attestations, sync committees, blocks, blobs).

---

## 8. Geth (EL Client) Log Format

Geth uses a completely different log format from Lodestar. **Not JSON by default.**

### Default (human-readable, terminal-colored):
```
INFO [10-04|10:20:52.028] Starting Geth on Ethereum mainnet...
INFO [10-04|10:20:52.028] Bumping default cache on mainnet         provided=1024 updated=4096
WARN [10-04|10:20:55.123] Peer count low                           peers=3 threshold=5
DEBUG[10-04|10:20:55.200] Received block from peer                 peer=abcd1234 block=0x... number=21456789
```

**Format:** `LEVEL [MM-DD|HH:MM:SS.mmm] message key=value key=value`

**Geth log levels (verbosity flags):**
- `0` = silent
- `1` = error
- `2` = warn (default behavior)
- `3` = info (default `--verbosity 3`)
- `4` = debug
- `5` = detail

**JSON mode:** Geth supports `--log.json` flag (added ~2023) which outputs:
```json
{"t":"2026-03-21T14:23:11.042+0000","lvl":"info","msg":"Starting Geth on Ethereum mainnet"}
{"t":"2026-03-21T14:23:11.050+0000","lvl":"info","msg":"Bumping default cache","provided":1024,"updated":4096}
```
Fields: `t` (ISO timestamp), `lvl` (level string), `msg` (message), then additional key-value pairs at top level.

**Key differences from Lodestar:**
- Geth level tag is uppercase, uncolored in format string (colors separately)
- Timestamp format `[MM-DD|HH:MM:SS.mmm]` vs Lodestar's `MMM-DD HH:mm:ss.SSS`
- JSON uses `t`/`lvl`/`msg` vs Lodestar's `timestamp`/`level`/`message`
- Geth KV pairs are positional slog key-value pairs, not a nested `context` object
- No module/namespace field in Geth (no child logger pattern)

---

## 9. Per-Module Level Filtering (Lodestar Feature)

Lodestar supports runtime per-module log level overrides:
```bash
lodestar beacon --logLevel info --logLevelModule network=debug,chain=verbose
```

This is critical for targeted debugging — you can increase verbosity for just `network` or `sync` without drowning in chain debug output.

The `ConsoleDynamicLevel` transport checks `info.module` against the module level map on every log call. **Module matching is exact string match** (not prefix). So `network` matches `[network]` but NOT `[network/peers]` if that's how the child was named.

---

## 10. Summary — Log Format Quick Reference

| Property | Value |
|----------|-------|
| Logger backend | Winston |
| Default format | Human-readable (colored) |
| JSON format flag | `--logFormat json` |
| Timestamp (default) | `MMM-DD HH:mm:ss.SSS` |
| Timestamp (epoch mode) | `Eph EPOCH/SLOT SECS` via `--logFormatGenesisTime` |
| Module separator | `/` (e.g. `network/peers`) |
| Context serialization | `key=value, key=value` (human) or `{"context":{...}}` (JSON) |
| Error serialization | ` - message\nstack` (human) or `{"error":{...}}` (JSON) |
| LodestarError | Inline with context: `, code=X, field=Y` |
| Block root format | `0x1234…5678` (8 chars + ellipsis) |
| Peer ID format | `16…a3b4f2` (first 2 + last 6) |
| Default log file level | `debug` |
| Log file rotation | Daily (configurable, default 5 files) |
| Levels (in order) | error, warn, info, verbose, debug, trace |
| trace callsites | 0 (unused) |
| Most verbose module | network (gossip handlers fire per message) |
| EL (Geth) format | `LEVEL [MM-DD|HH:MM:SS.mmm] msg key=val` |
| Geth JSON flag | `--log.json` → `{t, lvl, msg, key: val}` |
# Past Investigation Analysis — Log Reading Patterns

**Date:** 2026-03-21
**Author:** Lodekeeper (subagent: log-research-past-investigations)
**Purpose:** Extract log-access patterns and lessons from real investigations to inform log reader skill design.

---

## Overview

Seven distinct investigations were analyzed, drawn from:
- `memory/2026-03-20.md`, `memory/2026-03-17.md`, `memory/2026-03-14.md`
- `notes/memory-leak-8969-feat1-super-2026-03-10.md`
- `notes/epbs-devnet-0/TRACKER.md` and `RESEARCH.md`
- `notes/epbs-state-restart/TRACKER.md`
- `notes/epbs-withdrawals-regression/TRACKER.md`
- `notes/epbs-envelope-reqresp-investigation.md`
- `notes/fork-choice-metrics-report.md`
- `notes/v8-ptr-compress-metrics-latest.md`
- `MEMORY.md` (lessons section)

---

## Investigation 1: Sync Aggregate Bug — Bad Participation in Small Devnets (Issue #8294)

**Date:** 2026-03-20
**Type:** Protocol bug (gossip deduplication + pool indexing)

### What was being investigated?
Blocks produced by Lodestar in small devnets (64 validators) consistently showed ~64% sync aggregate participation instead of 100%. Issue traced to two independent gossip-layer bugs.

### How were logs accessed?
1. **Loki** — Queried `lodestar_oppool_sync_contribution_and_proof_pool_get_aggregate_returns_empty_total` metric via Grafana/Loki. Narrowed to `feat2` group (only non-zero instances). Retrieved 9 specific log events from last 7 days.
2. **Prometheus via Grafana** — Queried metric counters to confirm which node groups were affected.
3. **Kurtosis service logs** — Spun up 4-node local devnet (`kurtosis run`), observed `512/512` vs `328/512` participation counts per block in node output.
4. **Python simulation** — Modeled the statistical distribution of both bugs across 10,000 trials before deploying any containers.

### What worked?
- **Loki pattern A/B classification**: Breaking down 9 log events into "empty pool" vs "root mismatch" immediately clarified that two different failure modes existed. Without this classification, the investigation might have chased only one.
- **Prometheus metric drilling**: `lodestar_oppool_sync_*_returns_empty_total` being zero on mainnet/holesky but non-zero on `feat2` immediately scoped the investigation to PeerDAS/Hoodi behavior.
- **Kurtosis rapid reproduction**: 4-node devnet reproduced the exact participation number (64.1% vs issue-reported 63.87%) within one run — confirming the bug was deterministic.
- **Simulation before Kurtosis**: Mathematical modeling correctly predicted participation percentages before any containers were deployed, saving multiple iteration cycles.
- **Context log correlation**: In Loki, reading context logs around the exact problem slot (2643619) revealed `recvToValLatency=23.6s` and `expectedColumns=128`, pointing to PeerDAS backpressure as Pattern A's root cause.

### What failed or was inefficient?
- Initial investigation (Issue #7299) was later redirected (Issue #8294) — two separate issues with similar symptoms. Having a single unified Loki query that distinguished "empty pool" vs "root mismatch" upfront would have saved time.
- The "message pool merge" fix was implemented, Kurtosis-validated, and then stripped — extra work because the fix wasn't needed once both gossip bugs were resolved. Simulation should have been run earlier to predict this outcome.

### Most useful log patterns?
- **Named metric counter with non-zero filter**: `returns_empty_total > 0` immediately identifies affected groups.
- **Context window around error event**: Reading ±5 log lines around the anomalous slot revealed the actual delay chain (PeerDAS column processing backlog → head stuck → missed gossip).
- **Timing correlations**: `recvToValLatency=23.6s` was the single most diagnostic field — it explained the entire Pattern A failure chain.
- **Participation ratio per block**: Simple `bits_set / total_bits` from Kurtosis output was a reliable, observable invariant.

---

## Investigation 2: Memory Leak — feat1-super Network Thread (2026-03-10 to 03-12)

**Date:** 2026-03-10 to 2026-03-12
**Type:** Memory leak (native/V8 heap growth in network worker thread)

### What was being investigated?
`network_worker_nodejs_heap_space_size_used_bytes{space="old"}` showing multi-day linear growth on `feat1-super`. Suspected leak in network worker (separate thread from main beacon process).

### How were logs accessed?
1. **Prometheus via Grafana** — Polled `heap_space_size_used_bytes{space="old"}` every 30 minutes with hourly gate decisions. Custom Python sampler running as background exec session, writing to `tmp/feat1-super-heap/postfix-verify/*.log`.
2. **Heap snapshots via REST API** — `POST /eth/v1/lodestar/write_heapdump?thread=network&dirpath=/tmp` to capture 3 snapshots on the live remote host. Files retrieved via `scp` to `~/.openclaw/workspace/tmp/feat1-super-heap/`.
3. **Local repro** — Ran a synthetic instrumented loop with `AbortSignal.add/removeEventListener` tracking to validate the fix without requiring production traffic.
4. **Retainer chain analysis** — Parsed heap snapshots with custom tooling to extract constructor counts, retainer chains, and edge patterns (`retainers-WeakRef.txt`, `chains-AbortSignal.txt`, etc.)

### What worked?
- **Prometheus slope as primary signal**: Measuring `old` space MB/h slope per hourly gate was the only reliable way to distinguish real leaks from GC noise. Point-in-time values were unreliable.
- **Consecutive-window confirmation gate**: Requiring 2+ consecutive positive-slope windows before escalating prevented false positives from GC pause oscillation. This gate design was critical.
- **Constructor-level heap diff**: Diffing heap snapshots at T0/T+20/T+40/T+60 intervals revealed `WeakRef +17252`, `WeakCell +8664` over 60 minutes as the dominant growth pattern — directly identifying `AbortSignal` composition retention.
- **Retainer chain files**: `chains-WeakRef.txt` showing `sourceSignalRef/composedSignalRef → WeakRef` fanout immediately identified the code path (`@libp2p/utils repeating-task.ts`).
- **A/B local synthetic test**: Before/after listener count comparison (`add=220, remove=0` → `add=216, remove=216`) confirmed the fix works without needing a production deploy.

### What failed or was inefficient?
- **Oscillatory signal**: The metric oscillated significantly, causing multiple false escalation/downgrade cycles over 24+ hours. A single "is it going up?" question took 15+ hourly gate decisions to answer definitively.
- **Session continuity loss**: Monitor sessions stalled mid-run at 16:06 UTC (sampler stopped), requiring manual restart and one-shot samples to close the gate window. Critical monitors should not rely on long-lived exec sessions.
- **Initial req/resp patch was insufficient**: First deployed fix (clearable signals in reqresp) showed partial improvement but didn't stop the leak. Post-deploy monitoring revealed the primary driver was elsewhere. This wasted several hours of deploy + monitor time.
- **Heap snapshot size**: Full-process snapshots were too large for the analyzer. Had to pivot to network-thread-only snapshots. Should default to thread-specific snapshots for thread-local leaks.

### Most useful log patterns?
- **`heap_space_size_used{space="old"}` slope over ≥1h window** — the single most reliable leak indicator.
- **Constructor count diff between snapshots** — `WeakRef`, `WeakCell`, `Listener`, `AbortSignal` count increases point directly at retention pattern.
- **Retainer chain signature** — `sourceSignalRef/composedSignalRef → WeakRef` fanout was unique to this leak and absent in the patched version.
- **Socket count correlation**: `sockets 208 → 21` at restart time confirmed anchor point for post-deploy measurement window.

---

## Investigation 3: EPBS Devnet-0 — Chain Stall After Slot Transition

**Date:** 2026-02-21
**Type:** Interop protocol bug (fork choice stale hash, unknown-parent sync failure)

### What was being investigated?
Lodestar+Lighthouse+Geth Kurtosis devnet stalling after slot ~49: Lodestar produced slot 33, then couldn't import Lighthouse blocks from slot 34 onward. Error: `PARENT_UNKNOWN` with `parentInForkChoice=false`.

### How were logs accessed?
1. **Kurtosis service logs** — `kurtosis service logs <enclave> <service-name> --follow` to stream live logs from individual nodes.
2. **Targeted diagnostic logging** — Added temporary `logger.warn` statements in `validateGossipBlock` and `gossipHandlers.ts` to surface `PARENT_UNKNOWN` diagnostic with specific context.
3. **Geth logs** — Observed `Ignoring beacon update to old head` in Geth execution client logs, which was the first signal pointing to stale FCU hash.
4. **Prometheus metrics** — `unknown_parent` counter increasing confirmed that unknown-parent sync was being triggered (but failing).
5. **Error message parsing** — `UnknownBlockSync processBlock failed slot=34 ... errCode=BLOCK_ERROR_BEACON_CHAIN_ERROR` with nested cause `Parent block hash ... does not match state's latest block hash` gave the exact state inconsistency.

### What worked?
- **EL (Geth) log inspection**: `Ignoring beacon update to old head` in Geth logs was the earliest signal — it appeared before Lodestar logs made the cause obvious.
- **Targeted in-code diagnostics**: Adding `PARENT_UNKNOWN diagnostic` log with `parentInForkChoice=false` in `validateGossipBlock` immediately confirmed the exact failure condition.
- **Nested error cause extraction**: The error chain `BLOCK_ERROR_BEACON_CHAIN_ERROR → Parent block hash ... does not match` was only visible when full error context was printed — truncated errors would have missed it.
- **Kurtosis multi-service observation**: Being able to stream Lodestar + Lighthouse + Geth logs simultaneously allowed correlation across the consensus/execution client boundary.
- **Soak monitor (slot 40→136)**: Running a structured soak with specific error counters confirmed zero occurrences after fix: `ISR=0/0`, `UnknownBlockSync=0/0`.

### What failed or was inefficient?
- **Multiple Kurtosis restarts**: The investigation required 6+ enclave restarts, each with a 5-10 minute rebuild+deploy cycle. More upfront logging would have reduced iterations.
- **Deferred retry workaround**: Added `scheduleDeferredEnvelopeImport` retry worker as a temporary fix, which worked but masked the root cause. A proper event-driven pipeline was needed (designed separately in `epbs-envelope-reqresp-investigation.md`).
- **Resource contention**: 3×LH + 3×LS topology failed three times with `service has Docker resources but not a container` race — had to downgrade to 2×2 lean topology. Kurtosis devnets need headroom.
- **Ephemeral log loss**: After `kurtosis enclave rm`, all container logs are gone. Key findings must be extracted and written during the investigation.

### Most useful log patterns?
- **Execution client (Geth) "Ignoring beacon update to old head"** — earliest cross-layer signal of stale FCU hash.
- **`errCode=BLOCK_ERROR_*`** — Lodestar's structured error codes for gossip block validation failures.
- **`parentInForkChoice=false`** — custom diagnostic that pinpointed the exact failure condition.
- **Nested error chain** — `BLOCK_ERROR_BEACON_CHAIN_ERROR` wrapping the actual state consistency failure.
- **Soak monitor counters** (ISR, UnknownBlockSync, publishBlock errors, payloadId=null) as acceptance criteria.

---

## Investigation 4: feat3 / blst-z Native Memory Leak (2026-03-20)

**Date:** 2026-03-20
**Type:** Native memory leak in Zig NAPI bindings

### What was being investigated?
RSS growing linearly on all feat3 nodes (blst-z PR #248) while V8 heap and external memory stayed flat. Growth rate correlated with BLS workload (custody group count), pointing to missing `napi_adjust_external_memory` calls in Zig NAPI bindings.

### How were logs accessed?
1. **Prometheus via Grafana** — Queried `process_resident_memory_bytes`, `nodejs_heap_size_used_bytes`, and `nodejs_external_memory_bytes` for feat3 vs unstable groups.
2. **Time series comparison** — 12h vs 48h RSS values to compute growth rate per node type.
3. **Metric correlation** — Cross-referenced RSS growth rate with custody group count per node.
4. **Code-level analysis** — Traced the NAPI binding code path (`blst.zig:Signature_ctor`) to identify missing `napi_adjust_external_memory` calls.

### What worked?
- **Three-metric combination (RSS + V8 heap + external memory)**: V8 heap flat while RSS grows linearly immediately ruled out JS-layer leaks and pointed to native allocations.
- **Growth rate per workload group**: Comparing `semi` (64 custody, 42 MB/h) vs `super` (128, 75 MB/h) vs `sas` (validator+128, 223 MB/h) confirmed leak was per-BLS-operation.
- **Baseline comparison (unstable group)**: `unstable-semi` oscillating with no trend was the critical control — it ruled out the application code and pointed to the zig bindings.

### What failed or was inefficient?
- Unstable nodes had restarted ~12h ago vs feat3's 55h uptime, making direct RSS comparisons misleading. Uptime normalization was necessary.
- `unstable-sas` was stalled (sync_status=0) during analysis, making it an invalid comparison target.

### Most useful log patterns?
- **RSS trend over time** (slope, not absolute value).
- **V8 heap flat + RSS growing = native leak** — two-metric pattern is a reliable diagnostic shortcut.
- **Growth rate per workload dimension** — BLS sigs/slot × 192 bytes predicted actual MB/h within noise bounds.

---

## Investigation 5: EPBS State Restart Crash (2026-03-07)

**Date:** 2026-03-07
**Type:** Node crash on restart (`headState does not exist`)

### What was being investigated?
Lodestar crashed on restart in EPBS (Gloas) devnet with `headState does not exist` error. Also: finalized API returning wrong state bytes vs checkpoint-sync endpoint.

### How were logs accessed?
1. **Live devnet logs** — Checkpoint sync + restart cycle on local Kurtosis devnet connected to `checkpoint-sync.epbs-devnet-0.ethpandaops.io`.
2. **API response comparison** — `curl` the finalized state endpoint and compare bytes with checkpoint endpoint response.
3. **Code path tracing** — Read `chain.ts` and `forkChoice/index.ts` to trace anchor state construction logic.

### What worked?
- **Direct checkpoint sync URL as ground truth**: Comparing local API output against the public checkpoint URL gave an immediate binary pass/fail signal.
- **Targeted regression tests**: After fix, wrote targeted unit tests for fallback paths — served as both documentation and regression guards.

### What failed or was inefficient?
- The crash error (`headState does not exist`) was generic and didn't immediately indicate which code path failed. Required careful tracing of `anchorPayloadPresent` construction logic.

### Most useful log patterns?
- **Crash error message with exact field name** — `headState does not exist` pointed to state cache lookup, not fork choice or DB layer.
- **Checkpoint sync as reproducible trigger** — Using a public checkpoint URL made the bug 100% reproducible without a long-running devnet.

---

## Investigation 6: EPBS Withdrawals Regression (2026-02-24)

**Date:** 2026-02-24
**Type:** Block production mismatch (withdrawals computed from wrong parent state)

### What was being investigated?
`produceBlockV4` failing with withdrawals mismatch on `epbs-devnet-0`. EL returned a payload built with W1 (from PENDING parent state), but envelope validation compared against W2 (from FULL parent state).

### How were logs accessed?
1. **Kurtosis devnet** — 4-node 2×LH + 2×LS + assertoor (Nico's config).
2. **Error log pattern** — `produceBlockV4 error: Withdrawals mismatch` was the specific log line.
3. **Code path tracing** — Read `prepareNextSlot` → `computeNewStateRoot` → `getPayload` chain to identify the state-mismatch window.

### What worked?
- **Exact error message with field name** (`Withdrawals mismatch`) immediately pinpointed the comparison point.
- **Cache invalidation as root cause pattern**: Once the state-transition sequence was clear (`prepareNextSlot` caches payloadId from PENDING state, then FULL state changes withdrawals), the fix was obvious (bypass cache in Gloas path).

### What failed or was inefficient?
- Fix was implemented but Kurtosis strict validation left incomplete before closing the tracker.

### Most useful log patterns?
- **`produceBlockV4 error: Withdrawals mismatch`** — specific enough to immediately identify the failing code path.
- **`payloadId=null`** as a secondary signal (appeared in soak monitors for other EPBS issues).

---

## Investigation 7: Fork-Choice Latency Regression (feat1 vs stable, 2026-02-24)

**Date:** 2026-02-24
**Type:** Performance regression (fork choice timing anomaly + reorg rate spike)

### What was being investigated?
PR #8739 (EPBS fork choice) introduced a ~0.3s head-setting latency gap on all feat1 nodes, and a 5× reorg rate increase on feat1-semi specifically.

### How were logs accessed?
1. **Prometheus via Grafana** — Multi-day time series comparison (3 days) for block lifecycle timestamps, reorg counts, finalization, CPU, memory.
2. **Group comparison** — feat1 {solo, semi, super, sas, mainnet-super} vs stable counterparts.
3. **Depth analysis** — Reorg depth histogram (depth-2 vs depth-3) from Prometheus data.

### What worked?
- **Multi-metric comparison table** — Having 15+ metrics side-by-side for both groups made it immediately clear that the latency gap was specifically in the "processed → head" window.
- **Group-level breakdown** — Seeing that only feat1-semi had elevated reorgs (not super/sas) suggested a workload-size-dependent effect.
- **"Metrics That Are Fine" section** — Explicitly listing what was NOT regressed helped scope the investigation and prevent over-investigation.

### What failed or was inefficient?
- The 0.3s gap couldn't be definitively resolved without inspecting the code diff — it might have been a metric recording order change rather than real latency. Grafana alone wasn't sufficient to disambiguate.
- The reorg spike on feat1-semi required a separate follow-up investigation.

### Most useful log patterns?
- **Block lifecycle timestamps** (`received`, `processed`, `set_as_head`) — timing deltas between consecutive events exposed the latency gap.
- **Reorg count per node group** — aggregated 3-day totals with per-node breakdown immediately showed the semi-only pattern.

---

## Cross-Investigation Lessons for Log Reader Design

### 1. Log Access Hierarchy (by usefulness, most → least)

| Tier | Method | When useful |
|------|--------|-------------|
| **1** | Named metric counter (`> 0` filter) | First triage — is there a signal at all? |
| **2** | Prometheus time series (slope over ≥1h) | Memory leaks, performance regressions |
| **3** | Loki context window around event | Protocol bugs, timing failures |
| **4** | Cross-service log correlation | Interop bugs (CL + EL boundary) |
| **5** | Heap snapshot diffs | Memory leaks, object retention |
| **6** | Local repro with instrumentation | Validation after fix |

### 2. Most Diagnostic Log Fields (ranked by frequency of use)

1. **`errCode`** — Lodestar's structured block/gossip error codes immediately scope to the right subsystem
2. **Timing fields** (`recvToValLatency`, `slot`, timestamps) — correlate latency to protocol timing windows
3. **`parentInForkChoice`**, `payloadStatus` — fork choice state at error time
4. **Constructor names in heap diff** (`WeakRef`, `AbortSignal`, `Listener`) — leak type identification
5. **Participation ratios** (`328/512`, `bits_set`) — observable correctness invariants
6. **Nested error chain** — inner cause is often more diagnostic than outer wrapping error

### 3. What Log Readers Should NOT Do

- **Don't rely on point-in-time metric values for leak detection** — slope over ≥1h windows required
- **Don't truncate nested error causes** — the outer `BEACON_CHAIN_ERROR` wrapping the inner `Parent block hash mismatch` is useless without the inner message
- **Don't parse only one service's logs for interop bugs** — EL (Geth) often surfaces the signal first
- **Don't stream unfiltered Kurtosis logs** — at 12s slots with 4+ nodes, unfiltered output is ~100+ lines/minute; must filter to specific error codes or metrics
- **Don't assume a single good window means a leak is fixed** — oscillatory signals require consecutive confirmation windows

### 4. Effective Filter Patterns for Lodestar Logs

```
# Protocol bugs
"errCode=BLOCK_ERROR" OR "PARENT_UNKNOWN" OR "parentInForkChoice=false"

# Timing anomalies  
"recvToValLatency>" OR "recvToImportLatency>" OR "setHead" (with slot/time context)

# Memory leaks (Prometheus)
heap_space_size_used{space="old"} — track slope over ≥1h windows, not instant value

# Block production failures
"produceBlock.*error" OR "payloadId=null" OR "Withdrawals mismatch"

# Sync failures
"UnknownBlockSync.*failed" OR "BLOCK_ERROR_BEACON_CHAIN_ERROR"

# Network/gossip
"fastMsgId" OR "duplicate" OR "returns_empty_total" (filter to > 0)

# EPBS-specific
"Ignoring beacon update to old head" (from EL/Geth)
"PENDING" OR "FULL" OR "EMPTY" (payload status transitions)
```

### 5. Investigation Anti-Patterns (from real failures)

- **Investigating the wrong issue**: Issue #7299 was initially investigated; #8294 was the real target. Always confirm issue scope before deep-diving.
- **Deploying a fix before confirming root cause**: The req/resp clearable-signal fix (Investigation 2) was deployed before confirming it addressed the primary driver — several hours of deploy+monitor wasted.
- **Single-session long-running monitors**: Monitor sessions stalled, causing data gaps. Background collectors need liveness checks and restart logic.
- **Ephemeral Kurtosis logs**: No raw log preservation after `kurtosis enclave rm`. Key findings must be extracted and written during the investigation.
- **Sub-agent reviewer false positives**: Reviewers flagged files not in the diff — always cross-check findings against `git diff --name-only` before acting.

### 6. Kurtosis-Specific Log Access Patterns

```bash
# Stream logs from one service
kurtosis service logs <enclave> <service-name> --follow

# Get all service names in enclave
kurtosis enclave inspect <enclave>

# Filter for specific error pattern
kurtosis service logs <enclave> lodestar-1 --follow 2>&1 | grep "errCode=BLOCK_ERROR"

# Soak monitor: count specific errors over time
for i in $(seq 1 20); do
  echo "Sample $i: $(date -u +%H:%M:%S)"
  kurtosis service logs <enclave> lodestar-1 2>&1 | grep -c "ISR"
  sleep 30
done
```

### 7. Acceptance Criteria Pattern (from EPBS soak)

The most reliable post-fix validation pattern observed across investigations:
```
ISR (BLOCK_ERROR_INVALID_STATE_ROOT): 0/N samples
UnknownBlockSync processBlock failed: 0/N samples
Block production errors: 0 occurrences
payloadId=null: 0 occurrences
Finality: finalized epoch advances normally
```

Run for ≥20 samples over ≥10 minutes (or ≥100 slots) before declaring a fix valid.

### 8. Loki vs Prometheus: When to Use Each

| Signal Type | Use Loki | Use Prometheus |
|---|---|---|
| Specific error occurrence | ✅ | — |
| Timing of individual events | ✅ | — |
| Context around anomaly | ✅ | — |
| Trend/slope over time | — | ✅ |
| Memory leak detection | — | ✅ |
| Comparative group analysis | — | ✅ |
| Cross-node correlation | ✅ | ✅ |
| Error rate per unit time | — | ✅ |

---

## Summary Table

| Investigation | Type | Primary Log Source | Key Signal | Time to Root Cause |
|---|---|---|---|---|
| Sync aggregate bug (#8294) | Protocol bug | Loki + Kurtosis | `recvToValLatency=23.6s` + participation ratio | ~2h |
| feat1-super memory leak | Memory leak | Prometheus + heap snapshots | `old` space slope + constructor diff | ~24h (oscillatory) |
| EPBS devnet-0 stall | Interop bug | Kurtosis service logs | `Ignoring beacon update to old head` (EL) | ~6h + 6 restarts |
| feat3/blst-z native leak | Native memory | Prometheus | RSS slope vs V8 flat | ~1h |
| EPBS state restart crash | Crash | Live devnet + API | Crash message + checkpoint sync diff | ~2h |
| EPBS withdrawals mismatch | Block production | Kurtosis + error log | `Withdrawals mismatch` error | ~1h |
| Fork choice latency (feat1) | Performance | Prometheus multi-day | Block lifecycle timestamp delta | ~1h |
