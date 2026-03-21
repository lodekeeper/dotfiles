#!/usr/bin/env python3
"""Generate focused drill-down packs from normalized logskill events."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build import message_pattern  # noqa: E402
from scripts.state import (  # noqa: E402
    ensure_session,
    next_pack_path,
    parse_duration,
    parse_iso8601,
    resolve_session_id,
)


def load_json(path: Path) -> Any:
    """Load JSON from a file."""

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_events(path: Path) -> list[dict[str, Any]]:
    """Load normalized events."""

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                events.append(json.loads(stripped))
    return events


def filter_by_template(events: list[dict[str, Any]], template: dict[str, Any]) -> list[dict[str, Any]]:
    """Filter events that belong to a template id."""

    return [event for event in events if event.get("mod") == template.get("mod") and message_pattern(event.get("msg", "")) == template.get("pattern")]


def window_events(events: list[dict[str, Any]], start: str | None, end: str | None) -> list[dict[str, Any]]:
    """Filter events by ISO time bounds."""

    if not start and not end:
        return list(events)
    start_dt = parse_iso8601(start) if start else None
    end_dt = parse_iso8601(end) if end else None
    filtered = []
    for event in events:
        ts = parse_iso8601(event["ts"])
        if start_dt and ts < start_dt:
            continue
        if end_dt and ts > end_dt:
            continue
        filtered.append(event)
    return filtered


def context_lines(event: dict[str, Any]) -> list[str]:
    """Render a single event in drill output."""

    extras = []
    for key in ("slot", "epoch", "peer", "root", "err"):
        value = event.get(key)
        if value is not None:
            extras.append(f"{key}={value}")
    lines = [f"- {event['ts']} {event['svc']} {event['lvl']} {event['mod']} {event['msg']}"]
    if extras:
        lines.append(f"  fields: {', '.join(extras)}")
    if event.get("ctx"):
        lines.append(f"  ctx: {json.dumps(event['ctx'], sort_keys=True, ensure_ascii=False)}")
    if event.get("cause"):
        lines.append(f"  cause:\n{event['cause']}")
    lines.append(f"  raw_ref: {event['raw_ref']['file']}:{event['raw_ref']['line']}")
    return lines


def drill_pack(
    session_id: str,
    *,
    template_id: str | None,
    slot: int | None,
    peer: str | None,
    start: str | None,
    end: str | None,
    radius: str | None,
    service: str | None,
    limit: int,
) -> dict[str, Any]:
    """Generate a drill-down markdown pack."""

    session_path, _ = ensure_session(session_id)
    templates_payload = load_json(session_path / "templates.json")
    templates = {item["id"]: item for item in templates_payload.get("templates", [])}
    events = load_events(session_path / "normalized.jsonl")

    scope_lines: list[str] = [f"- Session: `{session_id}`"]
    filtered = events

    if template_id:
        if template_id not in templates:
            raise KeyError(f"unknown template id: {template_id}")
        template = templates[template_id]
        filtered = filter_by_template(filtered, template)
        scope_lines.append(f"- Template: `{template_id}` `{template['sample_msg']}`")

    if slot is not None:
        slot_events = [event for event in filtered if event.get("slot") == slot]
        if radius and slot_events:
            radius_delta = parse_duration(radius)
            min_ts = min(parse_iso8601(event["ts"]) for event in slot_events) - radius_delta
            max_ts = max(parse_iso8601(event["ts"]) for event in slot_events) + radius_delta
            filtered = [event for event in events if min_ts <= parse_iso8601(event["ts"]) <= max_ts]
            scope_lines.append(f"- Slot anchor: {slot} +/- {radius}")
        else:
            filtered = slot_events
            scope_lines.append(f"- Slot: {slot}")

    if peer:
        filtered = [event for event in filtered if peer in str(event.get("peer") or "")]
        scope_lines.append(f"- Peer: `{peer}`")

    filtered = window_events(filtered, start, end)
    if start or end:
        scope_lines.append(f"- Time window: {start or '-inf'} -> {end or '+inf'}")

    if service:
        filtered = [event for event in filtered if event["svc"] == service]
        scope_lines.append(f"- Service: `{service}`")

    filtered.sort(key=lambda event: event["ts"])
    selected = filtered[:limit]
    scope_lines.append(f"- Matching events: {len(filtered)} (showing {len(selected)})")

    sections = ["# Drill Pack", "## Scope\n" + "\n".join(scope_lines)]
    if template_id and template_id in templates:
        template = templates[template_id]
        template_lines = [
            f"- Score tier: {template['score_tier']}",
            f"- Score: {template['score']}",
            f"- Count: {template['count']}",
            f"- Module: {template['mod']}",
            f"- Pattern: {template['pattern']}",
            f"- Reasons: {', '.join(template.get('reasons', []))}",
        ]
        sections.append("## Template\n" + "\n".join(template_lines))

    event_lines: list[str] = []
    for event in selected:
        event_lines.extend(context_lines(event))
    sections.append("## Events\n" + "\n".join(event_lines if event_lines else ["- No matching events."]))

    pack_path = next_pack_path(session_id, "drill")
    with pack_path.open("w", encoding="utf-8") as handle:
        handle.write("\n\n".join(sections).rstrip() + "\n")
    return {
        "session_id": session_id,
        "pack_path": str(pack_path),
        "event_count": len(filtered),
        "shown": len(selected),
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(description="Generate a logskill drill-down pack.")
    parser.add_argument("--session", dest="session_id", help="Session identifier.")
    parser.add_argument("--template", dest="template_id", help="Template id to inspect.")
    parser.add_argument("--slot", type=int, help="Slot to inspect.")
    parser.add_argument("--peer", help="Peer id substring to inspect.")
    parser.add_argument("--start", help="ISO8601 start time.")
    parser.add_argument("--end", help="ISO8601 end time.")
    parser.add_argument("--radius", help="Relative time radius, e.g. 2m.")
    parser.add_argument("--service", help="Restrict to one service.")
    parser.add_argument("--limit", type=int, default=200, help="Maximum events to render.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    session_id = resolve_session_id(args.session_id)
    try:
        result = drill_pack(
            session_id,
            template_id=args.template_id,
            slot=args.slot,
            peer=args.peer,
            start=args.start,
            end=args.end,
            radius=args.radius,
            service=args.service,
            limit=args.limit,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

