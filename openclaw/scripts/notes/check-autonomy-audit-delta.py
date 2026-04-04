#!/usr/bin/env python3
"""Detect meaningful deltas between daily autonomy-audit snapshots.

This helps decide whether the daily audit should emit a summary or `NO_REPLY`.

Meaningful delta heuristic:
- Compare the target snapshot body to the previous snapshot body (excluding heading line)
- If body text differs after light normalization, it's a meaningful change
- Also reports which required section status lines changed for quick triage
- Optional `--json` mode emits machine-readable output for cron wrappers

Exit codes:
- 0: delta detected (or no delta and --fail-on-no-change not set)
- 3: no delta and --fail-on-no-change set
- 2: target/previous snapshot missing or malformed
- 1: runtime/usage error
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
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


@dataclass
class Snapshot:
    date: str
    start: int
    end: int
    heading_line: str
    body: str


def normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]

    # Collapse repeated blank lines to reduce noise from formatting-only edits.
    normalized: list[str] = []
    last_blank = False
    for line in lines:
        blank = line.strip() == ""
        if blank and last_blank:
            continue
        normalized.append(line)
        last_blank = blank

    return "\n".join(normalized).strip()


def parse_snapshots(text: str) -> list[Snapshot]:
    matches = list(SNAPSHOT_HEADING.finditer(text))
    snapshots: list[Snapshot] = []

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        first_newline = block.find("\n")
        if first_newline == -1:
            heading_line = block.strip()
            body = ""
        else:
            heading_line = block[:first_newline].strip()
            body = block[first_newline + 1 :]

        snapshots.append(
            Snapshot(
                date=match.group(1),
                start=start,
                end=end,
                heading_line=heading_line,
                body=body,
            )
        )

    return snapshots


def parse_sections(body: str) -> dict[str, str]:
    section_matches = list(SECTION_HEADING.finditer(body))
    sections: dict[str, str] = {}

    for i, match in enumerate(section_matches):
        section_name = match.group(1).strip()
        start = match.end()
        end = section_matches[i + 1].start() if i + 1 < len(section_matches) else len(body)
        sections[section_name] = body[start:end]

    return sections


def get_required_statuses(body: str) -> dict[str, str]:
    sections = parse_sections(body)

    statuses: dict[str, str] = {}
    for section_name in REQUIRED_SECTIONS:
        section_body = sections.get(section_name, "")
        status_match = STATUS_LINE.search(section_body)
        if status_match:
            statuses[section_name] = normalize_text(status_match.group(1))

    return statuses


def find_snapshot_with_previous(snapshots: list[Snapshot], date_str: str | None) -> tuple[Snapshot, Snapshot]:
    if not snapshots:
        raise ValueError("No snapshots found")

    if date_str is None:
        if len(snapshots) < 2:
            raise ValueError("Need at least two snapshots to compare")
        return snapshots[0], snapshots[1]

    for i, snap in enumerate(snapshots):
        if snap.date != date_str:
            continue
        if i + 1 >= len(snapshots):
            raise ValueError(f"No previous snapshot found for date {date_str}")
        return snap, snapshots[i + 1]

    raise ValueError(f"Snapshot not found for date {date_str}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether autonomy-audit snapshot changed meaningfully")
    parser.add_argument("--file", default="notes/autonomy-gaps.md", help="Path to autonomy-gaps markdown")
    parser.add_argument("--date", help="Target snapshot date YYYY-MM-DD (default: latest snapshot)")
    parser.add_argument(
        "--fail-on-no-change",
        action="store_true",
        help="Return exit code 3 when no meaningful change is detected",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output instead of human-readable text",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    snapshots = parse_snapshots(text)

    try:
        current, previous = find_snapshot_with_previous(snapshots, args.date)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    current_norm = normalize_text(current.body)
    previous_norm = normalize_text(previous.body)
    has_delta = current_norm != previous_norm

    current_statuses = get_required_statuses(current.body)
    previous_statuses = get_required_statuses(previous.body)
    changed_required_sections = [
        section
        for section in REQUIRED_SECTIONS
        if current_statuses.get(section) != previous_statuses.get(section)
    ]

    current_sections = parse_sections(current.body)
    previous_sections = parse_sections(previous.body)

    current_headings = [name.strip() for name in current_sections.keys()]
    previous_headings = [name.strip() for name in previous_sections.keys()]

    added_headings = [name for name in current_headings if name not in previous_headings]
    removed_headings = [name for name in previous_headings if name not in current_headings]

    required_lookup = {name.lower() for name in REQUIRED_SECTIONS}
    shared_non_required = [
        name
        for name in current_sections.keys()
        if name in previous_sections and name.lower() not in required_lookup
    ]
    changed_non_required_sections = [
        name
        for name in shared_non_required
        if normalize_text(current_sections[name]) != normalize_text(previous_sections[name])
    ]

    status_deltas = {
        section: {
            "current": current_statuses.get(section),
            "previous": previous_statuses.get(section),
        }
        for section in changed_required_sections
    }

    payload = {
        "currentDate": current.date,
        "previousDate": previous.date,
        "hasDelta": has_delta,
        "changedRequiredSections": changed_required_sections,
        "statusDeltas": status_deltas,
        "changedNonRequiredSections": changed_non_required_sections,
        "addedSectionHeadings": added_headings,
        "removedSectionHeadings": removed_headings,
        "noReplyRecommended": (not has_delta),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"Compared snapshots: {current.date} vs {previous.date}")
        print(f"Meaningful delta: {'yes' if has_delta else 'no'}")

        if changed_required_sections:
            print("Changed required-section status lines:")
            for section in changed_required_sections:
                print(f"- {section}")
        else:
            print("Changed required-section status lines: none")

        if changed_non_required_sections:
            print("Changed non-required section bodies:")
            for section in changed_non_required_sections:
                print(f"- {section}")
        else:
            print("Changed non-required section bodies: none")

        if added_headings:
            print("Added section headings:")
            for heading in added_headings:
                print(f"- {heading}")

        if removed_headings:
            print("Removed section headings:")
            for heading in removed_headings:
                print(f"- {heading}")

    if not has_delta and args.fail_on_no_change:
        if not args.json:
            print("⚠️ No meaningful change detected; recommend NO_REPLY")
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
