#!/usr/bin/env python3
import os, json, subprocess
G="https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1/query"
TOK=os.environ["GRAFANA_TOKEN"]
def q(p):
    out=subprocess.run(["curl","-s","-G",G,"-H",f"Authorization: Bearer {TOK}",
        "--data-urlencode",f"query={p}"],capture_output=True,text=True).stdout
    try: r=json.loads(out).get("data",{}).get("result",[])
    except: return None
    return float(r[0]["value"][1]) if r else None
def hq(m,ql,win="6h"):
    return q(f'histogram_quantile({ql}, sum by (le) (rate({m}_bucket{{group="lido_prod"}}[{win}])))')
print("metric                                  p50     p90     p99    p999")
for m,lab in [("lodestar_gossip_block_state_transition_time","state_transition_time (PURE ST compute, incl epoch tx)"),
              ("lodestar_gossip_block_received_to_state_transition","received_to_AFTER_ST (pre-ST latency + compute)")]:
    row=[]
    for ql in [0.5,0.9,0.99,0.999]:
        v=hq(m,ql); row.append(f"{v*1000:7.1f}" if v is not None else "   n/a ")
    print(f"{lab:52s} {' '.join(row)} ms")
# implied pre-ST latency at each percentile (rough; independent-quantile subtraction)
print("\nimplied pre-ST latency (recvToAfterST - ST_compute) at matched percentile:")
for ql in [0.5,0.9,0.99,0.999]:
    a=hq("lodestar_gossip_block_received_to_state_transition",ql)
    b=hq("lodestar_gossip_block_state_transition_time",ql)
    if a is not None and b is not None:
        print(f"  p{ql}: {a*1000:7.1f} - {b*1000:7.1f} = {(a-b)*1000:7.1f} ms")
