#!/usr/bin/env python3
"""Session state management for logskill."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml


STATE_VERSION = 1
SESSION_ROOT = Path.home() / ".cache" / "logskill" / "sessions"
SESSION_DIRS = ("raw", "reducers", "packs")
DURATION_RE = re.compile(r"(?P<value>\d+)(?P<unit>ms|s|m|h|d|w)")


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC time in ISO8601 Z format."""

    return utc_now().isoformat().replace("+00:00", "Z")


def parse_iso8601(value: str) -> datetime:
    """Parse an ISO8601 timestamp into a timezone-aware UTC datetime."""

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_duration(value: str) -> timedelta:
    """Parse a simple duration string like 30m or 2h15m."""

    if not value:
        raise ValueError("duration value is required")
    total = timedelta()
    position = 0
    for match in DURATION_RE.finditer(value):
        if match.start() != position:
            raise ValueError(f"invalid duration segment near {value[position:]!r}")
        amount = int(match.group("value"))
        unit = match.group("unit")
        if unit == "ms":
            total += timedelta(milliseconds=amount)
        elif unit == "s":
            total += timedelta(seconds=amount)
        elif unit == "m":
            total += timedelta(minutes=amount)
        elif unit == "h":
            total += timedelta(hours=amount)
        elif unit == "d":
            total += timedelta(days=amount)
        elif unit == "w":
            total += timedelta(weeks=amount)
        position = match.end()
    if position != len(value):
        raise ValueError(f"invalid duration value: {value!r}")
    return total


def format_duration(delta: timedelta) -> str:
    """Format a timedelta using a compact representation."""

    seconds = int(delta.total_seconds())
    if seconds < 0:
        return f"-{format_duration(-delta)}"
    units = (
        ("w", 7 * 24 * 3600),
        ("d", 24 * 3600),
        ("h", 3600),
        ("m", 60),
        ("s", 1),
    )
    parts: list[str] = []
    remaining = seconds
    for suffix, size in units:
        if remaining >= size:
            count, remaining = divmod(remaining, size)
            parts.append(f"{count}{suffix}")
    if not parts:
        return "0s"
    return "".join(parts)


def session_root(root: str | Path | None = None) -> Path:
    """Return the base directory for sessions."""

    if root is None:
        return SESSION_ROOT
    return Path(root).expanduser().resolve()


def session_dir(session_id: str, root: str | Path | None = None) -> Path:
    """Return the path for a session id."""

    if not session_id:
        raise ValueError("session id is required")
    return session_root(root) / session_id


def state_file(session_id: str, root: str | Path | None = None) -> Path:
    """Return the state file for a session."""

    return session_dir(session_id, root) / "state.yaml"


def ensure_session_dirs(path: Path) -> None:
    """Create the standard session directory layout."""

    path.mkdir(parents=True, exist_ok=True)
    for name in SESSION_DIRS:
        (path / name).mkdir(parents=True, exist_ok=True)


def default_state(session_id: str) -> dict[str, Any]:
    """Create a new default state document."""

    return {
        "version": STATE_VERSION,
        "session_id": session_id,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "sources": {},
        "cursors": {},
        "artifacts": {},
        "packs": {"overview": 0, "drill": 0, "compare": 0},
    }


def load_state(session_id: str, root: str | Path | None = None) -> dict[str, Any]:
    """Load the state document for a session."""

    path = state_file(session_id, root)
    if not path.exists():
        raise FileNotFoundError(f"session state does not exist: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid state format in {path}")
    data.setdefault("version", STATE_VERSION)
    data.setdefault("session_id", session_id)
    data.setdefault("sources", {})
    data.setdefault("cursors", {})
    data.setdefault("artifacts", {})
    data.setdefault("packs", {"overview": 0, "drill": 0, "compare": 0})
    for pack_kind in ("overview", "drill", "compare"):
        data["packs"].setdefault(pack_kind, 0)
    return data


def save_state(session_id: str, state: dict[str, Any], root: str | Path | None = None) -> Path:
    """Persist the state document atomically and return the file path."""

    path = state_file(session_id, root)
    ensure_session_dirs(path.parent)
    state["updated_at"] = utc_now_iso()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        yaml.safe_dump(state, handle, sort_keys=False)
        temp_name = handle.name
    Path(temp_name).replace(path)
    return path


def init_session(session_id: str, root: str | Path | None = None, force: bool = False) -> tuple[Path, dict[str, Any]]:
    """Initialize a session workspace and return its path and state."""

    path = session_dir(session_id, root)
    ensure_session_dirs(path)
    state_path = path / "state.yaml"
    if state_path.exists() and not force:
        return path, load_state(session_id, root)
    state = default_state(session_id)
    save_state(session_id, state, root)
    return path, state


def resolve_session_id(value: str | None) -> str:
    """Resolve a session id from the CLI or environment."""

    session_id = value or os.environ.get("LOGSKILL_SESSION")
    if not session_id:
        raise ValueError("session id is required via --session or LOGSKILL_SESSION")
    return session_id


