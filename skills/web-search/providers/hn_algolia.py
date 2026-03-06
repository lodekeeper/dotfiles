"""Hacker News search via Algolia API. Free, no auth, 10K req/hr."""
import urllib.request
import urllib.parse
import json
import time


def search(query: str, params: dict) -> list[dict]:
    """Search HN stories and comments via Algolia."""
    max_results = min(params.get("max_results", 10), 20)

    qparams = {
        "query": query,
        "tags": "story",
        "hitsPerPage": str(max_results),
    }

    # Freshness filter
    if params.get("freshness") == "day":
        qparams["numericFilters"] = f"created_at_i>{int(time.time()) - 86400}"
    elif params.get("freshness") == "week":
        qparams["numericFilters"] = f"created_at_i>{int(time.time()) - 604800}"
    elif params.get("freshness") == "month":
        qparams["numericFilters"] = f"created_at_i>{int(time.time()) - 2592000}"

    url = f"https://hn.algolia.com/api/v1/search?{urllib.parse.urlencode(qparams)}"
    req = urllib.request.Request(url, headers={"User-Agent": "lodekeeper-web-search"})

    with urllib.request.urlopen(req, timeout=4) as resp:
        data = json.loads(resp.read().decode())

    results = []
    for hit in data.get("hits", []):
        hn_url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
        story_url = hit.get("url", hn_url)
        points = hit.get("points", 0) or 0
        comments = hit.get("num_comments", 0) or 0
        results.append({
            "url": story_url,
            "title": hit.get("title", ""),
            "snippet": f"HN: {points} points, {comments} comments | {hn_url}",
            "published_at": hit.get("created_at", ""),
        })

    return results
