#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_BACKLOG = Path("/home/openclaw/.openclaw/workspace/BACKLOG.md")
DONE_PREFIXES = ("✅",)
NON_ACTIONABLE_STATUS_PREFIXES = (
    "blocked",
    "passive",
    "parked",
    "superseded",
)
CORRUPTION_GUARD_MARKERS = (
    "DO NOT ACT ON THIS FILE",
    "DO NOT ACT ON ENTRIES BELOW",
)


@dataclass
class TaskBlock:
    section: str
    heading: str
    status: str | None
    body: list[str]
    start_line: int


STATUS_RE = re.compile(r"^- \*\*Status:\*\*\s*(.*)$")


def parse_backlog(text: str) -> list[TaskBlock]:
    lines = text.splitlines()
    section = "(no section)"
    tasks: list[TaskBlock] = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]

        if line.startswith("## "):
            section = line
            idx += 1
            continue

        if not line.startswith("### "):
            idx += 1
            continue

        heading = line
        start_line = idx + 1
        idx += 1
        body: list[str] = []

        while idx < len(lines) and not lines[idx].startswith("### ") and not lines[idx].startswith("## "):
            body.append(lines[idx])
            idx += 1

        status = None
        for body_line in body:
            m = STATUS_RE.match(body_line)
            if m:
                status = m.group(1).strip()
                break

        tasks.append(TaskBlock(section=section, heading=heading, status=status, body=body, start_line=start_line))

    return tasks


def has_corruption_guard(text: str) -> bool:
    head = "\n".join(text.splitlines()[:12])
    return any(marker in head for marker in CORRUPTION_GUARD_MARKERS)


def is_done(task: TaskBlock) -> bool:
    icon = task.heading.replace("###", "", 1).strip().split(" ", 1)[0]
    if icon.startswith(DONE_PREFIXES):
        return True
    if task.status is None:
        return False
    status = task.status.strip()
    return status.startswith(DONE_PREFIXES) or status.casefold().startswith("done")


def is_actionable(task: TaskBlock) -> bool:
    if is_done(task):
        return False
    if task.status is None:
        return True

    status = task.status.casefold()
    if status.startswith(NON_ACTIONABLE_STATUS_PREFIXES):
        return False
    return not status.startswith("awaiting")


def render_text(tasks: Iterable[TaskBlock]) -> str:
    out: list[str] = []
    current_section: str | None = None
    for task in tasks:
        if task.section != current_section:
            if out:
                out.append("")
            out.append(task.section)
            current_section = task.section
        out.append(f"- {task.heading}")
        out.append(f"  status: {task.status or '(missing)'}")
        out.append(f"  line: {task.start_line}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Safely list task headings and status lines from BACKLOG.md")
    ap.add_argument("--file", type=Path, default=DEFAULT_BACKLOG)
    ap.add_argument("--active-only", action="store_true", help="Exclude done task headings and done status lines")
    ap.add_argument(
        "--actionable-only",
        action="store_true",
        help="Exclude done task headings/statuses plus passive-watch, blocked, parked, and awaiting statuses",
    )
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    ap.add_argument(
        "--allow-corrupted-backlog",
        action="store_true",
        help="Allow parsing a backlog file that carries the corruption/recovery guard",
    )
    ap.add_argument(
        "--require-corruption-guard",
        action="store_true",
        help="Fail if the backlog file is missing the corruption/recovery guard",
    )
    args = ap.parse_args()

    text = args.file.read_text()
    guarded = has_corruption_guard(text)
    if args.require_corruption_guard and not guarded:
        print(
            f"{args.file} is missing the corruption/recovery guard.",
            file=sys.stderr,
        )
        return 3

    if guarded and not args.allow_corrupted_backlog:
        print(
            f"{args.file} is marked corrupted/under recovery; refusing to list task statuses. "
            "Use --allow-corrupted-backlog only for recovery/audit work.",
            file=sys.stderr,
        )
        return 2

    tasks = parse_backlog(text)
    if args.actionable_only:
        tasks = [task for task in tasks if is_actionable(task)]
    elif args.active_only:
        tasks = [task for task in tasks if not is_done(task)]

    if args.json:
        print(json.dumps([asdict(task) for task in tasks], indent=2))
    else:
        print(render_text(tasks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
