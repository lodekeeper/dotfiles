---
name: log-reader
description: Parse, index, and analyze Ethereum client logs (Lodestar, Lighthouse, Geth) without reading raw log files. Produces compact overview packs for triage, drill packs for deep-dives, and cross-service comparison packs. Best for first-pass breadth triage on unfamiliar logs and multi-client correlation. For targeted "find error X" debugging, use grep directly.
version: 1.1.0
author: lodekeeper
tags: [ethereum, logs, debugging, lodestar, lighthouse, geth, kurtosis, docker]
related_skills: [grafana-loki, kurtosis-devnet, local-mainnet-debug, beacon-node]
---

# Log Reader Skill

Parse, index, and analyze Ethereum client logs (Lodestar, Geth, Nethermind, etc.) without reading raw log files. The tool produces compact **packs** — structured markdown reports sized for LLM context windows.

## When to Use vs Grep

| Scenario | Best Tool |
|----------|-----------|
| First-pass triage on unfamiliar logs | **Skill overview** (~1.5K tokens for 100K lines) |
| "How many X errors?" quick count | **Grep** (faster, cheaper) |
| Multi-service correlation around an incident | **Skill compare** |
| Targeted "find events matching pattern" | **Grep** |
| Post-fix soak monitoring | **Skill watch** |
| Understanding what happened chronologically | **Skill overview** (timeline + reducers) |

**Best workflow:** Skill overview for triage → grep for targeted follow-up → skill compare for multi-client correlation.

## Prerequisites

```bash
pip install --user pyyaml requests  # one-time
```

## Quick Start

