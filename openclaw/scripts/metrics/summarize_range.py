#!/usr/bin/env python3
"""Summarize a Prometheus query_range JSON payload (stdin).

For each series prints: group/host_type/network, start, end, min, max, mean,
and least-squares slope per day. Values divided by SCALE (default 1e9 -> GB).

Usage: curl ... | summarize_range.py [--scale 1e9] [--label group,host_type,network]
"""
import sys
import json
import argparse


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1e9)
    ap.add_argument("--label", default="group,host_type,network")
    ap.add_argument("--unit", default="")
    args = ap.parse_args()
    labels = args.label.split(",")

    d = json.load(sys.stdin)
    res = d.get("data", {}).get("result", [])
    hdr = "/".join(labels)
    print(f"{hdr:32} {'start':>8} {'end':>8} {'min':>8} {'max':>8} {'mean':>8} {'slope/d':>9}")
    rows = []
    for m in res:
        met = m["metric"]
        key = "/".join(met.get(l, "?") for l in labels)
        vals = [(float(t), float(v)) for t, v in m.get("values", []) if v not in ("NaN",)]
        if not vals:
            continue
        ys = [v / args.scale for _, v in vals]
        t0 = vals[0][0]
        xs = [(t - t0) / 86400 for t, _ in vals]
        n = len(xs)
        sx, sy = sum(xs), sum(ys)
        sxx = sum(x * x for x in xs)
        sxy = sum(x * y for x, y in zip(xs, ys))
        denom = n * sxx - sx * sx
        slope = (n * sxy - sx * sy) / denom if denom else 0.0
        sort_key = (met.get(labels[-1] if len(labels) > 1 else labels[0], ""),
                    met.get("host_type", ""), met.get("group", ""))
        rows.append((sort_key, key, ys[0], ys[-1], min(ys), max(ys), sy / n, slope))
    for _, key, s, e, mn, mx, mean, slope in sorted(rows, key=lambda r: r[0]):
        print(f"{key:32} {s:8.2f} {e:8.2f} {mn:8.2f} {mx:8.2f} {mean:8.2f} {slope:+9.3f}")


if __name__ == "__main__":
    main()
