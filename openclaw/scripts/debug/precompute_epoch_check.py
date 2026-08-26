#!/usr/bin/env python3
import os, json, subprocess
G="https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1/query"
TOK=os.environ["GRAFANA_TOKEN"]
def qr(p):
    out=subprocess.run(["curl","-s","-G",G,"-H",f"Authorization: Bearer {TOK}",
        "--data-urlencode",f"query={p}"],capture_output=True,text=True).stdout
    try: return json.loads(out).get("data",{}).get("result",[])
    except: return []
def val(p):
    r=qr(p); return float(r[0]["value"][1]) if r else None
grp='group="lido_prod"'
print("=== epoch_transition_by_caller (rate/h), lido_prod 6h ===")
r=qr(f'sum by (caller) (rate(lodestar_epoch_transition_by_caller_total{{{grp}}}[6h]))')
tot=sum(float(x["value"][1]) for x in r) or 1
for x in sorted(r,key=lambda x:-float(x["value"][1])):
    v=float(x["value"][1]); print(f"  {x['metric'].get('caller','?'):34s} {v*3600:7.2f}/h  {v/tot*100:5.1f}%")
print("\n=== precompute_next_epoch_transition, lido_prod 6h ===")
res=qr(f'sum by (result) (rate(lodestar_precompute_next_epoch_transition_result_total{{{grp}}}[6h]))')
for x in res: print(f"  result={x['metric'].get('result','?'):10s} {float(x['value'][1])*3600:6.2f}/h")
for m,lab in [("lodestar_precompute_next_epoch_transition_hits_total","hits (state reused by a block)"),
              ("lodestar_precompute_next_epoch_transition_waste_total","waste (precomputed, never used)")]:
    v=val(f'sum(rate({m}{{{grp}}}[6h]))'); print(f"  {lab:36s} {v*3600 if v is not None else 'n/a':}/h" if v is not None else f"  {lab}: n/a")
for ql in [0.5,0.9,0.99]:
    v=val(f'histogram_quantile({ql}, sum by (le) (rate(lodestar_precompute_next_epoch_transition_duration_seconds_bucket{{{grp}}}[6h])))')
    print(f"  precompute duration p{ql}: {v*1000:.1f}ms" if v is not None else f"  precompute duration p{ql}: n/a")
