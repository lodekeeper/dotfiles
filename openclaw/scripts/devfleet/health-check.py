#!/usr/bin/env python3
"""Daily health check for the ChainSafe Lodestar dev fleet.

SSHes into every host from the private inventory (never stored in this repo),
runs remote-probe.sh (read-only), evaluates issues, and prints a Discord-ready
report when a new or worsened issue appeared since the last acknowledged report.

Usage:
  health-check.py            # probe + print report (or NO_REPORT)
  health-check.py --force    # always print the full report
  health-check.py --ack      # mark the latest report as posted
"""

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

INVENTORY = Path(os.environ.get("DEVFLEET_HOSTS", Path.home() / ".config/devfleet/hosts.txt"))
STATE_DIR = Path(os.environ.get("DEVFLEET_STATE_DIR", Path.home() / ".openclaw/workspace/memory/devfleet-health"))
PROBE = Path(__file__).with_name("remote-probe.sh")
SSH_USER = "devops"
SSH_PORT = "3022"
SSH_TIMEOUT_S = 90
REMINDER_AFTER = dt.timedelta(days=7)
DISCORD_MAX = 1900
CORE = ("beacon", "validator", "execution")
IGNORED_UNITS = {"fwupd-refresh.service", "motd-news.service", "apt-daily.service", "apt-daily-upgrade.service"}
KERR_DISK = re.compile(r"I/O error|EXT4-fs error|XFS .*error|Buffer I/O|blk_update_request|nvme|ata[0-9.]+:|md/raid|Medium Error|critical medium", re.I)


def load_inventory():
    hosts = []
    for line in INVENTORY.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ip, name = line.split()[:2]
            hosts.append((name, ip))
    return hosts


def group_of(name):
    return "no_group" if name.startswith("nogroup") else name.split("-", 1)[0]


def probe(name, ip):
    cmd = [
        "ssh", "-p", SSH_PORT, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=10",
        f"{SSH_USER}@{ip}", "bash -s",
    ]
    try:
        with PROBE.open("rb") as stdin:
            res = subprocess.run(cmd, stdin=stdin, capture_output=True, timeout=SSH_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"name": name, "ok": False, "error": f"probe timed out after {SSH_TIMEOUT_S}s"}
    out = res.stdout.decode(errors="replace")
    if "probe_done=1" not in out and res.returncode != 0:
        err = res.stderr.decode(errors="replace").strip().splitlines()
        err = err[-1] if err else f"ssh exit {res.returncode}"
        return {"name": name, "ok": False, "error": err.replace(ip, "<ip>")[:200]}
    data = defaultdict(list)
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k].append(v)
    return {"name": name, "ok": True, "complete": "probe_done" in data, "data": dict(data)}


def first(d, k, default=None):
    v = d.get(k)
    return v[0] if v else default


def parse_json(s):
    try:
        return json.loads(s).get("data", {})
    except (TypeError, ValueError, AttributeError):
        return {}


def lodestar_minor(version):
    m = re.search(r"v(\d+\.\d+)", version or "")
    return m.group(1) if m else None


