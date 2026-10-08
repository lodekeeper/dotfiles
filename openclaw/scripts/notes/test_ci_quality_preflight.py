#!/usr/bin/env python3
"""Regression coverage for honest CI credential prerequisites in daily audits."""
import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


WORKSPACE = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, WORKSPACE / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


domains = load_module("quality_domains", "scripts/notes/check-autonomy-domain-preflights.py")
renderer = load_module("quality_renderer", "scripts/notes/render-autonomy-domain-statuses.py")
quality = load_module("quality_probe", "scripts/ci/check_fix_quality.py")


class CiCredentialPreflightTests(unittest.TestCase):
    def build_quality_check(self, env, strict=False):
        args = argparse.Namespace(strict_ci_api_key=strict, require_devnet_grafana=False,
                                  expected_github_actor="lodekeeper", timeout_seconds=30)
        with patch.dict(domains.os.environ, env, clear=True):
            return next(check for check in domains.build_checks(args, WORKSPACE)
                        if check[:2] == ("ciFix", "fixQualityGate"))

    def test_missing_key_is_not_fabricated_even_for_legacy_non_strict_callers(self):
        for strict in (False, True):
            with self.subTest(strict=strict):
                _, _, _, env, warnings = self.build_quality_check({"PATH": "/bin"}, strict)
                self.assertNotIn("OPENAI_API_KEY", env)
                self.assertEqual(env, {"PATH": "/bin"})
                self.assertIn("gateway_exec", warnings[0])
                self.assertIn("does not establish", warnings[0])

    def test_inherited_environment_is_unchanged_and_key_is_not_reported(self):
        inherited = {"PATH": "/bin", "OPENAI_API_KEY": "test-credential-presence-only"}
        _, _, command, env, warnings = self.build_quality_check(inherited)
        self.assertEqual(env, inherited)
        self.assertEqual(warnings, [])
        self.assertNotIn(inherited["OPENAI_API_KEY"], json.dumps([command, warnings]))

    def run_quality_preflight(self, env):
        domain, name, command, check_env, warnings = self.build_quality_check(env)

        def probe(*args, **kwargs):
            with patch.dict(quality.os.environ, kwargs["env"], clear=True), \
                 patch.object(quality.importlib.util, "find_spec", return_value=object()):
                payload = quality.check_environment()
            return subprocess.CompletedProcess(command, 0 if payload["ok"] else 1,
                                               json.dumps(payload), "")

        with patch.object(domains.subprocess, "run", side_effect=probe):
            return domains.run_check(workspace=WORKSPACE, domain=domain, name=name,
                                     command=command, env=check_env, warnings=warnings,
                                     timeout_s=1)

    def test_native_absence_fails_while_existing_gateway_prerequisites_pass(self):
        native = self.run_quality_preflight({})
        self.assertFalse(native["ok"])
        self.assertEqual(native["returnCode"], 1)
        self.assertEqual(native["stdout"]["checks"],
                         {"openaiApiKey": False, "openaiPackage": True})
        inherited = self.run_quality_preflight({"OPENAI_API_KEY": "test-presence-only"})
        self.assertTrue(inherited["ok"])
        self.assertNotIn("test-presence-only", json.dumps(inherited))

    def render_ci(self, *, key=True, package=True):
        checks = [{"domain": "ciFix", "name": name, "ok": True,
                   "stdout": {"ok": True}, "warnings": []}
                  for name in renderer.EXPECTED_CHECKS["ciFix"]]
        quality_check = next(check for check in checks if check["name"] == "fixQualityGate")
        quality_check.update(ok=key and package, stdout={"ok": key and package,
            "checks": {"openaiApiKey": key, "openaiPackage": package}})
        return renderer.render_statuses({"selectedDomains": ["ciFix"], "checks": checks})["CI fix"]

    def test_key_only_failure_is_runtime_scoped_and_package_failures_stay_visible(self):
        native = self.render_ci(key=False)
        self.assertTrue(native.startswith("BLOCKER:"))
        self.assertIn("gateway_exec", native)
        self.assertIn("native-shell key absence is not proof", native)
        for key in (False, True):
            with self.subTest(key=key):
                status = self.render_ci(key=key, package=False)
                self.assertTrue(status.startswith("BLOCKER:"))
                self.assertIn("Python OpenAI package prerequisite", status)

    def test_success_does_not_claim_live_model_or_credential_validity(self):
        status = self.render_ci()
        self.assertIn("existing credential presence/package discovery only", status)
        self.assertIn("no live model request", status)

    def test_default_and_compatibility_flag_always_emit_strict_semantics(self):
        results = []
        for flags in ([], ["--strict-ci-api-key"]):
            output = io.StringIO()
            with patch("sys.argv", ["preflight", "--json", *flags]), \
                 patch.object(domains, "build_checks", return_value=[]) as build, \
                 redirect_stdout(output):
                self.assertEqual(domains.main(), 0)
            self.assertTrue(build.call_args.args[0].strict_ci_api_key)
            results.append(json.loads(output.getvalue()))
        self.assertTrue(results[0]["strictCiApiKey"])
        self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()
