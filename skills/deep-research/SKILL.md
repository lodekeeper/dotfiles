---
name: deep-research
description: Multi-agent deep research pipeline for complex questions (EIP analysis, architecture decisions, cross-client comparisons, protocol design). Use when single-shot answers are insufficient and you need decomposition, parallel investigation, adversarial critique, and a formal output document.
---

# Deep Research Skill

Multi-agent deep research pipeline for complex topics. Produces formalized research documents (specs, analyses, proposals) through iterative investigation, synthesis, and adversarial critique.

**When to use:** Complex questions requiring genuine research — EIP analysis, implementation strategies, novel ideas, cross-client comparisons, protocol design, or any topic where a single-shot answer isn't good enough.

**Expected duration:** 30-90 minutes depending on complexity.

---

## Prerequisites

- **Hard-reasoning CLIs (subscription-billed, verified 2026-10-04):** Codex CLI with `gpt-6-astra` at `max` effort (ChatGPT login); Claude CLI with `fable` at `max` effort (claude.ai Max). See the `codex` skill for flags and detaching long runs.
- **ChatGPT Pro (optional):** `scripts/oracle/oracle-browser` (Camoufox) — needs valid ChatGPT cookies; see `skills/oracle-bridge/SKILL.md`
- **Sub-agents:** Available via `sessions_spawn` (explorer, specialist, adversary, surveyor are role labels for the task prompt, not `agentId`s)
- **Web search:** For prior art, papers, existing implementations
- **File access:** For reading specs, code, EIPs locally

## Related Skills

- `codex` skill — Codex CLI invocation (astra max), output files, detaching long runs.
- `skills/oracle-bridge/SKILL.md` — ChatGPT Pro browser path (optional; needs fresh cookies).
- `skills/web-scraping/SKILL.md` — use when `web_search`/`web_fetch` are insufficient or blocked and you need robust page acquisition before synthesis.
- `skills/dev-workflow/SKILL.md` — use when research is feeding directly into a Lodestar implementation plan/PR.

Check the CLIs are available:
```bash
source ~/.nvm/nvm.sh && nvm use 24 && codex --version && claude --version
```

### ⚠️ Always Save Model Output to File

Hard-reasoning runs take minutes+. Context can compact mid-run, losing stdout. **Every Codex/Claude/Oracle call MUST write to a file** (`codex exec -o <path>`, `claude -p … > <path>`, `oracle-browser --write-output <path>`). No exceptions. This ensures output survives compaction and can be read back later.

### Hard-Reasoning Engine Priority

| Engine | Command | Cost |
|--------|---------|------|
| **Codex CLI, astra max (default)** | `cat <ctx.md> \| codex exec -m gpt-6-astra -c model_reasoning_effort=max -s read-only --skip-git-repo-check -o <out.md> "<prompt>"` | Subscription |
| **Claude CLI, fable max** | `cat <ctx.md> \| claude -p --model fable --effort max "<prompt>" > <out.md>` | Subscription |
| **ChatGPT Pro (browser, optional)** | `~/.openclaw/workspace/scripts/oracle/oracle-browser -p "<prompt>" -f <ctx.md> -m pro -t 3600 --write-output <out.md>` | Pro subscription; needs valid cookies |
| **OpenAI API** | `oracle --engine api …` / direct API | Per-token — ask Nico first |

`max` runs can exceed the Bash tool's 10-minute foreground cap — detach them with `setsid` (pattern in the `codex` skill) and poll the output file.

**⚠️ CRITICAL:** Do NOT silently fall back to API-billed models. If a subscription engine fails (auth expired, rate-limited), switch to the other subscription engine; if all fail, stop and ask Nico for fresh auth or explicit approval to use the API.

---

## Research Type Classification

Different research questions need different tools. **Classify each sub-question during Phase 1** and route accordingly:

### Type A: Web Literature / Ecosystem Survey
*"What tools exist for X?", "Compare approaches to Y", "Find prior art on Z"*

