#!/usr/bin/env python3
"""Fetch all GitHub PR discussion surfaces in one compact report.

This prevents review follow-up passes from checking only inline review comments
while missing issue-level PR comments or review bodies.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


KIND_LABELS = {
    "issue_comment": ("Issue comment", "Issue comments"),
    "inline_review_comment": ("Inline review comment", "Inline review comments"),
    "review_body": ("Review body", "Review bodies"),
}


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def bail_if_github_suspended(skip_guard: bool) -> None:
    if skip_guard:
        return

    guard = workspace_root() / "scripts/github/check-github-access.sh"
    if not guard.exists() or not os.access(guard, os.X_OK):
        return

    cmd = [str(guard)]
    state_file = os.environ.get("GITHUB_ACCESS_STATE_FILE")
    max_age = os.environ.get("GITHUB_ACCESS_MAX_AGE_MINUTES")
    if state_file:
        cmd.extend(["--state-file", state_file])
    if max_age:
        cmd.extend(["--max-age-minutes", max_age])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
    except subprocess.TimeoutExpired:
        return

    if result.returncode == 2:
        print("GITHUB_SUSPENDED_SKIP")
        raise SystemExit(4)


def gh_items(endpoint: str) -> list[dict[str, Any]]:
    cmd = ["gh", "api", "--paginate", endpoint, "--jq", ".[] | @base64"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(f"ERROR: failed to fetch {endpoint}", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(1)

    items: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            decoded = base64.b64decode(line).decode("utf-8")
            items.append(json.loads(decoded))
        except Exception:
            continue
    return items


def normalize_issue_comment(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "issue_comment",
        "id": comment.get("id"),
        "author": (comment.get("user") or {}).get("login"),
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
        "url": comment.get("html_url"),
        "body": comment.get("body") or "",
    }


def normalize_inline_comment(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "inline_review_comment",
        "id": comment.get("id"),
        "author": (comment.get("user") or {}).get("login"),
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
        "url": comment.get("html_url"),
        "body": comment.get("body") or "",
        "path": comment.get("path"),
        "line": comment.get("line") or comment.get("original_line"),
        "in_reply_to_id": comment.get("in_reply_to_id"),
    }


def normalize_review_body(review: dict[str, Any], include_empty: bool) -> dict[str, Any] | None:
    body = review.get("body") or ""
    if not include_empty and not body.strip():
        return None

    return {
        "kind": "review_body",
        "id": review.get("id"),
        "author": (review.get("user") or {}).get("login"),
        "created_at": review.get("submitted_at"),
        "updated_at": review.get("submitted_at"),
        "url": review.get("html_url"),
        "body": body,
        "state": review.get("state"),
    }


def item_time(item: dict[str, Any]) -> str:
    return str(item.get("updated_at") or item.get("created_at") or "")


def cap_line(line: str, max_chars: int) -> str:
    line = " ".join(line.strip().split())
    if len(line) <= max_chars:
        return line
    if max_chars <= 3:
        return line[:max_chars]
    return line[: max_chars - 3] + "..."


def body_preview(body: str, body_lines: int, max_chars: int) -> list[str]:
    lines = [line.strip() for line in body.replace("\r", "").splitlines() if line.strip()]
    if not lines:
        return ["(empty body)"]
    return [cap_line(line, max_chars) for line in lines[:body_lines]]


def render_text(
    repo: str,
    pr: int,
    items: list[dict[str, Any]],
    displayed_items: list[dict[str, Any]],
    author_filters: list[str],
    limit: int,
    body_lines: int,
    max_body_chars: int,
) -> str:
    counts = {kind: 0 for kind in KIND_LABELS}
    for item in items:
        counts[item["kind"]] += 1

    lines = [f"PR discussion coverage for {repo}#{pr}"]
    lines.append("Fetched counts:")
    for kind, (_, plural_label) in KIND_LABELS.items():
        lines.append(f"- {plural_label}: {counts[kind]}")
    if author_filters:
        lines.append(f"Author filter: {', '.join(author_filters)}")
    lines.append(f"Display limit: latest {limit} per surface")

    for kind, (label, plural_label) in KIND_LABELS.items():
        section_items = [item for item in displayed_items if item["kind"] == kind]
        lines.append("")
        lines.append(plural_label)
        if not section_items:
            lines.append("- (none)")
            continue

        for item in section_items:
            where = ""
            if item.get("path"):
                where = f" {item.get('path')}:{item.get('line') or '?'}"
            reply = ""
            if item.get("in_reply_to_id"):
                reply = f" reply-to={item['in_reply_to_id']}"
            state = ""
            if item.get("state"):
                state = f" state={item['state']}"
            lines.append(
                f"- #{item.get('id')} {item.get('author') or 'unknown'} "
                f"{item_time(item)}{where}{reply}{state}"
            )
            if item.get("url"):
                lines.append(f"  {item['url']}")
            for preview_line in body_preview(str(item.get("body") or ""), body_lines, max_body_chars):
                lines.append(f"  {preview_line}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch GitHub PR issue comments, inline comments, and review bodies")
    parser.add_argument("pr", type=int, help="Pull request number")
    parser.add_argument("--repo", default="ChainSafe/lodestar", help="Repository owner/name (default: ChainSafe/lodestar)")
    parser.add_argument("--author", action="append", default=[], help="Only display comments from this author (repeatable)")
    parser.add_argument("--limit", type=int, default=20, help="Latest items to display per surface (default: 20)")
    parser.add_argument("--body-lines", type=int, default=2, help="Preview lines per item (default: 2)")
    parser.add_argument("--max-body-chars", type=int, default=220, help="Max characters per preview line (default: 220)")
    parser.add_argument("--include-empty-reviews", action="store_true", help="Include approval/comment reviews with empty bodies")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument("--check-only", action="store_true", help="Validate local prerequisites without calling GitHub")
    parser.add_argument("--skip-github-guard", action="store_true", help="Skip the cached GitHub suspension guard")
    args = parser.parse_args()

    if args.limit < 1:
        print("ERROR: --limit must be >= 1", file=sys.stderr)
        return 1
    if args.body_lines < 1:
        print("ERROR: --body-lines must be >= 1", file=sys.stderr)
        return 1
    if args.max_body_chars < 1:
        print("ERROR: --max-body-chars must be >= 1", file=sys.stderr)
        return 1

    if shutil.which("gh") is None:
        print("ERROR: gh CLI is not available", file=sys.stderr)
        return 1

    if not args.skip_github_guard:
        guard = workspace_root() / "scripts/github/check-github-access.sh"
        if not guard.exists() or not os.access(guard, os.X_OK):
            print(f"ERROR: GitHub access guard is missing or not executable: {guard}", file=sys.stderr)
            return 1

    if args.check_only:
        print("PR discussion scan preflight OK")
        print(f"Repo: {args.repo}")
        print(f"PR: {args.pr}")
        print("GitHub guard: enabled" if not args.skip_github_guard else "GitHub guard: skipped")
        return 0

    bail_if_github_suspended(args.skip_github_guard)

    issue_comments = [normalize_issue_comment(c) for c in gh_items(f"repos/{args.repo}/issues/{args.pr}/comments")]
    inline_comments = [normalize_inline_comment(c) for c in gh_items(f"repos/{args.repo}/pulls/{args.pr}/comments")]
    review_bodies = [
        normalized
        for review in gh_items(f"repos/{args.repo}/pulls/{args.pr}/reviews")
        if (normalized := normalize_review_body(review, args.include_empty_reviews)) is not None
    ]

    items = issue_comments + inline_comments + review_bodies
    author_filters = [author.lower() for author in args.author]
    if author_filters:
        filtered = [
            item
            for item in items
            if str(item.get("author") or "").lower() in author_filters
        ]
    else:
        filtered = items

    displayed: list[dict[str, Any]] = []
    for kind in KIND_LABELS:
        kind_items = [item for item in filtered if item["kind"] == kind]
        kind_items.sort(key=item_time, reverse=True)
        displayed.extend(kind_items[: args.limit])

    displayed.sort(key=item_time, reverse=True)
    counts = {kind: sum(1 for item in items if item["kind"] == kind) for kind in KIND_LABELS}

    if args.json:
        print(
            json.dumps(
                {
                    "repo": args.repo,
                    "pr": args.pr,
                    "counts": counts,
                    "authorFilters": args.author,
                    "generatedAt": datetime.now(tz=timezone.utc).isoformat(),
                    "items": filtered,
                    "displayedItems": displayed,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(
            render_text(
                args.repo,
                args.pr,
                items,
                displayed,
                args.author,
                args.limit,
                args.body_lines,
                args.max_body_chars,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
