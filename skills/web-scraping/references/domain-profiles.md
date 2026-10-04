# Domain Profile Learning (optional, not in use)

Moved from `SKILL.md` (2026-10-04). Not wired into `scripts/auto_scrape.py`, and `~/camoufox-env/domain-profiles.json` did not exist when this was moved; `save_profile()` creates it on first use.

For repeated scraping of the same domains, remember which tier works:

```python
"""Simple domain profile store — remember what works."""
import json, os
from urllib.parse import urlparse

PROFILE_PATH = os.path.expanduser("~/camoufox-env/domain-profiles.json")

def load_profiles() -> dict:
    if os.path.isfile(PROFILE_PATH):
        with open(PROFILE_PATH) as f:
            return json.load(f)
    return {}

def save_profile(url: str, tier: int, success: bool):
    domain = urlparse(url).netloc
    profiles = load_profiles()
    profiles.setdefault(domain, {"successes": {}, "failures": {}})
    key = "successes" if success else "failures"
    profiles[domain][key][str(tier)] = profiles[domain][key].get(str(tier), 0) + 1
    with open(PROFILE_PATH, "w") as f:
        json.dump(profiles, f, indent=2)

def best_tier(url: str) -> int:
    """Return the cheapest tier that has succeeded for this domain."""
    domain = urlparse(url).netloc
    profiles = load_profiles()
    if domain in profiles:
        for tier in [1, 2, 3]:
            if profiles[domain]["successes"].get(str(tier), 0) > 0:
                return tier
    return 1  # default: try cheapest first
```
