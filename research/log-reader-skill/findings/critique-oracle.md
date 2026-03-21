# Adversarial Critique: Oracle Architecture for Log Reader Skill

**Date:** 2026-03-21  
**Author:** Lodekeeper (subagent: log-research-adversary-oracle)  
**Role:** Adversarial reviewer — find what's wrong, not what's right  
**Confidence ratings:** HIGH / MEDIUM / LOW per section

---

## Executive Summary

The Oracle architecture is intellectually serious and solves the right problem. The two-plane design (data plane vs agent plane), the exposure ledger, and the cold-start scoring formula are all good ideas. But the design has a cluster of v1 implementation risks that could sink it before it ships:

1. **SQLite is the wrong persistence layer for a debugging tool.** It trades hackability and crash-resilience for query expressiveness that a v1 doesn't need.
2. **Pack profile token budgets are wrong by 3–5×.** The numbers don't match real Lodestar log density. This will either produce useless truncated output or blow the budget constantly.
3. **The cold-start scoring formula has undefined terms.** Three of the nine scoring components can't be implemented without additional design work.
4. **The dependency tree has landmines.** `drain3` pulls `scipy`; `orjson` may need a Rust compiler. On a minimal server these are real install failures.
5. **The exposure ledger breaks after session compaction.** The one feature that justifies SQLite doesn't actually survive the scenario it's designed for.

The Sonnet alternative (pipeline-architecture.md) is less ambitious but ships faster and fails more gracefully. The best design takes Oracle's conceptual model and replaces the implementation choices with Sonnet's simpler ones.

---

## 1. SQLite vs Flat Files

**Confidence: HIGH**

### What could go wrong

- **Crash-mid-write corruption.** SQLite in WAL mode handles concurrent readers but a hard crash during a schema migration or bulk insert will leave the DB in an unknown state. Flat JSONL files are append-only — a crash loses at most one line.
- **Schema drift over time.** The Oracle schema has 7 tables. As the skill evolves (new fields, new bundle types), schema migrations become mandatory. A `pip install --upgrade logskill` that changes the schema will silently break existing sessions. There's no migration story in the document.
- **Tool compatibility.** The primary consumer of the state is the AI agent via shell commands. Debugging a broken session means either using `sqlite3` CLI interactively or writing ad-hoc queries. Debugging a broken flat-file session means `jq` and `cat`.
- **Lock contention.** If two fetch operations run in parallel (acquiring Loki + Kurtosis simultaneously), SQLite write locks will serialize them. JSONL files can be appended concurrently without locking.

### What's missing

The Oracle document doesn't address:
- How to recover a corrupted session DB
- How to inspect raw session state without a special CLI command
- What happens to `session.sqlite` during a Docker container restart (if running inside one)
- Version/schema tagging so old sessions can be detected and rejected cleanly

### What's wrong about the assumption

The assumption is that complex queries (template × service × time joins) justify a relational store. But the actual query pattern in practice is:

1. `SELECT * FROM templates ORDER BY score DESC LIMIT 20` — for overview
2. `SELECT * FROM events WHERE template_key = ?` — for drill
3. `SELECT * FROM templates WHERE created_ts > last_seen_ts` — for delta

None of these require joins. They can all be implemented with a sorted JSONL file and `jq`. The SQLite advantage only materializes for cross-table joins that the v1 workflow doesn't exercise.

### What's over-engineered

The `bundle_items` table (associating bundles with their source events) is correct in principle but adds a write amplification problem: every pack emission writes to both `bundles` and `bundle_items`. For a debugging tool that runs a handful of sessions per day, this is unnecessary bookkeeping.

### Verdict

Use SQLite for the exposure ledger only (it genuinely benefits from queries like "have I seen template T in bundle B?") and flat JSONL for everything else. Sonnet's approach of `/tmp/logreader/*.jsonl` is correct for v1.

---

## 2. Cold-Start Scoring Formula

**Confidence: HIGH**

### The formula

```
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
```

### Undefined terms (implementation blockers)

