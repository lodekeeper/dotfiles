# Research: Log Reader Skill for Beacon Node Investigation

**Date:** 2026-03-21
**Requested by:** Nico
**Duration:** ~90 minutes
**Confidence:** HIGH (design) / MEDIUM (specific token estimates)
**Models used:** GPT-5.4 Pro (Oracle, architecture design × 2), Claude Sonnet 4.6 (sub-agents: web survey, format catalog, past investigations, alternative architecture, adversarial critique)

## Executive Summary

The log reader skill should be a **cache-first, session-based CLI tool** that sits between raw log sources and the AI agent. The agent never reads raw logs — it reads progressively smaller **packs** (overview → drill → compare → delta) built from a persistent normalized index. This solves both the context bloat problem AND the "I don't know what to look for" cold-start problem.

**Key design principles (from GPT-5.4 Pro):**
1. **Two-plane separation:** Data plane (fetch, normalize, index) has zero token cost. Agent plane (packs) has strict, predictable token budgets.
2. **Exposure tracking:** The skill remembers what the agent has already seen, so delta packs only show new information.
3. **Always-surface rules:** Hard-coded critical patterns bypass all filters and appear in every output.
4. **Progressive disclosure:** overview → hotspots → drill → raw (never skip steps).
5. **Reducers:** Domain-specific compressors turn 500 repeated lines into 1-3 diagnostic rows.

**What to build for v1 (practical synthesis):**
- Use flat JSONL files for storage (not SQLite — simpler, crash-safe, jq-debuggable)
- Implement 6 commands: `init`, `fetch`, `build`, `overview`, `drill`, `compare`
- Add `delta` and `watch` in v2
- Use Oracle's conceptual model (packs, exposure, reducers) with Sonnet's implementation approach (flat files, bash dispatcher, Python stages)

## Problem Statement

When debugging Ethereum beacon node issues, the AI agent faces a fundamental tension:
- **Debug logs are extremely verbose** — 50-200 lines/second from gossip alone at mainnet rates
- **The agent's context window is limited** — 200k tokens, shared with reasoning and code
- **The agent often doesn't know what to look for** — the cold-start problem
- **Missing a signal is worse than wasting tokens** — a missed error can mean hours of dead-end investigation

Current approach: `tail -500 | grep ERROR` — crude, misses subtle signals, no structured analysis.

## Research Findings

### Existing Tools & Patterns
- **Drain algorithm** (`drain3`) is the standard for extracting message templates from raw logs — groups variable log messages into stable clusters. Massive token saver.
- **Two-pass LLM pattern** (LogSage, LogSentinelAI): template report first, raw lines on demand. 10-50× cheaper than raw ingestion.
- **Loki + LogQL** is the right stack for production (we already use it). Supports server-side JSON extraction.
- Pre-filtering pipeline: raw → level filter → time window → field projection → dedup → LLM.

### Lodestar Log Characteristics
- **Human format (default):** `MMM-DD HH:mm:ss.SSS [MODULE]    LEVEL: message key=val, key=val`
- **JSON format:** `{"timestamp","level","message","module","context":{...},"error":{...}}`
- **10 top-level modules:** api, backfill, chain, execution, metrics, monitoring, network, vmon, rest, sync
- **Debug is 2.5× more call sites than info** — fires per-message in gossip, per-batch in sync
- **713 total log call sites** in beacon-node package
- **Network module alone** can produce 50-200 debug lines/second at mainnet rates

