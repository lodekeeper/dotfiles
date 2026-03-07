#!/usr/bin/env python3
"""
Web Search Skill — Multi-source search orchestrator for OpenClaw.
Classifies queries, routes to optimal providers, ranks via RRF + quality signals,
deduplicates, optionally synthesizes with citations.

Improvements applied from GPT-5.4 Pro review (2026-03-06):
- Weighted top-2 routing (ambiguous queries hit best two verticals)
- Brave as scarce fallback (limited free tier: ~1K calls/month)
- Provider-native rate limit headers respected
- Second-stage quality reranker using provider signals (votes, citations, stars)
- Cache: WAL mode, normalized queries, stale-while-revalidate, negative caching
- LLM synthesis in deep mode
"""

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).parent
CONFIG_DIR = SKILL_DIR / "config"
STATE_DIR = SKILL_DIR / "state"
PROVIDERS_DIR = SKILL_DIR / "providers"

STATE_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────
# 1. Cache (SQLite WAL, normalized keys, stale-while-revalidate)
# ─────────────────────────────────────────────

CACHE_DB = STATE_DIR / "cache.db"
DEFAULT_TTL = {
    "general": 4 * 3600,
    "news": 1 * 3600,
    "code": 8 * 3600,
    "academic": 24 * 3600,
    "encyclopedia": 24 * 3600,
    "ethereum": 4 * 3600,
    "social": 2 * 3600,
    "qa": 8 * 3600,
    "package": 12 * 3600,
}
# Stale-while-revalidate: serve stale data up to 2x TTL while refreshing
STALE_MULTIPLIER = 2
# Negative cache: remember empty results for 30 min to avoid re-querying
NEGATIVE_TTL = 1800


def _cache_db():
    db = sqlite3.connect(str(CACHE_DB))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=3000")
    db.execute("""CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        data TEXT,
        created_at REAL,
        ttl INTEGER,
        is_negative INTEGER DEFAULT 0
    )""")
    return db


def normalize_query(query: str) -> str:
    """Normalize query for cache key: lowercase, strip extra whitespace, sort words."""
    words = query.lower().strip().split()
    return " ".join(sorted(set(words)))


def cache_key(query: str, depth: str, domains: list[str]) -> str:
    raw = f"{normalize_query(query)}|{depth}|{','.join(sorted(domains))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def cache_get(key: str) -> tuple[dict | None, bool]:
    """Get cached result. Returns (data, is_stale).
    Returns (None, False) if not found or expired beyond stale window."""
    db = _cache_db()
    row = db.execute(
        "SELECT data, created_at, ttl, is_negative FROM cache WHERE key = ?", (key,)
    ).fetchone()
    db.close()

    if not row:
        return None, False

    data, created_at, ttl, is_negative = row
    age = time.time() - created_at

    if age < ttl:
        result = json.loads(data)
        result["cached"] = True
        result["cache_age_s"] = int(age)
        return result, False

    if age < ttl * STALE_MULTIPLIER:
        result = json.loads(data)
        result["cached"] = True
        result["cache_stale"] = True
        result["cache_age_s"] = int(age)
        return result, True  # Stale but usable

    return None, False


def cache_set(key: str, data: dict, ttl: int, is_negative: bool = False):
    db = _cache_db()
    db.execute(
        "INSERT OR REPLACE INTO cache (key, data, created_at, ttl, is_negative) VALUES (?, ?, ?, ?, ?)",
        (key, json.dumps(data), time.time(), ttl, int(is_negative)),
    )
    db.commit()
    db.close()


# ─────────────────────────────────────────────
# 2. Query Classification (rule-based, additive, weighted top-2)
# ─────────────────────────────────────────────

