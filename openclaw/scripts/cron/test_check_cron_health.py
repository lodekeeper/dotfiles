#!/usr/bin/env python3
"""Isolated CLI regressions; never read or update the live watchdog state."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(os.environ.get(
    'TEST_CRON_HEALTH_SCRIPT',
    str(Path(__file__).with_name('check_cron_health.py')),
)).resolve()


class CronHealthCliTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory()
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.jobs = self.root / 'jobs.json'
        self.state = self.root / 'state.json'
        self.probes = self.root / 'probe-calls'
        self.cadence = self.root / 'cadence.py'
        self.cadence.write_text(
            'from pathlib import Path\n'
            f'Path({str(self.probes)!r}).write_text("cadence probe executed")\n',
        )
        self.openclaw = self.root / 'openclaw'
        self.openclaw.write_text(
            '#!/usr/bin/env python3\n'
            'from pathlib import Path\n'
            f'Path({str(self.probes)!r}).write_text("openclaw probe executed")\n'
            'raise SystemExit(70)\n',
        )
        self.openclaw.chmod(0o700)
        self.env = {
            **os.environ,
            'CRON_JOBS_PATH': str(self.jobs),
            'CRON_HEALTH_STATE_PATH': str(self.state),
            'WORKSPACE_PATH': str(self.root),
            'OPENCLAW_BIN': str(self.openclaw),
            'AUTONOMY_CADENCE_SCRIPT': str(self.cadence),
            'AUTONOMY_CADENCE_FILE': str(self.root / 'audit.md'),
            'AUTONOMY_CADENCE_REFERENCE_DATE': '2026-10-20',
            'AUTONOMY_CADENCE_EXPECTED_EVERY_DAYS': '1',
        }

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env=self.env, cwd=self.root, text=True, capture_output=True,
            timeout=10, check=False,
        )

    def write_jobs(self, failing=False):
        self.jobs.write_text(json.dumps({'jobs': [{
            'id': 'fixture-job', 'name': 'fixture-job', 'enabled': True,
            'state': {
                'lastStatus': 'error' if failing else 'ok',
                'lastDeliveryStatus': 'not-requested',
                'consecutiveErrors': 1 if failing else 0,
                'lastRunAtMs': 1000, 'nextRunAtMs': 2000,
            },
        }]}))

    def check_non_operational_args(self, args, expected_code, existing_state):
        if existing_state:
            # A completed check would consume this pending recovery transition.
            self.state.write_text('{"activeFailures":{"old-job":{"id":"old-job"}},"updatedAtMs":1}\n')
            os.utime(self.state, ns=(1000000000, 1000000000))
            before = (self.state.read_bytes(), self.state.stat().st_mtime_ns)
        # Most callers omit jobs to trip the CLI fallback; valid-job callers
        # would reach the fake cadence probe and consume pending recoveries.
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, expected_code, result.stderr)
        self.assertFalse(self.probes.exists(), 'help/errors must not execute any probe')
        if existing_state:
            self.assertEqual((self.state.read_bytes(), self.state.stat().st_mtime_ns), before)
        else:
            self.assertFalse(self.state.exists(), 'help/errors must not create state')
        return result

    def test_help_preserves_existing_state_without_probes(self):
        for flag in ('-h', '--help'):
            with self.subTest(flag=flag):
                result = self.check_non_operational_args((flag,), 0, True)
                self.assertIn('usage:', result.stdout)
                self.assertIn('deduplication state', result.stdout)
                self.assertEqual(result.stderr, '')

    def test_help_does_not_create_missing_state(self):
        for flag in ('-h', '--help'):
            with self.subTest(flag=flag):
                self.check_non_operational_args((flag,), 0, False)

    def test_help_with_valid_jobs_keeps_pending_recovery(self):
        self.write_jobs()
        for flag in ('-h', '--help'):
            with self.subTest(flag=flag):
                self.check_non_operational_args((flag,), 0, True)

    def test_invalid_arguments_preserve_state_without_probes(self):
        for argument in ('--unknown-option', 'unexpected-positional'):
            with self.subTest(argument=argument):
                result = self.check_non_operational_args((argument,), 2, True)
                self.assertIn('unrecognized arguments:', result.stderr)
                self.assertEqual(result.stdout, '')

    def test_invalid_arguments_do_not_create_missing_state(self):
        for argument in ('--unknown-option', 'unexpected-positional'):
            with self.subTest(argument=argument):
                self.check_non_operational_args((argument,), 2, False)

    def test_no_arguments_preserve_failure_dedup_recovery_behavior(self):
        self.write_jobs(failing=True)
        failure = self.run_cli()
        self.assertEqual(failure.returncode, 0, failure.stderr)
        self.assertIn('detected 1 failing job(s)', failure.stdout)
        self.assertTrue(self.probes.exists(), 'normal checks must still execute probes')
        state = json.loads(self.state.read_text())
        self.assertEqual(set(state['activeFailures']), {'fixture-job'})
        self.assertEqual(state['activeFailures']['fixture-job']['consecutiveErrors'], 1)

        duplicate = self.run_cli()
        self.assertEqual(duplicate.returncode, 0, duplicate.stderr)
        self.assertEqual(duplicate.stdout.strip(), 'NO_REPLY')

        self.write_jobs(failing=False)
        recovery = self.run_cli()
        self.assertEqual(recovery.returncode, 0, recovery.stderr)
        self.assertIn('Recovered since last check: 1', recovery.stdout)
        self.assertEqual(json.loads(self.state.read_text())['activeFailures'], {})

        settled = self.run_cli()
        self.assertEqual(settled.returncode, 0, settled.stderr)
        self.assertEqual(settled.stdout.strip(), 'NO_REPLY')


if __name__ == '__main__':
    unittest.main()
