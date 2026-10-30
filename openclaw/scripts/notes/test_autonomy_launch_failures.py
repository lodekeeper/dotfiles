"""Keep prerequisite launch failures from suppressing the remaining audit evidence."""
from contextlib import redirect_stdout
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


WORKSPACE = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "launch_failure_domains", WORKSPACE / "scripts/notes/check-autonomy-domain-preflights.py"
)
domains = importlib.util.module_from_spec(spec)
spec.loader.exec_module(domains)


class LaunchFailureTests(unittest.TestCase):
    def run_check(self, command, **kwargs):
        return domains.run_check(
            workspace=WORKSPACE, domain="prReview", name="launchProbe",
            command=command, env=os.environ.copy(), timeout_s=5, **kwargs
        )

    def test_missing_executable_is_a_failed_prerequisite(self):
        command = ["/nonexistent-autonomy-preflight-executable"]
        result = self.run_check(command, warnings=["existing advisory"])
        self.assertFalse(result["ok"])
        self.assertIsNone(result["returnCode"])
        self.assertIsNone(result["stdout"])
        self.assertEqual(result["command"], command)
        self.assertEqual((result["domain"], result["name"]), ("prReview", "launchProbe"))
        self.assertEqual(result["warnings"], ["existing advisory"])
        self.assertIn("FileNotFoundError", result["stderr"])

    def test_permission_failure_is_bounded_and_does_not_dump_environment(self):
        error = PermissionError(errno.EACCES, "denied " * 1000)
        with patch.object(domains.subprocess, "run", side_effect=error), \
             patch.dict(os.environ, {"AUTONOMY_TEST_SECRET": "must-not-appear"}):
            result = self.run_check(["permission-probe"])
        self.assertFalse(result["ok"])
        self.assertIsNone(result["returnCode"])
        self.assertIn("PermissionError", result["stderr"])
        self.assertLess(len(result["stderr"]), 4100)
        self.assertNotIn("must-not-appear", json.dumps(result))

    def test_main_collects_later_checks_and_emits_failure_json(self):
        checks = [
            ("prReview", "missing", ["/nonexistent-autonomy-preflight-executable"], os.environ.copy(), []),
            ("ciFix", "later", [sys.executable, "-c", 'print(\'{"ok": true}\')'], os.environ.copy(), []),
        ]
        output = io.StringIO()
        with patch.object(domains, "build_checks", return_value=checks), \
             patch.object(sys, "argv", ["preflight", "--json"]), redirect_stdout(output):
            self.assertEqual(domains.main(), 2)
        result = json.loads(output.getvalue())
        self.assertFalse(result["ok"])
        self.assertEqual([check["ok"] for check in result["checks"]], [False, True])
        self.assertEqual(result["checks"][1]["stdout"], {"ok": True})
        self.assertEqual(result["cacheStats"]["uniqueCommands"], 2)

    def test_unexpected_programming_errors_are_not_suppressed(self):
        with patch.object(domains.subprocess, "run", side_effect=ValueError("invalid invocation")):
            with self.assertRaisesRegex(ValueError, "invalid invocation"):
                self.run_check(["programming-error-probe"])


if __name__ == "__main__":
    unittest.main()
