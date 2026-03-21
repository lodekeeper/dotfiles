#!/usr/bin/env python3
"""Fetch raw logs from supported sources into a logskill session."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.state import (  # noqa: E402
    append_jsonl,
    ensure_session,
    parse_duration,
    parse_iso8601,
    raw_file_path,
    resolve_session_id,
    save_state,
    sanitize_name,
    update_cursor,
    update_source,
    utc_now,
    utc_now_iso,
)


def infer_client(service: str | None) -> str | None:
    """Infer a client name from a service string."""

    if not service:
        return None
    lowered = service.lower()
    for candidate in ("lodestar", "geth", "nethermind", "besu", "prysm", "teku", "nimbus"):
        if candidate in lowered:
            return candidate
    return None


def build_source_id(kind: str, service: str | None, explicit: str | None = None) -> str:
    """Choose a stable source id."""

    if explicit:
        return sanitize_name(explicit)
    if service:
        return sanitize_name(service)
    return sanitize_name(kind)


def fingerprint_record(record: dict[str, Any]) -> str:
    """Generate a stable fingerprint for deduplication."""

    payload = json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:16]


def apply_boundary_dedup(records: list[dict[str, Any]], cursor: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    """Drop duplicates that may repeat at the cursor boundary."""

    recent_hashes = list(cursor.get("recent_hashes", [])) if cursor else []
    recent_set = set(recent_hashes)
    filtered: list[dict[str, Any]] = []
    for record in records:
        record_hash = fingerprint_record(record)
        if record_hash in recent_set:
            continue
        filtered.append(record)
        recent_hashes.append(record_hash)
        if len(recent_hashes) > 20:
            recent_hashes = recent_hashes[-20:]
        recent_set = set(recent_hashes)
    return filtered, recent_hashes


def build_raw_record(
    *,
    service: str,
    source_kind: str,
    source_id: str,
    line: str,
    source_ts: str | None = None,
    line_number: int | None = None,
    stream: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a raw JSONL record."""

    record: dict[str, Any] = {
        "service": service,
        "source": {
            "kind": source_kind,
            "id": source_id,
            "client_hint": infer_client(service),
        },
        "observed_at": utc_now_iso(),
        "line": line.rstrip("\r\n"),
    }
    if source_ts:
        record["source_ts"] = source_ts
    if line_number is not None:
        record["line_number"] = line_number
    if stream:
        record["stream"] = stream
    if metadata:
        record["metadata"] = metadata
    return record


