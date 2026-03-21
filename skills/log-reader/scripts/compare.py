#!/usr/bin/env python3
"""Generate a cross-service comparison pack around an incident anchor."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
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


def resolve_anchor(events: list[dict[str, Any]], anchor: str) -> tuple[str, Any]:
    """Resolve an anchor string into type and value."""

    if anchor.startswith("slot:"):
        slot = int(anchor.split(":", 1)[1])
        slot_events = [event for event in events if event.get("slot") == slot]
        if not slot_events:
            raise ValueError(f"no events found for slot {slot}")
        anchor_ts = min(event["ts"] for event in slot_events)
        return "slot", {"slot": slot, "ts": anchor_ts}
    if anchor.startswith("time:"):
        ts = anchor.split(":", 1)[1]
        parse_iso8601(ts)
        return "time", {"ts": ts}
    raise ValueError("anchor must look like slot:<n> or time:<iso8601>")


def compare_pack(session_id: str, services: list[str] | None, anchor: str, radius: str) -> dict[str, Any]:
    """Generate a service comparison markdown pack."""

    session_path, _ = ensure_session(session_id)
    events = load_events(session_path / "normalized.jsonl")
    anchor_kind, anchor_data = resolve_anchor(events, anchor)
    anchor_ts = parse_iso8601(anchor_data["ts"])
    delta = parse_duration(radius)
    start = anchor_ts - delta
    end = anchor_ts + delta

    filtered = [
        event
        for event in events
        if start <= parse_iso8601(event["ts"]) <= end and (not services or event["svc"] in services)
    ]
    filtered.sort(key=lambda event: (event["ts"], event["svc"]))

    by_service: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in filtered:
        by_service[event["svc"]].append(event)

    sections = ["# Compare Pack"]
    scope_lines = [
        f"- Session: `{session_id}`",
        f"- Anchor: `{anchor}` ({anchor_kind})",
        f"- Window: {start.isoformat().replace('+00:00', 'Z')} -> {end.isoformat().replace('+00:00', 'Z')}",
        f"- Services: {', '.join(services) if services else 'all'}",
        f"- Matching events: {len(filtered)}",
    ]
    sections.append("## Scope\n" + "\n".join(scope_lines))

    timeline_lines = []
    for event in filtered[:200]:
        extras = []
        if event.get("slot") is not None:
            extras.append(f"slot={event['slot']}")
        if event.get("err"):
            extras.append(f"err={event['err']}")
        extra_text = f" ({', '.join(extras)})" if extras else ""
        timeline_lines.append(f"- {event['ts']} {event['svc']} {event['lvl']} {event['msg']}{extra_text}")
    sections.append("## Timeline\n" + "\n".join(timeline_lines if timeline_lines else ["- No events in window."]))

    service_sections: list[str] = []
    for service, service_events in sorted(by_service.items()):
        level_counts = Counter(event["lvl"] for event in service_events)
        patterns = Counter(message_pattern(event["msg"]) for event in service_events)
        service_lines = [
            f"- Count: {len(service_events)}",
            f"- Levels: {dict(level_counts)}",
            f"- Top patterns: {dict(patterns.most_common(5))}",
        ]
        for event in service_events[:20]:
            service_lines.append(f"- {event['ts']} {event['lvl']} {event['mod']} {event['msg']}")
            if event.get("cause"):
                service_lines.append(f"  cause:\n{event['cause']}")
        service_sections.append(f"### {service}\n" + "\n".join(service_lines))
    sections.append("## Services\n" + ("\n\n".join(service_sections) if service_sections else "- No service slices."))

    pack_path = next_pack_path(session_id, "compare")
    with pack_path.open("w", encoding="utf-8") as handle:
        handle.write("\n\n".join(sections).rstrip() + "\n")
    return {
        "session_id": session_id,
        "pack_path": str(pack_path),
        "event_count": len(filtered),
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(description="Generate a cross-service compare pack.")
    parser.add_argument("--session", dest="session_id", help="Session identifier.")
    parser.add_argument("--services", help="Comma-separated service filter.")
    parser.add_argument("--anchor", required=True, help="Anchor spec: slot:<n> or time:<iso8601>.")
    parser.add_argument("--radius", default="2m", help="Relative time radius around the anchor.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    session_id = resolve_session_id(args.session_id)
    services = [item.strip() for item in args.services.split(",")] if args.services else None
    try:
        result = compare_pack(session_id, services, args.anchor, args.radius)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
