#!/usr/bin/env python3
"""Check notes/autonomy-gaps.md for contradictory status markers.

Examples of contradictions this guard catches:
- Same gap item appears both open and fixed in "### Gaps"
- A script/doc path appears in an open gap's proposed fix and also in
  "## Improvements Implemented This Cycle"

Exit codes:
- 0: no contradictions found
- 2: contradictions found
- 1: usage or parsing/runtime error
"""

from __future__ import annotations

import argparse
from datetime import date
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


HEADING_GAPS = re.compile(r"^###\s+Gaps\s*$", re.IGNORECASE)
HEADING_IMPROVEMENTS = re.compile(r"^##\s+Improvements Implemented This Cycle\s*$", re.IGNORECASE)
HEADING_H2 = re.compile(r"^##\s+")
HEADING_H3 = re.compile(r"^###\s+")
HEADING_H4 = re.compile(r"^####\s+")
SNAPSHOT_HEADING = re.compile(r"^## Daily Audit Snapshot — (\d{4}-\d{2}-\d{2})\b", re.MULTILINE)
UPDATED_LINE = re.compile(r"^>\s*Updated:\s*(\d{4}-\d{2}-\d{2})\s*\((\d+)(?:st|nd|rd|th)\s+pass\)\s*$", re.MULTILINE)
SNAPSHOT_SECTION_HEADING = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
SNAPSHOT_STATUS_LINE = re.compile(r"^\s*-\s+\*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)
SNAPSHOT_LEGACY_MARKER = re.compile(
    r"^\s*-\s+\*\*(?:Blocker|Fix applied this cycle|Proposed fix|Status):\*\*",
    re.MULTILINE,
)

REQUIRED_SNAPSHOT_SECTIONS = [
    "PR review",
    "CI fix",
    "Spec implementation",
    "Devnet debugging",
]
STATUS_PLACEHOLDERS = {"", "_fill in_", "fill in", "tbd", "todo"}

CODE_SPAN = re.compile(r"`([^`]+)`")
PATH_LIKE = re.compile(r"^(?:\.?\.?/)?(?:scripts|notes|skills|docs|config|openclaw)/[^\s`]+$")


@dataclass
class GapItem:
    heading: str
    body: str
    fixed: bool
    title_norm: str
    refs: set[str]


@dataclass
class ImprovementItem:
    heading: str
    body: str
    refs: set[str]


def normalize_title(raw_heading: str) -> str:
    text = raw_heading
    text = re.sub(r"^####\s+", "", text)
    text = text.replace("~~", "")
    text = re.sub(r"✅\s*FIXED.*$", "", text)
    text = re.sub(r"^[🔴🟡🟢⏸️✅❌⚠️]\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def extract_refs(text: str) -> set[str]:
    refs: set[str] = set()

    for match in CODE_SPAN.findall(text):
        candidate = match.strip()
        if PATH_LIKE.match(candidate):
            refs.add(candidate)

    # Also catch bare script-like paths not wrapped in backticks.
    for token in re.findall(r"(?:\.?\.?/)?(?:scripts|notes|skills|docs|config|openclaw)/[^\s)]+", text):
        cleaned = token.rstrip('.,:;!\"\'')
        if PATH_LIKE.match(cleaned):
            refs.add(cleaned)

    return refs


def parse_gaps(lines: list[str]) -> list[GapItem]:
    items: list[GapItem] = []
    in_gaps = False
    current_heading: str | None = None
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, body_lines
        if not current_heading:
            return
        body = "\n".join(body_lines).strip()
        fixed = "✅" in current_heading and "FIXED" in current_heading.upper()
        refs = extract_refs(current_heading + "\n" + body)
        items.append(
            GapItem(
                heading=current_heading,
                body=body,
                fixed=fixed,
                title_norm=normalize_title(current_heading),
                refs=refs,
            )
        )
        current_heading = None
        body_lines = []

    for line in lines:
        if HEADING_GAPS.match(line):
            in_gaps = True
            flush()
            continue

        if in_gaps and (HEADING_H2.match(line) or HEADING_H3.match(line)) and not HEADING_H4.match(line):
            flush()
            in_gaps = False

        if not in_gaps:
            continue

        if HEADING_H4.match(line):
            flush()
            current_heading = line.rstrip()
            continue

        if current_heading is not None:
            body_lines.append(line.rstrip("\n"))

    flush()
    return items


def parse_improvements(lines: list[str]) -> list[ImprovementItem]:
    items: list[ImprovementItem] = []
    in_improvements = False
    current_heading: str | None = None
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, body_lines
        if not current_heading:
            return
        body = "\n".join(body_lines).strip()
        refs = extract_refs(current_heading + "\n" + body)
        items.append(ImprovementItem(heading=current_heading, body=body, refs=refs))
        current_heading = None
        body_lines = []

    for line in lines:
        if HEADING_IMPROVEMENTS.match(line):
            in_improvements = True
            flush()
            continue

        if in_improvements and HEADING_H2.match(line) and not HEADING_IMPROVEMENTS.match(line):
            flush()
            in_improvements = False

        if not in_improvements:
            continue

        if re.match(r"^###\s+", line):
            flush()
            current_heading = line.rstrip()
            continue

        if current_heading is not None:
            body_lines.append(line.rstrip("\n"))

    flush()
    return items


def find_title_conflicts(gaps: Iterable[GapItem]) -> list[str]:
    by_title: dict[str, set[bool]] = {}
    by_display: dict[str, str] = {}

    for g in gaps:
        by_title.setdefault(g.title_norm, set()).add(g.fixed)
        by_display.setdefault(g.title_norm, g.heading)

    conflicts = []
    for title, statuses in sorted(by_title.items()):
        if len(statuses) > 1:
            conflicts.append(f"Title appears as both open and fixed: {by_display[title]}")
    return conflicts


def find_ref_conflicts(gaps: Iterable[GapItem], improvements: Iterable[ImprovementItem]) -> list[str]:
    open_refs: dict[str, list[str]] = {}
    for g in gaps:
        if g.fixed:
            continue
        for ref in g.refs:
            open_refs.setdefault(ref, []).append(g.heading)

    improvement_refs: dict[str, list[str]] = {}
    for imp in improvements:
        for ref in imp.refs:
            improvement_refs.setdefault(ref, []).append(imp.heading)

    conflicts = []
    shared = sorted(set(open_refs) & set(improvement_refs))
    for ref in shared:
        conflicts.append(
            "Path appears both in open gap and improvements: "
            f"{ref} (open gap: {open_refs[ref][0]} | improvement: {improvement_refs[ref][0]})"
        )
    return conflicts


def find_fixed_gap_proposed_fix_conflicts(gaps: Iterable[GapItem]) -> list[str]:
    conflicts: list[str] = []
    proposed_fix_re = re.compile(r"^\s*(?:-\s*)?\*\*Proposed fix:\*\*", re.IGNORECASE | re.MULTILINE)

    for gap in gaps:
        if not gap.fixed:
            continue
        if proposed_fix_re.search(gap.body):
            conflicts.append(
                "Fixed gap still contains 'Proposed fix' wording: "
                f"{gap.heading}"
            )

    return conflicts


def find_duplicate_snapshot_dates(text: str) -> tuple[int, str | None, list[str], list[str]]:
    all_dates = [match.group(1) for match in SNAPSHOT_HEADING.finditer(text)]
    counts: dict[str, int] = {}
    for date_str in all_dates:
        counts[date_str] = counts.get(date_str, 0) + 1

    latest_date = all_dates[0] if all_dates else None
    conflicts: list[str] = []
    warnings: list[str] = []

    for date_str, count in sorted(counts.items()):
        if count <= 1:
            continue
        message = f"Snapshot date appears multiple times: {date_str} ({count} entries)"
        if date_str == latest_date:
            conflicts.append(message)
        else:
            warnings.append(message)

    return len(all_dates), latest_date, conflicts, warnings


def find_snapshot_order_conflicts(text: str) -> list[str]:
    snapshot_dates: list[date] = []
    for match in SNAPSHOT_HEADING.finditer(text):
        snapshot_dates.append(date.fromisoformat(match.group(1)))

    conflicts: list[str] = []
    for i in range(len(snapshot_dates) - 1):
        current_date = snapshot_dates[i]
        next_date = snapshot_dates[i + 1]

        # File order should be newest -> oldest (descending by date).
        if next_date > current_date:
            conflicts.append(
                "Snapshot headings out of order (expected newest→oldest): "
                f"{current_date.isoformat()} appears above newer {next_date.isoformat()}"
            )

    return conflicts


def iter_snapshot_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(SNAPSHOT_HEADING.finditer(text))
    blocks: list[tuple[str, str]] = []

    for i, match in enumerate(matches):
        date_str = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((date_str, text[start:end]))

    return blocks


def section_blocks(snapshot_block: str) -> dict[str, str]:
    matches = list(SNAPSHOT_SECTION_HEADING.finditer(snapshot_block))
    sections: dict[str, str] = {}

    for i, match in enumerate(matches):
        name = match.group(1).strip().lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(snapshot_block)
        sections[name] = snapshot_block[start:end]

    return sections


def find_snapshot_structure_conflicts(text: str) -> list[str]:
    conflicts: list[str] = []

    for date_str, block in iter_snapshot_blocks(text):
        sections = section_blocks(block)

        for section_name in REQUIRED_SNAPSHOT_SECTIONS:
            body = sections.get(section_name.lower())
            if body is None:
                conflicts.append(
                    f"Snapshot {date_str} missing required section heading: {section_name}"
                )
                continue

            status_matches = list(SNAPSHOT_STATUS_LINE.finditer(body))
            if len(status_matches) > 1:
                conflicts.append(
                    f"Snapshot {date_str} section '{section_name}' must contain at most one status line; found {len(status_matches)}"
                )
                continue

            if len(status_matches) == 1:
                status_value = status_matches[0].group(1).strip().strip("`").lower()
                if status_value in STATUS_PLACEHOLDERS:
                    conflicts.append(
                        f"Snapshot {date_str} section '{section_name}' has empty/placeholder status value"
                    )
                continue

            # Legacy snapshots may use blocker/fix/proposed-fix bullets instead of
            # normalized status lines. Require at least one structured marker so
            # fully empty sections are still rejected.
            if not SNAPSHOT_LEGACY_MARKER.search(body):
                conflicts.append(
                    f"Snapshot {date_str} section '{section_name}' has no structured status/blocker/fix marker"
                )

    return conflicts


def find_updated_line_conflicts(text: str, snapshot_count: int, latest_snapshot_date: str | None) -> list[str]:
    matches = list(UPDATED_LINE.finditer(text))
    if not matches:
        return [
            "Missing or malformed '> Updated: YYYY-MM-DD (Nth pass)' metadata line"
        ]

    conflicts: list[str] = []
    if len(matches) > 1:
        conflicts.append(f"Multiple '> Updated:' metadata lines found ({len(matches)})")

    updated_date = matches[0].group(1)
    updated_pass_count = int(matches[0].group(2))

    if latest_snapshot_date and updated_date != latest_snapshot_date:
        conflicts.append(
            "Updated metadata date does not match latest snapshot date: "
            f"updated={updated_date}, latest_snapshot={latest_snapshot_date}"
        )

    if updated_pass_count != snapshot_count:
        conflicts.append(
            "Updated metadata pass count does not match snapshot heading count: "
            f"updated={updated_pass_count}, snapshots={snapshot_count}"
        )

    return conflicts


def main() -> int:
    parser = argparse.ArgumentParser(description="Check autonomy-gaps markdown for contradictory status.")
    parser.add_argument(
        "--file",
        default="notes/autonomy-gaps.md",
        help="Path to autonomy-gaps markdown file (default: notes/autonomy-gaps.md)",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    gaps = parse_gaps(lines)
    improvements = parse_improvements(lines)

    title_conflicts = find_title_conflicts(gaps)
    ref_conflicts = find_ref_conflicts(gaps, improvements)
    fixed_gap_proposed_fix_conflicts = find_fixed_gap_proposed_fix_conflicts(gaps)
    snapshot_count, latest_snapshot_date, snapshot_conflicts, snapshot_warnings = find_duplicate_snapshot_dates(text)
    snapshot_order_conflicts = find_snapshot_order_conflicts(text)
    snapshot_structure_conflicts = find_snapshot_structure_conflicts(text)
    updated_line_conflicts = find_updated_line_conflicts(text, snapshot_count, latest_snapshot_date)

    print(f"Checked: {path}")
    print(f"- Gap items parsed: {len(gaps)}")
    print(f"- Improvement entries parsed: {len(improvements)}")
    print(f"- Snapshot headings parsed: {snapshot_count}")

    if snapshot_warnings:
        print("⚠️ Historical snapshot-date duplicates detected (non-blocking):")
        for warning in snapshot_warnings:
            print(f"- {warning}")
        print(
            "ℹ️ Optional cleanup: python3 scripts/notes/dedupe-autonomy-audit-snapshots.py "
            f"--file {path} --apply"
        )

    all_conflicts = (
        title_conflicts
        + ref_conflicts
        + fixed_gap_proposed_fix_conflicts
        + snapshot_conflicts
        + snapshot_order_conflicts
        + snapshot_structure_conflicts
        + updated_line_conflicts
    )
    if not all_conflicts:
        print("✅ No contradictions detected")
        return 0

    print("❌ Contradictions detected:")
    for c in all_conflicts:
        print(f"- {c}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
