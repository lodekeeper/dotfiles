# Deep Research Skill

Multi-agent deep research pipeline for complex topics. Produces formalized research documents (specs, analyses, proposals) through iterative investigation, synthesis, and adversarial critique.

**When to use:** Complex questions requiring genuine research — EIP analysis, implementation strategies, novel ideas, cross-client comparisons, protocol design, or any topic where a single-shot answer isn't good enough.

**Expected duration:** 30-90 minutes depending on complexity.

---

## Prerequisites

- **Oracle CLI:** `oracle` (GPT-5 Pro access for deep reasoning)
- **Oracle Bridge:** See `skills/oracle-bridge/SKILL.md` — required for browser mode on this server
- **Sub-agents:** Available via `sessions_spawn` (explorer, specialist, adversary roles)
- **Web search:** For prior art, papers, existing implementations
- **File access:** For reading specs, code, EIPs locally

Check Oracle is available:
```bash
source ~/.nvm/nvm.sh && nvm use 22 && oracle --version
```

### Oracle Engine Priority

Oracle has two engines. **Always use browser mode first** (uses ChatGPT Pro subscription, no per-query cost).

| Engine | Command | Cost | Reliability |
|--------|---------|------|-------------|
| **Browser (default)** | `ORACLE_REUSE_TAB=1 oracle --engine browser --remote-chrome localhost:9222` | Free (Pro sub) | Requires bridge running + valid session token |
| **API (fallback)** | `oracle --engine api` | ~$0.09/query | Always works if API key set |

**⚠️ CRITICAL:** Do NOT silently fall back to API mode. If browser mode fails (expired token, bridge down):
1. **Stop** — do not continue research
2. **Alert user:** "ChatGPT session token expired. Need fresh `__Secure-next-auth.session-token` from chatgpt.com, or explicit approval to use API mode."
3. Only switch to API if user explicitly approves

### Starting the Oracle Bridge

Before any Oracle browser-mode call, ensure the bridge is running:

```bash
# Check if bridge is already running
curl -s http://localhost:9222/json/version && echo "Bridge running" || echo "Bridge not running"

# Start bridge (if not running)
source ~/camoufox-env/bin/activate
python3 ~/.openclaw/workspace/research/oracle-bridge-v3.py \
  --cookies ~/.oracle/chatgpt-cookies.json &
sleep 15  # wait for browser + CF bypass + login

# Verify
curl -s http://localhost:9222/json/version | grep -q Chrome && echo "Ready"
```

For full bridge documentation, see `skills/oracle-bridge/SKILL.md`.

---

## Workflow

### Phase 0: Scoping (5-10 min) — MANDATORY

Before any research begins, return to the human with:

1. **Problem statement** — your understanding of what's being asked
2. **Decomposition** — 3-5 sub-questions you'd investigate
3. **Assumptions** — anything you'd need to assume if not clarified
4. **Approach** — which agents/tools you'd use for each sub-question
5. **Estimated time** — rough estimate based on complexity
6. **Clarifying questions** — anything ambiguous or underspecified

**Wait for approval before proceeding.** The human may redirect, narrow, or expand scope. This phase prevents wasted research on wrong assumptions.

### Phase 1: Decomposition (5 min)

Once approved, finalize the research plan:

1. Break the topic into 3-5 independent sub-questions
2. Assign each sub-question to the best agent/tool:
   - **Web search** → prior art, papers, related work, existing implementations
   - **Oracle (GPT-5 Pro)** → deep reasoning, novel analysis, theoretical questions
   - **Sub-agent (Specialist)** → code reading, spec analysis, implementation details
   - **Sub-agent (Surveyor)** → cross-client comparison, ecosystem survey
3. Create the research workspace:
   ```bash
   mkdir -p ~/research/<topic-slug>/{findings,drafts}
   ```
4. Write the research plan to `~/research/<topic-slug>/plan.md`

### Phase 2: Parallel Investigation (15-30 min)

Spawn agents simultaneously for independent sub-questions:

**Web Research (Explorer):**
```
sessions_spawn task:"Research [sub-question]. Search for:
- Academic papers and blog posts
- Existing implementations in other projects
- Related EIPs/specs/proposals
- Known tradeoffs and criticisms
Write findings to ~/research/<topic>/findings/web-research.md"
```

**Deep Reasoning (Oracle / GPT-5 Pro — browser mode):**

