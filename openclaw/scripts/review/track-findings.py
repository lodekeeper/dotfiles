#!/usr/bin/env python3
"""
Review finding resolution tracker for Lodestar PRs.

Stores, queries, and tracks the resolution of code review findings.
Helps answer: "which of my review comments were addressed by the author's latest commit?"

Usage:
  track-findings.py add <pr> --file <path> --line <n> --severity <sev> --reviewer <name> --body "..."
  track-findings.py list <pr> [--open-only]
  track-findings.py resolve <pr> <id> [--commit <sha>] [--note "..."]
  track-findings.py check <pr> --changed-files <file1> [file2 ...]
  track-findings.py dump <pr>   # markdown summary (for GitHub comment copy-paste)
  track-findings.py import <pr> --markdown <file>   # parse reviewer output file
  track-findings.py import-gh <pr> --repo owner/repo   # import PR review comments via GitHub API
  track-findings.py sync-gh <pr> --repo owner/repo     # checkpointed delta sync + reverify metadata
  track-findings.py dedup <pr>  # group findings by file+line proximity
  track-findings.py stale <pr> [--days 7] [--severity critical major] [--fail-on-match]

Severity levels: critical, major, minor, nit, question
Status values:   open, addressed, acknowledged, wontfix
"""

import argparse
import base64
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

FINDINGS_DIR = Path(__file__).parent.parent / "notes" / "review-findings"
FINDINGS_DIR.mkdir(parents=True, exist_ok=True)

SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "nit": 3, "question": 4}
SEVERITY_EMOJI = {"critical": "🔴", "major": "🟠", "minor": "🟡", "nit": "⚪", "question": "❓"}
SEVERITY_KEYWORDS = {
    "critical": "critical", "security": "critical", "vulnerability": "critical",
    "major": "major", "bug": "major", "error": "major", "race": "major", "panic": "major",
    "minor": "minor", "warn": "minor",
    "nit": "nit", "style": "nit", "nitpick": "nit",
    "question": "question", "why": "question",
}


def pr_path(pr: int) -> Path:
    return FINDINGS_DIR / f"PR-{pr}.json"


def load(pr: int) -> dict:
    p = pr_path(pr)
    if p.exists():
        return json.loads(p.read_text())
    return {"pr": pr, "created": now(), "updated": now(), "findings": []}


def save(pr: int, data: dict):
    data["updated"] = now()
    pr_path(pr).write_text(json.dumps(data, indent=2))


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(ts: str | None) -> datetime | None:
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def short_id() -> str:
    return str(uuid.uuid4())[:6]


def severity_key(f: dict) -> int:
    return SEVERITY_ORDER.get(f.get("severity", "nit"), 99)


def detect_severity(text: str) -> str:
    severity = "minor"
    lower = text.lower()
    for kw, sev in SEVERITY_KEYWORDS.items():
        if kw in lower:
            return sev
    return severity


def make_finding(file: str, line: int, reviewer: str, body: str, severity: str | None = None, source: dict | None = None) -> dict:
    return {
        "id": short_id(),
        "file": file,
        "line": line,
        "severity": severity or detect_severity(body),
        "reviewer": reviewer,
        "body": body[:500],
        "status": "open",
        "addressed_commit": None,
        "note": None,
        "source": source,
        "created": now(),
        "updated": now(),
    }


def find_by_source_id(findings: list[dict], source_kind: str, source_id: str) -> dict | None:
    for finding in findings:
        source = finding.get("source") or {}
        if source.get("kind") == source_kind and str(source.get("id")) == str(source_id):
            return finding
    return None


def normalize_path(path: str | None) -> str:
    return (path or "unknown").lstrip("/")


def find_matching_findings(findings: list[dict], filepath: str, line_no: int, line_window: int) -> list[dict]:
    """Find related findings by file + line proximity to mark for re-verification."""
    normalized_file = normalize_path(filepath)
    matches: list[dict] = []

    for finding in findings:
        if normalize_path(finding.get("file")) != normalized_file:
            continue

        existing_line = int(finding.get("line") or 0)
        if line_no <= 0 or existing_line <= 0:
            # if line metadata is missing for either side, file-level match is enough
            matches.append(finding)
            continue

        if abs(existing_line - line_no) <= line_window:
            matches.append(finding)

    return matches


