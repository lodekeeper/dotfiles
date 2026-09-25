#!/usr/bin/env python3
"""Detect structured health drift in autonomy-audit domain preflights."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

SIGNATURE_VERSION = 1
DEFAULT_STATE_FILE = "state/autonomy-domain-preflight-health.json"
SIGNIFICANT_STDOUT_KEYS = {
    "actual",
    "available",
    "error",
    "expected",
    "message",
    "missing",
    "names",
    "ok",
    "state",
    "status",
    "version",
}


def _load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _compact_value(value: Any) -> Any:
    if _scalar(value):
        return value

    if isinstance(value, list):
        compacted = [_compact_value(item) for item in value if _scalar(item)]
        return sorted(compacted, key=lambda item: json.dumps(item, sort_keys=True))[:40]

    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        for key, child in sorted(value.items()):
            if key not in SIGNIFICANT_STDOUT_KEYS and not isinstance(child, dict):
                continue
            child_value = _compact_value(child)
            if child_value not in ({}, []):
                compacted[key] = child_value
        return compacted

    return repr(value)


def _check_key(check: dict[str, Any]) -> str | None:
    domain = check.get("domain")
    name = check.get("name")
    if not isinstance(domain, str) or not isinstance(name, str):
        return None
    return f"{domain}/{name}"


def _warnings(check: dict[str, Any]) -> list[str]:
    warnings = check.get("warnings")
    if not isinstance(warnings, list):
        return []
    return sorted({warning for warning in warnings if isinstance(warning, str)})


def _failure_stderr(check: dict[str, Any]) -> str | None:
    if check.get("ok") is True:
        return None
    stderr = check.get("stderr")
    if not isinstance(stderr, str):
        return None
    return stderr.strip()[:500] or None


def _check_signature(check: dict[str, Any]) -> dict[str, Any]:
    signature: dict[str, Any] = {
        "ok": check.get("ok") is True,
        "returnCode": check.get("returnCode"),
        "warnings": _warnings(check),
    }

    stdout = check.get("stdout")
    if isinstance(stdout, dict):
        compact_stdout = _compact_value(stdout)
        if compact_stdout:
            signature["stdout"] = compact_stdout
    elif check.get("ok") is not True and isinstance(stdout, str) and stdout.strip():
        signature["stdoutText"] = stdout.strip()[:500]

    stderr = _failure_stderr(check)
    if stderr:
        signature["stderr"] = stderr

    return signature


def build_signature(payload: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for raw_check in payload.get("checks") or []:
        if not isinstance(raw_check, dict):
            continue
        key = _check_key(raw_check)
        if key:
            checks[key] = _check_signature(raw_check)

    selected_domains = payload.get("selectedDomains")
    if not isinstance(selected_domains, list):
        selected_domains = []

    return {
        "version": SIGNATURE_VERSION,
        "ok": payload.get("ok") is True,
        "options": {
            "expectedGitHubActor": payload.get("expectedGitHubActor"),
            "requireDevnetGrafana": payload.get("requireDevnetGrafana") is True,
            "selectedDomains": sorted(domain for domain in selected_domains if isinstance(domain, str)),
            "strictCiApiKey": payload.get("strictCiApiKey") is True,
        },
        "checks": checks,
    }


def _state_signature(payload: dict[str, Any]) -> dict[str, Any] | None:
    signature = payload.get("signature")
    if isinstance(signature, dict):
        return signature
    if "checks" in payload and "version" in payload:
        return payload
    return None


def load_previous_signature(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _load_json(str(path))
    return _state_signature(payload)


def diff_signatures(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if previous is None:
        return {
            "initialized": True,
            "hasDrift": True,
            "addedChecks": sorted((current.get("checks") or {}).keys()),
            "removedChecks": [],
            "changedChecks": [],
            "optionsChanged": False,
            "okChanged": False,
        }

    previous_checks = previous.get("checks") if isinstance(previous.get("checks"), dict) else {}
    current_checks = current.get("checks") if isinstance(current.get("checks"), dict) else {}

    previous_names = set(previous_checks)
    current_names = set(current_checks)
    shared_names = sorted(previous_names & current_names)
    changed_checks = [
        name
        for name in shared_names
        if previous_checks.get(name) != current_checks.get(name)
    ]
    options_changed = previous.get("options") != current.get("options")
    ok_changed = previous.get("ok") != current.get("ok")

    return {
        "initialized": False,
        "hasDrift": bool(
            changed_checks
            or previous_names != current_names
            or options_changed
            or ok_changed
        ),
        "addedChecks": sorted(current_names - previous_names),
        "removedChecks": sorted(previous_names - current_names),
        "changedChecks": changed_checks,
        "optionsChanged": options_changed,
        "okChanged": ok_changed,
    }


def _code_list(values: list[str], *, limit: int = 6) -> str:
    if not values:
        return "none"
    rendered = ", ".join(f"`{value}`" for value in values[:limit])
    if len(values) > limit:
        rendered += f", +{len(values) - limit} more"
    return rendered


def render_status(diff: dict[str, Any], state_file: Path) -> str | None:
    if not diff.get("hasDrift"):
        return None

    if diff.get("initialized"):
        added = diff.get("addedChecks") or []
        return (
            "structured domain-preflight health baseline initialized "
            f"({len(added)} check(s)) in `{state_file}`. Proposed fix: future audits now compare "
            "structured preflight health before treating unchanged prose statuses as `NO_REPLY`."
        )

    parts: list[str] = []
    if diff.get("okChanged"):
        parts.append("overall ok state changed")
    if diff.get("optionsChanged"):
        parts.append("preflight options changed")
    if diff.get("addedChecks"):
        parts.append(f"added checks {_code_list(diff['addedChecks'])}")
    if diff.get("removedChecks"):
        parts.append(f"removed checks {_code_list(diff['removedChecks'])}")
    if diff.get("changedChecks"):
        parts.append(f"changed checks {_code_list(diff['changedChecks'])}")

    details = "; ".join(parts) or "signature changed"
    return (
        f"structured domain-preflight health drift detected: {details}. "
        "Proposed fix: inspect the changed preflight JSON/check output before treating unchanged "
        "rendered status text as a no-op."
    )


def write_state(path: Path, signature: dict[str, Any], diff: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "signature": signature,
        "lastDiff": diff,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check autonomy domain preflight health drift")
    parser.add_argument("--preflight-json", required=True, help="Path to domain preflight JSON")
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE, help="Persistent state JSON path")
    parser.add_argument("--update", action="store_true", help="Write the current signature to the state file")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable diff output")
    parser.add_argument("--quiet-no-change", action="store_true", help="Print nothing when no drift is detected")
    args = parser.parse_args()

    preflight = _load_json(args.preflight_json)
    current = build_signature(preflight)
    state_file = Path(args.state_file)
    previous = load_previous_signature(state_file)
    diff = diff_signatures(previous, current)

    if args.update:
        write_state(state_file, current, diff)

    status = render_status(diff, state_file)
    output = {
        "hasDrift": diff["hasDrift"],
        "stateFile": str(state_file),
        "diff": diff,
        "status": status,
    }

    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    elif status:
        print(status)
    elif not args.quiet_no_change:
        print("No structured domain-preflight health drift detected.")

    return 4 if diff["hasDrift"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
