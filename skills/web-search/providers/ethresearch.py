"""ethresear.ch Discourse API provider. Free, no auth for search."""
import urllib.request
import urllib.parse
import json


def search(query: str, params: dict) -> list[dict]:
    """Search ethresear.ch (Ethereum research forum) via Discourse API."""
    max_results = min(params.get("max_results", 10), 50)

    # Discourse search API
    url = f"https://ethresear.ch/search.json?{urllib.parse.urlencode({'q': query})}"
    req = urllib.request.Request(url, headers={"User-Agent": "lodekeeper-web-search"})

    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())

    results = []

    # Topics
    for topic in (data.get("topics") or [])[:max_results]:
        topic_id = topic.get("id", "")
        slug = topic.get("slug", "")
        results.append({
            "url": f"https://ethresear.ch/t/{slug}/{topic_id}",
            "title": topic.get("title", ""),
            "snippet": f"Posts: {topic.get('posts_count', 0)}, Views: {topic.get('views', 0)}, "
                       f"Likes: {topic.get('like_count', 0)} | Created: {topic.get('created_at', '')}",
            "published_at": topic.get("created_at", ""),
        })

    # Posts (if any)
    for post in (data.get("posts") or [])[:max_results - len(results)]:
        topic_id = post.get("topic_id", "")
        blurb = post.get("blurb", "")[:300]
        results.append({
            "url": f"https://ethresear.ch/t/{topic_id}/{post.get('post_number', 1)}",
            "title": f"Post in topic #{topic_id}",
            "snippet": blurb,
        })

    return results[:max_results]
