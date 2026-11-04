"""Offline CLI regressions for raw job-log recovery; no GitHub calls."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


SCRIPT = Path(__file__).with_name("fetch-run-logs.sh")


class FetchRunLogsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = self.root / "calls.jsonl"
        self.output = self.root / "logs.txt"
        self.output.write_text("previous useful evidence\n")
        state = self.root / "access.json"
        state.write_text(json.dumps({"status": "ok", "checked_at_epoch": int(time.time())}))
        self.env = dict(os.environ, PATH=f"{self.root}:{os.environ['PATH']}",
                        GITHUB_ACCESS_STATE_FILE=str(state),
                        GITHUB_ACCESS_MAX_AGE_MINUTES="10", TEST_CALLS=str(self.calls))
        fake = self.root / "gh"
        fake.write_text('''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["TEST_CALLS"], "a") as f:
    f.write(json.dumps(args) + "\\n")
if args[0] == "run":
    if "--log-failed" in args and os.environ.get("TEST_FORMATTED_FAIL"):
        print("formatted fetch failed", file=sys.stderr)
        sys.exit(1)
    print("53-line formatted excerpt" if "--log-failed" in args else "run fallback")
elif args == ["api", "repos/ChainSafe/lodestar/actions/jobs/200"]:
    if os.environ.get("TEST_METADATA_FAIL"):
        print("metadata unavailable", file=sys.stderr)
        sys.exit(1)
    print(os.environ.get("TEST_METADATA", '{"id":200,"run_id":100,"status":"completed"}'))
elif args == ["api", "repos/ChainSafe/lodestar/actions/jobs/200/logs"]:
    if os.environ.get("TEST_DOWNLOAD_FAIL"):
        print("partial download")
        print("download interrupted", file=sys.stderr)
        sys.exit(1)
    if not os.environ.get("TEST_EMPTY"):
        print("raw job start\\nkeymanager EADDRINUSE\\njob end")
else:
    print("unexpected gh call", args, file=sys.stderr)
    sys.exit(99)
''')
        fake.chmod(0o755)

    def run_cli(self, *args, **env):
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=self.root,
                              env=dict(self.env, **env), capture_output=True, text=True)

    def recover(self, **env):
        return self.run_cli("100", "--job-id", "200", "--output", str(self.output), **env)

    def recorded(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_short_success_can_be_recovered_explicitly(self):
        formatted = self.run_cli("100", "--output", str(self.output))
        self.assertEqual(formatted.returncode, 0, formatted.stderr)
        self.assertIn("--job-id", formatted.stdout)
        self.assertNotIn("EADDRINUSE", self.output.read_text())
        recovered = self.recover()
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertIn("keymanager EADDRINUSE", self.output.read_text())
        self.assertIn("Job scope only", recovered.stdout)
        self.assertIn("does not establish completeness", recovered.stdout)
        self.assertEqual(json.loads(Path(str(self.output) + ".job.json").read_text())["run_id"], 100)
        self.assertTrue(Path(str(self.output) + ".err").exists())

    def test_wrong_run_id_job_id_and_incomplete_metadata_are_rejected_before_download(self):
        for job in [{"id": 200, "run_id": 101, "status": "completed"},
                    {"id": 201, "run_id": 100, "status": "completed"},
                    {"id": 200, "run_id": 100, "status": "in_progress"},
                    {"id": 200, "run_id": 100}, [], "invalid json"]:
            with self.subTest(job=job):
                text = job if isinstance(job, str) else json.dumps(job)
                result = self.recover(TEST_METADATA=text)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.output.read_text(), "previous useful evidence\n")
                self.assertFalse(any(call[-1].endswith("/logs") for call in self.recorded()))

    def test_metadata_api_failure_preserves_output(self):
        result = self.recover(TEST_METADATA_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(), "previous useful evidence\n")
        self.assertFalse(any(call[-1].endswith("/logs") for call in self.recorded()))
        self.assertIn("metadata unavailable", Path(str(self.output) + ".err").read_text())

    def test_partial_failed_download_preserves_output_and_diagnostics(self):
        result = self.recover(TEST_DOWNLOAD_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(), "previous useful evidence\n")
        self.assertIn("partial download", Path(str(self.output) + ".job-200.download").read_text())
        self.assertIn("download interrupted", Path(str(self.output) + ".err").read_text())

    def test_empty_download_preserves_output(self):
        result = self.recover(TEST_EMPTY="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(), "previous useful evidence\n")

    def test_default_path_is_job_specific(self):
        result = self.run_cli("100", "--job-id", "200")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "tmp/ci-logs/run-100-job-200.log").is_file())

    def test_directory_output_is_rejected_without_success_or_mutation(self):
        directory = self.root / "existing-dir"
        directory.mkdir()
        marker = directory / "keep.txt"
        marker.write_text("unrelated content")
        result = self.run_cli("100", "--job-id", "200", "--output", str(directory))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Saved raw-job logs", result.stdout)
        self.assertEqual(list(directory.iterdir()), [marker])
        self.assertEqual(marker.read_text(), "unrelated content")
        self.assertEqual(self.recorded(), [])

    def test_legacy_failure_still_falls_back(self):
        result = self.run_cli("100", "--output", str(self.output), TEST_FORMATTED_FAIL="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_text(), "run fallback\n")

    def test_invalid_options_do_not_call_github(self):
        for args in [("100", "--job-id"), ("100", "--job-id", "bad"),
                     ("bad", "--job-id", "200"), ("100", "--repo"), ("100", "--output")]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_cli(*args).returncode, 0)
                self.assertEqual(self.recorded(), [])

    def test_preflight_stays_offline(self):
        result = self.run_cli("--check-only", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])
        self.assertEqual(self.recorded(), [])


if __name__ == "__main__":
    unittest.main()
