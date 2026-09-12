#!/usr/bin/env python3
"""Render an autonomy-audit cadence-gap status with cron run-history evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any

DEFAULT_JOB_ID = "d7f95873-f30c-4f41-b944-3345542c5261"
DEFAULT_JOB_NAME = "self-improvement-audit-daily"
DEFAULT_OPENCLAW_BIN = "/home/openclaw/.nvm/versions/node/v22.22.0/bin/openclaw"


def compact_cadence_details(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    interesting = [
        line
        for line in lines
        if line.startswith("- ") and "missing" in line.lower()
    ]
    if not interesting:
        interesting = [
            line
            for line in lines
            if "missing-day cadence gaps" in line.lower()
        ]
    return " | ".join(interesting[:3]) or "missing-day gaps detected by cadence guard"


def load_runs_from_file(path: str) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    return entries if isinstance(entries, list) else []


def load_runs_from_cli(openclaw_bin: str, job_id: str, limit: int, timeout_s: int) -> list[dict[str, Any]]:
    if not Path(openclaw_bin).exists():
        return []

    result = subprocess.run(
        [
            openclaw_bin,
            "cron",
            "runs",
            "--id",
            job_id,
            "--limit",
            str(limit),
            "--timeout",
            str(timeout_s * 1000),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_s + 5,
        check=False,
    )
    if result.returncode != 0:
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    entries = payload.get("entries") if isinstance(payload, dict) else None
    return entries if isinstance(entries, list) else []


def run_reason(entry: dict[str, Any]) -> str:
    error = entry.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()

    diagnostics = entry.get("diagnostics")
    if isinstance(diagnostics, dict):
        summary = diagnostics.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()

    reason = entry.get("errorReason") or entry.get("cause") or entry.get("status")
    return str(reason) if reason else "unknown failure"


def fmt_ms(ms: Any) -> str:
    if not isinstance(ms, int):
        return "unknown time"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def latest_failure_streak(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = 0
    while index < len(entries):
        status = str(entries[index].get("status") or "").lower()
        if status not in {"ok", "success"}:
            break
        index += 1

    failures: list[dict[str, Any]] = []
    for entry in entries[index:]:
        status = str(entry.get("status") or "").lower()
        if status in {"ok", "success"}:
            break
        failures.append(entry)
    return failures


def summarize_failure_streak(entries: list[dict[str, Any]], job_name: str) -> str | None:
    failures = latest_failure_streak(entries)
    if not failures:
        return None

    oldest = failures[-1]
    newest = failures[0]
    reason = run_reason(newest)
    first_run = fmt_ms(oldest.get("runAtMs") or oldest.get("ts"))
    latest_run = fmt_ms(newest.get("runAtMs") or newest.get("ts"))

    reasons = {run_reason(entry) for entry in failures}
    setup_timeout = (
        len(reasons) == 1
        and "isolated agent setup timed out before runner start" in reason.lower()
    )
    if setup_timeout:
        return (
            f"Run-history root cause: `{job_name}` had {len(failures)} consecutive "
            f"isolated setup-timeout failure(s) from {first_run} to {latest_run}; "
            f"each failed before the runner started (`{reason}`)."
        )

    return (
        f"Run-history evidence: `{job_name}` had {len(failures)} consecutive "
        f"failure(s) from {first_run} to {latest_run}; latest reason: `{reason}`."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render autonomy-audit cadence-gap status text")
    parser.add_argument("--cadence-log", required=True, help="Path to cadence guard output")
    parser.add_argument("--job-id", default=DEFAULT_JOB_ID, help="Cron job id to inspect")
    parser.add_argument("--job-name", default=DEFAULT_JOB_NAME, help="Human-readable cron job name")
    parser.add_argument(
        "--openclaw-bin",
        default=os.environ.get("OPENCLAW_BIN", DEFAULT_OPENCLAW_BIN),
        help="Path to openclaw CLI",
    )
    parser.add_argument("--runs-json", help="Pre-fetched cron runs JSON for tests/offline rendering")
    parser.add_argument("--limit", type=int, default=8, help="Cron run-history entries to inspect")
    parser.add_argument("--timeout-seconds", type=int, default=10, help="openclaw CLI timeout")
    args = parser.parse_args()

    cadence_text = Path(args.cadence_log).read_text(encoding="utf-8", errors="replace")
    cadence_summary = compact_cadence_details(cadence_text)

    if args.runs_json:
        entries = load_runs_from_file(args.runs_json)
    else:
        entries = load_runs_from_cli(args.openclaw_bin, args.job_id, args.limit, args.timeout_seconds)

    run_summary = summarize_failure_streak(entries, args.job_name)
    if run_summary is None:
        run_summary = (
            f"Run-history evidence unavailable for `{args.job_name}`; inspect recent cron runs "
            "before treating the cadence gap as resolved."
        )

    print(
        " ".join(
            [
                f"cadence guard reported missing-day gap(s) during preflight: {cadence_summary}.",
                run_summary,
                "Proposed fix: keep the cadence watchdog active until a current daily snapshot lands; "
                "if setup-timeout failures recur, fix isolated runner startup reliability or add a "
                "fallback/alert path through the existing cron-config sign-off workflow.",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
