#!/usr/bin/env python3
"""Regression checks for fallback availability and visible audit degradation."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


WORKSPACE = Path(__file__).resolve().parents[2]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, WORKSPACE / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


memory = load_module("memory_readiness", "scripts/memory/check_context_search_readiness.py")
domains = load_module("domain_preflights", "scripts/notes/check-autonomy-domain-preflights.py")
renderer = load_module("domain_statuses", "scripts/notes/render-autonomy-domain-statuses.py")
health = load_module("domain_health", "scripts/notes/check-autonomy-preflight-health-drift.py")


class MemoryFallbackTests(unittest.TestCase):
    def test_backend_availability_matrix(self):
        cases = [
            (True, True, "ready", "qmd", 0),
            (False, True, "degraded", "sqlite", 0),
            (True, False, "degraded", "qmd", 0),
            (False, False, "blocked", None, 2),
        ]
        for qmd_ok, fallback_ok, status, backend, exit_code in cases:
            with self.subTest(qmd=qmd_ok, fallback=fallback_ok):
                output = io.StringIO()
                with patch.object(memory, "_check_qmd", return_value={"searchOk": qmd_ok}), \
                     patch.object(memory, "_check_fallback", return_value={"searchOk": fallback_ok}), \
                     patch("sys.argv", ["readiness", "--json"]), \
                     redirect_stdout(output), redirect_stderr(io.StringIO()):
                    self.assertEqual(memory.main(), exit_code)
                payload = json.loads(output.getvalue())
                self.assertEqual(payload["status"], status)
                self.assertEqual(payload["selectedBackend"], backend)
                self.assertEqual(bool(payload["warnings"]), status == "degraded")

    def check_qmd_result(self, result):
        with patch.object(memory.shutil, "which", return_value="/bin/qmd"), \
             patch.object(memory, "_run", return_value=result):
            return memory._check_qmd(workspace=WORKSPACE, query="autonomy", timeout_s=1)

    def test_signal_diagnostics_do_not_become_parse_errors_or_drift_noise(self):
        result = {"returnCode": -6, "stdout": "", "stderr": "assertion at 0x1234", "timedOut": False}
        first = self.check_qmd_result(result)
        self.assertFalse(first["searchOk"])
        self.assertIn("SIGABRT", first["error"])
        self.assertEqual(first["stderr"], result["stderr"])
        second = self.check_qmd_result({**result, "stderr": "assertion at 0x5678"})
        self.assertEqual(health._compact_value(first), health._compact_value(second))

    def test_timeout_malformed_json_and_empty_results_fail(self):
        cases = [
            (None, "", True, "timed out"),
            (0, "not json", False, "could not parse"),
            (0, "[]", False, "no search results"),
            (1, '[{"file":"memory.md"}]', False, "returnCode=1"),
        ]
        for return_code, stdout, timed_out, error in cases:
            with self.subTest(error=error):
                result = self.check_qmd_result({"returnCode": return_code, "stdout": stdout,
                                                "stderr": "", "timedOut": timed_out})
                self.assertFalse(result["searchOk"])
                self.assertIn(error, result["error"])

    def test_warnings_survive_cached_checks(self):
        payload = {"ok": True, "status": "degraded", "warnings": ["QMD unavailable", "QMD unavailable"]}
        proc = subprocess.CompletedProcess(["probe"], 0, json.dumps(payload), "")
        cache = {}
        with patch.object(domains.subprocess, "run", return_value=proc) as run:
            for domain in domains.VALID_DOMAINS:
                result = domains.cached_check_result(cache=cache, workspace=WORKSPACE,
                    domain=domain, name="memoryContextSearch", command=["probe"], env={},
                    timeout_s=1, warnings=["configured warning"])
                self.assertEqual(result["warnings"], ["configured warning", "QMD unavailable"])
            self.assertEqual(run.call_count, 1)

    def domain_payload(self):
        return {"ok": True, "checks": [
            {"domain": domain, "name": name, "ok": True, "returnCode": 0,
             "stdout": {"ok": True}, "warnings": ["QMD unavailable; degraded memory search"]
             if name == "memoryContextSearch" else []}
            for domain, names in renderer.EXPECTED_CHECKS.items() for name in names
        ]}

    def test_every_domain_renders_warnings_even_with_unrelated_blockers(self):
        payload = self.domain_payload()
        for status in renderer.render_statuses(payload).values():
            self.assertIn("QMD unavailable; degraded memory search", status)
        payload["checks"][0]["ok"] = False
        status = renderer.render_statuses(payload)["PR review"]
        self.assertTrue(status.startswith("BLOCKER:"))
        self.assertIn("QMD unavailable; degraded memory search", status)

    def test_backend_recovery_and_switch_are_health_drift(self):
        payload = self.domain_payload()
        check = next(c for c in payload["checks"] if c["name"] == "memoryContextSearch")
        check["stdout"].update(status="degraded", selectedBackend="sqlite",
                                qmd={"searchOk": False, "returnCode": -6, "timedOut": False})
        first = health.build_signature(payload)
        self.assertFalse(health.diff_signatures(first, health.build_signature(payload))["hasDrift"])
        check["stdout"]["selectedBackend"] = "qmd"
        self.assertTrue(health.diff_signatures(first, health.build_signature(payload))["hasDrift"])
        check["stdout"].update(status="ready", qmd={"searchOk": True, "returnCode": 0, "timedOut": False})
        check["warnings"] = []
        self.assertTrue(health.diff_signatures(first, health.build_signature(payload))["hasDrift"])


if __name__ == "__main__":
    unittest.main()
