"""Brave Search API provider."""
import os
import urllib.request
import urllib.parse
import json
import gzip
from pathlib import Path


def _load_api_key() -> str:
    """Load Brave API key from env, then OpenClaw config fallback."""
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if api_key:
        return api_key

    # Fallback: reuse configured key from OpenClaw built-in web search
    try:
        cfg_path = Path.home() / ".openclaw" / "openclaw.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            return (((cfg.get("tools") or {}).get("web") or {}).get("search") or {}).get("apiKey", "")
    except Exception:
        pass

    return ""


def search(query: str, params: dict) -> list[dict]:
    """Search via Brave Search API."""
    api_key = _load_api_key()
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY not set (env or tools.web.search.apiKey)")

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
        raw = resp.read()
        encoding = (resp.headers.get("Content-Encoding") or "").lower()
        if "gzip" in encoding:
            raw = gzip.decompress(raw)
        else:
            # Some environments return gzip without header; detect by magic bytes
            if len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B:
                raw = gzip.decompress(raw)
        data = json.loads(raw.decode("utf-8"))

    results = []
    for item in data.get("web", {}).get("results", []):
        results.append({
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "snippet": item.get("description", "")[:500],
            "published_at": item.get("page_age", ""),
        })

    return results
