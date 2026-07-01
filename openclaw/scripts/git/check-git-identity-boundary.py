#!/usr/bin/env python3
"""Verify that local Git commits would use the expected author identity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


def emit(payload: dict, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, sort_keys=True))
        return

    if payload["ok"]:
        print(
            "Git identity boundary OK: "
            f"{payload['actualName']} <{payload['actualEmail']}>"
        )
        return

    print(
        "GIT_IDENTITY_BOUNDARY_FAIL: "
        f"expected {payload['expectedName']} <{payload['expectedEmail']}>, "
        f"got {payload.get('actualName') or 'unknown'} "
        f"<{payload.get('actualEmail') or 'unknown'}> ({payload['status']})"
    )
    if payload.get("stderr"):
        print(payload["stderr"], file=sys.stderr)


def git_config(git: str, key: str, cwd: Path, timeout_seconds: int) -> tuple[int, str, str]:
    proc = subprocess.run(
        [git, "config", "--get", key],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-name",
        default="lodekeeper",
        help="Expected git user.name for commits (default: lodekeeper)",
    )
    parser.add_argument(
        "--expected-email",
        default="lodekeeper@users.noreply.github.com",
        help="Expected git user.email for commits",
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="Directory whose effective git config should be checked (default: current directory)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=10,
        help="Timeout for each git config lookup (default: 10)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    cwd = Path(args.cwd).expanduser().resolve()
    payload = {
        "ok": False,
        "expectedName": args.expected_name,
        "expectedEmail": args.expected_email,
        "actualName": None,
        "actualEmail": None,
        "cwd": str(cwd),
        "gitAvailable": False,
        "status": "unknown",
        "stderr": "",
    }

    if args.timeout_seconds < 1:
        payload["status"] = "invalid_timeout"
        payload["stderr"] = "--timeout-seconds must be >= 1"
        emit(payload, args.json)
        return 1

    if not cwd.exists():
        payload["status"] = "missing_cwd"
        payload["stderr"] = f"cwd does not exist: {cwd}"
        emit(payload, args.json)
        return 2

    git = shutil.which("git")
    if not git:
        payload["status"] = "missing_git"
        emit(payload, args.json)
        return 2

    payload["gitAvailable"] = True
    try:
        name_rc, name, name_err = git_config(git, "user.name", cwd, args.timeout_seconds)
        email_rc, email, email_err = git_config(git, "user.email", cwd, args.timeout_seconds)
    except subprocess.TimeoutExpired:
        payload["status"] = "timeout"
        emit(payload, args.json)
        return 2

    payload["actualName"] = name or None
    payload["actualEmail"] = email or None
    if name_err or email_err:
        payload["stderr"] = "\n".join(part for part in [name_err, email_err] if part)

    if name_rc != 0 or email_rc != 0 or not name or not email:
        payload["status"] = "missing_identity"
        emit(payload, args.json)
        return 2

    payload["ok"] = name == args.expected_name and email == args.expected_email
    payload["status"] = "ready" if payload["ok"] else "wrong_identity"
    emit(payload, args.json)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