**Best tool:** Sub-agent + native `web_search`/`web_fetch` (plus the `web-search` skill for code/StackExchange/HN/ethresear.ch sources); if sources are blocked/partial, switch to `skills/web-scraping/SKILL.md` for robust acquisition before synthesis. For a major survey with the human available, suggest ChatGPT Deep Research (manual mode, below).

The OpenAI API no longer lists `o3-deep-research` / `o4-mini-deep-research` (checked 2026-10-04), so there is no automated deep-research API path.
```
sessions_spawn task:"Research [sub-question]. Start with web_search/web_fetch for prior art and papers. If key pages are blocked or JS-rendered, use skills/web-scraping/SKILL.md tiered scraper. Write findings to ~/research/<topic>/findings/web-research.md"
```

### Type B: Codebase / Spec Analysis
*"How does Lodestar handle X?", "What does the spec say about Y?", "Find the bug in Z"*

**Best tool:** Codex CLI (`gpt-6-astra`; config default `xhigh`, `max` for hard questions) or Claude CLI + sub-agents
- Needs local file access (repos, specs, code)
- Can run tests, grep codebases, read large files
- Web-only research models can't do this

```bash
# Codex for focused code investigation (read-only; reply lands in the -o file)
codex exec -m gpt-6-astra -c model_reasoning_effort=max -s read-only -C ~/lodestar \
  -o ~/research/<topic>/findings/code-analysis.md "Analyze [question] in packages/..."

# Or Claude CLI (fable) for broader reasoning
# (prompt BEFORE --add-dir — the flag is variadic and would swallow the prompt)
claude -p --model fable --effort max "Read [files] and analyze [question]." --add-dir ~/lodestar \
  > ~/research/<topic>/findings/code-analysis.md
```

**Or via sub-agent:**
```
sessions_spawn task:"Analyze [sub-question] by reading:
- Relevant consensus specs: ~/consensus-specs/specs/...
- Lodestar implementation: ~/lodestar/packages/...
- Other client implementations (search GitHub)
Write findings to ~/research/<topic>/findings/spec-analysis.md"
```

### Type C: Deep Reasoning / Novel Analysis
*"What are the tradeoffs of X?", "Design an approach for Y", "What's the best architecture for Z?"*

**Best tool:** GPT-6 Astra at `max` (Codex CLI); alternative Claude Fable at `max` (Claude CLI)
- Strongest reasoning for novel analysis and synthesis
- Best when you already have the materials and need deep thinking
- Also excellent for adversarial critique

```bash
cat ~/research/<topic>/plan.md | codex exec -m gpt-6-astra -c model_reasoning_effort=max \
  -s read-only --skip-git-repo-check -o ~/research/<topic>/findings/analysis.md \
  "[Your reasoning prompt]"
```

### Type D: Cross-Client Comparison
*"How do other clients implement X?"*

**Best tool:** Sub-agent (surveyor) — can search GitHub, read code
```
sessions_spawn task:"Survey how Prysm, Lighthouse, Teku, and Nimbus handle [topic].
Compare approaches, identify patterns. Write to ~/research/<topic>/findings/cross-client.md"
```

---

## Workflow

### Phase 0: Scoping (5-10 min) — MANDATORY

Before any research begins, return to the human with:

1. **Problem statement** — your understanding of what's being asked
2. **Decomposition** — 3-5 sub-questions, each **classified by type** (A/B/C/D)
3. **Tool routing** — which model/agent handles each sub-question and why
4. **Assumptions** — anything you'd need to assume if not clarified
5. **Cost estimate** — if proposing any API-billed model, estimate token cost (subscription CLIs: none)
6. **Estimated time** — rough estimate based on complexity
7. **Clarifying questions** — anything ambiguous or underspecified

**Wait for approval before proceeding.** Especially important when API-cost models are proposed.

### Phase 1: Decomposition (5 min)

Once approved, finalize the research plan:

