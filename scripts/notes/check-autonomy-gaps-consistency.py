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

    print(f"Checked: {path}")
    print(f"- Gap items parsed: {len(gaps)}")
    print(f"- Improvement entries parsed: {len(improvements)}")

    all_conflicts = title_conflicts + ref_conflicts
    if not all_conflicts:
        print("✅ No contradictions detected")
        return 0

    print("❌ Contradictions detected:")
    for c in all_conflicts:
        print(f"- {c}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
