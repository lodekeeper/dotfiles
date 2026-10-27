"""Report policy, fail-closed privacy, and read-only CLI regression coverage."""
import contextlib
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load("delivery_check", "check-report-delivery.py")
producer = load("delivery_producer", "health-check.py")
NOW = datetime(2026, 10, 27, 3, 16, tzinfo=timezone.utc)
CHECKED = NOW - timedelta(hours=20)
PRIVATE = "private-host:disk:198.51.100.44"


def issue(suffix="warn"):
    return {"key": PRIVATE + ":" + suffix, "sev": suffix, "host": "private-host", "msg": "secret report"}


def state(keys=(), ack=None):
    return {"reported_open": {key: {"host": "private-host", "msg": "secret"} for key in keys},
            "last_report_at": ack.isoformat() if ack is not None else None}


def latest(issues=(), checked=CHECKED):
    return {"issues": list(issues), "checked_at": checked.isoformat()}


class DeliveryTests(unittest.TestCase):
    def inspect(self, snapshot, previous):
        return check.inspect(snapshot, previous, now=NOW)

    def test_policy_matches_real_producer_without_network(self):
        # Execute the actual producer's main() against isolated fixtures; do not
        # duplicate its predicate as the expected oracle in this test.
        cases = [
            ([], state()),
            ([issue()], state()),
            ([issue()], state([issue()["key"]], CHECKED - timedelta(days=1))),
            ([], state([issue()["key"]], CHECKED - timedelta(days=20))),
            ([issue()], state([issue("crit")["key"]], CHECKED - timedelta(days=1))),
            ([issue("crit")], state([issue()["key"]], CHECKED - timedelta(days=1))),
            ([issue()], state([issue()["key"]], CHECKED - timedelta(days=7))),
            ([issue()], state([issue()["key"]], CHECKED - timedelta(days=7, microseconds=1))),
            ([issue()], state([issue()["key"]], CHECKED)),
            ([], state([], CHECKED)),
        ]
        class Clock:
            @classmethod
            def now(cls, tz):
                return CHECKED

            fromisoformat = staticmethod(datetime.fromisoformat)

        for issues, previous in cases:
            with self.subTest(issues=issues, ack=previous["last_report_at"]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "state.json").write_text(json.dumps(previous))
                output = io.StringIO()
                with patch.object(producer, "STATE_DIR", root), patch.object(producer.sys, "argv", ["health-check.py"]), \
                     patch.object(producer, "load_inventory", return_value=[]), \
                     patch.object(producer, "probe", side_effect=AssertionError("network forbidden")), \
                     patch.object(producer, "evaluate", return_value=(issues, {})), \
                     patch.object(producer.dt, "datetime", Clock), contextlib.redirect_stdout(output):
                    producer.main()
                actual = self.inspect(json.loads((root / "latest.json").read_text()), previous)
                self.assertEqual(actual["reportDue"], not output.getvalue().startswith("NO_REPORT"))
                self.assertFalse(actual["receiptVerified"])

    def test_pending_and_stale_both_preserved(self):
        result = self.inspect(latest([issue()], NOW - timedelta(hours=31)), state())
        self.assertEqual(result["status"], "stale_snapshot")
        self.assertTrue(result["reportDue"])
        self.assertFalse(result["snapshotFresh"])

    def test_newer_snapshot_not_automatically_pending(self):
        result = self.inspect(latest(), state([], CHECKED - timedelta(days=40)))
        self.assertEqual(result["status"], "no_report_due")
        self.assertTrue(result["ok"])

    def test_freshness_boundary(self):
        for hours, fresh in ((30, True), (30.001, False)):
            with self.subTest(hours=hours):
                self.assertEqual(self.inspect(latest(checked=NOW - timedelta(hours=hours)), state())["snapshotFresh"], fresh)

    def test_inconsistent_timestamps_and_equal_ack_key_mismatch(self):
        cases = [(latest(checked=NOW + timedelta(seconds=1)), state()),
                 (latest(), state([], CHECKED + timedelta(seconds=1))),
                 (latest([issue()]), state([], CHECKED)),
                 (latest(), state([issue()["key"]]))]
        for snapshot, previous in cases:
            with self.subTest(snapshot=snapshot), self.assertRaises(check.EvidenceError):
                self.inspect(snapshot, previous)

    def test_malformed_evidence_never_green(self):
        cases = [(None, state()), (latest(), []), ({}, state()),
                 (latest(), {}), (latest([issue(), issue()]), state()),
                 (latest([None]), state()), (latest([dict(issue(), sev="crit")]), state()),
                 (dict(latest(), checked_at="secret"), state()),
                 (dict(latest(), checked_at=CHECKED.replace(tzinfo=None).isoformat()), state()),
                 (latest(), dict(state(), reported_open=[]))]
        for snapshot, previous in cases:
            with self.subTest(snapshot=snapshot), self.assertRaises(check.EvidenceError):
                self.inspect(snapshot, previous)

    def test_cli_read_only_private_and_exit_codes(self):
        for issues, previous, expected in [([], state(), 0), ([issue()], state(), 1), ([], {}, 2)]:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "latest.json").write_text(json.dumps(latest(issues, datetime.now(timezone.utc))))
                (root / "state.json").write_text(json.dumps(previous))
                before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.iterdir()}
                result = subprocess.run(["python3", str(ROOT / "check-report-delivery.py"), "--state-dir", directory],
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.iterdir()})
                self.assertNotIn(PRIVATE, result.stdout + result.stderr)
                self.assertNotIn("secret", result.stdout + result.stderr)
                json.loads(result.stdout)

    def test_missing_state_first_run_and_unknown_inputs_create_nothing(self):
        for content, code in [(json.dumps(latest([], datetime.now(timezone.utc))), 0),
                              (json.dumps(latest([issue()], datetime.now(timezone.utc))), 1),
                              ('{"secret":1,"secret":2}', 2), ("not JSON secret", 2), (None, 2)]:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if content is not None:
                    (root / "latest.json").write_text(content)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(check.main(["--state-dir", directory]), code)
                self.assertFalse((root / "state.json").exists())
                self.assertNotIn("secret", output.getvalue())
                if code < 2:
                    self.assertFalse(json.loads(output.getvalue())["statePresent"])


if __name__ == "__main__":
    unittest.main()
