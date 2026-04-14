#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

OWNER_SELF = "lodekeeper"

# PRs that are NOT ours — skip all review comments on these.
# Format: "owner/repo#number"
EXCLUDED_PRS = {
    "ChainSafe/lodestar#8962",  # ensi321's EPBS import pipeline — not our PR
    "ChainSafe/lodestar#8988",  # ensi321's gloas range sync — not our PR, fully triaged
    "ChainSafe/lodestar#8994",  # Giulio2002's SSZ Engine API — not our PR
    "ChainSafe/lodestar#9100",  # ensi321's epbs-devnet-0 merge — not our PR, fully triaged
}


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_gh_json(args: List[str], timeout: int = 30) -> Any:
    cmd = ["gh", "api"] + args
    out = subprocess.check_output(cmd, text=True, timeout=timeout)
    return json.loads(out)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def parse_pr_key_from_subject_url(subject_url: str) -> Tuple[str, int]:
    # e.g. https://api.github.com/repos/ChainSafe/lodestar/pulls/8739
    m = re.search(r"/repos/([^/]+/[^/]+)/pulls/(\d+)$", subject_url)
    if not m:
        raise ValueError(f"Not a PR URL: {subject_url}")
    return m.group(1), int(m.group(2))


def is_explicit_ping(text: str, login: str = OWNER_SELF) -> bool:
    return bool(re.search(rf"@{re.escape(login)}\\b", text or "", re.IGNORECASE))


def extract_topic_routing_from_backlog(backlog_text: str) -> Dict[str, int]:
    """Extract PR → topic mappings from BACKLOG.md.

    Scans for patterns like:
    - Section headers: ## 📌 EPBS / devnet [topic:64]
    - PR lines: ### 🟡 PR #8993 — Engine SSZ transport [topic:395]
    - PR URLs: https://github.com/.../pull/123

    Returns a dict mapping 'repo#pr' (e.g. 'lodekeeper/lodestar#6') to topic ID.
    """
    topic_map: Dict[str, int] = {}
    current_topic: int | None = None

    for line in backlog_text.splitlines():
        # Check for [topic:ID] on any line
        topic_match = re.search(r'\[topic:(\d+)\]', line)
        if topic_match:
            current_topic = int(topic_match.group(1))

        # Section headers reset topic context
        if line.startswith('## '):
            if not topic_match:
                current_topic = None

        # Match PR references under current topic
        if current_topic is not None:
            # Match GitHub PR URLs
            for m in re.finditer(r'github\.com/([^/]+/[^/]+)/pull/(\d+)', line):
                repo, pr = m.group(1), m.group(2)
                topic_map[f"{repo}#{pr}"] = current_topic
            # Match "PR #NNN" patterns (assume ChainSafe/lodestar for unqualified refs)
            for m in re.finditer(r'PR\s+#(\d+)', line):
                pr = m.group(1)
                topic_map[f"ChainSafe/lodestar#{pr}"] = current_topic

    return topic_map


def extract_handled_ids_from_backlog(backlog_text: str) -> set:
    handled = set()
    in_done = False
    for line in backlog_text.splitlines():
        if line.startswith("### "):
            in_done = line.startswith("### ✅")
        if not in_done:
            continue
        for m in re.findall(r"issuecomment-(\d+)", line):
            handled.add(int(m))
        for m in re.findall(r"discussion_r(\d+)", line):
            handled.add(int(m))
        for m in re.findall(r"/pulls/comments/(\d+)", line):
            handled.add(int(m))
    return handled


def url_key_to_short(key: str) -> str | None:
    """Convert URL-format state key to short 'repo#pr' format. Returns None if not a URL key."""
    m = re.search(r"/repos/([^/]+/[^/]+)/pulls/(\d+)$", key)
    if m:
        return f"{m.group(1)}#{m.group(2)}"
    return None


