#!/usr/bin/env python3
import os, json, subprocess
G="https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1/query"
TOK=os.environ["GRAFANA_TOKEN"]
def val(p):
    out=subprocess.run(["curl","-s","-G",G,"-H",f"Authorization: Bearer {TOK}",
        "--data-urlencode",f"query={p}"],capture_output=True,text=True).stdout
    try: r=json.loads(out).get("data",{}).get("result",[])
    except: return None
    return float(r[0]["value"][1]) if r else None
grp='group="lido_prod"'
print("main-thread event-loop lag, lido_prod, weekly (ms):  p99avg  maxavg   |  archive_blocks avg")
for off in [0,7,14,21,28,35,42,49,56]:
    o=f" offset {off}d" if off else ""
    p99=val(f'avg(avg_over_time(nodejs_eventloop_lag_p99_seconds{{{grp}}}[7d]{o}))')
    mx =val(f'avg(avg_over_time(nodejs_eventloop_lag_max_seconds{{{grp}}}[7d]{o}))')
    m='lodestar_process_finalized_checkpoint_seconds'
    s=val(f'sum(rate({m}_sum{{{grp},source="archive_blocks"}}[7d]{o}))'); c=val(f'sum(rate({m}_count{{{grp},source="archive_blocks"}}[7d]{o}))')
    ab=(s/c*1000) if (s and c) else None
    f=lambda x,sc=1000:f"{x*sc:7.1f}" if x is not None else "   n/a "
    print(f"  ~{off:2d}d ago: {f(p99)} {f(mx)}   |  {f(ab,1)}")