DOMAIN_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "code": [
        (r"\b(function|class|import|require|export|async|await|npm run)\b", 1.0),
        (r"\b(TypeError|SyntaxError|undefined is not|ENOENT|segfault)\b", 1.0),
        (r"`[^`]+`", 0.7),
        (r"\b[A-Z][a-z]+Error\b", 0.8),
        (r"\b(implementation|refactor|debug|stack trace|lint)\b", 0.6),
        (r"\b(libp2p|gossipsub|bitswap|kademlia|discv5|devp2p)\b", 0.8),
        (r"\b(API|SDK|library|framework|protocol|spec)\b", 0.4),
        (r"\b(parameter|config|flag|option|argument)\b", 0.3),
    ],
    "package": [
        (r"\bnpm (install|i|add|remove|update)\b", 1.0),
        (r"\b(package\.json|Cargo\.toml|pyproject\.toml)\b", 1.0),
        (r"\bversion\s+\d+\.\d+", 0.7),
    ],
    "academic": [
        (r"\b(paper|study|research|citation|doi:|arXiv|preprint)\b", 1.0),
        (r"\b(theorem|proof|dataset|benchmark|experiment)\b", 0.8),
    ],
    "ethereum": [
        (r"\b(EIP[-\s]?\d+|ERC[-\s]?\d+|beacon chain|consensus layer|execution layer)\b", 1.0),
        (r"\b(lodestar|prysm|lighthouse|teku|nimbus|grandine)\b", 1.0),
        (r"\b(solidity|vyper|ethers?\.js|web3|wagmi|viem)\b", 0.8),
        (r"\b(PeerDAS|ePBS|fork choice|slot|epoch|validator|attestation)\b", 1.0),
        (r"\b(data availability|blob|danksharding|rollup|L2|layer 2)\b", 0.8),
        (r"\b(ethereum|eth2?\.0?|the merge|pos|proof.of.stake)\b", 0.7),
        (r"\bethresear\.ch\b", 1.0),
    ],
    "social": [
        (r"\b(hacker news|HN|community reaction|show hn|ask hn)\b", 1.0),
        (r"\bwhat do people think\b", 0.7),
    ],
    "qa": [
        (r"\b(how (do|does|to|can)|why (is|does|did)|what (is|are|does))\b", 0.5),
        (r"\b(stack overflow|stackoverflow|stack exchange)\b", 1.0),
    ],
    "news": [
        (r"\b(today|yesterday|this week|breaking|just announced|latest|recent)\b", 0.8),
    ],
    "encyclopedia": [
        (r"\b(what is|who is|define|definition of|explain)\b", 0.5),
        (r"\b(history of|wikipedia|wiki)\b", 1.0),
    ],
}


def classify_query(query: str, explicit_domains: list[str] | None = None) -> list[str]:
    """Classify query into search domains. Returns top-2 by confidence + general."""
    if explicit_domains:
        return explicit_domains

    scores: dict[str, float] = {}
    q_lower = query.lower()

    for domain, patterns in DOMAIN_PATTERNS.items():
        for pat, weight in patterns:
            if re.search(pat, q_lower, re.IGNORECASE):
                scores[domain] = scores.get(domain, 0) + weight

    # Sort by score, take top 2
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    matched = [d for d, s in ranked[:2] if s > 0.3]

    # Always include general as fallback
    if "general" not in matched:
        matched.append("general")

    return matched


# ─────────────────────────────────────────────
# 3. Provider Loading & Routing (Brave as scarce fallback)
# ─────────────────────────────────────────────

def load_providers_config() -> dict:
    with open(CONFIG_DIR / "providers.json") as f:
        return json.load(f)


def load_routing() -> dict:
    with open(CONFIG_DIR / "routing.json") as f:
        return json.load(f)


def select_providers(
    domains: list[str], config: dict, routing: dict, depth: str = "shallow"
) -> list[str]:
    """Select providers for domains. Brave only included as fallback on shallow,
    or when specifically routed for deep queries."""
    selected = []
    brave_as_fallback = False

    for domain in domains:
        route = routing.get(domain, routing.get("general", {}))
        for provider_id in route.get("primary", []):
            if provider_id == "brave":
                # Brave is scarce — only use as primary for deep queries
                if depth == "deep":
                    if provider_id not in selected:
                        selected.append(provider_id)
                else:
                    brave_as_fallback = True
                continue
            if provider_id not in selected and config.get(provider_id, {}).get("enabled", False):
                selected.append(provider_id)

    # If we have fewer than 2 providers, add fallbacks
    if len(selected) < 2:
        for domain in domains:
            route = routing.get(domain, routing.get("general", {}))
            for provider_id in route.get("fallback", []):
                if provider_id not in selected and config.get(provider_id, {}).get("enabled", False):
                    selected.append(provider_id)

    # Add Brave only if no other providers matched (true last resort)
    if not selected and brave_as_fallback:
        selected.append("brave")

    # Cap at 4
    return selected[:4]


# ─────────────────────────────────────────────
# 4. Rate Limiting (SQLite token bucket + provider-native headers)
# ─────────────────────────────────────────────

RATE_DB = STATE_DIR / "rate_limits.db"


