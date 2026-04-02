#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional, Tuple

DEFAULT_REST = "http://127.0.0.1:10069"
DEFAULT_LOG = "/home/openclaw/lodestar-9148-min/runs/pr9156-direct-caplin1/beacon-2026-04-02.log"
DEFAULT_HOST = "/ip4/46.224.62.16/tcp/4401"
DEFAULT_SEED_PEER = "16Uiu2HAmRCP28eEphgbDmrS7ihqAmtBjCwLUhh8aAV2fCc5Mu85x"


def http_json(url: str, method: str = "GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def connect_peer(rest: str, seed_peer: str, host_multiaddr: str) -> tuple[bool, Optional[str]]:
    query = urllib.parse.urlencode({"peerId": seed_peer, "multiaddr": host_multiaddr})
    try:
        http_json(f"{rest}/eth/v1/lodestar/connect_peer?{query}", method="POST")
        return True, None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "route_not_found"
        return False, f"http_{e.code}"


def get_sync(rest: str) -> dict:
    return http_json(f"{rest}/eth/v1/node/syncing")["data"]


def get_peers(rest: str) -> list[dict]:
    return http_json(f"{rest}/eth/v1/node/peers")["data"]


def find_caplin_peer(peers: list[dict], host_multiaddr: str) -> Optional[dict]:
    for peer in peers:
        seen = peer.get("last_seen_p2p_address") or ""
        if host_multiaddr in seen:
            return peer
    return None


def read_new_log_lines(path: str, offset: int) -> Tuple[list[str], int]:
    if not os.path.exists(path):
        return [], offset
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(offset)
        lines = f.readlines()
        return lines, f.tell()


def interesting(line: str) -> bool:
    needles = (
        "Peer sync classification",
        "UNDER_SSZ_MIN_SIZE",
        "beacon_blocks_by_range invalid_request details",
        "peer connected",
        "peer disconnected",
    )
    return any(n in line for n in needles)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Watch the epbs-devnet-1 Caplin host and auto-redial if needed")
    ap.add_argument("--rest", default=DEFAULT_REST)
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--host-multiaddr", default=DEFAULT_HOST)
    ap.add_argument("--seed-peer", default=DEFAULT_SEED_PEER)
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--redial-after-misses", type=int, default=2)
    ap.add_argument("--max-loops", type=int, default=0, help="0 = run forever")
    args = ap.parse_args()

    log_offset = os.path.getsize(args.log) if os.path.exists(args.log) else 0
    misses = 0
    last_peer_id = None
    last_sync_tuple = None
    loops = 0
    redial_enabled = True
    redial_failure = None

    print(json.dumps({
        "event": "start",
        "rest": args.rest,
        "log": args.log,
        "host_multiaddr": args.host_multiaddr,
        "seed_peer": args.seed_peer,
        "log_offset": log_offset,
    }), flush=True)

    while True:
        loops += 1
        try:
            sync = get_sync(args.rest)
            peers = get_peers(args.rest)
            caplin = find_caplin_peer(peers, args.host_multiaddr)

            sync_tuple = (
                sync.get("head_slot"),
                sync.get("sync_distance"),
                sync.get("is_syncing"),
                sync.get("is_optimistic"),
            )
            if sync_tuple != last_sync_tuple:
                print(json.dumps({"event": "sync", **sync}), flush=True)
                last_sync_tuple = sync_tuple

            if caplin is None:
                misses += 1
                print(json.dumps({"event": "peer_missing", "misses": misses}), flush=True)
                if misses >= args.redial_after_misses and redial_enabled:
                    ok, reason = connect_peer(args.rest, args.seed_peer, args.host_multiaddr)
                    if ok:
                        print(json.dumps({"event": "redial", "seed_peer": args.seed_peer, "host_multiaddr": args.host_multiaddr}), flush=True)
                        misses = 0
                    else:
                        redial_enabled = False
                        redial_failure = reason
                        print(json.dumps({
                            "event": "redial_disabled",
                            "reason": reason,
                            "seed_peer": args.seed_peer,
                            "host_multiaddr": args.host_multiaddr,
                        }), flush=True)
            else:
                misses = 0
                peer_id = caplin.get("peer_id")
                peer_state = caplin.get("state")
                direction = caplin.get("direction")
                peer_tuple = (peer_id, peer_state, direction)
                if peer_tuple != last_peer_id:
                    print(json.dumps({
                        "event": "peer",
                        "peer_id": peer_id,
                        "state": peer_state,
                        "direction": direction,
                        "last_seen_p2p_address": caplin.get("last_seen_p2p_address"),
                    }), flush=True)
                    last_peer_id = peer_tuple

            lines, log_offset = read_new_log_lines(args.log, log_offset)
            for line in lines:
                if interesting(line):
                    print(json.dumps({"event": "log", "line": line.rstrip("\n")}), flush=True)
                    if "syncType=Advanced" in line or "UNDER_SSZ_MIN_SIZE" in line:
                        print(json.dumps({"event": "target_hit", "reason": "advanced_or_invalid_request"}), flush=True)
                        sys.exit(0)

        except Exception as e:
            print(json.dumps({"event": "error", "error": repr(e)}), flush=True)

        if args.max_loops and loops >= args.max_loops:
            print(json.dumps({"event": "done", "loops": loops}), flush=True)
            break
        time.sleep(args.interval)