def fetch_file(args: argparse.Namespace, cursor: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Fetch new lines from a local file."""

    path = Path(args.path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"log file not found: {path}")
    service = args.service or path.stem
    source_id = build_source_id("file", service, args.source_id)
    start_offset = 0
    start_line = 0
    if cursor and cursor.get("path") == str(path):
        start_offset = int(cursor.get("offset", 0))
        start_line = int(cursor.get("line_number", 0))
        current_size = path.stat().st_size
        if start_offset > current_size:
            start_offset = 0
            start_line = 0
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(start_offset)
        line_number = start_line
        for raw_line in handle:
            line_number += 1
            records.append(
                build_raw_record(
                    service=service,
                    source_kind="file",
                    source_id=source_id,
                    line=raw_line,
                    line_number=line_number,
                    metadata={"path": str(path)},
                )
            )
        end_offset = handle.tell()
    new_cursor = {
        "kind": "file",
        "path": str(path),
        "offset": end_offset,
        "line_number": start_line + len(records),
    }
    return records, new_cursor, source_id


def parse_docker_line(service: str, source_id: str, line: str) -> dict[str, Any]:
    """Turn a docker log line into a raw record."""

    stripped = line.rstrip("\n")
    source_ts = None
    if " " in stripped:
        candidate, remainder = stripped.split(" ", 1)
        try:
            parse_iso8601(candidate)
        except ValueError:
            pass
        else:
            source_ts = candidate
            stripped = remainder
    return build_raw_record(
        service=service,
        source_kind="docker",
        source_id=source_id,
        line=stripped,
        source_ts=source_ts,
        metadata={"container": service},
    )


def fetch_docker(args: argparse.Namespace, cursor: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Fetch logs from `docker logs`."""

    service = args.service or args.container
    source_id = build_source_id("docker", service, args.source_id)
    command = ["docker", "logs", "--timestamps"]
    since_value = args.since
    if not since_value and cursor and cursor.get("last_ts"):
        since_value = str(cursor["last_ts"])
    if since_value:
        command.extend(["--since", since_value])
    if args.until:
        command.extend(["--until", args.until])
    command.append(args.container)
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    lines = completed.stdout.splitlines()
    records = [parse_docker_line(service, source_id, line) for line in lines if line.strip()]
    records, recent_hashes = apply_boundary_dedup(records, cursor)
    last_ts = None
    for record in reversed(records):
        if record.get("source_ts"):
            last_ts = record["source_ts"]
            break
    new_cursor = {
        "kind": "docker",
        "container": args.container,
        "last_ts": last_ts or cursor.get("last_ts") if cursor else last_ts,
        "recent_hashes": recent_hashes,
    }
    return records, new_cursor, source_id


def fetch_kurtosis(args: argparse.Namespace, cursor: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Fetch logs from `kurtosis service logs`."""

    service = args.service or (args.services if args.services != "all" else f"{args.enclave}-all")
    source_id = build_source_id("kurtosis", service, args.source_id)
    command = ["kurtosis", "service", "logs", args.enclave]
    if args.services == "all":
        command.extend(["-x", "-a"])
    else:
        for item in args.services.split(","):
            value = item.strip()
            if value:
                command.append(value)
        command.append("-a")
    if args.match:
        command.append(f"--match={args.match}")
    if args.regex_match:
        command.append(f"--regex-match={args.regex_match}")
    if args.invert_match:
        command.append("-v")
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    records = [
        build_raw_record(
            service=service,
            source_kind="kurtosis",
            source_id=source_id,
            line=line,
            metadata={"enclave": args.enclave, "services": args.services},
        )
        for line in completed.stdout.splitlines()
        if line.strip()
    ]
    records, recent_hashes = apply_boundary_dedup(records, cursor)
    new_cursor = {
        "kind": "kurtosis",
        "enclave": args.enclave,
        "services": args.services,
        "fetched_at": utc_now_iso(),
        "recent_hashes": recent_hashes,
    }
    return records, new_cursor, source_id


def choose_loki_service(labels: dict[str, str], fallback: str) -> str:
    """Pick a service name from Loki labels."""

    for key in ("service", "svc", "container", "container_name", "app", "job"):
        value = labels.get(key)
        if value:
            return value
    return fallback


def ns_to_iso8601(value: int) -> str:
    """Convert a nanosecond unix epoch into an ISO8601 Z timestamp."""

    dt = datetime.fromtimestamp(value / 1_000_000_000, tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def to_unix_ns(value: str) -> int:
    """Convert an ISO timestamp into a nanosecond unix epoch."""

    dt = parse_iso8601(value)
    return int(dt.timestamp() * 1_000_000_000)


def loki_get(url: str, params: dict[str, str], headers: dict[str, str]) -> dict[str, Any]:
    """Execute a Loki query_range request."""

    request = Request(f"{url}?{urlencode(params)}", headers=headers)
    with urlopen(request) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if data.get("status") != "success":
        raise RuntimeError(f"Loki query failed: {payload}")
    return data


def fetch_loki(args: argparse.Namespace, cursor: dict[str, Any] | None) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Fetch logs from Loki's HTTP API."""

    default_service = args.service or "loki"
    source_id = build_source_id("loki", default_service, args.source_id)
    headers: dict[str, str] = {}
    if args.org_id:
        headers["X-Scope-OrgID"] = args.org_id
    if args.auth_header:
        key, value = args.auth_header.split("=", 1)
        headers[key] = value
    end_ns = to_unix_ns(args.end) if args.end else int(utc_now().timestamp() * 1_000_000_000)
    if args.start:
        start_ns = to_unix_ns(args.start)
    elif args.since:
        start_ns = end_ns - int(parse_duration(args.since).total_seconds() * 1_000_000_000)
    elif cursor and cursor.get("last_ns"):
        start_ns = int(cursor["last_ns"])
    else:
        start_ns = end_ns - int(parse_duration("1h").total_seconds() * 1_000_000_000)
    params = {
        "query": args.query,
        "limit": str(args.limit),
        "direction": "forward",
        "start": str(start_ns),
        "end": str(end_ns),
    }
    data = loki_get(args.url.rstrip("/") + "/loki/api/v1/query_range", params, headers)
    records: list[dict[str, Any]] = []
    max_ns = start_ns
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {}) or {}
        service = choose_loki_service(labels, default_service)
        for entry_ns, line in stream.get("values", []):
            entry_ns_int = int(entry_ns)
            max_ns = max(max_ns, entry_ns_int)
            records.append(
                build_raw_record(
                    service=service,
                    source_kind="loki",
                    source_id=source_id,
                    line=line,
                    source_ts=ns_to_iso8601(entry_ns_int),
                    metadata={"labels": labels, "entry_ns": entry_ns_int},
                )
            )
    records, recent_hashes = apply_boundary_dedup(records, cursor)
    new_cursor = {
        "kind": "loki",
        "query": args.query,
        "last_ns": max_ns,
        "recent_hashes": recent_hashes,
    }
    return records, new_cursor, source_id


def persist_fetch(
    *,
    session_id: str,
    session_path: Path,
    state: dict[str, Any],
    source_id: str,
    source_kind: str,
    service: str | None,
    records: list[dict[str, Any]],
    cursor: dict[str, Any],
) -> dict[str, Any]:
    """Append fetched records and update session state."""

    raw_path = raw_file_path(session_id, source_id)
    written = append_jsonl(raw_path, records)
    update_source(
        state,
        source_id,
        kind=source_kind,
        service=service or source_id,
        metadata={"raw_file": str(raw_path), "client": infer_client(service or source_id)},
    )
    update_cursor(state, source_id, cursor)
    save_state(session_id, state)
    return {
        "session_id": session_id,
        "source_id": source_id,
        "raw_file": str(raw_path),
        "records_written": written,
        "session_path": str(session_path),
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(description="Fetch raw logs into a logskill session.")
    parser.add_argument("--session", dest="session_id", help="Session identifier.")
    subparsers = parser.add_subparsers(dest="source", required=True)

    file_parser = subparsers.add_parser("file", help="Fetch from a local file.")
    file_parser.add_argument("path", help="Path to the log file.")
    file_parser.add_argument("--service", help="Service name override.")
    file_parser.add_argument("--source-id", help="Source id override.")

    docker_parser = subparsers.add_parser("docker", help="Fetch from docker logs.")
    docker_parser.add_argument("container", help="Docker container name.")
    docker_parser.add_argument("--service", help="Service name override.")
    docker_parser.add_argument("--source-id", help="Source id override.")
    docker_parser.add_argument("--since", help="Fetch logs since this duration or timestamp.")
    docker_parser.add_argument("--until", help="Fetch logs until this timestamp.")

    kurtosis_parser = subparsers.add_parser("kurtosis", help="Fetch from Kurtosis service logs.")
    kurtosis_parser.add_argument("--enclave", required=True, help="Kurtosis enclave identifier.")
    kurtosis_parser.add_argument("--services", required=True, help="Comma-separated service names or 'all'.")
    kurtosis_parser.add_argument("--service", help="Service name override for metadata.")
    kurtosis_parser.add_argument("--source-id", help="Source id override.")
    kurtosis_parser.add_argument("--match", help="Plain-text filter for Kurtosis service logs.")
    kurtosis_parser.add_argument("--regex-match", help="Regex filter for Kurtosis service logs.")
    kurtosis_parser.add_argument("--invert-match", action="store_true", help="Invert the Kurtosis filter.")

    loki_parser = subparsers.add_parser("loki", help="Fetch from Loki query_range.")
    loki_parser.add_argument("--url", required=True, help="Base Loki URL, e.g. http://localhost:3100.")
    loki_parser.add_argument("--query", required=True, help="LogQL query.")
    loki_parser.add_argument("--service", help="Default service name when labels are missing.")
    loki_parser.add_argument("--source-id", help="Source id override.")
    loki_parser.add_argument("--since", help="Relative start duration, e.g. 30m.")
    loki_parser.add_argument("--start", help="Explicit ISO8601 start time.")
    loki_parser.add_argument("--end", help="Explicit ISO8601 end time.")
    loki_parser.add_argument("--limit", type=int, default=1000, help="Maximum number of entries to request.")
    loki_parser.add_argument("--org-id", help="Optional Loki tenant id header.")
    loki_parser.add_argument(
        "--auth-header",
        help="Optional custom header in KEY=VALUE format, for example Authorization=Bearer%20token.",
    )

    return parser


def cursor_key_for_args(args: argparse.Namespace) -> str:
    """Compute the cursor key used for a given source invocation."""

    if args.source == "file":
        return build_source_id("file", args.service or Path(args.path).stem, args.source_id)
    if args.source == "docker":
        return build_source_id("docker", args.service or args.container, args.source_id)
    if args.source == "kurtosis":
        service = args.service or (args.services if args.services != "all" else f"{args.enclave}-all")
        return build_source_id("kurtosis", service, args.source_id)
    if args.source == "loki":
        return build_source_id("loki", args.service or "loki", args.source_id)
    return args.source


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    session_id = resolve_session_id(args.session_id)
    try:
        session_path, state = ensure_session(session_id)
        cursor = state.get("cursors", {}).get(cursor_key_for_args(args))
        if args.source == "file":
            records, new_cursor, source_id = fetch_file(args, cursor)
            service = args.service or Path(args.path).stem
            result = persist_fetch(
                session_id=session_id,
                session_path=session_path,
                state=state,
                source_id=source_id,
                source_kind="file",
                service=service,
                records=records,
                cursor=new_cursor,
            )
        elif args.source == "docker":
            records, new_cursor, source_id = fetch_docker(args, cursor)
            result = persist_fetch(
                session_id=session_id,
                session_path=session_path,
                state=state,
                source_id=source_id,
                source_kind="docker",
                service=args.service or args.container,
                records=records,
                cursor=new_cursor,
            )
        elif args.source == "kurtosis":
            records, new_cursor, source_id = fetch_kurtosis(args, cursor)
            result = persist_fetch(
                session_id=session_id,
                session_path=session_path,
                state=state,
                source_id=source_id,
                source_kind="kurtosis",
                service=args.service or args.services,
                records=records,
                cursor=new_cursor,
            )
        elif args.source == "loki":
            records, new_cursor, source_id = fetch_loki(args, cursor)
            result = persist_fetch(
                session_id=session_id,
                session_path=session_path,
                state=state,
                source_id=source_id,
                source_kind="loki",
                service=args.service or "loki",
                records=records,
                cursor=new_cursor,
            )
        else:
            parser.error(f"unsupported source {args.source!r}")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
