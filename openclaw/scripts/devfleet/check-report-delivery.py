#!/usr/bin/env python3
"""Read-only fleet report observability; never probes, posts or acknowledges.

Run: python3 scripts/devfleet/check-report-delivery.py [--state-dir DIR]
Reads health-check.py's latest.json/state.json (same DEVFLEET_STATE_DIR default).
Mirrors its report-due policy at checked_at, not at the inspection time. Missing
state.json is the producer's empty first-run baseline. A newer snapshot alone
does not need acknowledgment. The configurable 30h freshness budget is local
observability policy for the daily scan, not a delivery SLA.

JSON contains only counts, timestamps and fixed status/reason codes. No host or
issue text is emitted, even on errors. Exit 0: fresh/no report due; 1: stale or
unacknowledged report due; 2: unknown/invalid input. An acknowledgment is NOT a
verified message receipt. This check neither repairs nor authorizes delivery.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path


class EvidenceError(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError("invalid_schema")
        result[key] = value
    return result


def timestamp(value):
    if not isinstance(value, str):
        raise EvidenceError("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise EvidenceError("invalid_timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceError("invalid_timestamp")
    return parsed.astimezone(timezone.utc)


def issue_keys(issues):
    if not isinstance(issues, list):
        raise EvidenceError("invalid_schema")
    keys = set()
    for issue in issues:
        if not isinstance(issue, dict):
            raise EvidenceError("invalid_schema")
        key, severity = issue.get("key"), issue.get("sev")
        if (not isinstance(key, str) or not key or key in keys
                or severity not in ("warn", "crit") or not key.endswith(":" + severity)):
            raise EvidenceError("invalid_schema")
        keys.add(key)
    return keys


def inspect(latest, state, *, now, max_age_hours=30, state_present=True):
    if not isinstance(latest, dict) or not isinstance(state, dict):
        raise EvidenceError("invalid_schema")
    checked = timestamp(latest.get("checked_at"))
    current = issue_keys(latest.get("issues"))
    previous = state.get("reported_open")
    if not isinstance(previous, dict) or "last_report_at" not in state:
        raise EvidenceError("invalid_schema")
    if any(not key or not key.endswith((":warn", ":crit")) or not isinstance(value, dict)
           for key, value in previous.items()):
        raise EvidenceError("invalid_schema")
    last = state["last_report_at"]
    ack = timestamp(last) if last is not None else None
    if checked > now or (ack is not None and ack > checked) or (ack is None and previous):
        raise EvidenceError("inconsistent_snapshot")
    acknowledged = ack == checked
    if acknowledged and current != set(previous):
        raise EvidenceError("inconsistent_snapshot")
    # Keep in sync with health-check.py's worsened/reminder policy. Resolutions
    # and crit->warn downgrades alone do not require a report/acknowledgment.
    worsened = {key for key in current - set(previous)
                if not (key.endswith(":warn") and key.rsplit(":", 1)[0] + ":crit" in previous)}
    reminder = bool(current) and (ack is None or checked - ack > timedelta(days=7))
    due = bool(worsened) or reminder
    fresh = now - checked <= timedelta(hours=max_age_hours)
    status = ("stale_snapshot" if not fresh else "unacknowledged_due" if due
              else "snapshot_acknowledged" if acknowledged else "no_report_due")
    return {
        "ok": fresh and not due,
        "status": status,
        "checkedAt": checked.isoformat(),
        "lastAcknowledgedAt": ack.isoformat() if ack else None,
        "observedAt": now.isoformat(),
        "snapshotFresh": fresh,
        "snapshotAgeHours": round((now - checked).total_seconds() / 3600, 6),
        "maxAgeHours": max_age_hours,
        "statePresent": state_present,
        "snapshotAcknowledged": acknowledged,
        "receiptVerified": False,
        "reportDue": due,
        "reasons": (["new_or_worsened"] if worsened else []) + (["weekly_reminder"] if reminder else []),
        "openCount": len(current),
        "acknowledgedOpenCount": len(previous),
        "newOrWorsenedCount": len(worsened),
    }


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state-dir", type=Path, default=Path(os.environ.get(
        "DEVFLEET_STATE_DIR", Path(__file__).resolve().parents[2] / "memory/devfleet-health")))
    parser.add_argument("--max-age-hours", type=int, default=30)
    args = parser.parse_args(argv)
    if args.max_age_hours <= 0:
        parser.error("--max-age-hours must be positive")
    try:
        latest = read_json(args.state_dir / "latest.json")
        state_present = True
        try:
            state = read_json(args.state_dir / "state.json")
        except FileNotFoundError:
            state_present = False
            state = {"reported_open": {}, "last_report_at": None}
        result = inspect(latest, state, now=datetime.now(timezone.utc),
                         max_age_hours=args.max_age_hours, state_present=state_present)
        code = 0 if result["ok"] else 1
    except (OSError, UnicodeError, ValueError, OverflowError) as exc:
        reason = str(exc) if isinstance(exc, EvidenceError) else "input_unavailable_or_invalid"
        result = {"ok": False, "status": "unknown", "reason": reason, "receiptVerified": False}
        code = 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
