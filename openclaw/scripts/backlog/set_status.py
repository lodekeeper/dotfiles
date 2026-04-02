#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys


DISABLED_REASON = """`set_status.py` is intentionally disabled for now.

Why:
- the first version did an unlocked whole-file read/modify/write
- that is not safe under multiple concurrent backlog writers
- the observed exact-match `edit` failures were mostly noisy, not evidence that we
  should switch to a weaker concurrency model

What would be required before this helper is safe to use:
1. Acquire an exclusive lock on the backlog file (or a dedicated lock file).
2. Re-read the file *after* acquiring the lock.
3. Resolve the target heading/status against that locked, current content.
4. Write to a temp file in the same directory.
5. `fsync()` the temp file.
6. Atomically replace the original file via rename.
7. Optionally `fsync()` the parent directory.
8. Detect/report conflicts clearly when the target block changed underneath us.
9. Prefer tests that simulate concurrent writers.

Until then, do not use this helper as the standard backlog update path.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DISABLED: backlog status updater prototype retained only with safety notes."
    )
    parser.add_argument("--file")
    parser.add_argument("--task")
    parser.add_argument("--status")
    return parser.parse_args()


def main() -> int:
    parse_args()
    print(DISABLED_REASON, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
