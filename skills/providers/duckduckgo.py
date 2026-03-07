"""DuckDuckGo search provider (unofficial, via duckduckgo-search library)."""


def search(query: str, params: dict) -> list[dict]:
    """Search via duckduckgo-search Python library. Unofficial — may break."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        raise RuntimeError("duckduckgo-search not installed. Run: pip install duckduckgo-search")

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
