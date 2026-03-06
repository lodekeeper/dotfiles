#!/usr/bin/env python3
"""CI auto-fix pipeline for flaky sim/e2e tests on unstable.

Detects new failures, classifies them, and outputs actionable JSON
for the cron agent to act on (investigate, fix, PR).

Usage:
    python3 scripts/ci/auto_fix_flaky.py [--apply]

Without --apply: prints what it found (detection only).
With --apply: updates the tracker file with new findings.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
TRACKER_PATH = WORKSPACE / "memory" / "unstable-ci-tracker.json"
REPO = "ChainSafe/lodestar"

# Only these workflows, and only specific job name patterns
TARGET_WORKFLOWS = ["Tests", "Sim tests", "Kurtosis sim tests"]
TARGET_JOB_PATTERNS = [
    "E2E Tests",
    "Browser Tests",
    "Sim test",
    "Multifork sim",
    "Kurtosis sim",
    "Eth backup provider",
]

# Known flaky patterns (error text → classification)
FLAKY_PATTERNS: list[tuple[str, str, str]] = [
    ("QUEUE_ERROR_QUEUE_ABORTED", "shutdown-race", "Unhandled rejection during test teardown — floating promise in shutdown path"),
    ("connectedPeerCount", "peer-count-flaky", "Peer connectivity assertion flakiness — node doesn't reach expected peer count in time"),
    ("Timed out", "timeout", "Test or hook timed out — may need increased timeout or async wait"),
    ("TIMEOUT", "timeout", "Test or hook timed out"),
    ("ECONNREFUSED", "infra-flaky", "Connection refused — test infra startup race"),
    ("error while removing network", "docker-teardown", "Docker network cleanup failure — not actionable"),
    ("ExitStatus:signal", "process-crash", "Child process crashed during test"),
    ("vitest", "vitest-crash", "Vitest runner crashed"),
]

# Patterns that are NOT actionable (skip)
SKIP_PATTERNS = [
    "Dependabot",
    "dependabot",
    "docker-teardown",
]


def gh_json(args: list[str]) -> Any:
    """Run gh CLI and parse JSON output."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(f"gh error: {result.stderr.strip()}", file=sys.stderr)
        return None
    return json.loads(result.stdout) if result.stdout.strip() else None


def load_tracker() -> dict[str, Any]:
    if TRACKER_PATH.exists():
        try:
            return json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"description": "Tracks investigated CI failures on unstable branch", "investigated": []}


