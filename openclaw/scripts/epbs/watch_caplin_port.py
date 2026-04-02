#!/usr/bin/env python3
import argparse
import json
import socket
import sys
import time

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Watch a TCP host:port and exit when it becomes reachable")
    ap.add_argument("--host", default="46.224.62.16")
    ap.add_argument("--port", type=int, default=4401)
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--timeout", type=float, default=5.0)
    args = ap.parse_args()

    print(json.dumps({"event": "start", "host": args.host, "port": args.port, "interval": args.interval, "timeout": args.timeout}), flush=True)
    while True:
        t0 = time.time()
        status = "closed"
        err = None
        try:
            with socket.create_connection((args.host, args.port), timeout=args.timeout):
                status = "open"
        except Exception as e:
            err = repr(e)
        evt = {
            "event": "probe",
            "ts": int(time.time()),
            "host": args.host,
            "port": args.port,
            "status": status,
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
        if err is not None:
            evt["error"] = err
        print(json.dumps(evt), flush=True)
        if status == "open":
            sys.exit(0)
        time.sleep(args.interval)
