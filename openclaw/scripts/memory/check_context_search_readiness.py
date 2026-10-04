#!/usr/bin/env python3
"""Check that durable memory search is ready for autonomous work."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


DEFAULT_QUERY = "autonomy"
RESULT_LINE = re.compile(r"^\d+\.\s+")


def _truncate(value: str, limit: int = 1000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n... truncated {len(value) - limit} chars ..."


def _run(command: list[str], *, cwd: Path, timeout_s: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
        return {
            "returnCode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timedOut": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returnCode": None,
            "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
            "stderr": f"timed out after {timeout_s}s",
            "timedOut": True,
        }


def _check_qmd(*, workspace: Path, query: str, timeout_s: int) -> dict[str, Any]:
    qmd_path = shutil.which("qmd")
    if qmd_path is None:
        return {
            "available": False,
            "searchOk": False,
            "resultCount": 0,
            "error": "qmd executable not found",
        }

    result = _run(
        ["qmd", "search", query, "-n", "1", "--json"],
        cwd=workspace,
        timeout_s=timeout_s,
    )
    payload: Any = None
    parse_error: str | None = None
    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        parse_error = str(exc)

    result_count = len(payload) if isinstance(payload, list) else 0
    first_file = None
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        raw_file = payload[0].get("file")
        if isinstance(raw_file, str):
            first_file = raw_file

    search_ok = result["returnCode"] == 0 and parse_error is None and result_count > 0
    rendered: dict[str, Any] = {
        "available": True,
        "path": qmd_path,
        "searchOk": search_ok,
        "resultCount": result_count,
        "returnCode": result["returnCode"],
    }
    if first_file:
        rendered["firstFile"] = first_file
    if parse_error:
        rendered["error"] = f"could not parse qmd JSON: {parse_error}"
    elif result["returnCode"] != 0:
        rendered["error"] = _truncate(result["stderr"].strip() or result["stdout"].strip())
    return rendered


def _check_fallback(*, workspace: Path, query: str, timeout_s: int) -> dict[str, Any]:
    script = workspace / "scripts/memory/query_index.py"
    if not script.exists():
        return {
            "available": False,
            "searchOk": False,
            "resultCount": 0,
            "error": f"fallback script not found: {script}",
        }

    result = _run(
        [sys.executable, str(script), query, "--limit", "1"],
        cwd=workspace,
        timeout_s=timeout_s,
    )
    lines = [line for line in result["stdout"].splitlines() if RESULT_LINE.match(line)]
    search_ok = result["returnCode"] == 0 and bool(lines)
    rendered: dict[str, Any] = {
        "available": True,
        "searchOk": search_ok,
        "resultCount": len(lines),
        "returnCode": result["returnCode"],
    }
    if not search_ok:
        rendered["error"] = _truncate(result["stderr"].strip() or result["stdout"].strip())
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description="Check QMD and fallback memory-search readiness")
    parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parents[2]),
        help="Workspace root (default: script-relative workspace)",
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Stable query used for readiness checks")
    parser.add_argument("--timeout-seconds", type=int, default=12, help="Per-search timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    qmd = _check_qmd(workspace=workspace, query=args.query, timeout_s=args.timeout_seconds)
    fallback = _check_fallback(workspace=workspace, query=args.query, timeout_s=args.timeout_seconds)
    ok = qmd.get("searchOk") is True and fallback.get("searchOk") is True
    payload = {
        "ok": ok,
        "status": "ready" if ok else "blocked",
        "query": args.query,
        "qmd": qmd,
        "fallback": fallback,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif ok:
        print(
            "MEMORY_CONTEXT_SEARCH_READY: "
            f"qmd_results={qmd['resultCount']} fallback_results={fallback['resultCount']}"
        )
    else:
        print("MEMORY_CONTEXT_SEARCH_BLOCKED", file=sys.stderr)
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
