#!/usr/bin/env python3
"""Discussion ingestion must not turn malformed records into empty coverage."""
import base64
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch


SCRIPT = Path(os.environ.get("DISCUSSION_SCRIPT", Path(__file__).with_name("fetch-pr-discussion.py")))
SPEC = importlib.util.spec_from_file_location("fetch_pr_discussion", SCRIPT)
DISCUSSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DISCUSSION)
ENDPOINT = "repos/example/repo/pulls/1/comments"


def encoded(value):
    return base64.b64encode(json.dumps(value, ensure_ascii=False).encode()).decode()


def completed(stdout, returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class DiscussionIngestionTests(unittest.TestCase):
    def test_valid_unicode_objects_and_blank_lines_preserve_pagination(self):
        values = [{"id": 1, "body": "Hello 🌟"}, {"id": 2, "body": "second"}]
        stdout = "\n  " + encoded(values[0]) + "  \n\t\n" + encoded(values[1]) + "\n"
        with patch.object(DISCUSSION.subprocess, "run", return_value=completed(stdout)) as run:
            self.assertEqual(DISCUSSION.gh_items(ENDPOINT), values)
        self.assertEqual(run.call_args.args[0], ["gh", "api", "--paginate", ENDPOINT, "--jq", ".[] | @base64"])

    def test_empty_output_is_valid_empty_coverage(self):
        with patch.object(DISCUSSION.subprocess, "run", return_value=completed("\n \t\n")):
            self.assertEqual(DISCUSSION.gh_items(ENDPOINT), [])

    def test_malformed_records_fail_closed_without_echoing_content(self):
        valid = encoded({"body": "PRIVATE_COMMENT"})
        records = {
            "invalid_alphabet": valid[:4] + "!" + valid[4:],
            "invalid_padding": "a",
            "non_ascii_base64": "🌟PRIVATE_COMMENT",
            "invalid_utf8": base64.b64encode(b"\xffPRIVATE_COMMENT").decode(),
            "invalid_json": base64.b64encode(b"PRIVATE_COMMENT").decode(),
            "json_null": encoded(None),
            "json_array": encoded(["PRIVATE_COMMENT"]),
            "json_string": encoded("PRIVATE_COMMENT"),
            "json_number": encoded(42),
            "json_boolean": encoded(True),
        }
        for name, record in records.items():
            with self.subTest(name=name):
                stderr = io.StringIO()
                with patch.object(DISCUSSION.subprocess, "run", return_value=completed(record + "\n")):
                    with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                        DISCUSSION.gh_items(ENDPOINT)
                self.assertEqual(raised.exception.code, 1)
                self.assertEqual(stderr.getvalue(), f"ERROR: invalid discussion record from {ENDPOINT} at output line 1\n")

    def test_malformed_record_after_valid_item_reports_physical_line(self):
        stdout = "\n" + encoded({"id": 1}) + "\n \nINVALID!\n"
        stderr = io.StringIO()
        with patch.object(DISCUSSION.subprocess, "run", return_value=completed(stdout)):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                DISCUSSION.gh_items(ENDPOINT)
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(stderr.getvalue(), f"ERROR: invalid discussion record from {ENDPOINT} at output line 4\n")

    def test_github_command_error_still_fails(self):
        stderr = io.StringIO()
        with patch.object(DISCUSSION.subprocess, "run", return_value=completed("", 1, "API unavailable")):
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                DISCUSSION.gh_items(ENDPOINT)
        self.assertEqual(raised.exception.code, 1)
        self.assertIn(f"ERROR: failed to fetch {ENDPOINT}", stderr.getvalue())
        self.assertIn("API unavailable", stderr.getvalue())

    def test_cli_emits_no_partial_report_when_later_surface_is_invalid(self):
        for output_format in ([], ["--json"]):
            with self.subTest(output_format=output_format):
                stdout, stderr = io.StringIO(), io.StringIO()
                responses = [completed(encoded({"id": 1, "body": "PRIVATE_COMMENT"})), completed("INVALID!")]
                argv = [str(SCRIPT), "1", "--repo", "example/repo", "--skip-github-guard", *output_format]
                with patch.object(sys, "argv", argv), patch.object(DISCUSSION.shutil, "which", return_value="/mock/gh"):
                    with patch.object(DISCUSSION.subprocess, "run", side_effect=responses) as run:
                        with redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                            DISCUSSION.main()
                self.assertEqual(raised.exception.code, 1)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(run.call_count, 2)
                self.assertEqual(stderr.getvalue(), f"ERROR: invalid discussion record from {ENDPOINT} at output line 1\n")


if __name__ == "__main__":
    unittest.main()
