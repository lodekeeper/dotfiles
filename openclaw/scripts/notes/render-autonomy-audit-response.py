#!/usr/bin/env python3
"""Render a cron-ready response for daily autonomy-audit runs.

Uses check-autonomy-audit-delta.py JSON output and returns either:
- NO_REPLY (no meaningful delta), or
- a concise human summary suitable for reminder notifications.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def _run_delta(script_dir: Path, file_path: str, date_str: str | None) -> dict:
    delta_script = script_dir / "check-autonomy-audit-delta.py"
    cmd = [
        sys.executable,
        str(delta_script),
        "--file",
        file_path,
        "--json",
    ]
    if date_str:
        cmd += ["--date", date_str]

    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"delta check failed (exit {result.returncode}): {stderr}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid delta JSON output: {exc}") from exc


def _format_list(values: list[str], empty: str = "none") -> str:
    return ", ".join(values) if values else empty


def _render_summary(payload: dict) -> str:
    current = payload.get("currentDate", "current")
    previous = payload.get("previousDate", "previous")

    changed_required = payload.get("changedRequiredSections") or []
    status_deltas = payload.get("statusDeltas") or {}
    changed_non_required = payload.get("changedNonRequiredSections") or []
    added = payload.get("addedSectionHeadings") or []
    removed = payload.get("removedSectionHeadings") or []

    parts: list[str] = []

    if changed_required:
        status_parts: list[str] = []
        for section in changed_required:
            delta = status_deltas.get(section, {})
            prev = (delta.get("previous") or "(missing)").strip()
            curr = (delta.get("current") or "(missing)").strip()
            status_parts.append(f"{section} ({prev} -> {curr})")
        parts.append(f"required status changes: {'; '.join(status_parts)}")
    else:
        parts.append("required status changes: none")

    if changed_non_required:
        parts.append(f"non-required section updates: {_format_list(changed_non_required)}")

    heading_changes: list[str] = []
    if added:
        heading_changes.append(f"+{_format_list(added)}")
    if removed:
        heading_changes.append(f"-{_format_list(removed)}")

    if heading_changes:
        parts.append(f"section heading changes: {'; '.join(heading_changes)}")

    summary = "; ".join(parts)
    return f"Autonomy audit updated ({current} vs {previous}): {summary}."


def main() -> int:
    parser = argparse.ArgumentParser(description="Render NO_REPLY or concise summary from autonomy-audit delta")
    parser.add_argument("--file", default="notes/autonomy-gaps.md", help="Path to autonomy-gaps markdown")
    parser.add_argument("--date", help="Snapshot date YYYY-MM-DD (default: latest snapshot)")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent

    try:
        payload = _run_delta(script_dir, args.file, args.date)
    except Exception as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    if payload.get("noReplyRecommended"):
        print("NO_REPLY")
        return 0

    print(_render_summary(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
