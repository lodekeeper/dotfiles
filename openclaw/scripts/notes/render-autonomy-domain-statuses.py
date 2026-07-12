#!/usr/bin/env python3
"""Render autonomy-audit status lines from domain preflight JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SECTION_BY_DOMAIN = {
    "prReview": "PR review",
    "ciFix": "CI fix",
    "specImplementation": "Spec implementation",
    "devnetDebugging": "Devnet debugging",
}

EXPECTED_CHECKS = {
    "prReview": ["followupGuards", "githubActorBoundary"],
    "ciFix": [
        "detectorEntrypoint",
        "fixQualityGate",
        "runLogFetch",
        "githubActorBoundary",
        "gitIdentityBoundary",
    ],
    "specImplementation": ["prePrComplianceGate", "githubActorBoundary", "gitIdentityBoundary"],
    "devnetDebugging": ["devnetTriage", "devnetRoutingReadiness"],
}


def _load_payload(path: str) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("preflight JSON root must be an object")
    return payload


def _checks_by_domain(payload: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    checks: dict[str, dict[str, dict[str, Any]]] = {}
    for raw_check in payload.get("checks") or []:
        if not isinstance(raw_check, dict):
            continue
        domain = raw_check.get("domain")
        name = raw_check.get("name")
        if not isinstance(domain, str) or not isinstance(name, str):
            continue
        checks.setdefault(domain, {})[name] = raw_check
    return checks


def _check_ok(check: dict[str, Any] | None) -> bool:
    if check is None:
        return False
    if check.get("ok") is not True:
        return False
    stdout = check.get("stdout")
    if isinstance(stdout, dict) and stdout.get("ok") is False:
        return False
    return True


def _failed_check_names(domain_checks: dict[str, dict[str, Any]], expected_names: list[str]) -> list[str]:
    return [
        name
        for name in expected_names
        if not _check_ok(domain_checks.get(name))
    ]


def _failure_detail(check: dict[str, Any] | None) -> str | None:
    if check is None:
        return "missing"

    stdout = check.get("stdout")
    if isinstance(stdout, dict):
        error = stdout.get("error")
        if isinstance(error, str) and error.strip():
            return error.strip()

        panda = stdout.get("panda")
        if isinstance(panda, dict):
            error = panda.get("error")
            if isinstance(error, str) and error.strip():
                return error.strip()

    stderr = check.get("stderr")
    if isinstance(stderr, str) and stderr.strip():
        return stderr.strip()

    return None


def _failure_summary(domain_checks: dict[str, dict[str, Any]], failed_names: list[str]) -> str:
    details: list[str] = []
    for name in failed_names:
        detail = _failure_detail(domain_checks.get(name))
        if detail:
            details.append(f"{name}: {detail}")

    if not details:
        return ""

    return f" Details: {'; '.join(details)}."


def _warning_text(checks: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for check in checks:
        for warning in check.get("warnings") or []:
            if isinstance(warning, str) and warning not in warnings:
                warnings.append(warning)
    return warnings


def _code_identifier(value: str) -> str:
    return f"`{value}`"


def _code_list(values: list[str]) -> str:
    return ", ".join(_code_identifier(value) for value in values)


def _format_warning(value: str) -> str:
    return value.replace("OPENAI_API_KEY", _code_identifier("OPENAI_API_KEY")).replace(
        "GRAFANA_TOKEN",
        _code_identifier("GRAFANA_TOKEN"),
    )


def _actor(check: dict[str, Any] | None) -> str:
    stdout = (check or {}).get("stdout")
    if isinstance(stdout, dict):
        actual = stdout.get("actual")
        expected = stdout.get("expected")
        if isinstance(actual, str) and isinstance(expected, str) and actual == expected:
            return actual
    return "expected account"


def _devnet_details(domain_checks: dict[str, dict[str, Any]]) -> tuple[str | None, list[str]]:
    triage_stdout = (domain_checks.get("devnetTriage") or {}).get("stdout")
    routing_stdout = (domain_checks.get("devnetRoutingReadiness") or {}).get("stdout")

    grafana_note: str | None = None
    if isinstance(triage_stdout, dict):
        grafana = triage_stdout.get("grafana")
        if isinstance(grafana, dict) and grafana.get("available") is False:
            missing = grafana.get("missing") or []
            if "GRAFANA_TOKEN" in missing:
                grafana_note = "`GRAFANA_TOKEN` is absent, so telemetry remains optional/local-only"

    panda_names: list[str] = []
    if isinstance(routing_stdout, dict):
        panda = routing_stdout.get("panda")
        if isinstance(panda, dict) and panda.get("state") == "ready":
            names = panda.get("names") or []
            panda_names = [name for name in names if isinstance(name, str)]

    return grafana_note, panda_names


def render_statuses(payload: dict[str, Any]) -> dict[str, str]:
    checks_by_domain = _checks_by_domain(payload)
    statuses: dict[str, str] = {}

    for domain, section in SECTION_BY_DOMAIN.items():
        expected_names = EXPECTED_CHECKS[domain]
        domain_checks = checks_by_domain.get(domain, {})
        failed = _failed_check_names(domain_checks, expected_names)
        checks = [domain_checks[name] for name in expected_names if name in domain_checks]
        warnings = _warning_text(checks)

        if failed:
            failure_summary = _failure_summary(domain_checks, failed)
            statuses[section] = " ".join(
                part
                for part in [
                    f"BLOCKER: domain preflight check(s) failed or were missing: {', '.join(failed)}.",
                    failure_summary,
                    "Proposed fix: inspect the failing preflight JSON/stderr before continuing autonomous work in this domain.",
                ]
                if part
            )
            continue

        if domain == "prReview":
            actor = _actor(domain_checks.get("githubActorBoundary"))
            statuses[section] = (
                f"follow-up guard and GitHub actor-boundary preflights verified from current preflight output "
                f"as `{actor}`; no new PR-review blocker discovered this cycle."
            )
        elif domain == "ciFix":
            status = (
                "detector entrypoint, fix-quality gate, run-log fetch, GitHub actor-boundary, and git identity preflights verified from current preflight output; "
                "no new CI-fix blocker discovered this cycle."
            )
            if warnings:
                status += f" Warning: {'; '.join(_format_warning(warning) for warning in warnings)}."
            statuses[section] = status
        elif domain == "specImplementation":
            actor = _actor(domain_checks.get("githubActorBoundary"))
            statuses[section] = (
                "pre-PR compliance gate, GitHub actor-boundary, and git identity preflights verified from current preflight output "
                f"as `{actor}`; no new spec-implementation blocker discovered this cycle."
            )
        elif domain == "devnetDebugging":
            grafana_note, panda_names = _devnet_details(domain_checks)
            details: list[str] = []
            if grafana_note:
                details.append(grafana_note)
            if panda_names:
                details.append(f"panda datasource discovery is ready ({_code_list(panda_names)})")
            suffix = f" {'; '.join(details)}." if details else ""
            statuses[section] = (
                "devnet-triage JSON preflight and local/remote routing readiness verified from current preflight output; "
                f"no new devnet-debugging blocker discovered this cycle.{suffix}"
            )

    missing_sections = [
        section
        for section in SECTION_BY_DOMAIN.values()
        if section not in statuses
    ]
    if missing_sections:
        raise ValueError(f"missing rendered status for section(s): {', '.join(missing_sections)}")

    return statuses


def main() -> int:
    parser = argparse.ArgumentParser(description="Render daily autonomy-audit statuses from preflight JSON")
    parser.add_argument("--preflight-json", required=True, help="Path to check-autonomy-domain-preflights.py --json output")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload with section statuses")
    args = parser.parse_args()

    payload = _load_payload(args.preflight_json)
    statuses = render_statuses(payload)
    rendered = {
        "ok": payload.get("ok") is True and not any(value.startswith("BLOCKER:") for value in statuses.values()),
        "statuses": statuses,
    }

    if args.json:
        print(json.dumps(rendered, indent=2, sort_keys=True))
    else:
        for section, status in statuses.items():
            print(f"{section}: {status}")

    return 0 if rendered["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
