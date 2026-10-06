#!/usr/bin/env python3
"""Diagnose upstream CI rerun restrictions using read-only GitHub requests.

A successful diagnostic is not authorization to rerun a workflow: repository
roles cannot prove token-level Actions write permission.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from typing import Any


PERMISSION_KEYS = ("pull", "push", "maintain", "admin")


def _get_json(gh: str, endpoint: str, timeout_s: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [gh, "api", "--method", "GET", endpoint],
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ValueError(f"GitHub GET {endpoint} failed ({type(exc).__name__})") from exc
    if proc.returncode != 0:
        raise ValueError(f"GitHub GET {endpoint} failed (exit {proc.returncode})")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"GitHub GET {endpoint} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"GitHub GET {endpoint} did not return an object")
    return payload


def diagnose(repo: str, expected: str, timeout_s: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "repo": repo,
        "expected": expected,
        "actual": None,
        "status": "blocked",
        "rerunCapability": "unknown",
        "permissions": {},
        "warnings": [],
    }
    if (timeout_s < 1 or not expected.strip()
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
            or any(part in (".", "..") for part in repo.split("/"))):
        result["error"] = "Expected a nonempty actor, owner/repo, and a positive timeout"
        return result
    gh = shutil.which("gh")
    if not gh:
        result["error"] = "gh executable not found"
        return result
    try:
        actor = _get_json(gh, "user", timeout_s).get("login")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("GitHub user payload has no valid login")
        result["actual"] = actor
        if actor != expected:
            raise ValueError(f"Wrong GitHub actor: expected {expected}, got {actor}")
        payload = _get_json(gh, f"repos/{repo}", timeout_s)
        full_name = payload.get("full_name")
        if not isinstance(full_name, str) or full_name.lower() != repo.lower():
            raise ValueError("GitHub repository identity did not match the requested repository")
        permissions = payload.get("permissions")
        if not isinstance(permissions, dict) or any(
            type(permissions.get(key)) is not bool for key in PERMISSION_KEYS
        ):
            raise ValueError("GitHub repository permissions are missing or not boolean")
        result["permissions"] = {key: permissions[key] for key in PERMISSION_KEYS}
        write_role = any(permissions[key] for key in ("push", "maintain", "admin"))
        if not permissions["pull"] and not write_role:
            raise ValueError("GitHub repository permissions establish no read or write access")
        result["ok"] = True
        result["repositoryWriteRole"] = write_role
        if write_role:
            result["status"] = "unverified"
            result["rerunCapability"] = "not_established"
            result["warnings"] = [
                f"{actor} has a write role on {repo}, but this read-only probe cannot "
                "prove token-level Actions write permission; upstream CI reruns remain unverified"
            ]
        else:
            result["status"] = "degraded"
            result["rerunCapability"] = "unavailable"
            result["warnings"] = [
                f"{actor} has no upstream write role on {repo}; a maintainer must rerun CI jobs. "
                "Local fixes and fork PRs remain possible; do not retry upstream reruns as this actor"
            ]
    except ValueError as exc:
        result["error"] = str(exc)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="ChainSafe/lodestar")
    parser.add_argument("--expected", default="lodekeeper")
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = diagnose(args.repo, args.expected, args.timeout_seconds)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"CI_RERUN_DIAGNOSTIC: {result['repo']} {result['rerunCapability']}")
        for warning in result["warnings"]:
            print(f"Warning: {warning}")
        if result.get("error"):
            print(f"Error: {result['error']}")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
