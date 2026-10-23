#!/usr/bin/env python3
"""Collect vulnerability candidates for Lodestar / lodestar-z and their production dependencies.

Sources
  osv-npm     OSV.dev over the production closure of the pnpm lockfiles
              (lodestar: packages/cli + root prod deps; lodestar-z: root prod deps),
              for the default branch and the latest release of each repo.
  osv-crates  OSV.dev over the Cargo.lock of the @chainsafe/libp2p-quic version Lodestar resolves.
  node        Node.js security releases newer than the Node in the published chainsafe/lodestar image.
  ghsa-repo   GitHub repository advisories: upstream native libs, lodestar-z Zig deps,
              peer consensus clients, libp2p implementations/specs.
  pwn         pwn.watch incidents (all categories), keyword-flagged against the Lodestar stack.

Commands
  scan        print candidates that have no triage verdict yet (state: memory/vuln-watch/)
  mark        record a verdict for one or more candidate keys
  mark-rest   record a verdict for every untriaged candidate of the last scan
  show        print ledger entries (optionally filtered by verdict)

Every alerted/ignored key is never surfaced again. Keys marked `watch` resurface when the
underlying record changes (new fixed version, patch status, severity, advisory update).
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request

import yaml

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
STATE_DIR = os.path.join(WORKSPACE, "memory", "vuln-watch")
LEDGER_PATH = os.path.join(STATE_DIR, "ledger.json")
LAST_SCAN_PATH = os.path.join(STATE_DIR, "last-scan.json")

BASELINE_DAYS = 30
PWN_BASELINE_DAYS = 14
VERDICTS = ("alert", "ignore", "watch", "covered")

NPM_REPOS = [
    # repo, default branch, importer roots that make up the production install
    ("ChainSafe/lodestar", "unstable", ["packages/cli", "."]),
    ("ChainSafe/lodestar-z", "main", ["."]),
]

# Zig deps compiled into the lodestar-z NAPI bindings (build.zig.zon `libraries.bindings` imports).
# zbuild/zbench/zig-yaml/snappy/zio are build, bench, test or non-bindings modules.
ZIG_PROD_DEPS = {"blst", "hashtree", "zapi", "metrics", "ere"}

ADVISORY_REPOS = {
    # upstream native code shipped inside Lodestar's production install
    "supranational/blst": "native: BLS (blst, via lodestar-z / blst.zig)",
    "OffchainLabs/hashtree": "native: SHA256 hashtree (via @chainsafe/hashtree, hashtree-z)",
    "crate-crypto/rust-eth-kzg": "native: KZG (@crate-crypto/node-eth-kzg)",
    "Brooooooklyn/snappy": "native: snappy npm package (napi-rs)",
    "google/leveldb": "native: LevelDB (classic-level)",
    "Level/classic-level": "native: classic-level LevelDB binding",
    "napi-rs/napi-rs": "native: napi-rs runtime used by Rust addons",
    "ziglang/zig": "toolchain: Zig compiler/stdlib for lodestar-z",
    # libp2p / networking (protocol-level bugs often apply across implementations)
    "libp2p/specs": "protocol: libp2p specs",
    "libp2p/js-libp2p": "networking: js-libp2p monorepo, incl. @libp2p/gossipsub (Lodestar's gossipsub)",
    "ChainSafe/js-libp2p-gossipsub": "networking: legacy ChainSafe gossipsub repo",
    "ChainSafe/js-libp2p-quic": "networking: libp2p QUIC transport (ChainSafe)",
    "ChainSafe/discv5": "networking: discv5 (ChainSafe)",
    "libp2p/go-libp2p": "protocol peer: go-libp2p",
    "libp2p/go-libp2p-pubsub": "protocol peer: go gossipsub",
    "libp2p/rust-libp2p": "protocol peer: rust-libp2p",
    "sigp/discv5": "protocol peer: rust discv5",
    # consensus clients: same spec, bug classes frequently shared
    "sigp/lighthouse": "peer client: Lighthouse",
    "OffchainLabs/prysm": "peer client: Prysm",
    "Consensys/teku": "peer client: Teku",
    "status-im/nimbus-eth2": "peer client: Nimbus",
    "grandinetech/grandine": "peer client: Grandine",
    "ethereum/consensus-specs": "spec: consensus-specs",
    # our own repos (published advisories are known to us; listed so nothing is missed)
    "ChainSafe/lodestar": "own: Lodestar",
    "ChainSafe/lodestar-z": "own: lodestar-z",
}

# Covered by the dedicated quinn automations (#quic-high-security-vulnerabilities); never re-alert here.
COVERED_ELSEWHERE_CRATES = {"quinn", "quinn-proto", "quinn-udp"}

PWN_TAG_HITS = {
    "node", "npm", "supply-chain", "shai-hulud", "rust", "docker", "github-actions", "github",
    "crypto", "tls", "linux",
}
PWN_KEYWORDS = [
    r"node\.?js", r"\bnpm\b", r"\bv8\b", r"libuv", r"undici", r"llhttp", r"openssl", r"\bc-ares\b",
    r"libp2p", r"\bquic\b", r"rustls", r"aws-lc", r"\bring\b crate", r"quinn", r"crates?\.io",
    r"\bcargo\b", r"\bzig\b", r"leveldb", r"snappy", r"\bblst\b", r"\bkzg\b", r"ethereum",
    r"consensus client", r"beacon (node|chain)", r"validator client", r"\bglibc\b", r"debian",
    r"docker", r"github actions?", r"pnpm", r"typescript", r"javascript", r"websocket",
    r"protobuf", r"\bsecp256k1\b", r"\bnoble\b", r"elliptic", r"bls12",
]
PWN_RE = re.compile("|".join(PWN_KEYWORDS), re.I)


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_ts(s):
    if not s:
        return None
    s = s.strip()
    if len(s) == 10:
        s += "T00:00:00Z"
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def days_ago(s):
    t = parse_ts(s)
    if t is None:
        return None
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 86400


def http(url, data=None, headers=None, timeout=60, raw=False):
    hdrs = {"User-Agent": "lodekeeper-vuln-watch/1.0"}
    hdrs.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        hdrs["Content-Type"] = "application/json"
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = r.read()
                return payload if raw else json.loads(payload)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404):
                raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
        time.sleep(2 * (attempt + 1))
    raise last


def gh(args, raw=False):
    cmd = ["gh", "api", *args]
    if raw:
        cmd += ["-H", "Accept: application/vnd.github.raw"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(f"gh api {' '.join(args)}: {p.stderr.strip()[:300]}")
    return p.stdout if raw else json.loads(p.stdout)


def gh_file(repo, path, ref):
    return gh([f"repos/{repo}/contents/{path}?ref={urllib.parse.quote(ref)}"], raw=True)


def latest_release_tag(repo):
    return gh([f"repos/{repo}/releases/latest"])["tag_name"]


# ---------------------------------------------------------------- npm closure


def split_dep(name, version):
    """Return (real_name, snapshot_key, clean_version) or None for links/files."""
    if version.startswith(("link:", "file:", "http:", "https:", "git")):
        return None
    if version[0].isdigit():
        return name, f"{name}@{version}", version.split("(")[0]
    base = version.split("(")[0]
    real, _, ver = base.rpartition("@")
    if not real:
        return None
    return real, version, ver


def npm_prod_closure(lock_text, roots):
    lock = yaml.safe_load(lock_text)
    importers = lock.get("importers", {})
    snapshots = lock.get("snapshots", {}) or {}
    pkgs = {}  # (name, ver) -> chain
    seen_keys = set()
    queue = []

    def importer_label(path):
        return "lodestar(root)" if path == "." else path

    seen_importers = set()

    def add_importer(path, chain):
        if path in seen_importers or path not in importers:
            return
        seen_importers.add(path)
        imp = importers[path]
        for section in ("dependencies", "optionalDependencies"):
            for name, spec in (imp.get(section) or {}).items():
                ver = spec["version"] if isinstance(spec, dict) else str(spec)
                if ver.startswith("link:"):
                    target = os.path.normpath(os.path.join(path, ver[5:]))
                    add_importer(target, chain + [name])
                    continue
                d = split_dep(name, ver)
                if d:
                    queue.append((d, chain + [f"{d[0]}@{d[2]}"]))

    for r in roots:
        add_importer(r, [importer_label(r)])

    while queue:
        (real, key, ver), chain = queue.pop(0)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        pkgs.setdefault((real, ver), chain)
        snap = snapshots.get(key) or {}
        for section in ("dependencies", "optionalDependencies"):
            for name, v in (snap.get(section) or {}).items():
                d = split_dep(name, str(v))
                if d and d[1] not in seen_keys:
                    queue.append((d, chain + [f"{d[0]}@{d[2]}"]))
    return pkgs


# ---------------------------------------------------------------- OSV


_vuln_cache = {}


def osv_batch(queries):
    """queries: list of (ecosystem, name, version) -> list of vuln id lists."""
    out = []
    for i in range(0, len(queries), 500):
        chunk = queries[i:i + 500]
        body = {"queries": [{"package": {"ecosystem": e, "name": n}, "version": v} for e, n, v in chunk]}
        res = http("https://api.osv.dev/v1/querybatch", data=body, timeout=120)
        for r in res.get("results", []):
            out.append([v["id"] for v in (r.get("vulns") or [])])
    return out


def osv_vuln(vid):
    if vid not in _vuln_cache:
        _vuln_cache[vid] = http(f"https://api.osv.dev/v1/vulns/{vid}")
    return _vuln_cache[vid]


def osv_summary(vid, ecosystem, name):
    v = osv_vuln(vid)
    if v.get("withdrawn"):
        return None
    fixed, ranges = set(), []
    for a in v.get("affected", []):
        p = a.get("package", {})
        if p.get("name") != name or p.get("ecosystem", "").lower() != ecosystem.lower():
            continue
        for rg in a.get("ranges", []):
            evs = rg.get("events", [])
            ranges.append(" ".join(f"{k}={val}" for e in evs for k, val in e.items()))
            for e in evs:
                if "fixed" in e:
                    fixed.add(e["fixed"])
    sev = (v.get("database_specific") or {}).get("severity")
    cvss = [s.get("score") for s in v.get("severity", []) if s.get("score")]
    refs = [r["url"] for r in v.get("references", []) if r.get("type") in ("ADVISORY", "WEB", "FIX")][:4]
    return {
        "id": vid,
        "aliases": v.get("aliases", []),
        "summary": v.get("summary") or "",
        "details": (v.get("details") or "")[:700],
        "severity": sev,
        "cvss": cvss[:1],
        "published": v.get("published"),
        "modified": v.get("modified"),
        "fixed": sorted(fixed),
        "ranges": ranges[:3],
        "refs": refs,
    }


# ---------------------------------------------------------------- collectors


def collect_npm(errors):
    found = {}  # key -> candidate
    targets = []
    for repo, branch, roots in NPM_REPOS:
        refs = [branch]
        try:
            tag = latest_release_tag(repo)
            refs.append(tag)
        except Exception as e:
            errors.append(f"{repo} latest release: {e}")
        for ref in refs:
            try:
                targets.append((repo, ref, npm_prod_closure(gh_file(repo, "pnpm-lock.yaml", ref), roots)))
            except Exception as e:
                errors.append(f"{repo}@{ref} lockfile: {e}")

    queries, owners = [], []
    for repo, ref, pkgs in targets:
        for (name, ver), chain in pkgs.items():
            queries.append(("npm", name, ver))
            owners.append((repo, ref, chain))
    if queries:
        try:
            results = osv_batch(queries)
        except Exception as e:
            errors.append(f"osv npm batch: {e}")
            results = []
        for (eco, name, ver), (repo, ref, chain), vids in zip(queries, owners, results):
            for vid in vids:
                key = f"osv:npm:{name}:{vid}"
                c = found.setdefault(key, {"key": key, "source": "osv-npm", "package": name, "versions": {}, "chains": {}})
                c["versions"].setdefault(ver, []).append(f"{repo.split('/')[1]}@{ref}")
                c["chains"].setdefault(f"{repo.split('/')[1]}@{ref}", " > ".join(chain))
    return found, targets


def collect_crates(npm_targets, errors):
    found = {}
    versions = set()
    for repo, ref, pkgs in npm_targets:
        if repo != "ChainSafe/lodestar":
            continue
        for (name, ver) in pkgs:
            if name == "@chainsafe/libp2p-quic":
                versions.add((ver, f"lodestar@{ref}"))
    by_ver = {}
    for ver, owner in versions:
        by_ver.setdefault(ver, []).append(owner)
    for ver, owners_ in by_ver.items():
        try:
            lock = tomllib.loads(gh_file("ChainSafe/js-libp2p-quic", "Cargo.lock", f"v{ver}"))
        except Exception as e:
            errors.append(f"js-libp2p-quic v{ver} Cargo.lock: {e}")
            continue
        crates = [(p["name"], p["version"]) for p in lock.get("package", []) if "crates.io-index" in (p.get("source") or "")]
        try:
            results = osv_batch([("crates.io", n, v) for n, v in crates])
        except Exception as e:
            errors.append(f"osv crates batch: {e}")
            continue
        for (name, cver), vids in zip(crates, results):
            for vid in vids:
                key = f"osv:crates.io:{name}:{vid}"
                c = found.setdefault(key, {"key": key, "source": "osv-crates", "package": name, "versions": {}, "chains": {}})
                c["versions"].setdefault(cver, []).extend(owners_)
                c["chains"].setdefault(f"libp2p-quic@{ver}", f"@chainsafe/libp2p-quic@{ver} (Rust) > {name}@{cver}")
                if name in COVERED_ELSEWHERE_CRATES:
                    c["covered_elsewhere"] = "quinn-advisory-watch automation"
    return found


def semver(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def docker_image_node_version(image="chainsafe/lodestar", tag="latest"):
    tok = http(f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{image}:pull")["token"]
    auth = {"Authorization": f"Bearer {tok}"}
    accept_index = "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json"
    accept_manifest = "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"
    idx = http(f"https://registry-1.docker.io/v2/{image}/manifests/{tag}", headers={**auth, "Accept": f"{accept_index}, {accept_manifest}"})
    manifest = idx
    if "manifests" in idx:
        amd = next(m for m in idx["manifests"] if m.get("platform", {}).get("architecture") == "amd64")
        manifest = http(f"https://registry-1.docker.io/v2/{image}/manifests/{amd['digest']}", headers={**auth, "Accept": accept_manifest})
    cfg = http(f"https://registry-1.docker.io/v2/{image}/blobs/{manifest['config']['digest']}", headers=auth)
    env = dict(e.split("=", 1) for e in cfg.get("config", {}).get("Env", []) if "=" in e)
    labels = cfg.get("config", {}).get("Labels") or {}
    return env.get("NODE_VERSION"), cfg.get("created"), labels


def collect_node(errors):
    found = {}
    try:
        img_node, created, _ = docker_image_node_version()
    except Exception as e:
        errors.append(f"docker image node version: {e}")
        return found
    if not img_node:
        errors.append("docker image: NODE_VERSION env missing")
        return found
    try:
        idx = http("https://nodejs.org/dist/index.json")
    except Exception as e:
        errors.append(f"nodejs dist index: {e}")
        return found
    major = semver(img_node)[0]
    newer_sec = [r for r in idx if r.get("security") and semver(r["version"])[0] == major and semver(r["version"]) > semver(img_node)]
    if newer_sec:
        latest = max(newer_sec, key=lambda r: semver(r["version"]))
        key = f"node:image-{img_node}:sec-{latest['version'].lstrip('v')}"
        found[key] = {
            "key": key,
            "source": "node",
            "image": "chainsafe/lodestar:latest",
            "image_node": img_node,
            "image_created": created,
            "security_releases_newer_than_image": [f"{r['version']} ({r['date']})" for r in sorted(newer_sec, key=lambda r: semver(r["version"]))],
            "latest_in_major": max((r for r in idx if semver(r["version"])[0] == major), key=lambda r: semver(r["version"]))["version"],
            "hint": "CVE list: https://nodejs.org/en/blog/vulnerability (pick the post for the release date)",
        }
    return found


def zig_dep_repos(errors):
    repos = {}
    for ref in ("main",):
        try:
            zon = gh_file("ChainSafe/lodestar-z", "build.zig.zon", ref)
        except Exception as e:
            errors.append(f"lodestar-z build.zig.zon: {e}")
            continue
        for name, url in re.findall(r"^\s*\.(\w+)\s*=\s*\.\{\s*\n\s*\.url\s*=\s*\"([^\"]+)\"", zon, re.M):
            m = re.search(r"github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[#?/]|$)", url)
            if not m:
                continue
            pin = re.search(r"(?:#|/archive/)([0-9a-f]{7,40})", url)
            role = "lodestar-z zig dep (bindings, production)" if name in ZIG_PROD_DEPS else "lodestar-z zig dep (build/test/non-bindings)"
            repos[f"{m.group(1)}/{m.group(2)}"] = f"{role}: .{name} pinned {pin.group(1) if pin else '?'}"
    return repos


def collect_repo_advisories(ledger, errors):
    found = {}
    repos = dict(ADVISORY_REPOS)
    repos.update(zig_dep_repos(errors))
    init = ledger.setdefault("sources", {}).setdefault("ghsa-repo", {})
    for repo, role in sorted(repos.items()):
        try:
            advs = gh([f"repos/{repo}/security-advisories?per_page=100&sort=updated&direction=desc"])
        except Exception as e:
            if "Not Found" in str(e):
                continue  # repo has no advisories feature / renamed; not an error worth noise
            errors.append(f"advisories {repo}: {e}")
            continue
        first_time = repo not in init
        for a in advs:
            if a.get("state") != "published":
                continue
            key = f"ghsa:{repo}:{a['ghsa_id']}"
            cand = {
                "key": key,
                "source": "ghsa-repo",
                "repo": repo,
                "role": role,
                "ghsa": a["ghsa_id"],
                "cve": a.get("cve_id"),
                "severity": a.get("severity"),
                "summary": a.get("summary"),
                "published": a.get("published_at"),
                "updated": a.get("updated_at"),
                "url": a.get("html_url"),
                "packages": [
                    {"pkg": (v.get("package") or {}).get("name"), "eco": (v.get("package") or {}).get("ecosystem"),
                     "vulnerable": v.get("vulnerable_version_range"), "patched": v.get("patched_versions")}
                    for v in (a.get("vulnerabilities") or [])
                ][:4],
                "description": (a.get("description") or "")[:900],
                "_baseline": first_time and (days_ago(a.get("published_at")) or 0) > BASELINE_DAYS,
                "_fingerprint": a.get("updated_at"),
            }
            found[key] = cand
        init[repo] = init.get(repo) or now_iso()
    return found


def collect_pwn(ledger, errors):
    found = {}
    try:
        data = http("https://pwn.watch/incidents.json")
    except Exception as e:
        errors.append(f"pwn.watch: {e}")
        return found
    src = ledger.setdefault("sources", {})
    first_time = "pwn" not in src
    live = set(data.get("live", []))
    for i in data.get("incidents", []):
        text = " ".join([i.get("title") or "", i.get("product") or "", i.get("summary") or ""])
        tags = set(i.get("tags") or []) | set(i.get("stacks") or [])
        hit = bool(tags & PWN_TAG_HITS) or bool(PWN_RE.search(text)) or i.get("category") == "supply-chain"
        key = f"pwn:{i['slug']}"
        found[key] = {
            "key": key,
            "source": "pwn",
            "stack_hit": hit,
            "title": i.get("title"),
            "url": i.get("url"),
            "json": i.get("json"),
            "category": i.get("category"),
            "severity": i.get("severity"),
            "patchStatus": i.get("patchStatus"),
            "status": i.get("status"),
            "product": i.get("product"),
            "tags": sorted(tags),
            "cves": i.get("cveIds", [])[:6],
            "affected": (i.get("affectedVersions") or [])[:5],
            "fixed": (i.get("fixedVersions") or [])[:6],
            "summary": (i.get("summary") or "")[:700],
            "updatedAt": i.get("updatedAt"),
            "_baseline": first_time and i["slug"] not in live and (days_ago(i.get("updatedAt")) or 0) > PWN_BASELINE_DAYS,
            "_fingerprint": f"{i.get('patchStatus')}|{i.get('severity')}|{i.get('status')}",
        }
    src["pwn"] = src.get("pwn") or now_iso()
    return found


# ---------------------------------------------------------------- ledger


def load_ledger():
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH) as f:
            return json.load(f)
    return {"items": {}, "sources": {}}


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def fingerprint(c):
    if "_fingerprint" in c:
        return c["_fingerprint"]
    if c["source"] in ("osv-npm", "osv-crates"):
        return "|".join(sorted(c.get("versions", {}))) + "|" + ",".join(c.get("detail", {}).get("fixed", []))
    return c["key"]


def needs_triage(c, ledger):
    e = ledger["items"].get(c["key"])
    if not e:
        return True
    if e["verdict"] == "watch":
        return e.get("fingerprint") != fingerprint(c)
    return False


def cmd_scan(args):
    ledger = load_ledger()
    errors = []
    candidates = {}
    npm_found, npm_targets = collect_npm(errors)
    candidates.update(npm_found)
    candidates.update(collect_crates(npm_targets, errors))
    candidates.update(collect_node(errors))
    candidates.update(collect_repo_advisories(ledger, errors))
    candidates.update(collect_pwn(ledger, errors))

    # Auto-baseline old records from sources seen for the first time.
    baselined = 0
    for k, c in candidates.items():
        if c.pop("_baseline", False) and k not in ledger["items"]:
            ledger["items"][k] = {"verdict": "ignore", "reason": "baseline: older than first-scan window",
                                  "at": now_iso(), "fingerprint": fingerprint(c), "auto": True}
            baselined += 1

    def osv_needs_detail(c):
        e = ledger["items"].get(c["key"])
        return c["source"] in ("osv-npm", "osv-crates") and (not e or e["verdict"] == "watch")

    for c in candidates.values():
        if osv_needs_detail(c):
            try:
                det = osv_summary(c["key"].rsplit(":", 1)[1], "npm" if c["source"] == "osv-npm" else "crates.io", c["package"])
            except Exception as e:
                errors.append(f"osv detail {c['key']}: {e}")
                det = None
            if det is None and not any(c["key"] in err for err in errors):
                c["withdrawn"] = True
            c["detail"] = det or {}
    pending = [c for c in candidates.values() if needs_triage(c, ledger)]
    for c in pending:
        prev = ledger["items"].get(c["key"])
        if prev:
            c["previous_verdict"] = {k: prev.get(k) for k in ("verdict", "reason", "at")}
    pending = [c for c in pending if not c.get("withdrawn")]
    for c in pending:
        c["_fp"] = fingerprint(c)

    inventory = {f"{r.split('/')[1]}@{ref}": len(p) for r, ref, p in npm_targets}
    scan = {"at": now_iso(), "inventory_npm_prod_packages": inventory, "errors": errors,
            "baselined": baselined, "pending": pending}
    save_json(LAST_SCAN_PATH, scan)
    save_json(LEDGER_PATH, ledger)

    if args.json:
        print(json.dumps(scan, indent=1))
        return
    print(f"# vuln-watch scan {scan['at']}")
    print(f"npm prod packages scanned: {inventory}")
    if baselined:
        print(f"auto-baselined (first scan of a source, older than window): {baselined}")
    if errors:
        print("SOURCE ERRORS (coverage gaps this run):")
        for e in errors:
            print(f"  - {e}")
    if not pending:
        print("NO_NEW_CANDIDATES")
        return
    detailed = [c for c in pending if c["source"] != "pwn" or c["stack_hit"]]
    compact = [c for c in pending if c["source"] == "pwn" and not c["stack_hit"]]
    print(f"\n{len(pending)} untriaged candidates ({len(detailed)} detailed, {len(compact)} pwn.watch one-liners)\n")
    for c in detailed:
        out = {k: v for k, v in c.items() if not k.startswith("_") and k not in ("stack_hit",)}
        print("=== " + c["key"])
        print(json.dumps(out, indent=1, ensure_ascii=False))
    if compact:
        print("\n--- pwn.watch incidents without a Lodestar-stack keyword hit (scan titles; mark any that matter) ---")
        for c in compact:
            print(f"{c['key']} | {c['category']} | {c['severity']} | {c['patchStatus']} | {c['title']} | {c['product']}")


def cmd_mark(args):
    ledger = load_ledger()
    scan = json.load(open(LAST_SCAN_PATH)) if os.path.exists(LAST_SCAN_PATH) else {"pending": []}
    fps = {c["key"]: c.get("_fp", "") for c in scan["pending"]}
    for key in args.keys:
        if key not in fps and key not in ledger["items"]:
            print(f"warning: {key} not in last scan", file=sys.stderr)
        ledger["items"][key] = {"verdict": args.verdict, "reason": args.reason, "at": now_iso(),
                                "fingerprint": fps.get(key, ledger["items"].get(key, {}).get("fingerprint", ""))}
        print(f"marked {key} -> {args.verdict}")
    save_json(LEDGER_PATH, ledger)


def cmd_mark_rest(args):
    ledger = load_ledger()
    scan = json.load(open(LAST_SCAN_PATH))
    n = 0
    for c in scan["pending"]:
        e = ledger["items"].get(c["key"])
        if e and e.get("at", "") >= scan["at"]:
            continue  # already marked after this scan
        if args.source and c["source"] != args.source:
            continue
        ledger["items"][c["key"]] = {"verdict": args.verdict, "reason": args.reason, "at": now_iso(), "fingerprint": c.get("_fp", "")}
        n += 1
    save_json(LEDGER_PATH, ledger)
    print(f"marked {n} remaining candidates -> {args.verdict}")


def cmd_lookup(args):
    """Search every lockfile entry (prod AND dev) for supply-chain checks."""
    pats = [re.compile(rf"^'?{re.escape(n)}@([^':(]+)", re.M) for n in args.names]
    for repo, branch, _ in NPM_REPOS:
        refs = [branch]
        try:
            refs.append(latest_release_tag(repo))
        except Exception as e:
            print(f"{repo}: latest release lookup failed: {e}")
        for ref in refs:
            try:
                text = gh_file(repo, "pnpm-lock.yaml", ref)
            except Exception as e:
                print(f"{repo}@{ref}: lockfile fetch failed: {e}")
                continue
            body = "\n".join(line[2:] for line in text.splitlines() if line.startswith("  ") and not line.startswith("   "))
            for n, pat in zip(args.names, pats):
                vers = sorted(set(pat.findall(body)))
                print(f"{repo}@{ref}: {n}: {', '.join(vers) if vers else 'not present'}")


def cmd_show(args):
    ledger = load_ledger()
    for k, e in sorted(ledger["items"].items()):
        if args.verdict and e["verdict"] != args.verdict:
            continue
        if e.get("auto") and not args.all:
            continue
        print(f"{k} | {e['verdict']} | {e['at']} | {e['reason']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="collect and print untriaged candidates")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_scan)
    m = sub.add_parser("mark", help="record a verdict for candidate keys")
    m.add_argument("keys", nargs="+")
    m.add_argument("--verdict", required=True, choices=VERDICTS)
    m.add_argument("--reason", required=True)
    m.set_defaults(func=cmd_mark)
    r = sub.add_parser("mark-rest", help="record a verdict for every candidate of the last scan not yet marked")
    r.add_argument("--verdict", required=True, choices=VERDICTS)
    r.add_argument("--reason", required=True)
    r.add_argument("--source", choices=("osv-npm", "osv-crates", "node", "ghsa-repo", "pwn"))
    r.set_defaults(func=cmd_mark_rest)
    lk = sub.add_parser("lookup", help="list versions of npm packages present in any lockfile (prod and dev)")
    lk.add_argument("names", nargs="+")
    lk.set_defaults(func=cmd_lookup)
    sh = sub.add_parser("show", help="print ledger entries")
    sh.add_argument("--verdict", choices=VERDICTS)
    sh.add_argument("--all", action="store_true", help="include auto-baselined entries")
    sh.set_defaults(func=cmd_show)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
