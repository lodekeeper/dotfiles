#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_BACKLOG = Path("/home/openclaw/.openclaw/workspace/BACKLOG.md")
DONE_PREFIXES = ("✅", "🟢")


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


def is_done(task: TaskBlock) -> bool:
    icon = task.heading.replace("###", "", 1).strip().split(" ", 1)[0]
    return icon.startswith(DONE_PREFIXES)


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
    ap.add_argument("--active-only", action="store_true", help="Exclude done/green task headings")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = ap.parse_args()

    text = args.file.read_text()
    tasks = parse_backlog(text)
    if args.active_only:
        tasks = [task for task in tasks if not is_done(task)]

    if args.json:
        print(json.dumps([asdict(task) for task in tasks], indent=2))
    else:
        print(render_text(tasks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
