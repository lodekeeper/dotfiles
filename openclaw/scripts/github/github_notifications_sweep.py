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
CHECKLIST_RESERVED_KEYS = {"version", "items", "updatedAt"}
HANDLED_STATUS_RE = re.compile(r"^\s*-\s+\*\*Status:\*\*\s*(?:Addressed|Done|Closed|Handled)\b", re.IGNORECASE)
EXPLICIT_HANDLED_TEXT_RE = re.compile(
    r"\b(?:already handled|already answered|nothing new to answer|nothing new to answer or clear|marked checklist item|no remaining .* notification threads|thread is already fully handled|currently clean)\b",
    re.IGNORECASE,
)


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


def extract_handled_ids_from_text(text: str) -> set[int]:
    handled = set()
    for m in re.findall(r"issuecomment-(\d+)", text):
        handled.add(int(m))
    for m in re.findall(r"discussion_r(\d+)", text):
        handled.add(int(m))
    for m in re.findall(r"/pulls/comments/(\d+)", text):
        handled.add(int(m))
    for m in re.findall(r"pullrequestreview-(\d+)", text):
        handled.add(int(m))
    for m in re.findall(r"\b(?:checklist item|comment(?: id)?|review(?: body)? id)\s*`?(\d{6,})`?", text, re.IGNORECASE):
        handled.add(int(m))
    return handled


def extract_handled_ids_from_backlog(backlog_text: str) -> set[int]:
    handled = set()
    section_lines: List[str] = []
    section_handled = False

    def flush_section() -> None:
        nonlocal handled, section_lines, section_handled
        if section_handled and section_lines:
            handled.update(extract_handled_ids_from_text("\n".join(section_lines)))

    for line in backlog_text.splitlines():
        if EXPLICIT_HANDLED_TEXT_RE.search(line):
            handled.update(extract_handled_ids_from_text(line))

        if line.startswith("### "):
            flush_section()
            section_lines = [line]
            section_handled = line.startswith("### ✅")
            continue

        section_lines.append(line)
        if HANDLED_STATUS_RE.match(line):
            section_handled = True

    flush_section()
    return handled


def normalize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    state.setdefault("version", 2)
    state.setdefault("prs", {})
    state.setdefault("updatedAt", utc_now_iso())
    return state


def parse_legacy_checklist_key(key: str) -> Dict[str, Any] | None:
    m = re.match(r"^(?P<repo>[^#]+/[^#]+)#(?P<pr>\d+):(?P<suffix>.+)$", key)
    if not m:
        return None
    suffix = m.group("suffix")
    id_match = re.search(r"(\d+)$", suffix)
    if not id_match:
        return None

    kind = "legacy"
    if suffix.startswith("review-body:"):
        kind = "review_body"
    elif suffix.startswith("issue:"):
        kind = "issue"
    elif suffix.startswith("review:") or suffix.startswith("r"):
        kind = "review"

    return {
        "repo": m.group("repo"),
        "pr": int(m.group("pr")),
        "kind": kind,
        "id": int(id_match.group(1)),
    }


def normalize_checklist(checklist: Dict[str, Any]) -> Dict[str, Any]:
    checklist.setdefault("version", 1)
    items = checklist.setdefault("items", {})
    checklist.setdefault("updatedAt", utc_now_iso())

    # Legacy handled entries were historically stored at the checklist top level
    # (e.g. ChainSafe/lodestar#9221:review-body:4169103826). Migrate/overlay
    # those statuses into the numeric items map so already-handled reminders do
    # not get resurfaced as open entries forever.
    for key, legacy in list(checklist.items()):
        if key in CHECKLIST_RESERVED_KEYS or not isinstance(legacy, dict):
            continue

        parsed = parse_legacy_checklist_key(key)
        if not parsed:
            continue

        legacy_status = str(legacy.get("status") or "").lower()
        if legacy_status not in {"handled", "done", "closed"}:
            continue

        item = items.setdefault(
            str(parsed["id"]),
            {
                "id": parsed["id"],
                "repo": parsed["repo"],
                "pr": parsed["pr"],
                "kind": parsed["kind"],
            },
        )
        item.setdefault("id", parsed["id"])
        item.setdefault("repo", parsed["repo"])
        item.setdefault("pr", parsed["pr"])
        item.setdefault("kind", parsed["kind"])

        if legacy_status == "closed":
            item["status"] = "closed"
            if legacy.get("closed_at") is not None:
                item["closed_at"] = legacy.get("closed_at")
            if legacy.get("close_reason"):
                item["close_reason"] = legacy.get("close_reason")
        elif legacy_status == "done":
            item["status"] = "done"
            if legacy.get("handled_at"):
                item.setdefault("doneAt", legacy.get("handled_at"))
        else:
            item["status"] = "handled"
            if legacy.get("handled_at"):
                item.setdefault("handledAt", legacy.get("handled_at"))

        if legacy.get("note"):
            item.setdefault("note", legacy.get("note"))
        if legacy.get("action"):
            item.setdefault("action", legacy.get("action"))

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


def fetch_thread_comments(
    repo: str, number: int, kind: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    # For PRs: fetch inline review comments, issue-style thread comments, and review bodies.
    # For Issues: only the issue-style thread comments exist.
    review: List[Dict[str, Any]] = []
    review_bodies: List[Dict[str, Any]] = []
    if kind == "pr":
        review = run_gh_json([f"repos/{repo}/pulls/{number}/comments?per_page=100"])
        # Review bodies: only count reviews that have a non-empty body (pure approvals
        # without a comment have body == "" and are not actionable as comments).
        raw_reviews = run_gh_json([f"repos/{repo}/pulls/{number}/reviews?per_page=100"])
        for r in raw_reviews:
            body = (r.get("body") or "").strip()
            if not body:
                continue
            review_bodies.append(
                {
                    "id": r.get("id"),
                    "user": r.get("user") or {},
                    "html_url": r.get("html_url"),
                    "created_at": r.get("submitted_at"),
                    "body": body,
                }
            )
    issue = run_gh_json([f"repos/{repo}/issues/{number}/comments?per_page=100"])
    return review, issue, review_bodies


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
                "last_review_body_id": 0,
            },
        )
        # Backfill new watermark for existing state entries
        pr_state.setdefault("last_review_body_id", 0)

        review_comments, issue_comments, review_bodies = fetch_thread_comments(repo, pr, kind)

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

        for c in review_bodies:
            cid = int(c["id"])
            max_review_body = max(max_review_body, cid)
            author = (c.get("user") or {}).get("login", "")
            if author.lower() == OWNER_SELF:
                continue

            item = checklist["items"].get(str(cid))
            if item is None and cid > int(pr_state.get("last_review_body_id", 0)):
                item = {
                    "id": cid,
                    "repo": repo,
                    "pr": pr,
                    "kind": "review_body",
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
        pr_state["last_review_body_id"] = max_review_body

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