Ensure the Oracle bridge is running first (see Prerequisites above), then:

```bash
source ~/.nvm/nvm.sh && nvm use 22
ORACLE_REUSE_TAB=1 oracle --engine browser \
  --remote-chrome localhost:9222 \
  -p "Given the following context: [context]

Analyze [sub-question] in depth. Consider:
- First-principles reasoning
- Edge cases and failure modes
- Novel approaches not commonly discussed
- Theoretical limits and tradeoffs

Be rigorous and cite specific reasoning." \
  --file ~/research/<topic>/plan.md \
  --model gpt-5.2-pro --wait \
  2>&1 | tee ~/research/<topic>/findings/oracle-analysis.md
```

> **If bridge fails:** Do NOT silently switch to `--engine api`. Alert the user — see "Oracle Engine Priority" above.

**Code/Spec Specialist:**
```
sessions_spawn task:"Analyze [sub-question] by reading:
- Relevant consensus specs: ~/consensus-specs/specs/...
- Lodestar implementation: ~/lodestar/packages/...
- Beacon APIs: ~/beacon-APIs/...
- Other client implementations (search GitHub)
Write findings to ~/research/<topic>/findings/spec-analysis.md"
```

**Cross-Client Survey:**
```
sessions_spawn task:"Survey how other clients handle [topic]:
- Prysm (Go): github.com/prysmaticlabs/prysm
- Lighthouse (Rust): github.com/sigp/lighthouse
- Teku (Java): github.com/Consensys/teku
- Nimbus (Nim): github.com/status-im/nimbus-eth2
Compare approaches, identify patterns and divergences.
Write findings to ~/research/<topic>/findings/cross-client.md"
```

**Wait for all agents to complete before proceeding.**

### Phase 3: Synthesis (10-15 min)

1. Read all findings from `~/research/<topic>/findings/`
2. Identify:
   - Common themes across sources
   - Contradictions or disagreements
   - Gaps in coverage
   - Surprising or novel findings
3. Write a draft document to `~/research/<topic>/drafts/v1.md` using the output template (see below)

### Phase 4: Adversarial Critique (10-15 min)

Send the draft through adversarial review using Oracle (GPT-5 Pro):

```bash
source ~/.nvm/nvm.sh && nvm use 22
ORACLE_REUSE_TAB=1 oracle --engine browser \
  --remote-chrome localhost:9222 \
  -p "You are a rigorous adversarial reviewer. Your job is to find weaknesses, gaps, and flawed reasoning in this research document.

For each section:
1. Challenge the key claims — are they well-supported?
2. Identify missing perspectives or counterarguments
3. Point out logical gaps or unsupported leaps
4. Suggest what additional evidence would strengthen weak points
5. Rate confidence: HIGH / MEDIUM / LOW for each major conclusion

Be constructive but ruthless. Don't accept hand-waving." \
  --file ~/research/<topic>/drafts/v1.md \
  --model gpt-5.2-pro --wait \
  2>&1 | tee ~/research/<topic>/drafts/critique.md
```

Also spawn a sub-agent for a second adversarial perspective:
```
sessions_spawn task:"Review this research document as a devil's advocate.
[paste draft or point to file]
Challenge every assumption. Find what's missing. Identify risks.
Write critique to ~/research/<topic>/drafts/critique-2.md"
model:"anthropic/claude-sonnet-4-5" thinking:"high"
```

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

## Output Template

```markdown
# Research: [Topic Title]

**Date:** YYYY-MM-DD
**Requested by:** [who]
**Duration:** [time spent]
**Confidence:** HIGH / MEDIUM / LOW

## Executive Summary
[2-3 paragraph summary of findings and recommendations]

## Problem Statement
[Clear definition of what was researched and why]

## Prior Art / Related Work
[What exists, who's done what, relevant papers/EIPs/implementations]

## Analysis
### [Sub-topic 1]
[Findings, evidence, reasoning]

### [Sub-topic 2]
[Findings, evidence, reasoning]

### [Sub-topic N]
[Findings, evidence, reasoning]

## Cross-Client Comparison (if applicable)
| Aspect | Lodestar | Lighthouse | Prysm | Teku |
|--------|----------|------------|-------|------|
| ...    | ...      | ...        | ...   | ...  |

## Proposed Approach
[Recommended solution/direction with justification]

### Alternatives Considered
[Other approaches and why they were rejected]

### Tradeoffs
[Explicit tradeoffs of the proposed approach]

## Implementation Sketch (if applicable)
[High-level design, key interfaces, data flow]

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ...  | ...       | ...    | ...        |

## Open Questions
[Things that couldn't be resolved and need human judgment or further research]

## Sources
[Links, references, citations]
```

