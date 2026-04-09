#!/usr/bin/env python3
"""Check daily autonomy-audit snapshot cadence.

Detects missing day gaps between snapshot headings in notes/autonomy-gaps.md.
Useful as an advisory guard so missed cron runs don't go unnoticed.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import re
import sys

SNAPSHOT_HEADING = re.compile(r"^## Daily Audit Snapshot — (\d{4}-\d{2}-\d{2})\b", re.MULTILINE)


def parse_dates(text: str) -> list[date]:
    seen: set[date] = set()
    dates: list[date] = []

    for match in SNAPSHOT_HEADING.finditer(text):
        raw = match.group(1)
        parsed = date.fromisoformat(raw)
        if parsed in seen:
            continue
        seen.add(parsed)
        dates.append(parsed)

    # Compare in chronological order for intuitive gap reports.
    return sorted(dates)


def find_gaps(dates: list[date], expected_every_days: int) -> list[tuple[date, date, int]]:
    gaps: list[tuple[date, date, int]] = []
    if len(dates) < 2:
        return gaps

    for older, newer in zip(dates, dates[1:]):
        delta_days = (newer - older).days
        missing_days = delta_days - expected_every_days
        if missing_days > 0:
            gaps.append((older, newer, missing_days))

    return gaps


def main() -> int:
    parser = argparse.ArgumentParser(description="Check autonomy-audit snapshot cadence for missing days")
    parser.add_argument(
        "--file",
        default="notes/autonomy-gaps.md",
        help="Path to autonomy-gaps markdown file (default: notes/autonomy-gaps.md)",
    )
    parser.add_argument(
        "--expected-every-days",
        type=int,
        default=1,
        help="Expected spacing between snapshots in days (default: 1)",
    )
    parser.add_argument(
        "--latest-only",
        action="store_true",
        help="Only check the latest snapshot pair (ignore historical gaps)",
    )
    parser.add_argument(
        "--fail-on-gap",
        action="store_true",
        help="Exit 2 when missing-day gaps are detected",
    )
    args = parser.parse_args()

    if args.expected_every_days < 1:
        print("❌ --expected-every-days must be >= 1", file=sys.stderr)
        return 1

    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    dates = parse_dates(text)

    if not dates:
        print(f"❌ No snapshot headings found in {path}", file=sys.stderr)
        return 1

    check_dates = dates
    if args.latest_only and len(dates) >= 2:
        check_dates = dates[-2:]

    gaps = find_gaps(check_dates, expected_every_days=args.expected_every_days)

    print(f"Cadence check: {path}")
    print(f"- Snapshots parsed: {len(dates)}")
    print(f"- Range (all): {dates[0].isoformat()} → {dates[-1].isoformat()}")
    if args.latest_only and len(dates) >= 2:
        print(f"- Scope: latest pair only ({check_dates[0].isoformat()} → {check_dates[-1].isoformat()})")

    if not gaps:
        print("✅ No missing-day cadence gaps detected")
        return 0

    print("⚠️ Missing-day cadence gaps detected:")
    for older, newer, missing_days in gaps:
        print(f"- {older.isoformat()} → {newer.isoformat()}: missing {missing_days} day(s)")

    if args.fail_on_gap:
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
