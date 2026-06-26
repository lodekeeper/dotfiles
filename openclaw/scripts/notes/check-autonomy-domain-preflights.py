#!/usr/bin/env python3
"""Run side-effect-free preflights for the daily autonomy-audit domains."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


VALID_DOMAINS = [
    "prReview",
    "ciFix",
    "specImplementation",
    "devnetDebugging",
]


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... truncated {len(text) - limit} chars ..."


def _json_or_text(stdout: str) -> Any:
    stripped = stdout.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return _truncate(stripped)


def run_check(
    *,
    workspace: Path,
    domain: str,
    name: str,
    command: list[str],
    env: dict[str, str],
    timeout_s: int,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
        payload = _json_or_text(proc.stdout)
        ok = proc.returncode == 0
        if isinstance(payload, dict) and payload.get("ok") is False:
            ok = False
        return {
            "domain": domain,
            "name": name,
            "ok": ok,
            "returnCode": proc.returncode,
            "command": command,
            "stdout": payload,
            "stderr": _truncate(proc.stderr.strip()),
            "warnings": warnings or [],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "domain": domain,
            "name": name,
            "ok": False,
            "returnCode": None,
            "command": command,
            "stdout": _truncate((exc.stdout or "").strip() if isinstance(exc.stdout, str) else ""),
            "stderr": f"timed out after {timeout_s}s",
            "warnings": warnings or [],
        }


def build_checks(args: argparse.Namespace, workspace: Path) -> list[tuple[str, str, list[str], dict[str, str], list[str]]]:
    base_env = os.environ.copy()
    python = sys.executable

    ci_env = base_env.copy()
    ci_warnings: list[str] = []
    if not args.strict_ci_api_key and not ci_env.get("OPENAI_API_KEY"):
        ci_env["OPENAI_API_KEY"] = "autonomy-preflight-dummy-key"
        ci_warnings.append(
            "OPENAI_API_KEY was absent; used a dummy value to verify package/import readiness only"
        )

    devnet_command = [
        "bash",
        "scripts/debug/devnet-triage.sh",
        "autonomy-preflight",
        "--check-only",
        "--json",
    ]
    devnet_warnings: list[str] = []
    if args.require_devnet_grafana:
        devnet_command.append("--require-grafana")
    elif not base_env.get("GRAFANA_TOKEN"):
        devnet_warnings.append(
            "GRAFANA_TOKEN was absent; verified local devnet triage tooling only"
        )

    return [
        (
            "prReview",
            "followupGuards",
            ["bash", "scripts/review/run-followup-guards.sh", "--check-only", "--json"],
            base_env,
            [],
        ),
        (
            "prReview",
            "githubActorBoundary",
            [
                python,
                "scripts/github/check-gh-actor-boundary.py",
                "--expected",
                args.expected_github_actor,
                "--json",
            ],
            base_env,
            [],
        ),
        (
            "ciFix",
            "fixQualityGate",
            [python, "scripts/ci/check_fix_quality.py", "--check-only"],
            ci_env,
            ci_warnings,
        ),
        (
            "specImplementation",
            "prePrComplianceGate",
            ["bash", "scripts/spec/prepr-compliance-gate.sh", "--check-only", "--json"],
            base_env,
            [],
        ),
        (
            "devnetDebugging",
            "devnetTriage",
            devnet_command,
            base_env,
            devnet_warnings,
        ),
        (
            "devnetDebugging",
            "devnetRoutingReadiness",
            [
                python,
                "scripts/debug/check-devnet-routing-readiness.py",
                "--json",
                "--timeout",
                str(args.timeout_seconds),
            ],
            base_env,
            [],
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run side-effect-free preflights for autonomy-audit domains"
    )
    parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parents[2]),
        help="Workspace root (default: script-relative workspace)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    parser.add_argument(
        "--strict-ci-api-key",
        action="store_true",
        help="Require the real CI quality-gate OPENAI_API_KEY instead of using a dummy import preflight",
    )
    parser.add_argument(
        "--require-devnet-grafana",
        action="store_true",
        help="Require Grafana token/tooling for the devnet-debugging preflight",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="Per-check timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--expected-github-actor",
        default=os.environ.get("GITHUB_EXPECTED_ACTOR", "lodekeeper"),
        help="Expected GitHub login for write-action preflights (default: lodekeeper)",
    )
    parser.add_argument(
        "--domain",
        action="append",
        choices=VALID_DOMAINS,
        help="Run only the selected domain preflight; may be passed more than once",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    check_defs = build_checks(args, workspace)
    if args.domain:
        selected_domains = set(args.domain)
        check_defs = [
            check_def
            for check_def in check_defs
            if check_def[0] in selected_domains
        ]

    checks = [
        run_check(
            workspace=workspace,
            domain=domain,
            name=name,
            command=command,
            env=env,
            timeout_s=args.timeout_seconds,
            warnings=warnings,
        )
        for domain, name, command, env, warnings in check_defs
    ]
    payload = {
        "ok": all(check["ok"] for check in checks),
        "workspace": str(workspace),
        "strictCiApiKey": args.strict_ci_api_key,
        "requireDevnetGrafana": args.require_devnet_grafana,
        "expectedGitHubActor": args.expected_github_actor,
        "selectedDomains": args.domain or VALID_DOMAINS,
        "checks": checks,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for check in checks:
            status = "OK" if check["ok"] else "FAIL"
            print(f"{status} {check['domain']}/{check['name']} (rc={check['returnCode']})")
            for warning in check["warnings"]:
                print(f"  warning: {warning}")
            if not check["ok"] and check["stderr"]:
                print(f"  stderr: {check['stderr']}")
        print("Autonomy domain preflights OK" if payload["ok"] else "Autonomy domain preflights failed")

    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
