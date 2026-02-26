# Research: Context Compaction Resilience & Memory Robustness

**Date:** 2026-02-26
**Requested by:** Nico
**Duration:** ~45 min (3 parallel sub-agents + synthesis)
**Confidence:** HIGH
**Models used:** Claude Opus 4.6 (orchestrator + sub-agents), web_search

## Executive Summary

Context compaction is the biggest threat to our operational continuity. When the 200K token window fills up, older conversation is summarized and tool outputs are lost. This happens most during heavy work — exactly when state is richest and most fragile.

Our current system (MEMORY.md + daily notes + BACKLOG.md + skills) is remarkably effective for a manual system: 25/25 days of daily notes, zero missed task entries when discipline holds. But it has three structural gaps: (1) no working memory file for "what I'm doing RIGHT NOW," (2) tool outputs are 100% ephemeral, and (3) the memory flush prompt is generic and fires too late.

The research identifies **3 tiers of improvements**, from config-only changes (deployable immediately) to new file patterns (need testing) to architectural proposals (longer-term).

## Problem Statement

When the context window fills (~200K tokens), OpenClaw:
1. Fires a silent "memory flush" turn (configurable, currently using defaults)
2. Summarizes older conversation into a compact entry
3. Keeps only recent messages after the cutoff

**What's lost:** All tool outputs (exec results, web fetches, sub-agent outputs), intermediate reasoning chains, in-flight async state (Oracle runs, background processes), and nuanced conversation context.

**When it's worst:** During heavy work sessions — high token usage means compaction hits sooner, but that's exactly when the most valuable state exists in context.

## Key Findings

### Finding 1: The Memory Flush Is Our Best Lever (and It's Underutilized)

OpenClaw already has a pre-compaction memory flush mechanism. It fires a silent agentic turn before compaction, telling the model to save state. But our config is all defaults:
- `softThresholdTokens: 4000` — flush fires only 4K tokens before compaction (very little time)
- Generic prompt: "Write any lasting notes to memory/YYYY-MM-DD.md"
- `reserveTokensFloor: 20000` — headroom for the flush turn

**The fix:** Increase the threshold to 8K tokens, customize the prompt to demand structured state dumps, increase reserve floor to 24K.

### Finding 2: Industry Convergence on File-Based Memory

Manus ($2B acquisition), Claude Code, Cline, Cursor, and OpenClaw independently converged on the same pattern: **plain Markdown files as durable memory.** This is the right architecture.

But the most successful implementations add a **working memory / scratchpad file** that captures current session state — something we lack.

### Finding 3: Three Structural Gaps

1. **No working memory file.** No "what am I doing RIGHT NOW" state dump. After compaction, must reconstruct from BACKLOG + daily notes + filesystem.
2. **Tool outputs are fire-and-forget.** The most information-dense artifacts (exec results, sub-agent outputs, Oracle responses) are the most ephemeral.
3. **Notes are retrospective.** Daily notes capture what happened, not what to do next. No resumption context.

### Finding 4: Context Pruning Is Not Configured

Session pruning (trimming old tool results from context before each LLM call) would extend session life before compaction triggers. Smart defaults may apply for Anthropic, but explicit adaptive pruning would be more aggressive and predictable.

## Proposed Changes

### Tier 1: Config Changes Only (Immediate, No Code)

These can be applied via `gateway config.patch`:

```json5
{
  agents: {
    defaults: {
      compaction: {
        mode: "safeguard",
        reserveTokensFloor: 24000,
        memoryFlush: {
          enabled: true,
          softThresholdTokens: 8000,
          systemPrompt: "CRITICAL: Session nearing compaction. You MUST persist all active work state to disk. Write a structured state dump covering: (1) current task and progress, (2) active PRs/branches, (3) decisions made this session, (4) pending items and blockers, (5) key file paths and next steps. Use memory/YYYY-MM-DD.md with clear headers.",
          prompt: "Pre-compaction memory flush. Store durable memories now (use memory/YYYY-MM-DD.md; create memory/ if needed). Include active task state, not just summaries. If nothing to store, reply with NO_REPLY."
        }
      },
      contextPruning: {
        mode: "cache-ttl",
        ttl: "5m",
        keepLastAssistants: 5,
        softTrim: { maxChars: 6000, headChars: 2500, tailChars: 2500 },
        hardClear: { enabled: true, placeholder: "[Older tool output cleared — re-read file if needed]" }
      }
    }
  }
}
```

**Impact:** HIGH. The custom flush prompt alone would dramatically improve state preservation. Pruning extends session life.

### Tier 2: New File Patterns (Behavioral, No Config)

#### 2a. Working Memory File (`STATE.md` or `.scratchpad.md`)

A workspace file that captures current session state. Updated continuously, read on every session resume.

```markdown
# STATE.md — Current Working State
Last updated: 2026-02-26 00:45 UTC

## Active Task
Building web scraping skill — Phase: testing auto_scrape.py

## In-Flight Operations
- Sub-agent `compaction-research` running (3 tasks)
- Cron: libp2p npm monitor (hourly)
- Cron: eth-rnd-archive hourly check

## Recent Decisions
- Use tiered architecture: curl_cffi → DynamicFetcher → Camoufox
- Trafilatura for text extraction (F1=0.958)

## Key File Paths
- ~/research/web-scraping-skill/findings/
- skills/web-scraping/SKILL.md
- skills/web-scraping/scripts/auto_scrape.py

## Next Steps
1. Synthesize Oracle consultation into skill
2. Test auto_scrape.py on CF-protected sites
3. Push to dotfiles
```

