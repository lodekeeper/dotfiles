#!/usr/bin/env python3
"""Build template, reducer, and always-surface artifacts from normalized logs."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.state import (  # noqa: E402
    ensure_session,
    parse_iso8601,
    resolve_session_id,
    save_state,
    update_artifact,
    utc_now_iso,
)


HEX_RE = re.compile(r"\b0x[a-fA-F0-9]{8,}\b")
PEER_RE = re.compile(r"\b(16Uiu[0-9A-Za-z]+|Qm[0-9A-Za-z]{20,})\b")
NUMBER_RE = re.compile(r"\b\d+\b")
QUOTED_RE = re.compile(r'"[^"]*"')

ALWAYS_SURFACE_PATH = Path(__file__).resolve().parent.parent / "references" / "always_surface.yaml"


def load_normalized_events(session_path: Path) -> list[dict[str, Any]]:
    """Load normalized JSONL events from the session workspace."""

    path = session_path / "normalized.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"normalized events missing: {path}")
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            events.append(value)
    return events


def load_always_surface(path: Path = ALWAYS_SURFACE_PATH) -> list[dict[str, Any]]:
    """Load runtime always-surface rules from YAML."""

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    rules = payload.get("always_surface", [])
    if not isinstance(rules, list):
        raise ValueError(f"invalid always_surface rules in {path}")
    return rules


def get_field(event: dict[str, Any], field: str) -> Any:
    """Resolve a dotted field path, falling back into ctx when needed."""

    current: Any = event
    for segment in field.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
            continue
        if current is event and "ctx" in event and isinstance(event["ctx"], dict) and segment in event["ctx"]:
            current = event["ctx"][segment]
            continue
        return None
    return current


def rule_matches(event: dict[str, Any], rule: dict[str, Any]) -> bool:
    """Evaluate a single always-surface matcher against an event."""

    match = rule.get("match") or {}
    if "any" in match:
        return any(rule_matches(event, {"match": subrule}) for subrule in match["any"])
    field = match.get("field")
    if not field:
        return False
    value = get_field(event, field)
    if "contains" in match:
        return str(match["contains"]) in str(value)
    if "equals" in match:
        return value == match["equals"]
    if "pattern" in match:
        return re.search(str(match["pattern"]), str(value)) is not None
    if "gt" in match:
        try:
            return float(value) > float(match["gt"])
        except (TypeError, ValueError):
            return False
    return False


def extract_keep_fields(event: dict[str, Any], keep_fields: list[str] | None) -> dict[str, Any]:
    """Extract keep_fields from an event, falling back into ctx."""

    fields: dict[str, Any] = {}
    for field in keep_fields or []:
        value = get_field(event, field)
        if value is not None:
            fields[field] = value
    return fields


def scan_always_surface(events: list[dict[str, Any]], rules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Return matched always-surface hits and a template lookup map."""

    hits: list[dict[str, Any]] = []
    event_rule_map: dict[str, list[str]] = {}
    for event in events:
        matched_ids: list[str] = []
        for rule in rules:
            if not rule_matches(event, rule):
                continue
            matched_ids.append(str(rule["id"]))
            hits.append(
                {
                    "rule_id": rule["id"],
                    "severity": rule.get("severity", "critical"),
                    "label": rule.get("label", rule["id"]),
                    "event_id": event["id"],
                    "ts": event["ts"],
                    "svc": event["svc"],
                    "lvl": event["lvl"],
                    "msg": event["msg"],
                    "err": event.get("err"),
                    "cause": event.get("cause"),
                    "fields": extract_keep_fields(event, rule.get("keep_fields")),
                    "raw_ref": event["raw_ref"],
                }
            )
        if matched_ids:
            event_rule_map[event["id"]] = matched_ids
    return hits, event_rule_map


def message_pattern(message: str) -> str:
    """Generalize a message into a stable clustering pattern."""

    pattern = QUOTED_RE.sub("<str>", message)
    pattern = HEX_RE.sub("<hex>", pattern)
    pattern = PEER_RE.sub("<peer>", pattern)
    pattern = NUMBER_RE.sub("<num>", pattern)
    return pattern


def template_key(event: dict[str, Any]) -> tuple[str, str]:
    """Return the grouping key for a normalized event."""

    return str(event.get("mod", "generic")), message_pattern(str(event.get("msg", "")))


def bucket_minute(ts: str) -> str:
    """Bucket a timestamp at minute resolution."""

    dt = parse_iso8601(ts)
    return dt.replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def top_counter_items(values: Counter[str], limit: int = 5) -> dict[str, int]:
    """Render a counter as a small ordered mapping."""

    return {key: count for key, count in values.most_common(limit)}


