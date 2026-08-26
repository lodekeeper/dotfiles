#!/usr/bin/env python3
"""Decompose Lodestar block-processing latency on lido_prod. state_transition_time p99 ~= epoch-boundary
transition cost (epoch tx happens ~1/32 blocks). received_to_state_transition = queue+availability wait."""
import os, json, subprocess
G="https://grafana-lodestar.chainsafe.io/api/datasources/proxy/1/api/v1/query"
TOK=os.environ["GRAFANA_TOKEN"]
def q(p):
    out=subprocess.run(["curl","-s","-G",G,"-H",f"Authorization: Bearer {TOK}",
        "--data-urlencode",f"query={p}"],capture_output=True,text=True).stdout
    try: r=json.loads(out).get("data",{}).get("result",[])
    except: return None
    return float(r[0]["value"][1]) if r else None
grp='group="lido_prod"'
def hq(metric, ql): return q(f'histogram_quantile({ql}, sum by (le) (rate({metric}_bucket{{{grp}}}[1h])))')
def avg(metric):
    s=q(f'sum(rate({metric}_sum{{{grp}}}[1h]))'); c=q(f'sum(rate({metric}_count{{{grp}}}[1h]))')
    return (s/c) if (s and c) else None
print("=== Lodestar block-path decomposition, lido_prod (last 1h), ms ===")
for m,label in [("lodestar_gossip_block_state_transition_time","state-transition compute"),
                ("lodestar_gossip_block_received_to_state_transition","received->ST (queue+avail wait)"),
                ("lodestar_gossip_block_elapsed_time_till_received","till_received (arrival)"),
                ("lodestar_gossip_block_elapsed_time_till_processed","till_processed")]:
    a=avg(m); p50=hq(m,0.5); p90=hq(m,0.9); p99=hq(m,0.99)
    fmt=lambda x: f"{x*1000:7.1f}" if x is not None else "   n/a "
    print(f"  {label:32s} avg={fmt(a)} p50={fmt(p50)} p90={fmt(p90)} p99={fmt(p99)}  (p99~boundary)")
# late-head exposure
sh=q(f'sum(rate(lodestar_import_block_set_head_after_cutoff_total{{{grp}}}[1h]))')
ib=q(f'sum(rate(lodestar_import_block_by_source_total{{{grp}}}[1h]))')
print(f"\n  set_head_after_cutoff rate = {sh}/s ; import_block rate = {ib}/s ; frac = {sh/ib*100 if (sh and ib) else 'n/a'}%")
# epoch transition caller counts (sanity: epoch tx on the block path)
et=q(f'sum(rate(lodestar_epoch_transition_by_caller_total{{{grp}}}[1h]))')
print(f"  epoch_transition_by_caller total rate = {et}/s")
