#!/usr/bin/env python3
"""
Quantify how much the bn-21 -> rescue-2 drain dragged Lido aggregate attestation
performance during the 1.45 window, vs the network-wide shift.
Read-only, grafana-lodestar Prom DS1.
"""
import json, os, time, urllib.parse, urllib.request
BASE = "https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1"
TOK = os.environ["GRAFANA_TOKEN"]
def E(iso): return int(time.mktime(time.strptime(iso, "%Y-%m-%dT%H:%M:%S")) - time.timezone)
def isod(ts): return time.strftime("%m-%d", time.gmtime(ts))

def qinst(expr, ts):
    p = urllib.parse.urlencode({"query": expr, "time": ts})
    r = urllib.request.Request(f"{BASE}/query?{p}", headers={"Authorization": f"Bearer {TOK}"})
    d = json.load(urllib.request.urlopen(r, timeout=90))
    return {x["metric"].get("instance", "?"): float(x["value"][1]) for x in d["data"]["result"]}

def qrange(expr, S, Eend, step=86400):
    p = urllib.parse.urlencode({"query": expr, "start": S, "end": Eend, "step": step})
    r = urllib.request.Request(f"{BASE}/query_range?{p}", headers={"Authorization": f"Bearer {TOK}"})
    d = json.load(urllib.request.urlopen(r, timeout=90))
    out = {}
    for s in d["data"]["result"]:
        out[s["metric"].get("instance", "?")] = [(int(float(t)), float(v)) for t, v in s["values"]]
    return out

G = 'group="lido_prod"'
WIN_END = E("2026-08-17T18:00:00")   # 1.45 -> 1.46 deploy ~19:00
WIN = "18d5h"                         # ~Jul 30 13:00 -> Aug 17 18:00 (inside 1.45 window)

# ---- 1. validator-count migration bn-21 -> rescue-2 ----
print("=== validator_monitor_validators (capped@200) time series — migration shape ===")
vc = qrange(f'validator_monitor_validators{{{G}}}', E("2026-07-25T00:00:00"), E("2026-08-20T00:00:00"))
watch = ["ovh-lido-prod-bn-21", "hetzner-lido-prod-bn-rescue-2", "hetzner-lido-prod-bn-rescue-1",
         "hetzner-lido-prod-bn-rescue-3", "hetzner-lido-prod-bn-rescue-0", "ovh-lido-prod-bn-rescue-0",
         "hetzner-lido-prod-bn-5"]
days = sorted({t for s in vc.values() for t, _ in s})
print("date    " + " ".join(f"{w.split('-')[-1]:>6}" if 'rescue' not in w else f"r{w.split('-')[-1]:>5}" for w in watch))
for d in days[::2]:
    row = []
    for w in watch:
        v = dict(vc.get(w, [])).get(d)
        row.append(f"{v:>6.0f}" if v is not None else f"{'--':>6}")
    print(f"{isod(d)}  " + " ".join(row))

# ---- 2. per-node window rates via increase() ----
def rate_pair(hit_m, miss_m):
    h = qinst(f'increase({hit_m}{{{G}}}[{WIN}])', WIN_END)
    m = qinst(f'increase({miss_m}{{{G}}}[{WIN}])', WIN_END)
    return h, m
hh, hm = rate_pair("validator_monitor_prev_epoch_on_chain_head_attester_hit_total",
                   "validator_monitor_prev_epoch_on_chain_head_attester_miss_total")
th, tm = rate_pair("validator_monitor_prev_epoch_on_chain_target_attester_hit_total",
                   "validator_monitor_prev_epoch_on_chain_target_attester_miss_total")
idist_s = qinst(f'increase(validator_monitor_prev_epoch_on_chain_inclusion_distance_sum{{{G}}}[{WIN}])', WIN_END)
idist_c = qinst(f'increase(validator_monitor_prev_epoch_on_chain_inclusion_distance_count{{{G}}}[{WIN}])', WIN_END)

nodes = sorted(k for k in hh if "-bn-" in k)
def rate(h, m, k):
    a, b = h.get(k, 0), m.get(k, 0)
    return (a / (a + b) * 100) if (a + b) > 0 else None, (a + b)
def fmt(v, nd): return "  n/a" if v is None else f"{round(v,nd)}"

