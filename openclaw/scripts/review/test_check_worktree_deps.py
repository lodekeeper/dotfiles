from __future__ import annotations

import importlib.util
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("check-worktree-deps.py")
SPEC = importlib.util.spec_from_file_location("worktree_deps", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ContainmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.modules = self.repo / "node_modules"
        self.store = self.modules / ".pnpm"
        self.store.mkdir(parents=True)
        self.metadata = self.modules / ".modules.yaml"
        self.metadata.write_text(json.dumps({"virtualStoreDir": ".pnpm", "storeDir": "/shared/content-store"}))
        self.external = self.root / "repo-other"
        self.external.mkdir()
        (self.external / "sentinel").write_text("must remain unchanged")

    def snapshot(self):
        return {
            str(p.relative_to(self.root)): (
                p.lstat().st_mode,
                p.lstat().st_mtime_ns,
                os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None,
            )
            for p in self.root.rglob("*")
        }

    def run_cli(self, expected):
        before = self.snapshot()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.repo)],
            env={**os.environ, "PATH": str(self.root / "no-tools")},
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(expected, result.returncode, result.stderr)
        self.assertEqual(before, self.snapshot())
        return result

    def test_local_json_and_normal_package_links_pass_without_writes(self):
        (self.modules / "workspace-package").symlink_to(self.external, target_is_directory=True)
        self.assertIn("readiness is not verified", self.run_cli(0).stdout)

    def test_supported_yaml_scalars_pass(self):
        for value in [".pnpm", "'.pnpm'", '".pnpm"']:
            with self.subTest(value=value):
                self.metadata.write_text("layoutVersion: 5\nhoistPattern:\n  - '*'\nvirtualStoreDir: " + value + "\n  # comment\notherNested:\n  item: value\n")
                self.run_cli(0)

    def test_external_root_and_ancestor_symlinks_are_blocked(self):
        (self.root / "parent-link").symlink_to(self.root, target_is_directory=True)
        for target in [self.external, self.root / "parent-link" / "repo-other"]:
            with self.subTest(target=target):
                alias = self.root / ("alias-" + str(len(target.parts)))
                alias.mkdir()
                (alias / "node_modules").symlink_to(target, target_is_directory=True)
                original = self.repo
                self.repo = alias
                try:
                    self.run_cli(2)
                finally:
                    self.repo = original

    def test_metadata_and_virtual_store_external_symlinks_are_blocked(self):
        original = self.metadata.read_bytes()
        self.metadata.unlink()
        metadata_target = self.external / "metadata.json"
        metadata_target.write_bytes(original)
        self.metadata.symlink_to(metadata_target)
        self.run_cli(2)
        self.metadata.unlink()
        self.metadata.write_bytes(original)
        self.store.rmdir()
        self.store.symlink_to(self.external, target_is_directory=True)
        self.run_cli(2)

    def test_missing_broken_and_non_directory_paths_are_blocked(self):
        self.store.rmdir()
        self.run_cli(2)
        self.store.symlink_to(self.root / "missing")
        self.run_cli(2)
        self.store.unlink()
        self.store.write_text("not a directory")
        self.run_cli(2)
        self.store.unlink()
        self.store.mkdir()
        self.metadata.unlink()
        self.run_cli(2)

    def test_configured_store_and_conventional_store_both_checked(self):
        self.metadata.write_text(json.dumps({"virtualStoreDir": str(self.external)}))
        self.run_cli(2)
        local = self.repo / "local-store"
        local.mkdir()
        self.metadata.write_text(json.dumps({"virtualStoreDir": str(local)}))
        self.run_cli(0)
        self.store.rmdir()
        self.store.symlink_to(self.external, target_is_directory=True)
        self.run_cli(2)

    def test_malformed_duplicate_missing_and_unsupported_metadata_blocked(self):
        for text in [
            '{', '{}', '{"virtualStoreDir": null}', '{"virtualStoreDir": 3}',
            '{"virtualStoreDir": ""}', '{"virtualStoreDir": "\\u0000"}',
            '{"virtualStoreDir": ".pnpm", "virtualStoreDir": ".pnpm"}',
            'virtualStoreDir: .pnpm\nvirtualStoreDir: .pnpm\n',
            'virtualStoreDir: *alias\n', 'virtualStoreDir: ../external\n',
            '"virtualStoreDir": .pnpm\n',
            'virtualStoreDir: .pnpm\n<<: *other\n',
            'virtualStoreDir: .pnpm\n"virtualStoreDir": ../external\n',
            'virtualStoreDir: .pnpm\n  /../../external\n',
            'virtualStoreDir: .pnpm\n  # comment\n\n  /../../external\n',
            'virtualStoreDir: .pnpm\n---\nstoreDir: /external\n',
        ]:
            with self.subTest(text=text):
                self.metadata.write_text(text)
                self.run_cli(2)

    def test_internal_symlink_layout_passes_but_parent_traversal_blocked(self):
        local = self.repo / "local-modules"
        self.modules.rename(local)
        self.modules.symlink_to(local, target_is_directory=True)
        self.run_cli(0)
        (local / ".modules.yaml").write_text('{"virtualStoreDir": "../local-modules/.pnpm"}')
        self.run_cli(2)

    def test_help_and_bad_arguments_never_inspect_layout(self):
        from unittest.mock import patch
        for args, code in [(["--help"], 0), (["--repo", "/missing", "--unknown"], 2)]:
            with self.subTest(args=args), patch.object(MODULE, "check_layout", side_effect=AssertionError("unexpected inspection")):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    MODULE.main(args)
                self.assertEqual(code, error.exception.code)


if __name__ == "__main__":
    unittest.main()