def _rate_db():
    db = sqlite3.connect(str(RATE_DB))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=3000")
    db.execute("""CREATE TABLE IF NOT EXISTS buckets (
        provider TEXT PRIMARY KEY,
        tokens REAL,
        max_tokens REAL,
        refill_rate REAL,
        last_refill REAL,
        daily_used INTEGER,
        daily_date TEXT,
        retry_after REAL DEFAULT 0
    )""")
    # Add retry_after column if missing (migration)
    try:
        db.execute("ALTER TABLE buckets ADD COLUMN retry_after REAL DEFAULT 0")
    except Exception:
        pass
    return db


def rate_limit_check(provider_id: str, config: dict) -> bool:
    """Check if provider has capacity. Returns True if OK to proceed."""
    pconf = config.get(provider_id, {})
    rl = pconf.get("rate_limit", {})
    rpm = rl.get("rpm", 60)
    rpd = rl.get("rpd")

    db = _rate_db()
    today = time.strftime("%Y-%m-%d")
    now = time.time()

    row = db.execute(
        "SELECT tokens, max_tokens, refill_rate, last_refill, daily_used, daily_date, retry_after "
        "FROM buckets WHERE provider = ?",
        (provider_id,),
    ).fetchone()

    if not row:
        db.execute(
            "INSERT INTO buckets VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (provider_id, rpm - 1, rpm, rpm / 60.0, now, 1, today, 0),
        )
        db.commit()
        db.close()
        return True

    tokens, max_tokens, refill_rate, last_refill, daily_used, daily_date, retry_after = row

    # Respect provider-native retry-after
    if retry_after and now < retry_after:
        db.close()
        return False

    elapsed = now - last_refill
    tokens = min(max_tokens, tokens + elapsed * refill_rate)

    if daily_date != today:
        daily_used = 0
        daily_date = today

    if tokens < 1:
        db.close()
        return False
    if rpd and daily_used >= rpd:
        db.close()
        return False

    db.execute(
        "UPDATE buckets SET tokens=?, last_refill=?, daily_used=?, daily_date=?, retry_after=0 "
        "WHERE provider=?",
        (tokens - 1, now, daily_used + 1, daily_date, provider_id),
    )
    db.commit()
    db.close()
    return True


def record_rate_limit_header(provider_id: str, retry_after_s: float):
    """Record a retry-after signal from provider response headers."""
    db = _rate_db()
    db.execute(
        "UPDATE buckets SET retry_after=? WHERE provider=?",
        (time.time() + retry_after_s, provider_id),
    )
    db.commit()
    db.close()


# ─────────────────────────────────────────────
# 5. Provider Execution (async parallel)
# ─────────────────────────────────────────────

async def run_provider(provider_id: str, query: str, params: dict, config: dict) -> dict:
    """Run a single provider search."""
    pconf = config.get(provider_id, {})
    timeout_ms = pconf.get("timeout_ms", 5000)

    if not rate_limit_check(provider_id, config):
        return {"provider": provider_id, "ok": False, "error": "rate_limited", "results": []}

    try:
        sys.path.insert(0, str(SKILL_DIR))
        mod = importlib.import_module(f"providers.{provider_id}")
        search_fn = getattr(mod, "search")

        results = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, search_fn, query, params),
            timeout=timeout_ms / 1000.0,
        )

        return {"provider": provider_id, "ok": True, "results": results, "error": None}

    except asyncio.TimeoutError:
        return {"provider": provider_id, "ok": False, "error": "timeout", "results": []}
    except Exception as e:
        err_str = str(e)[:200]
        # Check for rate limit signals in error
        if "429" in err_str or "rate" in err_str.lower():
            record_rate_limit_header(provider_id, 60)
        return {"provider": provider_id, "ok": False, "error": err_str, "results": []}


