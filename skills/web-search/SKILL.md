# web-search

Multi-source web search orchestrator. Finds answers to any question by querying optimal sources in parallel, deduplicating, ranking, and synthesizing results with citations.

## When to use

Use this skill when:
- You need current information beyond training data
- You need to verify a specific fact with a source
- A question could be answered by code search, academic papers, or specialized databases
- The `web_search` tool alone is insufficient (rate limit, quality, coverage)
- You need results from multiple source types (web + code + academic + social)

Do NOT use for:
- Questions you can confidently answer from training knowledge
- Internal workspace file lookups (use Read/exec instead)
- Simple single-source searches (use `web_search` directly)

## How to invoke

```bash
python3 ~/.openclaw/workspace/skills/web-search/search.py \
  --query "your question here" \
  [--depth shallow|deep]          # shallow=fast/no synthesis, deep=full pipeline
  [--domains general,code,...]    # override auto-classification
  [--max-results 10]              # per provider
  [--freshness day|week|month]    # time filter
  [--no-cache]                    # skip cache
  [--no-synthesis]                # skip LLM synthesis
```

### Output (JSON to stdout)

```json
{
  "answer": "Synthesized answer with citations [1][2].",
  "citations": [{"id": 1, "url": "...", "title": "...", "source": "brave"}],
  "results": [{"url": "...", "title": "...", "snippet": "...", "score": 0.85, "source": "brave"}],
  "query": {"original": "...", "domains": ["ethereum", "code"]},
  "providers_used": ["brave", "github_code"],
  "providers_failed": [],
  "cached": false,
  "latency_ms": 2340
}
```

### Depth modes

- **shallow** (≤4s): No synthesis, no content extraction. Returns ranked result list. Good for quick lookups.
- **deep** (≤15s): Full pipeline with LLM synthesis + citations. Extracts content from top-3 URLs. Best for research questions.

## Configuration

Edit `config/providers.json` to enable/disable providers, set API keys (via env vars), adjust rate limits.

## Adding a provider

1. Create `providers/<name>.py` implementing `search(query, params) -> list[dict]`
2. Add entry to `config/providers.json`
3. Add domain routing in `config/routing.json`

## Providers (MVP)

| Provider | Domain | Auth | Cost |
|----------|--------|------|------|
| Brave Search | general, news | `BRAVE_API_KEY` | Free tier (1.7K/mo) |
| DuckDuckGo | general (fallback) | None | Free |
| GitHub Code Search | code | `GITHUB_TOKEN` | Free (PAT) |

## Environment Setup

The skill needs these env vars for full functionality:
```bash
export GITHUB_TOKEN=$(gh auth token)    # GitHub code search
# export BRAVE_API_KEY=...              # If you have a Brave Search API key
# export SEMANTIC_SCHOLAR_KEY=...       # Optional: higher rate limits
# export STACKEXCHANGE_KEY=...          # Optional: 10K/day vs 300/day
```

Without any API keys, the skill still works via DuckDuckGo, HN Algolia, Wikipedia, and ethresear.ch.

## State files

- `state/cache.db` — SQLite query result cache (TTL-based)
- `state/rate_limits.db` — Per-provider token buckets
- `state/health.json` — Circuit breaker status
