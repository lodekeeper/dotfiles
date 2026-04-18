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


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_gh_json(args: List[str]) -> Any:
    cmd = ["gh", "api"] + args
    out = subprocess.check_output(cmd, text=True)
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


def parse_thread_key_from_subject_url(subject_url: str) -> Tuple[str, int, str]:
    # e.g. https://api.github.com/repos/ChainSafe/lodestar/pulls/8739
    #      https://api.github.com/repos/ChainSafe/lodestar/issues/9228
    m = re.search(r"/repos/([^/]+/[^/]+)/(pulls|issues)/(\d+)$", subject_url)
    if not m:
        raise ValueError(f"Not a PR/Issue URL: {subject_url}")
    kind = "pr" if m.group(2) == "pulls" else "issue"
    return m.group(1), int(m.group(3)), kind


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


def normalize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    state.setdefault("version", 2)
    state.setdefault("prs", {})
    state.setdefault("updatedAt", utc_now_iso())
    return state


def normalize_checklist(checklist: Dict[str, Any]) -> Dict[str, Any]:
    checklist.setdefault("version", 1)
    checklist.setdefault("items", {})
    checklist.setdefault("updatedAt", utc_now_iso())
    return checklist


def fetch_notifications() -> List[Dict[str, Any]]:
    data = run_gh_json(["notifications?participating=true"])
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
            if subj.get("type") not in ("PullRequest", "Issue"):
                continue
            out.append(
                {
                    "thread_id": str(n.get("id")),
                    "title": subj.get("title"),
                    "url": subj.get("url"),
                    "updated_at": updated,
                    "reason": n.get("reason"),
                }
            )
        except Exception:
            continue
    return out


def fetch_thread_comments(repo: str, number: int, kind: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    # For PRs: fetch both inline review comments and the issue-style thread comments.
    # For Issues: only the issue-style thread comments exist.
    review: List[Dict[str, Any]] = []
    if kind == "pr":
        review = run_gh_json([f"repos/{repo}/pulls/{number}/comments?per_page=100"])
    issue = run_gh_json([f"repos/{repo}/issues/{number}/comments?per_page=100"])
    return review, issue


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

    # Auto-mark from backlog done entries
    now = utc_now_iso()
    for sid, item in checklist["items"].items():
        if item.get("status") == "open" and int(sid) in handled_ids:
            item["status"] = "done"
            item["doneAt"] = now
            item["doneReason"] = "backlog-done-link"

    notifications = fetch_notifications()

    actionable_new = []
    actionable_reminders = []

    for n in notifications:
        try:
            repo, pr, kind = parse_thread_key_from_subject_url(n["url"])
        except Exception:
            continue

        pr_key = f"{repo}#{pr}"
        pr_state = state["prs"].setdefault(
            pr_key,
            {
                "last_review_comment_id": 0,
                "last_issue_comment_id": 0,
            },
        )

        review_comments, issue_comments = fetch_thread_comments(repo, pr, kind)

        # Update watermark candidates
        max_review = pr_state.get("last_review_comment_id", 0)
        max_issue = pr_state.get("last_issue_comment_id", 0)

        for c in review_comments:
            cid = int(c["id"])
            max_review = max(max_review, cid)
            author = (c.get("user") or {}).get("login", "")
            if author.lower() == OWNER_SELF:
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

        for c in issue_comments:
            cid = int(c["id"])
            max_issue = max(max_issue, cid)
            author = (c.get("user") or {}).get("login", "")
            if author.lower() == OWNER_SELF:
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

        pr_state["last_review_comment_id"] = max_review
        pr_state["last_issue_comment_id"] = max_issue

    # Reminder for stale open entries (to avoid misses), throttled
    remind_delta = dt.timedelta(hours=float(args.remind_hours))
    now_dt = dt.datetime.now(dt.timezone.utc)
    for item in checklist["items"].values():
        if item.get("status") != "open":
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

    if not actionable_new and not actionable_reminders:
        print("HEARTBEAT_OK")
        return 0

    # concise summary output for cron delivery
    print("GitHub notifications check complete.\n")
    if actionable_new:
        print(f"New actionable PR comments: {len(actionable_new)}")
        for item in actionable_new[:12]:
            print(f"- {item['repo']}#{item['pr']} [{item['kind']}] by {item['author']} — {item['url']}")
    if actionable_reminders:
        print("\nOpen comment reminders (still unhandled):")
        for item in actionable_reminders[:8]:
            print(f"- {item['repo']}#{item['pr']} [{item['kind']}] by {item['author']} — {item['url']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
