# Design Brief: Log Reader Skill for AI Agent

## Context
I'm an AI agent (Lodekeeper) that debugs Ethereum beacon node issues. I read logs from Lodestar (TypeScript CL client), EL clients (Geth, Nethermind), and multi-client Kurtosis devnets. My biggest operational challenge is reading verbose debug logs without either:
- **Bloating my context** (I have 200k token limit, and logs at debug level can produce 100k+ lines/hour)
- **Missing critical signals** (especially when I don't know what I'm looking for yet — the "cold start" problem)

## The Core Design Challenge
When investigating a bug, I often don't know what to grep for. The important signal might be an error 2000 lines back, a timing anomaly, a specific peer ID, or a pattern across multiple modules. A simple `grep ERROR` misses subtle issues. But ingesting raw debug logs burns my entire context window in minutes.

## What I Need You To Design
A multi-stage log analysis pipeline that an AI agent can use as a reusable skill. The pipeline should have these properties:

1. **Progressive disclosure** — start broad (overview/summary), drill into specifics on demand
2. **Format-agnostic** — handle both human-readable and JSON Lodestar logs, plus Geth/EL logs
3. **Cold-start capable** — useful even when I don't know what I'm looking for
4. **Token-budget aware** — each stage should have a predictable token cost
5. **Stateful** — remember what I've already looked at so I don't re-ingest
6. **Multi-source** — handle Kurtosis (multiple services), docker logs, Loki, local files

## Constraints
- Must work as CLI tools I can call from my agent session (bash scripts, Python)
- Must run on a Linux server (no GUI)
- Dependencies should be minimal and installable without sudo (pip, npm)
- Lodestar human-readable format: `MMM-DD HH:mm:ss.SSS [MODULE]    LEVEL: message key=val, key=val`
- Lodestar JSON format: `{"timestamp","level","message","module","context":{...}}`
- Geth format: `INFO [10-04|10:20:52.028] message key=value`
- I have access to Grafana Loki for production nodes (LogQL queries)
- Kurtosis logs via `kurtosis service logs <enclave> <service>`

## My Real Experience (attached findings)
The attached file contains:
1. A web survey of existing log analysis tools and AI-assisted approaches
2. A detailed catalog of Lodestar's log formats, modules, and verbosity characteristics
3. Analysis of 7 real debugging investigations I've done, with what worked and failed

## What I Want From You
Design the complete pipeline architecture. For each stage:
- What it does
- Input/output format
- Expected token cost
- CLI interface (how I'd invoke it)
- What tools/libraries to use

Also address:
- How to handle the "cold start" problem (don't know what to look for)
- How to handle multi-service logs (Kurtosis with 4+ nodes)
- How to balance summary fidelity vs token cost
- When to use Loki vs local log files vs docker logs
- How the skill should be structured (files, entry points, configuration)
- Error patterns that should ALWAYS be surfaced regardless of filter settings

Be specific and practical. I'll be implementing this, so I need concrete designs, not abstract principles.
