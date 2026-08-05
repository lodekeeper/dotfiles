#!/usr/bin/env python3
"""Scrape recent ethereum/EIPs PR feedback from likely EIP editors.

The script keeps raw evidence and a lightweight regex categorization so a
human-authored AGENTS.md draft can be checked against actual review history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


OWNER = "ethereum"
REPO = "EIPs"
API = "https://api.github.com"

# Current and emeritus editors from EIPS/eip-1.md as of 2026-08-04.
EIP_EDITORS = {
    "lightclient",
    "SamWilsn",
    "xinbenlv",
    "g11tech",
    "jochem-brouwer",
    "axic",
    "cdetrio",
    "Pandapip1",
    "gcolvin",
    "Souptacular",
    "wanderer",
    "MicahZoltu",
    "arachnid",
    "nicksavers",
    "vbuterin",
}

CATEGORIES: dict[str, list[str]] = {
    "discussions_to": [
        r"\bdiscussions?-to\b",
        r"ethereum magicians",
        r"\bmagicians\b",
        r"discussion thread",
        r"discussion topic",
    ],
    "external_links": [
        r"external link",
        r"permalink",
        r"\bassets?/",
        r"links? to",
        r"remove (?:this|the) link",
        r"anchor(?:ed)? to (?:a )?(?:specific )?commit",
    ],
    "rfc2119_keywords": [
        r"\bMUST\b",
        r"\bSHOULD\b",
        r"\bSHALL\b",
        r"\bREQUIRED\b",
        r"\bOPTIONAL\b",
        r"\bRFC 2119\b",
        r"\bRFC 8174\b",
        r"normative",
    ],
    "final_tense": [
        r"written as if",
        r"\bFinal\b",
        r"future tense",
        r"\bwill\b",
        r"\bproposed\b",
        r"\bproposal(?:'s)? status\b",
        r"status of other proposals",
    ],
    "front_matter": [
        r"preamble",
        r"front matter",
        r"\bheader\b",
        r"\bmetadata\b",
        r"\btitle\b",
        r"\bdescription\b",
        r"\bauthor\b",
        r"\bcategory\b",
        r"\bstatus\b",
        r"\bcreated\b",
        r"\brequires\b",
    ],
    "requires_dependency": [
        r"\brequires\b",
        r"depend(?:s|ency|encies)",
        r"cannot be understood",
    ],
    "motivation_rationale": [
        r"\bMotivation\b",
        r"\bRationale\b",
        r"motivat(?:e|ion)",
        r"design decision",
    ],
    "security_considerations": [
        r"Security Considerations",
        r"security implications",
        r"generic",
        r"best practices",
        r"audit your code",
    ],
    "test_cases": [
        r"Test Cases",
        r"test vectors?",
        r"tests?",
        r"consensus changes?",
    ],
    "reference_implementation": [
        r"Reference Implementation",
        r"implementation",
        r"reference code",
    ],
    "implementation_agnostic": [
        r"implementation[- ]specific",
        r"implementation[- ]independent",
        r"agnostic",
        r"externally visible behavior",
    ],
    "template_structure": [
        r"template",
        r"section",
        r"heading",
        r"Abstract",
        r"Copyright",
        r"CC0",
        r"Backwards Compatibility",
    ],
    "style_language": [
        r"title case",
        r"sentence case",
        r"backticks?",
        r"uppercase",
        r"abbreviation",
        r"hyphen",
        r"grammar",
        r"typo",
        r"wording",
        r"paragraph",
    ],
    "erc_split_scope": [
        r"\bERC\b",
        r"ethereum/ercs",
        r"moved to ERCs",
        r"not an EIP",
    ],
    "process_status": [
        r"Draft",
        r"Review",
        r"Last Call",
        r"Stagnant",
        r"Withdrawn",
        r"status update",
        r"move to",
    ],
}


@dataclass
class GitHubClient:
    token: str

    def request_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode(params or {})
        url = f"{API}{path}"
        if query:
            url = f"{url}?{query}"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lodekeeper-eips-feedback-scraper",
        }
        req = urllib.request.Request(url, headers=headers)
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as err:
                body = err.read().decode("utf-8", errors="replace")
                if err.code in {403, 429} and attempt < 5:
                    retry_after = err.headers.get("Retry-After")
                    sleep_s = int(retry_after) if retry_after else 10 * (attempt + 1)
                    print(f"[warn] throttled {err.code} for {path}; sleeping {sleep_s}s", file=sys.stderr)
                    time.sleep(sleep_s)
                    continue
                raise RuntimeError(f"GitHub API failed {err.code} for {url}: {body}") from err

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        items: list[Any] = []
        page = 1
        while True:
            page_params = dict(params or {})
            page_params.update({"per_page": 100, "page": page})
            batch = self.request_json(path, page_params)
            if not isinstance(batch, list):
                raise TypeError(f"Expected list response for {path}, got {type(batch).__name__}")
            items.extend(batch)
            if len(batch) < 100:
                return items
            page += 1


def get_token() -> str:
    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    if not token:
        raise RuntimeError("gh auth token returned empty output")
    return token


def normalize_comment(pr: dict[str, Any], kind: str, item: dict[str, Any]) -> dict[str, Any]:
    body = item.get("body") or ""
    user = (item.get("user") or {}).get("login") or ""
    created_at = item.get("created_at") or item.get("submitted_at") or ""
    return {
        "pr": pr["number"],
        "pr_title": pr.get("title", ""),
        "pr_state": pr.get("state", ""),
        "pr_created_at": pr.get("created_at", ""),
        "kind": kind,
        "author": user,
        "author_association": item.get("author_association", ""),
        "created_at": created_at,
        "url": item.get("html_url", ""),
        "path": item.get("path", ""),
        "body": body.strip(),
    }


def categorize(body: str) -> list[str]:
    import re

    matches: list[str] = []
    for name, patterns in CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, body, flags=re.IGNORECASE):
                matches.append(name)
                break
    return matches


def fetch_pr_feedback(client: GitHubClient, pr: dict[str, Any]) -> list[dict[str, Any]]:
    n = pr["number"]
    comments: list[dict[str, Any]] = []
    for item in client.paginate(f"/repos/{OWNER}/{REPO}/issues/{n}/comments"):
        comments.append(normalize_comment(pr, "issue_comment", item))
    for item in client.paginate(f"/repos/{OWNER}/{REPO}/pulls/{n}/comments"):
        comments.append(normalize_comment(pr, "review_comment", item))
    for item in client.paginate(f"/repos/{OWNER}/{REPO}/pulls/{n}/reviews"):
        if item.get("body"):
            comments.append(normalize_comment(pr, "review_body", item))
    return comments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--out-dir", type=Path, default=Path("notes/eip-editor-agents/data"))
    args = parser.parse_args()

    client = GitHubClient(get_token())
    args.out_dir.mkdir(parents=True, exist_ok=True)

    prs: list[dict[str, Any]] = []
    page = 1
    while len(prs) < args.limit:
        batch = client.request_json(
            f"/repos/{OWNER}/{REPO}/pulls",
            {
                "state": "all",
                "sort": "created",
                "direction": "desc",
                "per_page": min(100, args.limit - len(prs)),
                "page": page,
            },
        )
        if not batch:
            break
        prs.extend(batch)
        print(f"[info] fetched PR list page {page}; total PRs={len(prs)}", file=sys.stderr)
        page += 1

    (args.out_dir / "recent_prs.json").write_text(json.dumps(prs, indent=2), encoding="utf-8")

    all_comments: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_pr_feedback, client, pr): pr for pr in prs}
        done = 0
        for future in as_completed(futures):
            pr = futures[future]
            try:
                all_comments.extend(future.result())
            except Exception as exc:  # noqa: BLE001 - keep partial scrape useful.
                print(f"[error] PR #{pr['number']} failed: {exc}", file=sys.stderr)
            done += 1
            if done % 50 == 0 or done == len(prs):
                print(f"[info] fetched feedback for {done}/{len(prs)} PRs; comments={len(all_comments)}", file=sys.stderr)

    editor_comments = [
        {**comment, "categories": categorize(comment["body"])}
        for comment in all_comments
        if comment["author"] in EIP_EDITORS and comment["body"]
    ]
    nonempty_comments = [comment for comment in all_comments if comment["body"]]

    category_counts: dict[str, int] = {name: 0 for name in CATEGORIES}
    examples: dict[str, list[dict[str, str]]] = {name: [] for name in CATEGORIES}
    for comment in editor_comments:
        for category in comment["categories"]:
            category_counts[category] += 1
            if len(examples[category]) < 8:
                examples[category].append(
                    {
                        "pr": str(comment["pr"]),
                        "author": comment["author"],
                        "url": comment["url"],
                        "excerpt": " ".join(comment["body"].split())[:500],
                    }
                )

    summary = {
        "repo": f"{OWNER}/{REPO}",
        "sample_prs": len(prs),
        "oldest_pr": prs[-1]["number"] if prs else None,
        "newest_pr": prs[0]["number"] if prs else None,
        "all_nonempty_comments": len(nonempty_comments),
        "editor_nonempty_comments": len(editor_comments),
        "editors": sorted(EIP_EDITORS, key=str.lower),
        "category_counts": dict(sorted(category_counts.items(), key=lambda item: item[1], reverse=True)),
        "examples": examples,
    }

    (args.out_dir / "all_comments.jsonl").write_text(
        "\n".join(json.dumps(comment, ensure_ascii=False) for comment in all_comments) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "editor_comments.jsonl").write_text(
        "\n".join(json.dumps(comment, ensure_ascii=False) for comment in editor_comments) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
