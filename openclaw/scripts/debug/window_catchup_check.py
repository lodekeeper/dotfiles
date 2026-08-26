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
et='lodestar_epoch_transition_by_caller_total'
print("Contamination check for the 6h p999 window (lido_prod):")
print(f"  precomputeEpoch increase 6h      = {val(f'sum(increase({et}{{{grp},caller=\"precomputeEpoch\"}}[6h]))')}")
print(f"  processBlocksInEpoch increase 6h = {val(f'sum(increase({et}{{{grp},caller=\"processBlocksInEpoch\"}}[6h]))')}")
print(f"  nodes uptime<6h (restarts)       = {val(f'count((time()-process_start_time_seconds{{{grp}}})<21600)')}")
print(f"  nodes uptime<24h                 = {val(f'count((time()-process_start_time_seconds{{{grp}}})<86400)')}")