print("\n=== per-node 1.45-window rates (validator_monitor sample) ===")
print(f"{'node':<30} {'head%':>7} {'target%':>8} {'inclDist':>8} {'sampleDuties':>12}")
rows = {}
for k in nodes:
    hr, w = rate(hh, hm, k)
    tr, _ = rate(th, tm, k)
    idd = (idist_s.get(k, 0) / idist_c.get(k, 1)) if idist_c.get(k, 0) else None
    rows[k] = dict(head=hr, tgt=tr, incl=idd, duties=w)
for k in sorted(nodes, key=lambda x: (rows[x]["head"] if rows[x]["head"] is not None else 999)):
    r = rows[k]
    tag = "  <-- rescue" if "rescue" in k else ("  <-- bn-21(drained)" if k.endswith("bn-21") else "")
    print(f"{k:<30} {fmt(r['head'],2):>7} {fmt(r['tgt'],2):>8} {fmt(r['incl'],3):>8} {r['duties']:>12.0f}{tag}")

# ---- 3. decomposition ----
ACTIVE = 5000   # sampleDuties threshold: a node actually carrying load in-window
prim = [k for k in nodes if "rescue" not in k and not k.endswith("bn-21")
        and rows[k]["head"] is not None and rows[k]["duties"] > ACTIVE]
prim_heads = sorted(rows[k]["head"] for k in prim)
med = prim_heads[len(prim_heads)//2]
mean_prim = sum(rows[k]["head"] for k in prim) / len(prim)
r2 = rows["hetzner-lido-prod-bn-rescue-2"]
print("\n=== decomposition (head-vote) ===")
print(f"online primaries (excl bn-21): n={len(prim)}, head median={med:.2f}%, mean={mean_prim:.2f}%")
print(f"rescue-2 head={r2['head']:.2f}%, delta vs primary median = {(r2['head']-med):+.2f}pp")
act_res = [k for k in nodes if "rescue" in k and rows[k]["duties"] > 500]
print("active rescue nodes (sampleDuties>500):",
      [(k.split('-')[-1], round(rows[k]['head'],1), int(rows[k]['duties'])) for k in act_res])

# duty-weighted sample aggregate over all in-window-active lido bn (primaries + active rescues)
active = [k for k in nodes if rows[k]["head"] is not None and rows[k]["duties"] > ACTIVE]
def agg(node_rate):
    num = sum(node_rate(k) / 100 * rows[k]["duties"] for k in active)
    den = sum(rows[k]["duties"] for k in active)
    return num / den * 100
actual = agg(lambda k: rows[k]["head"])
# counterfactual: rescue-2's validators had stayed on bn-21 (=> attest at primary median)
cf = agg(lambda k: med if k == "hetzner-lido-prod-bn-rescue-2" else rows[k]["head"])
print(f"\nduty-weighted aggregate head-vote (in-window): actual={actual:.3f}%  "
      f"counterfactual(rescue-2 at median)={cf:.3f}%  => drain drag = {(cf-actual):+.3f}pp")

# ---- 4. July baseline to size the TOTAL shortfall (network-wide shift) ----
BASE_END = E("2026-07-27T00:00:00")
bhh = qinst(f'increase(validator_monitor_prev_epoch_on_chain_head_attester_hit_total{{{G}}}[20d])', BASE_END)
bhm = qinst(f'increase(validator_monitor_prev_epoch_on_chain_head_attester_miss_total{{{G}}}[20d])', BASE_END)
bprim = [k for k in bhh if "-bn-" in k and "rescue" not in k]
bnum = sum(bhh.get(k, 0) for k in bprim); bden = sum(bhh.get(k, 0) + bhm.get(k, 0) for k in bprim)
base = bnum / bden * 100 if bden else None
print(f"\nJuly baseline (pre-1.45, primaries) head-vote = {base:.3f}%")
print(f"network-wide shift (baseline -> in-window primary mean) = {(mean_prim-base):+.3f}pp  (hits ALL validators)")
tot_short = base - actual
drain_share = (cf - actual) / tot_short * 100 if tot_short else 0
print(f"\n=== ANSWER ===")
print(f"total Lido head-vote shortfall (July -> 1.45 window) = {tot_short:.3f}pp")
print(f"  from network-wide head-timing shift : {(base-cf):.3f}pp  ({(base-cf)/tot_short*100:.0f}%)")
print(f"  from bn-21 -> rescue-2 drain        : {(cf-actual):.3f}pp  ({drain_share:.0f}%)")