1. Break the topic into 3-5 independent sub-questions
2. **Classify each sub-question** by research type (A/B/C/D — see above)
3. Assign each to the best agent/tool based on classification
4. Create the research workspace:
   ```bash
   mkdir -p ~/research/<topic-slug>/{findings,drafts}
   ```
5. Write the research plan to `~/research/<topic-slug>/plan.md`

### Phase 2: Parallel Investigation (15-30 min)

Launch all sub-questions simultaneously. Use the routing from Phase 1.

**Example mixed investigation:**

```
# Type A: Web survey (sub-agent with web_search/web_fetch)
sessions_spawn task:"Research [web question]. Write to ~/research/<topic>/findings/web-survey.md"

# Type B: Code analysis (Codex or sub-agent)
sessions_spawn task:"Analyze [code question] in ~/lodestar/... Write to ~/research/<topic>/findings/code-analysis.md"

# Type C: Deep reasoning (Codex CLI, astra max — detach with setsid if it may exceed 10 min)
cat ~/research/<topic>/plan.md | codex exec -m gpt-6-astra -c model_reasoning_effort=max \
  -s read-only --skip-git-repo-check -o ~/research/<topic>/findings/astra-analysis.md "[reasoning question]"

# Type D: Cross-client survey (sub-agent)
sessions_spawn task:"Survey other clients on [topic]. Write to ~/research/<topic>/findings/cross-client.md"
```

**Wait for all agents to complete before proceeding.** In the Claude-CLI harness `sessions_yield` fails and completion announcements can be lost, so collect results actively: keep each `sessions_spawn` result's `runId`, poll `subagents action:"wait" runIds:[...] timeoutSeconds:60` (60s max per call; a wait timeout doesn't cancel the run), and/or check `~/research/<topic>/findings/` for the expected files. For work you need back synchronously, use the `Agent` tool instead of `sessions_spawn`. For detached CLI runs, poll their output files.

### Phase 3: Synthesis (10-15 min)

1. Read all findings from `~/research/<topic>/findings/`
2. Identify:
   - Common themes across sources
   - Contradictions or disagreements
   - Gaps in coverage
   - Surprising or novel findings
3. Write a draft document to `~/research/<topic>/drafts/v1.md` using `references/output-template.md`

### Phase 4: Adversarial Critique (10-15 min)

Send the draft through adversarial review. Use **two different perspectives**:

**Adversary #1 — GPT-6 Astra at `max` (Codex CLI):**
```bash
cat ~/research/<topic>/drafts/v1.md | codex exec -m gpt-6-astra -c model_reasoning_effort=max \
  -s read-only --skip-git-repo-check -o ~/research/<topic>/drafts/critique.md \
  "You are a rigorous adversarial reviewer. Find weaknesses, gaps, and flawed reasoning.

For each section:
1. Challenge the key claims — are they well-supported?
2. Identify missing perspectives or counterarguments
3. Point out logical gaps or unsupported leaps
4. Suggest what additional evidence would strengthen weak points
5. Rate confidence: HIGH / MEDIUM / LOW for each major conclusion

Be constructive but ruthless."
```

**Adversary #2 — Claude Fable at `max` (different model family from Adversary #1):**
```bash
cat ~/research/<topic>/drafts/v1.md | claude -p --model fable --effort max \
  "Review this research document as a devil's advocate. Challenge every assumption. Find what's missing. Identify risks." \
  > ~/research/<topic>/drafts/critique-2.md
```
Sub-agent alternative: `sessions_spawn` with `model: "anthropic/claude-fable-5-1"` (or `"anthropic/claude-sonnet-5-5"` for a cheaper pass), task as above.

### Phase 5: Revision (5-10 min)

1. Read both critiques
2. Address valid criticisms — strengthen weak arguments, add missing perspectives
3. Mark unresolvable disagreements as "Open Questions"
4. Write final document to `~/research/<topic>/output.md`
5. If critiques revealed fundamental gaps, loop back to Phase 2 for targeted investigation

