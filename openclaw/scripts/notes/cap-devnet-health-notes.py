#!/usr/bin/env python3
"""Cap the append-only `note` field on devnet-health dedup entries.

`memory/devnet-health/state.json` is written by the isolated "Devnet health
monitor" cron every ~2h. Each `reported` entry's `note` field is a
` | `-joined, ISO-timestamp-prefixed log that previously grew unbounded
(one entry reached 40 segments / ~10.6KB), pushing the whole file past the
Read tool's ~25K-token cap and silently hiding older entries from any
session that reads it naively instead of via a script.

This does NOT touch `signature` / `first_seen` / `last_seen` / `thread_id` /
`network` / `title` / `client` / `lodestar_impacted` — the dedup mechanism
depends only on those fields, never on `note` content.

Exit codes:
- 0: success (or, with --check-only, no entries currently over the cap)
- 1: runtime/usage error
- 3: --check-only --fail-if-over set and at least one entry is over the cap
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEGMENT_SEP = " | "
MARKER_RE = re.compile(r"^\[\.\.\.(\d+) earlier entries truncated\.\.\.\]" + re.escape(SEGMENT_SEP))


def cap_note(note: str, max_segments: int) -> tuple[str, int]:
    """Return (possibly-truncated note, number of *new* segments dropped this call).

    Idempotent: a note already capped to max_segments (with or without a
    leading marker) round-trips unchanged, and re-running against an
    already-capped note never eats the marker as if it were content.
    """
    match = MARKER_RE.match(note)
    prior_dropped = int(match.group(1)) if match else 0
    remainder = note[match.end():] if match else note

    parts = remainder.split(SEGMENT_SEP)
    if len(parts) <= max_segments:
        return note, 0

    new_dropped = len(parts) - max_segments
    total_dropped = prior_dropped + new_dropped
    marker = f"[...{total_dropped} earlier entries truncated...]"
    kept = SEGMENT_SEP.join(parts[-max_segments:])
    return f"{marker}{SEGMENT_SEP}{kept}", new_dropped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="memory/devnet-health/state.json", help="Path to the dedup state JSON")
    parser.add_argument("--max-segments", type=int, default=3, help="Timestamped log segments to keep per note")
    parser.add_argument("--check-only", action="store_true", help="Report over-cap entries without writing")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--fail-if-over", action="store_true", help="With --check-only, exit 3 if any entry is over cap")
    parser.add_argument("--no-backup", action="store_true", help="Skip writing a .bak-<orig-size> sidecar before mutating")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ Invalid JSON in {path}: {exc}", file=sys.stderr)
        return 1

    reported = data.get("reported")
    if not isinstance(reported, list):
        print(f"❌ Expected a 'reported' list in {path}", file=sys.stderr)
        return 1

    changes = []
    for entry in reported:
        note = entry.get("note")
        if not isinstance(note, str) or not note:
            continue
        new_note, dropped = cap_note(note, args.max_segments)
        if dropped:
            changes.append(
                {
                    "signature": entry.get("signature"),
                    "before_len": len(note),
                    "after_len": len(new_note),
                    "segments_dropped": dropped,
                }
            )
            if not args.check_only:
                entry["note"] = new_note

    payload = {
        "file": str(path),
        "maxSegments": args.max_segments,
        "entriesOverCap": len(changes),
        "changes": changes,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if not changes:
            print("NO_ENTRIES_OVER_CAP")
        else:
            mode = "would cap" if args.check_only else "capped"
            for change in changes:
                print(f"{mode} {change['signature']}: {change['before_len']} -> {change['after_len']} bytes")

    if args.check_only:
        if args.fail_if_over and changes:
            return 3
        return 0

    if changes:
        if not args.no_backup:
            backup_path = path.with_name(f"{path.name}.bak-{path.stat().st_size}")
            backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
