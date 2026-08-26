#!/usr/bin/env python3
"""Decompose the Aug block-timing shift: arrival (recv) vs become-head vs actual compute (job_time).
avg = rate(_sum)/rate(_count) to match Grafana 'Avg' panels. Now [1d] vs late-July baseline [1d offset 30d]."""
import os, json, subprocess
G="https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1/query"
TOK=os.environ["GRAFANA_TOKEN"]
def q(p):
    out=subprocess.run(["curl","-s","-G",G,"-H",f"Authorization: Bearer {TOK}",
        "--data-urlencode",f"query={p}"],capture_output=True,text=True).stdout
    try: r=json.loads(out).get("data",{}).get("result",[])
    except: return None
    return float(r[0]["value"][1]) if r else None
def avg(metric, grp, win="1d", off=""):
    o=f" offset {off}" if off else ""
    s=q(f'sum(rate({metric}_sum{{group="{grp}"}}[{win}]{o}))')
    c=q(f'sum(rate({metric}_count{{group="{grp}"}}[{win}]{o}))')
    return (s/c) if (s and c) else None
for grp in ["lido_prod","prod_cip"]:
    print(f"\n=== {grp}: now [1d] vs baseline [1d @ -30d ~ late Jul] ===")
    for metric,label in [
        ("lodestar_gossip_block_elapsed_time_till_received","recv delay (arrival)"),
        ("lodestar_gossip_block_elapsed_time_till_processed","processed delay"),
        ("lodestar_gossip_block_elapsed_time_till_become_head","become-head delay"),
        ("lodestar_block_processor_queue_job_time_seconds","block compute (job_time)"),
        ("lodestar_import_payload_elapsed_time_till_imported_seconds","payload import"),
    ]:
        now=avg(metric,grp); base=avg(metric,grp,off="30d")
        if now is None or base is None:
            print(f"  {label:28s}: now={now} base={base}"); continue
        d=(now-base)*1000
        print(f"  {label:28s}: {base*1000:7.1f}ms -> {now*1000:7.1f}ms  ({'+' if d>=0 else ''}{d:.1f}ms)")