def add_reverify_metadata(finding: dict, comment: dict, repo: str, pr: int):
    """Annotate finding with metadata that a new related GH comment requires re-verification."""
    finding["needs_reverify"] = True
    reverify = finding.setdefault("reverify", {})
    events = reverify.setdefault("events", [])

    events.append(
        {
            "at": now(),
            "source": {
                "kind": "github-review-comment",
                "repo": repo,
                "pr": pr,
                "id": str(comment.get("id")),
                "url": comment.get("html_url"),
                "author": (comment.get("user") or {}).get("login"),
                "in_reply_to_id": comment.get("in_reply_to_id"),
            },
            "reason": "new related GitHub review comment in same file/line region",
        }
    )
    reverify["last_event_at"] = now()
    finding["updated"] = now()


# ─────────────────────────── Commands ───────────────────────────

def cmd_add(args):
    data = load(args.pr)
    finding = {
        "id": short_id(),
        "file": args.file,
        "line": args.line,
        "severity": args.severity,
        "reviewer": args.reviewer,
        "body": args.body,
        "status": "open",
        "addressed_commit": None,
        "note": None,
        "created": now(),
        "updated": now(),
    }
    data["findings"].append(finding)
    save(args.pr, data)
    print(f"✅ Added finding [{finding['id']}] on {args.file}:{args.line} ({args.severity})")


def cmd_list(args):
    data = load(args.pr)
    findings = data["findings"]
    if args.open_only:
        findings = [f for f in findings if f["status"] == "open"]
    if not findings:
        print(f"No {'open ' if args.open_only else ''}findings for PR #{args.pr}")
        return
    findings = sorted(findings, key=severity_key)
    print(f"\n### PR #{args.pr} — {'Open ' if args.open_only else ''}Findings ({len(findings)})\n")
    for f in findings:
        emoji = SEVERITY_EMOJI.get(f["severity"], "•")
        status_tag = "" if f["status"] == "open" else f" [{f['status'].upper()}]"
        commit_tag = f" (commit: {f['addressed_commit']})" if f.get("addressed_commit") else ""
        print(f"{emoji} [{f['id']}]{status_tag} **{f['file']}:{f['line']}** ({f['reviewer']})")
        print(f"   {f['body'][:120]}{'...' if len(f['body']) > 120 else ''}")
        if f.get("note"):
            print(f"   _Note: {f['note']}_")
        if commit_tag:
            print(f"   {commit_tag}")
        print()


def cmd_resolve(args):
    data = load(args.pr)
    for f in data["findings"]:
        if f["id"] == args.finding_id:
            f["status"] = args.status
            f["addressed_commit"] = args.commit
            f["note"] = args.note
            f["updated"] = now()
            save(args.pr, data)
            print(f"✅ Marked [{args.finding_id}] as {args.status}" +
                  (f" (commit: {args.commit})" if args.commit else ""))
            return
    print(f"❌ Finding [{args.finding_id}] not found in PR #{args.pr}", file=sys.stderr)
    sys.exit(1)


def cmd_check(args):
    """Given a list of changed files (from a new commit), flag open findings on those files as needing verification."""
    data = load(args.pr)
    changed = set(args.changed_files)
    needs_verify = []
    unaffected = []

    for f in data["findings"]:
        if f["status"] != "open":
            continue
        # normalize paths — strip leading slashes/repo prefix for fuzzy match
        finding_file = f["file"].lstrip("/")
        matched = any(
            finding_file.endswith(cf) or cf.endswith(finding_file) or finding_file == cf
            for cf in changed
        )
        if matched:
            needs_verify.append(f)
        else:
            unaffected.append(f)

    print(f"\n### PR #{args.pr} — Findings check against {len(changed)} changed file(s)\n")
    if needs_verify:
        print(f"🔍 **{len(needs_verify)} finding(s) need verification** (file was changed):\n")
        for f in sorted(needs_verify, key=severity_key):
            emoji = SEVERITY_EMOJI.get(f["severity"], "•")
            print(f"  {emoji} [{f['id']}] {f['file']}:{f['line']} — {f['body'][:100]}")
    else:
        print("✅ No open findings on changed files.")

    if unaffected:
        print(f"\n⏳ **{len(unaffected)} open finding(s) still unaddressed** (file not changed):\n")
        for f in sorted(unaffected, key=severity_key):
            emoji = SEVERITY_EMOJI.get(f["severity"], "•")
            print(f"  {emoji} [{f['id']}] {f['file']}:{f['line']} — {f['body'][:100]}")

    print()
    print("Run `resolve <pr> <id>` to mark addressed ones or `check` again with a new commit's file list.")


