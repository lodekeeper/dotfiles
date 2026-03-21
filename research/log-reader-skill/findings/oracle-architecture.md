Build it as a two-plane skill:

Data plane: fetch, normalize, index, template, reduce. This is zero- or near-zero-token to the agent.
Agent plane: emit small, budgeted packs: overview, suspects, drill, compare, delta.

That separation is the core fix for your problem. The agent should never read raw logs first. It should read a compact pack built from a persistent index.

Architecture at a glance
sources
  Loki / files / docker / Kurtosis
      ↓
raw cache or file refs
      ↓
normalize → event index → template index → reducers
      ↓
overview pack (cold start)
      ↓
drill packs / compare packs / delta packs

The important design choice is to persist three kinds of state:

Source cursor state: what bytes/time ranges you have already fetched.

Analysis state: normalized events, template counts, reducers, bookmarks.

Exposure state: what bundles/templates/events the agent has already seen.

That last one is what stops you from re-spending tokens on the same material.

Stage 0: Session + cursor registry

Does: Create one investigation workspace. Track sources, fetch cursors, seen bundles, bookmarks, and optional baseline.
In → out: source descriptors → session.sqlite + state/session.yaml
Agent-visible cost: ~0–30 tokens
CLI:

Bash
logskill session init epbs-stall-2026-03-21
logskill session show epbs-stall-2026-03-21

Tools: stdlib argparse, sqlite3, json, pathlib

What to persist

Store these tables:

sources(id, kind, uri, service, client, cursor_json, config_json)

fetches(id, source_id, start_ns, end_ns, chunk_path, sha256)

events(id, ts_ns, service, client, lvl, module_top, module_full, msg, slot, epoch, peer, err_code, template_key, raw_ref)

templates(id, template_key, cluster_id, count, first_ts, last_ts, max_lvl, services_json, examples_json, scores_json)

bundles(id, stage, params_json, token_estimate, created_ts, path)

bundle_items(bundle_id, item_type, item_id)

bookmarks(id, kind, ref_id, note, created_ts)

Stage 1: Acquisition cache

