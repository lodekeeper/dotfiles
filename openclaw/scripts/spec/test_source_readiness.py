#!/usr/bin/env python3
"""Regression coverage for source-cache false greens, not fixture provenance."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


WORKSPACE = Path(__file__).resolve().parents[2]
READINESS = WORKSPACE / "scripts/spec/check-test-vector-readiness.sh"
CACHE = WORKSPACE / "scripts/spec/ensure-fresh-test-vectors.sh"


class SourceReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "specs"
        self.repo.mkdir()
        self.git("init", "-q")

    def git(self, *args, env=None):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True,
            capture_output=True, text=True, env=env,
        ).stdout.strip()

    def write(self, path, content="def test_case():\n    pass\n"):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return target

    def source(self, package="eth_consensus_specs"):
        return self.write(f"tests/core/pyspec/{package}/test/phase0/test_example.py")

    def commit(self, old=False):
        self.git("add", "--all")
        env = os.environ.copy()
        # Isolated fixture commits never inherit an acting identity or date.
        env.update(GIT_AUTHOR_NAME="lodekeeper", GIT_COMMITTER_NAME="lodekeeper",
                   GIT_AUTHOR_EMAIL="lodekeeper@users.noreply.github.com",
                   GIT_COMMITTER_EMAIL="lodekeeper@users.noreply.github.com")
        if old:
            env.update(GIT_AUTHOR_DATE="2020-01-01T00:00:00Z",
                       GIT_COMMITTER_DATE="2020-01-01T00:00:00Z")
        else:
            env.pop("GIT_AUTHOR_DATE", None)
            env.pop("GIT_COMMITTER_DATE", None)
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "test fixture", env=env)

    def run_helper(self, *flags, cache=False):
        command = ["bash", str(CACHE if cache else READINESS)]
        if cache:
            command += ["--target-repo", str(self.repo), "--check-only"]
        else:
            command += ["--spec-repo", str(self.repo)]
        result = subprocess.run(command + ["--json", *flags], capture_output=True, text=True)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["evidenceKind"], "test_sources")
        self.assertIs(payload["generatedFixturesVerified"], False)
        return result.returncode, payload

    def test_current_pyspec_sources_pass_without_claiming_generated_fixtures(self):
        source = self.source()
        self.commit()
        rc, payload = self.run_helper("--require-fresh")
        self.assertEqual(rc, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["sampleFile"], str(source.relative_to(self.repo)))
        self.assertEqual(payload["testsAgeBasis"], "tests_git_history")
        self.assertIn("generated fixtures unverified", payload["message"])

    def test_historical_eth2spec_layout_remains_supported(self):
        self.source("eth2spec")
        self.commit()
        rc, payload = self.run_helper("--require-fresh")
        self.assertEqual(rc, 0)
        self.assertTrue(payload["ok"])

    def test_readme_and_helper_only_tree_cannot_pass_as_test_sources(self):
        self.write("tests/README.md", "not test sources")
        self.write("tests/core/pyspec/eth_consensus_specs/test/helpers/specs.py")
        self.commit()
        rc, payload = self.run_helper()
        self.assertEqual(rc, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "no_vectors")

    def test_generated_only_tree_is_not_source_readiness(self):
        self.write("tests/minimal/heze/sanity/blocks/pyspec_tests/case/pre.ssz_snappy", "fixture")
        self.commit()
        rc, payload = self.run_helper()
        self.assertEqual(rc, 1)
        self.assertFalse(payload["ok"])

    def test_cached_or_reported_python_tests_do_not_count(self):
        for directory in ("__pycache__", "test-reports"):
            self.write(f"tests/core/pyspec/eth_consensus_specs/test/{directory}/test_example.py")
        self.commit()
        rc, payload = self.run_helper()
        self.assertEqual(rc, 1)
        self.assertFalse(payload["ok"])

    def test_unknown_history_is_advisory_only_without_strict_freshness(self):
        self.write("README.md", "committed unrelated history")
        self.commit()
        self.source()
        rc, payload = self.run_helper()
        self.assertEqual(rc, 0)
        self.assertEqual(payload["status"], "ready_unknown_age")
        self.assertIsNone(payload["testsAgeDays"])
        rc, payload = self.run_helper("--require-fresh")
        self.assertEqual(rc, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "unknown_age")

    def test_unborn_repo_returns_parseable_strict_unknown_history_failure(self):
        self.source()
        rc, payload = self.run_helper("--require-fresh")
        self.assertEqual(rc, 2)
        self.assertEqual(payload["status"], "unknown_age")
        self.assertIsNone(payload["headSha"])

    def test_stale_source_history_preserves_strict_and_advisory_behavior(self):
        self.source()
        self.commit(old=True)
        for flags, expected_rc, expected_status in (
            ([], 0, "stale_warning"), (["--require-fresh"], 2, "stale"),
        ):
            with self.subTest(flags=flags):
                rc, payload = self.run_helper(*flags)
                self.assertEqual(rc, expected_rc)
                self.assertEqual(payload["status"], expected_status)
                self.assertTrue(payload["stale"])

    def test_check_only_cache_accepts_clean_sources_without_changing_head(self):
        source = self.source()
        self.commit()
        before = (self.git("rev-parse", "HEAD"), source.read_bytes(), self.git("status", "--porcelain"))
        rc, payload = self.run_helper(cache=True)
        self.assertEqual(rc, 0)
        self.assertTrue(payload["ok"])
        self.assertIs(payload["readiness"]["generatedFixturesVerified"], False)
        self.assertEqual(before, (self.git("rev-parse", "HEAD"), source.read_bytes(),
                                  self.git("status", "--porcelain")))

    def test_check_only_rejects_dirty_tracked_and_untracked_sources_unchanged(self):
        source = self.source()
        self.commit()
        source.write_text("def test_changed():\n    pass\n")
        self.write("local-scratch.txt", "untracked")
        before = (self.git("rev-parse", "HEAD"), source.read_bytes(), self.git("status", "--porcelain"))
        rc, payload = self.run_helper(cache=True)
        self.assertEqual(rc, 2)
        self.assertEqual(payload["status"], "dirty_cache")
        self.assertFalse(payload["ok"])
        self.assertEqual(before, (self.git("rev-parse", "HEAD"), source.read_bytes(),
                                  self.git("status", "--porcelain")))

    def test_check_only_rejects_untracked_only_cache(self):
        self.source()
        self.commit()
        self.write("untracked.txt", "untracked")
        rc, payload = self.run_helper(cache=True)
        self.assertEqual(rc, 2)
        self.assertEqual(payload["status"], "dirty_cache")

    def test_check_only_does_not_inherit_hidden_untracked_git_preference(self):
        self.source()
        self.commit()
        self.git("config", "status.showUntrackedFiles", "no")
        scratch = self.write("untracked.txt", "untracked must remain visible to the guard")
        before = (self.git("rev-parse", "HEAD"), scratch.read_bytes())
        rc, payload = self.run_helper(cache=True)
        self.assertEqual(rc, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "dirty_cache")
        self.assertEqual(before, (self.git("rev-parse", "HEAD"), scratch.read_bytes()))
        self.assertEqual(self.git("config", "status.showUntrackedFiles"), "no")

    def test_missing_tests_returns_parseable_failure(self):
        self.write("README.md", "no tests directory")
        self.commit()
        rc, payload = self.run_helper()
        self.assertEqual(rc, 1)
        self.assertEqual(payload["status"], "missing_tests_dir")


if __name__ == "__main__":
    unittest.main()
