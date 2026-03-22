# Log Reader Skill

Parse, index, and analyze Ethereum client logs (Lodestar, Geth, Nethermind, etc.) without reading raw log files. The tool produces compact **packs** — structured markdown reports sized for LLM context windows.

## When to Use

- Debugging a beacon node issue from Kurtosis devnet, Docker, or local logs
- Investigating a production incident with Loki-sourced logs
- Comparing behaviour across multiple services around a slot/time window
- Post-fix soak monitoring to verify a fix holds
- Any time you need to triage thousands of log lines into a few hundred tokens

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
$SKILL_DIR/scripts/logskill.sh fetch --session my-debug file --service lodestar-1 /path/to/node.log
$SKILL_DIR/scripts/logskill.sh fetch --session my-debug kurtosis --enclave kt-devnet --service cl-1-lodestar-geth
$SKILL_DIR/scripts/logskill.sh fetch --session my-debug docker --container lodestar-beacon --tail 50000
$SKILL_DIR/scripts/logskill.sh fetch --session my-debug loki --url http://loki:3100 --query '{app="lodestar"}' --since 2h

# 3. Build index (normalize + template mine + score)
$SKILL_DIR/scripts/logskill.sh build --session my-debug

# 4. Get overview pack (your starting point)
$SKILL_DIR/scripts/logskill.sh overview --session my-debug

# 5. Drill into specific templates, slots, or time windows
$SKILL_DIR/scripts/logskill.sh drill --session my-debug --template T001
$SKILL_DIR/scripts/logskill.sh drill --session my-debug --slot 49 --radius 5m
$SKILL_DIR/scripts/logskill.sh drill --session my-debug --time-start 2026-03-21T14:00:00Z --time-end 2026-03-21T14:05:00Z

# 6. Compare services around an incident
$SKILL_DIR/scripts/logskill.sh compare --session my-debug --anchor slot:49 --radius 2m

# 7. Live soak monitor (post-fix verification)
$SKILL_DIR/scripts/logskill.sh watch --session my-debug --source docker --container lodestar-beacon --interval 30
```

## Commands Reference

### `init <session_id>`
Create a session workspace under `~/.cache/logskill/sessions/<id>/`.

Options:
- `--root DIR` — override session root directory
- `--force` — reset if session already exists

### `fetch --session <id> <source> [args]`
Fetch raw logs into the session. Sources:

| Source | Key Args |
|--------|----------|
| `file` | `<path>` positional, `--service NAME` |
| `docker` | `--container NAME`, `--tail N`, `--since DURATION` |
| `kurtosis` | `--enclave NAME`, `--service NAME` |
| `loki` | `--url URL`, `--query LOGQL`, `--since DURATION`, `--start/--end ISO` |

Incremental: re-running fetch appends new records (cursor-based dedup).

### `build --session <id>`
Runs normalize → template mining → always-surface scan → reducer generation → 3-tier scoring.

### `overview --session <id> [--profile tiny|small|medium|large]`
Generate the cold-start triage pack. Contains:
- **Always-surface hits** — critical patterns that always appear (see `references/always_surface.yaml`)
- **Top templates** — ranked by severity score
- **Reducers** — status, imports, peers summaries per service
- **Timeline** — chronological event listing
- **Drill hints** — suggested follow-up commands

Profiles control token budget: tiny (~3k), small (~8k, default), medium (~20k), large (~40k).

### `drill --session <id> [filters]`
Deep-dive into specific log regions:
- `--template TXXX` — all events matching a template
- `--slot N [--radius DURATION]` — events around a slot
- `--time-start/--time-end ISO` — time window
- `--service NAME` — filter by service
- `--level LEVEL` — filter by level (error, warn, etc.)
- `--module MODULE` — filter by module prefix

### `compare --session <id> --anchor slot:N|time:ISO [--radius DURATION] [--services SVC1,SVC2]`
Cross-service comparison pack showing what each service was doing around an incident. Anchor can be `slot:N` or `time:ISO8601`.

### `watch --session <id> --source <docker|kurtosis|loki|file> [source-args] [--interval SEC] [--duration DURATION]`
Live soak monitor. Polls the source, normalizes, scans always-surface patterns, and prints alerts.
Exits on Ctrl-C or when `--duration` expires.

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
- **Nested error causes are never truncated**

## Supported Log Formats

| Format | Detection |
|--------|-----------|
| Lodestar human | `MMM-DD HH:mm:ss.SSS [MODULE] LEVEL: message` |
| Lodestar JSON | `{"timestamp","level","message","module","context"}` |
| Lodestar epoch | `Eph EPOCH/SLOT SECS [MODULE] LEVEL: message` |
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
reducers/           # reducer outputs (status, imports, peers)
packs/              # generated packs (overview, drill, compare)
```

## Workflow Pattern

1. **Start with overview** — get the lay of the land
2. **Follow drill hints** — dive into the highest-scored templates
3. **Compare services** — if multi-service, compare around the incident slot/time
4. **Check Grafana** — if overview finds nothing, check Prometheus/Grafana metrics (see `release-metrics` and `grafana-loki` skills)
5. **Soak watch** — after applying a fix, run `watch` to verify it holds

## Customization

### Always-Surface Patterns
Edit `references/always_surface.yaml` to add/remove patterns. Each pattern has:
- `id` — unique identifier
- `severity` — critical/high
- `match` — field/pattern/contains matching rules
- `label` — human-readable label
- `keep_fields` — fields to always include in output

### Token Profiles
Override with `--profile` on overview/drill/compare commands.

## Examples

Sample log files in `examples/`:
- `smoke-lodestar.log` — mixed Lodestar human + JSON format
- `smoke-geth.log` — Geth human format


## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.
