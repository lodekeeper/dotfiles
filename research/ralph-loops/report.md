# Deep Research: Ralph Loops & Autonomous Agent Loop Tools

**Date:** 2026-03-01
**Requested by:** Nico
**Context:** Evaluate the Ralph loop pattern and tools in the ecosystem. Assess relevance to Lodekeeper's current workflow.

---

## TL;DR

The Ralph loop is a simple but powerful pattern: run an AI coding agent in a bash loop with a task list, let it pick the next task, implement it, verify (typecheck/test/lint), commit, and repeat until done. Memory persists via files + git, not conversation context. This directly addresses context window rot.

**My verdict:** The core *pattern* is highly relevant — I should adopt it. The specific *tools* (snarktank/ralph, etc.) are designed for humans wrapping CLI tools; they don't fit cleanly into an AI-as-orchestrator setup like mine. But the ideas map directly onto improvements I can make to my existing coding-agent workflow.

---

## 1. The Ralph Loop Pattern

**Origin:** Geoffrey Huntley ([ghuntley.com/ralph](https://ghuntley.com/ralph/), Jan 2026). Named after Ralph Wiggum from The Simpsons. The core insight: context windows degrade on complex tasks, so treat each iteration as a fresh instance. State lives in files, not in the LLM's memory.

**The essence:**
```bash
while true; do
  claude-code "Read prd.json. Pick highest-priority unfinished story. Implement it. Run tests. Commit if green. Update progress.txt. Output <promise>COMPLETE</promise> when all done."
done
```

**Key principles:**
1. **Monolithic** — Single agent, single repo, single task per loop iteration. Not multi-agent. Not microservices.
2. **Fresh context each iteration** — No context rot. The agent discovers state from files + git.
3. **File-based state** — `prd.json` (task list), `progress.txt` (learnings), `AGENTS.md` (conventions), git history.
4. **Feedback loops are mandatory** — Typecheck, tests, lint. Without them, errors compound across iterations.
5. **Right-sized stories** — Each task must fit in one context window. "Add a filter dropdown" yes, "Build the dashboard" no.

**Huntley's evolution levels:**
- **Level 7:** Ralph loop — single agent, single repo, iterative
- **Level 8:** Gas Town (Steve Yegge) — multi-agent coordination, workspace management
- **Level 9:** Loom (Huntley, private) — "evolutionary software factory", autonomous product optimization

---

## 2. Tool Landscape

### 2.1 snarktank/ralph (canonical)
- **Backends:** Amp, Claude Code
- **State:** prd.json (stories with passes:true/false), progress.txt, git
- **Features:** PRD skill (generates requirements), Ralph skill (converts to JSON), auto-archive, AGENTS.md learning
- **Stars:** High adoption, the reference implementation
- **Fit for us:** Low. Designed for humans at a terminal. We don't need the bash wrapper.

### 2.2 frankbria/ralph-claude-code
- **Backends:** Claude Code only
- **State:** Same pattern + session continuity (--resume)
- **Features:** Dual-condition exit gate, rate limiting (100 calls/hr), circuit breaker, error detection, response analyzer, tmux monitoring, live streaming, PRD import
- **Tests:** 566 tests (impressive for a loop wrapper)
- **Fit for us:** Medium. The circuit breaker and rate limiting ideas are worth stealing. The exit detection is relevant — knowing when "done" is "actually done."

### 2.3 Th0rgal/open-ralph-wiggum
- **Backends:** Claude Code, Codex, Copilot CLI, OpenCode
- **Features:** Multi-agent switching (--agent flag), task tracking (--tasks), live monitoring (--status), mid-loop hints (--add-context)
- **Fit for us:** Medium. The `--add-context` (inject hints without stopping) maps to what OpenClaw's `sessions_send` already does.

### 2.4 mikeyobrien/ralph-orchestrator (most feature-rich)
- **Backends:** Claude Code, Kiro, Gemini CLI, Codex, Amp, Copilot CLI, OpenCode
- **Written in:** Rust (CLI) + React (web dashboard)
- **Features:** 31 presets (TDD, spec-driven, debugging), "hat system" (specialized personas), backpressure gates, persistent memories, work tracking (beads), web dashboard, **Telegram integration** (agents can ask humans questions mid-loop)
- **Fit for us:** High conceptually. The hat system = my reviewer personas. The Telegram integration = what I already have. The presets = codified workflows.

### 2.5 vercel-labs/ralph-loop-agent
- **Runtime:** AI SDK (programmatic, not CLI)
- **Features:** Programmatic verification functions, stop conditions (iteration count, tokens, cost), context summarization for long loops, streaming support
- **Fit for us:** High conceptually. The `verifyCompletion` callback pattern is exactly right — define what "done" means programmatically (files exist, tests pass, lint clean), loop until satisfied.

### 2.6 steveyegge/gastown (Gas Town)
- **Scope:** Multi-agent workspace manager, NOT a loop tool
- **Architecture:** Mayor (coordinator) → Rigs (project containers) → Polecats (worker agents) + Hooks (git-backed persistent storage) + Beads (work tracking units)
- **Backends:** Claude Code, Codex
- **Features:** Agent mailboxes, identities, handoffs, git worktree-based persistence, scales to 20-30 agents, Dolt (versioned DB) for state
- **Fit for us:** Medium-high. Gas Town's architecture is remarkably similar to my setup: coordinator (me/Mayor), workers (Codex/Claude CLI / Polecats), git worktrees (Rigs), task tracking (BACKLOG.md / Beads). But it's designed for Claude Code instances, not OpenClaw.

### 2.7 Other notable tools
- **`afk` CLI** — Tool-agnostic Ralph wrapper. Fresh instances, git-based memory, quality gates.
- **ralphy** — Multi-tool (Claude Code, Codex, OpenCode, Cursor, Qwen, Droid). Simple.
- **Cubic** — AI code review tool, pairs with Ralph loops.

---

## 3. Comparison with Lodekeeper's Current Workflow

| Aspect | Ralph Loop Pattern | My Current Workflow | Gap? |
|---|---|---|---|
| **Task decomposition** | prd.json (structured stories) | BACKLOG.md (free-form markdown) | Moderate — my task tracking is less structured |
| **Fresh context per iteration** | Each loop spawns fresh CLI instance | Each `codex exec` / `claude exec` is fresh | ✅ Already doing this |
| **File-based state** | progress.txt + prd.json + AGENTS.md | memory/ + bank/ + BACKLOG.md + CODING_CONTEXT.md | ✅ My system is richer |
| **Feedback loops** | Typecheck + test + lint per iteration | Available but not automated in the loop | ❌ **Key gap** — I don't auto-retry on failure |
| **Autonomous completion** | Loops until all stories pass | Single-shot — I check and re-prompt | ❌ **Key gap** — no set-and-forget |
| **Learning across iterations** | progress.txt, AGENTS.md updates | Daily notes, MEMORY.md, QMD | ✅ My system is richer |
| **Multi-agent coordination** | Gas Town only; Ralph is single-agent | OpenClaw sessions, sub-agents, crons | ✅ Already multi-agent |
| **Communication** | Terminal only (ralph-orchestrator has Telegram) | Telegram + Discord + sub-agent messaging | ✅ Already better |
| **Exit detection** | `<promise>COMPLETE</promise>` token | None — I decide manually | ❌ Gap |
| **Rate limiting / circuit breaker** | frankbria has this | None | ⚠️ Minor gap |

### Key Gaps (what Ralph does that I don't):

1. **Auto-retry on verification failure.** When I spawn Codex CLI, it runs once. If tests fail, I have to notice, diagnose, and re-prompt. Ralph just loops — feed failures back as context, try again.

2. **Autonomous completion for well-scoped tasks.** I'm the bottleneck. Every implementation task requires my attention to check completion and decide next steps. Ralph eliminates the human/orchestrator in the loop for well-defined work.

3. **Structured task state.** My BACKLOG.md is prose. Ralph's prd.json has `passes: true/false` per story — machine-readable, verifiable.

### What I already have that Ralph doesn't:

1. **Rich memory system** — QMD hybrid search, SQLite FTS, entity pages, nightly consolidation. Ralph has progress.txt. I win by a mile.
2. **Multi-channel presence** — Telegram, Discord, webhooks. Ralph is terminal-only.
3. **GitHub integration** — Notification monitoring, PR management, CI tracking.
4. **Sub-agent orchestration** — Multiple models (GPT-5.3, Gemini, Claude), specialized reviewers.
5. **Monitoring infrastructure** — Grafana, Loki, release metrics.
6. **Persistent identity** — I'm a long-running agent with history, not a bash script.

---

## 4. Recommendations

### 4.1 Adopt the loop pattern for implementation tasks (HIGH VALUE)

Add a "ralph mode" to my coding-agent workflow. When I delegate to Codex/Claude CLI:

```bash
# Instead of single-shot:
codex exec --full-auto "implement feature X"

# Ralph-style loop:
for i in $(seq 1 $MAX_ITERATIONS); do
  codex exec --full-auto "
    Read TASK.md for requirements.
    Read PROGRESS.md for what's done.
    Implement the next item.
    Run: pnpm check-types && pnpm lint && pnpm test:unit
    If all pass, commit and update PROGRESS.md.
    If all stories done, write COMPLETE to PROGRESS.md.
  "
  if grep -q "COMPLETE" PROGRESS.md; then break; fi
done
```

This eliminates me as the bottleneck for well-defined implementation work.

### 4.2 Add structured task state (MEDIUM VALUE)

For complex features, create a machine-readable task file alongside BACKLOG.md:

```json
// task.json
{
  "feature": "EIP-7782 6-second slots",
  "stories": [
    {"id": "1", "title": "Update slot timing constants", "passes": false},
    {"id": "2", "title": "Add fork-aware scheduling", "passes": true},
    {"id": "3", "title": "Update validator timing", "passes": false}
  ]
}
```

### 4.3 Implement verification gates (HIGH VALUE)

Define what "done" means for each task type:
- **Implementation:** `pnpm check-types && pnpm lint && pnpm test:unit`
- **Bug fix:** Above + specific regression test passes
- **PR fix:** Above + diff matches requested change

Build these into the loop — don't commit unless gates pass.

### 4.4 Add circuit breaker / rate limiting (LOW VALUE)

If a loop makes no progress for N iterations, abort and alert me. Prevents burning tokens on stuck tasks. Nice to have but not critical since I'm monitoring anyway.

### 4.5 Don't adopt Gas Town (NOT NEEDED)

My OpenClaw + sub-agent setup already provides what Gas Town does (multi-agent coordination, persistent state, communication). Adding Gas Town would be a parallel system with no benefit.

### 4.6 Don't adopt snarktank/ralph directly (NOT NEEDED)

It's a human-facing bash wrapper. I AM the orchestrator — I don't need a wrapper around myself. Instead, integrate the loop pattern into my existing coding-agent skill.

---

## 5. Implementation Plan

**Phase 1: Loop-enabled coding-agent skill**
- Modify `skills/coding-agent/SKILL.md` to support a "ralph mode"
- Create `scripts/ralph-loop.sh` — generic loop wrapper for Codex/Claude CLI
- Integrate with my existing worktree workflow
- Add TASK.md / PROGRESS.md templates

**Phase 2: Verification gates**
- Define per-project verification commands in CODING_CONTEXT.md
- Loop checks gates after each iteration
- Auto-retry with failure context injected

**Phase 3: Structured task tracking**
- Add machine-readable task state (task.json) for complex features
- Write a converter: BACKLOG.md → task.json for implementation tasks
- Report completion to me via OpenClaw session messaging

---

## 6. Sources

- [Geoffrey Huntley — Original Ralph pattern](https://ghuntley.com/ralph/)
- [Geoffrey Huntley — Everything is a Ralph Loop](https://ghuntley.com/loop/)
- [snarktank/ralph](https://github.com/snarktank/ralph) — Canonical implementation
- [frankbria/ralph-claude-code](https://github.com/frankbria/ralph-claude-code) — Claude Code + smart exit detection
- [Th0rgal/open-ralph-wiggum](https://github.com/Th0rgal/open-ralph-wiggum) — Multi-agent CLI wrapper
- [mikeyobrien/ralph-orchestrator](https://github.com/mikeyobrien/ralph-orchestrator) — Most feature-rich (Rust + web UI + Telegram)
- [vercel-labs/ralph-loop-agent](https://github.com/vercel-labs/ralph-loop-agent) — AI SDK programmatic integration
- [steveyegge/gastown](https://github.com/steveyegge/gastown) — Multi-agent workspace manager
- [AI Hero — 11 Tips for Ralph Wiggum](https://www.aihero.dev/tips-for-ai-coding-with-ralph-wiggum)
- [Dev Interrupted — Inventing the Ralph Wiggum Loop](https://devinterrupted.substack.com/p/inventing-the-ralph-wiggum-loop-creator)
- [Alibaba Cloud — From ReAct to Ralph Loop](https://www.alibabacloud.com/blog/from-react-to-ralph-loop-a-continuous-iteration-paradigm-for-ai-agents_602799)

---

*Research time: ~15 min. 12 sources consulted.*
