#!/usr/bin/env python3
"""Collect public Dora client/fork evidence using its advertised Swagger GETs.

First save fresh `panda devnets endpoints <active-id> -o json` output, then run:
  python3 scripts/debug/fetch-dora-snapshot.py --endpoints-json endpoints.json > memory/<dir>/snapshot.json

Write snapshots under memory/ (private), never notes/: client entries carry
peer IPs, and notes/ is published by the dotfiles sync, whose content gate rejects them.

The caller owns endpoint discovery/freshness. This supports Swagger 2 at the
observed /api/swagger/doc.json location; it does not probe guessed routes,
change auth, or judge network health. Stdout is emitted only on full success.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit


OPERATIONS = {"clients": "getConsensusClients", "forks": "getNetworkClientHeadForks"}


class SnapshotError(ValueError):
    pass


def reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON number")


def finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite JSON number")
    return number


def dora_origin(endpoints: object) -> str:
    value = endpoints.get("dora") if isinstance(endpoints, dict) else None
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise SnapshotError("endpoint inventory must contain a Dora HTTPS origin")
    try:
        url = urlsplit(value)
        port = url.port  # Validate malformed ports even though the original netloc is retained.
        if (url.scheme != "https" or not url.hostname or url.username is not None
                or url.password is not None or url.path not in ("", "/")
                or url.query or url.fragment or port == 0):
            raise ValueError
    except ValueError:
        raise SnapshotError("Dora endpoint must be an HTTPS origin without credentials or URL extras") from None
    return f"https://{url.netloc}"


def safe_path(value: object, *, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return ""
    if (not isinstance(value, str) or not re.fullmatch(r"/[A-Za-z0-9_/-]*", value)
            or "//" in value):
        raise SnapshotError("schema contains an unsupported non-literal API path")
    return value


def discover_paths(schema: object) -> dict[str, str]:
    if not isinstance(schema, dict) or schema.get("swagger") != "2.0":
        raise SnapshotError("expected a Swagger 2 schema")
    base = safe_path(schema.get("basePath", ""), allow_empty=True).rstrip("/")
    paths = schema.get("paths")
    if not isinstance(paths, dict):
        raise SnapshotError("schema paths must be an object")
    selected: dict[str, str] = {}
    for label, operation_id in OPERATIONS.items():
        matches = []
        for path, item in paths.items():
            if not isinstance(item, dict):
                continue
            get = item.get("get")
            if not isinstance(get, dict) or get.get("operationId") != operation_id:
                continue
            for owner in (item, get):
                parameters = owner.get("parameters", [])
                if not isinstance(parameters, list) or any(
                    not isinstance(p, dict) or p.get("required") or "$ref" in p
                    for p in parameters
                ):
                    raise SnapshotError(f"{label} operation has unsupported parameters")
            matches.append(base + safe_path(path))
        if len(matches) != 1:
            raise SnapshotError(f"expected exactly one advertised GET for {label}, found {len(matches)}")
        selected[label] = matches[0]
    return selected


def fetch_json(url: str, timeout: int) -> object:
    # -q MUST be first: ignore ambient curlrc auth/redirect/extra-request settings.
    command = ["curl", "-q", "--fail", "--silent", "--show-error", "--proto", "=https",
               "--connect-timeout", str(min(timeout, 5)), "--max-time", str(timeout),
               "--max-filesize", "10485760", "--write-out", "\n%{http_code}", url]
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout + 2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise SnapshotError("public Dora request could not complete") from None
    if result.returncode:
        raise SnapshotError(f"public Dora request failed (curl exit {result.returncode})")
    body, separator, status = result.stdout.rpartition(b"\n")
    if not separator or status != b"200":
        raise SnapshotError("public Dora request did not return HTTP 200")
    try:
        return json.loads(body.decode("utf-8"), parse_constant=reject_constant, parse_float=finite_float)
    except (UnicodeDecodeError, ValueError):
        raise SnapshotError("public Dora response was not valid UTF-8 JSON") from None


def checked_list(envelope: object, list_key: str, count_key: str) -> list[dict]:
    if not isinstance(envelope, dict):
        raise SnapshotError(f"{list_key} envelope must be an object")
    items, count = envelope.get(list_key), envelope.get(count_key)
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise SnapshotError(f"{list_key} must be an array of objects")
    if type(count) is not int or count != len(items):
        raise SnapshotError(f"{count_key} must match the {list_key} array length")
    return items


def collect_snapshot(origin: str, timeout: int) -> dict:
    schema_path = "/api/swagger/doc.json"
    schema = fetch_json(origin + schema_path, timeout)
    paths = discover_paths(schema)
    clients = fetch_json(origin + paths["clients"], timeout)
    if isinstance(clients, dict) and "status" in clients and clients["status"] != "OK":
        raise SnapshotError("clients response reports a non-OK status")
    client_list = checked_list(clients, "clients", "count")
    forks = fetch_json(origin + paths["forks"], timeout)
    if not isinstance(forks, dict) or forks.get("status") != "OK":
        raise SnapshotError("forks response must report status OK")
    fork_list = checked_list(forks.get("data"), "forks", "fork_count")
    return {
        "transportOk": True,
        "scope": "Explorer evidence only; not a network-health verdict or proof of client failure",
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "doraUrl": origin,
        "schemaPath": schema_path,
        "paths": paths,
        "counts": {"clients": len(client_list), "forks": len(fork_list)},
        "schema": schema,
        "clients": clients,
        "forks": forks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoints-json", type=Path, required=True,
                        help="Fresh panda devnets endpoints <active-id> -o json output")
    parser.add_argument("--timeout-seconds", type=int, default=15,
                        help="Per-request timeout, 1-60 seconds (default: 15)")
    args = parser.parse_args()
    if not 1 <= args.timeout_seconds <= 60:
        parser.error("--timeout-seconds must be between 1 and 60")
    try:
        inventory = json.loads(args.endpoints_json.read_text(encoding="utf-8"))
        snapshot = collect_snapshot(dora_origin(inventory), args.timeout_seconds)
        serialized = json.dumps(snapshot, indent=2, sort_keys=True, allow_nan=False)
    except (OSError, ValueError) as exc:
        # No remote body, source-file content, or credential material in diagnostics.
        detail = str(exc) if isinstance(exc, SnapshotError) else "endpoint inventory could not be read as JSON"
        print(f"Dora evidence collection failed: {detail}", file=sys.stderr)
        return 1
    print(serialized)
    print(f"Dora evidence collected: {snapshot['counts']['clients']} clients, "
          f"{snapshot['counts']['forks']} forks; not a health verdict", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
