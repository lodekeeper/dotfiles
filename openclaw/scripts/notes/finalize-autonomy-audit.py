#!/usr/bin/env python3
"""Finalize daily autonomy-audit notes.

Checks today's snapshot is fully filled, refreshes the top-level Updated line,
and re-runs the consistency guard as a final safety check.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys

SNAPSHOT_HEADING = re.compile(r"^## Daily Audit Snapshot — (\d{4}-\d{2}-\d{2})\b.*$", re.MULTILINE)
UPDATED_LINE = re.compile(r"^> Updated: .*$", re.MULTILINE)
SECTION_HEADING = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
STATUS_LINE = re.compile(r"^\s*-\s+\*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)
REQUIRED_SECTIONS = [
    "PR review",
    "CI fix",
    "Spec implementation",
    "Devnet debugging",
]
STATUS_PLACEHOLDERS = {"", "_fill in_", "fill in", "tbd", "todo"}


def ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def snapshot_block(text: str, date_str: str) -> str | None:
    headings = list(SNAPSHOT_HEADING.finditer(text))
    for i, match in enumerate(headings):
        if match.group(1) != date_str:
            continue
        start = match.start()
        if i + 1 < len(headings):
            end = headings[i + 1].start()
        else:
            end = len(text)
        return text[start:end]
    return None


def find_missing_sections(block: str) -> list[str]:
    present = {m.group(1).strip().lower() for m in SECTION_HEADING.finditer(block)}
    return [name for name in REQUIRED_SECTIONS if name.lower() not in present]


def section_blocks(block: str) -> dict[str, str]:
    matches = list(SECTION_HEADING.finditer(block))
    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        name = match.group(1).strip().lower()
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(block)
        sections[name] = block[start:end]
    return sections


def find_sections_with_invalid_status(block: str) -> list[str]:
    sections = section_blocks(block)
    invalid: list[str] = []
    for name in REQUIRED_SECTIONS:
        body = sections.get(name.lower(), "")
        status_match = STATUS_LINE.search(body)
        if status_match is None:
            invalid.append(name)
            continue

        status_value = status_match.group(1).strip().strip("`").lower()
        if status_value in STATUS_PLACEHOLDERS:
            invalid.append(name)

    return invalid


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize autonomy-audit markdown for a given date")
    parser.add_argument("--file", default="notes/autonomy-gaps.md", help="Target markdown file")
    parser.add_argument("--date", help="Audit date YYYY-MM-DD (default: current UTC date)")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    date_str = args.date or now.strftime("%Y-%m-%d")

    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    headings = list(SNAPSHOT_HEADING.finditer(text))
    if not headings:
        print("❌ No snapshot headings found in file", file=sys.stderr)
        return 2

    block = snapshot_block(text, date_str)
    if block is None:
        print(f"❌ No snapshot found for date {date_str}", file=sys.stderr)
        return 2

    if "_fill in_" in block:
        print(f"❌ Snapshot {date_str} still has '_fill in_' placeholders", file=sys.stderr)
        return 2

    missing_sections = find_missing_sections(block)
    if missing_sections:
        joined = ", ".join(missing_sections)
        print(
            f"❌ Snapshot {date_str} is missing required section heading(s): {joined}",
            file=sys.stderr,
        )
        return 2

    invalid_status_sections = find_sections_with_invalid_status(block)
    if invalid_status_sections:
        joined = ", ".join(invalid_status_sections)
        print(
            "❌ Snapshot "
            f"{date_str} must include a non-empty '- **Status:** ...' line in each required section. "
            f"Fix section(s): {joined}",
            file=sys.stderr,
        )
        return 2

    pass_count = len(headings)
    new_updated = f"> Updated: {date_str} ({ordinal(pass_count)} pass)"
    if not UPDATED_LINE.search(text):
        print("❌ Could not find '> Updated:' line", file=sys.stderr)
        return 2

    updated_text = UPDATED_LINE.sub(new_updated, text, count=1)
    if updated_text != text:
        path.write_text(updated_text, encoding="utf-8")
        print(f"✅ Updated header line: {new_updated}")
    else:
        print(f"ℹ️ Header already current: {new_updated}")

    script_dir = Path(__file__).resolve().parent
    check_script = script_dir / "check-autonomy-gaps-consistency.py"
    cmd = [sys.executable, str(check_script), "--file", str(path)]
    print("[final check] running consistency guard")
    subprocess.run(cmd, check=True)

    print(f"✅ Finalized autonomy audit for {date_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
