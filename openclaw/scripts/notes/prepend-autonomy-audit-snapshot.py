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

TIME_LABEL_PREFIX = "self-improvement-audit-daily"

STEADY_STATE_STATUS = {
    "PR review": "no new PR-review blocker discovered this cycle; existing review guardrails remain healthy.",
    "CI fix": "retry telemetry + fallback log acquisition path remain healthy; no new blocker discovered this cycle.",
    "Spec implementation": "architecture-timeout fallback + compliance/vector gates remain healthy; no new blocker discovered this cycle.",
    "Devnet debugging": "triage/correlator/incident bundle workflow remains healthy; no new blocker discovered this cycle.",
}

# Carry-forward prefill should not copy prior-cycle "fix applied" language verbatim.
# If those phrases are detected, collapse back to section steady-state wording.
CHANGE_EVENT_PATTERNS = [
    re.compile(r"\bfix applied this cycle\b", re.IGNORECASE),
    re.compile(r"\bfound and fixed this cycle\b", re.IGNORECASE),
    re.compile(r"\bimplemented\b", re.IGNORECASE),
    re.compile(r"\badded\b", re.IGNORECASE),
    re.compile(r"\bupdated\b", re.IGNORECASE),
]


def normalize_time_label(raw_time_label: str) -> str:
    """Normalize user-provided time labels to avoid duplicated heading prefixes.

    Accepts both:
    - "HH:MM UTC" (preferred)
    - "self-improvement-audit-daily, HH:MM UTC" (legacy / copied from cron text)
    """
    label = raw_time_label.strip()
    prefix_pattern = re.compile(rf"^{re.escape(TIME_LABEL_PREFIX)}\s*,\s*", re.IGNORECASE)
    label = prefix_pattern.sub("", label)
    return label.strip()


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


def sanitize_carry_forward_status(section_name: str, value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return trimmed

    if any(pattern.search(trimmed) for pattern in CHANGE_EVENT_PATTERNS):
        return STEADY_STATE_STATUS.get(section_name, trimmed)

    return trimmed


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
            prefill[section_name] = sanitize_carry_forward_status(section_name, value)

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
    raw_time_label = args.time_label or now.strftime("%H:%M UTC")
    time_label = normalize_time_label(raw_time_label)

    if not time_label:
        print("❌ Time label resolved to empty value after normalization", file=sys.stderr)
        return 1

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