def migrate_state_keys(state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge URL-format PR keys into short-format keys, taking max watermarks.

    Fixes data integrity issue where the same PR was tracked under both
    'https://api.github.com/repos/owner/repo/pulls/123' and 'owner/repo#123'
    with potentially diverged watermarks.
    """
    prs = state.get("prs", {})
    url_keys_to_remove = []

    for key in list(prs.keys()):
        short = url_key_to_short(key)
        if short is None:
            continue  # already short format

        url_entry = prs[key]
        url_keys_to_remove.append(key)

        if short in prs:
            # Merge: take max watermark from both entries
            existing = prs[short]
            existing["last_review_comment_id"] = max(
                int(existing.get("last_review_comment_id", 0)),
                int(url_entry.get("last_review_comment_id", 0)),
            )
            existing["last_issue_comment_id"] = max(
                int(existing.get("last_issue_comment_id", 0)),
                int(url_entry.get("last_issue_comment_id", 0)),
            )
        else:
            # Just rename the key
            prs[short] = url_entry

    for key in url_keys_to_remove:
        del prs[key]

    if url_keys_to_remove:
        print(f"Migrated {len(url_keys_to_remove)} URL-format state keys to short format", file=sys.stderr)

    return state


def normalize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    state.setdefault("version", 2)
    state.setdefault("prs", {})
    state.setdefault("updatedAt", utc_now_iso())
    migrate_state_keys(state)
    return state


def normalize_checklist(checklist: Dict[str, Any]) -> Dict[str, Any]:
    checklist.setdefault("version", 1)
    checklist.setdefault("items", {})
    checklist.setdefault("updatedAt", utc_now_iso())
    return checklist


def fetch_notifications() -> List[Dict[str, Any]]:
    # Use full notification stream (not just participating) so we do not miss PR comments that fail
    # to appear in the participating-only slice. Keep this focused to PR subjects only.
    data = fetch_paginated("notifications?all=true&per_page=100")
    out = []
    for n in data:
        try:
            unread = bool(n.get("unread"))
            updated = n.get("updated_at")
            last_read = n.get("last_read_at")
            has_new = unread or (updated and last_read and updated > last_read)
            if not has_new:
                continue
            subj = n.get("subject", {})
            if subj.get("type") != "PullRequest":
                continue
            out.append(
                {
                    "thread_id": str(n.get("id")),
                    "title": subj.get("title"),
                    "url": subj.get("url"),
                    "updated_at": updated,
                    "reason": (n.get("reason") or "").lower(),
                }
            )
        except Exception:
            continue
    return out


def fetch_paginated(endpoint: str) -> List[Dict[str, Any]]:
    """Fetch all pages from a GitHub API list endpoint."""
    page = 1
    all_items: List[Dict[str, Any]] = []
    while True:
        items = run_gh_json([f"{endpoint}{'&' if '?' in endpoint else '?'}per_page=100&page={page}"])
        if not items:
            break
        all_items.extend(items)
        if len(items) < 100:
            break
        page += 1
    return all_items


def fetch_pr_comments(repo: str, pr: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    review = fetch_paginated(f"repos/{repo}/pulls/{pr}/comments")
    issue = fetch_paginated(f"repos/{repo}/issues/{pr}/comments")
    return review, issue


def fetch_pr_reviews(repo: str, pr: int) -> List[Dict[str, Any]]:
    """Fetch top-level PR reviews (not inline comments).

    These are reviews submitted via the Reviews API with a body but potentially
    no inline comments. Without this, reviews like 'CHANGES_REQUESTED' with only
    a top-level body are invisible to the notification sweep.
    """
    try:
        reviews = fetch_paginated(f"repos/{repo}/pulls/{pr}/reviews")
        # Only return reviews with a non-empty body (skip empty approvals etc.)
        # Also skip pure APPROVED reviews without substantive body — those are acknowledgments
        out = []
        for r in reviews:
            body = (r.get("body") or "").strip()
            if not body:
                continue
            out.append(r)
        return out
    except Exception:
        return []


def is_pr_merged_or_closed(repo: str, pr: int) -> bool:
    """Check if a PR is merged or closed. Returns True for either state."""
    try:
        data = run_gh_json([f"repos/{repo}/pulls/{pr}"])
        if data.get("merged", False):
            return True
        if data.get("state") == "closed" and data.get("merged_at") is not None:
            return True
        if data.get("state") == "closed":
            return True
        return False
    except Exception as e:
        print(f"WARNING: is_pr_merged_or_closed({repo}#{pr}) failed: {e}", file=sys.stderr)
        return False


def mark_notification_done(thread_id: str) -> None:
    """Mark a GitHub notification thread as done (dismiss it)."""
    try:
        subprocess.check_call(
            ["gh", "api", "-X", "DELETE", f"notifications/threads/{thread_id}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except Exception as e:
        print(f"WARNING: failed to dismiss notification thread {thread_id}: {e}", file=sys.stderr)


def scan_open_prs_for_unreplied(state: Dict, checklist: Dict) -> List[Dict[str, Any]]:
    """Scan open PRs for comments not yet in the checklist.

    Scans TWO sources to catch comments missed by notification race conditions:
    1. All open PRs authored by lodekeeper (gh pr list)
    2. All open PRs tracked in state (previously notified, may not be our own)

    Returns synthetic notification-like dicts for PRs with new comments,
    so they can be processed by the main notification loop.
    """
    # Search across ALL repos for open PRs authored by lodekeeper
    try:
        search_results = json.loads(subprocess.check_output(
            ["gh", "search", "prs", "--author", OWNER_SELF, "--state", "open",
             "--json", "number,title,repository", "--limit", "50"],
            text=True, timeout=60,
        ))
        prs = []
        for sr in search_results:
            repo_info = sr.get("repository", {})
            repo_name = repo_info.get("nameWithOwner", "")
            if not repo_name:
                continue
            prs.append({
                "number": sr["number"],
                "title": sr.get("title", ""),
                "_repo": repo_name,
            })
    except Exception as e:
        print(f"WARNING: scan_open_prs (cross-repo search) failed: {e}", file=sys.stderr)
        # Fallback to just ChainSafe/lodestar
        try:
            fallback = json.loads(subprocess.check_output(
                ["gh", "pr", "list", "--author", OWNER_SELF, "--state", "open",
                 "--repo", "ChainSafe/lodestar", "--json", "number,title",
                 "--limit", "20"],
                text=True, timeout=30,
            ))
            prs = fallback
        except Exception as e2:
            print(f"WARNING: scan_open_prs fallback failed: {e2}", file=sys.stderr)
            prs = []

    # Build set of PR keys already covered by own-PR scan
    own_pr_keys = {f"{pr_info.get('_repo', 'ChainSafe/lodestar')}#{pr_info['number']}" for pr_info in prs}

    # Also scan PRs from state that we've previously been notified about
    # (catches non-owned PRs where we're a reviewer/participant).
    # Only check PRs that have open checklist items to avoid wasting API calls
    # on merged/closed PRs.
    open_checklist_prs = set()
    for item in checklist.get("items", {}).values():
        if item.get("status") == "open":
            r = item.get("repo", "")
            p = item.get("pr", 0)
            if r and p:
                open_checklist_prs.add(f"{r}#{p}")

    for pr_key, pr_state_entry in state.get("prs", {}).items():
        m = re.match(r"^([^#]+)#(\d+)$", pr_key)
        if not m:
            continue
        repo, pr_num = m.group(1), int(m.group(2))
        if f"{repo}#{pr_num}" in own_pr_keys:
            continue
        # Only scan if there are open checklist items OR the PR was recently updated
        if pr_key in open_checklist_prs:
            prs.append({"number": pr_num, "title": "", "_repo": repo})
            own_pr_keys.add(f"{repo}#{pr_num}")

    synthetic = []
    for pr_info in prs:
        pr_num = pr_info["number"]
        repo = pr_info.get("_repo", "ChainSafe/lodestar")
        pr_key = f"{repo}#{pr_num}"
        pr_state = state["prs"].get(pr_key, {})
        watermark_review = int(pr_state.get("last_review_comment_id", 0))
        watermark_issue = int(pr_state.get("last_issue_comment_id", 0))

        # Quick check: fetch latest comment IDs without full comment bodies
        try:
            review_comments = run_gh_json(
                [f"repos/{repo}/pulls/{pr_num}/comments?per_page=5&sort=created&direction=desc"]
            )
            issue_comments = run_gh_json(
                [f"repos/{repo}/issues/{pr_num}/comments?per_page=5&sort=created&direction=desc"]
            )
        except Exception:
            continue

        has_new_review = any(
            int(c["id"]) > watermark_review
            and (c.get("user", {}).get("login", "")).lower() != OWNER_SELF
            for c in review_comments
        )
        has_new_issue = any(
            int(c["id"]) > watermark_issue
            and (c.get("user", {}).get("login", "")).lower() != OWNER_SELF
            for c in issue_comments
        )

        if has_new_review or has_new_issue:
            synthetic.append({
                "thread_id": None,  # no notification thread to mark
                "title": pr_info.get("title", ""),
                "url": f"https://api.github.com/repos/{repo}/pulls/{pr_num}",
                "updated_at": utc_now_iso(),
                "reason": "open-pr-scan",
            })

    return synthetic


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="/home/openclaw/gh-notif-state.json")
    ap.add_argument("--checklist", default="/home/openclaw/gh-notif-checklist.json")
    ap.add_argument("--backlog", default="/home/openclaw/.openclaw/workspace/BACKLOG.md")
    ap.add_argument("--remind-hours", type=float, default=12.0)
    args = ap.parse_args()

    state_path = Path(args.state)
    checklist_path = Path(args.checklist)
    backlog_path = Path(args.backlog)

    state = normalize_state(load_json(state_path, {}))
    checklist = normalize_checklist(load_json(checklist_path, {}))

    backlog_text = backlog_path.read_text() if backlog_path.exists() else ""
    handled_ids = extract_handled_ids_from_backlog(backlog_text)
    topic_routing = extract_topic_routing_from_backlog(backlog_text)

    # Auto-mark from backlog done entries
    now = utc_now_iso()

    # Also auto-close any items where handledReason is set but status is still open (migration fix)
    for sid, item in checklist["items"].items():
        if item.get("status") == "open" and item.get("handledReason"):
            item["status"] = "done"
            item["doneAt"] = item.get("handledAt", now)
            item["doneReason"] = item["handledReason"]

    # Cache of merged/closed PR state to avoid duplicate API calls
    merged_pr_cache: Dict[str, bool] = {}
    # Cache PR author (for scope gating)
    pr_author_cache: Dict[str, str] = {}

    # Auto-close open items for PRs that are now merged/closed
    for sid, item in checklist["items"].items():
        if item.get("status") != "open":
            continue
        repo = item.get("repo", "")
        pr = item.get("pr", 0)
        if not repo or not pr:
            continue
        cache_key = f"{repo}#{pr}"
        if cache_key not in merged_pr_cache:
            merged_pr_cache[cache_key] = is_pr_merged_or_closed(repo, pr)
        if merged_pr_cache[cache_key]:
            item["status"] = "done"
            item["doneAt"] = now
            item["doneReason"] = "pr-merged"

    for sid, item in checklist["items"].items():
        if not sid.isdigit():
            continue
        if item.get("status") == "open" and int(sid) in handled_ids:
            item["status"] = "done"
            item["doneAt"] = now
            item["doneReason"] = "backlog-done-link"

    notifications = fetch_notifications()

    # Belt-and-suspenders: also scan ALL open PRs by lodekeeper for unreplied
    # comments, regardless of notification state. This catches comments missed
    # due to notification race conditions (marked read before script processes).
    open_pr_keys = scan_open_prs_for_unreplied(state, checklist)
    # Merge open PR keys into notification stream so they get processed below
    notification_pr_keys = set()

    actionable_new = []
    actionable_reminders = []
    # Collect thread IDs to mark as read AFTER state is saved (prevents race condition
    # where notification is marked read but state/watermarks aren't persisted yet).
    threads_to_mark_read: List[str] = []

    # Merge synthetic open-PR-scan entries with real notifications
    all_entries = notifications + open_pr_keys

    for n in all_entries:
        try:
            repo, pr = parse_pr_key_from_subject_url(n["url"])
        except Exception:
            continue

        pr_key = f"{repo}#{pr}"

        # Skip PRs that aren't ours — but still dismiss the notification
        # so it doesn't reappear every sweep cycle.
        if pr_key in EXCLUDED_PRS:
            if n.get("thread_id"):
                mark_notification_done(n["thread_id"])
            continue

        notification_pr_keys.add(pr_key)

        pr_state = state["prs"].setdefault(
            pr_key,
            {
                "last_review_comment_id": 0,
                "last_issue_comment_id": 0,
            },
        )

        if pr_key not in pr_author_cache:
            try:
                pr_data = run_gh_json([f"repos/{repo}/pulls/{pr}"])
                pr_author_cache[pr_key] = ((pr_data.get("user") or {}).get("login") or "").lower()
            except Exception:
                pr_author_cache[pr_key] = ""

        is_own_pr = pr_author_cache.get(pr_key, "") == OWNER_SELF
        notification_reason = (n.get("reason") or "").lower()

        review_comments, issue_comments = fetch_pr_comments(repo, pr)
        pr_reviews = fetch_pr_reviews(repo, pr)

        # Thread-aware dedupe: if lodekeeper has replied in-thread to any node in a review thread,
        # mark the entire parent thread as handled to avoid stale false-positive reminders.
        review_by_id = {int(r.get("id")): r for r in review_comments}

        def resolve_thread_root(comment_id: int) -> int:
            cur = comment_id
            seen = set()
            while True:
                rc = review_by_id.get(cur)
                if not rc:
                    return cur
                parent = rc.get("in_reply_to_id")
                if parent is None:
                    return cur
                try:
                    parent_id = int(parent)
                except Exception:
                    return cur
                if parent_id in seen:
                    return cur
                seen.add(cur)
                cur = parent_id

        def thread_has_owner_participation(comment_id: int) -> bool:
            """True if this review-comment thread includes lodekeeper in its ancestor chain.

            This captures non-owned PR cases where someone replies in-thread to one of
            our review comments without explicitly tagging @lodekeeper.
            """
            cur = comment_id
            seen = set()
            while True:
                rc = review_by_id.get(cur)
                if not rc:
                    return False
                author = ((rc.get("user") or {}).get("login") or "").lower()
                if author == OWNER_SELF:
                    return True
                parent = rc.get("in_reply_to_id")
                if parent is None:
                    return False
                try:
                    parent_id = int(parent)
                except Exception:
                    return False
                if parent_id in seen:
                    return False
                seen.add(cur)
                cur = parent_id

        owner_replied_review_roots = set()
        for rc in review_comments:
            r_author = (rc.get("user") or {}).get("login", "")
            in_reply_to = rc.get("in_reply_to_id")
            if r_author.lower() == OWNER_SELF and in_reply_to is not None:
                try:
                    owner_replied_review_roots.add(resolve_thread_root(int(in_reply_to)))
                except Exception:
                    pass

        # Update watermark candidates
        max_review = pr_state.get("last_review_comment_id", 0)
        max_issue = pr_state.get("last_issue_comment_id", 0)
        max_review_body = pr_state.get("last_review_body_id", 0)

        for c in review_comments:
            cid = int(c["id"])
            max_review = max(max_review, cid)
            author = (c.get("user") or {}).get("login", "")
            if author.lower() == OWNER_SELF:
                continue

            body = c.get("body") or ""
            in_scope = (
                is_own_pr
                or notification_reason == "mention"
                or is_explicit_ping(body)
                or thread_has_owner_participation(cid)
            )
            if not in_scope:
                existing = checklist["items"].get(str(cid))
                if existing is not None and existing.get("status") == "open":
                    existing["status"] = "done"
                    existing["doneAt"] = now
                    existing["doneReason"] = "out-of-scope-non-owned-no-mention"
                continue

            item = checklist["items"].get(str(cid))
            if item is None and cid > int(pr_state.get("last_review_comment_id", 0)):
                item = {
                    "id": cid,
                    "repo": repo,
                    "pr": pr,
                    "kind": "review",
                    "author": author,
                    "url": c.get("html_url"),
                    "createdAt": c.get("created_at"),
                    "status": "open",
                    "firstSeenAt": now,
                    "lastSeenAt": now,
                    "reportedCount": 0,
                }
                checklist["items"][str(cid)] = item
                actionable_new.append(item)
            elif item is not None:
                item["lastSeenAt"] = now

            # Auto-close stale reminder if we've replied in this thread.
            if item is not None and item.get("status") == "open":
                thread_root = resolve_thread_root(cid)
                if thread_root in owner_replied_review_roots:
                    item["status"] = "done"
                    item["doneAt"] = now
                    item["doneReason"] = "owner-replied-in-thread"

        # Process top-level PR review bodies (reviews submitted via the Reviews API
        # with a body but no inline comments — e.g. CHANGES_REQUESTED with text).
        for rv in pr_reviews:
            rv_id = int(rv["id"])
            max_review_body = max(max_review_body, rv_id)
            author = (rv.get("user") or {}).get("login", "")
            if author.lower() == OWNER_SELF:
                continue

            body = rv.get("body") or ""
            in_scope = (
                is_own_pr
                or notification_reason == "mention"
                or is_explicit_ping(body)
            )
            if not in_scope:
                continue

            # Use "rv_" prefix to distinguish from inline review comment IDs
            item_key = f"rv_{rv_id}"
            item = checklist["items"].get(item_key)
            if item is None and rv_id > int(pr_state.get("last_review_body_id", 0)):
                item = {
                    "id": rv_id,
                    "repo": repo,
                    "pr": pr,
                    "kind": "review-body",
                    "author": author,
                    "url": rv.get("html_url"),
                    "createdAt": rv.get("submitted_at"),
                    "status": "open",
                    "firstSeenAt": now,
                    "lastSeenAt": now,
                    "reportedCount": 0,
                    "reviewState": rv.get("state"),
                }
                checklist["items"][item_key] = item
                actionable_new.append(item)
            elif item is not None:
                item["lastSeenAt"] = now

            # Auto-close if we've already replied on the PR after this review.
            # Check both issue comments (PR-level) AND inline review comments
            # so that replies posted in review threads also satisfy the condition.
            if item is not None and item.get("status") == "open":
                review_time = rv.get("submitted_at", "")
                owner_reply_times = [
                    c.get("created_at", "") for c in issue_comments
                    if (c.get("user") or {}).get("login", "").lower() == OWNER_SELF
                ] + [
                    c.get("created_at", "") for c in review_comments
                    if (c.get("user") or {}).get("login", "").lower() == OWNER_SELF
                ]
                for owner_time in owner_reply_times:
                    if owner_time > review_time:
                        item["status"] = "done"
                        item["doneAt"] = now
                        item["doneReason"] = "owner-replied-after-review"
                        break

        # Build a set of issue comment IDs that lodekeeper has replied to.
        # For non-threaded issue comments, we check if any subsequent comment
        # from lodekeeper references or follows the target comment.
        owner_issue_comment_times = []
        for c in issue_comments:
            c_author = (c.get("user") or {}).get("login", "")
            if c_author.lower() == OWNER_SELF:
                owner_issue_comment_times.append(c.get("created_at", ""))

        # Check if lodekeeper reacted to issue comments (only for open checklist items
        # to avoid burning API calls on already-resolved items)
        reacted_issue_ids = set()
        if is_own_pr:
            open_issue_ids = {
                int(sid) for sid, item in checklist["items"].items()
                if item.get("status") == "open" and item.get("kind") == "issue"
                and item.get("repo") == repo and item.get("pr") == pr
            }
            for c in issue_comments:
                cid_check = int(c["id"])
                if cid_check not in open_issue_ids:
                    continue
                try:
                    reactions = run_gh_json(
                        [f"repos/{repo}/issues/comments/{cid_check}/reactions?per_page=100"]
                    )
                    for r in reactions:
                        if (r.get("user", {}).get("login", "")).lower() == OWNER_SELF:
                            reacted_issue_ids.add(cid_check)
                            break
                except Exception:
                    pass

        for c in issue_comments:
            cid = int(c["id"])
            max_issue = max(max_issue, cid)
            author = (c.get("user") or {}).get("login", "")
            if author.lower() == OWNER_SELF:
                continue

            body = c.get("body") or ""
            in_scope = is_own_pr or notification_reason == "mention" or is_explicit_ping(body)
            if not in_scope:
                existing = checklist["items"].get(str(cid))
                if existing is not None and existing.get("status") == "open":
                    existing["status"] = "done"
                    existing["doneAt"] = now
                    existing["doneReason"] = "out-of-scope-non-owned-no-mention"
                continue

            item = checklist["items"].get(str(cid))
            if item is None and cid > int(pr_state.get("last_issue_comment_id", 0)):
                item = {
                    "id": cid,
                    "repo": repo,
                    "pr": pr,
                    "kind": "issue",
                    "author": author,
                    "url": c.get("html_url"),
                    "createdAt": c.get("created_at"),
                    "status": "open",
                    "firstSeenAt": now,
                    "lastSeenAt": now,
                    "reportedCount": 0,
                }
                checklist["items"][str(cid)] = item
                actionable_new.append(item)
            elif item is not None:
                item["lastSeenAt"] = now

            # Auto-close if lodekeeper reacted to this comment (emoji = acknowledged)
            if item is not None and item.get("status") == "open" and cid in reacted_issue_ids:
                item["status"] = "done"
                item["doneAt"] = now
                item["doneReason"] = "owner-reacted"

            # Auto-close if lodekeeper posted a reply AFTER this comment
            if item is not None and item.get("status") == "open":
                comment_time = c.get("created_at", "")
                for owner_time in owner_issue_comment_times:
                    if owner_time > comment_time:
                        item["status"] = "done"
                        item["doneAt"] = now
                        item["doneReason"] = "owner-replied-after"
                        break

        pr_state["last_review_comment_id"] = max_review
        pr_state["last_issue_comment_id"] = max_issue
        pr_state["last_review_body_id"] = max_review_body

        # Defer notification marking to after state save (race condition fix).
        # Synthetic entries from open-PR-scan have no thread_id.
        if n.get("thread_id"):
            threads_to_mark_read.append(n["thread_id"])

        # Check merged status for the auto-close pass below (cache it now to
        # avoid duplicate API calls).
        if pr_key not in merged_pr_cache:
            merged_pr_cache[pr_key] = is_pr_merged_or_closed(repo, pr)
        # NOTE: we intentionally do NOT delete notification threads, even for
        # merged PRs. GitHub's "mark as done" (DELETE) may suppress future
        # notifications on the same thread, which would cause us to miss
        # post-merge comments. PATCH (mark as read) is sufficient — the
        # notification will only reappear if updated_at > last_read_at.

    # Filter out any items that were just auto-closed from actionable lists
    actionable_new = [i for i in actionable_new if i.get("status") == "open"]

    # Reminder for stale open entries (to avoid misses), throttled
    remind_delta = dt.timedelta(hours=float(args.remind_hours))
    now_dt = dt.datetime.now(dt.timezone.utc)
    for item in checklist["items"].values():
        if item.get("status") != "open":
            continue
        # Auto-close items reported excessively without resolution (safety net for
        # items that the auto-close logic can't reach, e.g. stale non-owned PR
        # comments whose watermarks are already caught up).
        if int(item.get("reportedCount", 0)) >= 20:
            item["status"] = "done"
            item["doneAt"] = now
            item["doneReason"] = "auto-closed-excessive-reminders"
            continue
        last_reported = item.get("lastReportedAt")
        if not last_reported:
            continue
        try:
            lr = dt.datetime.fromisoformat(last_reported.replace("Z", "+00:00"))
        except Exception:
            continue
        if now_dt - lr >= remind_delta:
            actionable_reminders.append(item)

    # stamp reported metadata
    for item in actionable_new + actionable_reminders:
        item["lastReportedAt"] = now
        item["reportedCount"] = int(item.get("reportedCount", 0)) + 1

    state["updatedAt"] = now
    checklist["updatedAt"] = now

    save_json(state_path, state)
    save_json(checklist_path, checklist)

    # NOW mark notifications as read — state is safely persisted, so even if
    # this step fails, the watermarks are saved and duplicates won't occur.
    for tid in threads_to_mark_read:
        try:
            subprocess.check_call(
                ["gh", "api", "-X", "PATCH", f"notifications/threads/{tid}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=20,
            )
        except Exception:
            pass

    if not actionable_new and not actionable_reminders:
        print("HEARTBEAT_OK")
        return 0

    # concise summary output for cron delivery
    print("GitHub notifications check complete.\n")

    # Collect topic routing for actionable PRs
    routed_topics: Dict[int, List[Dict]] = {}  # topic_id → items
    unrouted: List[Dict] = []

    for item in actionable_new:
        pr_key = f"{item['repo']}#{item['pr']}"
        topic_id = topic_routing.get(pr_key)
        if topic_id is not None:
            routed_topics.setdefault(topic_id, []).append(item)
        else:
            unrouted.append(item)

    if routed_topics:
        print("TOPIC-ROUTED comments (nudge these topic sessions):")
        for topic_id, items in routed_topics.items():
            print(f"\n  [topic:{topic_id}] session: agent:main:telegram:group:-1003764039429:topic:{topic_id}")
            for item in items:
                print(f"  - {item['repo']}#{item['pr']} [{item['kind']}] by {item['author']} — {item['url']}")

    if unrouted:
        print(f"\nNew actionable PR comments (no topic routing): {len(unrouted)}")
        for item in unrouted[:12]:
            print(f"- {item['repo']}#{item['pr']} [{item['kind']}] by {item['author']} — {item['url']}")

    if actionable_reminders:
        # Also route reminders to topics if applicable
        reminder_routed: Dict[int, List[Dict]] = {}
        reminder_unrouted: List[Dict] = []
        for item in actionable_reminders:
            pr_key = f"{item['repo']}#{item['pr']}"
            topic_id = topic_routing.get(pr_key)
            if topic_id is not None:
                reminder_routed.setdefault(topic_id, []).append(item)
            else:
                reminder_unrouted.append(item)

        if reminder_routed:
            print("\nTOPIC-ROUTED reminders (nudge these topic sessions):")
            for topic_id, items in reminder_routed.items():
                print(f"\n  [topic:{topic_id}] session: agent:main:telegram:group:-1003764039429:topic:{topic_id}")
                for item in items:
                    print(f"  - {item['repo']}#{item['pr']} [{item['kind']}] by {item['author']} — {item['url']}")

        if reminder_unrouted:
            print("\nOpen comment reminders (still unhandled, no topic routing):")
            for item in reminder_unrouted[:8]:
                print(f"- {item['repo']}#{item['pr']} [{item['kind']}] by {item['author']} — {item['url']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
