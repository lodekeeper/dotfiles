#!/usr/bin/env python3
"""Normalize raw log records into the unified logskill event schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.state import (  # noqa: E402
    ensure_session,
    iter_jsonl,
    resolve_session_id,
    save_state,
    update_artifact,
    utc_now_iso,
    write_jsonl,
)


LODSTAR_HUMAN_RE = re.compile(
    r"^(?P<stamp>[A-Z][a-z]{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s*\[(?P<module>[^\]]*)\]\s+"
    r"(?P<level>[A-Za-z]+):\s*(?P<body>.*)$"
)
LODSTAR_EPOCH_RE = re.compile(
    r"^Eph\s+(?P<epoch>\d+)\/(?P<slot>\d+)(?:\s+(?P<seconds>[0-9:.]+))?\s+\[(?P<module>[^\]]*)\]\s+"
    r"(?P<level>[A-Za-z]+):\s*(?P<body>.*)$"
)
GETH_HUMAN_RE = re.compile(
    r"^(?P<level>TRACE|DEBUG|INFO|WARN|ERRO|CRIT)\s+\[(?P<stamp>\d{2}-\d{2}\|\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(?P<body>.*)$"
)
LIGHTHOUSE_HUMAN_RE = re.compile(
    r"^(?P<stamp>[A-Z][a-z]{2}\s+\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(?P<level>[A-Z]+)\s+"
    r"(?P<body>.+)$"
)
KURTOSIS_PREFIX_RE = re.compile(r"^\[[\w.-]+\]\s*")
GENERIC_LEVEL_RE = re.compile(r"\b(trace|debug|info|warn|warning|error|fatal|critical|panic)\b", re.IGNORECASE)
KEY_RE = re.compile(r"(?:(?<=\s)|^)([A-Za-z_][A-Za-z0-9_./-]*)=")
HEX_RE = re.compile(r"\b0x[a-fA-F0-9]{8,}\b")
PEER_RE = re.compile(r"\b(16Uiu[0-9A-Za-z]+|Qm[0-9A-Za-z]{20,})\b")
SLOT_RE = re.compile(r"\bslot(?:=|\s+)(\d+)\b", re.IGNORECASE)
EPOCH_RE = re.compile(r"\bepoch(?:=|\s+)(\d+)\b", re.IGNORECASE)
ERR_RE = re.compile(r"\b([A-Z][A-Z0-9_]{5,})\b")
ISO_PREFIX_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T[0-9:.+-]+Z?)\s+(?P<rest>.*)$")

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

LEVEL_MAP = {
    "trace": "trace",
    "debug": "debug",
    "info": "info",
    "warn": "warn",
    "warning": "warn",
    "erro": "error",
    "error": "error",
    "fatal": "fatal",
    "critical": "critical",
    "crit": "critical",
    "panic": "fatal",
}


def normalize_level(level: str | None) -> str:
    """Normalize a log level."""

    if not level:
        return "info"
    return LEVEL_MAP.get(level.strip().lower(), level.strip().lower())


def current_year() -> int:
    """Return the current UTC year."""

    return datetime.now(timezone.utc).year


def parse_human_timestamp(stamp: str) -> str:
    """Parse a month-day timestamp that omits the year."""

    dt = datetime.strptime(f"{current_year()} {stamp}", "%Y %b-%d %H:%M:%S.%f")
    dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def parse_geth_timestamp(stamp: str) -> str:
    """Parse a Geth MM-DD|HH:MM:SS.mmm timestamp."""

    dt = datetime.strptime(f"{current_year()} {stamp}", "%Y %m-%d|%H:%M:%S.%f")
    dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def parse_lighthouse_timestamp(stamp: str) -> str:
    """Parse a Lighthouse 'Mon DD HH:MM:SS.mmm' timestamp."""

    dt = datetime.strptime(f"{current_year()} {stamp}", "%Y %b %d %H:%M:%S.%f")
    dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def strip_outer_timestamp(line: str) -> tuple[str | None, str]:
    """Strip an outer ISO timestamp prefix often added by docker logs."""

    match = ISO_PREFIX_RE.match(line)
    if not match:
        return None, line
    return match.group("ts"), match.group("rest")


def coerce_scalar(value: str) -> Any:
    """Convert a scalar string into a more useful Python value."""

    text = value.strip().rstrip(",")
    if not text:
        return ""
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1]
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null" or lowered == "none":
        return None
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    if re.fullmatch(r"-?\d+\.\d+", text):
        try:
            return float(text)
        except ValueError:
            return text
    if text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


LODESTAR_DASH_KV_RE = re.compile(r"\s+-\s+([a-zA-Z][a-zA-Z0-9_-]*):\s+")


def split_message_and_kv(body: str) -> tuple[str, dict[str, Any]]:
    """Split a log body into message text and trailing key-value pairs."""

    # Try standard key=value first
    matches = list(KEY_RE.finditer(body))
    if matches:
        first = matches[0]
        message = body[: first.start()].rstrip(" ,")
        fields: dict[str, Any] = {}
        for index, match in enumerate(matches):
            key = match.group(1)
            value_start = match.end()
            value_end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            fields[key] = coerce_scalar(body[value_start:value_end])
        return message.strip(), fields

    # Try Lodestar dash-separated "msg - key: value - key: value" format
    dash_matches = list(LODESTAR_DASH_KV_RE.finditer(body))
    if dash_matches:
        first = dash_matches[0]
        message = body[: first.start()].strip()
        fields = {}
        for index, match in enumerate(dash_matches):
            key = match.group(1).replace("-", "_")
            value_start = match.end()
            value_end = dash_matches[index + 1].start() if index + 1 < len(dash_matches) else len(body)
            fields[key] = coerce_scalar(body[value_start:value_end])
        return message, fields

    # Try simple "key=value, key=value" (comma-separated)
    return body.strip(), {}


def flatten_error(value: Any) -> str | None:
    """Render nested error payloads without truncation."""

    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [flatten_error(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        parts: list[str] = []
        for key in ("code", "type", "name", "message", "reason", "stack"):
            item = value.get(key)
            if item:
                parts.append(f"{key}: {flatten_error(item)}")
        nested = value.get("cause")
        if nested:
            nested_text = flatten_error(nested)
            if nested_text:
                parts.append(f"cause:\n{nested_text}")
        for key, item in value.items():
            if key in {"code", "type", "name", "message", "reason", "stack", "cause"}:
                continue
            rendered = flatten_error(item)
            if rendered:
                parts.append(f"{key}: {rendered}")
        return "\n".join(parts) if parts else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def detect_client(service: str, fmt: str) -> str:
    """Infer the client from the parsed format or service name."""

    if fmt.startswith("lodestar"):
        return "lodestar"
    if fmt.startswith("geth"):
        return "geth"
    lowered = service.lower()
    for candidate in ("lodestar", "geth", "besu", "nethermind", "prysm", "teku", "nimbus"):
        if candidate in lowered:
            return candidate
    return "generic"


def sanitize_module(module: str | None, client: str) -> str:
    """Normalize a module field."""

    if module:
        cleaned = module.strip().strip("/")
        cleaned = cleaned.replace("::", "/").replace(".", "/")
        cleaned = re.sub(r"/{2,}", "/", cleaned)
        return cleaned.lower()
    return client


def mod_top(module: str) -> str:
    """Return the top-level module segment."""

    return module.split("/", 1)[0] if module else "generic"


def find_first(ctx: dict[str, Any], keys: Iterable[str]) -> Any:
    """Return the first matching key from a context dictionary."""

    lowered = {key.lower(): value for key, value in ctx.items()}
    for key in keys:
        if key in ctx:
            return ctx[key]
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def extract_root_from_values(values: Iterable[Any]) -> str | None:
    """Find the first hex-like root value."""

    for value in values:
        if isinstance(value, str) and value.startswith("0x"):
            return value
    return None


def extract_event_fields(message: str, ctx: dict[str, Any], error_text: str | None) -> tuple[int | None, int | None, str | None, str | None, str | None, str | None]:
    """Extract slot, epoch, peer, root, err, and cause from a parsed event."""

    slot_value = find_first(ctx, ("slot", "slotnumber", "headslot", "blockslot"))
    epoch_value = find_first(ctx, ("epoch", "eph", "headepoch"))
    peer_value = find_first(ctx, ("peer", "peerid", "remotepeerid", "peer_id"))
    root_value = extract_root_from_values(
        [
            find_first(ctx, ("root", "blockroot", "headroot", "hash", "blockhash", "beaconblockroot")),
            message,
            error_text,
        ]
    )
    err_value = find_first(ctx, ("err", "code", "errorcode", "error_code"))
    cause_value = find_first(ctx, ("cause", "reason", "error", "details"))

    slot = int(slot_value) if isinstance(slot_value, int) else None
    if slot is None and isinstance(slot_value, str) and slot_value.isdigit():
        slot = int(slot_value)
    if slot is None:
        slot_match = SLOT_RE.search(message)
        if slot_match:
            slot = int(slot_match.group(1))

    epoch = int(epoch_value) if isinstance(epoch_value, int) else None
    if epoch is None and isinstance(epoch_value, str) and epoch_value.isdigit():
        epoch = int(epoch_value)
    if epoch is None:
        epoch_match = EPOCH_RE.search(message)
        if epoch_match:
            epoch = int(epoch_match.group(1))

    peer = peer_value if isinstance(peer_value, str) and peer_value else None
    if peer is None:
        peer_match = PEER_RE.search(message)
        if peer_match:
            peer = peer_match.group(1)

    if root_value is None:
        root_match = HEX_RE.search(message)
        if root_match:
            root_value = root_match.group(0)

    err = err_value if isinstance(err_value, str) and err_value else None
    if err is None:
        err_match = ERR_RE.search(message)
        if err_match:
            candidate = err_match.group(1)
            if "_" in candidate or candidate.startswith("BLOCK_ERROR_"):
                err = candidate

    cause = error_text
    if not cause and isinstance(cause_value, str):
        cause = cause_value
    return slot, epoch, peer, root_value, err, cause


def event_id(payload: dict[str, Any]) -> str:
    """Build a stable event id."""

    seed = "|".join(
        str(payload.get(key, ""))
        for key in ("ts", "svc", "fmt", "lvl", "mod", "msg", "slot", "epoch", "peer", "root", "err", "cause")
    )
    raw_ref = payload.get("raw_ref", {})
    seed += f"|{raw_ref.get('file', '')}|{raw_ref.get('line', '')}"
    return f"e_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:16]}"


def base_event(*, ts: str, svc: str, client: str, fmt: str, lvl: str, mod: str, msg: str, ctx: dict[str, Any], raw_ref: dict[str, Any], slot: int | None = None, epoch: int | None = None, peer: str | None = None, root: str | None = None, err: str | None = None, cause: str | None = None) -> dict[str, Any]:
    """Create a normalized event with the exact schema required by the spec."""

    event = {
        "id": "",
        "ts": ts,
        "svc": svc,
        "client": client,
        "fmt": fmt,
        "lvl": lvl,
        "mod": mod,
        "mod_top": mod_top(mod),
        "msg": msg,
        "slot": slot,
        "epoch": epoch,
        "peer": peer,
        "root": root,
        "err": err,
        "cause": cause,
        "ctx": ctx,
        "raw_ref": raw_ref,
    }
    event["id"] = event_id(event)
    return event


def parse_json_event(raw: dict[str, Any], payload: dict[str, Any], outer_ts: str | None, raw_ref: dict[str, Any]) -> dict[str, Any]:
    """Parse a JSON log line."""

    if "timestamp" in payload and "message" in payload:
        fmt = "lodestar-json"
        ts = payload.get("timestamp") or outer_ts or raw.get("source_ts") or raw.get("observed_at") or utc_now_iso()
        level = normalize_level(str(payload.get("level", "info")))
        module = sanitize_module(str(payload.get("module") or payload.get("logger") or ""), "lodestar")
        message = str(payload.get("message", "")).strip()
        ctx = dict(payload.get("context") or {})
        error_text = flatten_error(payload.get("error"))
        slot, epoch, peer, root, err, cause = extract_event_fields(message, ctx, error_text)
        if error_text and not cause:
            cause = error_text
        return base_event(
            ts=ts,
            svc=str(raw["service"]),
            client="lodestar",
            fmt=fmt,
            lvl=level,
            mod=module,
            msg=message,
            ctx=ctx,
            raw_ref=raw_ref,
            slot=slot,
            epoch=epoch,
            peer=peer,
            root=root,
            err=err,
            cause=cause,
        )
    if "t" in payload and "msg" in payload:
        fmt = "geth-json"
        ts = payload.get("t") or outer_ts or raw.get("source_ts") or raw.get("observed_at") or utc_now_iso()
        level = normalize_level(str(payload.get("lvl", "info")))
        message = str(payload.get("msg", "")).strip()
        ctx = {key: value for key, value in payload.items() if key not in {"t", "lvl", "msg"}}
        module = sanitize_module(str(payload.get("logger") or payload.get("module") or payload.get("component") or ""), "geth")
        error_text = flatten_error(ctx.get("error"))
        slot, epoch, peer, root, err, cause = extract_event_fields(message, ctx, error_text)
        return base_event(
            ts=ts,
            svc=str(raw["service"]),
            client="geth",
            fmt=fmt,
            lvl=level,
            mod=module,
            msg=message,
            ctx=ctx,
            raw_ref=raw_ref,
            slot=slot,
            epoch=epoch,
            peer=peer,
            root=root,
            err=err,
            cause=cause,
        )
    message = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return parse_generic_event(raw, message, outer_ts, raw_ref)


def parse_lodestar_human(raw: dict[str, Any], line: str, raw_ref: dict[str, Any]) -> dict[str, Any]:
    """Parse a human-readable Lodestar line."""

    epoch_match = LODSTAR_EPOCH_RE.match(line)
    if epoch_match:
        message, ctx = split_message_and_kv(epoch_match.group("body"))
        epoch = int(epoch_match.group("epoch"))
        slot = int(epoch_match.group("slot"))
        ctx.setdefault("epoch", epoch)
        ctx.setdefault("slot", slot)
        error_text = flatten_error(ctx.get("error"))
        _, _, peer, root, err, cause = extract_event_fields(message, ctx, error_text)
        module = sanitize_module(epoch_match.group("module"), "lodestar")
        return base_event(
            ts=raw.get("source_ts") or raw.get("observed_at") or utc_now_iso(),
            svc=str(raw["service"]),
            client="lodestar",
            fmt="lodestar-epoch",
            lvl=normalize_level(epoch_match.group("level")),
            mod=module,
            msg=message,
            ctx=ctx,
            raw_ref=raw_ref,
            slot=slot,
            epoch=epoch,
            peer=peer,
            root=root,
            err=err,
            cause=cause,
        )
    human_match = LODSTAR_HUMAN_RE.match(line)
    if not human_match:
        raise ValueError("not a Lodestar human log line")
    message, ctx = split_message_and_kv(human_match.group("body"))
    error_text = flatten_error(ctx.get("error"))
    slot, epoch, peer, root, err, cause = extract_event_fields(message, ctx, error_text)
    module = sanitize_module(human_match.group("module"), "lodestar")
    return base_event(
        ts=parse_human_timestamp(human_match.group("stamp")),
        svc=str(raw["service"]),
        client="lodestar",
        fmt="lodestar-human",
        lvl=normalize_level(human_match.group("level")),
        mod=module,
        msg=message,
        ctx=ctx,
        raw_ref=raw_ref,
        slot=slot,
        epoch=epoch,
        peer=peer,
        root=root,
        err=err,
        cause=cause,
    )


def parse_lighthouse_human(raw: dict[str, Any], line: str, raw_ref: dict[str, Any]) -> dict[str, Any]:
    """Parse a human-readable Lighthouse line."""

    match = LIGHTHOUSE_HUMAN_RE.match(line)
    if not match:
        raise ValueError("not a Lighthouse human log line")
    body = match.group("body")
    # Lighthouse format: "Message text  key: value, key: value"
    # Split on double-space boundary between message and KV pairs
    LH_KV_RE = re.compile(r"\s{2,}(\w[\w_-]*):\s+")
    kv_matches = list(LH_KV_RE.finditer(body))
    if kv_matches:
        message = body[: kv_matches[0].start()].strip()
        ctx: dict[str, Any] = {}
        for idx, kv_match in enumerate(kv_matches):
            key = kv_match.group(1)
            val_start = kv_match.end()
            val_end = kv_matches[idx + 1].start() if idx + 1 < len(kv_matches) else len(body)
            val_str = body[val_start:val_end].strip().rstrip(",")
            # Strip quotes
            if val_str.startswith('"') and val_str.endswith('"'):
                val_str = val_str[1:-1]
            ctx[key] = coerce_scalar(val_str)
        if not ctx:
            ctx = {}
    else:
        message = body.strip()
        ctx = {}
    error_text = flatten_error(ctx.get("error"))
    slot, epoch, peer, root, err, cause = extract_event_fields(message, ctx, error_text)
    module = sanitize_module(str(ctx.pop("service", "") or ctx.pop("component", "") or ""), "lighthouse")
    return base_event(
        ts=parse_lighthouse_timestamp(match.group("stamp")),
        svc=str(raw["service"]),
        client="lighthouse",
        fmt="lighthouse-human",
        lvl=normalize_level(match.group("level")),
        mod=module or "lighthouse",
        msg=message,
        ctx=ctx,
        raw_ref=raw_ref,
        slot=slot,
        epoch=epoch,
        peer=peer,
        root=root,
        err=err,
        cause=cause,
    )


def parse_geth_human(raw: dict[str, Any], line: str, raw_ref: dict[str, Any]) -> dict[str, Any]:
    """Parse a human-readable Geth line."""

    match = GETH_HUMAN_RE.match(line)
    if not match:
        raise ValueError("not a Geth human log line")
    message, ctx = split_message_and_kv(match.group("body"))
    module = sanitize_module(str(find_first(ctx, ("logger", "module", "component")) or "execution"), "geth")
    error_text = flatten_error(ctx.get("error"))
    slot, epoch, peer, root, err, cause = extract_event_fields(message, ctx, error_text)
    return base_event(
        ts=parse_geth_timestamp(match.group("stamp")),
        svc=str(raw["service"]),
        client="geth",
        fmt="geth-human",
        lvl=normalize_level(match.group("level")),
        mod=module,
        msg=message,
        ctx=ctx,
        raw_ref=raw_ref,
        slot=slot,
        epoch=epoch,
        peer=peer,
        root=root,
        err=err,
        cause=cause,
    )


def parse_generic_event(raw: dict[str, Any], line: str, outer_ts: str | None, raw_ref: dict[str, Any]) -> dict[str, Any]:
    """Fallback parser for unrecognized log formats."""

    message = line.strip()
    level_match = GENERIC_LEVEL_RE.search(message)
    level = normalize_level(level_match.group(1) if level_match else "info")
    ctx: dict[str, Any] = {}
    slot, epoch, peer, root, err, cause = extract_event_fields(message, ctx, None)
    fmt = "generic"
    client = detect_client(str(raw["service"]), fmt)
    module = sanitize_module(None, client)
    return base_event(
        ts=outer_ts or raw.get("source_ts") or raw.get("observed_at") or utc_now_iso(),
        svc=str(raw["service"]),
        client=client,
        fmt=fmt,
        lvl=level,
        mod=module,
        msg=message,
        ctx=ctx,
        raw_ref=raw_ref,
        slot=slot,
        epoch=epoch,
        peer=peer,
        root=root,
        err=err,
        cause=cause,
    )


def parse_event(raw: dict[str, Any], raw_file: str, raw_line_number: int) -> dict[str, Any]:
    """Parse a single raw record into a normalized event."""

    line = ANSI_RE.sub("", str(raw.get("line", "")))
    # Strip Kurtosis service prefix "[service-name] ..."
    line = KURTOSIS_PREFIX_RE.sub("", line)
    outer_ts, inner = strip_outer_timestamp(line)
    raw_ref = {"file": raw_file, "line": raw_line_number}
    stripped = inner.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            return parse_json_event(raw, payload, outer_ts, raw_ref)
    try:
        return parse_lodestar_human(raw, inner, raw_ref)
    except ValueError:
        pass
    try:
        return parse_lighthouse_human(raw, inner, raw_ref)
    except ValueError:
        pass
    try:
        return parse_geth_human(raw, inner, raw_ref)
    except ValueError:
        pass
    return parse_generic_event(raw, inner, outer_ts, raw_ref)


@dataclass
class PendingEvent:
    """Buffered event used for multiline stitching."""

    event: dict[str, Any]

    def append_line(self, line: str) -> None:
        """Append a continuation line to the buffered event."""

        text = ANSI_RE.sub("", line.rstrip("\r\n"))
        text = KURTOSIS_PREFIX_RE.sub("", text)
        if not text:
            return
        existing = self.event.get("cause")
        if existing:
            self.event["cause"] = f"{existing}\n{text}"
        else:
            self.event["cause"] = text
        self.event["id"] = event_id(self.event)


class SourceNormalizer:
    """Stateful normalizer that merges multiline stack traces."""

    def __init__(self, raw_file: str) -> None:
        self.raw_file = raw_file
        self.pending: PendingEvent | None = None

    def is_new_event(self, raw: dict[str, Any]) -> bool:
        """Return True if the raw line starts a new log event."""

        line = ANSI_RE.sub("", str(raw.get("line", ""))).strip()
        if not line:
            return False
        line = KURTOSIS_PREFIX_RE.sub("", line)
        _, inner = strip_outer_timestamp(line)
        stripped = inner.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return True
        return bool(
            LODSTAR_EPOCH_RE.match(inner)
            or LODSTAR_HUMAN_RE.match(inner)
            or LIGHTHOUSE_HUMAN_RE.match(inner)
            or GETH_HUMAN_RE.match(inner)
        )

    def process(self, raw: dict[str, Any], raw_line_number: int) -> list[dict[str, Any]]:
        """Process a raw line and emit zero or more completed events."""

        line = str(raw.get("line", ""))
        if self.pending is not None and not self.is_new_event(raw):
            self.pending.append_line(line)
            return []
        completed: list[dict[str, Any]] = []
        if self.pending is not None:
            completed.append(self.pending.event)
            self.pending = None
        if not line.strip():
            return completed
        parsed = parse_event(raw, self.raw_file, raw_line_number)
        self.pending = PendingEvent(parsed)
        return completed

    def flush(self) -> list[dict[str, Any]]:
        """Emit any buffered event."""

        if self.pending is None:
            return []
        event = self.pending.event
        self.pending = None
        return [event]


def normalize_raw_file(path: Path, session_path: Path) -> list[dict[str, Any]]:
    """Normalize a raw JSONL file."""

    normalizer = SourceNormalizer(path.relative_to(session_path).as_posix())
    events: list[dict[str, Any]] = []
    for raw_line_number, raw in enumerate(iter_jsonl(path), start=1):
        events.extend(normalizer.process(raw, raw_line_number))
    events.extend(normalizer.flush())
    return events


def normalize_session(session_id: str) -> dict[str, Any]:
    """Normalize all raw logs in a session."""

    session_path, state = ensure_session(session_id)
    raw_paths = sorted((session_path / "raw").glob("*.jsonl"))
    if not raw_paths:
        raise FileNotFoundError(f"no raw log files found in {session_path / 'raw'}")
    all_events: list[dict[str, Any]] = []
    for raw_path in raw_paths:
        all_events.extend(normalize_raw_file(raw_path, session_path))
    all_events.sort(key=lambda item: (str(item.get("ts", "")), str(item.get("svc", "")), int(item["raw_ref"]["line"])))
    output_path = session_path / "normalized.jsonl"
    event_count = write_jsonl(output_path, all_events)
    update_artifact(
        state,
        "normalized",
        {
            "path": str(output_path),
            "event_count": event_count,
            "updated_at": utc_now_iso(),
        },
    )
    save_state(session_id, state)
    return {
        "session_id": session_id,
        "normalized_path": str(output_path),
        "event_count": event_count,
        "raw_files": [path.name for path in raw_paths],
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(description="Normalize raw log JSONL into the unified logskill schema.")
    parser.add_argument("--session", dest="session_id", help="Session identifier.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    session_id = resolve_session_id(args.session_id)
    try:
        result = normalize_session(session_id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
