#!/usr/bin/env python3
"""
Zoom into one gossip-flood episode at fine resolution and check, per bn node:
  recv_msgs spike -> network-worker stall (eventloop p99 / GC time) -> mesh loss (count drop + churn)
with a WORKER-RESTART guard (a worker restart also resets GC + drops mesh = false triple).
Usage: gossip_gc_mesh_zoom.py <start_iso_utc> <hours>
"""
import json, os, sys, time, urllib.parse, urllib.request, statistics as st
from datetime import datetime, timezone

BASE = "https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1"
TOKEN = os.environ["GRAFANA_TOKEN"]
NRE = '.*-bn-[0-9]+'
G = f'group="lido_prod",instance=~"{NRE}"'
STEP = 120

start_iso = sys.argv[1] if len(sys.argv) > 1 else "2026-08-25T04:00:00"
hours = float(sys.argv[2]) if len(sys.argv) > 2 else 7.5
START = int(datetime.fromisoformat(start_iso).replace(tzinfo=timezone.utc).timestamp())
END = min(int(time.time()), START + int(hours * 3600))

SIG = {
    "recv": f'sum by (instance)(rate(gossipsub_rpc_recv_message_total{{{G}}}[3m]))',
    "gc":   f'sum by (instance)(rate(network_worker_nodejs_gc_duration_seconds_sum{{{G}}}[3m]))',
    "elp99":f'max by (instance)(network_worker_nodejs_eventloop_lag_p99_seconds{{{G}}})',
    "mesh": f'sum by (instance)(lodestar_gossip_mesh_peers_by_type_count{{{G},type!~"beacon_attestation"}})',
    "churn":f'sum by (instance)(rate(gossipsub_peer_churn_events_disconnected_total{{{G}}}[3m]) + rate(gossipsub_peer_churn_events_prune_total{{{G}}}[3m]))',
    "start":f'max by (instance)(network_worker_process_start_time_seconds{{{G}}})',
}


def qr(expr):
    p = urllib.parse.urlencode({"query": expr, "start": START, "end": END, "step": STEP})
    r = urllib.request.Request(f"{BASE}/query_range?{p}", headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(r, timeout=120) as f:
        d = json.load(f)
    return {s["metric"]["instance"]: {int(float(t)): float(v) for t, v in s["values"] if v not in ("NaN","+Inf","-Inf")}
            for s in d["data"]["result"]}


def isot(ts): return time.strftime("%m-%d %H:%M", time.gmtime(ts))
data = {k: qr(e) for k, e in SIG.items()}
nodes = sorted(set(data["recv"]), key=lambda s: (("ovh" in s), int(s.split("-")[-1])))
print(f"episode {isot(START)} -> {isot(END)} UTC (step {STEP}s)\n")
print(f"{'node':<26} {'recv base->pk':>16} {'gc pk':>7} {'elP99 pk':>9} {'mesh base->min':>15} {'churn pk':>9} {'restart':>8} {'STALL@flood':>12}")
hits = []
for n in nodes:
    rc, gc, el = data["recv"].get(n,{}), data["gc"].get(n,{}), data["elp99"].get(n,{})
    mp, ch, stt = data["mesh"].get(n,{}), data["churn"].get(n,{}), data["start"].get(n,{})
    if not rc: continue
    ts = sorted(rc)
    base_rc = st.median(list(rc.values())); pk_rc = max(rc.values())
    base_mp = st.median(list(mp.values())) if mp else 0; min_mp = min(mp.values()) if mp else 0
    pk_gc = max(gc.values()) if gc else 0; pk_el = max(el.values()) if el else 0; pk_ch = max(ch.values()) if ch else 0
    restarted = bool(stt) and (max(stt.values()) - min(stt.values()) > 1)
    # flood window = times recv > 1.8x base
    flood_ts = [t for t in ts if rc[t] > max(base_rc*1.8, base_rc+200)]
    stall_at_flood = False
    base_el = st.median(list(el.values())) if el else 0
    base_gc = st.median(list(gc.values())) if gc else 0
    for t in flood_ts:
        win=[t-STEP, t, t+STEP, t+2*STEP]
        if (any(el.get(w,0) > max(base_el*2, base_el+0.05) for w in win) or
            any(gc.get(w,0) > max(base_gc*2, 0.05) for w in win)):
            stall_at_flood = True; break
    flag = "RESTART" if restarted else ("yes" if stall_at_flood else "-")
    if stall_at_flood and not restarted: hits.append(n)
    print(f"{n:<26} {base_rc:>6.0f}->{pk_rc:>6.0f} {pk_gc:>7.2f} {pk_el:>9.2f} "
          f"{base_mp:>6.0f}->{min_mp:>5.0f} {pk_ch:>9.1f} {'yes' if restarted else '-':>8} {flag:>12}")
print(f"\nnodes with network-worker STALL co-timed with the flood (excluding restarts): {len(hits)}/{len(nodes)}")
print(" ", ", ".join(h.replace('-lido-prod','') for h in hits))
