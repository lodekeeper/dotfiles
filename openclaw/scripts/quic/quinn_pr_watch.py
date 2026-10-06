#!/usr/bin/env python3
"""List recent quinn-rs/quinn code changes for review: PRs (by head commit) and commits pushed to main / 0.11.x
without an associated PR.

Each item has a stable `id` and a `sha`. The automation gate compares them with its saved state, so a PR is
reviewed again when its head commit changes. Items that only touch docs/CI/benchmarks/release metadata, or that
come from dependency bots, are marked `trivial` and are never reviewed. `backfill` marks the items worth a first
pass when the watcher starts: open PRs updated in the last 30 days, plus anything merged or pushed after the latest
quinn-proto release.

Always exits 0. The last stdout line is one JSON object. `ok: false` means the check itself failed.
"""

import json
import re
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone

BRANCHES = ("main", "0.11.x")
BOT_RE = re.compile(r"dependabot|renovate|github-actions", re.I)
TRIVIAL_PATH_RE = re.compile(r"^(\.github/|docs/|book/|perf/|bench/|fuzz/corpus/)|\.md$|^(Cargo\.toml|[^/]+/Cargo\.toml|Cargo\.lock|deny\.toml|LICENSE.*)$")

QUERY = """
query($since: GitTimestamp!) {
  repository(owner: "quinn-rs", name: "quinn") {
    pullRequests(first: 100, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        number title state isDraft createdAt updatedAt mergedAt headRefOid baseRefName url
        author { login }
        files(first: 100) { totalCount nodes { path } }
      }
    }
    %s
  }
}
"""
BRANCH_FRAGMENT = """
    b%d: ref(qualifiedName: "refs/heads/%s") {
      target { ... on Commit { history(first: 50, since: $since) {
        nodes { oid messageHeadline committedDate url associatedPullRequests(first: 1) { nodes { number } } }
      } } }
    }"""


def latest_proto_release():
    req = urllib.request.Request(
        "https://crates.io/api/v1/crates/quinn-proto",
        headers={"User-Agent": "lodekeeper-quinn-watch (github.com/lodekeeper)"},
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.load(res)
    newest = data["crate"]["max_stable_version"]
    version = next(v for v in data["versions"] if v["num"] == newest)
    return newest, datetime.fromisoformat(version["created_at"].replace("Z", "+00:00"))


def parse_ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def run():
    now = datetime.now(timezone.utc)
    release, released_at = latest_proto_release()
    since = min(released_at, now - timedelta(days=14))
    query = QUERY % "".join(BRANCH_FRAGMENT % (i, b) for i, b in enumerate(BRANCHES))
    res = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}", "-f", f"since={since.isoformat()}"],
        capture_output=True, text=True, timeout=25,
    )
    if res.returncode != 0:
        raise RuntimeError(f"graphql failed: {res.stderr.strip()[:300]}")
    repo = json.loads(res.stdout)["data"]["repository"]

    items = []
    for pr in repo["pullRequests"]["nodes"]:
        paths = [f["path"] for f in pr["files"]["nodes"]]
        author = (pr.get("author") or {}).get("login") or "ghost"
        trivial = bool(BOT_RE.search(author)) or (
            pr["files"]["totalCount"] <= len(paths) and bool(paths) and all(TRIVIAL_PATH_RE.search(p) for p in paths)
        )
        merged_at = parse_ts(pr["mergedAt"])
        updated_at = parse_ts(pr["updatedAt"])
        backfill = (pr["state"] == "OPEN" and updated_at >= now - timedelta(days=30)) or bool(merged_at and merged_at >= released_at)
        items.append({
            "id": f"pr:{pr['number']}",
            "sha": pr["headRefOid"][:12],
            "title": pr["title"][:120],
            "state": "DRAFT" if pr["isDraft"] and pr["state"] == "OPEN" else pr["state"],
            "base": pr["baseRefName"],
            "author": author,
            "updated_at": pr["updatedAt"],
            "merged_at": pr["mergedAt"],
            "url": pr["url"],
            "files": pr["files"]["totalCount"],
            "trivial": trivial,
            "backfill": backfill,
        })

    seen_commits = set()
    for i, branch in enumerate(BRANCHES):
        ref = repo.get(f"b{i}")
        if not ref:
            raise RuntimeError(f"branch {branch} not found")
        for c in ref["target"]["history"]["nodes"]:
            if c["associatedPullRequests"]["nodes"] or c["oid"] in seen_commits:
                continue
            seen_commits.add(c["oid"])
            committed = parse_ts(c["committedDate"])
            items.append({
                "id": f"commit:{c['oid'][:12]}",
                "sha": c["oid"][:12],
                "title": c["messageHeadline"][:120],
                "state": f"PUSHED:{branch}",
                "base": branch,
                "updated_at": c["committedDate"],
                "url": c["url"],
                "trivial": False,
                "backfill": committed >= released_at,
            })

    return {
        "ok": True,
        "checked_at": now.isoformat(timespec="seconds"),
        "latest_quinn_proto": release,
        "latest_quinn_proto_at": released_at.isoformat(timespec="seconds"),
        "items": items,
    }


def main():
    try:
        out = run()
    except Exception as e:  # noqa: BLE001 - the gate must always get a JSON line
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"[:500]}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