**`service_asymmetry` (12 pts)** — computed how? Between which services? A template that appears on `lodestar-1` but not `lodestar-2` gets +12? What if you only have one service? What if services have different log verbosity settings? This term requires a service baseline comparison that isn't defined anywhere in the document. It also implicitly requires fetching logs from all services before computing it — circular dependency with the acquisition stage.

**`numeric_outlier_present` (6 pts)** — which numeric fields? How is "outlier" defined? Against the template's own historical distribution? Against slot-normalized expectations? Against other services? The `recvToValLatency=23.6s` in the sync aggregate investigation was the single most diagnostic number in that entire session. But whether `23.6s` is an outlier depends on whether you know that 12s is the nominal slot time. The formula doesn't say where this context comes from.

**`cross_layer_match` (4 pts)** — this requires correlating CL and EL log events by timestamp and detecting when a CL error was preceded by an EL event. That's a non-trivial join even with SQLite. The document doesn't describe the matching algorithm, the time window, or how it handles EL logs that have no slot field. For EPBS specifically, the Geth `Ignoring beacon update to old head` appearing 1 second before the Lodestar `BLOCK_ERROR` was the key signal (Investigation 3) — but implementing this detector correctly is weeks of work, not days.

### What's over-engineered

The formula has 9 components. A scoring function with 9 independent terms that are all additive will not produce a clean ranking — it produces a noisy priority score that looks authoritative but is highly sensitive to which terms happened to fire. For v1, a three-tier ranking is sufficient:
- **Critical:** any `critical_rule_hit`
- **Suspicious:** any `warn/error` + `burst_ratio` + `singleton`
- **Background:** everything else

That captures 80% of the diagnostic value with 20% of the implementation risk.

### What's wrong about the assumption

The formula assumes that scoring is the right approach for "what to look at first." But from the real investigations, the actual cold-start question was almost always answered by: **is there a BLOCK_ERROR in the log?** Seven out of seven investigations had a clear primary signal visible in a simple `grep BLOCK_ERROR | grep PARENT_UNKNOWN | grep Withdrawals` pass. The scoring formula is solving for the case where there's no obvious signal — but that case is rare in Lodestar debugging. The common case is "there's an error, I just need context around it."

### What's under-engineered

The formula doesn't handle **silence gaps** explicitly. Investigation 3 (EPBS devnet stall after slot 49) was definitively characterized by the fact that block production stopped. A silence gap detector (no "Imported block" for N consecutive expected slots) would have been the first and most obvious signal. The formula has a `near_restart_or_gap` term worth only 4 points, but detecting the gap is the primary signal — it should be worth 60+ or be a separate always-surface rule.

---

## 3. Exposure Ledger

**Confidence: HIGH**

### The concept

The exposure ledger tracks which templates, events, and windows the agent has already seen so the delta pack can return only new information. It's the right idea.

### Why it breaks after session compaction

The exposure ledger is stored in SQLite on disk. The agent's context window is ephemeral — it can be compacted at any time. After compaction:

1. **The agent doesn't remember what it asked for.** It may call `logskill overview` again, not knowing it already ran it.
2. **The ledger says "already seen."** The delta pack returns nothing (or very little).
3. **The agent is stuck.** It has no overview, and the delta pack is empty because the ledger already marked everything as seen.

This is a direct inversion of the intended behavior. The ledger prevents re-reading old material — but after compaction, re-reading old material is exactly what the agent needs to do.

**The correct model:** the exposure ledger should track agent-visible bundle IDs that the agent explicitly acknowledges having processed, not just emitted. The skill CLI should support `logskill reset-exposure` or `logskill re-overview` that clears the seen flags and regenerates. Without this, compaction leaves the agent in an unrecoverable state.

### What's missing

