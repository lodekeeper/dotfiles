Build it as a cache-first, session-based log reader. Raw logs should go into a local session cache and normalized SQLite store; the model should only ever see progressively smaller packs: survey → hotspots → focus → raw expand → delta. For production breadth, use Loki’s bounded query_range API and LogQL pipelines to pre-scope streams and parse/filter at query time; for full-fidelity debug, use local files or spooled container/Kurtosis output. Keep Drain3 optional: it is a streaming template miner with a fixed-depth parse tree, which is useful for noisy text logs, but you do not need it for every Lodestar run. 
Grafana Labs
+2
Grafana Labs
+2

Core architecture
source adapters
  ├─ loki
  ├─ local file
  ├─ docker logs
  └─ kurtosis service logs
        ↓
collect + normalize + fingerprint
  ├─ strip ANSI
  ├─ multiline join
  ├─ parse client format
  ├─ extract common keys
  ├─ template ID
  └─ raw offset ref
        ↓
session store (SQLite + raw spool + cursors + views)
        ↓
survey (broad census, cold start)
        ↓
hotspots (rank suspicious windows/patterns)
        ↓
focus pack (timeline + evidence for one hotspot)
        ↓
expand/raw (exact windows, exact matches)
        ↓
delta (only new/unseen since last pack)

The key rule is: never send raw debug streams directly to the model. Send only budgeted packs generated from the local store.

Canonical event schema

Normalize every source into one event shape:

JSON
{
  "event_id": "E_8f1b2c7a",
  "ts": "2026-03-21T14:23:11.042Z",
  "seq": 182991,
  "source_kind": "loki",
  "source_ref": "prod-eu-west",
  "service": "lodestar-1",
  "client": "lodestar",
  "layer": "CL",
  "role": "beacon",
  "format": "lodestar-json",
  "level": "warn",
  "level_num": 1,
  "module": "chain",
  "msg": "Head state not available, triggering regen",
  "msg_norm": "Head state not available, triggering regen",
  "template_id": "T_4a91d2",
  "kv": {"slot": 1234567, "epoch": 38580},
  "slot": 1234567,
  "epoch": 38580,
  "peer": null,
  "root": null,
  "payload_id": null,
  "request_id": null,
  "err_code": null,
  "err_message": null,
  "stack_raw": null,
  "parse_status": "parsed",
  "raw_ref": {"file": "raw/pull-003.log", "offset": 9128374, "length": 184}
}

Important implementation choices:

Materialize common search keys as columns: slot, epoch, peer, root, parent_root, payload_id, request_id, err_code, latency_ms, elapsed_ms, peers.

Keep kv as JSON too, but do not rely on JSON querying for common paths.

Store raw_ref so you can re-open exact raw context without re-fetching.

If parsing fails, keep the line as parse_status=unparsed; the unparsed rate itself must show up in survey output.

Stages
Stage	What it does	Input → output	Expected token cost	CLI	Tools
0. collect	Pull logs, join multiline events, parse, normalize, extract keys, assign template_id, update cursors, cache raw	source/window → events.db, raw/, manifest.json	0	lkr collect ...	Python stdlib, sqlite3, subprocess, re, PyYAML; optional orjson
1. survey	Broad cold-start census: counts by service/level/module, top templates, rare/new templates, burst windows, parse failures, notifier-derived health, always-surface hits	session/window → survey.json, survey.md	800–1800 typical, hard cap 2500	lkr survey --session X --since -15m --budget 1800	SQLite queries, lightweight stats
2. hotspots	Cluster suspicious seeds into ranked candidate investigations with stable IDs (H1, H2)	session/window or survey → hotspots.json, hotspots.md	400–1200	lkr hotspots --session X --since -15m --limit 8	heuristic scoring
3. focus	Build one LLM-ready evidence pack for a hotspot/key: concise narrative, timeline, cross-service correlation, representative raw lines, full nested error chain	hotspot/key → pack.json, pack.md	preset 2k / 4k / 8k / 16k	lkr focus --session X H2 --budget 6000	token estimator + retrieval
4. expand	Exact raw windows or all matches for a template/event/key; no heavy summarization	event/template/key → raw or JSONL	~50–70 tokens/line	lkr expand --session X --template T12 --lines 40	raw cache + offsets
5. delta	Only what is new since the last shown pack; skip already-seen events/templates unless severity changed or recurrence spiked	session + last pack → delta.json, delta.md	300–1500	lkr delta --session X --budget 1200	views ledger + cursors

Add one macro command for convenience:

Bash
lkr triage <source> ...    # collect + survey + hotspots

That should be your default cold-start entry point.

Parsing and normalization rules

Treat each client as a separate parser, then converge into the same schema.

Parsers to implement

lodestar_json

lodestar_human_regular

lodestar_human_epochslot

geth_json

geth_human

java_multiline_generic for Nethermind/Besu-style stack traces

fallback_text

