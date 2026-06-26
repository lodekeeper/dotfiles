#!/usr/bin/env python3
"""Verify that GitHub CLI writes would run as the expected account."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys


def emit(payload: dict, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, sort_keys=True))
        return

    if payload["ok"]:
        print(f"GitHub actor boundary OK: {payload['actual']}")
        return

    actual = payload.get("actual") or "unknown"
    print(
        "GITHUB_ACTOR_BOUNDARY_FAIL: "
        f"expected {payload['expected']}, got {actual} ({payload['status']})"
    )
    if payload.get("stderr"):
        print(payload["stderr"], file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected",
        default="lodekeeper",
        help="Expected GitHub login for write actions (default: lodekeeper)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
        help="Timeout for gh api user lookup (default: 20)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    payload = {
        "ok": False,
        "expected": args.expected,
        "actual": None,
        "status": "unknown",
        "ghAvailable": False,
        "stderr": "",
    }

    if args.timeout_seconds < 1:
        payload["status"] = "invalid_timeout"
        payload["stderr"] = "--timeout-seconds must be >= 1"
        emit(payload, args.json)
        return 1

    gh = shutil.which("gh")
    if not gh:
        payload["status"] = "missing_gh"
        emit(payload, args.json)
        return 2

    payload["ghAvailable"] = True
    try:
        proc = subprocess.run(
            [gh, "api", "user", "--jq", ".login"],
            text=True,
            capture_output=True,
            timeout=args.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        payload["status"] = "timeout"
        emit(payload, args.json)
        return 2

    if proc.returncode != 0:
        payload["status"] = "gh_api_failed"
        payload["stderr"] = proc.stderr.strip()
        emit(payload, args.json)
        return 2

    actual = proc.stdout.strip()
    payload["actual"] = actual
    payload["ok"] = actual == args.expected
    payload["status"] = "ready" if payload["ok"] else "wrong_actor"
    emit(payload, args.json)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
