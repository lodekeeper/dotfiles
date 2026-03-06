"""Stack Exchange API provider. Free with optional API key (10K/day keyed, 300/day without)."""
import os
import urllib.request
import urllib.parse
import json
import gzip
import io


def search(query: str, params: dict) -> list[dict]:
    """Search Stack Overflow via Stack Exchange API."""
    max_results = min(params.get("max_results", 10), 20)

    qparams = {
        "order": "desc",
        "sort": "relevance",
        "intitle": query,
        "site": "stackoverflow",
        "pagesize": str(max_results),
        "filter": "!nNPvSNdWme",  # Include body excerpt
    }

    api_key = os.environ.get("STACKEXCHANGE_KEY", "")
    if api_key:
        qparams["key"] = api_key

    url = f"https://api.stackexchange.com/2.3/search/advanced?{urllib.parse.urlencode(qparams)}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "lodekeeper-web-search",
        "Accept-Encoding": "gzip",
    })

    with urllib.request.urlopen(req, timeout=5) as resp:
        raw = resp.read()
        # SE API always returns gzip
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
        data = json.loads(raw.decode())

    results = []
    for item in data.get("items", []):
        score = item.get("score", 0)
        answers = item.get("answer_count", 0)
        accepted = "✅" if item.get("is_answered") else ""
        tags = ", ".join(item.get("tags", [])[:5])

        results.append({
            "url": item.get("link", ""),
            "title": item.get("title", ""),
            "snippet": f"{accepted} Score: {score}, Answers: {answers} | Tags: {tags}",
        })

    return results