### Lessons from Real Investigations
- **Earliest signal often comes from EL, not CL** (EPBS chain stall: Geth's "old head" warning preceded Lodestar errors by 1 second)
- **Context fields are more diagnostic than message text** (`recvToValLatency=23.6s` was the single most useful field in the sync aggregate investigation)
- **Absence is a signal** — sync batch downloads dropping to 0/min indicates a stall
- **Nested error causes must NEVER be truncated** — the root cause is often buried 2-3 levels deep
- **Memory leaks are better tracked via metrics (Prometheus), not logs** — V8 heap flat + RSS growing = native leak

## Proposed Architecture

### Overview

```
sources (Loki / files / Docker / Kurtosis)
    ↓
[fetch] → raw cache (JSONL files, cursor tracking)
    ↓
[normalize] → normalized.jsonl (unified schema)
    ↓
[build] → templates.json + reducers + always-surface hits
    ↓
[overview/drill/compare/delta] → compact packs for agent consumption
```

### Skill Directory Layout

```
skills/log-reader/
├── SKILL.md                     # Agent instructions
├── scripts/
│   ├── logskill.sh              # Main CLI dispatcher
│   ├── fetch.py                 # Source adapters → raw JSONL
│   ├── normalize.py             # Format parsing → normalized JSONL
│   ├── build.py                 # Template mining + reducers + scoring
│   ├── overview.py              # Cold-start overview pack
│   ├── drill.py                 # Deep dive on template/slot/peer
│   ├── compare.py               # Cross-service comparison
│   ├── delta.py                 # Only-new-since-last-check (v2)
│   ├── watch.py                 # Live streaming monitor (v2)
│   └── state.py                 # Session state management
├── references/
│   ├── always_surface.yaml      # Critical patterns (never filtered)
│   ├── lodestar_rules.yaml      # Known Lodestar error patterns
│   ├── geth_rules.yaml          # Known Geth error patterns
│   └── prompts/                 # LLM analysis prompts by mode
└── examples/
    ├── cold_start.sh
    ├── kurtosis_devnet.sh
    └── production_loki.sh
```

### Session Workspace

```
~/.cache/logskill/sessions/<session-id>/
├── state.yaml                   # Session metadata, cursors, exposure log
├── raw/                         # Raw fetched logs (JSONL, one per source)
├── normalized.jsonl             # Unified normalized events
├── templates.json               # Template index with scores
├── reducers/                    # Reducer outputs (status.json, blocks.json, etc.)
└── packs/                       # Generated packs for agent consumption
    ├── overview-001.md
    ├── drill-t017.md
    └── compare-slot49.md
```

### Normalized Event Schema

```json
{
  "id": "e_8f3c...",
  "ts": "2026-03-21T14:03:11.201Z",
  "svc": "lodestar-1",
  "client": "lodestar",
  "fmt": "lodestar-human",
  "lvl": "error",
  "mod": "chain/blocks",
  "mod_top": "chain",
  "msg": "Failed to import block",
  "slot": 49,
  "epoch": 1,
  "peer": "16…a3b4f2",
  "root": "0x1234…5678",
  "err": "BLOCK_ERROR_INVALID_STATE_ROOT",
  "cause": "Parent block hash does not match",
  "ctx": {"parentInForkChoice": false},
  "raw_ref": {"file": "raw/lodestar-1.jsonl", "line": 918}
}
```

### Cold-Start Scoring (Simplified from Oracle)

The adversarial review showed Oracle's 9-term formula has 3 undefined terms. Use a simpler 3-tier ranking for v1:

**Critical (always surface):** Any match in `always_surface.yaml`
**Suspicious:** 
- Error or warn level
- Rate burst (>5× normal in a time bucket)
- Singleton or first-occurrence template
- Silence/gap (expected template drops to 0)
**Background:** Everything else, ranked by frequency

This captures 80% of diagnostic value. Add the full scoring formula in v2 after we have real-world calibration data.

### Always-Surface Patterns

These ALWAYS appear regardless of filters:

```yaml
# Consensus / Block Validation
- BLOCK_ERROR_* (any block validation error)
- PARENT_UNKNOWN / parentInForkChoice=false
- Error on head state regen
- headState does not exist

# Execution Bridge
- Execution client is offline / syncing
- JWT auth failure
- Error pushing notifyForkchoiceUpdate
- Ignoring beacon update to old head (Geth)

# Block Production
- produceBlock.*error
- payloadId=null
- Withdrawals mismatch
- Engine/Builder failed to produce block within cutoff

# Network Health
- Low peer count
- Network worker thread error
- discv5 has no boot enr

# Process Lifecycle
- panic / fatal / uncaught
- Silence gap > 2× expected slot time

# Timing Anomalies (configurable threshold)
- recvToValLatency > 4s (warn) / > 8s (critical) at 12s slots
- elapsed > slot_time
```

### Reducers (v1)

Domain-specific compressors that turn hundreds of repetitive lines into diagnostic summaries:

1. **Status reducer** — Collapse notifier/status lines into state changes + peer min/max + head lag
2. **Block import reducer** — Summarize imported slots, gaps, duplicate imports, import latency outliers
3. **Peer health reducer** — Low-peer periods, connect/disconnect churn, dominant peers
4. **ReqResp reducer** — Counts by method/peer, error rate, top failing peers, timeouts

### CLI Interface

```bash
# Initialize a session
logskill init epbs-stall-2026-03-21

# Fetch from various sources
logskill fetch kurtosis --enclave epbs-devnet-0 --services all --since 30m
logskill fetch loki --query '{job="beacon"}' --since 1h
logskill fetch file /var/log/lodestar.log --service lodestar-1
logskill fetch docker lodestar-bn-1 --since 15m

# Build index (normalize + templates + reducers)
logskill build

# Get cold-start overview (first thing agent reads)
logskill overview --profile small     # ~3-8k tokens

# Drill into specific template/slot/peer
logskill drill --template T017
logskill drill --slot 49 --radius 2m
logskill drill --peer 16Uiu2...

# Compare services around an incident
logskill compare --services lodestar-1,geth-1 --anchor slot:49

# Show session state
logskill status
```

### Token Budget (Revised from Adversarial Review)

Oracle's original profiles (600/1500/4000) were underestimated by 3-5×. Realistic profiles:

| Profile | Max tokens | Use case |
|---------|-----------|----------|
| tiny    | 3,000     | Quick delta check, single hotspot |
| small   | 8,000     | Standard overview, single drill |
| medium  | 20,000    | Full overview + multi-template drill |
| large   | 40,000    | Multi-service compare + deep analysis |

**Typical investigation session:** 20-40k tokens total across overview + 2-3 drills.
**Worst case:** 80k tokens (hard cap, never exceed).

### Source Selection Guide

| Situation | Source | Why |
|-----------|--------|-----|
| Production nodes | Loki | Server-side filtering, bounded windows, cross-node |
| Local Kurtosis devnet | Kurtosis | Direct access, multi-service snapshot |
| Local file (`--logFile`) | File | Full fidelity, offline re-analysis |
| Live container | Docker | Fast recent slice, before logs reach Loki |
| Memory leaks | Prometheus | NOT logs — use Grafana skill instead |

### Format Support

| Format | Parser | Detection |
|--------|--------|-----------|
| Lodestar human | Regex + KV split | `^[A-Z][a-z]{2}-\d{2} \d{2}:` |
| Lodestar JSON | `json.loads` | `^{"timestamp"` |
| Lodestar epoch/slot | Regex variant | `^Eph \d+/\d+` |
| Geth human | Regex + KV split | `^(INFO\|WARN\|ERRO)` |
| Geth JSON | `json.loads` | `^{"t"` |
| Besu/Nethermind | Java multiline | Header + continuation |
| Generic | Best-effort | Fallback |

### Multiline Stack Trace Handling

A new event starts only when a line matches a known header pattern. Otherwise append to previous event's stack/continuation field. **Nested error causes are NEVER truncated** — this is where root causes live.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Token estimates wrong | Medium | High | Hard cap enforced by budget manager |
| Always-surface patterns miss real errors | Low | High | Start comprehensive, add patterns from investigations |
| Parser fails on unexpected format | Medium | Medium | Generic fallback, parse_error flag |
| Session state lost to disk cleanup | Medium | Medium | Warn if /tmp used; default to ~/.cache |
| Reducers produce misleading summaries | Low | Medium | Keep raw_ref pointers for verification |
| Cold-start ranking surfaces noise | Medium | Low | 3-tier ranking simpler than scored formula |

## Cheap LLM Triage Layer — Research Conclusion

**Verdict: Skip for v1. Add as opt-in `--semantic-triage` flag in v2 if real investigations reveal gaps.**

GPT-5.4 Pro recommended "yes, but narrowly" — a post-template annotation stage using Haiku/Flash. The devil's advocate (Opus) argued against it convincingly:

1. **The 8k overview pack is already 4% of context** — Opus can read it directly with zero strain
2. **5 of 6 "LLM-only capabilities" are already covered** by deterministic components (template mining, always-surface rules, reducers, scoring, candidate pivots)
3. **For Lodestar specifically, the module field IS the semantic category** — we don't need an LLM to classify `[chain]` vs `[network]`
4. **False positive cost is debugging time, not tokens** — Haiku hallucinating "suspicious" wastes engineering hours
5. **Legitimate narrow cases exist:** unfamiliar client logs (Besu/Nethermind Java-style), completely novel error patterns not in always-surface YAML

**If added in v2:** Post-template annotation only, opt-in via `--semantic-triage`, configurable model, with deterministic pipeline results always shown first (LLM annotations are additive, never replace).

## Design Stress-Test Conclusions

From the adversarial review:

1. **Add soak monitor to v1** — every investigation ends with "verify fix over N clean slots." Without it, the tool covers diagnosis but not validation (half the workflow).
2. **Exposure ledger needs reset mechanism** — breaks silently after session compaction. For v1: use simple cursor-based tracking (last timestamp seen per source), not a full exposure database.
3. **Add "not in logs" escape hatch** — when overview finds nothing, explicitly suggest checking Prometheus/Grafana. Memory leaks, performance regressions, and resource exhaustion don't show in logs.
4. **Minimum viable commands:** `fetch + build + overview` (3 commands). Everything else can be deferred.
5. **Skip SQLite for v1** — flat JSONL + state.yaml is sufficient and more debuggable.

## Open Questions (Remaining)

1. **Drain3 dependency:** Useful for noisy Geth/Besu logs but pulls scipy (200MB). Worth it for v1, or use simple groupby(message) as fallback?
2. **Cross-layer correlation:** Matching CL events with EL events by timestamp is the highest-value but hardest feature. Target v2.
3. **LLM analysis integration:** Overview produces the pack; the agent (me) decides what to do with it. No LLM calls inside the tool for v1.

## Recommended Implementation Order

1. **fetch.py** — Source adapters (Kurtosis first, then file, Docker, Loki)
2. **normalize.py** — Format parsers (Lodestar human first, then JSON, Geth)
3. **build.py** — Template mining + always-surface scan + basic reducers
4. **overview.py** — Cold-start pack generator
5. **drill.py** — Template/slot/time drill-down
6. **compare.py** — Multi-service comparison
7. **logskill.sh** — CLI dispatcher wrapping all stages
8. **SKILL.md** — Agent instructions

**Estimated implementation time:** 2-3 days for a functional v1 with Codex CLI.

## Sources

- GPT-5.4 Pro (Oracle): 2 architecture design sessions
- Claude Sonnet 4.6: 5 sub-agent sessions (web survey, format catalog, past investigations, alternative architecture, adversarial critique)
- Lodestar source: `~/lodestar/packages/logger/`, `packages/beacon-node/`
- Past investigations: libp2p identify, EPBS chain stall, sync aggregate, memory leaks, fork choice regression
- LogSage, LogSentinelAI, Drain3, Salesforce LogAI (web survey)
- Grafana Loki documentation, Kurtosis documentation
