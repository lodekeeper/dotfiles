#!/usr/bin/env python3
"""Unlink registered temp files without accepting broad cleanup patterns."""
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path


def allowed_temp_roots() -> list[str]:
    roots = {tempfile.gettempdir()}
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        roots.add(tmpdir)
    return sorted({os.path.abspath(root) for root in roots})


def is_under(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([root, path]) == root
    except ValueError:
        return False


def unlink_one(raw_path: str, roots: list[str]) -> str | None:
    path = os.path.abspath(raw_path)
    if not any(is_under(path, root) for root in roots):
        return f"refusing non-temp path: {raw_path}"

    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return None

    if stat.S_ISDIR(mode):
        return f"refusing directory path: {raw_path}"

    Path(path).unlink()
    return None


def main() -> int:
    roots = allowed_temp_roots()
    errors = [
        error
        for raw_path in sys.argv[1:]
        if (error := unlink_one(raw_path, roots)) is not None
    ]

    for error in errors:
        print(error, file=sys.stderr)
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
