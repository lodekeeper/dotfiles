#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the status line for a BACKLOG.md task heading without brittle exact-match edits."
    )
    parser.add_argument(
        "--file",
        default="/home/openclaw/.openclaw/workspace/BACKLOG.md",
        help="Path to backlog file (default: workspace BACKLOG.md)",
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task heading text to match. Uses case-insensitive substring matching against '### ...' headings.",
    )
    parser.add_argument(
        "--status",
        required=True,
        help="Replacement text after '- **Status:** '.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.file)
    if not path.exists():
        print(f"error: backlog file not found: {path}", file=sys.stderr)
        return 1

    lines = path.read_text(encoding="utf-8").splitlines()
    task_query = args.task.casefold()

    matches: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if line.startswith("### ") and task_query in line.casefold():
            matches.append((i, line))

    if not matches:
        print(f"error: no task heading matched query: {args.task!r}", file=sys.stderr)
        return 1

    if len(matches) > 1:
        print("error: task query matched multiple headings; be more specific:", file=sys.stderr)
        for _, heading in matches:
            print(f"  - {heading}", file=sys.stderr)
        return 1

    task_idx, task_heading = matches[0]
    status_idx = None
    for i in range(task_idx + 1, len(lines)):
        line = lines[i]
        if re.match(r"^### ", line):
            break
        if line.startswith("- **Status:**"):
            status_idx = i
            break

    if status_idx is None:
        print(f"error: no status line found under heading: {task_heading}", file=sys.stderr)
        return 1

    lines[status_idx] = f"- **Status:** {args.status}"
    new_text = "\n".join(lines) + "\n"
    path.write_text(new_text, encoding="utf-8")
    print(f"updated {path}: {task_heading}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