- No mechanism to detect "agent context was compacted, start fresh"
- No "re-baseline" command that regenerates overview without mark-seen
- No TTL on seen entries (a 48h investigation with rotation should allow re-seeing yesterday's material)
- The STATE.md in the Sonnet design explicitly addresses the compaction scenario via `analyses_done` and `findings` in a flat JSON — much simpler and more resilient

### Session compaction vs ledger state: a concrete failure scenario

```
T+0: Agent calls logskill overview → sees T1–T20, marks all seen
T+1: Agent drills T17, marks seen
T+2: Context compaction occurs (session limit hit)
T+3: Agent (now fresh) calls logskill delta → gets NOTHING (all already marked seen)
T+4: Agent calls logskill overview → still gets NOTHING (already marked seen)
T+5: Agent is stuck; doesn't know to call logskill session init or reset-exposure
```

This is a silent failure mode — no error, just empty output.

---

## 4. Pack Profiles (tiny/small/medium) — Token Budgets

**Confidence: HIGH**

### The numbers

```yaml
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

medium:
  max_tokens: 4000
  max_critical: 12
  max_templates: 20
  max_windows: 8
```

### Why these are wrong

**`tiny` (600 tokens):** A single Lodestar error template entry with one example and context looks like:

```
[t0018] count=3  level=error  [chain]  "Failed to import block slot=<*> errCode=<*>"
  ctx_keys: slot, errCode, parentRoot, root, peer
  first: 14:17:32  last: 14:18:55
  examples:
    14:17:32 error [chain] Failed to import block slot=1234567 errCode=BLOCK_ERROR_INVALID_STATE_ROOT
              parentRoot=0x1234…5678 root=0xabcd…ef12 peer=16…a3b4f2
              cause: Parent block hash does not match state's latest block hash
```

That's ~150 tokens for one template entry. With a header (~80 tokens), 4 critical hits at 150 tokens each = 680 tokens. The `tiny` profile allows 4 criticals but only 600 total tokens. The numbers are internally inconsistent.

**`small` (1500 tokens):** 10 templates × 150 tokens/template = 1500 tokens. That leaves zero tokens for the scope section, timeline, module breakdown, or pivot hints. In practice, a useful `small` overview is ~5,000–8,000 tokens. This matches the Sonnet design's stated range of 4,000–8,000 tokens for a triage report.

**`medium` (4000 tokens, 8 compare services):** A compare pack for 8 services around one incident window would need: 8 service summaries × ~500 tokens each = 4,000 tokens, leaving nothing for the aligned timeline or the divergence analysis. Realistic estimate for a useful 8-service compare is 10,000–20,000 tokens.

### What this means in practice

The `--profile small` will be the default for most uses. It will produce truncated, nearly-useless output because 1500 tokens is too small. Either:
1. Users will constantly switch to `--profile medium` (which is also too small)
2. They'll hit the budget cap constantly and wonder why the output is incomplete
3. The pruning logic will strip the context windows and exemplars that make the output useful

**Recommendation:** Realistic profiles should be:
- tiny: 3,000 tokens (emergency, just criticals + top 3 templates)
- small: 8,000 tokens (standard cold start)
- medium: 20,000 tokens (deep analysis, multi-service)
- large: 50,000 tokens (full compare, rare)

---

## 5. Reducers — Are 4 Enough?

**Confidence: MEDIUM**

### The 4 proposed reducers

1. **Status** — collapse notifier/status lines into intervals
2. **Block import** — summarize imported slots, gaps, latency outliers
3. **Peer health** — connect/disconnect churn, dominant peers
4. **ReqResp** — counts by method/peer, error rate, top failing peers

### What's missing for v1

**Execution bridge reducer.** The single most diagnostic cross-layer signal in the real investigations (Investigation 3: EPBS devnet stall) was the Geth `Ignoring beacon update to old head`. An execution bridge reducer would collapse FCU/newPayload call statistics: call count, error count, error rate, EL state transitions (syncing → synced → offline). The status reducer won't catch this because it collapses Lodestar notifier lines, not Geth lines. Without a dedicated execution bridge reducer, Geth logs remain unsummarized and the cross-layer correlation is manual.

**Sync state machine reducer.** Lodestar's sync has 4+ states: `SyncState.Stalled`, `SyncState.SyncingFinalized`, `SyncState.SyncingHead`, `SyncState.Synced`. The status reducer "collapses repetitive notifier/status lines" but doesn't explicitly track sync state transitions. In Investigation 1 (sync aggregate bug), the sync state machine was the primary source of truth. A sync reducer would emit: `14:00:00 SyncingHead → 14:17:30 Stalled → 14:18:55 SyncingHead (9 transitions total)`.

**Timing distribution reducer.** The `recvToValLatency=23.6s` in Investigation 1 was the single most diagnostic field in the entire session. A timing reducer would compute per-slot latency percentiles across all timing fields (`recvToValLatency`, `recvToImportLatency`, `elapsed`, `setHead`, `*Latency`) and surface p95/p99 values. Without this, timing outliers are surfaced only if they hit the `numeric_outlier_present` scoring term — which is undefined (see section 2).

**PeerDAS / attestation participation reducer.** For PeerDAS-specific investigations, the "Published data columns to 0 peers" warning and participation ratios are primary signals. These don't fit into any of the 4 proposed reducers.

### What's over-engineered

The ReqResp reducer description says "top failing peers, timeouts" — this is correct but it should also output "methods with >X% error rate" and "peers with zero successful exchanges" (complete dead peers), which are the signals that matter for network health.

---

## 6. The 7-Stage Pipeline — Too Many Stages?

**Confidence: MEDIUM**

### The stages

0: Session init  
1: Acquisition cache  
2: Parse + normalize  
3: Template index + reducers  
4: Cold-start overview pack  
5: Drill packs  
6: Cross-service compare pack  
7: Delta pack  

### The problem

Stages 4, 5, 6, and 7 are all "emit a budgeted pack from the index." They share the same inputs (SQLite) and the same output machinery (tiktoken counting + pruning). Implementing them as 4 separate pipeline stages means 4 separate CLI commands, 4 separate modules, 4 separate token-accounting code paths. In practice, this is a single `emit --mode [overview|drill|compare|delta]` command.

The Sonnet design is more honest: `run`, `triage`, `drill`, `compare`, `watch`, `soak`, `status` — the commands map to user workflows, not pipeline internals. A user doesn't think "I want to run stage 4." They think "I want an overview."

### What should be collapsed

- **Stages 0+1** → `logskill fetch` (session init is implicit on first fetch)
- **Stages 2+3** → `logskill build` (already named this way in the Oracle doc, but stages 2+3 aren't numbered consistently — the "Stage 3" section conflates parse, normalize, AND index into one)
- **Stages 4+5+6+7** → `logskill pack --mode [overview|drill|compare|delta]`

The 7-stage framing is useful as documentation (explaining what the system does internally) but should NOT be the CLI interface.

### What's over-engineered

The "Large-window rule" in Stage 4 adds conditional logic to automatically "pick top 3 slices" for 50k+ event windows. This is premature optimization. The first question to ask about a 50k event window is "did you fetch the right time range?" A better default is to reject windows >50k events and ask the user to narrow the time range first.

---

## 7. Parser Chain — Real-World Robustness

**Confidence: MEDIUM**

### Lodestar EpochSlot timestamps

The document mentions `Eph EPOCH/SLOT_INDEX SLOT_SECONDS` format as a variant to handle, but gives no regex or parser implementation. This format (`Eph 312/3 5.123 [chain] ...`) requires knowing the genesis time to convert back to wall-clock time — otherwise events can't be correlated with Geth logs (which use wall clock). The Oracle document says "parse EpochSlot timestamps when used" but doesn't say how to reconstruct the UTC timestamp. This is a silent normalization failure.

### The Lodestar notifier status line

```
info: Syncing 4d 2h left - 3.42 slots/s - slot: 1234567 - head: (slot -15) 0x1234…5678 - exec: 0x4567… - finalized: 0xabcd…ef12:123450 - peers: 35
```

The Oracle approach uses `module | mod_top | canonical_message` as the template key. But `canonical_message` canonicalizes the `message` field only — for Lodestar JSON, this is fine. For Lodestar human format, the message field IS the whole rest of the line after the level prefix, including all KV pairs. The canonical_message for the notifier line would be:

```
Syncing 4d 2h left - 3.42 slots/s - slot: <NUM> - head: (slot -15) <HEX> - exec: <HEX> - finalized: <HEX>:<NUM> - peers: <NUM>
```

...which requires correctly tokenizing "4d 2h left" as a duration (not a bare slot number), and the `(slot -15)` as a slot-relative expression. The document's canonicalization rules (`long hex → <HEX>`, `integers → <NUM>`, `durations → <DUR>`) would partially handle this but not cleanly. Missing: handling of relative slot expressions like `(slot -15)`.

### ANSI stripping in the parser chain

The document says "strip ANSI color" in Stage 2, but the format detector runs BEFORE stripping in Stage 1. If detection runs on colored text, the Lodestar human regex:

```
^(?P<ts>[A-Z][a-z]{2}-\d{2} ...)
```

will fail if there's an ANSI color code prefix on the line (`\x1b[33m` for warn, `\x1b[31m` for error). The Oracle document doesn't address whether stripping happens before or after format detection, or whether the format detector handles ANSI prefixes.

### Mixed-format streams from Kurtosis

Kurtosis's `service logs` command prepends its own metadata prefix to each log line (enclave name, container name, timestamp). The Oracle document doesn't mention this. These prefixes will cause format detection to fail (line starts with `[enclave-name]` not with `{` or `MMM-DD`). Both Sonnet and Oracle miss this, but it's a real issue.

### Truncated lines

Log files rotated mid-write may have truncated final lines. Interleaved Kurtosis streams may have byte-boundary cuts. The multiline merger will fail on truncated stack traces. The Oracle document has no `parse_error=true` handling path that preserves context for the agent.

---

## 8. Always-Surface Rules — Missing Patterns

**Confidence: HIGH**

### Critical gaps from real investigations

**Missing: `Error on head state regen`** (Investigation 5, EPBS state restart crash)  
The headState crash was characterized by `headState does not exist` and `Error on head state regen`. The Oracle rules section 1 mentions "Error on head state regen" but the YAML rule block doesn't include it. The text and the spec don't match.

**Missing: `BlsMultiThreadWorkerPool error`**  
Listed in the log-format-catalog as a critical error callsite. BLS failures mean no block signatures can be verified — the node is effectively dead. Absent from always-surface rules.

**Missing: `Published data columns to 0 peers` (PeerDAS)**  
Listed in the log-format-catalog under most common warnings. "0 peers received data columns" means the node is isolated from the PeerDAS network. High risk of reorg. Not in always-surface rules.

**Missing: Silence gaps as a primary signal**  
The "process lifecycle" rule mentions "silence gap > configurable threshold" but there's no YAML rule entry for it, no description of how gaps are detected (absence of `Imported block` for N expected slots), and no slot-duration-based calibration. Yet in Investigation 3 (EPBS devnet stall), the *absence* of block import logs was the primary diagnostic — the chain stopped at slot 49. A proper gap detector is more important than several of the listed rules.

**Missing: `Skipped slot due to task taking more than one slot to run` (validator)**  
Listed in the log-format-catalog under validator warnings. This is high priority for validator effectiveness — it means missed block proposals.

### Wrong threshold for timing anomalies

```
For mainnet-like 12s slots, start with warn if > 4s, critical if > 8s.
```

These are wrong for Lodestar's actual performance targets. Lodestar processes blocks in 100–500ms under normal conditions. A `recvToValLatency` of 4s is already a catastrophic failure, not a "warning." The thresholds should be:

- warn: > 1s (possible backpressure)
- critical: > 4s (confirmed congestion or resource exhaustion)

At > 8s (the proposed "critical" threshold), the node is already stalling attestations and likely missing blocks. The investigation data confirms this: `recvToValLatency=23.6s` was in the Investigation 1 failure case. With an 8s critical threshold, the first alert would have come only after the node was already failing.

For 1s devnet slots, the thresholds need to be 10× lower: warn > 0.1s, critical > 0.4s.

---

## 9. Dependencies — Install Risks

**Confidence: HIGH**

### `drain3` — the hidden dependency bomb

The Oracle document says:
```bash
pip install --user orjson requests zstandard drain3 tiktoken
```

`drain3` has this dependency chain:
```
drain3 → scipy → numpy (compiled C extension, ~200MB)
        → cachetools
        → jsonpickle
```

On a minimal server (CI node, Kurtosis host, lean VPS), `pip install --user drain3` will attempt to install `scipy` which is a 200MB compiled package. If no binary wheel exists for the target platform (arm64 Linux with older glibc, Alpine, or non-standard Python version), it will try to compile from source — which requires Fortran, BLAS, and LAPACK. This will fail loudly on most minimal servers.

**The fix:** make `drain3` import optional (it already is per the "optional Drain3 cluster id" language) and don't put it in the default install command. The document says drain3 is optional but installs it unconditionally.

### `orjson` — Rust compiler dependency

`orjson` is significantly faster than `json` but requires Rust to build from source if no binary wheel is available. This is a known issue on musl-libc targets (Alpine) and some arm64 configurations.

**The fix:** make it a soft dependency with `try: import orjson as json except: import json`. This is a 2-line change. The Oracle document doesn't mention this fallback anywhere.

### `zstandard` — binary extension

Similar issue to `orjson`. Usually has wheels, but fails on edge case platforms. `zst` files can also be read with Python's built-in `lzma` if renamed — but the document doesn't mention a fallback to uncompressed storage.

### `tiktoken` — Rust-backed tokenizer

`tiktoken` has Rust bindings. Usually has wheels. Fallback to `len // 4` is mentioned in the document but only as an aside ("tiktoken provides ... so render the pack, count tokens, then prune"). The actual fallback path isn't specified in the implementation.

### The install command is a lie

```bash
pip install --user orjson requests zstandard drain3 tiktoken
```

On a typical Kurtosis-hosting server (Ubuntu 22.04, Python 3.10, no Rust, no Fortran), this command may:
1. Install `orjson` cleanly ✅ (wheels available)
2. Install `requests` cleanly ✅
3. Install `zstandard` cleanly ✅ (wheels available)
4. Fail on `drain3` ❌ (scipy compile attempt)
5. Fail on `tiktoken` ❌ (Rust required if no wheel)

The document's claim "No GUI, no sudo, no extra services required" is true but obscures the risk of step 4 failing.

---

## 10. Oracle vs Sonnet: Direct Comparison

**Confidence: HIGH**

### Where Oracle is stronger

| Area | Oracle advantage |
|------|-----------------|
| **Exposure ledger** | Genuinely novel; prevents token waste on already-seen material. Sonnet has no equivalent. |
| **Cold-start scoring** | More principled than Sonnet's ad-hoc anomaly detection. The concept is right even if the formula needs work. |
| **Compare pack with service grouping** | Oracle's behavior-hash grouping for 6-node devnets is better than Sonnet's per-service triage. |
| **Reducer abstraction** | Oracle explicitly names reducers as first-class objects with a registry. Sonnet buries reduction in triage.py. |
| **Fidelity ladder** | Oracle's explicit "never skip from step 1 to step 5" is a clean mental model. Sonnet doesn't have this. |
| **Delta pack** | Oracle's delta concept is essential for long investigations. Sonnet's watch mode is LLM-free but lacks structured delta. |
| **Source cursor tracking** | Oracle tracks fetch cursors in SQLite. Sonnet's cursor is a flat JSON field. Oracle's is more robust for multi-source sessions. |

### Where Sonnet is simpler/more practical

| Area | Sonnet advantage |
|------|-----------------|
| **State resilience** | Sonnet's flat JSON state.json survives crashes, is grep-able, and explicitly designed around session compaction. Oracle's SQLite breaks post-compaction (see Section 3). |
| **Token budget realism** | Sonnet's estimates (8–15k for overview) match actual Lodestar log density. Oracle's tiny/small/medium profiles are 3–5× too small. |
| **Soak monitor** | Sonnet has `logreader soak` as a first-class command with acceptance-criteria output. Oracle doesn't have this at all — but it's used after every investigation fix (all 7 investigations). |
| **Dependencies** | Sonnet needs only `requests` + optional `drain3`. Oracle requires `orjson + zstandard + drain3 + tiktoken`. |
| **No-database state** | Sonnet's `/tmp/logreader/*.jsonl` approach is hackable, debuggable, and grep-able. |
| **Watch mode** | Sonnet's watch mode is explicitly LLM-free and designed for live streaming. Oracle conflates watch with delta. |
| **Two-pass pattern** | Sonnet's explicit "Pass 1: templates, Pass 2: raw lines" is cleaner than Oracle's pack hierarchy. |
| **Error recovery** | If Sonnet's normalize.py crashes, you lose that run. If Oracle's Stage 2 crashes mid-write to SQLite, the entire session may be corrupt. |
| **Compaction-aware design** | Sonnet's state.json explicitly records `findings` and `analyses_done` so a fresh agent can pick up where it left off. Oracle has no equivalent. |

### What the final design should take from each

**From Oracle:**
1. Exposure ledger concept (but in flat JSONL, not SQLite)
2. Cold-start scoring formula (simplified to 3 tiers, with the 3 undefined terms removed for v1)
3. Compare pack with service-grouping by behavior hash
4. Reducer abstraction as named objects
5. The fidelity ladder (counts → templates → context windows → raw lines)
6. Source cursor tracking per session

**From Sonnet:**
1. Flat file state instead of SQLite
2. Realistic token budget estimates (profiles 3k/8k/20k, not 600/1500/4000)
3. Soak monitor as first-class command (non-negotiable given real investigation patterns)
4. Explicit compaction-aware state.json with `findings` log
5. Watch mode as LLM-free streaming
6. Soft dependency on drain3 and tiktoken with fallbacks
7. Per-line format detection (handles Kurtosis mixed streams)

---

## 11. Summary: Ranked Issues by Risk

| # | Issue | Risk | Effort to fix |
|---|-------|------|---------------|
| 1 | Token budget profiles 3–5× too small | Renders tool nearly unusable | Low — just change the numbers |
| 2 | Exposure ledger breaks after compaction | Silent failure mode in the core differentiator | Medium — need reset command + compaction detection |
| 3 | `drain3` → `scipy` install bomb | Blocks installation on most servers | Low — make drain3 optional in install docs |
| 4 | `service_asymmetry` + `numeric_outlier` + `cross_layer_match` undefined | Scoring formula can't be implemented as written | Medium — define each or drop for v1 |
| 5 | SQLite schema for v1 | Brittle, hard to debug, overkill for a CLI tool | Medium — replace events/templates tables with JSONL |
| 6 | Missing silence gap detector | Misses the primary signal in chain-stall scenarios | Medium — slot-based gap detection |
| 7 | Missing execution bridge reducer | Misses EL-side signals in EPBS/interop bugs | Low — 50-line reducer |
| 8 | ANSI stripping before format detection | Format detection fails on colored Lodestar output | Low — reorder two lines |
| 9 | Timing thresholds too permissive (4s warn, 8s critical) | Alerts fire after the node is already failing | Low — change the constants |
| 10 | `orjson`/`tiktoken` missing soft-dependency fallbacks | Import error on edge-case platforms | Low — 2-line try/except |
| 11 | EpochSlot timestamp without genesis-time conversion | Silent time-correlation failures | Medium — needs genesis_time parameter |
| 12 | Kurtosis log prefix stripping missing | Format detection fails for kurtosis service logs output | Low — strip known prefix pattern |
| 13 | Missing `BlsMultiThreadWorkerPool error` in always-surface | Critical BLS failures go undetected | Trivial — add one rule |
| 14 | Missing `Published data columns to 0 peers` in always-surface | PeerDAS isolation undetected | Trivial — add one rule |
| 15 | No soak monitor command | Missing the most common post-fix validation workflow | Medium — lift from Sonnet design |

---

## Final Verdict

The Oracle design is the right architecture for a mature v2 skill. The two-plane model, exposure ledger, and compare-pack grouping are genuinely better ideas than the Sonnet equivalent. But it will not ship as written because of the token budget errors, dependency risks, and post-compaction failure mode.

**Recommended path:** Start with Sonnet's implementation approach (flat files, minimal deps, soak monitor included), layer in Oracle's conceptual additions (exposure ledger in flat JSONL, simplified scoring, reducer registry), and leave SQLite and the full scoring formula for v2 once the basic pipeline is validated against real sessions.

Do not start with SQLite. Start with JSONL. The first 20 debugging sessions will clarify what queries you actually need; then you'll know if SQLite is worth adding.
