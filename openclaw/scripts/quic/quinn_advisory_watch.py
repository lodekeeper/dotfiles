#!/usr/bin/env python3
"""Check ChainSafe/js-libp2p-quic against published quinn security advisories.

Sources: quinn-rs/quinn repository advisories (these show up before the global
GitHub advisory DB, which lags by weeks) merged with the global DB for the
quinn crates.

Checked locations:
  main     - Cargo.lock on js-libp2p-quic main        -> a dependency-bump PR is needed
  release  - Cargo.lock at the latest release tag     -> a release is needed
  lodestar - Cargo.lock of the libp2p-quic version that Lodestar unstable resolves -> a Lodestar bump is needed

Always exits 0. The last stdout line is one JSON object. `ok: false` means the check itself failed.

  quinn_advisory_watch.py                      # remote check
  quinn_advisory_watch.py --lockfile Cargo.lock  # check a local lockfile only (verify a bump)
"""

import argparse
import base64
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

QUIC_REPO = "ChainSafe/js-libp2p-quic"
LODESTAR_REPO = "ChainSafe/lodestar"
ADVISORY_REPO = "quinn-rs/quinn"
PACKAGES = ("quinn", "quinn-proto", "quinn-udp")
STAGE_ORDER = ("main", "release", "lodestar")
ACTIONS = {"main": "pr_needed", "release": "release_needed", "lodestar": "lodestar_bump_needed"}


def gh(path, raw=False):
    cmd = ["gh", "api", path]
    if raw:
        cmd += ["-H", "Accept: application/vnd.github.raw"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if res.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {res.stderr.strip()[:300]}")
    return res.stdout if raw else json.loads(res.stdout)


def parse_version(v):
    v = v.strip().lstrip("v").split("+")[0].split("-")[0]
    parts = [int(p) for p in v.split(".") if p.isdigit()]
    if not parts:
        raise ValueError(f"bad version {v!r}")
    return tuple((parts + [0, 0, 0])[:3])


CONSTRAINT_RE = r"(>=|<=|>|<|==|=)?\s*v?([0-9]+(?:\.[0-9]+)*(?:-[0-9A-Za-z.]+)?)"
LOWER, UPPER, EXACT = (">=", ">"), ("<=", "<"), ("=", "==")


def parse_range(spec):
    """Return a list of OR-alternatives, each a list of (op, version) constraints.

    GHSA ranges are free-form: ">= 0.11.0, <= 0.11.18", "0.11.17", "= 0.11.13", "> 0.7.0",
    "0.11.0 - 0.11.6", "< 0.5.16, >= 0.6.0 < 0.6.3". A new alternative starts whenever a
    constraint cannot narrow the current one. Raises ValueError on anything else.
    """
    alternatives = []
    for alt in spec.split("||"):
        alt = re.sub(r"([0-9][0-9A-Za-z.]*)\s+-\s+([0-9][0-9A-Za-z.]*)", r">= \1, <= \2", alt)
        if re.sub(CONSTRAINT_RE, "", alt).strip(" ,"):
            raise ValueError(f"unparseable range {spec!r}")
        group = []
        for op, ver in re.findall(CONSTRAINT_RE, alt):
            op = op or "="
            ops = {o for o, _ in group}
            if group and (op in EXACT or ops & set(EXACT) or (op in LOWER and ops) or (op in UPPER and ops & set(UPPER))):
                alternatives.append(group)
                group = []
            group.append((op, parse_version(ver)))
        if group:
            alternatives.append(group)
    if not alternatives:
        raise ValueError(f"empty range {spec!r}")
    return alternatives


def same_line(a, b):
    """Semver-compatible release line (0.x.y lines are split by minor)."""
    return a[0] == b[0] and (a[0] != 0 or a[1] == b[1])


def is_vulnerable(version, alternatives, patched):
    ops = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        "=": lambda a, b: a == b,
        "==": lambda a, b: a == b,
    }
    v = parse_version(version)
    if not any(all(ops[op](v, bound) for op, bound in alt) for alt in alternatives):
        return False
    # Repository advisories often leave the range open-ended ("> 0.7.0") and only carry the
    # fix in patched_versions, so a version at or above a patch on its own line is fixed.
    fixes = [parse_version(p) for _, p in re.findall(CONSTRAINT_RE, patched)]
    if any(same_line(v, p) and v >= p for p in fixes):
        return False
    return not (len(fixes) == 1 and v >= fixes[0])


def patched_str(value):
    if isinstance(value, dict):
        return value.get("identifier") or ""
    return value or ""


