#!/usr/bin/env python3
"""Generate a cold-start markdown overview pack from built artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.state import (  # noqa: E402
    ensure_session,
    next_pack_path,
    resolve_session_id,
)


TOKEN_BUDGETS = {
    "tiny": 3000,
    "small": 8000,
    "medium": 20000,
    "large": 40000,
}


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON artifact from disk."""

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def format_fields(fields: dict[str, Any]) -> str:
    """Render keep_fields as inline text."""

    if not fields:
        return ""
    return ", ".join(f"{key}={value}" for key, value in fields.items())


def format_template_line(template: dict[str, Any]) -> str:
    """Render a single template summary line."""

    reasons = ", ".join(template.get("reasons", []))
    return (
        f"- `{template['id']}` [{template['score_tier']}] score={template['score']} count={template['count']} "
        f"svc={','.join(sorted(template.get('svc_counts', {}).keys()))} mod={template['mod']} "
        f"msg={template['sample_msg']} reasons={reasons}"
    )


def format_hit_line(hit: dict[str, Any]) -> str:
    """Render an always-surface hit line without truncating the cause."""

    parts = [
        f"- `{hit['rule_id']}` {hit['ts']} {hit['svc']} lvl={hit['lvl']} msg={hit['msg']}",
    ]
    field_text = format_fields(hit.get("fields", {}))
    if field_text:
        parts.append(f"  fields: {field_text}")
    if hit.get("err"):
        parts.append(f"  err: {hit['err']}")
    if hit.get("cause"):
        parts.append(f"  cause:\n{hit['cause']}")
    return "\n".join(parts)


def format_timeline_line(entry: dict[str, Any]) -> str:
    """Render a timeline entry."""

    extras: list[str] = []
    if entry.get("slot") is not None:
        extras.append(f"slot={entry['slot']}")
    if entry.get("peer"):
        extras.append(f"peer={entry['peer']}")
    if entry.get("err"):
        extras.append(f"err={entry['err']}")
    if entry.get("rules"):
        extras.append(f"rules={','.join(entry['rules'])}")
    extra_text = f" ({', '.join(extras)})" if extras else ""
    return f"- {entry['ts']} {entry['svc']} {entry['lvl']} {entry['msg']}{extra_text}"


def append_section(sections: list[str], title: str, lines: list[str]) -> None:
    """Append a markdown section if it has content."""

    if not lines:
        return
    body = "\n".join(lines)
    sections.append(f"## {title}\n{body}")


def enforce_budget(sections: list[str], max_chars: int) -> str:
    """Join sections while respecting an approximate token budget."""

    output: list[str] = []
    current = 0
    for section in sections:
        addition = section + "\n\n"
        if output and current + len(addition) > max_chars:
            break
        output.append(section)
        current += len(addition)
    return "\n\n".join(output).rstrip() + "\n"


def overview_pack(session_id: str, profile: str) -> dict[str, Any]:
    """Generate and persist an overview pack."""

    session_path, _ = ensure_session(session_id)
    templates_payload = load_json(session_path / "templates.json")
    always_surface = load_json(session_path / "reducers" / "always_surface.json")
    status = load_json(session_path / "reducers" / "status.json")
    block_import = load_json(session_path / "reducers" / "block_import.json")
    peer_health = load_json(session_path / "reducers" / "peer_health.json")
    reqresp = load_json(session_path / "reducers" / "reqresp.json")
    timeline = load_json(session_path / "reducers" / "timeline.json")

    templates = templates_payload.get("templates", [])
    critical_templates = [item for item in templates if item.get("score_tier") == "critical"]
    suspicious_templates = [item for item in templates if item.get("score_tier") == "suspicious"]
    budget_chars = TOKEN_BUDGETS[profile] * 4

    sections: list[str] = []
    summary_lines = [
        f"- Session: `{session_id}`",
        f"- Events: {templates_payload.get('event_count', 0)}",
        f"- Templates: {templates_payload.get('template_count', 0)}",
        f"- Services: {', '.join(templates_payload.get('services', [])) or '(none)'}",
        f"- Time range: {templates_payload.get('time_range', {}).get('start')} -> {templates_payload.get('time_range', {}).get('end')}",
        f"- Always-surface hits: {always_surface.get('hit_count', 0)}",
    ]
    append_section(sections, "Summary", summary_lines)

    hit_lines = [format_hit_line(hit) for hit in always_surface.get("hits", [])[:12]]
    append_section(sections, "Always Surface", hit_lines)

    suspicious_lines = [format_template_line(template) for template in templates[:20]]
    append_section(sections, "Top Templates", suspicious_lines)

    reducer_lines: list[str] = []
    for service, data in status.get("services", {}).items():
        reducer_lines.append(
            f"- status `{service}` peer_count={data['peer_count']['min']}..{data['peer_count']['max']} "
            f"head_slot={data['head_slot']['min']}..{data['head_slot']['max']}"
        )
    for service, data in block_import.get("services", {}).items():
        reducer_lines.append(
            f"- imports `{service}` count={data['count']} slot_range={data['slot_min']}..{data['slot_max']} gaps={len(data['gaps'])} duplicates={len(data['duplicate_slots'])}"
        )
    for service, data in peer_health.get("services", {}).items():
        reducer_lines.append(
            f"- peers `{service}` low_peer_events={len(data['low_peer_events'])} connects={data['connects']} disconnects={data['disconnects']}"
        )
    for service, data in reqresp.get("services", {}).items():
        reducer_lines.append(
            f"- reqresp `{service}` count={data['count']} errors={data['errors']} timeouts={data['timeouts']}"
        )
    append_section(sections, "Reducers", reducer_lines)

    timeline_lines = [format_timeline_line(entry) for entry in timeline.get("timeline", [])[:25]]
    append_section(sections, "Timeline", timeline_lines)

    hint_lines: list[str] = []
    for template in templates[:5]:
        hint_lines.append(f"- `scripts/logskill.sh drill --session {session_id} --template {template['id']}`")
    for hit in always_surface.get("hits", [])[:3]:
        if hit.get("fields", {}).get("slot") is not None:
            hint_lines.append(
                f"- `scripts/logskill.sh drill --session {session_id} --slot {hit['fields']['slot']} --radius 2m`"
            )
            break
    for hit in always_surface.get("hits", [])[:3]:
        if hit.get("fields", {}).get("peer"):
            hint_lines.append(
                f"- `scripts/logskill.sh drill --session {session_id} --peer {hit['fields']['peer']}`"
            )
            break
    if not critical_templates and not suspicious_templates and not always_surface.get("hits"):
        hint_lines.append("- Nothing suspicious surfaced in logs. Check Prometheus/Grafana for metrics-side failures.")
    append_section(sections, "Drill Hints", hint_lines)

    content = enforce_budget(sections, budget_chars)
    pack_path = next_pack_path(session_id, "overview")
    with pack_path.open("w", encoding="utf-8") as handle:
        handle.write(content)
    return {
        "session_id": session_id,
        "profile": profile,
        "pack_path": str(pack_path),
        "approx_tokens": len(content) // 4,
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(description="Generate a cold-start logskill overview pack.")
    parser.add_argument("--session", dest="session_id", help="Session identifier.")
    parser.add_argument("--profile", choices=sorted(TOKEN_BUDGETS), default="small", help="Approximate token budget profile.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    session_id = resolve_session_id(args.session_id)
    try:
        result = overview_pack(session_id, args.profile)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

