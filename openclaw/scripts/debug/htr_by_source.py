#!/usr/bin/env python3
import os, json, subprocess
G="https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1/query"
TOK=os.environ["GRAFANA_TOKEN"]
def qr(p):
    out=subprocess.run(["curl","-s","-G",G,"-H",f"Authorization: Bearer {TOK}",
        "--data-urlencode",f"query={p}"],capture_output=True,text=True).stdout
    try: return json.loads(out).get("data",{}).get("result",[])
    except: return []
grp='group="lido_prod"'
m="lodestar_stfn_hash_tree_root_seconds"
print("hashTreeRoot time by source (lido_prod, 6h):   p50     p99    p999    rate/s")
srcs=qr(f'sum by (source) (rate({m}_count{{{grp}}}[6h]))')
for s in sorted(srcs,key=lambda x:-float(x["value"][1])):
    src=s["metric"].get("source","?"); rate=float(s["value"][1])
    row=[]
    for ql in [0.5,0.99,0.999]:
        r=qr(f'histogram_quantile({ql}, sum by (le) (rate({m}_bucket{{{grp},source="{src}"}}[6h])))')
        v=float(r[0]["value"][1]) if r else None
        row.append(f"{v*1000:7.1f}" if v is not None else "   n/a ")
    print(f"  {src:22s} {row[0]} {row[1]} {row[2]}   {rate:.2f}/s")