**Rules:**
- Update at start/end of each task phase
- Update before any long-running operation (Oracle, sub-agents)
- The memory flush prompt should explicitly reference this file

#### 2b. Learned Rules File (`learned-rules.md`)

Separate from MEMORY.md's "Lessons Learned" — a structured, categorized ruleset:

```markdown
# learned-rules.md — Accumulated Corrections

## Git
- Never force push (2026-02-01)
- Use merge, not rebase for upstream changes (2026-02-03)

## Communication
- Respond to ALL PR comments including bot reviewers (2026-02-14)
- Don't spam Discord with incremental updates (2026-02-09)

## Operations
- Always tee Oracle output to file (2026-02-26)
- BACKLOG entry BEFORE starting work (2026-02-20)
- Never delete gists without asking (2026-02-20)
```

#### 2c. Progressive Summarization of Daily Notes

Weekly consolidation pass: daily notes → weekly summary → MEMORY.md distillation.

```
memory/2026-02-24.md  ─┐
memory/2026-02-25.md  ─┤──→ memory/2026-W09-summary.md ──→ MEMORY.md updates
memory/2026-02-26.md  ─┘
```

### Tier 3: Architectural Proposals (Longer-Term)

#### 3a. Pre-Operation Checkpointing

Before any operation likely to consume lots of tokens (Oracle calls, multi-step investigations, sub-agent orchestration), automatically write a checkpoint:

```
Before: STATE.md updated with "about to run Oracle on X"
During: Output tee'd to file (existing rule)
After: STATE.md updated with results
```

This isn't automatic — it requires discipline. But making it part of the skill instructions (oracle-bridge, deep-research, dev-workflow) would help.

#### 3b. Session Memory Search

Enable OpenClaw's experimental session transcript indexing so past session context is searchable:

```json5
memorySearch: {
  experimental: { sessionMemory: true },
  sources: ["memory", "sessions"]
}
```

This would let the agent recall "what did I do last Tuesday?" by searching past session transcripts. Currently blocked by the fact we use `memory-lancedb` plugin, not `memory-core` — need to verify compatibility.

#### 3c. Workspace File Optimization

Every token in workspace files (AGENTS.md, TOOLS.md, MEMORY.md, etc.) counts against context budget every turn. Keeping them lean delays compaction.

Current workspace file audit needed:
- AGENTS.md: Is everything in there necessary?
- TOOLS.md: Growing — could some move to reference files?
- MEMORY.md: Lessons Learned section growing — could categorize and trim

## Risk Assessment

| Change | Risk | Impact | Effort |
|--------|------|--------|--------|
| Tune memory flush config | LOW | HIGH | 5 min |
| Enable context pruning | LOW | MEDIUM | 5 min |
| Add STATE.md pattern | LOW | HIGH | 30 min |
| Add learned-rules.md | LOW | MEDIUM | 30 min |
| Progressive summarization | LOW | MEDIUM | 1-2 hrs |
| Session memory search | MEDIUM | MEDIUM | 30 min |
| Workspace optimization | MEDIUM | LOW-MEDIUM | 1 hr |

## Open Questions

1. **Does `memory-lancedb` support session memory search?** If not, switching to `memory-core` + QMD might be worth it for the hybrid BM25+vector search and session indexing.
2. **How much context do workspace files consume?** Need to run `/context list` and audit actual token usage.
3. **Should STATE.md be a workspace file (always in context)?** Pro: always available. Con: adds to context budget every turn.
4. **Can we make checkpointing automatic?** A custom wrapper around long-running exec commands that auto-saves state before and after.

## Recommendations (Priority Order)

1. **[IMMEDIATE]** Tune memory flush config — bigger threshold, custom prompt
2. **[IMMEDIATE]** Enable explicit context pruning
3. **[THIS WEEK]** Start using STATE.md pattern — manual at first
4. **[THIS WEEK]** Restructure MEMORY.md Lessons Learned → learned-rules.md
5. **[NEXT WEEK]** Implement progressive summarization cron (weekly)
6. **[EVALUATE]** Session memory search compatibility with memory-lancedb
7. **[EVALUATE]** Workspace file token audit and optimization

## Sources

### Research Artifacts
- `findings/incident-audit.md` — Internal audit of compaction incidents and memory system gaps (18KB)
- `findings/openclaw-internals.md` — Deep dive into OpenClaw compaction/memory configuration (25KB)
- `findings/agent-memory-patterns.md` — Survey of 12+ agent frameworks' memory strategies (35KB)

### OpenClaw Docs
- `/concepts/compaction.md` — Compaction overview
- `/concepts/memory.md` — Memory file layout and search
- `/reference/session-management-compaction.md` — Session management deep dive
- `/concepts/session-pruning.md` — Tool result pruning

### Key Papers & References
- MemGPT (Packer et al., 2023) — OS-inspired tiered memory for LLMs
- Mem0 — Memory extraction, consolidation, and retrieval with graph store
- Reflexion (Shinn et al., 2023) — Self-learning feedback loops
- Generative Agents (Park et al., 2023) — Progressive memory consolidation
- Context Engineering (Karpathy, 2025) — "The art of filling the context window"
