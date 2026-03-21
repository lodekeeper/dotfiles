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