def ensure_session(session_id: str, root: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    """Load an existing session or initialize it if missing."""

    path = session_dir(session_id, root)
    if not (path / "state.yaml").exists():
        return init_session(session_id, root=root, force=False)
    ensure_session_dirs(path)
    return path, load_state(session_id, root)


def sanitize_name(value: str) -> str:
    """Convert an arbitrary string into a filename-safe identifier."""

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    cleaned = cleaned.strip("-")
    return cleaned or "source"


def raw_file_path(session_id: str, source_id: str, root: str | Path | None = None) -> Path:
    """Return the raw JSONL path for a source id."""

    return session_dir(session_id, root) / "raw" / f"{sanitize_name(source_id)}.jsonl"


def artifact_path(session_id: str, relative: str, root: str | Path | None = None) -> Path:
    """Return a session artifact path."""

    return session_dir(session_id, root) / relative


def relative_session_path(path: Path, session_path: Path) -> str:
    """Return a session-relative string path."""

    return path.resolve().relative_to(session_path.resolve()).as_posix()


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    """Append rows to a JSONL file and return how many were written."""

    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False))
            handle.write("\n")
            count += 1
    return count


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    """Rewrite a JSONL file and return how many rows were written."""

    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False))
            handle.write("\n")
            count += 1
    return count


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield JSON records from a JSONL file."""

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL record: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            yield value


def count_jsonl(path: Path) -> int:
    """Count lines in a JSONL file without parsing them."""

    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def next_pack_path(session_id: str, pack_kind: str, extension: str = ".md", root: str | Path | None = None) -> Path:
    """Reserve the next pack file path for a given pack kind."""

    _, state = ensure_session(session_id, root=root)
    state["packs"][pack_kind] = int(state["packs"].get(pack_kind, 0)) + 1
    sequence = state["packs"][pack_kind]
    save_state(session_id, state, root=root)
    return session_dir(session_id, root) / "packs" / f"{pack_kind}-{sequence:03d}{extension}"


def update_source(
    state: dict[str, Any],
    source_id: str,
    *,
    kind: str,
    service: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Update source metadata in state."""

    state.setdefault("sources", {})
    existing = state["sources"].setdefault(source_id, {})
    existing["kind"] = kind
    if service:
        existing["service"] = service
    if metadata:
        existing.setdefault("metadata", {}).update(metadata)


def update_cursor(state: dict[str, Any], source_id: str, cursor: dict[str, Any]) -> None:
    """Update a cursor entry in state."""

    state.setdefault("cursors", {})
    state["cursors"][source_id] = cursor


def update_artifact(state: dict[str, Any], name: str, metadata: dict[str, Any]) -> None:
    """Update artifact metadata in state."""

    state.setdefault("artifacts", {})
    state["artifacts"][name] = metadata


def dump_pretty_json(data: Any) -> str:
    """Render JSON with stable formatting."""

    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for session state operations."""

    parser = argparse.ArgumentParser(description="Manage logskill session state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a session workspace.")
    init_parser.add_argument("session_id", help="Session identifier.")
    init_parser.add_argument("--force", action="store_true", help="Reset the state file if it exists.")
    init_parser.add_argument("--root", help="Override the session root directory.")

    status_parser = subparsers.add_parser("status", help="Show session state.")
    status_parser.add_argument("--session", dest="session_id", help="Session identifier.")
    status_parser.add_argument("--root", help="Override the session root directory.")
    status_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    cursor_parser = subparsers.add_parser("cursor", help="Update a source cursor entry.")
    cursor_parser.add_argument("--session", dest="session_id", required=True, help="Session identifier.")
    cursor_parser.add_argument("--root", help="Override the session root directory.")
    cursor_parser.add_argument("--source", required=True, help="Source id.")
    cursor_parser.add_argument("--cursor-json", required=True, help="Cursor JSON object.")

    return parser


def command_init(args: argparse.Namespace) -> int:
    """Handle the init command."""

    path, state = init_session(args.session_id, root=args.root, force=args.force)
    output = {
        "session_id": state["session_id"],
        "path": str(path),
        "created_at": state["created_at"],
    }
    print(dump_pretty_json(output))
    return 0


def summarize_status(session_id: str, root: str | Path | None = None) -> dict[str, Any]:
    """Create a summarized status payload for a session."""

    path, state = ensure_session(session_id, root=root)
    normalized_path = path / "normalized.jsonl"
    templates_path = path / "templates.json"
    raw_files = sorted((path / "raw").glob("*.jsonl"))
    packs = sorted((path / "packs").glob("*.md"))
    return {
        "session_id": session_id,
        "path": str(path),
        "updated_at": state.get("updated_at"),
        "sources": list(sorted(state.get("sources", {}).keys())),
        "raw_files": [f.name for f in raw_files],
        "normalized_exists": normalized_path.exists(),
        "templates_exists": templates_path.exists(),
        "pack_count": len(packs),
        "artifacts": state.get("artifacts", {}),
        "cursors": state.get("cursors", {}),
    }


def command_status(args: argparse.Namespace) -> int:
    """Handle the status command."""

    session_id = resolve_session_id(args.session_id)
    summary = summarize_status(session_id, root=args.root)
    if args.json:
        print(dump_pretty_json(summary))
        return 0
    print(f"session: {summary['session_id']}")
    print(f"path: {summary['path']}")
    print(f"updated_at: {summary['updated_at']}")
    print(f"sources: {', '.join(summary['sources']) or '(none)'}")
    print(f"raw_files: {', '.join(summary['raw_files']) or '(none)'}")
    print(f"normalized: {'yes' if summary['normalized_exists'] else 'no'}")
    print(f"templates: {'yes' if summary['templates_exists'] else 'no'}")
    print(f"packs: {summary['pack_count']}")
    return 0


def command_cursor(args: argparse.Namespace) -> int:
    """Handle the cursor command."""

    session_id = resolve_session_id(args.session_id)
    _, state = ensure_session(session_id, root=args.root)
    cursor = json.loads(args.cursor_json)
    if not isinstance(cursor, dict):
        raise ValueError("cursor JSON must be an object")
    update_cursor(state, args.source, cursor)
    save_state(session_id, state, root=args.root)
    print(dump_pretty_json({"session_id": session_id, "source": args.source, "cursor": cursor}))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return command_init(args)
        if args.command == "status":
            return command_status(args)
        if args.command == "cursor":
            return command_cursor(args)
        parser.error(f"unknown command {args.command!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

