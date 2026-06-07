#!/usr/bin/env python3
"""Preflight devnet investigation routing.

Classifies a target network as a local Kurtosis enclave or a remote panda
datasource, and fails early when panda datasource discovery is unavailable.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from typing import Any


LOCAL_STATUSES = {"RUNNING", "STOPPED", "STOPPING"}
NAME_KEYS = ("name", "id", "network", "cluster", "slug", "title")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def run_command(cmd: list[str], timeout: int) -> tuple[int | None, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return None, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return 124, stdout, stderr or f"timed out after {timeout}s"

    return proc.returncode, proc.stdout, proc.stderr


def collect_kurtosis_enclaves(timeout: int) -> dict[str, Any]:
    if shutil.which("kurtosis") is None:
        return {"state": "missing", "names": [], "error": "kurtosis not found"}

    rc, stdout, stderr = run_command(["kurtosis", "enclave", "ls"], timeout)
    if rc != 0:
        return {
            "state": "error",
            "names": [],
            "error": (stderr or stdout).strip(),
            "returncode": rc,
        }

    names: list[str] = []
    for raw_line in stdout.splitlines():
        line = ANSI_RE.sub("", raw_line).strip()
        parts = line.split()
        if len(parts) >= 3 and parts[0] != "UUID" and parts[2] in LOCAL_STATUSES:
            names.append(parts[1])

    return {"state": "ready", "names": sorted(set(names))}


def datasource_name(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return None

    for key in NAME_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def collect_panda_datasources(timeout: int) -> dict[str, Any]:
    if shutil.which("panda") is None:
        return {"state": "missing", "names": [], "error": "panda not found"}

    rc, stdout, stderr = run_command(["panda", "datasources", "--json"], timeout)
    if rc != 0:
        return {
            "state": "error",
            "names": [],
            "error": (stderr or stdout).strip(),
            "returncode": rc,
        }

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {
            "state": "invalid_json",
            "names": [],
            "error": f"panda datasources --json returned invalid JSON: {exc}",
            "raw": stdout.strip()[:500],
        }

    datasources = payload.get("datasources") if isinstance(payload, dict) else payload
    if datasources is None:
        return {
            "state": "unavailable",
            "names": [],
            "error": "panda returned datasources=null; auth or server datasource access is not ready",
        }
    if not isinstance(datasources, list):
        return {
            "state": "invalid_shape",
            "names": [],
            "error": "panda datasources payload is not a list",
        }

    names = [name for item in datasources if (name := datasource_name(item))]
    if not names:
        return {
            "state": "empty",
            "names": [],
            "error": "panda returned no datasource names",
        }

    return {"state": "ready", "names": sorted(set(names))}


def find_match(target: str | None, names: list[str]) -> str | None:
    if not target:
        return None

    wanted = target.lower()
    by_lower = {name.lower(): name for name in names}
    if wanted in by_lower:
        return by_lower[wanted]

    for name in names:
        lowered = name.lower()
        if wanted in lowered or lowered in wanted:
            return name

    return None


def build_result(target: str | None, timeout: int) -> tuple[int, dict[str, Any]]:
    local = collect_kurtosis_enclaves(timeout)
    panda = collect_panda_datasources(timeout)
    local_match = find_match(target, local["names"])
    remote_match = find_match(target, panda["names"])

    result: dict[str, Any] = {
        "target": target,
        "local": local,
        "panda": panda,
        "localMatch": local_match,
        "remoteMatch": remote_match,
        "classification": None,
        "status": None,
    }

    if target and local_match:
        result["classification"] = "local-kurtosis"
        result["status"] = "ready"
        return 0, result

    if target and remote_match:
        result["classification"] = "remote-panda"
        result["status"] = "ready"
        return 0, result

    if panda["state"] != "ready":
        result["status"] = "panda-unavailable"
        return 2, result

    if target:
        result["status"] = "target-not-found"
        return 3, result

    result["status"] = "ready"
    return 0, result


def render_text(exit_code: int, result: dict[str, Any]) -> str:
    target = result.get("target") or "(none)"
    if exit_code == 0 and result.get("classification") == "local-kurtosis":
        return f"LOCAL_DEVNET_READY target={target} enclave={result['localMatch']}"
    if exit_code == 0 and result.get("classification") == "remote-panda":
        return f"REMOTE_DEVNET_READY target={target} datasource={result['remoteMatch']}"
    if exit_code == 0:
        local_count = len(result["local"]["names"])
        remote_count = len(result["panda"]["names"])
        return f"DEVNET_ROUTING_READY local_enclaves={local_count} panda_datasources={remote_count}"
    if exit_code == 2:
        return f"PANDA_DATASOURCES_UNAVAILABLE target={target} reason={result['panda'].get('error', 'unknown')}"
    if exit_code == 3:
        return f"DEVNET_NOT_FOUND target={target}"
    return f"DEVNET_ROUTING_CHECK_FAILED target={target}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight local/remote devnet investigation routing")
    parser.add_argument("target", nargs="?", help="Network/enclave/datasource name to classify")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--timeout", type=int, default=20, help="Per-command timeout in seconds")
    args = parser.parse_args()

    exit_code, result = build_result(args.target, args.timeout)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_text(exit_code, result))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
