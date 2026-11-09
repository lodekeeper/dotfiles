"""Storage observations must not mistake device capacity for usable space."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("check-datadir-storage.py")
spec = importlib.util.spec_from_file_location("datadir_storage", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
GIB = 1024 ** 3


class StorageTests(unittest.TestCase):
    def test_live_cli_resolves_symlink_and_does_not_change_datadir(self):
        with tempfile.TemporaryDirectory(prefix="storage evidence ") as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            record = data / "record"
            record.write_text("keep this input")
            alias = root / "link"
            alias.symlink_to(data, target_is_directory=True)
            before = (record.read_bytes(), record.stat().st_mtime_ns, sorted(root.iterdir()))
            proc = subprocess.run([sys.executable, str(SCRIPT), "--path", str(alias)],
                                  capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            result = json.loads(proc.stdout)
            usage = os.statvfs(data)
            self.assertEqual(result["path"], str(data.resolve()))
            self.assertEqual(result["filesystemBytes"], usage.f_blocks * usage.f_frsize)
            self.assertEqual(result["sameDeviceIdAsRoot"], data.stat().st_dev == Path("/").stat().st_dev)
            self.assertEqual(before, (record.read_bytes(), record.stat().st_mtime_ns, sorted(root.iterdir())))

    def test_undersized_filesystem_remains_distinct_from_device_and_reserved_space(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve()
            usage = SimpleNamespace(f_frsize=4096, f_bsize=8192,
                                    f_blocks=100 * GIB // 4096,
                                    f_bfree=30 * GIB // 4096, f_bavail=25 * GIB // 4096)
            for root_id in (os.makedev(8, 1), os.makedev(8, 2)):
                with self.subTest(root_id=root_id):
                    def fake_stat(p, **kwargs):
                        return SimpleNamespace(st_mode=stat.S_IFDIR,
                                               st_dev=root_id if p == Path("/") else os.makedev(8, 1))
                    mount = {"target": str(path), "source": "/dev/test-partition", "fstype": "ext4", "maj:min": "8:1"}
                    with patch.object(check.Path, "stat", autospec=True, side_effect=fake_stat), \
                         patch.object(check, "mount_for", return_value=mount), \
                         patch.object(check.os, "statvfs", return_value=usage), \
                         patch.object(check, "block_capacity", return_value={"bytes": 200 * GIB, "status": "observed"}):
                        result = check.inspect(path)
                    self.assertEqual(result["filesystemBytes"], 100 * GIB)
                    self.assertEqual(result["blockDevice"]["bytes"], 200 * GIB)
                    self.assertEqual(result["freeBytes"], 30 * GIB)
                    self.assertEqual(result["availableBytes"], 25 * GIB)
                    self.assertEqual(result["sameDeviceIdAsRoot"], root_id == os.makedev(8, 1))
                    self.assertEqual(result["evidenceKind"], "local_storage_observation")
                    self.assertNotIn("healthy", result)

    def test_sysfs_uses_only_matched_partition_and_unknown_stays_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "8:0").mkdir()
            (root / "8:0" / "size").write_text("9999999999")
            self.assertEqual(check.block_capacity("8:1", root), {"bytes": None, "status": "unavailable"})
            (root / "8:1").mkdir()
            for content, expected in (("419430400\n", {"bytes": 200 * GIB, "status": "observed"}),
                                      ("bad", {"bytes": None, "status": "invalid"}),
                                      ("-1", {"bytes": None, "status": "invalid"}),
                                      ("0", {"bytes": None, "status": "invalid"})):
                with self.subTest(content=content):
                    (root / "8:1" / "size").write_text(content)
                    self.assertEqual(check.block_capacity("8:1", root), expected)

    def test_malformed_or_failed_mount_evidence_is_rejected(self):
        valid = {"target": "/", "source": "/dev/test", "fstype": "ext4", "maj:min": "8:1"}
        for payload in (None, [], {}, {"filesystems": []}, {"filesystems": [valid, valid]},
                        {"filesystems": [{}]}, {"filesystems": [dict(valid, target="/elsewhere")]},
                        {"filesystems": [dict(valid, target="relative")]}, {"filesystems": [None]}):
            with self.subTest(payload=payload), \
                 patch.object(check.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload))):
                with self.assertRaises(check.CollectionError):
                    check.mount_for(Path("/data"))
        for failure in (FileNotFoundError(), subprocess.TimeoutExpired("findmnt", 10)):
            with self.subTest(failure=type(failure)), patch.object(check.subprocess, "run", side_effect=failure):
                with self.assertRaises(check.CollectionError):
                    check.mount_for(Path("/data"))
        with patch.object(check.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(check.CollectionError):
                check.mount_for(Path("/data"))

    def test_missing_and_non_directory_inputs_do_not_collect_or_create(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(check, "mount_for") as collector:
            root = Path(directory)
            for path in (root / "missing", SCRIPT):
                with self.subTest(path=path), contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(check.main(["--path", str(path)]), 2)
                    self.assertFalse(json.loads(output.getvalue())["ok"])
            self.assertEqual(list(root.iterdir()), [])
            collector.assert_not_called()

    def test_device_mismatch_and_zero_fragment_size_are_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            mount = {"maj:min": "mismatch"}
            with patch.object(check, "mount_for", return_value=mount), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(check.main(["--path", str(path)]), 2)
            self.assertEqual(json.loads(output.getvalue())["reason"], "inconsistent_device_evidence")
            mount["maj:min"] = f"{os.major(path.stat().st_dev)}:{os.minor(path.stat().st_dev)}"
            with patch.object(check, "mount_for", return_value=mount), \
                 patch.object(check.os, "statvfs", return_value=SimpleNamespace(f_frsize=0)), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(check.main(["--path", str(path)]), 2)
            self.assertEqual(json.loads(output.getvalue())["reason"], "invalid_fragment_size")

    def test_help_and_invalid_arguments_do_not_collect(self):
        for argv, code in ((["--help"], 0), ([], 2), (["--unknown"], 2)):
            with self.subTest(argv=argv), patch.object(check, "inspect") as collector, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    check.main(argv)
                self.assertEqual(result.exception.code, code)
                collector.assert_not_called()


if __name__ == "__main__":
    unittest.main()