---

## Self-Healing

If something fails during research:

1. **Oracle browser mode fails (token expired):** Alert user immediately. Do NOT silently fall back to API. Only use `--engine api` with explicit user approval.
2. **Oracle bridge won't start:** Kill stale processes (`pkill -f "chromium.*headless"`), check `~/.oracle/chatgpt-cookies.json` exists, reinstall browser if needed (`python3 -m rebrowser_playwright install chromium`). See `skills/oracle-bridge/SKILL.md` for full troubleshooting.
3. **Oracle completely unavailable (no bridge, no API key):** Fall back to sub-agents with thinking:high for deep reasoning
4. **Web search returns nothing:** Try alternative search queries, check specific repos/forums directly
3. **Sub-agent times out:** Retry with a narrower scope or split the task
4. **Source contradictions:** Document both perspectives, flag for human judgment
5. **Scope creep:** If a sub-question opens up a rabbit hole, note it in "Open Questions" rather than derailing the main research

**After each research run, update this skill:**
- If a tool/approach consistently fails, document the failure and alternative
- If a new tool or source proves valuable, add it to the workflow
- If the output template needs adjustment based on feedback, update it

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

## Model Selection Guide

| Role | Recommended Model | Why |
|------|------------------|-----|
| Scoping/Decomposition | Opus (me) | Needs judgment about what matters |
| Web Explorer | Gemini Flash / GPT | Fast, good at search synthesis |
| Oracle Deep Reasoning | GPT-5 Pro (via oracle) | Strongest reasoning for novel analysis |
| Code/Spec Specialist | Codex / Claude | Good at code reading and analysis |
| Cross-Client Survey | Gemini / GPT | Fast, good at pattern matching |
| Adversary #1 | GPT-5 Pro (via oracle) | Strongest adversarial reasoning |
| Adversary #2 | Claude Sonnet (thinking:high) | Different perspective, good at critique |
| Synthesis/Revision | Opus (me) | Quality control, coherent narrative |

---

## Oracle Quick Reference

```bash
source ~/.nvm/nvm.sh && nvm use 22

# --- BROWSER MODE (default — uses ChatGPT Pro subscription, free) ---

# 1. Ensure bridge is running (see skills/oracle-bridge/SKILL.md)
curl -s http://localhost:9222/json/version | grep -q Chrome || {
  echo "Start bridge first!"
  echo "source ~/camoufox-env/bin/activate"
  echo "python3 ~/.openclaw/workspace/research/oracle-bridge-v3.py --cookies ~/.oracle/chatgpt-cookies.json &"
}

# 2. Run queries
ORACLE_REUSE_TAB=1 oracle --engine browser \
  --remote-chrome localhost:9222 \
  -p "Your prompt" --file path/to/context.md \
  --model gpt-5.2-pro --wait

# With multiple context files
ORACLE_REUSE_TAB=1 oracle --engine browser \
  --remote-chrome localhost:9222 \
  -p "Your prompt" --file "src/**/*.ts" --file specs/phase0.md \
  --model gpt-5.2-pro --wait

# --- API MODE (fallback — costs per query, needs user approval) ---

oracle --engine api -p "Your prompt" --file context.md --model gpt-5.2-pro

# Dry run (preview without spending tokens)
oracle --dry-run summary -p "Your prompt" --file context.md
```

**Browser mode:** Requires oracle-bridge running + valid session token at `~/.oracle/chatgpt-cookies.json`.
**API mode:** Requires `OPENAI_API_KEY` (set in `~/.bashrc`). Only use as explicit fallback.

See `skills/oracle-bridge/SKILL.md` for full bridge setup, troubleshooting, and token refresh.

---

## Notes

- **Always create `~/research/<topic-slug>/`** for each research task — keeps outputs organized and referenceable
- **Save intermediate findings** — if a session crashes, you don't lose work
- **Time-box phases** — if Phase 2 is taking >30 min, wrap up what you have and move to synthesis
- **Human in the loop** — Phase 0 (scoping) is mandatory. Don't skip it, even for "obvious" topics
- **Quality > Speed** — this skill is designed for depth, not quick answers. Take the time needed.
