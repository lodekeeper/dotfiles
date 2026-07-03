#!/usr/bin/env python3
"""Print a compact human summary from autonomy domain preflight JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_payload(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("preflight JSON root must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize autonomy domain preflight JSON")
    parser.add_argument("--preflight-json", required=True, help="Path to check-autonomy-domain-preflights.py --json output")
    args = parser.parse_args()

    payload = _load_payload(args.preflight_json)
    for raw_check in payload.get("checks") or []:
        if not isinstance(raw_check, dict):
            continue

        status = "OK" if raw_check.get("ok") is True else "FAIL"
        domain = raw_check.get("domain", "unknown")
        name = raw_check.get("name", "unknown")
        return_code = raw_check.get("returnCode")
        print(f"{status} {domain}/{name} (rc={return_code})")

        for warning in raw_check.get("warnings") or []:
            if isinstance(warning, str):
                print(f"  warning: {warning}")

        stderr = raw_check.get("stderr")
        if raw_check.get("ok") is not True and isinstance(stderr, str) and stderr:
            print(f"  stderr: {stderr}")

    ok = payload.get("ok") is True
    print("Autonomy domain preflights OK" if ok else "Autonomy domain preflights failed")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