def evaluate(results):
    issues = []

    def add(sev, host, check, detail, msg):
        issues.append({"key": f"{host}:{check}:{detail}:{sev}", "sev": sev, "host": host, "msg": msg})

    versions = {}
    for r in results:
        h = r["name"]
        if not r["ok"]:
            add("crit", h, "unreachable", "-", f"unreachable: {r['error']}")
            continue
        d = r["data"]
        if not r["complete"]:
            add("warn", h, "probe", "incomplete", "probe output incomplete")
        ncpu = int(first(d, "ncpu", "1") or 1)
        load1 = float(first(d, "load1", "0") or 0)
        if load1 > 2 * ncpu:
            add("warn", h, "load", "-", f"load {load1:.1f} on {ncpu} cpus")
        mem = int(first(d, "mem_avail_pct", "100") or 100)
        if mem < 5:
            add("warn", h, "mem", "-", f"only {mem}% memory available")
        for entry in d.get("disk", []):
            mnt, pct = entry.rsplit(":", 1)
            pct = int(pct)
            if pct >= 90:
                add("crit", h, "disk", mnt, f"disk {mnt} {pct}% full")
            elif pct >= 80:
                add("warn", h, "disk", mnt, f"disk {mnt} {pct}% full")
        for entry in d.get("inode", []):
            mnt, pct = entry.rsplit(":", 1)
            if int(pct) >= 90:
                add("warn", h, "inode", mnt, f"inodes on {mnt} {pct}% used")
        failed = {}
        for entry in d.get("failed_unit", []):
            unit, _, enabled = entry.partition(":")
            failed[unit] = enabled
            # disabled + failed = leftover from a deployment that moved elsewhere (e.g. systemd -> docker)
            if unit in IGNORED_UNITS or enabled == "disabled":
                continue
            sev = "crit" if unit.split(".")[0] in CORE else "warn"
            add(sev, h, "failed_unit", unit, f"systemd unit failed: {unit}")
        has_beacon = False
        for entry in d.get("svc", []):
            svc, state = entry.split(":", 1)
            if f"{svc}.service" in failed:
                continue
            has_beacon |= svc == "beacon"
            if state != "active":
                add("crit", h, "svc", svc, f"{svc}.service is {state}")
        for entry in d.get("ctr", []):
            cname, status, code, health, restarts, image = (entry.split("|") + [""] * 6)[:6]
            has_beacon |= cname == "beacon"
            if cname in CORE and status != "running":
                add("crit", h, "ctr", cname, f"container {cname} is {status} (exit {code})")
            elif status in ("restarting", "dead"):
                add("crit", h, "ctr", cname, f"container {cname} is {status}")
            elif status == "exited" and code not in ("0", "137", "143"):
                add("warn", h, "ctr", cname, f"container {cname} exited with code {code}")
            if health == "unhealthy":
                add("warn", h, "ctr_health", cname, f"container {cname} is unhealthy")
        for entry in d.get("md", []):
            md, level, st, member = (entry.split(":") + ["", "", ""])[:4]
            if level == "INACTIVE" or "_" in st or member != "ok":
                add("crit", h, "raid", md, f"RAID {md} degraded ({level} {st} {member})")
        kerr = d.get("kerr", [])
        disk_err = [k for k in kerr if KERR_DISK.search(k)]
        if disk_err:
            add("crit", h, "kernel_disk", "-", f"kernel disk errors in last 24h, e.g. `{disk_err[-1][-160:]}`")
        if any(re.search(r"Out of memory|oom-kill", k, re.I) for k in kerr):
            add("warn", h, "oom", "-", "OOM kill in last 24h")
        for entry in d.get("smart", []):
            disk, health, used = (entry.split(":") + ["?", "?"])[:3]
            health = health.strip().rstrip("!")
            if health.upper() not in ("PASSED", "OK"):
                wear = f", wear {used}% of rated endurance" if used not in ("?", "") else ""
                add("crit", h, "smart", disk, f"SMART {disk} {health}{wear}")
        sync = parse_json(first(d, "bn_syncing"))
        if sync:
            dist = int(sync.get("sync_distance", "0") or 0)
            if sync.get("el_offline") in (True, "true"):
                add("crit", h, "bn", "el_offline", "beacon reports execution client offline")
            if sync.get("is_syncing") in (True, "true") and dist > 32:
                add("crit" if dist > 320 else "warn", h, "bn", "syncing", f"beacon syncing, {dist} slots behind")
            elif sync.get("is_optimistic") in (True, "true"):
                add("warn", h, "bn", "optimistic", "beacon head is optimistic")
            peers = int(parse_json(first(d, "bn_peers")).get("connected", "0") or 0)
            if peers < 10:
                add("warn", h, "bn", "peers", f"beacon has only {peers} peers")
            versions[h] = parse_json(first(d, "bn_version")).get("version", "")
        elif has_beacon:
            add("crit", h, "bn", "rest", "beacon REST API not responding")

    by_group = defaultdict(dict)
    for h, v in versions.items():
        if lodestar_minor(v):
            by_group[group_of(h)][h] = v
    for g, hv in by_group.items():
        if g == "no_group" or len(hv) < 3:
            continue
        majority, count = Counter(lodestar_minor(v) for v in hv.values()).most_common(1)[0]
        if count * 2 <= len(hv):
            continue
        for h, v in hv.items():
            if lodestar_minor(v) != majority:
                add("warn", h, "version", "drift", f"runs {v.split('/')[1]}, rest of {g} is on v{majority}")
    return issues, versions


