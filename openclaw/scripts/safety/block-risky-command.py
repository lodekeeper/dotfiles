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
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
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


def load_touched_paths(paths: list[str]) -> set[str]:
    touched: set[str] = set()
    for raw_path in paths:
        if raw_path:
            touched.add(os.path.abspath(os.path.expanduser(raw_path)))
    return touched


def load_touched_paths_file(path: str | None) -> set[str]:
    if not path:
        return set()

    touched: set[str] = set()
    try:
        lines = Path(path).read_text(encoding="utf8").splitlines()
    except FileNotFoundError:
        return touched

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            touched.add(os.path.abspath(os.path.expanduser(line)))
            continue
        if not isinstance(item, dict):
            continue
        action = item.get("action")
        raw_path = item.get("path")
        if action in {"read", "created", "wrote", "touched"} and isinstance(raw_path, str):
            touched.add(os.path.abspath(os.path.expanduser(raw_path)))
    return touched


def command_parts(command: str) -> list[list[str]]:
    parts: list[list[str]] = []
    for raw_part in re.split(r"[;&|()\n]+", command):
        raw_part = raw_part.strip()
        if not raw_part:
            continue
        try:
            part = shlex.split(raw_part)
        except ValueError:
            continue
        if part:
            parts.append(part)
    return parts


def destructive_targets(command: str) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    for part in command_parts(command):
        if part[0] == "sudo":
            part = part[1:]
        if not part:
            continue

        command_name = part[0]
        args = part[1:]
        if command_name == "gio" and args[:1] == ["trash"]:
            command_name = "gio trash"
            args = args[1:]

        if command_name not in {"rm", "trash", "trash-put", "gio trash"}:
            continue

        end_of_options = False
        for arg in args:
            if not end_of_options and arg == "--":
                end_of_options = True
                continue
            if not end_of_options and arg.startswith("-"):
                continue
            targets.append(
                {
                    "command": command_name,
                    "path": arg,
                    "absolutePath": os.path.abspath(os.path.expanduser(arg)),
                }
            )
    return targets


def evaluate_warn_only(command: str, *, touched_paths: set[str]) -> dict[str, Any]:
    matches = find_matches(command)
    targets = destructive_targets(command)
    unverified_targets = [
        target for target in targets if target["absolutePath"] not in touched_paths
    ]
    broad_matches = [
        match
        for match in matches
        if match["name"] not in {"rm", "trash", "gio-trash"}
    ]
    should_warn = bool(unverified_targets or broad_matches)

    message = "command accepted"
    if unverified_targets:
        target_list = ", ".join(target["path"] for target in unverified_targets)
        message = (
            "warn-only risky command check: destructive target(s) were not marked "
            f"read/created in this session: {target_list}"
        )
    elif broad_matches:
        names = ", ".join(match["name"] for match in broad_matches)
        message = f"warn-only risky command check: broad state command pattern(s): {names}"

    return {
        "ok": True,
        "shouldWarn": should_warn,
        "matches": matches,
        "targets": targets,
        "unverifiedTargets": unverified_targets,
        "message": message,
    }


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
        ('rm -f /tmp/example; echo "SKIPPED-DO-NOT-RUN"', False),
        ('rm -f /tmp/example && echo "noop"', False),
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


def run_warn_self_test() -> tuple[bool, list[dict[str, Any]]]:
    touched = {"/tmp/read-before"}
    cases = [
        ("sed -n '1,20p' BACKLOG.md", False),
        ("rm -f /tmp/read-before", False),
        ("rm -f /tmp/unread-after-task", True),
        ('rm -f /tmp/unread-after-task; echo "SKIPPED-DO-NOT-RUN"', True),
        ("trash-put /tmp/unread-after-task", True),
        ("gio trash /tmp/unread-after-task", True),
        ("git stash && pnpm test", True),
    ]

    results: list[dict[str, Any]] = []
    ok = True
    for command, expected_warn in cases:
        result = evaluate_warn_only(command, touched_paths=touched)
        actual_warn = result["shouldWarn"]
        passed = actual_warn is expected_warn
        ok = ok and passed
        results.append(
            {
                "command": command,
                "expectedWarn": expected_warn,
                "actualWarn": actual_warn,
                "passed": passed,
                "unverifiedTargets": result["unverifiedTargets"],
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
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Warn about risky commands but always exit successfully",
    )
    parser.add_argument(
        "--touched-path",
        action="append",
        default=[],
        help="Path read or created in this session; repeatable for warn-only checks",
    )
    parser.add_argument(
        "--touched-paths-file",
        help="Line- or JSONL-formatted paths read or created in this session for warn-only checks",
    )
    args = parser.parse_args()

    if args.self_test:
        ok, cases = run_warn_self_test() if args.warn_only else run_self_test()
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

    if args.warn_only:
        touched_paths = load_touched_paths(args.touched_path)
        touched_paths.update(load_touched_paths_file(args.touched_paths_file))
        payload = evaluate_warn_only(command, touched_paths=touched_paths)
        print_payload(payload, as_json=args.json)
        return 0

    payload = evaluate(command)
    print_payload(payload, as_json=args.json)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