All commands use the dispatcher script at `scripts/logskill.sh` (resolve relative to this skill's directory).

```bash
SKILL_DIR="$(dirname "$(realpath SKILL.md)")"

# 1. Create a session
$SKILL_DIR/scripts/logskill.sh init my-debug

# 2. Fetch logs (pick one source)
$SKILL_DIR/scripts/logskill.sh fetch --session my-debug file /path/to/node.log --service lodestar-1
$SKILL_DIR/scripts/logskill.sh fetch --session my-debug docker lodestar-beacon --since 30m
$SKILL_DIR/scripts/logskill.sh fetch --session my-debug kurtosis --enclave kt-devnet --services cl-1-lodestar-geth
$SKILL_DIR/scripts/logskill.sh fetch --session my-debug loki --url http://loki:3100 --query '{app="lodestar"}' --since 2h

# 3. Build index (normalize + template mine + score)
$SKILL_DIR/scripts/logskill.sh build --session my-debug

# 4. Get overview pack (your starting point)
$SKILL_DIR/scripts/logskill.sh overview --session my-debug --profile medium

# 5. Drill into specific templates, slots, or time windows
$SKILL_DIR/scripts/logskill.sh drill --session my-debug --template T001
$SKILL_DIR/scripts/logskill.sh drill --session my-debug --slot 49 --radius 5m
$SKILL_DIR/scripts/logskill.sh drill --session my-debug --start 2026-03-21T14:00:00Z --end 2026-03-21T14:05:00Z

# 6. Compare services around an incident
$SKILL_DIR/scripts/logskill.sh compare --session my-debug --anchor slot:49 --radius 2m

# 7. Live soak monitor (post-fix verification)
$SKILL_DIR/scripts/logskill.sh watch --session my-debug docker lodestar-beacon --poll 30
```

## Commands Reference

### `init <session_id>`
Create a session workspace under `~/.cache/logskill/sessions/<id>/`.

Options:
- `--root DIR` — override session root directory
- `--force` — reset if session already exists

### `fetch --session <id> <source> [args]`
Fetch raw logs into the session. Sources:

| Source | Syntax | Key Args |
|--------|--------|----------|
| `file` | `fetch file <path>` | `--service NAME` |
| `docker` | `fetch docker <container>` | `--since DURATION`, `--until TIMESTAMP` |
| `kurtosis` | `fetch kurtosis` | `--enclave NAME`, `--services NAME[,NAME]` or `all` |
| `loki` | `fetch loki` | `--url URL`, `--query LOGQL`, `--since DURATION`, `--start/--end ISO` |

Incremental: re-running fetch appends new records (cursor-based dedup).

### `build --session <id>`
Runs normalize → template mining → always-surface scan → reducer generation → 3-tier scoring.

Scoring priorities:
1. **Critical** — always-surface rules matched
2. **Suspicious** — error/warn levels, error causes, bursts, singletons
3. **Background** — normal operations (block processing, peer discovery churn)

Normal operation patterns (block imports, peer discovery, req/resp lifecycle) are automatically demoted to background even if they burst during sync.

### `overview --session <id> [--profile tiny|small|medium|large]`
Generate the cold-start triage pack. Contains:
- **Always-surface hits** — critical patterns that always appear
- **Top templates** — ranked by severity score, with error type breakdown inline
- **Reducers** — status (peer count, head slot), imports (gaps, duplicates), peers (connect/disconnect), reqresp (error types)
- **Timeline** — chronological notable events (deduplicated)
- **Drill hints** — suggested follow-up commands

Profiles control token budget: tiny (~3k), small (~8k, default), medium (~20k), large (~40k).

### `drill --session <id> [filters]`
Deep-dive into specific log regions:
- `--template TXXX` — all events matching a template
- `--slot N [--radius DURATION]` — events around a slot
- `--peer PEER_ID` — events involving a specific peer
- `--start/--end ISO` — time window
- `--service NAME` — filter by service
- `--limit N` — max events to render (default: 200)

### `compare --session <id> --anchor slot:N|time:ISO [--radius DURATION] [--services SVC1,SVC2]`
Cross-service comparison pack showing what each service was doing around an incident. Anchor can be `slot:N` or `time:ISO8601`.

### `watch --session <id> <source> [source-args] [--poll SEC] [--cycles N]`
Live soak monitor. Polls the source, normalizes, scans always-surface patterns, and prints alerts.

Source subcommands match `fetch` syntax:
- `watch docker <container> [--since DURATION]`
- `watch file <path>`
- `watch kurtosis --enclave NAME --services NAME`
- `watch loki --url URL --query LOGQL [--since DURATION]`

Options:
- `--poll SEC` — polling interval (default: 5s)
- `--status-every SEC` — status line interval (default: 30s)
- `--cycles N` — max polling cycles before exit

### `status --session <id>`
Show session state (sources, raw files, artifacts, cursors).

## Architecture

```
raw logs → fetch → raw/*.jsonl → normalize → normalized.jsonl → build → templates.json + reducers/
                                                                              ↓
                                                           overview/drill/compare → packs/*.md
```

- **No raw log reading** — the agent reads only packs (structured markdown)
- **No LLM calls** — all analysis is deterministic (v1)
- **Always-surface patterns** bypass all filters (defined in `references/always_surface.yaml`)
- **3-tier scoring**: critical (always-surface/error/singleton) → suspicious → background
- **Normal operation demotion** — block processing pipeline, peer discovery churn, and routine req/resp events stay background even during sync bursts
- **Error type breakdown** — overview includes top error types per template inline
- **Nested error causes are never truncated**

## Supported Log Formats

| Format | Detection |
|--------|-----------|
| Lodestar human | `MMM-DD HH:mm:ss.SSS [MODULE] LEVEL: message` |
| Lodestar JSON | `{"timestamp","level","message","module","context"}` |
| Lodestar epoch | `Eph EPOCH/SLOT SECS [MODULE] LEVEL: message` |
| Lighthouse human | `Mon DD HH:MM:SS.mmm LEVEL message` |
| Geth human | `LEVEL [MM-DD\|HH:MM:SS.mmm] message key=val` |
| Geth JSON | `{"t","lvl","msg",...}` |
| Generic fallback | Best-effort timestamp + level + message extraction |

## Session Data

Sessions live under `~/.cache/logskill/sessions/<id>/`:
```
state.yaml          # metadata, cursors, config
raw/                # raw fetched logs (JSONL per source)
normalized.jsonl    # unified events
templates.json      # template index with scores
reducers/           # reducer outputs (status, imports, peers, reqresp, timeline)
packs/              # generated packs (overview, drill, compare)
```

## Workflow Pattern

1. **Start with overview** — get the lay of the land (~1.5K tokens)
2. **Use grep for targeted follow-up** — drill packs are expensive (~27K tokens); grep is 50× cheaper for "find pattern X"
3. **Compare services** — if multi-service, compare around the incident slot/time
4. **Check Grafana** — if overview finds nothing, check Prometheus/Grafana metrics (see `release-metrics` and `grafana-loki` skills)
5. **Soak watch** — after applying a fix, run `watch` to verify it holds

## Customization

### Always-Surface Patterns
Edit `references/always_surface.yaml` to add/remove patterns. Each pattern has:
- `id` — unique identifier
- `severity` — critical/high
- `match` — field/pattern/contains/gt matching rules (supports `any` for OR logic)
- `label` — human-readable label
- `keep_fields` — fields to always include in output

### Token Profiles
Override with `--profile` on overview command:
- `tiny` — ~3K tokens (minimal summary)
- `small` — ~8K tokens (default, good for most investigations)
- `medium` — ~20K tokens (detailed, includes more templates and timeline)
- `large` — ~40K tokens (comprehensive, for complex multi-service incidents)

## Examples

Sample log files in `examples/`:
- `smoke-lodestar.log` — mixed Lodestar human + JSON format
- `smoke-geth.log` — Geth human format


## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.