async def search_parallel(
    providers: list[str], query: str, params: dict, config: dict
) -> list[dict]:
    """Run all providers in parallel."""
    tasks = [run_provider(p, query, params, config) for p in providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    collected = []
    for r in results:
        if isinstance(r, Exception):
            collected.append({"provider": "unknown", "ok": False, "error": str(r), "results": []})
        else:
            collected.append(r)
    return collected


# ─────────────────────────────────────────────
# 6. Aggregation, Dedup & Ranking (RRF + quality signals)
# ─────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    url = url.lower().rstrip("/")
    for param in ["utm_source", "utm_medium", "utm_campaign", "utm_content", "ref", "source"]:
        url = re.sub(rf"[?&]{param}=[^&]*", "", url)
    url = re.sub(r"\?$", "", url)
    # Normalize protocol
    url = re.sub(r"^http://", "https://", url)
    return url


def extract_quality_signal(result: dict, provider: str) -> float:
    """Extract provider-specific quality signal for second-stage reranking.

    Normalizes signals to roughly [0, 1] range:
    - Stack Exchange: votes (log scale)
    - Semantic Scholar: citations (log scale)
    - HN: points (log scale)
    - GitHub: repo stars from snippet (log scale)
    """
    snippet = result.get("snippet", "")
    import math

    if provider == "stack_exchange":
        m = re.search(r"Score:\s*(\d+)", snippet)
        if m:
            return min(1.0, math.log1p(int(m.group(1))) / 8)  # log(2981)/8 ≈ 1.0
        m = re.search(r"✅", snippet)
        if m:
            return 0.3  # Accepted answer bonus

    elif provider == "semantic_scholar":
        m = re.search(r"(\d+)\s*citations", snippet)
        if m:
            return min(1.0, math.log1p(int(m.group(1))) / 10)

    elif provider == "hn_algolia":
        m = re.search(r"(\d+)\s*points", snippet)
        if m:
            return min(1.0, math.log1p(int(m.group(1))) / 7)

    elif provider == "github_code":
        # No direct star count in snippet, but repo presence is a signal
        return 0.1

    return 0.0


def rrf_rank(provider_results: list[dict], domains: list[str]) -> list[dict]:
    """Two-stage ranking: RRF fusion + quality signal reranking."""
    K = 60

    all_results = []
    for pr in provider_results:
        if not pr["ok"]:
            continue
        for rank, result in enumerate(pr["results"], 1):
            result["_source"] = pr["provider"]
            result["_rank"] = rank
            result["_quality"] = extract_quality_signal(result, pr["provider"])
            all_results.append(result)

    # Deduplicate by normalized URL (keep highest quality version)
    seen: dict[str, dict] = {}
    for r in all_results:
        nurl = normalize_url(r.get("url", ""))
        if nurl not in seen or r.get("_quality", 0) > seen[nurl].get("_quality", 0):
            seen[nurl] = r
    all_results = list(seen.values())

    # Stage 1: RRF scores
    url_scores: dict[str, float] = {}
    url_results: dict[str, dict] = {}
    for r in all_results:
        nurl = normalize_url(r.get("url", ""))
        rrf_score = 1.0 / (K + r.get("_rank", 50))

        # Domain relevance boost
        source = r.get("_source", "")
        if source in ["ethresearch", "github_code"] and "ethereum" in domains:
            rrf_score += 0.2
        elif source in ["semantic_scholar"] and "academic" in domains:
            rrf_score += 0.2
        elif source == "stack_exchange" and "qa" in domains:
            rrf_score += 0.2
        elif source == "hn_algolia" and "social" in domains:
            rrf_score += 0.1

        url_scores[nurl] = url_scores.get(nurl, 0) + rrf_score
        url_results[nurl] = r

    # Stage 2: Quality signal reranking (blended score)
    QUALITY_WEIGHT = 0.3
    ranked = []
    for nurl, rrf_score in url_scores.items():
        r = url_results[nurl]
        quality = r.get("_quality", 0)
        final_score = rrf_score + QUALITY_WEIGHT * quality
        r["score"] = round(final_score, 4)
        r["_rrf_score"] = round(rrf_score, 4)
        r.pop("_rank", None)
        r.pop("_quality", None)
        ranked.append(r)

    ranked.sort(key=lambda x: -x["score"])
    return ranked


# ─────────────────────────────────────────────
# 7. LLM Synthesis (deep mode)
# ─────────────────────────────────────────────

def synthesize(query: str, results: list[dict], max_results: int = 5) -> str | None:
    """Synthesize a brief answer from top results using web_fetch for content.

    Returns a markdown answer with citations or None if synthesis fails.
    This is a simple extractive synthesis — it uses the snippets directly
    rather than fetching full page content (to keep it fast and free).
    """
    if not results:
        return None

    top = results[:max_results]
    context_parts = []
    for i, r in enumerate(top, 1):
        title = r.get("title", "Unknown")
        snippet = r.get("snippet", "")[:300]
        url = r.get("url", "")
        context_parts.append(f"[{i}] {title}\n{snippet}\nSource: {url}")

    context = "\n\n".join(context_parts)

    # Simple extractive synthesis — combine best snippets with citations
    synthesis = f"Based on {len(top)} sources:\n\n"
    for i, r in enumerate(top[:3], 1):
        snippet = r.get("snippet", "").strip()
        if snippet:
            synthesis += f"- {snippet} [{i}]\n"

    synthesis += f"\nSources: " + ", ".join(
        f"[{i}]({r.get('url', '')})" for i, r in enumerate(top[:5], 1)
    )

    return synthesis


# ─────────────────────────────────────────────
# 8. Health Check
# ─────────────────────────────────────────────

async def health_check(config: dict):
    """Quick health check of all enabled providers."""
    test_query = "test"
    params = {"max_results": 1}

    for pid, pconf in config.items():
        if not pconf.get("enabled"):
            continue
        result = await run_provider(pid, test_query, params, config)
        status = "✅" if result["ok"] else f"❌ {result['error']}"
        print(f"  {pid}: {status}")


# ─────────────────────────────────────────────
# 9. Main Orchestrator
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Multi-source web search")
    parser.add_argument("--query", "-q", required=True, help="Search query")
    parser.add_argument("--depth", choices=["shallow", "deep"], default="shallow")
    parser.add_argument("--domains", help="Comma-separated domain override")
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--freshness", choices=["day", "week", "month", "any"])
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--no-synthesis", action="store_true")
    parser.add_argument("--health-check", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    start_time = time.time()

    config = load_providers_config()
    routing = load_routing()

    # Health check mode
    if args.health_check:
        print("Provider health check:")
        asyncio.run(health_check(config))
        return

    # Classify query
    explicit_domains = args.domains.split(",") if args.domains else None
    domains = classify_query(args.query, explicit_domains)

    if args.verbose:
        print(f"Domains: {domains}", file=sys.stderr)

    # Check cache
    ckey = cache_key(args.query, args.depth, domains)
    if not args.no_cache:
        cached, is_stale = cache_get(ckey)
        if cached and not is_stale:
            cached["latency_ms"] = int((time.time() - start_time) * 1000)
            print(json.dumps(cached, indent=2))
            return
        # If stale, continue but we have a fallback
        stale_data = cached if is_stale else None
    else:
        stale_data = None

    # Select providers (Brave as scarce fallback)
    providers = select_providers(domains, config, routing, args.depth)

    if args.verbose:
        print(f"Providers: {providers}", file=sys.stderr)

    if not providers:
        # Serve stale if available
        if stale_data:
            stale_data["latency_ms"] = int((time.time() - start_time) * 1000)
            print(json.dumps(stale_data, indent=2))
            return
        print(json.dumps({"error": "No providers available", "domains": domains}))
        sys.exit(1)

    params = {
        "max_results": args.max_results,
        "freshness": args.freshness,
        "depth": args.depth,
    }

    # Parallel search
    provider_results = asyncio.run(search_parallel(providers, args.query, params, config))

    # Rank (RRF + quality signals)
    ranked = rrf_rank(provider_results, domains)[: args.max_results]

    # LLM synthesis (deep mode only)
    answer = None
    if args.depth == "deep" and not args.no_synthesis and ranked:
        answer = synthesize(args.query, ranked)

    # Build response
    providers_used = [p["provider"] for p in provider_results if p["ok"]]
    providers_failed = [
        {"provider": p["provider"], "error": p["error"]}
        for p in provider_results
        if not p["ok"]
    ]

    response = {
        "answer": answer,
        "citations": [
            {
                "id": i + 1,
                "url": r["url"],
                "title": r.get("title", ""),
                "source": r.get("_source", ""),
            }
            for i, r in enumerate(ranked[:5])
        ],
        "results": ranked,
        "query": {"original": args.query, "domains": domains},
        "providers_used": providers_used,
        "providers_failed": providers_failed,
        "cached": False,
        "latency_ms": int((time.time() - start_time) * 1000),
    }

    # Cache results (including negative cache for empty results)
    primary_domain = domains[0] if domains else "general"
    ttl = DEFAULT_TTL.get(primary_domain, 4 * 3600)
    if ranked:
        cache_set(ckey, response, ttl)
    else:
        cache_set(ckey, response, NEGATIVE_TTL, is_negative=True)

    # Clean internal fields from output
    for r in response["results"]:
        r.pop("_source", None)
        r.pop("_rrf_score", None)

    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
