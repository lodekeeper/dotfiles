#!/usr/bin/env python3
"""Content gate for sync-dotfiles.sh: block the push if staged additions contain
secrets or public IP addresses.

Scans only lines ADDED in the staged diff (`git diff --cached`), so existing history
is never touched. Exit 0 = clean, exit 1 = hits found (printed masked), exit 2 = error.

False positives: add the exact literal to ~/dotfiles/.sync-gate-allow (one per line).
"""
import ipaddress
import os
import re
import subprocess
import sys

ALLOW_FILE = os.path.expanduser("~/dotfiles/.sync-gate-allow")
INVENTORY = os.path.expanduser("~/.config/devfleet/hosts.txt")

SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")),
    ("github token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai key", re.compile(r"\bsk-(?!ant-)(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}")),
    ("slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("aws access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("docker hub token", re.compile(r"\bdckr_pat_[A-Za-z0-9_-]{20,}")),
    ("gitlab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("telegram bot token", re.compile(r"\b\d{8,10}:AA[0-9A-Za-z_-]{33}\b")),
    ("discord bot token", re.compile(r"\b[MNO][A-Za-z0-9_-]{23,25}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}\b")),
    ("bearer/basic credential in URL", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s:@]{6,}@")),
]
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
IPV6 = re.compile(r"(?<![\w:])[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4}){2,7}(?![\w:])")


def mask(s):
    return s[:4] + "…" + f"({len(s)} chars)" if len(s) > 8 else "****"


def load_lines(path):
    try:
        with open(path) as f:
            return [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]
    except FileNotFoundError:
        return []


def inventory_tokens():
    toks = set()
    for line in load_lines(INVENTORY):
        for t in re.split(r"[\s,]+", line):
            if IPV4.fullmatch(t) or IPV6.fullmatch(t):
                toks.add(t)
    return toks


VERSION_CONTEXT = re.compile(r"(?i)(?:v|version\s*|ver\.?\s*|/|v8\s+|node\s+|chrome/|safari/|webkit/)$")
PLACEHOLDER = re.compile(r"[<>{}$]")


def looks_like_version(line, start, tok):
    if tok.endswith(".0.0.0"):
        return True
    return bool(VERSION_CONTEXT.search(line[max(0, start - 12):start]))


def is_public_ip(s):
    try:
        ip = ipaddress.ip_address(s)
    except ValueError:
        return False
    return ip.is_global


def added_lines():
    out = subprocess.run(["git", "diff", "--cached", "-U0", "--no-color", "--no-ext-diff"],
                         capture_output=True, text=True, check=True).stdout
    path, lineno = None, 0
    for raw in out.splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else None
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
        elif raw.startswith("+") and path:
            yield path, lineno, raw[1:]
            lineno += 1


def main():
    allow = load_lines(ALLOW_FILE)
    inv = inventory_tokens()
    hits = []
    for path, n, line in added_lines():
        if any(a in line for a in allow):
            continue
        for name, rx in SECRET_PATTERNS:
            for m in rx.finditer(line):
                if name.startswith("bearer") and PLACEHOLDER.search(m.group(0)):
                    continue
                hits.append((path, n, name, mask(m.group(0))))
        for rx in (IPV4, IPV6):
            for m in rx.finditer(line):
                tok = m.group(0)
                if rx is IPV6 and len([g for g in tok.split(":") if g]) < 3:
                    continue
                if rx is IPV4 and looks_like_version(line, m.start(), tok):
                    continue
                if tok in inv:
                    hits.append((path, n, "dev-fleet inventory IP", tok))
                elif is_public_ip(tok):
                    hits.append((path, n, "public IP address", tok))
    if hits:
        print("❌ content gate: sensitive data in staged changes (push blocked):", file=sys.stderr)
        for path, n, name, shown in hits:
            print(f"  {path}:{n}: {name}: {shown}", file=sys.stderr)
        print(f"  False positive? add the exact literal to {ALLOW_FILE}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as e:
        print(f"content gate error: {e}", file=sys.stderr)
        sys.exit(2)
