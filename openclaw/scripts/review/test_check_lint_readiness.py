#!/usr/bin/env python3
"""Regression controls for false-positive local lint readiness."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "lint_readiness", Path(__file__).with_name("check-lint-readiness.py")
)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

LOCK = """lockfileVersion: '9.0'
importers:
  .:
    devDependencies:
      '@biomejs/biome':
        specifier: ^2.6.3
        version: 2.6.3
  packages/example:
    devDependencies:
      '@biomejs/biome':
        specifier: ^1.0.0
        version: 1.0.0
"""


class LintReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.installed = self.root / "node_modules/@biomejs/biome/package.json"
        self.installed.parent.mkdir(parents=True)
        self.installed.write_text(json.dumps({"name": "@biomejs/biome", "version": "2.6.3"}))
        (self.root / "package.json").write_text(json.dumps({"devDependencies": {"@biomejs/biome": "^2.6.3"}}))
        (self.root / "pnpm-lock.yaml").write_text(LOCK)
        (self.root / "biome.jsonc").write_bytes(b'{"linter":{"enabled":true}}\n')
        self.baseline = (self.root / "biome.jsonc").read_bytes()
        self.git_patch = patch.object(guard, "git", side_effect=self.fake_git)
        self.git_patch.start()
        self.addCleanup(self.git_patch.stop)

    def fake_git(self, repo, *args):
        if args == ("rev-parse", "--show-toplevel"):
            return str(self.root).encode() + b"\n"
        if args == ("rev-parse", "HEAD"):
            return b"a" * 40 + b"\n"
        if args == ("show", "a" * 40 + ":biome.jsonc"):
            return self.baseline
        self.fail(f"unexpected Git operation: {args}")

    def test_matching_metadata_is_not_a_lint_pass(self):
        result = guard.check_readiness(self.root)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "metadata_checks_passed")
        self.assertFalse(result["lintExecuted"])
        self.assertEqual(result["lockedVersion"], "2.6.3")

    def test_stale_installed_biome_blocks(self):
        self.installed.write_text('{"name":"@biomejs/biome","version":"2.2.2"}')
        result = guard.check_readiness(self.root)
        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["installedMatchesLock"])

    def test_trimmed_root_config_blocks_independently_of_version(self):
        (self.root / "biome.jsonc").write_text('{}')
        result = guard.check_readiness(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(result["checks"]["installedMatchesLock"])
        self.assertFalse(result["checks"]["rootConfigMatchesHead"])

    def test_declared_specifier_mismatch_blocks(self):
        (self.root / "package.json").write_text('{"devDependencies":{"@biomejs/biome":"^2.2.0"}}')
        result = guard.check_readiness(self.root)
        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["declaredMatchesLock"])

    def test_nested_biome_does_not_replace_missing_root_biome(self):
        no_root = LOCK.replace("      '@biomejs/biome':", "      other:", 1)
        with self.assertRaises(guard.ReadinessError):
            guard.locked_biome(no_root)

    def test_ambiguous_or_unsupported_lock_metadata_blocks(self):
        variants = [
            LOCK.replace("'9.0'", "'8.0'"),
            LOCK.replace("  .:\n", "  .: &root\n"),
            LOCK.replace("    devDependencies:\n", "    devDependencies:\n    devDependencies:\n", 1),
            LOCK.replace("importers:\n", "importers :\nimporters:\n"),
            LOCK.replace("  .:\n", "  \".\" :\n  .:\n"),
            LOCK.replace("    devDependencies:\n", "    devDependencies :\n    devDependencies:\n", 1),
            LOCK.replace("        version: 2.6.3", "        version: 2.6.3\n        version: 2.6.3", 1),
            LOCK.replace("        version: 2.6.3", "        version: ^2.6.3", 1),
            LOCK.replace("        specifier: ^2.6.3", "        specifier: 'catalog:'", 1),
        ]
        for text in variants:
            with self.subTest(text=text), self.assertRaises(guard.ReadinessError):
                guard.locked_biome(text)

    def test_missing_or_both_root_configs_block(self):
        (self.root / "biome.json").write_text('{}')
        with self.assertRaises(guard.ReadinessError):
            guard.check_readiness(self.root)
        (self.root / "biome.jsonc").rename(self.root / "saved.jsonc")
        (self.root / "biome.json").rename(self.root / "saved.json")
        with self.assertRaises(guard.ReadinessError):
            guard.check_readiness(self.root)

    def test_malformed_and_missing_installed_package_block(self):
        self.installed.write_text('{"name":')
        with self.assertRaises(ValueError):
            guard.check_readiness(self.root)
        self.installed.rename(self.installed.with_suffix('.saved'))
        with self.assertRaises(OSError):
            guard.check_readiness(self.root)

    def test_duplicate_json_keys_block(self):
        self.installed.write_text('{"name":"@biomejs/biome","version":"2.2.2","version":"2.6.3"}')
        with self.assertRaises(guard.ReadinessError):
            guard.check_readiness(self.root)

    def test_nested_workdir_is_not_treated_as_repo_root(self):
        nested = self.root / "packages"
        nested.mkdir()
        with self.assertRaises(guard.ReadinessError):
            guard.check_readiness(nested)


if __name__ == "__main__":
    unittest.main()
