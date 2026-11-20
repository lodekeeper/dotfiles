#!/usr/bin/env python3
"""Regression coverage for read-only PR CI evidence reconciliation."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


WORKSPACE = Path(__file__).resolve().parents[2]
SHA = "feae3c50b9cd7b332357cc2e26eb21fd5abeb9f0"
OTHER_SHA = "86246d2d0540000000000000000000000000abcd"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, WORKSPACE / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evidence = load_module("pr_ci_evidence", "scripts/github/check-pr-ci-evidence.py")


def run(run_id, name, conclusion, status="completed", event="pull_request", workflow_id=None, prs=()):
    return {"id": run_id, "workflow_id": workflow_id or name, "name": name, "event": event,
            "status": status, "conclusion": conclusion, "run_attempt": 1, "check_suite_id": 1000 + run_id,
            "pull_requests": [{"number": n} for n in prs], "html_url": f"https://example.test/runs/{run_id}"}


def check(check_id, name, conclusion, *, suite, status="completed", app="github-actions"):
    return {"id": check_id, "name": name, "status": status, "conclusion": conclusion,
            "check_suite": {"id": suite}, "app": {"slug": app},
            "html_url": f"https://example.test/checks/{check_id}"}


def ext_check(check_id, name, conclusion, status="completed"):
    return check(check_id, name, conclusion, suite=5000 + check_id, status=status, app="external-ci")


class FakeGh:
    def __init__(self, runs=(), checks=(), statuses=(), heads=(SHA, SHA), fail_endpoint=None,
                 page_size=None, raw=None, stderr="boom"):
        self.runs = list(runs)
        self.checks = list(checks)
        self.statuses = list(statuses)
        self.heads = list(heads)
        self.fail_endpoint = fail_endpoint
        self.page_size = page_size
        self.raw = raw or {}
        self.stderr = stderr
        self.calls = []

    def page(self, key, items, endpoint):
        page = int(endpoint.rsplit("page=", 1)[1]) if "&page=" in endpoint else 1
        size = self.page_size or evidence.PER_PAGE
        return {"total_count": len(items), key: items[(page - 1) * size: page * size]}

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        endpoint = cmd[-1]
        if self.fail_endpoint and self.fail_endpoint in endpoint:
            return subprocess.CompletedProcess(cmd, 1, "", self.stderr)
        for fragment, stdout in self.raw.items():
            if fragment in endpoint:
                return subprocess.CompletedProcess(cmd, 0, stdout, "")
        if "/pulls/" in endpoint:
            payload = {"state": "open", "head": {"sha": self.heads.pop(0), "repo": {"full_name": "fork/lodestar"}}}
        elif "/actions/runs" in endpoint:
            payload = self.page("workflow_runs", self.runs, endpoint)
        elif "/check-runs" in endpoint:
            payload = self.page("check_runs", self.checks, endpoint)
        elif endpoint.split("?")[0].endswith("/status"):
            payload = self.page("statuses", self.statuses, endpoint)
        else:
            raise AssertionError(f"unexpected endpoint {endpoint}")
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")


def invoke(fake, argv=("--repo", "ChainSafe/lodestar", "--pr", "10460")):
    out = io.StringIO()
    with patch.object(evidence.shutil, "which", return_value="/usr/bin/gh"), \
            patch.object(evidence.subprocess, "run", side_effect=fake), \
            contextlib.redirect_stdout(out):
        rc = evidence.main(list(argv))
    return rc, json.loads(out.getvalue())


def verdict(fake):
    return invoke(fake)[1]["verdict"]


class PrCiEvidenceTests(unittest.TestCase):
    def expect(self, fake, *names):
        argv = ["--repo", "ChainSafe/lodestar", "--pr", "10460"]
        for name in names:
            argv.extend(["--expect-workflow", name])
        return invoke(fake, argv)

    def test_missing_expected_workflow_overrides_unrelated_green_or_no_ci(self):
        for fake in (FakeGh(), FakeGh(runs=[run(1, "Unrelated", "success")]),
                     FakeGh(checks=[ext_check(1, "Tests", "success")]),
                     FakeGh(statuses=[{"context": "Tests", "state": "success"}])):
            with self.subTest(runs=fake.runs, checks=fake.checks, statuses=fake.statuses):
                rc, out = self.expect(fake, "Tests")
                self.assertEqual((rc, out["ok"], out["verdict"]), (0, True, "insufficient_coverage"))
                self.assertFalse(out["workflowCoverage"]["satisfied"])
                self.assertEqual(out["workflowCoverage"]["workflows"], [
                    {"name": "Tests", "satisfied": False, "reason": "missing", "latestRuns": []}])

    def test_all_exact_expected_names_are_required_and_duplicates_are_deduplicated(self):
        rc, out = self.expect(FakeGh(runs=[run(1, "Tests", "success"), run(2, "Interop", "success")]),
                              "Tests", "Interop", "Tests")
        self.assertEqual((rc, out["verdict"]), (0, "observed_green"))
        self.assertEqual(out["workflowCoverage"]["requested"], ["Tests", "Interop"])
        self.assertTrue(out["workflowCoverage"]["satisfied"])
        for expected in ("tests", "Tests ", "Missing"):
            with self.subTest(expected=expected):
                _, out = self.expect(FakeGh(runs=[run(1, "Tests", "success")]), "Tests", expected)
                self.assertEqual(out["verdict"], "insufficient_coverage")
                self.assertEqual([c["satisfied"] for c in out["workflowCoverage"]["workflows"]], [True, False])

    def test_skipped_or_neutral_expected_workflow_does_not_count_as_executed_success(self):
        for conclusion in ("skipped", "neutral"):
            with self.subTest(conclusion=conclusion):
                _, out = self.expect(FakeGh(runs=[run(1, "Tests", conclusion),
                                                  run(2, "Unrelated", "success")]), "Tests")
                self.assertEqual(out["verdict"], "insufficient_coverage")
                item = out["workflowCoverage"]["workflows"][0]
                self.assertEqual((item["satisfied"], item["reason"]), (False, "not_successful"))
                self.assertEqual(item["latestRuns"][0]["conclusion"], conclusion)

    def test_newer_skipped_run_cannot_borrow_old_success_for_explicit_coverage(self):
        runs = [run(1, "Tests", "success"), run(2, "Tests", "skipped")]
        self.assertEqual(verdict(FakeGh(runs=runs)), "observed_green", "default semantics remain unchanged")
        _, out = self.expect(FakeGh(runs=runs), "Tests")
        self.assertEqual(out["verdict"], "insufficient_coverage")
        self.assertEqual([r["id"] for r in out["workflowCoverage"]["workflows"][0]["latestRuns"]], [2])

    def test_successful_latest_rerun_satisfies_coverage(self):
        _, out = self.expect(FakeGh(runs=[run(1, "Tests", "failure"), run(2, "Tests", "success")]), "Tests")
        self.assertEqual(out["verdict"], "observed_green")
        item = out["workflowCoverage"]["workflows"][0]
        self.assertEqual((item["satisfied"], item["reason"]), (True, "success"))
        latest = item["latestRuns"][0]
        self.assertEqual((latest["id"], latest["workflowId"], latest["event"], latest["attempt"]),
                         (2, "Tests", "pull_request", 1))
        self.assertEqual(latest["url"], "https://example.test/runs/2")

    def test_non_ci_events_and_other_pr_runs_do_not_satisfy_expected_workflows(self):
        for runs in ([run(1, "Tests", "success", event="pull_request_target")],
                     [run(1, "Tests", "success", prs=(999,))]):
            with self.subTest(runs=runs):
                _, out = self.expect(FakeGh(runs=runs), "Tests")
                self.assertEqual(out["verdict"], "insufficient_coverage")
                self.assertEqual(out["workflowCoverage"]["workflows"][0]["reason"], "missing")

    def test_one_eligible_success_satisfies_name_despite_skipped_other_event(self):
        for event in evidence.CI_EVENTS:
            with self.subTest(event=event):
                other_event = "push" if event != "push" else "pull_request"
                _, out = self.expect(FakeGh(runs=[run(1, "Tests", "success", event=event),
                                                  run(2, "Tests", "skipped", event=other_event)]), "Tests")
                self.assertEqual(out["verdict"], "observed_green")
                self.assertTrue(out["workflowCoverage"]["satisfied"])

    def test_expected_coverage_does_not_override_existing_blocker_precedence(self):
        for conclusion, status, expected in (("failure", "completed", "failing"),
                                              ("action_required", "completed", "action_required"),
                                              (None, "in_progress", "pending"),
                                              ("cancelled", "completed", "cancelled")):
            with self.subTest(expected=expected):
                _, out = self.expect(FakeGh(runs=[run(1, "Tests", conclusion, status=status)]),
                                     "Tests", "Missing")
                self.assertEqual(out["verdict"], expected)
                self.assertFalse(out["workflowCoverage"]["satisfied"])

    def test_explicit_expectations_add_no_requests_and_use_only_get(self):
        plain, expected = FakeGh(runs=[run(1, "Tests", "success")]), FakeGh(runs=[run(1, "Tests", "success")])
        invoke(plain)
        self.expect(expected, "Tests", "Interop")
        self.assertEqual(plain.calls, expected.calls)
        self.assertTrue(all(c[1:4] == ["api", "--method", "GET"] for c in expected.calls))

    def test_approval_gated_runs_are_not_green_despite_zero_failing_checks(self):
        gated = ["Tests", "Sim tests", "Native portability", "Check Spec References", "CodeQL", "Check docs", "Benchmark"]
        lint = run(99, "Lint PR title", "success", event="pull_request_target")
        fake = FakeGh(runs=[run(i, n, "action_required") for i, n in enumerate(gated, 1)] + [lint],
                      checks=[check(1, "Validate PR title", "success", suite=lint["check_suite_id"])])
        rc, out = invoke(fake)
        self.assertEqual(rc, 0)
        self.assertEqual(out["verdict"], "action_required")
        self.assertEqual(out["counts"]["failing"], 0)
        self.assertEqual(out["counts"]["action_required"], 7)
        self.assertEqual(sorted(i["name"] for i in out["nonGreen"]), sorted(gated))
        self.assertEqual(out["workflowRunsByEvent"]["pull_request"], {"action_required": 7})

    def test_completed_success_is_observed_green(self):
        tests = run(1, "Tests", "success")
        fake = FakeGh(runs=[tests, run(2, "Benchmark", "skipped")],
                      checks=[check(1, "unit", "success", suite=tests["check_suite_id"]),
                              check(2, "docs", "neutral", suite=1002)],
                      statuses=[{"context": "ci/ext", "state": "success"}])
        rc, out = invoke(fake)
        self.assertEqual((rc, out["verdict"], out["nonGreen"]), (0, "observed_green", []))
        self.assertEqual((out["counts"]["ok"], out["counts"]["skipped"]), (3, 2))
        self.assertTrue(any("not merge readiness" in c for c in out["caveats"]))

    def test_success_from_non_actions_check_or_status_alone_is_green(self):
        self.assertEqual(verdict(FakeGh(checks=[ext_check(1, "buildkite", "success")])), "observed_green")
        self.assertEqual(verdict(FakeGh(statuses=[{"context": "ci/ext", "state": "success"}])), "observed_green")

    def test_newer_skipped_run_does_not_hide_older_failure(self):
        old, new = run(1, "Tests", "failure"), run(2, "Tests", "skipped")
        fake = FakeGh(runs=[old, new], checks=[check(1, "unit", "failure", suite=old["check_suite_id"]),
                                               check(2, "unit", "skipped", suite=new["check_suite_id"])])
        rc, out = invoke(fake)
        self.assertEqual(out["verdict"], "failing")
        self.assertEqual(out["observed"]["supersededWorkflowRuns"], 0)

    def test_newer_successful_run_with_skipped_job_does_not_hide_older_failed_job(self):
        old, new = run(1, "Tests", "failure"), run(2, "Tests", "success")
        fake = FakeGh(runs=[old, new], checks=[check(1, "unit", "failure", suite=old["check_suite_id"]),
                                               check(2, "unit", "skipped", suite=new["check_suite_id"]),
                                               check(3, "label-gate", "success", suite=new["check_suite_id"])])
        rc, out = invoke(fake)
        self.assertEqual(out["verdict"], "failing")
        self.assertEqual([i["name"] for i in out["nonGreen"]], ["unit"])

    def test_newer_run_re_executing_job_supersedes_older_check(self):
        old, new = run(1, "Tests", "failure"), run(2, "Tests", "success")
        fake = FakeGh(runs=[old, new], checks=[check(1, "unit", "failure", suite=old["check_suite_id"]),
                                               check(2, "unit", "success", suite=new["check_suite_id"])])
        rc, out = invoke(fake)
        self.assertEqual(out["verdict"], "observed_green")
        self.assertEqual(out["observed"]["supersededCheckRuns"], 1)

    def test_unlinked_actions_check_is_not_external_success(self):
        lint = run(1, "Lint PR title", "success", event="pull_request_target")
        fake = FakeGh(runs=[lint], checks=[check(1, "unit", "success", suite=9999)])
        self.assertEqual(verdict(fake), "no_ci")

    def test_same_job_name_in_different_workflows_is_not_collapsed(self):
        a, b = run(1, "Tests", None, status="in_progress"), run(2, "Sim", "success")
        fake = FakeGh(runs=[a, b], checks=[check(1, "build", "failure", suite=a["check_suite_id"]),
                                           check(2, "build", "success", suite=b["check_suite_id"])])
        rc, out = invoke(fake)
        self.assertEqual(out["verdict"], "failing")
        self.assertEqual(out["supersededNonGreen"], [])

    def test_pull_request_target_only_success_is_no_ci(self):
        lint = run(1, "Lint PR title", "success", event="pull_request_target")
        board = run(2, "Project board", "success", event="pull_request_review")
        fake = FakeGh(runs=[lint, board], checks=[check(1, "Validate PR title", "success", suite=lint["check_suite_id"])])
        self.assertEqual(verdict(fake), "no_ci")

    def test_all_skipped_is_no_ci(self):
        fake = FakeGh(runs=[run(1, "Benchmark", "skipped")], checks=[ext_check(1, "ext", "neutral")])
        self.assertEqual(verdict(fake), "no_ci")

    def test_no_observed_ci_is_no_ci(self):
        self.assertEqual(verdict(FakeGh()), "no_ci")

    def test_blocking_verdict_order(self):
        ok = run(9, "Lint", "success")
        cases = [
            ([run(1, "A", "failure"), run(2, "B", "action_required"), run(3, "C", None, status="queued")], "failing"),
            ([run(2, "B", "action_required"), run(3, "C", None, status="queued"), run(4, "D", "cancelled")],
             "action_required"),
            ([run(3, "C", None, status="queued"), run(4, "D", "cancelled"), ok], "pending"),
            ([run(4, "D", "cancelled"), ok], "cancelled"),
        ]
        for runs, expected in cases:
            self.assertEqual(verdict(FakeGh(runs=runs)), expected, f"runs={[r['name'] for r in runs]}")

    def test_conclusion_and_status_mapping(self):
        mapping = [
            (("completed", "stale"), "failing"),
            (("completed", "some_future_value"), "failing"),
            (("completed", "timed_out"), "failing"),
            (("completed", "startup_failure"), "failing"),
            (("waiting", None), "pending"),
            (("requested", None), "pending"),
            (("completed", None), "pending"),
            (("completed", "action_required"), "action_required"),
        ]
        for (status, conclusion), expected in mapping:
            self.assertEqual(evidence.classify_run(status, conclusion), expected, f"{status}/{conclusion}")
        self.assertEqual(verdict(FakeGh(checks=[ext_check(1, "ext", "action_required")])), "action_required")

    def test_failing_or_pending_status_context(self):
        base = [run(1, "Tests", "success")]
        self.assertEqual(verdict(FakeGh(runs=base, statuses=[{"context": "x", "state": "error"}])), "failing")
        self.assertEqual(verdict(FakeGh(runs=base, statuses=[{"context": "x", "state": "pending"}])), "pending")

    def test_superseded_cancellation_is_reported_but_not_current(self):
        old, new = run(1, "Tests", "cancelled"), run(2, "Tests", "success")
        fake = FakeGh(runs=[old, new], checks=[check(1, "unit", "cancelled", suite=old["check_suite_id"]),
                                               check(2, "unit", "success", suite=new["check_suite_id"])])
        rc, out = invoke(fake)
        self.assertEqual(out["verdict"], "observed_green")
        self.assertEqual((out["observed"]["supersededWorkflowRuns"], out["observed"]["supersededCheckRuns"]), (1, 1))
        self.assertEqual([i["conclusion"] for i in out["supersededNonGreen"]], ["cancelled", "cancelled"])

    def test_unsuperseded_cancellation_is_cancelled(self):
        self.assertEqual(verdict(FakeGh(runs=[run(1, "Tests", "cancelled")])), "cancelled")

    def test_runs_belonging_only_to_another_pr_are_excluded(self):
        mine, other = run(1, "Tests", "success", prs=(10460,)), run(2, "Tests2", "failure", prs=(10999,))
        fake = FakeGh(runs=[mine, other], checks=[check(1, "unit", "failure", suite=other["check_suite_id"])])
        rc, out = invoke(fake)
        self.assertEqual((out["verdict"], out["observed"]["otherPrWorkflowRuns"]), ("observed_green", 1))
        self.assertEqual(out["observed"]["checkRuns"], 0)

    def test_head_moved_during_collection_fails_closed(self):
        rc, out = invoke(FakeGh(runs=[run(1, "Tests", "success")], heads=(SHA, OTHER_SHA)))
        self.assertEqual((rc, out["ok"], out["verdict"]), (1, False, "unknown"))
        self.assertIn("head moved", out["error"])

    def test_query_failure_fails_closed_with_stderr_detail(self):
        rc, out = invoke(FakeGh(fail_endpoint="/actions/runs", stderr="HTTP 403: rate limit exceeded\nmore"))
        self.assertEqual((rc, out["ok"], out["verdict"]), (1, False, "unknown"))
        self.assertIn("HTTP 403: rate limit exceeded", out["error"])
        self.assertNotIn("more", out["error"])

    def test_malformed_responses_fail_closed(self):
        for raw in ({"/check-runs": "not json"}, {"/check-runs": "[]"}, {"/check-runs": json.dumps({"total_count": 0})}):
            rc, out = invoke(FakeGh(raw=raw))
            self.assertEqual((rc, out["verdict"]), (1, "unknown"), f"raw={raw}")

    def test_paginates_each_endpoint_and_fails_closed_past_page_cap(self):
        fake = FakeGh(checks=[ext_check(i, f"job-{i}", "success") for i in range(1, 6)],
                      statuses=[{"context": f"c{i}", "state": "success"} for i in range(4)], page_size=2)
        with patch.object(evidence, "PER_PAGE", 2):
            rc, out = invoke(fake)
        self.assertEqual((rc, out["observed"]["checkRuns"], out["observed"]["statusContexts"]), (0, 5, 4))
        status_calls = [c[-1] for c in fake.calls if "/status?" in c[-1]]
        self.assertEqual(len(status_calls), 2, "status paging should stop once total_count is reached")
        fake = FakeGh(checks=[ext_check(i, f"job-{i}", "success") for i in range(1, 20)], page_size=2)
        with patch.object(evidence, "PER_PAGE", 2):
            rc, out = invoke(fake)
        self.assertEqual((rc, out["verdict"]), (1, "unknown"))
        self.assertIn("exceeded", out["error"])

    def test_non_object_records_never_become_empty_or_green_evidence(self):
        endpoints = (("/actions/runs", "workflow_runs"), ("/check-runs", "check_runs"),
                     ("/status?", "statuses"))
        for fragment, key in endpoints:
            for bad in (None, "lost failure", [], 1):
                with self.subTest(endpoint=fragment, record=bad):
                    fake = FakeGh(runs=[run(1, "Tests", "success")],
                                  raw={fragment: json.dumps({"total_count": 1, key: [bad]})})
                    rc, out = invoke(fake)
                    self.assertEqual((rc, out["ok"], out["verdict"]), (1, False, "unknown"))
                    self.assertIn("non-object", out["error"])

    def test_invalid_totals_cannot_terminate_paging_as_success(self):
        for total in (True, False, -1, "1", 1.0, None):
            with self.subTest(total=total):
                fake = FakeGh(raw={"/actions/runs": json.dumps({
                    "total_count": total, "workflow_runs": [run(1, "Tests", "success")]})})
                rc, out = invoke(fake)
                self.assertEqual((rc, out["verdict"]), (1, "unknown"))
                self.assertIn("invalid total_count", out["error"])

    def test_short_first_or_later_page_cannot_hide_advertised_results(self):
        for full_first_page in (False, True):
            with self.subTest(full_first_page=full_first_page):
                pages = ({"total_count": 4, "workflow_runs": [run(1, "Tests", "success")]},)
                if full_first_page:
                    pages = ({"total_count": 4, "workflow_runs": [run(2, "Sim", "success"),
                              run(1, "Tests", "success")]}, *pages)
                with patch.object(evidence, "PER_PAGE", 2), \
                        patch.object(evidence, "get_json", side_effect=pages):
                    with self.assertRaisesRegex(evidence.CollectionError, "evidence incomplete"):
                        evidence.get_paged("gh", "runs", "workflow_runs", 30)

    def test_total_below_accumulated_records_is_not_complete_evidence(self):
        pages = [{"total_count": 4, "check_runs": [ext_check(4, "a", "success"), ext_check(3, "b", "success")]},
                 {"total_count": 2, "check_runs": [ext_check(2, "c", "success")]}]
        with patch.object(evidence, "PER_PAGE", 2), patch.object(evidence, "get_json", side_effect=pages):
            with self.assertRaisesRegex(evidence.CollectionError, "more records than total_count"):
                evidence.get_paged("gh", "checks", "check_runs", 30)
        rc, out = invoke(FakeGh(raw={"/actions/runs": json.dumps({
            "total_count": 0, "workflow_runs": [run(1, "Tests", "success")]})}))
        self.assertEqual((rc, out["verdict"]), (1, "unknown"))

    def test_valid_zero_and_exact_full_page_totals_still_work(self):
        self.assertEqual(verdict(FakeGh()), "no_ci")
        fake = FakeGh(checks=[ext_check(1, "a", "success"), ext_check(2, "b", "success")], page_size=2)
        with patch.object(evidence, "PER_PAGE", 2):
            rc, out = invoke(fake)
        self.assertEqual((rc, out["verdict"]), (0, "observed_green"))
        self.assertEqual(len([c for c in fake.calls if "/check-runs?" in c[-1]]), 1)

    def test_missing_totals_keep_bounded_pagination(self):
        pages = [{"statuses": [{"context": "a", "state": "success"}, {"context": "b", "state": "success"}]},
                 {"statuses": [{"context": "c", "state": "failure"}]}]
        with patch.object(evidence, "PER_PAGE", 2), patch.object(evidence, "get_json", side_effect=pages):
            statuses = evidence.get_paged("gh", "statuses", "statuses", 30)
        self.assertEqual([s["state"] for s in statuses], ["success", "success", "failure"])
        with patch.object(evidence, "PER_PAGE", 2), patch.object(evidence, "MAX_PAGES", 1), \
                patch.object(evidence, "get_json", return_value=pages[0]):
            with self.assertRaisesRegex(evidence.CollectionError, "exceeded"):
                evidence.get_paged("gh", "statuses", "statuses", 30)

    def test_only_get_requests_are_issued(self):
        fake = FakeGh(runs=[run(1, "Tests", "success")])
        invoke(fake)
        self.assertTrue(fake.calls)
        for cmd in fake.calls:
            self.assertEqual(cmd[1:4], ["api", "--method", "GET"], f"non-GET call: {cmd}")

    def test_help_and_bad_args_exit_before_any_request(self):
        fake = FakeGh()
        for argv, code in ((["--help"], 0), (["--repo", "bad", "--pr", "1"], 2), (["--repo", "a/b", "--pr", "0"], 2),
                           (["--repo", "a/b", "--pr", "1", "--expect-workflow", ""], 2),
                           (["--repo", "a/b", "--pr", "1", "--expect-workflow", "  "], 2)):
            with patch.object(evidence.subprocess, "run", side_effect=fake), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    evidence.main(argv)
            self.assertEqual(ctx.exception.code, code, f"argv={argv}")
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
