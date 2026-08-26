#!/usr/bin/env python3
import os, json, subprocess
G="https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1/query"
TOK=os.environ["GRAFANA_TOKEN"]
def qr(p):
    out=subprocess.run(["curl","-s","-G",G,"-H",f"Authorization: Bearer {TOK}",
        "--data-urlencode",f"query={p}"],capture_output=True,text=True).stdout
    try: return json.loads(out).get("data",{}).get("result",[])
    except: return []
print("=== epoch_transition_by_caller: total INCREASE over 30d, fleet lido_prod ===")
r=qr('sum by (caller) (increase(lodestar_epoch_transition_by_caller_total{group="lido_prod"}[30d]))')
tot=sum(float(x["value"][1]) for x in r) or 1
for x in sorted(r,key=lambda x:-float(x["value"][1])):
    v=float(x["value"][1]); print(f"  {x['metric'].get('caller','?'):26s} {v:12.0f}  {v/tot*100:6.3f}%")
print(f"  processBlocksInEpoch as share of ALL epoch transitions above")
print("\n=== bn-9 processBlocksInEpoch increase per day (last 30d), spike dates ===")
r=qr('sum by () (increase(lodestar_epoch_transition_by_caller_total{instance="hetzner-lido-prod-bn-9",caller="processBlocksInEpoch"}[1d]))')
# fallback: query_range would be better; use a simple per-offset loop
for off in range(0,31):
    v=qr(f'sum(increase(lodestar_epoch_transition_by_caller_total{{instance="hetzner-lido-prod-bn-9",caller="processBlocksInEpoch"}}[1d] offset {off}d))')
    val=float(v[0]["value"][1]) if v else 0
    if val>0.5: print(f"  {off}d ago: {val:.0f} block-path epoch transitions")
