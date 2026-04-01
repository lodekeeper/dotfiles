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
import re
import sys

SNAPSHOT_HEADING = re.compile(r"^## Daily Audit Snapshot — (\d{4}-\d{2}-\d{2})\b.*$", re.MULTILINE)
SECTION_HEADING = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
STATUS_LINE = re.compile(r"^\s*-\s+\*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)

REQUIRED_SECTIONS = [
    "PR review",
    "CI fix",
    "Spec implementation",
    "Devnet debugging",
]


def build_snapshot_block(date_str: str, time_label: str, status_prefill: dict[str, str] | None = None) -> str:
    status_prefill = status_prefill or {}

    lines = [
        f"## Daily Audit Snapshot — {date_str} (self-improvement-audit-daily, {time_label})",
        "",
    ]

    for section_name in REQUIRED_SECTIONS:
        status_value = status_prefill.get(section_name, "_fill in_")
        lines.extend(
            [
                f"### {section_name}",
                f"- **Status:** {status_value}",
                "",
            ]
        )

    lines.extend(["---", ""])
    return "\n".join(lines)


def first_snapshot_block(text: str) -> str | None:
    matches = list(SNAPSHOT_HEADING.finditer(text))
    if not matches:
        return None

    start = matches[0].start()
    end = matches[1].start() if len(matches) > 1 else len(text)
    return text[start:end]


def extract_status_prefill(snapshot_block: str) -> dict[str, str]:
    section_matches = list(SECTION_HEADING.finditer(snapshot_block))
    sections: dict[str, str] = {}

    for i, match in enumerate(section_matches):
        section_name = match.group(1).strip().lower()
        start = match.end()
        end = section_matches[i + 1].start() if i + 1 < len(section_matches) else len(snapshot_block)
        sections[section_name] = snapshot_block[start:end]

    prefill: dict[str, str] = {}
    for section_name in REQUIRED_SECTIONS:
        body = sections.get(section_name.lower(), "")
        matches = list(STATUS_LINE.finditer(body))
        if len(matches) != 1:
            continue

        value = matches[0].group(1).strip()
        if value:
            prefill[section_name] = value

    return prefill


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
    parser.add_argument(
        "--carry-forward-status",
        action="store_true",
        help="Prefill required section status lines using the latest existing snapshot",
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

    status_prefill: dict[str, str] | None = None
    if args.carry_forward_status:
        latest_snapshot = first_snapshot_block(text)
        if latest_snapshot:
            status_prefill = extract_status_prefill(latest_snapshot)
            if status_prefill:
                print("ℹ️ Carry-forward status prefill enabled (copied from latest snapshot)")
            else:
                print("ℹ️ Carry-forward status prefill enabled but no reusable status lines found")

    separator = "\n---\n\n"
    first_sep_idx = text.find(separator)
    if first_sep_idx == -1:
        print("❌ Could not find top-level separator '\n---\n\n' in target file", file=sys.stderr)
        return 2

    insert_at = first_sep_idx + len(separator)
    snapshot = build_snapshot_block(date_str=date_str, time_label=time_label, status_prefill=status_prefill)
    updated = text[:insert_at] + snapshot + text[insert_at:]

    path.write_text(updated, encoding="utf-8")
    print(f"✅ Inserted snapshot scaffold for {date_str} ({time_label}) into {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
