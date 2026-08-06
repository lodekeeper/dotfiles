#!/usr/bin/env python3
"""Block obvious idle/end-of-task placeholder tool calls.

This is intentionally side-effect free so it can be used from future tool hooks,
or from autonomy preflights now. It catches the small class of calls that are
neither domain work nor useful polling: bare no-op shell commands, cron
wakeup-cancel calls without a pending wakeup, empty review finding reports
outside a review, malformed monitor calls, and placeholder tool-discovery
queries.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


NOOP_SHELL_COMMANDS = {
    ":",
    "true",
    "echo done",
    "echo noop",
    "echo no_reply",
    "echo skipped",
}

PLACEHOLDER_LABELS = {
    "noop",
    "no-op",
    "noop placeholder",
    "no-op placeholder",
    "placeholder",
    "test",
}

NON_REVIEW_CONTEXTS = {"cron", "background-wait", "background_wait", "general"}


def _nested_get(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _load_payload(raw: str) -> tuple[str | None, dict[str, Any] | None]:
    if not raw.strip():
        return None, None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, {"command": raw.strip()}

    if not isinstance(data, dict):
        return None, None

    name_candidates = [
        ("tool_name",),
        ("toolName",),
        ("name",),
        ("tool",),
        ("recipient_name",),
    ]
    input_candidates = [
        ("tool_input",),
        ("toolInput",),
        ("arguments",),
        ("args",),
        ("parameters",),
        ("input",),
    ]

    tool_name = next(
        (
            value
            for path in name_candidates
            if isinstance((value := _nested_get(data, path)), str) and value.strip()
        ),
        None,
    )
    tool_input = next(
        (
            value
            for path in input_candidates
            if isinstance((value := _nested_get(data, path)), dict)
        ),
        None,
    )

    if tool_input is None and any(key in data for key in ("cmd", "command", "stop", "findings", "query")):
        tool_input = data

    return tool_name, tool_input


def _tool_key(tool_name: str) -> str:
    last_segment = re.split(r"[./:]", tool_name)[-1]
    return re.sub(r"[^a-z0-9]", "", last_segment.lower())


def _is_shell_tool(tool_key: str) -> bool:
    return tool_key in {
        "bash",
        "shell",
        "exec",
        "execcommand",
        "runcommand",
        "runterminalcommand",
    }


def _command_from_input(tool_input: dict[str, Any]) -> str | None:
    for key in ("cmd", "command"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _label_from_input(tool_input: dict[str, Any]) -> str | None:
    for key in ("description", "justification", "reason", "label"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def _canonical_shell(command: str) -> str:
    command = re.sub(r"\s+", " ", command.strip())
    command = command.split("#", 1)[0].strip()
    return command.lower()


def find_risks(tool_name: str, tool_input: dict[str, Any], *, context: str) -> list[dict[str, str]]:
    key = _tool_key(tool_name)
    risks: list[dict[str, str]] = []

    if _is_shell_tool(key):
        command = _command_from_input(tool_input)
        label = _label_from_input(tool_input)
        if command and _canonical_shell(command) in NOOP_SHELL_COMMANDS:
            risks.append(
                {
                    "name": "noop-shell-command",
                    "reason": "bare no-op shell commands are an idle/padding tool-call pattern",
                }
            )
        if label in PLACEHOLDER_LABELS:
            risks.append(
                {
                    "name": "placeholder-tool-label",
                    "reason": "placeholder/no-op labels have repeatedly accompanied unintended end-of-task tool calls",
                }
            )

    if key == "schedulewakeup":
        stop_value = tool_input.get("stop")
        has_target = any(tool_input.get(key_name) for key_name in ("id", "wakeup_id", "wakeupId"))
        if stop_value is True and not has_target and context in NON_REVIEW_CONTEXTS:
            risks.append(
                {
                    "name": "cron-stop-wakeup-without-target",
                    "reason": "stop-only wakeup calls in cron/background-wait context are usually inert filler",
                }
            )

    if key == "monitor":
        missing = [
            name
            for name in ("description", "timeout_ms", "persistent")
            if name not in tool_input
        ]
        if missing:
            risks.append(
                {
                    "name": "malformed-monitor-call",
                    "reason": f"monitor call is missing required field(s): {', '.join(missing)}",
                }
            )

    if key == "reportfindings":
        findings = tool_input.get("findings")
        if findings == [] and context in NON_REVIEW_CONTEXTS:
            risks.append(
                {
                    "name": "empty-report-findings-outside-review",
                    "reason": "empty code-review finding reports are not useful outside an active review",
                }
            )

    if key in {"toolsearch", "toolsearchtool"}:
        query = tool_input.get("query")
        if isinstance(query, str) and query.strip().lower() in PLACEHOLDER_LABELS:
            risks.append(
                {
                    "name": "placeholder-tool-search-query",
                    "reason": "placeholder tool-discovery queries are an idle/padding tool-call pattern",
                }
            )

    return risks


def evaluate(tool_name: str, tool_input: dict[str, Any], *, context: str) -> dict[str, Any]:
    risks = find_risks(tool_name, tool_input, context=context)
    return {
        "ok": not risks,
        "context": context,
        "toolName": tool_name,
        "risks": risks,
        "message": "tool call accepted"
        if not risks
        else "blocked idle/placeholder tool-call pattern(s): "
        + ", ".join(risk["name"] for risk in risks),
    }


def run_self_test() -> tuple[bool, list[dict[str, Any]]]:
    cases: list[tuple[str, dict[str, Any], str, bool]] = [
        ("functions.exec_command", {"cmd": "sed -n '1,20p' BACKLOG.md"}, "cron", True),
        ("functions.exec_command", {"cmd": "true"}, "cron", False),
        ("Bash", {"command": "echo done", "description": "noop placeholder"}, "cron", False),
        ("ScheduleWakeup", {"stop": True}, "cron", False),
        ("ScheduleWakeup", {"stop": True, "id": "known-wakeup"}, "cron", True),
        (
            "Monitor",
            {"description": "wait for sweep", "timeout_ms": 120000, "persistent": False},
            "cron",
            True,
        ),
        ("Monitor", {}, "cron", False),
        ("ReportFindings", {"findings": []}, "cron", False),
        ("ReportFindings", {"findings": []}, "code-review", True),
        ("tool_search.tool_search_tool", {"query": "placeholder", "limit": 1}, "cron", False),
        ("tool_search.tool_search_tool", {"query": "skill_workshop", "limit": 1}, "cron", True),
    ]

    results: list[dict[str, Any]] = []
    ok = True
    for tool_name, tool_input, context, expected_ok in cases:
        result = evaluate(tool_name, tool_input, context=context)
        actual_ok = result["ok"]
        passed = actual_ok is expected_ok
        ok = ok and passed
        results.append(
            {
                "toolName": tool_name,
                "toolInput": tool_input,
                "context": context,
                "expectedOk": expected_ok,
                "actualOk": actual_ok,
                "passed": passed,
                "risks": result["risks"],
            }
        )
    return ok, results


def print_payload(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print(payload["message"])
    for risk in payload.get("risks") or []:
        print(f"- {risk['name']}: {risk['reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Block idle/placeholder tool calls")
    parser.add_argument("--tool-name", help="Tool name to evaluate")
    parser.add_argument("--tool-input-json", help="JSON object with the proposed tool input")
    parser.add_argument(
        "--context",
        default="general",
        help="Execution context hint, e.g. cron, background-wait, code-review",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    parser.add_argument("--self-test", action="store_true", help="Run built-in side-effect-free checks")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Warn about idle tool calls but always exit successfully",
    )
    args = parser.parse_args()

    if args.self_test:
        ok, cases = run_self_test()
        payload = {
            "ok": ok,
            "message": "idle-tool-call guard self-test passed"
            if ok
            else "idle-tool-call guard self-test failed",
            "cases": cases,
        }
        print_payload(payload, as_json=args.json)
        return 0 if ok else 1

    tool_name = args.tool_name
    tool_input: dict[str, Any] | None = None
    if args.tool_input_json:
        try:
            tool_input = json.loads(args.tool_input_json)
        except json.JSONDecodeError as exc:
            print(f"invalid --tool-input-json: {exc}", file=sys.stderr)
            return 1
        if not isinstance(tool_input, dict):
            print("--tool-input-json must decode to an object", file=sys.stderr)
            return 1
    else:
        stdin_name, stdin_input = _load_payload(sys.stdin.read())
        tool_name = tool_name or stdin_name
        tool_input = stdin_input

    if not tool_name:
        print("no tool name provided via --tool-name or stdin payload", file=sys.stderr)
        return 1
    if tool_input is None:
        print("no tool input object provided via --tool-input-json or stdin payload", file=sys.stderr)
        return 1

    payload = evaluate(tool_name, tool_input, context=args.context)
    if args.warn_only:
        payload["ok"] = True
        payload["shouldWarn"] = bool(payload["risks"])

    print_payload(payload, as_json=args.json)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
