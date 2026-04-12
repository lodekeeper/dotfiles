#!/usr/bin/env python3
"""Safely replace the ChatGPT NextAuth session token in a local cookie jar.

This helper is intentionally narrow:
- updates `__Secure-next-auth.session-token` in an existing ChatGPT cookie jar
- preserves all other cookies when present
- creates a minimal cookie jar if none exists yet
- writes a timestamped backup before modification

Usage examples:
  scripts/oracle/replace-session-token.py --token-file /tmp/session-token.txt
  scripts/oracle/replace-session-token.py --token "fresh-session-token-value"
  cat /tmp/session-token.txt | scripts/oracle/replace-session-token.py --stdin
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
TOKEN_NAME = "__Secure-next-auth.session-token"


def load_cookie_jar(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"Cookie jar is not a JSON array: {path}")
    return data


def normalize_token(raw: str) -> str:
    token = raw.strip()
    if not token:
        raise ValueError("Session token is empty after trimming whitespace")
    return token


def patch_cookie_jar(cookies: list[dict], token: str) -> tuple[list[dict], int]:
    patched = []
    replaced = 0
    for cookie in cookies:
        if isinstance(cookie, dict) and cookie.get("name") == TOKEN_NAME:
            updated = dict(cookie)
            updated["value"] = token
            if not updated.get("path"):
                updated["path"] = "/"
            if "secure" not in updated:
                updated["secure"] = True
            if "httpOnly" not in updated:
                updated["httpOnly"] = True
            patched.append(updated)
            replaced += 1
        else:
            patched.append(cookie)

    if replaced == 0:
        patched.append(
            {
                "name": TOKEN_NAME,
                "value": token,
                "domain": ".chatgpt.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            }
        )
    return patched, replaced


def write_cookie_jar(path: Path, cookies: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies, indent=2) + "\n")
    os.chmod(path, 0o600)


def backup_path_for(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return path.with_name(path.name + f".bak-{stamp}")


def get_token(args: argparse.Namespace) -> str:
    provided = sum(bool(x) for x in [args.token, args.token_file, args.stdin])
    if provided != 1:
        raise ValueError("Provide exactly one of --token, --token-file, or --stdin")
    if args.token:
        return normalize_token(args.token)
    if args.token_file:
        return normalize_token(Path(args.token_file).read_text())
    return normalize_token(sys.stdin.read())


def format_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return f"file not found: {exc.filename}"
    if isinstance(exc, PermissionError):
        return f"permission denied: {exc.filename}"
    if isinstance(exc, json.JSONDecodeError):
        return f"invalid JSON input at line {exc.lineno}, column {exc.colno}: {exc.msg}"
    message = str(exc).strip()
    return message or exc.__class__.__name__


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cookie-file", default=str(DEFAULT_COOKIE_PATH), help="Cookie jar path (default: ~/.oracle/chatgpt-cookies.json)")
    parser.add_argument("--token", help="Fresh __Secure-next-auth.session-token value")
    parser.add_argument("--token-file", help="Read fresh token from file")
    parser.add_argument("--stdin", action="store_true", help="Read fresh token from stdin")
    parser.add_argument("--no-backup", action="store_true", help="Do not write a timestamped backup before updating")
    args = parser.parse_args()

    cookie_path = Path(args.cookie_file).expanduser()
    token = get_token(args)
    existing = load_cookie_jar(cookie_path)

    backup_path = None
    if cookie_path.exists() and not args.no_backup:
        backup_path = backup_path_for(cookie_path)
        shutil.copy2(cookie_path, backup_path)
        os.chmod(backup_path, 0o600)

    patched, replaced = patch_cookie_jar(existing, token)
    write_cookie_jar(cookie_path, patched)

    summary = {
        "status": "ok",
        "cookieFile": str(cookie_path),
        "backupFile": str(backup_path) if backup_path else None,
        "replacedExistingTokens": replaced,
        "createdMinimalTokenCookie": replaced == 0,
        "cookieCount": len(patched),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("ERROR: interrupted", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {format_error(exc)}", file=sys.stderr)
        raise SystemExit(1)
