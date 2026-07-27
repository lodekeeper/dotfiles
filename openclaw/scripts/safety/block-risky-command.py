#!/usr/bin/env python3
"""Block risky cleanup/state commands before a shell tool runs.

This is intentionally small and side-effect free so it can be used from a
PreToolUse hook later, or from autonomy preflights now. It reads a command from
--command or common JSON hook payload shapes on stdin.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any


ALLOW_ENV = "LODEKEEPER_ALLOW_RISKY_COMMAND"


@dataclass(frozen=True)
class RiskPattern:
    name: str
    pattern: re.Pattern[str]
    reason: str


COMMAND_PREFIX = r"(?:^|[;&|()\n]\s*)(?:sudo\s+)?"

RISK_PATTERNS = [
    RiskPattern(
        "rm",
        re.compile(COMMAND_PREFIX + r"rm\b", re.MULTILINE),
        "`rm` deletes immediately and has caused repeated end-of-turn cleanup mistakes",
    ),
    RiskPattern(
        "trash",
        re.compile(COMMAND_PREFIX + r"(?:trash|trash-put)\b", re.MULTILINE),
        "`trash`/`trash-put` are still destructive when used as reflexive cleanup",
    ),
    RiskPattern(
        "gio-trash",
        re.compile(COMMAND_PREFIX + r"gio\s+trash\b", re.MULTILINE),
        "`gio trash` is destructive when used as reflexive cleanup",
    ),
    RiskPattern(
        "git-stash",
        re.compile(COMMAND_PREFIX + r"git\s+stash\b", re.MULTILINE),
        "`git stash` can sweep unrelated dirty worktree state",
    ),
    RiskPattern(
        "git-clean",
        re.compile(COMMAND_PREFIX + r"git\s+clean\b", re.MULTILINE),
        "`git clean` removes untracked files",
    ),
    RiskPattern(
        "git-reset-hard",
        re.compile(COMMAND_PREFIX + r"git\s+reset\s+--hard\b", re.MULTILINE),
        "`git reset --hard` discards worktree state",
    ),
    RiskPattern(
        "git-checkout-paths",
        re.compile(COMMAND_PREFIX + r"git\s+checkout\s+--\s+", re.MULTILINE),
        "`git checkout -- <path>` discards local file changes",
    ),
]


def nested_get(data: dict[str, Any], path: tuple[str, ...]) -> str | None:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, str) and current.strip() else None


def command_from_stdin() -> str | None:
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    if not isinstance(data, dict):
        return None

    candidate_paths = [
        ("command",),
        ("cmd",),
        ("tool_input", "command"),
        ("tool_input", "cmd"),
        ("toolInput", "command"),
        ("toolInput", "cmd"),
        ("arguments", "command"),
        ("arguments", "cmd"),
    ]
    for path in candidate_paths:
        command = nested_get(data, path)
        if command:
            return command
    return None


def find_matches(command: str) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for risk in RISK_PATTERNS:
        if risk.pattern.search(command):
            matches.append(
                {
                    "name": risk.name,
                    "reason": risk.reason,
                }
            )
    return matches


def evaluate(command: str) -> dict[str, Any]:
    matches = find_matches(command)
    allowed = os.environ.get(ALLOW_ENV) == "1"
    ok = not matches or allowed
    message = "command accepted"
    if matches and allowed:
        message = f"risky command allowed because {ALLOW_ENV}=1"
    elif matches:
        names = ", ".join(match["name"] for match in matches)
        message = (
            f"blocked risky command pattern(s): {names}. "
            "Use a narrower non-destructive method, or get explicit approval before bypassing."
        )
    return {
        "ok": ok,
        "allowedByEnv": allowed,
        "allowEnv": ALLOW_ENV,
        "matches": matches,
        "message": message,
    }


def run_self_test() -> tuple[bool, list[dict[str, Any]]]:
    cases = [
        ("git status --short", True),
        ("sed -n '1,20p' BACKLOG.md", True),
        ("bash scripts/notes/run-daily-autonomy-audit.sh --response-only", True),
        ("rm -f /tmp/example", False),
        ("trash-put /tmp/example", False),
        ("gio trash /tmp/example", False),
        ("git stash && pnpm test", False),
        ("git reset --hard", False),
        ("git checkout -- packages/foo.ts", False),
        ("git clean -fd", False),
    ]

    results: list[dict[str, Any]] = []
    ok = True
    for command, expected_ok in cases:
        result = evaluate(command)
        actual_ok = result["ok"]
        passed = actual_ok is expected_ok
        ok = ok and passed
        results.append(
            {
                "command": command,
                "expectedOk": expected_ok,
                "actualOk": actual_ok,
                "passed": passed,
                "matches": result["matches"],
            }
        )
    return ok, results


def print_payload(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(payload["message"])
    for match in payload.get("matches") or []:
        print(f"- {match['name']}: {match['reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Block risky shell cleanup/state commands")
    parser.add_argument("--command", help="Command string to evaluate")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    parser.add_argument("--self-test", action="store_true", help="Run built-in side-effect-free checks")
    args = parser.parse_args()

    if args.self_test:
        ok, cases = run_self_test()
        payload = {
            "ok": ok,
            "message": "risky-command guard self-test passed" if ok else "risky-command guard self-test failed",
            "cases": cases,
        }
        print_payload(payload, as_json=args.json)
        return 0 if ok else 1

    command = args.command or command_from_stdin()
    if not command:
        print("no command provided via --command or stdin", file=sys.stderr)
        return 1

    payload = evaluate(command)
    print_payload(payload, as_json=args.json)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