### Phase 6: Delivery

1. Present the final document to the human
2. Highlight:
   - Key findings / recommendations
   - Confidence levels for major conclusions
   - Open questions that need human judgment
   - Suggested next steps
3. Save to `~/research/<topic>/output.md` (and any supplementary materials)

---

## ChatGPT Deep Research (Manual Mode)

ChatGPT's built-in **Deep Research** feature is the most powerful option for web-based research with citations. It's included in the Pro subscription (free to use) but **cannot be automated** via Oracle — it requires manual interaction in the browser.

**When to suggest it:** For major web literature reviews where the human is available to trigger it manually.

**How it works:**
1. Open chatgpt.com → select "Deep Research" from the model/agent dropdown
2. Enter the research question
3. Review and optionally edit the research plan
4. Wait 5-30 min for results (it browses, reads, synthesizes automatically)
5. Get a documented report with citations

**When our skill is better:** When research involves local code/specs, needs code execution, or requires custom agent coordination. ChatGPT Deep Research can't read our repos or run tests.

**Hybrid approach:** For mixed research, suggest the human triggers Deep Research for the web survey portion, then feed those results into our Phase 3 synthesis alongside our code/spec findings.

---

## Output Template

Section skeleton for drafts and `output.md` (summary, problem, prior art, analysis, cross-client table, proposed approach, risks, open questions, sources): `references/output-template.md`.

---

## Model Selection Guide

| Role | Best Model | Fallback | Why |
|------|-----------|----------|-----|
| **Scoping** | Opus 5.5 (me) | — | Needs judgment about what matters |
| **Web survey** | Sub-agent + web_search/web_fetch | web-scraping skill for blocked pages | No deep-research API model available anymore |
| **Code/spec analysis** | Codex CLI (gpt-6-astra; `max` when hard) | Claude CLI (fable) / sub-agent | Best for long-horizon code investigation |
| **Deep reasoning** | GPT-6 Astra `max` (Codex CLI) | Claude Fable `max` (Claude CLI); ChatGPT Pro browser | Strongest reasoning for novel analysis |
| **Cross-client survey** | Sub-agent (surveyor) | — | Needs GitHub access, code reading |
| **Adversary #1** | GPT-6 Astra `max` (Codex CLI) | — | Strongest adversarial reasoning |
| **Adversary #2** | Claude Fable `max` (Claude CLI) | Sub-agent `anthropic/claude-sonnet-5-5` | Different model family = different blind spots |
| **Synthesis** | Opus 5.5 (me) | — | Quality control, coherent narrative |
| **Manual deep research** | ChatGPT Deep Research (browser) | — | Most powerful but requires human to trigger |

### Cost Reference

| Model | Billing | Notes |
|-------|---------|-------|
| GPT-6 Astra / Sol / Luna via Codex CLI | ChatGPT subscription | `codex login status` → "Logged in using ChatGPT" |
| Claude Fable / Opus / Sonnet via Claude CLI | claude.ai Max subscription | `claude auth status` |
| ChatGPT Pro (browser) | Pro subscription | Via `oracle-browser`; needs valid cookies |
| OpenAI API (`gpt-6.1-sol`, `gpt-6-astra`, `gpt-5.5-pro`, …) | Per token | Needs user approval |
| Sub-agents | Session cost | Included in OpenClaw |

**Rules:**
1. **Always try subscription options first:** `web_search` + `web_fetch` + sub-agents + the Codex/Claude CLIs. Only escalate to API-billed models if those are genuinely insufficient.
2. **Any API-billed model requires explicit approval from Nico before use** — explain why the subscription paths weren't enough and get a "yes" first.

---

## Self-Healing

If something fails during research:

