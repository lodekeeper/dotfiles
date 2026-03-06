# GPT-5.4 Pro Review — Web Search Skill (Deep Thinking, 11m 42s)

Source: ChatGPT GPT-5.4 Pro via Camoufox bridge, 2026-03-06
Thinking summary: "I'm verifying which listed providers still reliably work within a true $0, low-volume setup, while also focusing on likely weak spots like routing errors, duplicate or low-trust results, and stale cache behavior. I've pinned down the five changes, and the main pattern is to make routing explicitly budget-aware and fault-tolerant around uneven quotas and 'best effort' providers."

## 5 Improvements

1. **Replace hard single-route classification with weighted top-2 routing.** Stack Exchange has separate `/search`, `/search/advanced`, and `/similar` flows; Semantic Scholar supports phrase/fielded paper search; Wikimedia splits title vs. content search. That means ambiguous prompts should usually hit the best two verticals, not exactly one provider bucket.

2. **Make Brave a scarce fallback, not part of the default parallel fan-out.** Brave Search API is priced at $5 per 1,000 requests and includes $5 of monthly free credits, so a $0 plan only covers about 1,000 Brave calls per month; reserve it for low-confidence queries, empty-result retries, or final tie-breaks.

3. **Replace one generic rate limiter with provider-native throttling state in SQLite.** GitHub tells you when to retry via `x-ratelimit-reset` and `retry-after`, Stack Exchange can return a `backoff` value and gives tokenized apps a default 10,000 daily quota, and Semantic Scholar recommends using an API key with an introductory 1 request/second limit; your scheduler should obey those signals per provider instead of applying one shared rule.

4. **Keep RRF for fusion, but add a second-stage reranker with canonical-URL dedup and provider-specific quality features.** The providers already expose useful tie-breaker signals such as Stack Exchange vote/activity fields, Semantic Scholar `citationCount`, and GitHub `stargazers_count`; use them after RRF so duplicate or weak hits do not outrank stronger evidence.

5. **Harden the cache/adapter layer.** Put SQLite in WAL mode for safer concurrent read/write behavior, add normalized-query + stale-while-revalidate + negative caching, and version the Wikimedia adapter now because the current Core REST search endpoints are scheduled for gradual deprecation starting July 2026.