Does: Pull logs from Loki, local files, Docker, or Kurtosis. Snapshot ephemeral sources. Use delta/follow mode when needed.
In → out: source spec → raw/*.jsonl.zst or file-offset references
Agent-visible cost: ~0–80 tokens
CLI:

Bash
# Loki
logskill fetch loki \
  --session epbs-stall-2026-03-21 \
  --selector '{job="beacon",network="epbs-devnet-0"}' \
  --start '2026-03-21T14:00:00Z' \
  --end   '2026-03-21T14:15:00Z'

# local file
logskill fetch file \
  --session epbs-stall-2026-03-21 \
  /var/log/lodestar/beacon.log \
  --service lodestar-1 --client lodestar

# docker
logskill fetch docker \
  --session epbs-stall-2026-03-21 \
  lodestar-bn-1 --since 15m --until now

# Kurtosis
logskill fetch kurtosis \
  --session epbs-stall-2026-03-21 \
  --enclave epbs-devnet-0 \
  --services lodestar-1,lighthouse-1,geth-1 \
  --snapshot

Tools: requests, subprocess, zstandard, orjson

Source policy

For Loki, use the HTTP query_range API with explicit start/end bounds. LogQL supports json, logfmt, pattern, regexp, and unpack; prefer json/logfmt when available, and use pattern rather than regex for odd human-readable formats. Use Loki for broad production triage and cross-node windows, but keep the final normalization logic in your skill so the same pipeline works for files, Docker, and Kurtosis. 
Grafana Labs
+3
Grafana Labs
+3
Grafana Labs
+3

For Kurtosis, service logs defaults to only the most recent 200 lines unless you use -a, -f is the live-stream mode, and kurtosis dump / enclave dump writes logs and config to disk. So the connector should default to -a for snapshots and optionally create a dump when you mark the session as persistent. 
Kurtosis Docs
+3
Kurtosis Docs
+3
Kurtosis Docs
+3

For Docker, use docker logs --since --until --timestamps for recent bounded windows on local hosts. That makes Docker the right source for live local repros when you do not already have Loki coverage. 
Docker Documentation
+1

Practical acquisition rules

Local file source: default to pointer mode. Store path + inode + byte ranges instead of duplicating raw log files.

Loki / Docker / Kurtosis: default to snapshot mode. Persist returned lines because retention and replay semantics can change.

Chunk by 5-minute windows or 10k events, whichever comes first.

Dedupe overlapping pulls with event_id = sha1(source_id | transport_ts | raw_line).

Stage 2: Parse + normalize

Does: Strip ANSI color, merge multiline events, detect format, parse into a compact event schema, extract pivots.
In → out: raw chunks → normalized NDJSON + parse stats
Agent-visible cost: ~0–60 tokens
CLI:

Bash
logskill build --session epbs-stall-2026-03-21 --normalize

Tools: re, orjson, stdlib datetime

Parser chain

Run this order:

JSON detector

Lodestar JSON: timestamp, level, message, module, context, error

Geth JSON: t, lvl, msg, ...

Erigon-style JSON: similar top-level KV

Lodestar human parser

MMM-DD HH:mm:ss.SSS [MODULE] LEVEL: message key=val, ...

also handle Eph EPOCH/SLOT SECS ... mode

Geth human parser

LEVEL [MM-DD|HH:MM:SS.mmm] message key=value ...

Java-style header + continuation parser

for Besu / Nethermind / stack traces

Fallback

raw line as msg, parse_error=true

Multiline rule

A new event starts only when a line matches a known header pattern. Otherwise append it to the previous event’s stack or continuation field. This is mandatory for Lodestar error stacks and Java EL traces.

Normalized event schema

Use a compact schema for storage and for agent-facing JSON:

JSON
{
  "id": "e_8f3c...",
  "ts": "2026-03-21T14:03:11.201Z",
  "ts_transport": "2026-03-21T14:03:11.223Z",
  "svc": "lodestar-1",
  "role": "cl",
  "client": "lodestar",
  "fmt": "lodestar-json",
  "lvl": "error",
  "mod": "chain/blocks",
  "mod_top": "chain",
  "msg": "PARENT_UNKNOWN diagnostic",
  "slot": 49,
  "epoch": 1,
  "peer": "16Uiu2...",
  "root": "0x1234...5678",
  "parent": "0xabcd...ef12",
  "err": "BLOCK_ERROR_BEACON_CHAIN_ERROR",
  "cause": "Parent block hash does not match state's latest block hash",
  "ctx": {"parentInForkChoice": false},
  "raw": {"chunk": "raw/0003.jsonl.zst", "line": 918}
}
Extraction rules

Always try to extract these into top-level fields:

slot, epoch

peer, peerId

blockRoot, parent, head, finalized

requestId, method, encoding, version

errCode / error.code

durations and timings: *Latency, elapsed, duration, time*, ms, s

payloadStatus, payloadId

Keep exact values in storage. Only abbreviate hashes/peer IDs in packs.

Stage 3: Template index + reducers

Does: Build stable message fingerprints, optional Drain clusters, per-template stats, and client-specific reducers.
In → out: normalized events → index.sqlite, templates.json, reducer tables
Agent-visible cost: ~0–100 tokens
CLI:

Bash
logskill build --session epbs-stall-2026-03-21 --index

Tools: sqlite3, drain3 optional, stdlib stats

Use a hybrid template strategy:

Deterministic heuristic key for everything:

template_key = client | mod_top | canonical_message

Optional Drain3 cluster id for noisy human logs:

only for Geth/Nethermind/Besu or for very noisy debug buckets

Drain3 is a good fit here because it is a streaming template miner based on the Drain algorithm’s fixed-depth parse tree, so you can update clusters online while you ingest logs. Use it as a secondary clustering signal, not as your only identifier. 
GitHub
+2
GitHub
+2

Canonicalization rule

Before clustering, normalize volatile tokens:

long hex → <HEX>

integers → <NUM>

durations → <DUR>

peer IDs → <PEER>

request IDs → <ID>

UUIDs / hashes / ENRs → <ID>

For Lodestar JSON, use message as the seed and ignore context values in the primary key. For Lodestar, simple module + message is often enough because messages are already quite templated.

Reducers you should implement on day 1

These are the highest-value token savers:

Status reducer

collapse repetitive notifier/status lines into intervals

output: state changes, peer min/max, head lag, sync speed

Block import reducer

summarize imported slots, gaps, duplicate imports, import latency outliers

Peer health reducer

summarize low-peer periods, connect/disconnect churn, dominant peers

ReqResp reducer

counts by method/peer, error rate, top failing peers, timeouts

Reducers are where you turn 500 repeated info/debug lines into 1–3 diagnostic rows.

Stage 4: Cold-start overview pack

Does: Produce the first thing the agent reads. Rank suspects without needing a grep term.
In → out: template index + reducers → overview.md and overview.json
Agent-visible cost:

tiny: ~600 tokens

small: ~1500 tokens

medium: ~4000 tokens
CLI:

Bash
logskill overview epbs-stall-2026-03-21 --profile small --mark-seen

Tools: sqlite3, tiktoken

Token accounting should be local and deterministic. tiktoken provides o200k_base and model-specific encodings, so render the pack, count tokens, then prune until it fits. 
GitHub
+1

What the overview pack contains

Always in this order:

Scope

time span, services, clients, event counts, restart count, silence/gap count

Critical hits

global rules, regardless of user filters

Hot slices

1-minute or 1-slot buckets ranked by errors/new templates/bursts

Top unusual templates

not just top frequency; top signal

State changes

sync/synced, execution offline→online, peer drops, restarts

Candidate pivots

exactly what to drill next: slot, template, peer, service, or compare window

Cold-start scoring

Use a simple explicit score:

score(template/window) =
  100 * critical_rule_hit
+  20 * max_severity(error=2,warn=1,info=0)
+  12 * service_asymmetry
+   8 * burst_ratio_gt_5x
+   8 * singleton_or_rare
+   6 * new_in_late_window
+   6 * numeric_outlier_present
+   4 * near_restart_or_gap
+   4 * cross_layer_match

This is the heart of the cold-start solution. It works even when the only clue is “something weird happened.”

Large-window rule

If a window has more than ~50k events:

first emit only a slice overview

then automatically pick the top 3 slices

then compute detailed suspect ranking inside those slices

Do not dump a single giant cross-window summary.

Fidelity policy

For each suspect template, keep:

count

affected services

first_seen

last_seen

one first exemplar

one worst/outlier exemplar

one neighboring context window if critical

That gives much better fidelity per token than either raw lines or bare counts alone.

Stage 5: Drill packs

Does: Show exact context only after overview picked a pivot.
In → out: selector → drill.md / drill.json
Agent-visible cost: ~250–1200 tokens per window, capped by profile
CLI:

Bash
# by template
logskill drill epbs-stall-2026-03-21 --template T17 --before 20 --after 40

# by slot
logskill drill epbs-stall-2026-03-21 --slot 49 --before-slots 1 --after-slots 1

# by event
logskill drill epbs-stall-2026-03-21 --event e_8f3c...

# by peer / request
logskill drill epbs-stall-2026-03-21 --peer 16Uiu2... --method beacon_blocks_by_range

Tools: sqlite3, raw chunk reader, tiktoken

Drill modes

Support these selectors:

--template Tn

--event En

--slot N

--epoch N

--peer ID

--service NAME

--err BLOCK_ERROR_*

--time START..END

Output policy

Default drill pack should include:

1–3 context windows

projected fields, not raw full JSON

full nested error cause

top 5–8 stack frames only

service-local summary above the raw lines

Do not truncate inner causes. That is exactly where a lot of your investigations got the answer.

Stage 6: Cross-service compare pack

Does: Align CL/EL/validator services around one incident window and compress symmetric behavior.
In → out: selected services + anchor → compare.md / compare.json
Agent-visible cost: ~800–2500 tokens
CLI:

Bash
logskill compare epbs-stall-2026-03-21 \
  --services lodestar-1,lighthouse-1,geth-1 \
  --anchor slot:49 \
  --profile small

Tools: sqlite3, alignment code, tiktoken

How to compare

Use two anchors:

Slot anchor when slot exists

Time anchor when it does not

For EL logs with no slot field, join by nearest time window around the CL anchor event.

Compression rule for 4+ services

Do not emit one section per service first. Group services by identical incident behavior:

G1 = [lodestar-1, lodestar-2, lodestar-3]

G2 = [lodestar-4]

Where behavior hash is based on suspect template counts + critical hits in the chosen window.

This is how you keep 6-node devnets readable.

Compare output structure

one-line summary of what diverges

matrix: suspect template × service/group

aligned timeline around anchor

“earliest signal per layer”

CL

EL

validator

Because your investigations repeatedly found that EL sometimes surfaces the first useful clue, always include the counterpart EL window when a CL event triggered the compare.

Stage 7: Delta pack

Does: Return only unseen information since the last bundle.
In → out: session + exposure ledger → delta.md / delta.json
Agent-visible cost: ~300–900 tokens
CLI:

Bash
logskill delta epbs-stall-2026-03-21 --profile tiny --mark-seen

Tools: sqlite3, exposure ledger, tiktoken

Exposure ledger rules

Mark as seen:

templates already summarized

events already shown raw

windows already compared

Then delta returns only:

new critical hits

new suspect templates

major state changes

changes to bookmarked templates/events

This is what makes the skill stateful for the model, not just for the source.

Format handling rules

Use JSON-first if you control the client, but the skill must not depend on JSON.

Lodestar

human and JSON both supported

normalize module_full and module_top

keep error.code and nested cause if present

parse EpochSlot timestamps when used

Geth

parse human format and JSON

no module field; set module_top = null or inferred subsystem

parse top-level KV as context

Nethermind / Besu

treat as Java-style header + multiline continuation

extract what you can; never drop stack traces

fallback to message-level grouping if structured parse is weak

Cold-start strategy in one sentence

Do not ask “what should I grep?” first. Ask “what changed, what is unique, what burst, what crossed layers, and what violated a rule?” first.

Concretely:

Run global critical scan.

Build slice heatmap.

Rank suspect templates by score.

Surface service asymmetry.

Surface numeric outliers.

Emit pivots.

That is the part that solves your “I don’t know what I’m looking for” problem.

Summary fidelity vs token cost

Use this strict ladder:

Counts / reducers

Template rows with first/last/example

One context window per suspect

Aligned compare around anchor

Exact raw lines

Never skip from 1 to 5.

Default pack profiles
YAML
profiles:
  tiny:
    max_tokens: 600
    max_critical: 4
    max_templates: 5
    max_windows: 1

  small:
    max_tokens: 1500
    max_critical: 8
    max_templates: 10
    max_windows: 3
    max_compare_services: 4

  medium:
    max_tokens: 4000
    max_critical: 12
    max_templates: 20
    max_windows: 8
    max_compare_services: 8
Pruning order

When over budget, prune in this order:

extra exemplars

extra windows

stack frame depth

low-score templates

service detail for non-divergent groups

Never prune:

critical rule hits

nested error causes

anchor window for the top suspect

When to use Loki vs local files vs Docker vs Kurtosis
Loki

Use first for:

production nodes

cross-node correlation

15m–24h windows

broad triage before deep dive

Loki is the best wide-angle source because you can query bounded windows through query_range and use server-side parsers before fetching. 
Grafana Labs
+2
Grafana Labs
+2

Local file

Use first for:

exact raw fidelity

repeated offline re-analysis

huge debug captures

rotated file history

one-node local repros

Once a Loki query identifies a 2–10 minute hot window, export or fetch that window and work from a local snapshot.

Docker

Use first for:

a live local container

recent windows only

debugging before logs reach Loki

Docker is your “fast recent slice” source because --since, --until, and --timestamps already match your needed workflow. 
Docker Documentation
+1

Kurtosis

Use first for:

live devnets

ephemeral container debugging

multi-service interop debugging

But always persist before cleanup. service logs is truncated by default, and dump commands exist specifically to package logs/config for offline analysis. 
Kurtosis Docs
+3
Kurtosis Docs
+3
Kurtosis Docs
+3

One strong current recommendation

Do not build new ingestion logic around Promtail-specific parsing. Grafana marks Promtail deprecated, LTS through February 28, 2026, with EOL on March 2, 2026. Also, Grafana’s built-in log-pattern mining is ephemeral to the previous three hours, so it is useful as a UI convenience but not as the durable stateful core of this skill. 
Grafana Labs
+2
Grafana Labs
+2

Skill structure

Repo layout:

logskill/
  cli.py
  config.py
  state.py

  connectors/
    loki.py
    file.py
    docker.py
    kurtosis.py

  parsers/
    lodestar_json.py
    lodestar_text.py
    geth_json.py
    geth_text.py
    java_multiline.py
    generic.py

  enrichers/
    common_fields.py
    lodestar.py
    geth.py

  reducers/
    status.py
    block_import.py
    peer_health.py
    reqresp.py

  rules/
    generic.yml
    lodestar.yml
    geth.yml
    epbs.yml
    peerdas.yml

  packers/
    overview.py
    drill.py
    compare.py
    delta.py

  templates/
    markdown.py
    compact_json.py

Runtime workspace:

~/.cache/logskill/sessions/<session-id>/
  session.sqlite
  state.yaml
  raw/
    0001.jsonl.zst
    0002.jsonl.zst
  bundles/
    overview-001.md
    compare-002.md
    delta-003.md
Minimal dependencies
Bash
pip install --user orjson requests zstandard drain3 tiktoken

No GUI, no sudo, no extra services required.

Always-surface rules

Run these before any user filter and inject hits into every overview.

1. Consensus / block validation

Match any of:

err_code =~ ^BLOCK_ERROR_

PARENT_UNKNOWN

UnknownBlockSync .* failed

parentInForkChoice=false

headState does not exist

Error on head state regen

2. Execution bridge

Match any of:

Execution client is offline

Execution client is syncing

Execution client authentication failed

Error pushing notifyForkchoiceUpdate

Ignoring beacon update to old head

3. Block production

Match any of:

produceBlock.*error

payloadId=null

Withdrawals mismatch

Engine failed to produce the block within cutoff time

Builder failed to produce the block within cutoff time

4. Network health

Match any of:

Low peer count

PeerDiscovery: discv5 has no boot enr

Error on discv5.findNode

Network worker thread error

Error on ReqResp

repeated reqresp timeout/error spikes by method/peer

5. Process lifecycle

Match any of:

panic

fatal

uncaught

shutting down

restart/startup messages

silence gap > configurable threshold

6. Timing anomalies

Surface when any extracted timing field exceeds a threshold:

recvToValLatency

recvToImportLatency

elapsed

any *_ms or *_s

Threshold should be configurable as a fraction of slot duration. For mainnet-like 12s slots, start with warn if > 4s, critical if > 8s. For 1s devnet slots, scale accordingly.

Rule format
YAML
- id: parent_unknown
  severity: critical
  match:
    any:
      - field: err
        regex: '^BLOCK_ERROR_'
      - field: msg
        regex: 'PARENT_UNKNOWN|UnknownBlockSync .* failed'
      - field: ctx.parentInForkChoice
        equals: false
  capture:
    before_lines: 20
    after_lines: 40
  keep_fields: [slot, epoch, parent, root, peer, err, cause]
Optional but worth adding: metrics-hints hook

Your own investigations show that memory and performance bugs often start from Prometheus, not logs. So I would add one optional pre-stage later:

Bash
logskill hint prometheus --session feat1-super --metrics old_heap_slope,rss,peer_count

Not part of v1, but the hook should exist.

End-to-end example
Bash
# 1. start a session
logskill session init epbs-stall

# 2. acquire a snapshot from Kurtosis
logskill fetch kurtosis \
  --session epbs-stall \
  --enclave epbs-devnet-0 \
  --services lodestar-1,lighthouse-1,geth-1 \
  --snapshot

# 3. parse and index
logskill build --session epbs-stall --all

# 4. first model-facing pack
logskill overview epbs-stall --profile small --mark-seen > /tmp/overview.md

# 5. compare around the strongest pivot
logskill compare epbs-stall \
  --services lodestar-1,lighthouse-1,geth-1 \
  --anchor slot:49 \
  --profile small \
  --mark-seen > /tmp/compare-slot49.md

# 6. fetch raw context only for the flagged template
logskill drill epbs-stall --template T17 --before 20 --after 40 > /tmp/t17.md

# 7. continue later without re-reading old material
logskill delta epbs-stall --profile tiny --mark-seen > /tmp/delta.md
The shortest practical recommendation

Implement session / fetch / build / overview / drill / compare / delta in that order.
Make overview the default first read.
Make delta the default second read.
Make raw logs a last resort, not a first step.