1. **Codex or Claude CLI fails (auth expired, rate-limited):** Switch to the other CLI. Do NOT silently fall back to API-billed models — only with explicit user approval.
2. **ChatGPT Pro browser path fails (cookies expired):** Ask Nico for fresh cookies; don't debug the bridge. See `skills/oracle-bridge/SKILL.md`.
3. **Both CLIs unavailable:** Fall back to sub-agents (`model: "openai/gpt-6-astra"` or `"anthropic/claude-fable-5-1"`; thinking inherits `max`) for deep reasoning.
4. **Web survey thin:** Escalate to the `web-search` skill sources and `skills/web-scraping/SKILL.md`, or suggest manual ChatGPT Deep Research.
5. **Web search returns nothing:** Try alternative search queries, check specific repos/forums directly.
6. **Sub-agent times out:** Retry with a narrower scope or split the task.
7. **Source contradictions:** Document both perspectives, flag for human judgment.
8. **Scope creep:** If a sub-question opens up a rabbit hole, note it in "Open Questions" rather than derailing the main research.

**After each research run, update this skill:**
- If a tool/approach consistently fails, document the failure and alternative
- If a new tool or source proves valuable, add it to the workflow
- If the output template needs adjustment based on feedback, update `references/output-template.md`

---

## Iteration

Research is rarely one-shot. The skill supports iterative deepening:

### "Go Deeper" Loop
When the human says "go deeper on X":
1. Extract the specific area from the previous output
2. Re-enter at Phase 1 with a narrowed scope focused on X
3. Use previous findings as context for the new investigation
4. Produce an updated document that integrates both rounds

### Follow-up Research
When new information emerges after initial research:
1. Read the previous output from `~/research/<topic>/output.md`
2. Identify what's changed or what new information is available
3. Run targeted Phase 2 investigation on the delta
4. Revise the document (don't start from scratch)

### Research Chains
Some topics naturally lead to follow-up questions:
1. After delivering output, explicitly note "This research suggests the following follow-up investigations: ..."
2. The human can trigger any of these as new research tasks
3. Link related research documents together via references

---

## Hard-Reasoning Quick Reference

```bash
source ~/.nvm/nvm.sh && nvm use 24

# --- Codex CLI, GPT-6 Astra at max (default; ChatGPT subscription) ---
cat context.md | codex exec -m gpt-6-astra -c model_reasoning_effort=max \
  -s read-only --skip-git-repo-check -o out.md "Your prompt"

# --- Claude CLI, Fable at max (claude.ai Max subscription) ---
cat context.md | claude -p --model fable --effort max "Your prompt" > out.md

# --- ChatGPT Pro via Camoufox wrapper (optional; needs valid cookies) ---
~/.openclaw/workspace/scripts/oracle/oracle-browser -p "Your prompt" -f context.md -m pro -t 3600 --write-output out.md
~/.openclaw/workspace/scripts/oracle/oracle-browser --dry-run summary -p "Your prompt" -f context.md   # preview, no send

# --- OpenAI API (per-token — needs user approval) ---
oracle --engine api -p "Your prompt" --file context.md --model gpt-6-astra
```

**API mode:** `OPENAI_API_KEY` lives in the gateway service env (`~/.config/systemd/user/openclaw-gateway.service`), not `~/.bashrc`. Only use with explicit user approval.

See the `codex` skill for detaching long runs and `skills/oracle-bridge/SKILL.md` for the ChatGPT browser path.

---

## Notes

- **Always create `~/research/<topic-slug>/`** for each research task — keeps outputs organized and referenceable
- **Save intermediate findings** — if a session crashes, you don't lose work
- **Time-box phases** — if Phase 2 is taking >30 min, wrap up what you have and move to synthesis
- **Human in the loop** — Phase 0 (scoping) is mandatory. Don't skip it, even for "obvious" topics
- **Classify before routing** — the Research Type Classification section is the key improvement. Use it.
- **Quality > Speed** — this skill is designed for depth, not quick answers. Take the time needed.
- **ChatGPT Deep Research** — suggest it for major web surveys when the human is available. It's the most powerful option and free with Pro sub.
