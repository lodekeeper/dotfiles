"""GitHub Code Search API provider."""
import os
import subprocess
import urllib.request
import urllib.parse
import json


def _get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def search(query: str, params: dict) -> list[dict]:
    """Search code on GitHub via REST API. Uses GITHUB_TOKEN or gh CLI auth."""
    token = _get_token()
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set and gh CLI not authenticated")

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
