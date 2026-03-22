# Log Reader Skill — Implementation Context

## What to Build
A CLI log analysis tool for an AI agent that debugs Ethereum beacon nodes. The agent never reads raw logs — it reads compact "packs" built from a normalized index.

## Architecture
Read the full design: `~/research/log-reader-skill/output.md`

Key research findings:
- `~/research/log-reader-skill/findings/oracle-architecture.md` — GPT-5.4 Pro architecture (primary)
- `~/.openclaw/workspace/research/log-reader-skill/findings/pipeline-architecture.md` — Sonnet architecture (supplementary)
- `~/research/log-reader-skill/findings/oracle-llm-triage.md` — LLM triage research (SKIP for v1)
- `~/.openclaw/workspace/research/log-reader-skill/findings/devils-advocate.md` — stress-test findings

## v1 Scope (implement these)

### Commands (priority order)
1. **fetch.py** — Source adapters: Kurtosis (`kurtosis service logs`), local file, Docker (`docker logs`), Loki (HTTP API)
2. **normalize.py** — Format parsers: Lodestar human-readable, Lodestar JSON, Geth human, Geth JSON, generic fallback
3. **build.py** — Template mining (groupby module+message), always-surface scan, basic reducers, 3-tier scoring
4. **overview.py** — Cold-start pack generator (triage report with always-surface hits, template ranking, timeline, drill hints)
5. **drill.py** — Deep dive on specific template/slot/time window
6. **compare.py** — Cross-service comparison around an incident
7. **watch.py** — Live soak monitor for post-fix verification
8. **logskill.sh** — Bash CLI dispatcher wrapping all stages

### Data Model
Normalized event schema (JSONL):
```json
{
  "id": "e_<hash>",
  "ts": "ISO8601",
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
  "ctx": {},
  "raw_ref": {"file": "raw/lodestar-1.jsonl", "line": 918}
}
```

### Session workspace
```
~/.cache/logskill/sessions/<session-id>/
├── state.yaml          # metadata, cursors, config
├── raw/                # raw fetched logs (JSONL per source)
├── normalized.jsonl    # unified events
├── templates.json      # template index with scores
├── reducers/           # reducer outputs
└── packs/              # generated packs
```

### Storage: flat JSONL + state.yaml (NO SQLite for v1)

### Always-surface patterns: see `references/always_surface.yaml`

### Token budgets (revised):
- tiny: 3,000 tokens
- small: 8,000 tokens  
- medium: 20,000 tokens
- large: 40,000 tokens

### Key design rules:
1. Agent never reads raw logs — only packs
2. Always-surface patterns bypass ALL filters
3. Nested error causes are NEVER truncated
4. Multiline stack traces merged into parent event
5. Template mining uses groupby(module, message) — Drain3 is optional
6. When overview finds nothing, suggest checking Prometheus/Grafana
7. Each stage has predictable token cost
8. No LLM calls inside the tool (v1)

### Format parsers needed:
- Lodestar human: `MMM-DD HH:mm:ss.SSS [MODULE]    LEVEL: message key=val, key=val`
- Lodestar JSON: `{"timestamp","level","message","module","context":{...}}`
- Lodestar epoch/slot: `Eph EPOCH/SLOT_INDEX SECS [MODULE]...`
- Geth human: `INFO [MM-DD|HH:MM:SS.mmm] message key=value`
- Geth JSON: `{"t","lvl","msg",...}`
- Generic fallback: best-effort timestamp + level + message extraction

### Dependencies (pip install --user):
- requests (Loki HTTP API)
- pyyaml (state.yaml)
- NO drain3 (pulls scipy), NO orjson, NO tiktoken for v1
- Token estimation: len(text) // 4

### Pre-push checklist:
- `python3 -m py_compile <file>` for every .py file
- Test with sample Lodestar logs
- Verify always_surface.yaml patterns match real error strings

## Lodestar Log Format Details
See `~/research/log-reader-skill/findings/log-format-catalog.md` for comprehensive format documentation including:
- Module names (LoggerModule enum)
- Log level hierarchy
- Context field patterns (slot, blockRoot, peer, etc.)
- Common error/warning messages
- Debug verbosity characteristics
