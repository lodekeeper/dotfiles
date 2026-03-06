"""Brave Search API provider."""
import os
import urllib.request
import urllib.parse
import json


def search(query: str, params: dict) -> list[dict]:
    """Search via Brave Search API."""
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY not set")

    max_results = min(params.get("max_results", 10), 20)
    base_url = "https://api.search.brave.com/res/v1/web/search"

    qparams = {
        "q": query,
        "count": str(max_results),
    }
    if params.get("freshness") == "day":
        qparams["freshness"] = "pd"
    elif params.get("freshness") == "week":
        qparams["freshness"] = "pw"
    elif params.get("freshness") == "month":
        qparams["freshness"] = "pm"

    url = f"{base_url}?{urllib.parse.urlencode(qparams)}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    })

    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())

    results = []
    for item in data.get("web", {}).get("results", []):
        results.append({
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "snippet": item.get("description", "")[:500],
            "published_at": item.get("page_age", ""),
        })

    return results