def find_gap_reason(events: list[dict[str, Any]]) -> str | None:
    """Detect a simple suspicious gap in slot progression or timestamps."""

    slots = sorted({event["slot"] for event in events if isinstance(event.get("slot"), int)})
    for previous, current in zip(slots, slots[1:]):
        if current - previous > 1:
            return f"slot gap {previous}->{current}"
    ordered = sorted(events, key=lambda item: item["ts"])
    for previous, current in zip(ordered, ordered[1:]):
        delta = (parse_iso8601(current["ts"]) - parse_iso8601(previous["ts"])).total_seconds()
        if delta > 24:
            return f"time gap {int(delta)}s"
    return None


def score_template(events: list[dict[str, Any]], matched_rule_ids: list[str]) -> tuple[str, int, list[str]]:
    """Assign a v1 tier and numeric score to a template."""

    reasons: list[str] = []
    levels = {event["lvl"] for event in events}
    if matched_rule_ids:
        reasons.append("always-surface")
    if {"error", "fatal", "critical"} & levels:
        reasons.append("error-level")
    elif "warn" in levels:
        reasons.append("warn-level")
    if len(events) == 1:
        reasons.append("singleton")
    buckets = Counter(bucket_minute(event["ts"]) for event in events)
    if buckets:
        bucket_values = list(buckets.values())
        baseline = statistics.median(bucket_values)
        peak = max(bucket_values)
        if baseline > 0 and peak >= max(5, baseline * 5):
            reasons.append("burst")
    gap_reason = find_gap_reason(events)
    if gap_reason:
        reasons.append(gap_reason)

    if matched_rule_ids:
        tier = "critical"
    elif {"error", "fatal", "critical", "warn"} & levels or any(reason in {"singleton", "burst"} or reason.startswith("slot gap") or reason.startswith("time gap") for reason in reasons):
        tier = "suspicious"
    else:
        tier = "background"

    base_score = {"critical": 300, "suspicious": 200, "background": 100}[tier]
    score = base_score + min(len(events), 99) + len(matched_rule_ids) * 50
    if "error-level" in reasons:
        score += 25
    elif "warn-level" in reasons:
        score += 10
    if "burst" in reasons:
        score += 20
    if "singleton" in reasons:
        score += 10
    return tier, score, reasons


