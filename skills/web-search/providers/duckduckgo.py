"""DuckDuckGo search provider (unofficial, via the ddgs library — successor of duckduckgo-search)."""


def search(query: str, params: dict) -> list[dict]:
    """Search via the ddgs Python library. Unofficial — may break."""
    try:
        from ddgs import DDGS
    except ImportError:
        raise RuntimeError("ddgs not installed. Run: python3 -m pip install --user --break-system-packages ddgs")

    max_results = min(params.get("max_results", 10), 20)

    timelimit = None
    if params.get("freshness") == "day":
        timelimit = "d"
    elif params.get("freshness") == "week":
        timelimit = "w"
    elif params.get("freshness") == "month":
        timelimit = "m"

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results, timelimit=timelimit):
            results.append({
                "url": r.get("href", ""),
                "title": r.get("title", ""),
                "snippet": r.get("body", "")[:500],
            })

    return results