Geth has its own default human log structure and verbosity model, so parse it as a first-class format rather than forcing Lodestar assumptions onto it. 
go-ethereum

Critical normalization rules

Strip ANSI color codes first.

Collapse multiline stack traces into a single event.

Normalize timestamps to UTC.

For Lodestar/Geth human logs with no year, infer year from:

requested time window,

file mtime,

current session date.

For Lodestar EpochSlot timestamps, support two modes:

if genesis_time and slot_seconds are configured, reconstruct UTC;

otherwise store ts=null, keep slot and seq, and order by file position.

Parse durations like 294.7µs, 23.6s, 1824ms into numeric milliseconds.

Compute msg_norm by replacing volatile fields with placeholders:

hex roots / hashes

peer IDs

request IDs

IPs / URLs

big integers / slot-like integers

durations

Default template_id = hash(client|module|msg_norm).

Only switch to Drain3 if the window is noisy enough to justify it:

events > 50k, or

unique msg_norm / total events > 0.2, or

unstructured text source with high cardinality.

For Lodestar JSON and most Lodestar human logs, simple normalized-message grouping is the default. Drain3 is the fallback, not the baseline.

Cold start: how to find signal when you do not know what to grep

Your survey stage should not be “top errors.” It should compute a fixed set of anomaly lenses every time.

The survey must always calculate

Service health matrix

events, warn, error counts

top modules

parse failure rate

service restart count

Template census

top templates by count

rare templates (count <= 3)

new templates not seen earlier in the session

burstiest templates by bucket

Status-line derived health

head slot progression

finalized progression

peer count minima

sync/synced transitions

missing notifier or no-head-advance windows

Timing outliers

any parsed numeric field matching *latency*, *delay*, *elapsed*, *_ms

compare against local p95 and static thresholds

Cross-service divergence

same-role peers behaving differently

one Lodestar node with unique warnings

EL events preceding CL failures

Always-surface rule hits

listed later below

Parser health

if unparsed rate > 2%, surface it

if multiline explosion is happening, surface it

Hotspot scoring

Start deterministic. Do not start with embeddings.

A good first scoring model is:

score =
  8 * always_surface_hit
+ 5 * critical_error
+ 4 * service_divergence
+ 4 * timing_outlier
+ 3 * rare_template
+ 3 * burst_spike
+ 2 * cross_service_link
+ 2 * new_template
+ 1 * parse_failure_nearby

Each hotspot should output:

id: H1

why: one sentence

services

time_window

seed_events

template_ids

keys: slot/root/peer/payload_id/request_id/err_code

next_commands

This is what makes cold start workable: the model gets a shortlist of plausible investigations instead of a log dump.

Multi-service logs, especially Kurtosis

For multi-service sessions, the model should see collapsed symmetry first, divergence second.

Required service labels

Every event should carry:

service

client

layer (CL, EL, validator, test)

role

node

Define these in a services.yaml mapping if the source does not provide enough metadata.

Overview behavior

In survey:

Collapse services with near-identical pattern sets.

Report divergence explicitly.

Example:

CL/beacon: 3 services normal, 1 divergent
  - common: synced notifier, imported blocks, no warn/error
  - divergent: lodestar-2 has 14x PARENT_UNKNOWN and 2x UnknownBlockSync failures
EL/execution: 2 services normal, 1 flagged
  - geth-1 shows "Ignoring beacon update to old head" near slot 49

That gives you multi-node coverage without 4× token blowup.

Correlation keys for cross-service focus

When building a focus pack, expand by:

slot

epoch

root

parent_root

payload_id

request_id

peer

err_code

Then also expand by time:

same service: ±10 lines or ±15s

related services: ±3s by default

for slot-centric issues: slot-1 through slot+2

For Kurtosis, treat the CLI as a transport only. First capture all service logs into the local session cache, then analyze there. Do not rely on re-reading the enclave later.

Summary fidelity vs token cost

Use a budget ladder, not naive truncation.

Budget presets

overview: 1200–1800 tokens

brief: 4000 tokens

deep: 8000 tokens

forensic: 16000 tokens

Section quotas inside each pack

A good default split:

25% must-show findings

15% service matrix

25% hotspots or timeline

25% representative evidence

10% next handles / open questions

When over budget, degrade in this order:

drop extra examples

collapse repeated templates

merge identical services

shorten timeline

drop low-score hotspots

Do not drop entire categories early. A 1200-token survey that includes one line from each category is much more useful than 1200 tokens of only errors.

Also: never put 100 raw lines into a survey. Raw belongs in expand, or at most as 1–3 exemplars in focus.

When to use Loki vs local files vs docker vs Kurtosis
Source	Use it for	Why	Avoid when
Loki	production cold start, cross-node history, retrospective windows, first-pass breadth	time-bounded query_range, label scoping, LogQL parse/filter pipelines 
Grafana Labs
+1
	you need full debug fidelity not shipped to Loki
