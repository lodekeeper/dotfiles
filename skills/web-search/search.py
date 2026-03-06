#!/usr/bin/env python3
"""
Web Search Skill — Multi-source search orchestrator for OpenClaw.
Classifies queries, routes to optimal providers, ranks via RRF, optionally synthesizes.
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

# Ensure state dir exists
STATE_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# 1. Cache (SQLite, TTL-based)
# ─────────────────────────────────────────────

CACHE_DB = STATE_DIR / "cache.db"
DEFAULT_TTL = {
    "general": 4 * 3600,       # 4 hours
    "news": 1 * 3600,          # 1 hour
    "code": 8 * 3600,          # 8 hours
    "academic": 24 * 3600,     # 24 hours
    "encyclopedia": 24 * 3600, # 24 hours
    "ethereum": 4 * 3600,      # 4 hours
    "social": 2 * 3600,        # 2 hours
    "qa": 8 * 3600,            # 8 hours
    "package": 12 * 3600,      # 12 hours
}

def _cache_db():
    db = sqlite3.connect(str(CACHE_DB))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        data TEXT,
        created_at REAL,
        ttl INTEGER
    )""")
    return db

def cache_get(key: str) -> dict | None:
    db = _cache_db()
    row = db.execute("SELECT data, created_at, ttl FROM cache WHERE key = ?", (key,)).fetchone()
    db.close()
    if row and (time.time() - row[1]) < row[2]:
        result = json.loads(row[0])
        result["cached"] = True
        return result
    return None

def cache_set(key: str, data: dict, ttl: int):
    db = _cache_db()
    db.execute(
        "INSERT OR REPLACE INTO cache (key, data, created_at, ttl) VALUES (?, ?, ?, ?)",
        (key, json.dumps(data), time.time(), ttl)
    )
    db.commit()
    db.close()

def cache_key(query: str, depth: str, domains: list[str]) -> str:
    raw = f"{query.lower().strip()}|{depth}|{','.join(sorted(domains))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ─────────────────────────────────────────────
# 2. Query Classification (rule-based, additive)
# ─────────────────────────────────────────────

DOMAIN_PATTERNS: dict[str, list[str]] = {
    "code": [
        r"\b(function|class|import|require|export|async|await|npm run)\b",
        r"\b(TypeError|SyntaxError|undefined is not|ENOENT|segfault)\b",
        r"`[^`]+`",
        r"\b[A-Z][a-z]+Error\b",
        r"\b(implementation|refactor|debug|stack trace|lint)\b",
    ],
    "package": [
        r"\bnpm (install|i|add|remove|update)\b",
        r"\b(package\.json|Cargo\.toml|pyproject\.toml)\b",
        r"\bversion\s+\d+\.\d+",
    ],
    "academic": [
        r"\b(paper|study|research|citation|doi:|arXiv|preprint)\b",
        r"\b(theorem|proof|dataset|benchmark|experiment)\b",
    ],
    "ethereum": [
        r"\b(EIP[-\s]?\d+|ERC[-\s]?\d+|beacon chain|consensus layer|execution layer)\b",
        r"\b(lodestar|prysm|lighthouse|teku|nimbus|grandine)\b",
        r"\b(solidity|vyper|ethers?\.js|web3|wagmi|viem)\b",
        r"\b(PeerDAS|ePBS|fork choice|slot|epoch|validator|attestation)\b",
        r"\bethresear\.ch\b",
    ],
    "social": [
        r"\b(hacker news|HN|community reaction|show hn|ask hn)\b",
        r"\bwhat do people think\b",
    ],
    "qa": [
        r"\b(how (do|does|to|can)|why (is|does|did)|what (is|are|does))\b",
        r"\b(stack overflow|stackoverflow|stack exchange)\b",
    ],
    "news": [
        r"\b(today|yesterday|this week|breaking|just announced|latest|recent)\b",
    ],
    "encyclopedia": [
        r"\b(what is|who is|define|definition of|explain)\b",
        r"\b(history of|wikipedia|wiki)\b",
    ],
}

def classify_query(query: str, explicit_domains: list[str] | None = None) -> list[str]:
    """Classify query into one or more search domains."""
    if explicit_domains:
        return explicit_domains

    matched = []
    q_lower = query.lower()
    for domain, patterns in DOMAIN_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, q_lower, re.IGNORECASE):
                matched.append(domain)
                break

    # Always include general as fallback
    if not matched or "general" not in matched:
        matched.append("general")

    return list(dict.fromkeys(matched))  # dedupe, preserve order


