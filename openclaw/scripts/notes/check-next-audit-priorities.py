#!/usr/bin/env python3
"""Check whether the live 'Next Audit Priorities' section has actionable items.

This helper distinguishes between:
- the intentional empty-state guidance block, and
- real live items that a reminder should act on.

Exit codes:
- 0: success
- 2: target section missing
- 1: runtime/usage error
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

SECTION_TITLE = "Next Audit Priorities (next daily cycles)"
H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
NUMBERED_ITEM_RE = re.compile(r"^\s*\d+\.\s+(.*)$")

EMPTY_STATE_POLICY_ITEMS = {
    "Only add a new item here when the **latest daily audit snapshot** introduces a still-open blocker or concrete follow-up.",
    "If the latest snapshot is fully green, leave this section empty of filler work and use `BACKLOG.md` for unrelated concrete tasks.",
    "When repopulating the list, prefer one specific automation gap that is **not already marked `✅ done` elsewhere in this file**.",
    "If a reminder fires while this section has no live items, the correct outcome is routine silence / `NO_REPLY`.",
}


def extract_section(text: str, title: str) -> str | None:
    matches = list(H2_RE.finditer(text))
    for i, match in enumerate(matches):
        if match.group(1).strip() != title:
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        return text[start:end]
    return None


def is_empty_state_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True

    if stripped.startswith("All previously listed priority items in this section are complete as of"):
        return True

    if stripped.startswith("Helper:"):
        return True

    numbered_match = NUMBERED_ITEM_RE.match(stripped)
    if numbered_match:
        item_body = numbered_match.group(1).strip()
        if item_body in EMPTY_STATE_POLICY_ITEMS:
            return True

    return False


def find_live_items(section_text: str) -> list[str]:
    live_items: list[str] = []
    for raw_line in section_text.splitlines():
        if is_empty_state_line(raw_line):
            continue
        live_items.append(raw_line.rstrip())
    return live_items


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether Next Audit Priorities has live actionable items")
    parser.add_argument("--file", default="notes/autonomy-gaps.md", help="Path to autonomy-gaps markdown")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    section = extract_section(text, SECTION_TITLE)
    if section is None:
        print(f"❌ Section not found: {SECTION_TITLE}", file=sys.stderr)
        return 2

    live_items = find_live_items(section)
    payload = {
        "sectionTitle": SECTION_TITLE,
        "hasLiveItems": bool(live_items),
        "items": live_items,
        "emptyStateOnly": not bool(live_items),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if live_items:
            print("LIVE_ITEMS_PRESENT")
            for item in live_items:
                print(item)
        else:
            print("NO_LIVE_ITEMS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