def cmd_dump(args):
    """Output a markdown summary suitable for pasting into a GitHub review comment."""
    data = load(args.pr)
    open_findings = [f for f in data["findings"] if f["status"] == "open"]
    addressed = [f for f in data["findings"] if f["status"] == "addressed"]

    print(f"## Code Review Summary — PR #{args.pr}\n")
    print(f"_Generated {now()}_\n")

    if open_findings:
        print(f"### 🔍 Open Findings ({len(open_findings)})\n")
        for f in sorted(open_findings, key=severity_key):
            emoji = SEVERITY_EMOJI.get(f["severity"], "•")
            print(f"{emoji} **[{f['severity'].upper()}]** `{f['file']}:{f['line']}` ({f['reviewer']})")
            print(f"> {f['body']}\n")

    if addressed:
        print(f"\n### ✅ Addressed ({len(addressed)})\n")
        for f in sorted(addressed, key=severity_key):
            commit = f" (commit: `{f['addressed_commit']}`)" if f.get("addressed_commit") else ""
            print(f"- `{f['file']}:{f['line']}` — {f['body'][:80]}...{commit}")

    wontfix = [f for f in data["findings"] if f["status"] == "wontfix"]
    if wontfix:
        print(f"\n### 🚫 Won't Fix ({len(wontfix)})\n")
        for f in wontfix:
            note = f" ({f['note']})" if f.get("note") else ""
            print(f"- `{f['file']}:{f['line']}` — {f['body'][:60]}...{note}")


def cmd_import(args):
    """
    Parse a reviewer markdown output file and extract findings.
    Looks for patterns like:
      ### file/path.ts:42
      **[severity]** body text
    or
      - **file.ts:42**: body
    Imports them as 'minor' by default; severity detected from keywords.
    """
    md = Path(args.markdown).read_text()
    data = load(args.pr)
    imported = 0

    # Pattern: ### path/to/file.ts:123 (optional — **severity** or [severity])
    block_pattern = re.compile(
        r"(?:#{1,4}|[-*])\s+[`\*]*([^\s`\*:]+\.[a-z]{1,5}):(\d+)[`\*]*[:\s]*(.+?)(?=\n(?:#{1,4}|[-*])\s+[^\s]+\.[a-z]{1,5}:|\Z)",
        re.DOTALL
    )
    for m in block_pattern.finditer(md):
        filepath, lineno, body = m.group(1), int(m.group(2)), m.group(3).strip()
        body = re.sub(r"\n+", " ", body).strip()
        if len(body) < 5:
            continue
        finding = make_finding(
            file=filepath,
            line=lineno,
            reviewer=args.reviewer or "imported",
            body=body,
            source={"kind": "markdown-import", "id": f"{args.markdown}:{filepath}:{lineno}"},
        )
        data["findings"].append(finding)
        imported += 1

    save(args.pr, data)
    print(f"✅ Imported {imported} finding(s) from {args.markdown} → PR #{args.pr}")