def save_tracker(tracker: dict[str, Any]) -> None:
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_PATH.write_text(json.dumps(tracker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def get_investigated_ids(tracker: dict[str, Any]) -> set[int]:
    """All run IDs we've already looked at."""
    ids = set()
    for entry in tracker.get("investigated", []):
        if isinstance(entry, dict) and "runId" in entry:
            ids.add(int(entry["runId"]))
        elif isinstance(entry, int):
            ids.add(entry)
    # Also check top-level keys (old format)
    for k in tracker:
        try:
            ids.add(int(k))
        except ValueError:
            pass
    return ids


def get_failed_runs() -> list[dict[str, Any]]:
    """Fetch recent failed runs on unstable for target workflows."""
    all_failed: list[dict[str, Any]] = []

    for wf in TARGET_WORKFLOWS:
        data = gh_json([
            "run", "list",
            "--repo", REPO,
            "--branch", "unstable",
            "--workflow", wf,
            "--limit", "10",
            "--json", "databaseId,name,conclusion,createdAt,status",
        ])
        if not data:
            continue

        for run in data:
            if run.get("conclusion") == "failure":
                all_failed.append(run)

    return all_failed


def get_failed_jobs(run_id: int) -> list[dict[str, Any]]:
    """Get failed jobs for a run."""
    data = gh_json([
        "run", "view", str(run_id),
        "--repo", REPO,
        "--json", "jobs",
    ])
    if not data or "jobs" not in data:
        return []

    return [j for j in data["jobs"] if j.get("conclusion") == "failure"]


def get_job_logs(run_id: int) -> str:
    """Try to get failed job logs."""
    result = subprocess.run(
        ["gh", "run", "view", str(run_id), "--repo", REPO, "--log-failed"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout[:20000] if result.stdout else ""


def classify_failure(job_name: str, logs: str) -> tuple[str, str]:
    """Classify a failure based on job name and logs.
    
    Returns (classification, description).
    """
    # Check skip patterns first
    for skip in SKIP_PATTERNS:
        if skip.lower() in job_name.lower() or skip.lower() in logs.lower():
            return "not-actionable", f"Matched skip pattern: {skip}"

    # Check if it's a target job
    is_target = any(pat.lower() in job_name.lower() for pat in TARGET_JOB_PATTERNS)
    if not is_target:
        return "not-target", f"Job '{job_name}' is not a target job type"

    # Classify by known patterns
    for pattern, classification, description in FLAKY_PATTERNS:
        if pattern.lower() in logs.lower():
            return classification, description

    # If no known pattern matched but it's a target job
    if logs:
        return "unknown-failure", f"Target job '{job_name}' failed with unknown pattern"
    else:
        return "logs-unavailable", f"Target job '{job_name}' failed but logs expired/unavailable"


def is_fixable(classification: str) -> bool:
    """Is this a classification we can auto-fix?"""
    return classification in {
        "shutdown-race",
        "peer-count-flaky",
        "timeout",
        "vitest-crash",
    }


def extract_test_file(logs: str) -> str | None:
    """Try to extract the failing test file from logs."""
    import re
    # Common patterns in Vitest/Mocha output
    patterns = [
        r"FAIL\s+(\S+\.test\.\S+)",
        r"❯\s+(\S+\.test\.\S+)",
        r"at\s+.*?(\S+\.test\.\S+:\d+)",
        r"(\S+\.test\.ts)\s",
    ]
    for pat in patterns:
        m = re.search(pat, logs)
        if m:
            return m.group(1)
    return None


def scan(apply: bool = False) -> list[dict[str, Any]]:
    """Scan for new failures and classify them."""
    tracker = load_tracker()
    investigated = get_investigated_ids(tracker)
    failed_runs = get_failed_runs()

    new_failures: list[dict[str, Any]] = []

    for run in failed_runs:
        run_id = int(run["databaseId"])
        if run_id in investigated:
            continue

        # Get failed jobs
        jobs = get_failed_jobs(run_id)
        if not jobs:
            continue

        # Get logs
        logs = get_job_logs(run_id)

        for job in jobs:
            job_name = job.get("name", "unknown")
            classification, description = classify_failure(job_name, logs)
            test_file = extract_test_file(logs) if logs else None

            finding = {
                "runId": run_id,
                "workflow": run.get("name", ""),
                "job": job_name,
                "created": run.get("createdAt", ""),
                "classification": classification,
                "description": description,
                "fixable": is_fixable(classification),
                "test_file": test_file,
                "log_snippet": logs[-500:] if logs else None,
            }
            new_failures.append(finding)

            if apply:
                tracker_entry = {
                    "runId": run_id,
                    "name": run.get("name", ""),
                    "job": job_name,
                    "created": run.get("createdAt", ""),
                    "cause": description,
                    "status": "auto-detected",
                    "classification": classification,
                    "fixable": is_fixable(classification),
                    "test_file": test_file,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                }
                tracker["investigated"].append(tracker_entry)

    if apply and new_failures:
        save_tracker(tracker)

    return new_failures


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Detect and classify flaky CI failures on unstable")
    ap.add_argument("--apply", action="store_true", help="Update tracker with findings")
    args = ap.parse_args()

    findings = scan(apply=args.apply)

    if not findings:
        print(json.dumps({"status": "clean", "message": "No new failures on unstable"}, indent=2))
        return

    actionable = [f for f in findings if f["fixable"]]
    skipped = [f for f in findings if not f["fixable"]]

    output = {
        "status": "failures_found",
        "total": len(findings),
        "actionable": len(actionable),
        "skipped": len(skipped),
        "findings": findings,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
