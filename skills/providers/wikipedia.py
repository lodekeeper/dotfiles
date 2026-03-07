"""Wikipedia search API provider. Free, no auth."""
import urllib.request
import urllib.parse
import json


def search(query: str, params: dict) -> list[dict]:
    """Search Wikipedia articles."""
    max_results = min(params.get("max_results", 10), 20)

    # Use Wikipedia's opensearch API for suggestions, then text search for snippets
    qparams = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": str(max_results),
        "format": "json",
        "srprop": "snippet|timestamp",
    }

    url = f"https://en.wikipedia.org/w/api.php?{urllib.parse.urlencode(qparams)}"
    req = urllib.request.Request(url, headers={"User-Agent": "lodekeeper-web-search"})

    with urllib.request.urlopen(req, timeout=3) as resp:
        data = json.loads(resp.read().decode())

    results = []
    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        # Strip HTML tags from snippet
        import re
        snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))

        results.append({
            "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
            "title": title,
            "snippet": snippet[:500],
            "published_at": item.get("timestamp", ""),
        })

    return results
