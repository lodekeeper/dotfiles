#!/usr/bin/env python3
"""Live soak monitor for logskill sessions."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build import load_always_surface, rule_matches  # noqa: E402
from scripts.fetch import (  # noqa: E402
    build_source_id,
    cursor_key_for_args,
    fetch_docker,
    fetch_file,
    fetch_kurtosis,
    fetch_loki,
    infer_client,
)
from scripts.normalize import SourceNormalizer  # noqa: E402
from scripts.state import (  # noqa: E402
    append_jsonl,
    count_jsonl,
    ensure_session,
    raw_file_path,
    resolve_session_id,
    save_state,
    sanitize_name,
    update_cursor,
    update_source,
    utc_now_iso,
)


def source_fetch(args: argparse.Namespace):
    """Return the fetch function for the selected source."""

    if args.source == "file":
        return fetch_file, "file"
    if args.source == "docker":
        return fetch_docker, "docker"
    if args.source == "kurtosis":
        return fetch_kurtosis, "kurtosis"
    if args.source == "loki":
        return fetch_loki, "loki"
    raise ValueError(f"unsupported source {args.source!r}")


def determine_service(args: argparse.Namespace) -> str:
    """Determine the service label used by the watcher."""

    if args.source == "file":
        return args.service or Path(args.path).stem
    if args.source == "docker":
        return args.service or args.container
    if args.source == "kurtosis":
        return args.service or (args.services if args.services != "all" else f"{args.enclave}-all")
    if args.source == "loki":
        return args.service or "loki"
    return args.source


def match_rules(event: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return always-surface rules that match an event."""

    return [rule for rule in rules if rule_matches(event, rule)]


def flush_events(normalizer: SourceNormalizer, normalized_path: Path) -> list[dict[str, Any]]:
    """Flush buffered events to the normalized JSONL file."""

    pending = normalizer.flush()
    if pending:
        append_jsonl(normalized_path, pending)
    return pending


def print_status(source_id: str, cycle: int, raw_count: int, normalized_count: int, hit_count: int) -> None:
    """Emit a compact status line."""

    print(
        json.dumps(
            {
                "source_id": source_id,
                "cycle": cycle,
                "raw_records": raw_count,
                "normalized_events": normalized_count,
                "always_surface_hits": hit_count,
                "ts": utc_now_iso(),
            },
            sort_keys=True,
        )
    )


