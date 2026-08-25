#!/usr/bin/env python3
"""
twoeths' hypothesis across all lido-prod bn nodes:
  gossip-attestation flood (gossipsub_rpc_recv_message spike)
  -> NETWORK WORKER gc spike (network_worker_nodejs_gc_duration_seconds)
  -> mesh peer loss (mesh_peers_by_type drop + peer_churn disconnected/prune)
Pulls 30d query_range from grafana-lodestar Prometheus (DS 1), detects co-timed
events locally, ranks nodes, and checks whether floods are fleet-wide. Read-only.
"""
import json, os, sys, time, urllib.parse, urllib.request, statistics as st
from collections import Counter, defaultdict

BASE = "https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1"
TOKEN = os.environ["GRAFANA_TOKEN"]
NRE = '.*-bn-[0-9]+'
END = int(time.time()); START = END - 30 * 86400; STEP = 900
G = f'group="lido_prod",instance=~"{NRE}"'

SIGNALS = {
    "recv_msgs": f'sum by (instance)(rate(gossipsub_rpc_recv_message_total{{{G}}}[5m]))',
    "recv_bytes": f'sum by (instance)(rate(gossipsub_rpc_recv_bytes_total{{{G}}}[5m]))',
    "net_gc":    f'sum by (instance)(rate(network_worker_nodejs_gc_duration_seconds_sum{{{G}}}[5m]))',
    "net_eloop": f'max by (instance)(network_worker_nodejs_eventloop_lag_p99_seconds{{{G}}})',
    "mesh":      f'sum by (instance)(lodestar_gossip_mesh_peers_by_type_count{{{G},type!~"beacon_attestation"}})',
    "churn":     f'sum by (instance)(rate(gossipsub_peer_churn_events_disconnected_total{{{G}}}[5m]) + rate(gossipsub_peer_churn_events_prune_total{{{G}}}[5m]))',
}


def q_range(expr):
    p = urllib.parse.urlencode({"query": expr, "start": START, "end": END, "step": STEP})
    req = urllib.request.Request(f"{BASE}/query_range?{p}", headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.load(r)
    assert d["status"] == "success", d
    out = {}
    for s in d["data"]["result"]:
        out[s["metric"]["instance"]] = {int(float(t)): float(v) for t, v in s["values"]
                                        if v not in ("NaN", "+Inf", "-Inf")}
    return out


def robust(vals):
    if not vals:
        return 0.0, 0.0
    med = st.median(vals)
    mad = st.median([abs(v - med) for v in vals]) or 0.0
    return med, 1.4826 * mad


def isot(ts):
    return time.strftime("%m-%d %H:%M", time.gmtime(ts))


print(f"window {isot(START)} -> {isot(END)} UTC step={STEP}s", file=sys.stderr)
data = {name: q_range(expr) for name, expr in SIGNALS.items()}
nodes = sorted(set(data["recv_msgs"]),
               key=lambda s: (("ovh" in s), int(s.split("-")[-1])))

rows = []
flood_by_hour = Counter()      # gossip flood incidence (fleet-wide?)
triple_by_hour = Counter()
for n in nodes:
    rm, rb = data["recv_msgs"].get(n, {}), data["recv_bytes"].get(n, {})
    gc, el = data["net_gc"].get(n, {}), data["net_eloop"].get(n, {})
    mp, ch = data["mesh"].get(n, {}), data["churn"].get(n, {})
    if not rm:
        continue
    med_rm, sig_rm = robust(list(rm.values()))
    med_gc, sig_gc = robust(list(gc.values()))
    med_el, sig_el = robust(list(el.values()))
    med_mp, sig_mp = robust(list(mp.values()))
    med_ch, sig_ch = robust(list(ch.values()))

    thr_rm = max(med_rm + 5 * sig_rm, med_rm * 1.8)
    thr_gc = max(med_gc + 5 * sig_gc, med_gc * 2)
    thr_el = max(med_el + 5 * sig_el, med_el * 2)
    thr_mp = med_mp - 4 * sig_mp
    thr_ch = max(med_ch + 5 * sig_ch, med_ch * 3) if med_ch else 0.5

    triples = []
    for t in sorted(rm):
        if rm[t] < thr_rm:
            continue
        flood_by_hour[t // 3600 * 3600] += 1
        win = [t - STEP, t, t + STEP]
        gc_hi = any(gc.get(w, 0) > thr_gc for w in win)
        el_hi = any(el.get(w, 0) > thr_el for w in win)
        mp_lo = sig_mp > 0 and any(w in mp and mp[w] < thr_mp for w in win)
        ch_hi = any(ch.get(w, 0) > thr_ch for w in win)
        if (gc_hi or el_hi) and (mp_lo or ch_hi):
            triples.append(t)
            triple_by_hour[t // 3600 * 3600] += 1
    rows.append(dict(
        node=n, med_rm=med_rm, peak_rm=max(rm.values()),
        med_gc=med_gc, peak_gc=max(gc.values()) if gc else 0,
        peak_el=max(el.values()) if el else 0,
        med_mp=med_mp, min_mp=min(mp.values()) if mp else 0,
        peak_ch=max(ch.values()) if ch else 0,
        n_triples=len(triples), triples=triples,
    ))

print("\n=== per-node (30d): gossip flood -> network GC -> mesh loss ===")
print(f"{'node':<26} {'recvMsg/s med->pk':>19} {'netGC s/s pk':>12} {'elP99 pk':>9} {'mesh med/min':>13} {'churn pk':>9} {'TRIPLE':>7}")
for r in sorted(rows, key=lambda x: (-x["n_triples"], -x["peak_gc"])):
    print(f"{r['node']:<26} {r['med_rm']:>8.0f}->{r['peak_rm']:>8.0f} "
          f"{r['peak_gc']:>12.2f} {r['peak_el']:>9.2f} "
          f"{r['med_mp']:>6.0f}/{r['min_mp']:>5.0f} {r['peak_ch']:>9.2f} {r['n_triples']:>7}")

hit = [r for r in rows if r["n_triples"] > 0]
grp = lambda n: "hetzner" if n.startswith("hetzner") else "ovh"
print(f"\n=== TRIPLE match (gossip flood ∧ netGC/eloop spike ∧ mesh dip/churn), same ±15m ===")
print(f"{len(hit)}/{len(rows)} bn nodes show >=1 co-timed triple  "
      f"(hetzner {sum(grp(r['node'])=='hetzner' for r in hit)}/{sum(grp(n)=='hetzner' for n in nodes)}, "
      f"ovh {sum(grp(r['node'])=='ovh' for r in hit)}/{sum(grp(n)=='ovh' for n in nodes)})")
for r in sorted(hit, key=lambda x: -x["n_triples"])[:15]:
    print(f"  {r['node']:<26} {r['n_triples']:>3} events  e.g. {', '.join(isot(t) for t in r['triples'][:6])}")

print("\n=== is the gossip flood fleet-wide? top hours by #nodes flooding simultaneously ===")
for hr, c in sorted(flood_by_hour.items(), key=lambda x: -x[1])[:10]:
    print(f"  {isot(hr)}  {c:>2} nodes flooding   ({triple_by_hour.get(hr,0)} of them w/ full triple)")

print("\n=== worst network-GC nodes (peak s/s) ===")
for r in sorted(rows, key=lambda x: -x["peak_gc"])[:8]:
    print(f"  {r['node']:<26} netGC {r['peak_gc']:.2f} s/s  elP99 {r['peak_el']:.2f}s  mesh {r['med_mp']:.0f}->{r['min_mp']:.0f}")