def cmd_import_gh(args):
    """
    Import PR review comments from GitHub API via gh CLI.
    Endpoint: repos/{owner}/{repo}/pulls/{pr}/comments
    """
    data = load(args.pr)

    cmd = [
        "gh", "api", "--paginate",
        f"repos/{args.repo}/pulls/{args.pr}/comments",
        "--jq",
        ".[] | @base64",
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print("❌ Failed to fetch GitHub review comments via gh API", file=sys.stderr)
        if e.stderr:
            print(e.stderr.strip(), file=sys.stderr)
        sys.exit(1)

    lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
    imported = 0
    skipped = 0

    for line in lines:
        try:
            decoded = base64.b64decode(line).decode("utf-8")
            comment = json.loads(decoded)
        except Exception:
            skipped += 1
            continue

        comment_id = comment.get("id")
        if comment_id is None:
            skipped += 1
            continue

        # Skip reply comments unless explicitly requested.
        if not args.include_replies and comment.get("in_reply_to_id"):
            skipped += 1
            continue

        if find_by_source_id(data["findings"], "github-review-comment", str(comment_id)):
            skipped += 1
            continue

        filepath = comment.get("path") or "unknown"
        line_no = comment.get("line") or comment.get("original_line") or 0
        reviewer = (comment.get("user") or {}).get("login") or "github-reviewer"
        body = (comment.get("body") or "").strip()
        if not body:
            skipped += 1
            continue

        finding = make_finding(
            file=filepath,
            line=int(line_no),
            reviewer=reviewer,
            body=body,
            source={
                "kind": "github-review-comment",
                "id": str(comment_id),
                "repo": args.repo,
                "pr": args.pr,
                "url": comment.get("html_url"),
            },
        )
        data["findings"].append(finding)
        imported += 1

    save(args.pr, data)
    print(
        f"✅ GitHub import complete for PR #{args.pr}: imported {imported}, skipped {skipped} "
        f"(repo: {args.repo})"
    )


def cmd_sync_gh(args):
    """
    Checkpointed delta-sync of GitHub PR review comments.

    - Imports only comments newer than the stored checkpoint (or --since-comment-id)
    - For each new comment, tags matching existing findings with re-verification metadata
    - Persists checkpoint in PR data under data.sync.github[repo]
    """
    data = load(args.pr)

    sync = data.setdefault("sync", {})
    github_sync = sync.setdefault("github", {})
    repo_sync = github_sync.setdefault(args.repo, {})

    checkpoint = args.since_comment_id
    if checkpoint is None:
        stored = repo_sync.get("last_comment_id")
        try:
            checkpoint = int(stored) if stored is not None else None
        except (TypeError, ValueError):
            checkpoint = None

    cmd = [
        "gh",
        "api",
        "--paginate",
        f"repos/{args.repo}/pulls/{args.pr}/comments",
        "--jq",
        ".[] | @base64",
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print("❌ Failed to fetch GitHub review comments via gh API", file=sys.stderr)
        if e.stderr:
            print(e.stderr.strip(), file=sys.stderr)
        sys.exit(1)

    comments: list[dict] = []
    for line in [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]:
        try:
            comments.append(json.loads(base64.b64decode(line).decode("utf-8")))
        except Exception:
            continue

    comments.sort(key=lambda c: int(c.get("id") or 0))

    imported = 0
    skipped_checkpoint = 0
    skipped_existing = 0
    skipped_replies = 0
    skipped_invalid = 0
    reverify_updates = 0
    max_seen = checkpoint or 0

    for comment in comments:
        comment_id = comment.get("id")
        try:
            comment_id_int = int(comment_id)
        except (TypeError, ValueError):
            skipped_invalid += 1
            continue

        if comment_id_int > max_seen:
            max_seen = comment_id_int

        if checkpoint is not None and comment_id_int <= checkpoint:
            skipped_checkpoint += 1
            continue

        if not args.include_replies and comment.get("in_reply_to_id"):
            skipped_replies += 1
            continue

        body = (comment.get("body") or "").strip()
        if not body:
            skipped_invalid += 1
            continue

        source_id = str(comment_id_int)
        if find_by_source_id(data["findings"], "github-review-comment", source_id):
            skipped_existing += 1
            continue

        filepath = normalize_path(comment.get("path"))
        line_no = int(comment.get("line") or comment.get("original_line") or 0)
        reviewer = (comment.get("user") or {}).get("login") or "github-reviewer"

        matches = find_matching_findings(data["findings"], filepath, line_no, args.match_window_lines)
        for finding in matches:
            add_reverify_metadata(finding, comment, args.repo, args.pr)
            reverify_updates += 1

        finding = make_finding(
            file=filepath,
            line=line_no,
            reviewer=reviewer,
            body=body,
            source={
                "kind": "github-review-comment",
                "id": source_id,
                "repo": args.repo,
                "pr": args.pr,
                "url": comment.get("html_url"),
            },
        )
        if matches:
            finding["matched_findings"] = [f.get("id") for f in matches if f.get("id")]

        data["findings"].append(finding)
        imported += 1

    if not args.dry_run:
        if max_seen:
            repo_sync["last_comment_id"] = str(max_seen)
        repo_sync["last_synced"] = now()
        repo_sync["last_imported"] = imported
        repo_sync["last_reverify_updates"] = reverify_updates
        save(args.pr, data)

    mode = "DRY-RUN" if args.dry_run else "SYNC"
    print(
        f"✅ GitHub {mode} complete for PR #{args.pr} ({args.repo}): "
        f"imported={imported}, reverify_updates={reverify_updates}, "
        f"skipped_checkpoint={skipped_checkpoint}, skipped_existing={skipped_existing}, "
        f"skipped_replies={skipped_replies}, skipped_invalid={skipped_invalid}, "
        f"checkpoint={(checkpoint if checkpoint is not None else 'none')}→{max_seen}"
    )


def cmd_dedup(args):
    """Group open findings by file, then by line proximity (±5 lines). Print dedup summary."""
    data = load(args.pr)
    open_findings = [f for f in data["findings"] if f["status"] == "open"]
    if not open_findings:
        print(f"No open findings for PR #{args.pr}")
        return

    # Group by file
    by_file: dict[str, list] = {}
    for f in open_findings:
        by_file.setdefault(f["file"], []).append(f)

    print(f"\n### PR #{args.pr} — Deduplicated Findings\n")
    total_groups = 0
    for filepath, findings in sorted(by_file.items()):
        # Sort by line
        findings.sort(key=lambda f: f.get("line") or 0)
        # Group by proximity (±5 lines)
        groups: list[list] = []
        for f in findings:
            placed = False
            for g in groups:
                if abs((f.get("line") or 0) - (g[-1].get("line") or 0)) <= 5:
                    g.append(f)
                    placed = True
                    break
            if not placed:
                groups.append([f])

        print(f"**{filepath}** — {len(findings)} finding(s) in {len(groups)} location(s):\n")
        for g in groups:
            lines = sorted(set(f.get("line") or 0 for f in g))
            reviewers = sorted(set(f["reviewer"] for f in g))
            severities = sorted(set(f["severity"] for f in g), key=lambda s: SEVERITY_ORDER.get(s, 99))
            top_sev = severities[0]
            emoji = SEVERITY_EMOJI.get(top_sev, "•")
            ids = [f["id"] for f in g]
            print(f"  {emoji} Lines {lines} | reviewers: {reviewers} | ids: {ids}")
            for f in g:
                print(f"    - [{f['id']}] ({f['reviewer']}) {f['body'][:90]}")
            print()
        total_groups += len(groups)

    print(f"Total: {len(open_findings)} findings → {total_groups} deduplicated locations")


def cmd_stale(args):
    """List stale open findings by age and severity; optional non-zero exit when matches exist."""
    data = load(args.pr)
    reference = datetime.now(timezone.utc)
    cutoff = reference - timedelta(days=args.days)

    stale: list[tuple[dict, datetime, int]] = []
    severities = set(args.severity)

    for finding in data["findings"]:
        if finding.get("status") != "open":
            continue
        if finding.get("severity") not in severities:
            continue

        ts_field = "created" if args.use_created else "updated"
        ts = parse_utc(finding.get(ts_field)) or parse_utc(finding.get("created"))
        if ts is None:
            continue

        if ts <= cutoff:
            age_days = int((reference - ts).total_seconds() // 86400)
            stale.append((finding, ts, age_days))

    stale.sort(key=lambda item: (severity_key(item[0]), item[1]))

    metric = "created" if args.use_created else "updated"
    print(
        f"\n### PR #{args.pr} — Stale open findings "
        f"(severity in {sorted(severities)}, {metric} >= {args.days}d old)\n"
    )

    if not stale:
        print("✅ No stale open findings matched the selected filters.")
        return

    for finding, _, age_days in stale:
        emoji = SEVERITY_EMOJI.get(finding.get("severity"), "•")
        print(
            f"{emoji} [{finding['id']}] {finding.get('file')}:{finding.get('line') or 0} "
            f"({finding.get('reviewer')}) — age={age_days}d"
        )
        print(f"   {finding.get('body', '')[:120]}{'...' if len(finding.get('body', '')) > 120 else ''}")

    print(f"\nTotal stale findings: {len(stale)}")

    if args.fail_on_match:
        sys.exit(2)


# ─────────────────────────── CLI ───────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Review finding tracker for Lodestar PRs")
    sub = parser.add_subparsers(dest="cmd")

    # add
    p_add = sub.add_parser("add", help="Add a new finding")
    p_add.add_argument("pr", type=int)
    p_add.add_argument("--file", required=True)
    p_add.add_argument("--line", type=int, default=0)
    p_add.add_argument("--severity", choices=["critical", "major", "minor", "nit", "question"], default="minor")
    p_add.add_argument("--reviewer", default="self")
    p_add.add_argument("--body", required=True)

    # list
    p_list = sub.add_parser("list", help="List findings")
    p_list.add_argument("pr", type=int)
    p_list.add_argument("--open-only", action="store_true")

    # resolve
    p_res = sub.add_parser("resolve", help="Mark a finding as resolved/addressed/wontfix")
    p_res.add_argument("pr", type=int)
    p_res.add_argument("finding_id")
    p_res.add_argument("--status", choices=["addressed", "acknowledged", "wontfix"], default="addressed")
    p_res.add_argument("--commit", default=None)
    p_res.add_argument("--note", default=None)

    # check
    p_chk = sub.add_parser("check", help="Check which findings may be addressed by a new commit")
    p_chk.add_argument("pr", type=int)
    p_chk.add_argument("--changed-files", nargs="+", required=True)

    # dump
    p_dump = sub.add_parser("dump", help="Dump markdown summary for GitHub")
    p_dump.add_argument("pr", type=int)

    # import
    p_imp = sub.add_parser("import", help="Import findings from reviewer markdown output")
    p_imp.add_argument("pr", type=int)
    p_imp.add_argument("--markdown", required=True)
    p_imp.add_argument("--reviewer", default=None)

    # import-gh
    p_imp_gh = sub.add_parser("import-gh", help="Import findings from GitHub PR review comments")
    p_imp_gh.add_argument("pr", type=int)
    p_imp_gh.add_argument("--repo", required=True, help="owner/repo (e.g. ChainSafe/lodestar)")
    p_imp_gh.add_argument("--include-replies", action="store_true", help="Include in-thread reply comments")

    # sync-gh
    p_sync_gh = sub.add_parser("sync-gh", help="Checkpointed delta sync from GitHub PR review comments")
    p_sync_gh.add_argument("pr", type=int)
    p_sync_gh.add_argument("--repo", required=True, help="owner/repo (e.g. ChainSafe/lodestar)")
    p_sync_gh.add_argument("--since-comment-id", type=int, default=None, help="Override checkpoint start (import comments with id > this value)")
    p_sync_gh.add_argument("--include-replies", action="store_true", help="Include in-thread reply comments")
    p_sync_gh.add_argument("--match-window-lines", type=int, default=5, help="Line-distance window for matching existing findings")
    p_sync_gh.add_argument("--dry-run", action="store_true", help="Compute and print sync results without saving")

    # dedup
    p_dedup = sub.add_parser("dedup", help="Group findings by file+line proximity")
    p_dedup.add_argument("pr", type=int)

    # stale
    p_stale = sub.add_parser("stale", help="List stale open findings by age/severity")
    p_stale.add_argument("pr", type=int)
    p_stale.add_argument("--days", type=int, default=7, help="Age threshold in days (default: 7)")
    p_stale.add_argument(
        "--severity",
        nargs="+",
        choices=["critical", "major", "minor", "nit", "question"],
        default=["critical", "major"],
        help="Severity filter (default: critical major)",
    )
    p_stale.add_argument(
        "--use-created",
        action="store_true",
        help="Use created timestamp instead of updated when calculating staleness",
    )
    p_stale.add_argument(
        "--fail-on-match",
        action="store_true",
        help="Exit with code 2 when stale findings are found",
    )

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "add": cmd_add, "list": cmd_list, "resolve": cmd_resolve,
        "check": cmd_check, "dump": cmd_dump, "import": cmd_import,
        "import-gh": cmd_import_gh, "sync-gh": cmd_sync_gh, "dedup": cmd_dedup,
        "stale": cmd_stale,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
