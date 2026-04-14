#!/usr/bin/env python3
"""Remove older duplicate daily snapshot blocks from autonomy-gaps notes.

Keeps the first occurrence of each snapshot date (top-most/newest block) and
removes later duplicates for the same date.

Exit codes:
- 0: no duplicates found, or duplicates fixed with --apply
- 2: duplicates found in dry-run mode
- 1: usage/runtime error
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SNAPSHOT_HEADING = re.compile(r"^## Daily Audit Snapshot — (\d{4}-\d{2}-\d{2})\b")


def find_snapshot_ranges(lines: list[str]) -> list[tuple[int, int, str]]:
    starts: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        match = SNAPSHOT_HEADING.match(line)
        if match:
            starts.append((idx, match.group(1)))

    ranges: list[tuple[int, int, str]] = []
    for i, (start, date_str) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(lines)
        ranges.append((start, end, date_str))
    return ranges


def main() -> int:
    parser = argparse.ArgumentParser(description="Dedupe duplicate daily snapshot blocks by date.")
    parser.add_argument("--file", default="notes/autonomy-gaps.md", help="Target markdown file")
    parser.add_argument("--apply", action="store_true", help="Write deduped output back to file")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    ranges = find_snapshot_ranges(lines)

    if not ranges:
        print(f"Checked: {path}")
        print("- Snapshot headings found: 0")
        print("✅ No snapshot headings found; nothing to dedupe")
        return 0

    seen_dates: set[str] = set()
    duplicate_ranges: list[tuple[int, int, str]] = []

    for start, end, date_str in ranges:
        if date_str in seen_dates:
            duplicate_ranges.append((start, end, date_str))
        else:
            seen_dates.add(date_str)

    print(f"Checked: {path}")
    print(f"- Snapshot headings found: {len(ranges)}")

    if not duplicate_ranges:
        print("✅ No duplicate snapshot dates found")
        return 0

    counts: dict[str, int] = {}
    for _, _, date_str in duplicate_ranges:
        counts[date_str] = counts.get(date_str, 0) + 1

    print("⚠️ Duplicate snapshot blocks detected (older duplicates):")
    for date_str in sorted(counts):
        # +1 because one kept copy exists in addition to removed duplicates
        print(f"- {date_str}: {counts[date_str] + 1} total entries")

    if not args.apply:
        print("ℹ️ Dry-run only. Re-run with --apply to remove older duplicate blocks.")
        return 2

    keep = [True] * len(lines)
    removed_lines = 0
    for start, end, _ in duplicate_ranges:
        for idx in range(start, end):
            if keep[idx]:
                keep[idx] = False
                removed_lines += 1

    new_text = "".join(line for idx, line in enumerate(lines) if keep[idx])
    path.write_text(new_text, encoding="utf-8")

    print(f"✅ Removed {len(duplicate_ranges)} duplicate snapshot block(s) ({removed_lines} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
