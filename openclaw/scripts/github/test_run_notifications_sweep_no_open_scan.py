#!/usr/bin/env python3
"""Offline CLI regressions: help/invalid arguments must never start a sweep."""

import builtins
import contextlib
import io
import os
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch


WRAPPER = Path(os.environ.get(
    "NOTIFICATION_SWEEP_WRAPPER_UNDER_TEST",
    Path(__file__).with_name("run_notifications_sweep_no_open_scan.py"),
))
SCANNER = "github_notifications_sweep"


class WrapperCliTests(unittest.TestCase):
    def run_wrapper(self, arguments):
        scanner = types.ModuleType(SCANNER)
        calls = []
        imports = []
        real_import = builtins.__import__

        def record_import(name, *args, **kwargs):
            if name == SCANNER:
                imports.append(name)
            return real_import(name, *args, **kwargs)

        def sweep():
            calls.append({
                "argv": list(sys.argv),
                "openPrScan": scanner.scan_open_prs_for_unreplied({}, {}),
            })
            return 37

        scanner.main = sweep
        scanner.scan_open_prs_for_unreplied = lambda *_: ["must be disabled"]
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(sys.modules, {SCANNER: scanner}), \
                patch.object(sys, "argv", [str(WRAPPER), *arguments]), \
                patch.object(sys, "path", list(sys.path)), \
                patch.object(builtins, "__import__", side_effect=record_import), \
                contextlib.redirect_stdout(stdout), \
                contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as stopped:
                runpy.run_path(str(WRAPPER), run_name="__main__")
        return stopped.exception.code, stdout.getvalue(), stderr.getvalue(), imports, calls

    def test_help_exits_without_importing_or_executing_scanner(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                code, stdout, stderr, imports, calls = self.run_wrapper([flag])
                self.assertEqual(code, 0)
                self.assertIn("usage:", stdout)
                self.assertEqual(stderr, "")
                self.assertEqual(imports, [])
                self.assertEqual(calls, [])

    def test_invalid_arguments_fail_before_scanner_import(self):
        for arguments in (["--typo"], ["unexpected"], ["--state", "/unused/state.json"]):
            with self.subTest(arguments=arguments):
                code, stdout, stderr, imports, calls = self.run_wrapper(arguments)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertIn("unrecognized arguments:", stderr)
                self.assertEqual(imports, [])
                self.assertEqual(calls, [])

    def test_zero_arguments_preserve_fixed_sweep_and_exit_status(self):
        code, stdout, stderr, imports, calls = self.run_wrapper([])
        self.assertEqual(code, 37)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(imports, [SCANNER])
        self.assertEqual(calls, [{
            "argv": [
                "github_notifications_sweep.py",
                "--state", "/home/openclaw/gh-notif-state.json",
                "--checklist", "/home/openclaw/gh-notif-checklist.json",
                "--backlog", "/home/openclaw/.openclaw/workspace/BACKLOG.md",
            ],
            "openPrScan": [],
        }])


if __name__ == "__main__":
    unittest.main()
