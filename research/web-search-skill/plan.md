# Research Plan: Comprehensive Web Search Skill

**Date:** 2026-03-06
**Requested by:** Nico
**Goal:** Build a skill that can find answers to arbitrary questions on the internet, going beyond Brave Search.

## Sub-questions

1. **Search engine landscape** (Type A) — What search APIs exist? Google, Bing, DuckDuckGo, Yandex, Mojeek, Searx/SearxNG, etc.
2. **Self-hosted / open-source search** (Type A) — SearxNG, Whoogle, meta-search engines.
3. **Specialized search sources** (Type A) — GitHub, Reddit/HN, academic, Stack Overflow, ethresear.ch, etc.
4. **Free vs paid tradeoffs** (Type C) — Cost/quality/rate-limit matrix.
5. **Skill architecture** (Type C) — Query routing, source selection, result merging, ranking.

## Tool Routing
- 1-3: Sub-agents with web_search + web_fetch
- 4-5: Oracle browser mode (GPT-5.4, free via Pro sub)
