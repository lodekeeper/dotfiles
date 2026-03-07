"""GitHub Code Search API provider."""
import os
import urllib.request
import urllib.parse
import json


def search(query: str, params: dict) -> list[dict]:
    """Search code on GitHub via REST API. Requires GITHUB_TOKEN."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set")

    max_results = min(params.get("max_results", 10), 30)
    url = f"https://api.github.com/search/code?{urllib.parse.urlencode({'q': query, 'per_page': str(max_results)})}"

    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
        "User-Agent": "lodekeeper-web-search",
    })

    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())

    results = []
    for item in data.get("items", []):
        repo = item.get("repository", {})
        results.append({
            "url": item.get("html_url", ""),
            "title": f"{repo.get('full_name', '')}/{item.get('name', '')}",
            "snippet": f"Path: {item.get('path', '')} | Repo: {repo.get('full_name', '')} ({repo.get('description', '')[:100]})",
        })

    return results
