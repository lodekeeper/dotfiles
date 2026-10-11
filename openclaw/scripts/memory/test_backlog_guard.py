#!/usr/bin/env python3
"""Keep guarded backlog data out of the index even after task prepends."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("rebuild_index_guard", Path(__file__).with_name("rebuild_index.py"))
assert SPEC is not None and SPEC.loader is not None
index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(index)

PREPENDED_TASKS = ("### ✅ Devnet health run\n- **Status:** Done\n- evidence\n- detail\n\n") * 3
UNGUARDED = "# BACKLOG\n\n### 🟡 Task\n- **Status:** In progress\n"


class BacklogGuardTests(unittest.TestCase):
    def assert_skip(self, filename: str, text: str, expected: bool) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / filename
            path.write_text(text, encoding="utf-8")
            self.assertEqual(index.should_skip_markdown(path), expected)

    def test_displaced_guards_still_exclude_backlog(self):
        for marker in index.BACKLOG_CORRUPTION_GUARD_MARKERS:
            with self.subTest(marker=marker):
                text = PREPENDED_TASKS + UNGUARDED + "\n> **⚠️ " + marker + "**\n"
                self.assertGreater(next(i for i, line in enumerate(text.splitlines(), 1) if marker in line), 12)
                self.assert_skip("BACKLOG.md", text, True)

    def test_preamble_guard_still_excludes_backlog(self):
        self.assert_skip("BACKLOG.md", "> DO NOT ACT ON THIS FILE\n" + UNGUARDED, True)

    def test_unguarded_backlog_is_eligible(self):
        self.assert_skip("BACKLOG.md", UNGUARDED, False)

    def test_other_markdown_is_not_excluded_by_backlog_warning(self):
        self.assert_skip("daily-note.md", PREPENDED_TASKS + "DO NOT ACT ON ENTRIES BELOW\n", False)

    def test_quoted_exact_guard_is_conservatively_excluded(self):
        self.assert_skip("BACKLOG.md", UNGUARDED + "\n- Historical warning: DO NOT ACT ON THIS FILE\n", True)


if __name__ == "__main__":
    unittest.main()
