---
name: web-search
description: Multi-source web search orchestrator. Use when `web_search`/`web_fetch` are insufficient and you need query classification, parallel provider search, ranking, deduplication, and optional synthesis across web/code/academic/social sources.
---

# web-search

Multi-source web search orchestrator. Classifies queries, routes to optimal providers in parallel, ranks via RRF + quality signals, deduplicates, and optionally synthesizes results with citations.

## When to use

Use this skill when:
- You need current information beyond training data
- You need to verify a specific fact with a source
- A question could be answered by code search, academic papers, or specialized databases
- You need sources native `web_search` doesn't cover: GitHub code, Stack Exchange, Semantic Scholar, HN, ethresear.ch, Wikipedia
- You need results from multiple source types (web + code + academic + social)

Do NOT use for:
- Questions you can confidently answer from training knowledge
- Internal workspace file lookups (use Read/exec instead)
- Simple single-source searches (use `web_search` directly)
- General or time-bounded web queries — use native `web_search` (`freshness` up to `year`, `date_after`/`date_before`, `country`/`language`; this script's `--freshness` stops at `month`). Both use the same Brave key, so this skill is no way around `web_search` rate limits.

## How to invoke

```bash
python3 ~/.openclaw/workspace/skills/web-search/search.py \
  --query "your question here" \
  [--depth shallow|deep]          # deep = shallow + extractive snippet summary
  [--domains general,code,...]    # override auto-classification
  [--max-results 10]              # limit results
  [--freshness day|week|month]    # time filter
  [--no-cache]                    # skip cache
  [--no-synthesis]                # skip synthesis (deep mode)
  [--health-check]                # test all providers
  [--verbose]                     # show classification + provider selection
```

### Output (JSON to stdout)

```json
{
  "answer": "Based on 5 sources:\n\n- <snippet> [1]\n...",
  "citations": [{"id": 1, "url": "...", "title": "...", "source": "github_code"}],
  "results": [{"url": "...", "title": "...", "snippet": "...", "score": 0.85}],
  "query": {"original": "...", "domains": ["ethereum", "code"]},
  "providers_used": ["ethresearch", "github_code"],
  "providers_failed": [],
  "cached": false,
  "latency_ms": 2340
}
```

### Depth modes

- **shallow** (≤4s): No summary (`answer` is null). Returns ranked result list. Good for quick lookups.
- **deep**: Same providers and ranking, plus an extractive summary: the top-3 snippets with citation links. There is no LLM call, so do the synthesis yourself.

Depth does not change provider selection: Brave is added at both depths whenever fewer than 2 other providers match (it is the `fallback` for general/news/package in `config/routing.json`).

## Architecture

```
Query → Classify (regex, weighted top-2) → Route → Parallel Search (up to 4 providers)
  → Deduplicate (normalized URLs) → RRF Fusion + Quality Reranking → [Synthesis] → JSON
```

### Key Design Decisions

1. **Weighted top-2 routing**: Ambiguous queries hit the best two verticals, not just one. Scores are additive across multiple pattern matches.
2. **Brave as scarce fallback**: ~1K calls/month free credit, shared with native `web_search`. DuckDuckGo is the primary general provider; Brave is the general/news/package fallback (see Depth modes), capped by `rpd` in `config/providers.json`.
3. **Rate limiting**: Per-provider token bucket (`rpm`) plus daily cap (`rpd`). Response headers (`retry-after`, `x-ratelimit-reset`) are not read: any provider error containing "429" or "rate" blocks that provider for a fixed 60s.
4. **Two-stage ranking**: RRF fusion across providers, then quality signal reranking using provider-specific signals (SE votes, S2 citations, HN points).
5. **Cache hardening**: WAL mode, normalized query keys, stale-while-revalidate (serve stale up to 2x TTL while refreshing), negative caching (30 min for empty results).

## Providers (8 total)

| Provider | Domain | Auth | Cost | Signal |
|----------|--------|------|------|--------|
| DuckDuckGo | general, news | None | Free | — |
| Brave Search | general, news, package (fallback) | `BRAVE_API_KEY` | ~1K/mo, shared with `web_search` | — |
| GitHub Code | code, ethereum | `GITHUB_TOKEN` | Free (PAT) | repo presence |
| HN Algolia | social | None | Free (10K/hr) | points |
| Semantic Scholar | academic | `SEMANTIC_SCHOLAR_KEY` (opt) | Free | citations |
| Wikipedia | encyclopedia | None | Free | — |
| Stack Exchange | qa, code | `STACKEXCHANGE_KEY` (opt) | Free (300/day, 10K w/key) | votes, accepted |
| ethresear.ch | ethereum | None | Free | views, likes |

## Environment Setup

```bash
export GITHUB_TOKEN=$(gh auth token)    # Required for code search
# Optional (higher limits):
# export BRAVE_API_KEY=...              # else read from plugins.entries.brave.config.webSearch.apiKey
# export SEMANTIC_SCHOLAR_KEY=...       # Higher rate limits
# export STACKEXCHANGE_KEY=...          # 10K/day vs 300/day
```

Without any API keys, 6 of 8 providers still work (DDG, HN, Wikipedia, Stack Exchange, ethresear.ch, Semantic Scholar).

## Adding a Provider

1. Create `providers/<name>.py` with `search(query: str, params: dict) -> list[dict]`
2. Each result dict must have: `url`, `title`, `snippet`
3. Optional: `published_at`, provider-specific fields in snippet for quality signals
4. Add entry to `config/providers.json`
5. Add domain routing in `config/routing.json`

## State Files

- `state/cache.db` — SQLite WAL query cache (TTL + stale-while-revalidate + negative caching)
- `state/rate_limits.db` — Per-provider token buckets, daily counts, 60s post-429 blocks
