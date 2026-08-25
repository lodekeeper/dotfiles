#!/usr/bin/env python3
import os, json, subprocess

G = "https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1/query"
TOK = os.environ["GRAFANA_TOKEN"]

def q(promql):
    out = subprocess.run(["curl","-s","-G",G,"-H",f"Authorization: Bearer {TOK}",
        "--data-urlencode",f"query={promql}"], capture_output=True, text=True).stdout
    try:
        d = json.loads(out)
    except Exception:
        return None
    r = d.get("data",{}).get("result",[])
    return r

def ssum(promql):
    r = q(promql)
    if not r: return None
    try: return float(r[0]["value"][1])
    except Exception: return None

grp='group="lido_prod"'
print("=== lido_prod raw increase over last 1d (sample-based counts) ===")
vals={}
for m in ["source_attester","target_attester","head_attester","attester"]:
    for k in ["hit","miss"]:
        v = ssum(f'sum(increase(validator_monitor_prev_epoch_on_chain_{m}_{k}_total{{{grp}}}[1d]))')
        vals[(m,k)]=v
        print(f"  {m:16s} {k:4s}: {v}")

print("\n=== miss fractions ===")
for m,label in [("source_attester","source (timely <=5 slot)"),
                ("target_attester","target (<=32 slot)"),
                ("head_attester","head (==1 slot)"),
                ("attester","overall (included at all)")]:
    h,mi = vals[(m,"hit")], vals[(m,"miss")]
    if h is None or mi is None or (h+mi)==0:
        print(f"  {label:28s}: n/a (hit={h} miss={mi})")
    else:
        print(f"  {label:28s}: {mi/(h+mi)*100:6.3f}% miss  (miss={mi:.0f})")

print("\n=== per-node source-miss fraction, last 1d (top 8) ===")
r = q('topk(8, '
      'sum by (instance) (increase(validator_monitor_prev_epoch_on_chain_source_attester_miss_total{group="lido_prod"}[1d])) '
      '/ (sum by (instance) (increase(validator_monitor_prev_epoch_on_chain_source_attester_hit_total{group="lido_prod"}[1d])) '
      '+ sum by (instance) (increase(validator_monitor_prev_epoch_on_chain_source_attester_miss_total{group="lido_prod"}[1d]))))')
for row in (r or []):
    inst = row["metric"].get("instance","?")
    print(f"  {inst:34s}: {float(row['value'][1])*100:6.3f}%")

print("\n=== per-node OVERALL attester-miss (never-included), last 1d (top 5) ===")
r = q('topk(5, sum by (instance) (increase(validator_monitor_prev_epoch_on_chain_attester_miss_total{group="lido_prod"}[1d])))')
for row in (r or []):
    print(f"  {row['metric'].get('instance','?'):34s}: {float(row['value'][1]):.1f} sample-misses")
if not r: print("  (no non-inclusion on any node)")

print("\n=== source-miss fraction trend: last 1d vs prior 6d ===")
def fleetfrac(win, off=""):
    o = f" offset {off}" if off else ""
    mi = ssum(f'sum(increase(validator_monitor_prev_epoch_on_chain_source_attester_miss_total{{group="lido_prod"}}[{win}]{o}))')
    hi = ssum(f'sum(increase(validator_monitor_prev_epoch_on_chain_source_attester_hit_total{{group="lido_prod"}}[{win}]{o}))')
    return (mi/(hi+mi)*100) if (mi is not None and hi is not None and hi+mi>0) else None
print(f"  last 1d      : {fleetfrac('1d')}")
print(f"  prior 6d(1-7): {fleetfrac('6d','1d')}")