# ─────────────────────────────────────────────
# 3. Provider Loading & Routing
# ─────────────────────────────────────────────

def load_providers_config() -> dict:
    with open(CONFIG_DIR / "providers.json") as f:
        return json.load(f)

def load_routing() -> dict:
    with open(CONFIG_DIR / "routing.json") as f:
        return json.load(f)

def select_providers(domains: list[str], config: dict, routing: dict) -> list[str]:
    """Select providers for the given domains, respecting enabled status."""
    selected = []
    for domain in domains:
        route = routing.get(domain, routing.get("general", {}))
        for provider_id in route.get("primary", []) + route.get("fallback", []):
            if provider_id not in selected and config.get(provider_id, {}).get("enabled", False):
                selected.append(provider_id)

    # Cap at 4 providers to manage latency
    return selected[:4]


# ─────────────────────────────────────────────
# 4. Rate Limiting (SQLite token bucket)
# ─────────────────────────────────────────────

RATE_DB = STATE_DIR / "rate_limits.db"

def _rate_db():
    db = sqlite3.connect(str(RATE_DB))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS buckets (
        provider TEXT PRIMARY KEY,
        tokens REAL,
        max_tokens REAL,
        refill_rate REAL,
        last_refill REAL,
        daily_used INTEGER,
        daily_date TEXT
    )""")
    return db

def rate_limit_check(provider_id: str, config: dict) -> bool:
    """Check if provider has capacity. Returns True if OK to proceed."""
    pconf = config.get(provider_id, {})
    rl = pconf.get("rate_limit", {})
    rpm = rl.get("rpm", 60)
    rpd = rl.get("rpd")

    db = _rate_db()
    today = time.strftime("%Y-%m-%d")
    row = db.execute("SELECT tokens, max_tokens, refill_rate, last_refill, daily_used, daily_date FROM buckets WHERE provider = ?",
                     (provider_id,)).fetchone()

    now = time.time()
    if not row:
        # Initialize bucket
        db.execute("INSERT INTO buckets VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (provider_id, rpm - 1, rpm, rpm / 60.0, now, 1, today))
        db.commit()
        db.close()
        return True

    tokens, max_tokens, refill_rate, last_refill, daily_used, daily_date = row

    # Refill tokens based on elapsed time
    elapsed = now - last_refill
    tokens = min(max_tokens, tokens + elapsed * refill_rate)

    # Reset daily counter if new day
    if daily_date != today:
        daily_used = 0
        daily_date = today

    # Check limits
    if tokens < 1:
        db.close()
        return False
    if rpd and daily_used >= rpd:
        db.close()
        return False

    # Consume token
    db.execute("UPDATE buckets SET tokens=?, last_refill=?, daily_used=?, daily_date=? WHERE provider=?",
               (tokens - 1, now, daily_used + 1, daily_date, provider_id))
    db.commit()
    db.close()
    return True


# ─────────────────────────────────────────────
# 5. Provider Execution (async parallel)
# ─────────────────────────────────────────────

async def run_provider(provider_id: str, query: str, params: dict, config: dict) -> dict:
    """Run a single provider search. Returns results or error."""
    pconf = config.get(provider_id, {})
    timeout_ms = pconf.get("timeout_ms", 5000)

    # Rate limit check
    if not rate_limit_check(provider_id, config):
        return {"provider": provider_id, "ok": False, "error": "rate_limited", "results": []}

    try:
        # Dynamic import of provider module
        sys.path.insert(0, str(SKILL_DIR))
        mod = importlib.import_module(f"providers.{provider_id}")
        search_fn = getattr(mod, "search")

        # Run with timeout
        results = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, search_fn, query, params
            ),
            timeout=timeout_ms / 1000.0
        )

        return {"provider": provider_id, "ok": True, "results": results, "error": None}

    except asyncio.TimeoutError:
        return {"provider": provider_id, "ok": False, "error": "timeout", "results": []}
    except Exception as e:
        return {"provider": provider_id, "ok": False, "error": str(e)[:200], "results": []}


async def search_parallel(providers: list[str], query: str, params: dict, config: dict) -> list[dict]:
    """Run all providers in parallel, collect results."""
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
# 6. Aggregation & Ranking (RRF)
# ─────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    url = url.lower().rstrip("/")
    # Strip tracking params
    for param in ["utm_source", "utm_medium", "utm_campaign", "utm_content", "ref"]:
        url = re.sub(rf"[?&]{param}=[^&]*", "", url)
    url = re.sub(r"\?$", "", url)
    return url

def deduplicate(results: list[dict]) -> list[dict]:
    """Remove duplicate URLs, keeping highest-scored version."""
    seen = {}
    for r in results:
        nurl = normalize_url(r.get("url", ""))
        if nurl not in seen or r.get("_rank", 999) < seen[nurl].get("_rank", 999):
            seen[nurl] = r
    return list(seen.values())

def rrf_rank(provider_results: list[dict], domains: list[str]) -> list[dict]:
    """Reciprocal Rank Fusion across all providers. Returns sorted results."""
    K = 60  # RRF constant

    all_results = []
    for pr in provider_results:
        if not pr["ok"]:
            continue
        for rank, result in enumerate(pr["results"], 1):
            result["_source"] = pr["provider"]
            result["_rank"] = rank
            all_results.append(result)

    # Deduplicate first
    all_results = deduplicate(all_results)

    # Calculate RRF scores (group by URL, sum across providers)
    url_scores: dict[str, float] = {}
    url_results: dict[str, dict] = {}
    for r in all_results:
        nurl = normalize_url(r.get("url", ""))
        score = 1.0 / (K + r.get("_rank", 50))

        # Domain boost
        source = r.get("_source", "")
        if source in ["ethresearch", "github_code"] and "ethereum" in domains:
            score += 0.2
        elif source in ["semantic_scholar", "arxiv"] and "academic" in domains:
            score += 0.2
        elif source == "stack_exchange" and "qa" in domains:
            score += 0.2

        url_scores[nurl] = url_scores.get(nurl, 0) + score
        if nurl not in url_results:
            url_results[nurl] = r

    # Sort by score
    ranked = []
    for nurl, score in sorted(url_scores.items(), key=lambda x: -x[1]):
        r = url_results[nurl]
        r["score"] = round(score, 4)
        # Clean up internal fields
        r.pop("_rank", None)
        ranked.append(r)

    return ranked


# ─────────────────────────────────────────────
# 7. Main Orchestrator
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
    parser.add_argument("--health-check", action="store_true", help="Check all providers")
    args = parser.parse_args()

    start_time = time.time()

    # Load config
    config = load_providers_config()
    routing = load_routing()

    # Classify query
    explicit_domains = args.domains.split(",") if args.domains else None
    domains = classify_query(args.query, explicit_domains)

    # Check cache
    if not args.no_cache:
        ckey = cache_key(args.query, args.depth, domains)
        cached = cache_get(ckey)
        if cached:
            cached["latency_ms"] = int((time.time() - start_time) * 1000)
            print(json.dumps(cached, indent=2))
            return

    # Select providers
    providers = select_providers(domains, config, routing)

    if not providers:
        print(json.dumps({"error": "No providers available", "domains": domains}))
        sys.exit(1)

    # Search params
    params = {
        "max_results": args.max_results,
        "freshness": args.freshness,
        "depth": args.depth,
    }

    # Run parallel search
    provider_results = asyncio.run(search_parallel(providers, args.query, params, config))

    # Rank results
    ranked = rrf_rank(provider_results, domains)[:args.max_results]

    # Build response
    providers_used = [p["provider"] for p in provider_results if p["ok"]]
    providers_failed = [{"provider": p["provider"], "error": p["error"]}
                       for p in provider_results if not p["ok"]]

    response = {
        "answer": None,
        "citations": [
            {"id": i + 1, "url": r["url"], "title": r.get("title", ""), "source": r.get("_source", "")}
            for i, r in enumerate(ranked[:5])
        ],
        "results": ranked,
        "query": {"original": args.query, "domains": domains},
        "providers_used": providers_used,
        "providers_failed": providers_failed,
        "cached": False,
        "latency_ms": int((time.time() - start_time) * 1000),
    }

    # Cache results
    if not args.no_cache and ranked:
        primary_domain = domains[0] if domains else "general"
        ttl = DEFAULT_TTL.get(primary_domain, 4 * 3600)
        ckey = cache_key(args.query, args.depth, domains)
        cache_set(ckey, response, ttl)

    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
