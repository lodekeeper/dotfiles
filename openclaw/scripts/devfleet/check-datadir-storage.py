#!/usr/bin/env python3
"""Collect read-only storage evidence for an existing local data directory.

Run on the data host: python3 check-datadir-storage.py --path /host/datadir
For containers, first resolve the real host-side mount source; this tool does
not inspect Docker, discover expected mounts, or enter another mount namespace.
JSON includes local paths/device names: retain it privately.

Exit 0 means core evidence was collected, NOT sufficient capacity, correct
placement, filesystem growth eligibility or disk health. Compare filesystem
bytes with the matched device/partition bytes; never substitute parent-disk
capacity. Missing optional sysfs evidence stays unknown. sameDeviceIdAsRoot
compares st_dev only (not physical storage identity). Reads are not atomic;
quiesce mount changes and recheck before any separately authorized maintenance.
No writes, sudo, network calls, thresholds or automatic fixes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import subprocess


class CollectionError(ValueError):
    pass


def mount_for(path: Path) -> dict:
    try:
        proc = subprocess.run(
            ["findmnt", "--json", "--first-only", "--target", str(path),
             "--output", "TARGET,SOURCE,FSTYPE,MAJ:MIN"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CollectionError("mount_collection_unavailable") from exc
    if proc.returncode != 0:
        raise CollectionError("mount_collection_failed")
    try:
        records = json.loads(proc.stdout)["filesystems"]
        if not isinstance(records, list) or len(records) != 1:
            raise ValueError
        mount = records[0]
        if not isinstance(mount, dict) or any(
            not isinstance(mount.get(k), str) or not mount[k]
            for k in ("target", "source", "fstype", "maj:min")
        ):
            raise ValueError
        target = Path(mount["target"])
        if not target.is_absolute() or not path.is_relative_to(target):
            raise ValueError
    except (ValueError, KeyError, TypeError) as exc:
        raise CollectionError("invalid_mount_evidence") from exc
    return mount


def block_capacity(device_id: str, sysfs: Path = Path("/sys/dev/block")) -> dict:
    # Kernel part_size_show reports bdev_nr_sectors: fixed 512-byte sectors,
    # regardless of the device's logical/physical sector size.
    try:
        sectors = int((sysfs / device_id / "size").read_text(encoding="ascii").strip())
        if sectors <= 0:
            raise ValueError
    except OSError:
        return {"bytes": None, "status": "unavailable"}
    except (ValueError, UnicodeError):
        return {"bytes": None, "status": "invalid"}
    return {"bytes": sectors * 512, "status": "observed"}


def inspect(path: Path) -> dict:
    path = path.expanduser().resolve(strict=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise CollectionError("not_directory")
    device_id = f"{os.major(info.st_dev)}:{os.minor(info.st_dev)}"
    mount = mount_for(path)
    if mount["maj:min"] != device_id:
        raise CollectionError("inconsistent_device_evidence")
    usage = os.statvfs(path)
    if usage.f_frsize <= 0:
        raise CollectionError("invalid_fragment_size")
    block = block_capacity(device_id)
    root_device = Path("/").stat().st_dev
    if path.stat().st_dev != info.st_dev:
        raise CollectionError("inconsistent_device_evidence")
    return {
        "ok": True,
        "evidenceKind": "local_storage_observation",
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "path": str(path),
        "mount": mount,
        "sameDeviceIdAsRoot": info.st_dev == root_device,
        "filesystemBytes": usage.f_blocks * usage.f_frsize,
        "freeBytes": usage.f_bfree * usage.f_frsize,
        "availableBytes": usage.f_bavail * usage.f_frsize,
        "blockDevice": block,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", type=Path, required=True, help="Existing host-side data directory")
    args = parser.parse_args(argv)
    try:
        result = inspect(args.path)
        code = 0
    except (OSError, ValueError, RuntimeError) as exc:
        reason = str(exc) if isinstance(exc, CollectionError) else "path_or_storage_unavailable"
        result = {"ok": False, "reason": reason}
        code = 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