def watch_loop(session_id: str, args: argparse.Namespace) -> dict[str, Any]:
    """Run the live soak monitor loop."""

    session_path, state = ensure_session(session_id)
    fetch_fn, source_kind = source_fetch(args)
    source_id = cursor_key_for_args(args)
    service = determine_service(args)
    raw_path = raw_file_path(session_id, source_id)
    raw_line_number = count_jsonl(raw_path) if raw_path.exists() else 0
    normalized_path = session_path / "normalized.jsonl"
    rules = load_always_surface()
    normalizer = SourceNormalizer(raw_path.relative_to(session_path).as_posix())

    raw_count = 0
    normalized_count = 0
    hit_count = 0
    cycle = 0
    last_status = time.monotonic()

    update_source(
        state,
        source_id,
        kind=source_kind,
        service=service,
        metadata={"raw_file": str(raw_path), "client": infer_client(service)},
    )
    save_state(session_id, state)

    try:
        while True:
            cycle += 1
            cursor = state.get("cursors", {}).get(source_id)
            records, new_cursor, _ = fetch_fn(args, cursor)
            if records:
                raw_count += append_jsonl(raw_path, records)
                update_cursor(state, source_id, new_cursor)
                save_state(session_id, state)
                emitted: list[dict[str, Any]] = []
                for record in records:
                    raw_line_number += 1
                    emitted.extend(normalizer.process(record, raw_line_number))
                if emitted:
                    normalized_count += append_jsonl(normalized_path, emitted)
                    for event in emitted:
                        for rule in match_rules(event, rules):
                            hit_count += 1
                            print(
                                json.dumps(
                                    {
                                        "type": "always_surface",
                                        "rule_id": rule["id"],
                                        "severity": rule.get("severity"),
                                        "ts": event["ts"],
                                        "svc": event["svc"],
                                        "msg": event["msg"],
                                        "err": event.get("err"),
                                        "cause": event.get("cause"),
                                    },
                                    ensure_ascii=False,
                                    sort_keys=True,
                                )
                            )
            now = time.monotonic()
            if now - last_status >= args.status_every:
                print_status(source_id, cycle, raw_count, normalized_count, hit_count)
                last_status = now
            if args.cycles and cycle >= args.cycles:
                break
            time.sleep(args.poll)
    except KeyboardInterrupt:
        pass

    flushed = flush_events(normalizer, normalized_path)
    normalized_count += len(flushed)
    for event in flushed:
        for rule in match_rules(event, rules):
            hit_count += 1
            print(
                json.dumps(
                    {
                        "type": "always_surface",
                        "rule_id": rule["id"],
                        "severity": rule.get("severity"),
                        "ts": event["ts"],
                        "svc": event["svc"],
                        "msg": event["msg"],
                        "err": event.get("err"),
                        "cause": event.get("cause"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
    save_state(session_id, state)
    print_status(source_id, cycle, raw_count, normalized_count, hit_count)
    return {
        "session_id": session_id,
        "source_id": source_id,
        "raw_records": raw_count,
        "normalized_events": normalized_count,
        "always_surface_hits": hit_count,
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(description="Watch a log source and surface live soak signals.")
    parser.add_argument("--session", dest="session_id", help="Session identifier.")
    parser.add_argument("--poll", type=float, default=5.0, help="Polling interval in seconds.")
    parser.add_argument("--status-every", type=float, default=30.0, help="Periodic status interval in seconds.")
    parser.add_argument("--cycles", type=int, help="Optional max number of polling cycles.")
    subparsers = parser.add_subparsers(dest="source", required=True)

    file_parser = subparsers.add_parser("file", help="Watch a local file.")
    file_parser.add_argument("path", help="Path to the log file.")
    file_parser.add_argument("--service", help="Service name override.")
    file_parser.add_argument("--source-id", help="Source id override.")

    docker_parser = subparsers.add_parser("docker", help="Watch a Docker container.")
    docker_parser.add_argument("container", help="Docker container name.")
    docker_parser.add_argument("--service", help="Service name override.")
    docker_parser.add_argument("--source-id", help="Source id override.")
    docker_parser.add_argument("--since", help="Initial since duration or timestamp.")
    docker_parser.add_argument("--until", help="Optional until timestamp for one-shot polling.")

    kurtosis_parser = subparsers.add_parser("kurtosis", help="Watch Kurtosis service logs.")
    kurtosis_parser.add_argument("--enclave", required=True, help="Kurtosis enclave identifier.")
    kurtosis_parser.add_argument("--services", required=True, help="Comma-separated service names or 'all'.")
    kurtosis_parser.add_argument("--service", help="Service name override.")
    kurtosis_parser.add_argument("--source-id", help="Source id override.")
    kurtosis_parser.add_argument("--match", help="Plain-text filter for Kurtosis service logs.")
    kurtosis_parser.add_argument("--regex-match", help="Regex filter for Kurtosis service logs.")
    kurtosis_parser.add_argument("--invert-match", action="store_true", help="Invert the Kurtosis filter.")

    loki_parser = subparsers.add_parser("loki", help="Watch Loki with polling.")
    loki_parser.add_argument("--url", required=True, help="Base Loki URL.")
    loki_parser.add_argument("--query", required=True, help="LogQL query.")
    loki_parser.add_argument("--service", help="Default service name.")
    loki_parser.add_argument("--source-id", help="Source id override.")
    loki_parser.add_argument("--since", help="Initial lookback duration.")
    loki_parser.add_argument("--start", help="Explicit ISO8601 start time.")
    loki_parser.add_argument("--end", help="Explicit ISO8601 end time.")
    loki_parser.add_argument("--limit", type=int, default=1000, help="Maximum number of entries per poll.")
    loki_parser.add_argument("--org-id", help="Optional Loki tenant id header.")
    loki_parser.add_argument("--auth-header", help="Optional custom header in KEY=VALUE format.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    session_id = resolve_session_id(args.session_id)
    try:
        result = watch_loop(session_id, args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
