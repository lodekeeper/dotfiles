#!/usr/bin/env python3
"""Safely install a full ChatGPT cookie export into the local Oracle cookie jar.

This helper is the full-cookie complement to `replace-session-token.py`.
It:
- loads a JSON cookie export from a file or stdin
- filters to ChatGPT/OpenAI-related domains only
- requires a session token by default
- writes a timestamped backup before replacing the destination jar
- writes the normalized jar with restrictive permissions

Usage examples:
  scripts/oracle/install-chatgpt-cookies.py --source /tmp/chatgpt-cookies.json
  scripts/oracle/install-chatgpt-cookies.py --source /tmp/export.json --cookie-file ~/.oracle/chatgpt-cookies.json
  cat /tmp/chatgpt-cookies.json | scripts/oracle/install-chatgpt-cookies.py --source -
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

DEFAULT_COOKIE_PATH = Path.home() / ".oracle" / "chatgpt-cookies.json"
SESSION_TOKEN = "__Secure-next-auth.session-token"
ALLOWED_DOMAIN_FRAGMENTS = (
    "chatgpt.com",
    "ws.chatgpt.com",
    "chat.openai.com",
    "openai.com",
)


def backup_path_for(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return path.with_name(path.name + f".bak-{stamp}")


def load_cookie_export(source: str) -> tuple[list[dict], str]:
    if source == "-":
        raw_text = sys.stdin.read()
        source_label = "<stdin>"
    else:
        path = Path(source).expanduser()
        raw_text = path.read_text()
        source_label = str(path)

    data = json.loads(raw_text)
    if not isinstance(data, list):
        raise ValueError(f"Cookie export is not a JSON array: {source_label}")
    cookies: list[dict] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Cookie export entry #{i} is not an object")
        cookies.append(item)
    return cookies, source_label


def cookie_domain(cookie: dict) -> str:
    domain = cookie.get("domain") or cookie.get("host") or ""
    return str(domain)


def domain_allowed(domain: str) -> bool:
    domain = domain.lower().lstrip(".")
    return any(fragment in domain for fragment in ALLOWED_DOMAIN_FRAGMENTS)


def normalize_cookie(cookie: dict) -> dict:
    normalized = dict(cookie)
    if "domain" not in normalized and "host" in normalized:
        normalized["domain"] = normalized["host"]
    normalized.setdefault("path", "/")
    if "secure" not in normalized and "isSecure" in normalized:
        normalized["secure"] = bool(normalized["isSecure"])
    if "httpOnly" not in normalized and "isHttpOnly" in normalized:
        normalized["httpOnly"] = bool(normalized["isHttpOnly"])
    return normalized


def filter_and_normalize(cookies: list[dict]) -> tuple[list[dict], int]:
    kept: list[dict] = []
    dropped = 0
    for cookie in cookies:
        domain = cookie_domain(cookie)
        if not domain_allowed(domain):
            dropped += 1
            continue
        kept.append(normalize_cookie(cookie))
    return kept, dropped


def write_cookie_jar(path: Path, cookies: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, indent=2) + "\n")
    os.chmod(path, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Path to the full cookie export JSON file, or '-' to read from stdin")
    parser.add_argument("--cookie-file", default=str(DEFAULT_COOKIE_PATH), help="Destination cookie jar path (default: ~/.oracle/chatgpt-cookies.json)")
    parser.add_argument("--no-backup", action="store_true", help="Do not write a timestamped backup before replacing the destination jar")
    parser.add_argument("--allow-no-session-token", action="store_true", help="Allow installing a jar that does not contain __Secure-next-auth.session-token")
    args = parser.parse_args()

    dest = Path(args.cookie_file).expanduser()
    raw, source_label = load_cookie_export(args.source)
    cookies, dropped = filter_and_normalize(raw)

    if not cookies:
        raise SystemExit(f"No ChatGPT/OpenAI cookies remained after filtering: {source_label}")

    names = [str(cookie.get("name", "")) for cookie in cookies]
    has_session_token = SESSION_TOKEN in names
    if not has_session_token and not args.allow_no_session_token:
        raise SystemExit(
            "Filtered cookie jar does not contain __Secure-next-auth.session-token; "
            "pass --allow-no-session-token only if you intentionally want to install it anyway"
        )

    backup = None
    if dest.exists() and not args.no_backup:
        backup = backup_path_for(dest)
        shutil.copy2(dest, backup)
        os.chmod(backup, 0o600)

    write_cookie_jar(dest, cookies)

    summary = {
        "status": "ok",
        "source": source_label,
        "cookieFile": str(dest),
        "backupFile": str(backup) if backup else None,
        "sourceCookieCount": len(raw),
        "installedCookieCount": len(cookies),
        "droppedNonChatgptCookies": dropped,
        "hasSessionToken": has_session_token,
        "cookieNames": sorted(set(name for name in names if name)),
        "domains": sorted(set(cookie_domain(cookie) for cookie in cookies if cookie_domain(cookie))),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