def format_report(now, results, issues, prev_open, reminder):
    ok = sum(1 for r in results if r["ok"])
    cur = {i["key"]: i for i in issues}
    base = lambda k: k.rsplit(":", 1)[0]
    cur_base = {base(k) for k in cur}
    new = [i for k, i in cur.items() if k not in prev_open]
    still = [i for k, i in cur.items() if k in prev_open]
    resolved = [dict(v, sev="ok") for k, v in prev_open.items() if k not in cur and base(k) not in cur_base]

    def host_lines(items, resolved_section=False):
        per_host = defaultdict(list)
        for i in items:
            per_host[i["host"]].append(i)
        rows = []
        for host, its in per_host.items():
            crit = any(i["sev"] == "crit" for i in its)
            icon = "✅" if resolved_section else ("🔴" if crit else "🟡")
            its.sort(key=lambda i: i["sev"] != "crit")
            rows.append((not crit, host, f"- {icon} **{host}**: " + "; ".join(i["msg"] for i in its)))
        return [r[2] for r in sorted(rows)]

    lines = [f"🩺 **Dev fleet health** ({now:%Y-%m-%d %H:%M} UTC): {ok}/{len(results)} hosts reachable, "
             f"{len({i['host'] for i in issues})} host(s) with issues"]
    if reminder and not new and not resolved:
        lines.append("_Weekly reminder, nothing changed:_")
    for title, items, res in (("New", new, False), ("Still open", still, False), ("Resolved", resolved, True)):
        if items:
            lines.append(f"**{title}**")
            lines.extend(host_lines(items, res))
    out, used = [], 0
    for idx, line in enumerate(lines):
        if used + len(line) + 1 > DISCORD_MAX:
            out.append(f"… +{len(lines) - idx} more lines (full report: memory/devfleet-health/latest.json)")
            break
        out.append(line)
        used += len(line) + 1
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--ack", action="store_true")
    args = ap.parse_args()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path, latest_path = STATE_DIR / "state.json", STATE_DIR / "latest.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"reported_open": {}, "last_report_at": None}

    if args.ack:
        latest = json.loads(latest_path.read_text())
        state["reported_open"] = {i["key"]: {"host": i["host"], "msg": i["msg"]} for i in latest["issues"]}
        state["last_report_at"] = latest["checked_at"]
        state_path.write_text(json.dumps(state, indent=2))
        print(f"acked report from {latest['checked_at']} ({len(latest['issues'])} open issues)")
        return

    now = dt.datetime.now(dt.timezone.utc)
    hosts = load_inventory()
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda nh: probe(*nh), hosts))
    issues, versions = evaluate(results)
    latest_path.write_text(json.dumps({
        "checked_at": now.isoformat(), "hosts": len(results),
        "reachable": sum(1 for r in results if r["ok"]), "issues": issues, "versions": versions,
    }, indent=2))

    prev_open = state.get("reported_open", {})
    cur_keys = {i["key"] for i in issues}
    # Only new or worsened issues trigger a post; resolutions ride along with the next report,
    # so a check flapping around its threshold does not post every day.
    worsened = {k for k in cur_keys - set(prev_open)
                if not (k.endswith(":warn") and k.rsplit(":", 1)[0] + ":crit" in prev_open)}
    last = state.get("last_report_at")
    reminder = bool(cur_keys) and (last is None or now - dt.datetime.fromisoformat(last) > REMINDER_AFTER)
    if args.force or worsened or reminder:
        print(format_report(now, results, issues, prev_open, reminder))
    else:
        print(f"NO_REPORT ({len(cur_keys)} open issue(s), unchanged since {last})")


if __name__ == "__main__":
    sys.exit(main())
