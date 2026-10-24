#!/usr/bin/env python3
"""Reconcile CI evidence for a PR's current head using read-only GitHub requests.

`gh pr checks` and check-run rollups omit workflow runs that never started,
for example fork-PR runs awaiting maintainer approval (`action_required`).
"0 failing checks" is therefore not "CI green". This helper joins workflow
runs, check runs and commit status contexts for the head revision.

`observed_green` means no observed current item is failing, gated, pending or
cancelled, and at least one CI item (a pull_request/push/merge_group workflow
run, a non-Actions check run or a status context) succeeded. Skipped/neutral
items never count as success. Required-check coverage is not evaluated
(branch protection needs admin access), so it is not merge readiness.
Exit 0 means evidence was collected; read `verdict`, it is not a green signal.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


PER_PAGE = 100
MAX_PAGES = 5
FAILING_CONCLUSIONS = {"failure", "timed_out", "startup_failure"}
SKIPPED_CONCLUSIONS = {"skipped", "neutral"}
CI_EVENTS = {"pull_request", "push", "merge_group"}
CLASSES = ("ok", "skipped", "failing", "action_required", "pending", "cancelled")
BLOCKING_ORDER = ("failing", "action_required", "pending", "cancelled")


class CollectionError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_json(gh: str, endpoint: str, timeout_s: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [gh, "api", "--method", "GET", endpoint],
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise CollectionError(f"GitHub GET {endpoint} failed ({type(exc).__name__})") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        suffix = f": {detail[0][:200]}" if detail else ""
        raise CollectionError(f"GitHub GET {endpoint} failed (exit {proc.returncode}){suffix}")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CollectionError(f"GitHub GET {endpoint} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise CollectionError(f"GitHub GET {endpoint} did not return an object")
    return payload


def get_paged(gh: str, endpoint: str, key: str, timeout_s: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    sep = "&" if "?" in endpoint else "?"
    for page in range(1, MAX_PAGES + 1):
        payload = get_json(gh, f"{endpoint}{sep}per_page={PER_PAGE}&page={page}", timeout_s)
        batch = payload.get(key)
        if not isinstance(batch, list):
            raise CollectionError(f"GitHub GET {endpoint} returned no '{key}' list")
        if any(not isinstance(item, dict) for item in batch):
            raise CollectionError(f"GitHub GET {endpoint} returned a non-object '{key}' record")
        total = payload.get("total_count")
        if "total_count" in payload and (type(total) is not int or total < 0):
            raise CollectionError(f"GitHub GET {endpoint} returned an invalid total_count")
        items.extend(batch)
        if total is not None and len(items) > total:
            raise CollectionError(f"GitHub GET {endpoint} returned more records than total_count; evidence changed or malformed")
        if len(batch) < PER_PAGE:
            if total is not None and len(items) < total:
                raise CollectionError(f"GitHub GET {endpoint} ended before total_count; evidence incomplete")
            return items
        if total is not None and len(items) == total:
            return items
    raise CollectionError(f"GitHub GET {endpoint} exceeded {MAX_PAGES} pages; evidence incomplete")


def classify_run(status: str | None, conclusion: str | None) -> str:
    if conclusion == "action_required":
        return "action_required"
    if status != "completed":
        return "pending"
    if conclusion == "success":
        return "ok"
    if conclusion in SKIPPED_CONCLUSIONS:
        return "skipped"
    if conclusion == "cancelled":
        return "cancelled"
    if conclusion is None:
        return "pending"
    return "failing"


def classify_context(state: str | None) -> str:
    if state == "success":
        return "ok"
    if state in ("failure", "error"):
        return "failing"
    return "pending"


def split_current(items: list[dict[str, Any]], key_fn) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Newest item per key is current. A newer skipped/neutral item does not
    supersede an older executed result, so both stay current."""
    groups: dict[Any, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(key_fn(item), []).append(item)
    current: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    for group in groups.values():
        group.sort(key=lambda item: item.get("id") or 0, reverse=True)
        keep = [group[0]]
        if classify_run(group[0].get("status"), group[0].get("conclusion")) == "skipped":
            executed = next((item for item in group[1:]
                             if classify_run(item.get("status"), item.get("conclusion")) != "skipped"), None)
            if executed is not None:
                keep.append(executed)
        current.extend(keep)
        superseded.extend(item for item in group if all(item is not k for k in keep))
    return current, superseded


def run_item(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "workflow_run",
        "name": r.get("name"),
        "event": r.get("event"),
        "status": r.get("status"),
        "conclusion": r.get("conclusion"),
        "attempt": r.get("run_attempt"),
        "class": classify_run(r.get("status"), r.get("conclusion")),
        "url": r.get("html_url"),
    }


def check_item(c: dict[str, Any], workflow: str | None) -> dict[str, Any]:
    return {
        "kind": "check_run",
        "name": c.get("name"),
        "workflow": workflow,
        "status": c.get("status"),
        "conclusion": c.get("conclusion"),
        "class": classify_run(c.get("status"), c.get("conclusion")),
        "url": c.get("html_url"),
    }


def suite_id(check: dict[str, Any]) -> Any:
    suite = check.get("check_suite")
    return suite.get("id") if isinstance(suite, dict) else None


def collect(repo: str, pr: int, timeout_s: int) -> dict[str, Any]:
    gh = shutil.which("gh")
    if not gh:
        raise CollectionError("gh executable not found")

    pull = get_json(gh, f"repos/{repo}/pulls/{pr}", timeout_s)
    head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
    sha = head.get("sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise CollectionError("PR response has no head SHA")

    runs = get_paged(gh, f"repos/{repo}/actions/runs?head_sha={sha}", "workflow_runs", timeout_s)
    checks = get_paged(gh, f"repos/{repo}/commits/{sha}/check-runs", "check_runs", timeout_s)
    contexts = get_paged(gh, f"repos/{repo}/commits/{sha}/status", "statuses", timeout_s)

    recheck = get_json(gh, f"repos/{repo}/pulls/{pr}", timeout_s)
    recheck_head = recheck.get("head") if isinstance(recheck.get("head"), dict) else {}
    if recheck_head.get("sha") != sha:
        raise CollectionError(f"PR head moved during collection ({sha[:12]} -> {str(recheck_head.get('sha'))[:12]})")

    # Same-repo runs list their PRs; drop runs (and their check suites) that belong only to another PR
    # sharing this head. Fork-PR runs have an empty `pull_requests` list and are kept.
    def other_pr(r: dict[str, Any]) -> bool:
        prs = r.get("pull_requests") or []
        return bool(prs) and all(isinstance(p, dict) and p.get("number") != pr for p in prs)

    def run_key(r: dict[str, Any]) -> tuple[Any, Any]:
        return (r.get("workflow_id") or r.get("name"), r.get("event"))

    other_runs = [r for r in runs if other_pr(r)]
    runs = [r for r in runs if not other_pr(r)]
    current_runs, superseded_runs = split_current(runs, run_key)

    suite_to_run = {r.get("check_suite_id"): r for r in current_runs + superseded_runs if r.get("check_suite_id")}
    other_suites = {r.get("check_suite_id") for r in other_runs if r.get("check_suite_id")}
    superseded_suites = {r.get("check_suite_id") for r in superseded_runs if r.get("check_suite_id")}

    # A check in a superseded run is superseded only if the newest run of the same workflow/event
    # re-executed a job with that name; a job the newer run skipped or omitted keeps its old result.
    newest_by_key: dict[Any, dict[str, Any]] = {}
    for r in runs:
        prev = newest_by_key.get(run_key(r))
        if prev is None or (r.get("id") or 0) > (prev.get("id") or 0):
            newest_by_key[run_key(r)] = r
    replaced_names: dict[Any, set[Any]] = {}
    for key, newest in newest_by_key.items():
        replaced_names[key] = {c.get("name") for c in checks if suite_id(c) == newest.get("check_suite_id")
                               and classify_run(c.get("status"), c.get("conclusion")) != "skipped"}

    live_checks: list[dict[str, Any]] = []
    superseded_checks: list[dict[str, Any]] = []
    for c in checks:
        if suite_id(c) in other_suites:
            continue
        if suite_id(c) in superseded_suites and c.get("name") in replaced_names[run_key(suite_to_run[suite_id(c)])]:
            superseded_checks.append(c)
        else:
            live_checks.append(c)
    current_checks, dup_checks = split_current(live_checks, lambda c: (suite_id(c), c.get("name")))
    superseded_checks += dup_checks

    def workflow_of(c: dict[str, Any]) -> str | None:
        run = suite_to_run.get(suite_id(c))
        return run.get("name") if run else None

    items = [run_item(r) for r in current_runs]
    items += [check_item(c, workflow_of(c)) for c in current_checks]
    items += [{"kind": "status_context", "name": s.get("context"), "state": s.get("state"),
               "class": classify_context(s.get("state")), "url": s.get("target_url")} for s in contexts]
    superseded = [run_item(r) for r in superseded_runs] + [check_item(c, workflow_of(c)) for c in superseded_checks]

    counts = {cls: 0 for cls in CLASSES}
    for item in items:
        counts[item["class"]] += 1
    by_event: dict[str, dict[str, int]] = {}
    for r in current_runs:
        event_counts = by_event.setdefault(str(r.get("event")), {})
        cls = classify_run(r.get("status"), r.get("conclusion"))
        event_counts[cls] = event_counts.get(cls, 0) + 1

    ci_success = (
        any(r.get("event") in CI_EVENTS and classify_run(r.get("status"), r.get("conclusion")) == "ok"
            for r in current_runs)
        or any(suite_id(c) not in suite_to_run and (c.get("app") or {}).get("slug") != "github-actions"
               and classify_run(c.get("status"), c.get("conclusion")) == "ok" for c in current_checks)
        or any(classify_context(s.get("state")) == "ok" for s in contexts)
    )
    present = {item["class"] for item in items}
    verdict = next((v for v in BLOCKING_ORDER if v in present), None)
    if verdict is None:
        verdict = "observed_green" if ci_success else "no_ci"

    return {
        "ok": True,
        "repo": repo,
        "pr": pr,
        "prState": pull.get("state"),
        "headSha": sha,
        "headRepo": (head.get("repo") or {}).get("full_name"),
        "observedAt": now_iso(),
        "verdict": verdict,
        "counts": counts,
        "workflowRunsByEvent": by_event,
        "observed": {
            "workflowRuns": len(current_runs),
            "checkRuns": len(current_checks),
            "statusContexts": len(contexts),
            "supersededWorkflowRuns": len(superseded_runs),
            "supersededCheckRuns": len(superseded_checks),
            "otherPrWorkflowRuns": len(other_runs),
        },
        "nonGreen": [item for item in items if item["class"] not in ("ok", "skipped")],
        "supersededNonGreen": [item for item in superseded if item["class"] not in ("ok", "skipped")],
        "caveats": [
            "Required-check coverage is not evaluated; observed_green is not merge readiness.",
            "Newest run per workflow/event and newest check per suite/name are current; a newer skipped item "
            "does not hide an older executed result.",
            "Other-PR exclusion matches PR number only and only while PRs are open; fork-PR runs and runs "
            "listing several PRs sharing this head SHA cannot be separated.",
        ],
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, help="owner/repo, e.g. ChainSafe/lodestar")
    parser.add_argument("--pr", required=True, type=int, help="pull request number")
    parser.add_argument("--timeout", type=int, default=30, help="per-request timeout in seconds")
    args = parser.parse_args(argv)
    if (args.pr < 1 or args.timeout < 1
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo)
            or any(part in (".", "..") for part in args.repo.split("/"))):
        parser.error("expected owner/repo, a positive PR number and a positive timeout")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = collect(args.repo, args.pr, args.timeout)
    except CollectionError as exc:
        result = {"ok": False, "repo": args.repo, "pr": args.pr, "observedAt": now_iso(),
                  "verdict": "unknown", "error": str(exc)}
        print(json.dumps(result, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
