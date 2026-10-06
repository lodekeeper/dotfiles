#!/usr/bin/env python3
"""Regression coverage for read-only CI authorization diagnostics."""
from __future__ import annotations

import argparse
import importlib.util
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


probe = load_module("ci_rerun", "scripts/github/check-ci-rerun-capability.py")
domains = load_module("ci_domains", "scripts/notes/check-autonomy-domain-preflights.py")
renderer = load_module("ci_renderer", "scripts/notes/render-autonomy-domain-statuses.py")
health = load_module("ci_health", "scripts/notes/check-autonomy-preflight-health-drift.py")


def response(payload, returncode=0):
    return subprocess.CompletedProcess([], returncode, json.dumps(payload), "")


def repository(**overrides):
    return {"full_name": "ChainSafe/lodestar", "permissions": {
        "pull": True, "push": False, "maintain": False, "admin": False, **overrides,
    }}


class CiRerunTests(unittest.TestCase):
    def diagnose(self, repo_payload, actor="lodekeeper"):
        with patch.object(probe.shutil, "which", return_value="/bin/gh"), \
             patch.object(probe.subprocess, "run", side_effect=[
                 response({"login": actor}), response(repo_payload),
             ]) as run:
            result = probe.diagnose("ChainSafe/lodestar", "lodekeeper", 1)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertTrue(all(cmd[1:4] == ["api", "--method", "GET"] for cmd in commands))
            return result, commands

    def test_read_only_role_warns_without_blocking_local_fixes(self):
        result, commands = self.diagnose(repository())
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["rerunCapability"], "unavailable")
        self.assertIn("maintainer", result["warnings"][0])
        self.assertIn("fork PRs", result["warnings"][0])
        self.assertEqual([cmd[-1] for cmd in commands], ["user", "repos/ChainSafe/lodestar"])

    def test_write_roles_do_not_prove_actions_token_authorization(self):
        for role in ("push", "maintain", "admin"):
            with self.subTest(role=role):
                result, _ = self.diagnose(repository(**{role: True}))
                self.assertTrue(result["ok"])
                self.assertEqual(result["rerunCapability"], "not_established")
                self.assertEqual(result["status"], "unverified")
                self.assertIn("token-level Actions write", result["warnings"][0])

    def test_wrong_actor_stops_before_repository_lookup(self):
        result, commands = self.diagnose(repository(), actor="nflaig")
        self.assertFalse(result["ok"])
        self.assertEqual(result["rerunCapability"], "unknown")
        self.assertEqual(len(commands), 1)

    def test_missing_or_malformed_permissions_and_wrong_repo_fail_closed(self):
        cases = [[], {}, {"full_name": "other/repo", "permissions": repository()["permissions"]},
                 {"full_name": "ChainSafe/lodestar"}, repository(push="false"),
                 repository(push=1), repository(pull=False)]
        missing = repository()
        del missing["permissions"]["admin"]
        cases.append(missing)
        for payload in cases:
            with self.subTest(payload=payload):
                result, _ = self.diagnose(payload)
                self.assertFalse(result["ok"])
                self.assertEqual(result["rerunCapability"], "unknown")

    def test_api_failures_invalid_json_and_timeout_do_not_become_ready(self):
        cases = [response({}, 403), subprocess.CompletedProcess([], 0, "not-json", ""),
                 subprocess.TimeoutExpired(["gh"], 1), OSError("missing executable")]
        for failure in cases:
            with self.subTest(failure=failure), \
                 patch.object(probe.shutil, "which", return_value="/bin/gh"), \
                 patch.object(probe.subprocess, "run", side_effect=[failure]):
                result = probe.diagnose("ChainSafe/lodestar", "lodekeeper", 1)
                self.assertFalse(result["ok"])
                self.assertEqual(result["rerunCapability"], "unknown")
                self.assertTrue(result["error"])

    def test_missing_gh_does_not_issue_requests(self):
        with patch.object(probe.shutil, "which", return_value=None), \
             patch.object(probe.subprocess, "run") as run:
            self.assertFalse(probe.diagnose("ChainSafe/lodestar", "lodekeeper", 1)["ok"])
            run.assert_not_called()

    def test_invalid_arguments_do_not_issue_requests_even_when_gh_exists(self):
        with patch.object(probe.shutil, "which", return_value="/bin/gh"), \
             patch.object(probe.subprocess, "run") as run:
            for repo, actor, timeout in [("../user", "lodekeeper", 1),
                                         ("ChainSafe/..", "lodekeeper", 1),
                                         ("ChainSafe/lodestar", "", 1),
                                         ("ChainSafe/lodestar", "lodekeeper", 0)]:
                self.assertFalse(probe.diagnose(repo, actor, timeout)["ok"])
            run.assert_not_called()

    def test_permission_probe_is_required_in_ci_preflights(self):
        args = argparse.Namespace(strict_ci_api_key=False, require_devnet_grafana=False,
                                  expected_github_actor="lodekeeper", timeout_seconds=30)
        checks = domains.build_checks(args, WORKSPACE)
        self.assertEqual(sum(domain == "ciFix" and name == "githubCiRerunCapability"
                             for domain, name, *_ in checks), 1)
        self.assertIn("githubCiRerunCapability", renderer.EXPECTED_CHECKS["ciFix"])

    def test_rendering_preserves_restriction_and_detects_missing_probe(self):
        result, _ = self.diagnose(repository())
        checks = [{"domain": "ciFix", "name": name, "ok": True, "stdout": {"ok": True},
                   "warnings": []} for name in renderer.EXPECTED_CHECKS["ciFix"]]
        check = next(c for c in checks if c["name"] == "githubCiRerunCapability")
        check.update(stdout=result, warnings=result["warnings"])
        payload = {"ok": True, "selectedDomains": ["ciFix"], "checks": checks}
        status = renderer.render_statuses(payload)["CI fix"]
        self.assertIn("maintainer must rerun", status)
        self.assertNotIn("no new CI-fix blocker", status)
        checks.remove(check)
        self.assertTrue(renderer.render_statuses(payload)["CI fix"].startswith("BLOCKER:"))

    def test_permission_changes_survive_health_compaction(self):
        before, _ = self.diagnose(repository(push=True))
        after, _ = self.diagnose(repository(admin=True))
        self.assertEqual(before["status"], after["status"])
        self.assertEqual(before["warnings"], after["warnings"])
        self.assertNotEqual(health._compact_value(before), health._compact_value(after))
        compact = health._compact_value(before)
        self.assertEqual(compact["rerunCapability"], "not_established")
        self.assertTrue(compact["permissions"]["push"])


if __name__ == "__main__":
    unittest.main()
