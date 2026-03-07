"""Semantic Scholar API provider. 214M papers, free."""
import os
import urllib.request
import urllib.parse
import json


def search(query: str, params: dict) -> list[dict]:
    """Search academic papers via Semantic Scholar API."""
    max_results = min(params.get("max_results", 10), 100)

    qparams = {
        "query": query,
        "limit": str(max_results),
        "fields": "title,url,abstract,year,citationCount,authors",
    }

    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{urllib.parse.urlencode(qparams)}"
    headers = {"User-Agent": "lodekeeper-web-search"}

    api_key = os.environ.get("SEMANTIC_SCHOLAR_KEY", "")
    if api_key:
        headers["x-api-key"] = api_key

    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())

    results = []
    for paper in data.get("data", []):
        authors = ", ".join(a.get("name", "") for a in (paper.get("authors") or [])[:3])
        citations = paper.get("citationCount", 0) or 0
        year = paper.get("year", "")
        abstract = (paper.get("abstract") or "")[:300]

        results.append({
            "url": paper.get("url", ""),
            "title": paper.get("title", ""),
            "snippet": f"({year}) {authors} | {citations} citations | {abstract}",
            "published_at": str(year) if year else "",
        })

    return results
