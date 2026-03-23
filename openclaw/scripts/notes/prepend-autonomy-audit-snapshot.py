#!/usr/bin/env python3
"""Prepend a dated autonomy-audit snapshot scaffold to notes/autonomy-gaps.md.

Keeps snapshot formatting consistent and ensures all four required domains are always present:
- PR review
- CI fix
- Spec implementation
- Devnet debugging
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


def build_snapshot_block(date_str: str, time_label: str) -> str:
    return (
        f"## Daily Audit Snapshot — {date_str} (self-improvement-audit-daily, {time_label})\n\n"
        "### PR review\n"
        "- **Status:** _fill in_\n\n"
        "### CI fix\n"
        "- **Status:** _fill in_\n\n"
        "### Spec implementation\n"
        "- **Status:** _fill in_\n\n"
        "### Devnet debugging\n"
        "- **Status:** _fill in_\n\n"
        "---\n\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepend a consistent daily snapshot scaffold to autonomy-gaps.md"
    )
    parser.add_argument(
        "--file",
        default="notes/autonomy-gaps.md",
        help="Target autonomy-gaps markdown file (default: notes/autonomy-gaps.md)",
    )
    parser.add_argument("--date", help="Snapshot date (YYYY-MM-DD). Default: current UTC date")
    parser.add_argument(
        "--time-label",
        help='Time label in heading (default: current UTC time as "HH:MM UTC")',
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow inserting even if a snapshot for the same date already exists",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    date_str = args.date or now.strftime("%Y-%m-%d")
    time_label = args.time_label or now.strftime("%H:%M UTC")

    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    marker = f"## Daily Audit Snapshot — {date_str}"
    if marker in text and not args.force:
        print(f"ℹ️ Snapshot already exists for {date_str}; skipped (use --force to override)")
        return 0

    separator = "\n---\n\n"
    first_sep_idx = text.find(separator)
    if first_sep_idx == -1:
        print("❌ Could not find top-level separator '\n---\n\n' in target file", file=sys.stderr)
        return 2

    insert_at = first_sep_idx + len(separator)
    snapshot = build_snapshot_block(date_str=date_str, time_label=time_label)
    updated = text[:insert_at] + snapshot + text[insert_at:]

    path.write_text(updated, encoding="utf-8")
    print(f"✅ Inserted snapshot scaffold for {date_str} ({time_label}) into {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
