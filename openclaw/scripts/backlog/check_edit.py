#!/usr/bin/env python3
"""Read-only recovery-warning preservation check for a proposed backlog rewrite."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from list_statuses import CORRUPTION_GUARD_MARKERS


def guard_lines(text: str) -> Counter[str]:
    return Counter(
        line for line in text.splitlines()
        if any(marker in line for marker in CORRUPTION_GUARD_MARKERS)
    )


def check_edit(before: Path, after: Path) -> dict:
    try:
        if not before.is_file() or not after.is_file():
            raise ValueError("Both inputs must be existing regular files")
        if before.samefile(after):
            raise ValueError("Before and after must be distinct files, not aliases")
        original = guard_lines(before.read_text(encoding="utf-8"))
        candidate = guard_lines(after.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}

    missing = original - candidate
    return {
        "ok": not missing,
        "beforeGuardLines": original.total(),
        "afterGuardLines": candidate.total(),
        "missingGuardLines": missing.total(),
        "missingMarkers": [
            marker for marker in CORRUPTION_GUARD_MARKERS
            if any(marker in line for line in missing)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="Snapshot saved before editing")
    parser.add_argument("--after", type=Path, required=True, help="Separate proposed live-backlog content")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = check_edit(args.before, args.after)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    elif "error" in result:
        print(f"Backlog edit check failed: {result['error']}")
    elif result["ok"]:
        print(f"Recovery-warning preservation passed ({result['beforeGuardLines']} original guard lines)")
    else:
        print(f"Backlog edit rejected: {result['missingGuardLines']} recovery-warning lines removed or changed")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
