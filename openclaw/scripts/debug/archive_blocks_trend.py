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
m='lodestar_process_finalized_checkpoint_seconds'
def week(off):
    o=f" offset {off}d" if off else ""
    s=val(f'sum(rate({m}_sum{{{grp},source="archive_blocks"}}[7d]{o}))')
    c=val(f'sum(rate({m}_count{{{grp},source="archive_blocks"}}[7d]{o}))')
    p90=val(f'histogram_quantile(0.9, sum by (le) (rate({m}_bucket{{{grp},source="archive_blocks"}}[7d]{o})))')
    p99=val(f'histogram_quantile(0.99, sum by (le) (rate({m}_bucket{{{grp},source="archive_blocks"}}[7d]{o})))')
    avg=(s/c*1000) if (s and c) else None
    return avg, (p90*1000 if p90 else None), (p99*1000 if p99 else None), (c*3600 if c else 0)
print("archive_blocks time, lido_prod, weekly (ms):  avg    p90     p99    calls/h")
for off in [0,7,14,21,28,35,42,49,56,63,70,77,84]:
    a,p90,p99,ch=week(off)
    f=lambda x:f"{x:7.1f}" if x is not None else "   n/a "
    print(f"  ~{off:2d}d ago: {f(a)} {f(p90)} {f(p99)}   {ch:5.0f}")
print("\n=== current processFinalizedCheckpoint task breakdown (avg ms, 1d) ===")
for task in ["archive_blocks","maybe_archive_state","on_finalized_checkpoint","prune_history","forkchoice_prune","update_backfill_range"]:
    s=val(f'sum(rate({m}_sum{{{grp},source="{task}"}}[1d]))'); c=val(f'sum(rate({m}_count{{{grp},source="{task}"}}[1d]))')
    print(f"  {task:26s} {s/c*1000 if (s and c) else 0:7.1f} ms")
