# Research: Cheap LLM as Intermediate Log Triage Layer

## Context
I'm designing a log reader skill for an AI agent (Claude Opus, 200k context) that debugs Ethereum beacon nodes. The current architecture has two layers:

1. **Data plane (zero LLM):** fetch → normalize → template mine → reduce → always-surface scan
2. **Agent plane (expensive LLM):** reads compact "packs" (overview, drill, compare)

The question: **should there be a middle layer where a cheap/fast LLM (e.g., Claude Haiku, GPT-4.1-mini, Gemini Flash) does initial log triage before the expensive main agent sees the results?**

## Current Pipeline (no LLM in data plane)
- Template mining groups messages by (module, message) — pure regex/counting
- Always-surface rules match hardcoded patterns — regex/YAML
- Reducers compress repetitive patterns — pure Python
- Cold-start scoring is a weighted formula — arithmetic
- The main agent gets a ~8k token "overview pack" and decides what to drill into

## The Gap
The non-LLM data plane is good at:
- Counting, grouping, pattern matching, rate detection
- Surfacing known error patterns
- Token budget management

But it CANNOT:
- Understand semantic meaning of log messages it hasn't seen before
- Detect novel error patterns not in the always-surface YAML
- Explain WHY a pattern is anomalous (requires domain knowledge)
- Correlate events across CL/EL layers by meaning (not just timestamp proximity)
- Classify logs into operational states (syncing, steady-state, degraded, failing)
- Identify which context fields are diagnostically important for a specific failure mode

## What I Want You To Research

1. **Is a cheap LLM triage layer worth the added complexity?**
   - What specific capabilities would it add that regex/templates can't?
   - What's the cost/latency tradeoff? (Haiku ~$0.25/1M input, Flash ~$0.15/1M input)
   - Would it make the overview pack significantly better for cold-start investigations?

2. **Where in the pipeline should it sit?**
   - Post-template-mining (classify/annotate templates before packing)?
   - Post-normalization (filter/annotate individual events)?
   - As a pack generator (replace the deterministic overview generator)?
   - As a pre-filter (decide which logs to even normalize)?

3. **What model characteristics matter?**
   - Speed vs quality tradeoff
   - Context window needs (how much log data per call?)
   - Structured output (JSON mode for reliable parsing?)
   - Domain knowledge (would fine-tuning on Ethereum node logs help?)

4. **Concrete design patterns:**
   - Chunk-and-summarize: split logs into N-line chunks, summarize each, then synthesize
   - Map-reduce: parallel cheap LLM passes then merge
   - Filter-first: cheap LLM decides "interesting/not-interesting" before template mining
   - Annotate-and-pass: cheap LLM adds annotations (severity assessment, category, explanation) to template entries

5. **What about using a local/on-device model?**
   - Ollama with a small model (Phi-4, Llama 3.2) for zero-cost triage?
   - Latency considerations for interactive debugging sessions
   - Quality vs API models for log analysis specifically

6. **Real-world evidence:**
   - Are there production systems using tiered LLM approaches for log analysis?
   - What does the research say about small vs large LLMs for log anomaly detection?
   - Any benchmarks on log classification accuracy for different model sizes?

## My Constraints
- The main agent (Claude Opus) has 200k context but burns ~$0.015/1k tokens
- Investigations happen 2-5 times per week, each looking at 10k-100k log lines
- Speed matters — I need the triage within 30 seconds, not minutes
- The cheap LLM output must be reliable enough to not mislead the main agent
- Must work on a Linux server without GPU (CPU inference only for local models)

## What I Want From You
A concrete recommendation with:
- Yes/no on the cheap LLM layer, with clear justification
- If yes: exactly where it sits, which model to use, what it does, cost estimate
- If partially: which specific sub-tasks benefit from a cheap LLM and which don't
- Design patterns with pseudocode for the recommended approach
- Risk analysis: what happens when the cheap LLM gets it wrong?
