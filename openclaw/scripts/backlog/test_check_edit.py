#!/usr/bin/env python3
"""Regressions for lost recovery banners during backlog archival/replacement."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

from check_edit import check_edit
from list_statuses import CORRUPTION_GUARD_MARKERS


BANNER = "> **⚠️ DO NOT ACT ON ENTRIES BELOW WITHOUT VERIFYING FIRST.** Verify against live evidence."
TASK = "\n### Task\n- **Status:** In progress\n"


class CheckEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.before = Path(self.tmp.name) / "before.md"
        self.after = Path(self.tmp.name) / "after.md"

    def pair(self, before: str, after: str) -> dict:
        self.before.write_text(before, encoding="utf-8")
        self.after.write_text(after, encoding="utf-8")
        original = self.before.read_bytes()
        proposed = self.after.read_bytes()
        result = check_edit(self.before, self.after)
        self.assertEqual(self.before.read_bytes(), original)
        self.assertEqual(self.after.read_bytes(), proposed)
        return result

    def test_archived_banner_is_rejected_for_each_marker(self):
        for marker in CORRUPTION_GUARD_MARKERS:
            with self.subTest(marker=marker):
                result = self.pair(f"> {marker}\n" + TASK, TASK)
                self.assertFalse(result["ok"])
                self.assertEqual(result["missingMarkers"], [marker])

    def test_wording_change_with_marker_retained_is_rejected(self):
        result = self.pair(BANNER + TASK, BANNER.replace("Verify", "Ignore") + TASK)
        self.assertFalse(result["ok"])
        self.assertEqual(result["missingGuardLines"], 1)

    def test_status_update_and_displaced_banner_pass(self):
        result = self.pair(BANNER + TASK, "\n" * 25 + TASK.replace("In progress", "Done") + BANNER)
        self.assertTrue(result["ok"])

    def test_duplicate_line_loss_is_rejected(self):
        result = self.pair(BANNER + "\n" + BANNER + TASK, BANNER + TASK)
        self.assertFalse(result["ok"])
        self.assertEqual(result["missingGuardLines"], 1)

    def test_guard_free_baseline_and_new_guard_pass(self):
        self.assertTrue(self.pair(TASK, TASK.replace("In progress", "Done"))["ok"])
        self.assertTrue(self.pair(TASK, BANNER + TASK)["ok"])

    def test_unrelated_guard_cannot_replace_original(self):
        self.assertFalse(self.pair(BANNER + TASK, "> DO NOT ACT ON THIS FILE\n" + TASK)["ok"])

    def test_same_path_symlink_and_hardlink_are_rejected(self):
        self.before.write_text(BANNER, encoding="utf-8")
        self.after.symlink_to(self.before)
        hardlink = Path(self.tmp.name) / "hardlink.md"
        os.link(self.before, hardlink)
        for alias in (self.before, self.after, hardlink):
            with self.subTest(alias=alias):
                self.assertIn("error", check_edit(self.before, alias))

    def test_missing_directory_and_invalid_utf8_fail_cleanly(self):
        self.before.write_text(BANNER, encoding="utf-8")
        self.assertFalse(check_edit(self.before, self.after)["ok"])
        self.assertFalse(check_edit(self.before, Path(self.tmp.name))["ok"])
        self.after.write_bytes(b"\xff")
        self.assertIn("error", check_edit(self.before, self.after))

    def test_cli_json_exit_codes_without_task_content(self):
        for text, code in ((BANNER + TASK, 0), (TASK, 2)):
            self.pair(BANNER + TASK, text)
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("check_edit.py")),
                 "--before", str(self.before), "--after", str(self.after), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, code)
            self.assertEqual(json.loads(proc.stdout)["ok"], code == 0)
            self.assertNotIn("Status", proc.stdout)
            self.assertEqual(proc.stderr, "")


if __name__ == "__main__":
    unittest.main()