Local files	deep debug, repeated drill-down, exact offsets, postmortem packs	best fidelity, cheap repeated access	you need many hosts at once
Docker logs	live local container without file logging	quick capture source	long investigations unless you spool locally first
Kurtosis	devnet multi-service debugging	easy per-service collection	anything after enclave removal unless captured first

Operational rule:

Production: Loki first for breadth, local file second for depth.

Local single host: local file first.

Docker-only: collect once, then work from local cache.

Kurtosis: collect immediately into a session cache.

Skill structure
log-reader-skill/
  pyproject.toml
  README.md
  bin/
    lkr
  logreader/
    cli.py
    config.py
    schema.py
    state.py
    render.py
    parsers/
      autodetect.py
      lodestar_json.py
      lodestar_human.py
      geth_json.py
      geth_human.py
      java_multiline.py
      fallback.py
    sources/
      loki.py
      file.py
      docker.py
      kurtosis.py
      stdin.py
    pipeline/
      collect.py
      survey.py
      hotspots.py
      focus.py
      expand.py
      delta.py
    rules/
      always.yaml
      thresholds.yaml
      service_patterns.yaml

Session state:

~/.cache/lkr/sessions/<session>/
  events.db
  cursors.json
  raw/
  packs/
  config.snapshot.yaml

SQLite tables:

pulls

events

templates

template_stats

views

bookmarks

views is critical. It tracks what has already been shown to the model so delta can emit only new or materially changed information.

Example CLI

Cold start from Loki:

Bash
lkr triage loki \
  --session issue-8294 \
  --selector '{job=~"beacon-node|execution"}' \
  --from -15m --to now \
  --services services.yaml \
  --budget 1800

Deepen one hotspot:

Bash
lkr focus --session issue-8294 H2 --budget 6000

Get exact raw around slot 2643619 across services:

Bash
lkr expand --session issue-8294 \
  --slot 2643619 \
  --cross-service \
  --before-lines 20 \
  --after-lines 10

Continue without re-ingesting old context:

Bash
lkr delta --session issue-8294 --budget 1200

Kurtosis:

Bash
lkr collect kurtosis \
  --session epbs-devnet0 \
  --enclave epbs-devnet-0 \
  --all-services

lkr survey --session epbs-devnet0 --since -10m --budget 1600
lkr focus  --session epbs-devnet0 H1 --budget 8000
Error patterns that should always be surfaced

These should bypass normal filters and be injected into every survey/focus pack if they occur inside the queried window or correlated window.

Class	Match examples
Process death / crash	panic, fatal, uncaught, out of memory, segfault, SIGABRT, unexpected restart/shutdown
EL auth / connectivity	Execution client authentication failed, Execution client is offline, Execution client is syncing, notifyForkchoiceUpdate failures
EL stale fork choice	Ignoring beacon update to old head
Consensus/block validation	BLOCK_ERROR_, PARENT_UNKNOWN, parentInForkChoice=false, UnknownBlockSync.*failed, Gossip validations failed, Consensus checks failed
Block production	produceBlock.*error, payloadId=null, Withdrawals mismatch, failed to produce the block within cutoff time
Head/state availability	headState does not exist, Head state not available, regen failures
Network degradation	Low peer count, PeerDiscovery, discv5 errors, Network worker thread error, Published data columns to 0 peers
Proposer/reorg anomalies	Multiple block proposers, Proposer duties re-org, Skipped slot
Timing anomalies	recvToValLatency, recvToImportLatency, set_as_head_time_ms, attestable_delay_ms, any parsed duration above configured thresholds
Parser health	unparsed rate spike, stack-trace explosion, format drift

Put these rules in rules/always.yaml with fields:

YAML
- id: consensus.parent_unknown
  regex: 'PARENT_UNKNOWN|parentInForkChoice=false|UnknownBlockSync.*failed'
  severity: critical
  always_surface: true
  correlate_on: [slot, root, parent_root]
Recommended thresholds config
YAML
chain:
  genesis_time: "2026-03-21T00:00:00Z"
  slot_seconds: 12

thresholds:
  peer_low_warn: 3
  peer_low_crit: 1
  stall_slots_warn: 2
  stall_slots_crit: 4
  latency_warn_ms: 4000
  latency_crit_ms: 12000
  rare_template_max_count: 3
  burst_zscore_warn: 3.0

templating:
  engine: simple
  use_drain_after_events: 50000

For 1-second Kurtosis devnets, override slot_seconds: 1. That makes stall and burst logic behave sanely.

What I would implement first

Version 1:

collect + parsers + SQLite store

survey with always-surface rules

focus with exact raw offsets

delta

Only after that:

service divergence scoring

Drain3 optional path

live follow mode

That gives you a usable cold-start-capable skill fast, with minimal dependencies and predictable token spend.

The design in one sentence: do expensive log ingestion locally once, normalize into a searchable event store, and only feed the model budgeted investigation packs built from ranked anomalies and exact evidence.