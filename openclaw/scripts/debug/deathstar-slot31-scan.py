#!/usr/bin/env python3
"""Scan all deathstar (validators 300-399) epoch-boundary (slot%32==31) proposals on
glamsterdam-devnet-7 via Dora, classify Canonical(reorg FAILED)/Orphaned(reorg OK)/Missed.
Ask: Nico 2026-07-29 — are any deathstar slot-31 blocks canonical (proposer-boost reorg failed)?"""
import urllib.request, json, concurrent.futures, collections, time

NET = "glamsterdam-devnet-7"
BASE = f"https://dora.{NET}.ethpandaops.io/api/v1/slots"

def fetch(idx, tries=5):
    url = f"{BASE}?proposer={idx}&limit=1000"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (lodekeeper-devnet-analysis)"})
    for a in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            return idx, d.get("data", {}).get("slots", [])
        except Exception:
            time.sleep(1.0 + a * 1.5)
    return idx, None

byslot, errs, names = {}, [], set()
def absorb(idx, slots):
    for s in slots:
        byslot[s["slot"]] = s
        names.add(s.get("proposer_name"))

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
    for idx, slots in ex.map(fetch, range(300, 400)):
        if slots is None:
            errs.append(idx)
        else:
            absorb(idx, slots)

# sequential retry pass for stragglers
for idx in list(errs):
    _, slots = fetch(idx, tries=6)
    if slots is not None:
        errs.remove(idx); absorb(idx, slots)
    time.sleep(0.3)

b31 = sorted((s for s in byslot.values() if s["slot"] % 32 == 31), key=lambda s: s["slot"])
tally = collections.Counter(s["status"] for s in b31)

print(f"proposer_names seen for 300-399: {sorted(n for n in names if n)}")
print(f"errors (idx with no response): {errs}")
print(f"total deathstar proposals fetched (all slots): {len(byslot)}")
print(f"deathstar SLOT-31 (epoch-boundary) proposals: {len(b31)} | tally: {dict(tally)}")
print(f"sanity: known orphaned slot 109311 present? {109311 in byslot} status={byslot.get(109311,{}).get('status')}")
print()
canon = [s for s in b31 if s["status"] == "Canonical"]
print(f"=== CANONICAL deathstar slot-31 blocks (reorg FAILED) : {len(canon)} ===")
for s in canon:
    print(f"  slot {s['slot']} epoch {s['slot']//32} proposer {s['proposer']} name {s.get('proposer_name')} status {s['status']}")
if not canon:
    print("  (none — every deathstar slot-31 block was orphaned/missed)")
print()
print("=== full deathstar slot-31 list (slot / epoch / proposer / status) ===")
for s in b31:
    print(f"  {s['slot']} e{s['slot']//32} p{s['proposer']} {s['status']}")

# ---- Phase 2: for each deathstar slot-31, check the honest next slot (epoch slot-0) ----
def fetch_slot(n):
    url = f"https://dora.{NET}.ethpandaops.io/api/v1/slot/{n}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (lodekeeper-devnet-analysis)"})
    for a in range(6):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return n, json.load(r).get("data", {})
        except Exception:
            time.sleep(1.0 + a * 1.2)
    return n, None

nxt = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    for n, info in ex.map(fetch_slot, [s["slot"] + 1 for s in b31]):
        nxt[n] = info

print("\n=== classification (deathstar s31 status  x  honest next-slot s0 status) ===")
cls = collections.Counter()
fails = []
for s in b31:
    n = s["slot"] + 1
    ni = nxt.get(n) or {}
    s0 = ni.get("status")
    cls[(s["status"], s0)] += 1
    if s["status"] == "Canonical" and s0 in ("Orphaned", "Missed", "Missing"):
        fails.append((s["slot"], s["slot"] // 32, s["proposer"], n, ni.get("proposer"), ni.get("proposer_name"), s0))
for k, v in sorted(cls.items(), key=lambda x: (-x[1])):
    print(f"  s31={str(k[0]):10} nextS0={str(k[1]):10} : {v}")
print(f"\n=== REORG FAILED? (deathstar s31 Canonical AND honest s0 NOT canonical): {len(fails)} ===")
for slot31, ep, p31, s0slot, s0p, s0name, s0st in sorted(fails):
    print(f"  epoch {ep}: deathstar s31={slot31} (p{p31}) Canonical -> honest s0={s0slot} (p{s0p} {s0name}) {s0st}")
if not fails:
    print("  (none — no canonical deathstar slot-31 block orphaned an honest slot-0)")
