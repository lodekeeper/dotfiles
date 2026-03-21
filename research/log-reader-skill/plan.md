# Research: Log Reader Skill for Beacon Node Investigation

**Date:** 2026-03-21
**Requested by:** Nico
**Goal:** Design a log reading/analysis framework that balances context efficiency with signal completeness for debugging beacon node issues.

## Sub-questions

1. **[Type A] Existing tools & patterns** — web survey of log analysis approaches for blockchain nodes and AI-assisted log analysis
2. **[Type B] Lodestar log format catalog** — actual log output formats, modules, patterns, verbosity characteristics
3. **[Type C] Pipeline architecture design** — multi-stage filtering, summarization, token budgets (Oracle GPT-5.4 Pro)
4. **[Type B] Past investigation analysis** — what worked/failed in my real debugging sessions
5. **[Type C] Adversarial review** — challenge the design for gaps

## Routing
- Sub-questions 1, 2, 4: parallel sub-agents (free)
- Sub-question 3: Oracle browser mode (free)
- Sub-question 5: Oracle + Claude Sonnet adversary (free)