def fetch_advisories():
    advisories = {}
    for a in gh(f"repos/{ADVISORY_REPO}/security-advisories?state=published&per_page=100"):
        advisories[a["ghsa_id"]] = {
            "ghsa": a["ghsa_id"],
            "severity": a.get("severity"),
            "summary": a.get("summary"),
            "published_at": a.get("published_at"),
            "url": a.get("html_url"),
            "vulns": [
                {"package": v["package"]["name"], "range": v.get("vulnerable_version_range") or "", "patched": v.get("patched_versions") or ""}
                for v in a.get("vulnerabilities") or []
                if (v.get("package") or {}).get("ecosystem") in ("rust", "cargo", "crates.io")
            ],
        }
    for a in gh(f"advisories?ecosystem=rust&affects={','.join(PACKAGES)}&per_page=100"):
        if a["ghsa_id"] in advisories or a.get("withdrawn_at"):
            continue
        advisories[a["ghsa_id"]] = {
            "ghsa": a["ghsa_id"],
            "severity": a.get("severity"),
            "summary": a.get("summary"),
            "published_at": a.get("published_at"),
            "url": a.get("html_url"),
            "vulns": [
                {"package": v["package"]["name"], "range": v.get("vulnerable_version_range") or "", "patched": patched_str(v.get("first_patched_version"))}
                for v in a.get("vulnerabilities") or []
            ],
        }
    return advisories


def locked_versions(lock_text):
    """Map package name -> sorted list of locked versions (Cargo.lock may hold several)."""
    found = {}
    for m in re.finditer(r'^name = "([^"]+)"\nversion = "([^"]+)"', lock_text, re.M):
        if m.group(1) in PACKAGES:
            found.setdefault(m.group(1), set()).add(m.group(2))
    return {k: sorted(v, key=parse_version) for k, v in found.items()}


def remote_lock(ref):
    data = gh(f"repos/{QUIC_REPO}/contents/Cargo.lock?ref={ref}")
    return base64.b64decode(data["content"]).decode()


def lodestar_quic_version():
    lock = gh(f"repos/{LODESTAR_REPO}/contents/pnpm-lock.yaml?ref=unstable", raw=True)
    versions = sorted(set(re.findall(r"^  '@chainsafe/libp2p-quic@([0-9][^':]*)':", lock, re.M)), key=parse_version)
    if not versions:
        raise RuntimeError("could not find @chainsafe/libp2p-quic in lodestar unstable pnpm-lock.yaml")
    return versions


def match(stage, ref, locked, advisories, unparsed):
    findings = []
    for adv in advisories.values():
        for vuln in adv["vulns"]:
            if vuln["package"] not in locked:
                continue
            try:
                alternatives = parse_range(vuln["range"])
            except ValueError:
                unparsed.add(f"{adv['ghsa']} {vuln['package']} {vuln['range']!r}")
                continue
            for version in locked[vuln["package"]]:
                if is_vulnerable(version, alternatives, vuln["patched"]):
                    findings.append({
                        "stage": stage,
                        "ref": ref,
                        "package": vuln["package"],
                        "version": version,
                        "ghsa": adv["ghsa"],
                        "severity": adv["severity"],
                        "summary": adv["summary"],
                        "range": vuln["range"],
                        "patched": vuln["patched"],
                        "published_at": adv["published_at"],
                        "url": adv["url"],
                    })
    return findings


def run(args):
    advisories = fetch_advisories()
    unparsed = set()
    findings = []
    refs = {}

    if args.lockfile:
        with open(args.lockfile) as f:
            locked = locked_versions(f.read())
        refs["local"] = {"path": args.lockfile, "locked": locked}
        findings += match("local", args.lockfile, locked, advisories, unparsed)
    else:
        main_locked = locked_versions(remote_lock("main"))
        refs["main"] = {"ref": "main", "locked": main_locked}
        findings += match("main", "main", main_locked, advisories, unparsed)

        tag = gh(f"repos/{QUIC_REPO}/releases/latest")["tag_name"]
        release_locked = locked_versions(remote_lock(tag))
        refs["release"] = {"ref": tag, "locked": release_locked}
        findings += match("release", tag, release_locked, advisories, unparsed)

        for version in lodestar_quic_version():
            ltag = f"v{version}"
            lodestar_locked = release_locked if ltag == tag else locked_versions(remote_lock(ltag))
            refs.setdefault("lodestar", []).append({"libp2p_quic": version, "ref": ltag, "locked": lodestar_locked})
            findings += match("lodestar", ltag, lodestar_locked, advisories, unparsed)

    stages = {f["stage"] for f in findings}
    action = next((ACTIONS[s] for s in STAGE_ORDER if s in stages), "vulnerable" if findings else "none")
    keys = sorted({f"{f['stage']}:{f['ghsa']}:{f['package']}@{f['version']}" for f in findings})
    return {
        "ok": True,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "advisories": len(advisories),
        "action": action,
        "keys": keys,
        "refs": refs,
        "findings": findings,
        "unparsed": sorted(unparsed),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lockfile", help="check a local Cargo.lock instead of the remote refs")
    parser.add_argument("--brief", action="store_true", help="omit per-finding detail (for the trigger gate)")
    args = parser.parse_args()
    try:
        out = run(args)
        if args.brief:
            out.pop("findings")
    except Exception as e:  # noqa: BLE001 - the gate must always get a JSON line
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"[:500]}
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    sys.exit(main())