def build_templates(events: list[dict[str, Any]], event_rule_map: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Group normalized events into templates."""

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[template_key(event)].append(event)

    templates: list[dict[str, Any]] = []
    for index, (key, grouped_events) in enumerate(sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])), start=1):
        mod, pattern = key
        first_event = min(grouped_events, key=lambda item: item["ts"])
        last_event = max(grouped_events, key=lambda item: item["ts"])
        lvl_counts = Counter(str(event["lvl"]) for event in grouped_events)
        svc_counts = Counter(str(event["svc"]) for event in grouped_events)
        matched_rule_ids = sorted({rule_id for event in grouped_events for rule_id in event_rule_map.get(event["id"], [])})
        tier, score, reasons = score_template(grouped_events, matched_rule_ids)
        slots = [event["slot"] for event in grouped_events if isinstance(event.get("slot"), int)]
        peers = Counter(str(event["peer"]) for event in grouped_events if event.get("peer"))
        roots = Counter(str(event["root"]) for event in grouped_events if event.get("root"))
        errors = Counter(str(event["err"]) for event in grouped_events if event.get("err"))
        templates.append(
            {
                "id": f"T{index:03d}",
                "mod": mod,
                "mod_top": first_event.get("mod_top", mod.split("/", 1)[0]),
                "pattern": pattern,
                "sample_msg": first_event["msg"],
                "count": len(grouped_events),
                "first_ts": first_event["ts"],
                "last_ts": last_event["ts"],
                "lvl_counts": dict(lvl_counts),
                "svc_counts": dict(svc_counts),
                "score_tier": tier,
                "score": score,
                "reasons": reasons,
                "always_surface_rule_ids": matched_rule_ids,
                "slots": {
                    "min": min(slots) if slots else None,
                    "max": max(slots) if slots else None,
                },
                "top_peers": top_counter_items(peers),
                "top_roots": top_counter_items(roots),
                "top_errors": top_counter_items(errors),
                "sample": {
                    "ts": first_event["ts"],
                    "svc": first_event["svc"],
                    "lvl": first_event["lvl"],
                    "slot": first_event.get("slot"),
                    "peer": first_event.get("peer"),
                    "root": first_event.get("root"),
                    "err": first_event.get("err"),
                    "cause": first_event.get("cause"),
                    "raw_ref": first_event["raw_ref"],
                },
            }
        )
    templates.sort(key=lambda item: (-item["score"], item["first_ts"], item["id"]))
    return templates


def peer_count_value(event: dict[str, Any]) -> int | None:
    """Extract a peer-count-like field from event context."""

    ctx = event.get("ctx", {})
    for key in ("peerCount", "peers", "connectedPeers", "peer_count", "numPeers"):
        value = ctx.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def head_slot_value(event: dict[str, Any]) -> int | None:
    """Extract a head slot value from event context."""

    ctx = event.get("ctx", {})
    for key in ("headSlot", "slot", "currentSlot"):
        value = ctx.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return event.get("slot") if isinstance(event.get("slot"), int) else None


def build_status_reducer(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse status-like events into service summaries."""

    services: dict[str, dict[str, Any]] = {}
    for event in events:
        service = event["svc"]
        summary = services.setdefault(
            service,
            {
                "count": 0,
                "peer_count": {"min": None, "max": None},
                "head_slot": {"min": None, "max": None},
                "state_changes": [],
            },
        )
        summary["count"] += 1
        peer_count = peer_count_value(event)
        head_slot = head_slot_value(event)
        if peer_count is not None:
            current_min = summary["peer_count"]["min"]
            current_max = summary["peer_count"]["max"]
            summary["peer_count"]["min"] = peer_count if current_min is None else min(current_min, peer_count)
            summary["peer_count"]["max"] = peer_count if current_max is None else max(current_max, peer_count)
        if head_slot is not None:
            current_min = summary["head_slot"]["min"]
            current_max = summary["head_slot"]["max"]
            summary["head_slot"]["min"] = head_slot if current_min is None else min(current_min, head_slot)
            summary["head_slot"]["max"] = head_slot if current_max is None else max(current_max, head_slot)
        if "status" in event["msg"].lower() or peer_count is not None or "sync" in event["msg"].lower():
            summary["state_changes"].append(
                {
                    "ts": event["ts"],
                    "lvl": event["lvl"],
                    "msg": event["msg"],
                    "peer_count": peer_count,
                    "head_slot": head_slot,
                    "raw_ref": event["raw_ref"],
                }
            )
    for summary in services.values():
        summary["state_changes"] = summary["state_changes"][:20]
    return {"services": services}


def build_block_import_reducer(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize block import activity and anomalies."""

    services: dict[str, dict[str, Any]] = {}
    for event in events:
        lower_msg = event["msg"].lower()
        if "import" not in lower_msg and event.get("slot") is None:
            continue
        service = event["svc"]
        summary = services.setdefault(
            service,
            {
                "count": 0,
                "slot_min": None,
                "slot_max": None,
                "duplicate_slots": [],
                "gaps": [],
                "slow_imports": [],
            },
        )
        summary["count"] += 1
        slot = event.get("slot")
        if isinstance(slot, int):
            if summary["slot_min"] is None or slot < summary["slot_min"]:
                summary["slot_min"] = slot
            if summary["slot_max"] is None or slot > summary["slot_max"]:
                summary["slot_max"] = slot
            seen = summary.setdefault("_seen_slots", set())
            if slot in seen and slot not in summary["duplicate_slots"]:
                summary["duplicate_slots"].append(slot)
            seen.add(slot)
        latency = event.get("ctx", {}).get("recvToImportLatency")
        if isinstance(latency, (int, float)) and latency > 8000:
            summary["slow_imports"].append(
                {
                    "ts": event["ts"],
                    "slot": slot,
                    "latency_ms": latency,
                    "msg": event["msg"],
                    "raw_ref": event["raw_ref"],
                }
            )
    for summary in services.values():
        slots = sorted(summary.pop("_seen_slots", set()))
        summary["gaps"] = [{"after": previous, "before": current} for previous, current in zip(slots, slots[1:]) if current - previous > 1]
        summary["slow_imports"] = summary["slow_imports"][:20]
    return {"services": services}


def build_peer_health_reducer(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize peer health and churn."""

    services: dict[str, dict[str, Any]] = {}
    for event in events:
        service = event["svc"]
        summary = services.setdefault(
            service,
            {
                "low_peer_events": [],
                "connects": 0,
                "disconnects": 0,
                "top_peers": Counter(),
            },
        )
        lower_msg = event["msg"].lower()
        peer = event.get("peer")
        if peer:
            summary["top_peers"][str(peer)] += 1
        if "low peer count" in lower_msg:
            summary["low_peer_events"].append(
                {
                    "ts": event["ts"],
                    "msg": event["msg"],
                    "peer_count": peer_count_value(event),
                    "raw_ref": event["raw_ref"],
                }
            )
        if "connect" in lower_msg:
            summary["connects"] += 1
        if "disconnect" in lower_msg:
            summary["disconnects"] += 1
    output_services: dict[str, dict[str, Any]] = {}
    for service, summary in services.items():
        output_services[service] = {
            "low_peer_events": summary["low_peer_events"][:20],
            "connects": summary["connects"],
            "disconnects": summary["disconnects"],
            "top_peers": top_counter_items(summary["top_peers"], limit=10),
        }
    return {"services": output_services}


def build_reqresp_reducer(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize request/response log activity."""

    services: dict[str, dict[str, Any]] = {}
    for event in events:
        lower_msg = event["msg"].lower()
        lower_mod = str(event.get("mod", "")).lower()
        if "reqresp" not in lower_mod and "rpc" not in lower_mod and "request" not in lower_msg and "response" not in lower_msg:
            continue
        service = event["svc"]
        summary = services.setdefault(
            service,
            {
                "count": 0,
                "errors": 0,
                "timeouts": 0,
                "methods": Counter(),
                "peers": Counter(),
            },
        )
        summary["count"] += 1
        method = event.get("ctx", {}).get("method") or event.get("ctx", {}).get("reqType")
        if method:
            summary["methods"][str(method)] += 1
        peer = event.get("peer")
        if peer:
            summary["peers"][str(peer)] += 1
        if event["lvl"] in {"error", "fatal", "critical"}:
            summary["errors"] += 1
        if "timeout" in lower_msg:
            summary["timeouts"] += 1
    output_services: dict[str, dict[str, Any]] = {}
    for service, summary in services.items():
        output_services[service] = {
            "count": summary["count"],
            "errors": summary["errors"],
            "timeouts": summary["timeouts"],
            "methods": top_counter_items(summary["methods"], limit=10),
            "peers": top_counter_items(summary["peers"], limit=10),
        }
    return {"services": output_services}


def build_timeline(events: list[dict[str, Any]], event_rule_map: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Create a compact timeline of notable events."""

    notable = []
    for event in events:
        if event_rule_map.get(event["id"]) or event["lvl"] in {"error", "fatal", "critical", "warn"}:
            notable.append(
                {
                    "ts": event["ts"],
                    "svc": event["svc"],
                    "lvl": event["lvl"],
                    "msg": event["msg"],
                    "slot": event.get("slot"),
                    "peer": event.get("peer"),
                    "err": event.get("err"),
                    "rules": event_rule_map.get(event["id"], []),
                    "raw_ref": event["raw_ref"],
                }
            )
    return notable[:200]


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    """Write formatted JSON to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def build_session(session_id: str) -> dict[str, Any]:
    """Build the template index and reducers for a session."""

    session_path, state = ensure_session(session_id)
    events = load_normalized_events(session_path)
    rules = load_always_surface()
    always_surface_hits, event_rule_map = scan_always_surface(events, rules)
    templates = build_templates(events, event_rule_map)
    reducers = {
        "always_surface": {
            "hit_count": len(always_surface_hits),
            "hits": always_surface_hits,
        },
        "status": build_status_reducer(events),
        "block_import": build_block_import_reducer(events),
        "peer_health": build_peer_health_reducer(events),
        "reqresp": build_reqresp_reducer(events),
        "timeline": {"timeline": build_timeline(events, event_rule_map)},
    }

    templates_payload = {
        "generated_at": utc_now_iso(),
        "event_count": len(events),
        "template_count": len(templates),
        "services": sorted({event["svc"] for event in events}),
        "time_range": {
            "start": min((event["ts"] for event in events), default=None),
            "end": max((event["ts"] for event in events), default=None),
        },
        "templates": templates,
    }
    write_json(session_path / "templates.json", templates_payload)
    reducers_dir = session_path / "reducers"
    for name, payload in reducers.items():
        write_json(reducers_dir / f"{name}.json", payload)

    update_artifact(
        state,
        "templates",
        {
            "path": str(session_path / "templates.json"),
            "template_count": len(templates),
            "updated_at": utc_now_iso(),
        },
    )
    update_artifact(
        state,
        "reducers",
        {
            "path": str(reducers_dir),
            "files": sorted(path.name for path in reducers_dir.glob("*.json")),
            "updated_at": utc_now_iso(),
        },
    )
    save_state(session_id, state)
    return {
        "session_id": session_id,
        "template_count": len(templates),
        "event_count": len(events),
        "always_surface_hits": len(always_surface_hits),
        "templates_path": str(session_path / "templates.json"),
        "reducers_dir": str(reducers_dir),
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(description="Build logskill template and reducer artifacts.")
    parser.add_argument("--session", dest="session_id", help="Session identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    session_id = resolve_session_id(args.session_id)
    try:
        result = build_session(session_id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
