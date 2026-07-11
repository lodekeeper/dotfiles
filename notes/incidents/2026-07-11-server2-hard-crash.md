# Incident: server2 hard crash — 2026-07-11

**Reported:** Nico, Lodestar WG topic "server2 crash investigation" (11893), 2026-07-11 10:31 UTC — "check why the server crashed today few hours ago."

**Host:** server2 (this OpenClaw host). Bare metal (`systemd-detect-virt` = none), 62 GiB RAM, 3.6 TB LVM root (78% used, 770 GB free).

## Timeline (UTC)
- **Jun 25 20:21:19** — previous boot started (boot id `d1b0bce4…`). Ran clean for ~16 days.
- **Jul 11 08:03:14** — last log line of previous boot. Normal per-minute `python3-leak-detector` run, then **dead stop**. No further entries.
- **Jul 11 ~08:03–08:04 → 10:27:56** — machine DOWN (~2h24m dark).
- **Jul 11 10:27:56** — kernel boots fresh (`uptime -s`).
- **Jul 11 10:28:15** — new boot (id `fbf2f139…`). OpenClaw gateway recovered healthy (pid 19214, probe ok, v2026.6.6).

## Evidence → conclusion
1. **Hard crash / power-or-hardware event, NOT a clean or software reboot.**
   - Previous-boot log ends abruptly mid-normal-operation. **Zero shutdown sequence** — no SIGTERM to gateway, no `systemd Stopping…`, no shutdown/reboot target. (All "Stopping openclaw-gateway" markers in the log are from earlier manual restarts on Jun 29/Jul 1/2/6/8/9, not Jul 11.)
   - `last` shows **no shutdown/crash record** for the previous boot.
   - No kernel-version change (6.8.0-134-generic both boots) → not an unattended-upgrade kernel reboot.
2. **Instantaneous kill, not a software death-spiral.** The final 3 minutes (08:00:30–08:04) contain **no error/warn/fatal burst** — steady normal cadence, then nothing. A software crash would leave an error trail; power loss / hard reset leaves a clean cutoff. This is a clean cutoff.
3. **Not resource exhaustion.** 62 GiB RAM (only ~1.5 GiB used by node; the "memory pressure" WARNs are app-level soft thresholds at 1.5 GiB, irrelevant at 62 GiB total). No kernel OOM-killer anywhere in the prior boot. Disk 78% (not full).
4. **One-off, not a crash loop.** Only 2 boots in journal; 16 days clean uptime before this single event.
5. **~2h24m downtime on bare metal** → came back only after a long dark period. Consistent with a **power outage** (returned when mains restored) or a fault that required a **manual/remote (IPMI) power-cycle**. A kernel panic with auto-reboot would return in seconds, not 2.5h.

**Most probable cause: external power loss or a hardware-level reset/fault.** Ruled out: OOM, disk-full, software/OS reboot, clean shutdown, crash loop.

## Blocked — needs Nico (root/BMC access)
`openclaw` user is in groups `openclaw users docker` — NOT `adm`/`systemd-journal`, so the **kernel/system journal and `/var/log/{kern,syslog}` are unreadable**, and there's no `ipmitool`. Final hardware trigger cannot be confirmed from this account. To pin it, run as root:
```bash
sudo journalctl -b -1 -k --no-pager | tail -50     # kernel tail of the boot that died (panic/MCE/thermal?)
sudo journalctl -b -1 -p err --no-pager | tail -50  # errors in the dead boot
sudo ipmitool sel list | tail -40                   # BMC System Event Log: power/thermal/PSU events
sudo dmesg -T | grep -iE 'mce|thermal|hardware error|edac'   # current-boot hardware complaints
# + check hosting/PDU/power provider for an outage window around 08:03–10:28 UTC
```
If `journalctl -b -1 -k` also shows a clean cutoff with no panic, that confirms power loss / hard reset over kernel panic.

## Recovery status
Gateway healthy post-reboot; no action needed on OpenClaw itself. Load was briefly high (~7) from boot-storm, expected to settle.

## Recovery status (verified ~10:43 UTC, ~15 min after reboot)

**Services:** All containers restarted. Nothing critical failed to come back. Still-down = expected only:
- review-royale-rr-{postgres,redis}-1 (Review Royale is PAUSED since 2026-05-28 — expected)
- kurtosis-engine-* (dev/test, not staking)
- vero-w3s-init-1 (init container, exit 0 = normal)

**Single root cause of validator impact — EL still catching up:**
- `mainnet-execution-1` (erigon) ~1,100 blocks / ~3-4h behind on Execution stage; has all headers/bodies, 26 peers, actively grinding. Will finish on its own.
- Therefore `mainnet-consensus-1` (Lodestar beacon) is at head (sync_distance 0) but **optimistic** (`is_optimistic:true`, `el_offline:false`) → returns 503 on `attestation_data`.

**Validator impact while optimistic:**
- Vero (main VC): ATTESTING fine — uses 2 remote synced beacons, threshold 2-of-3. ✅
- Obol/Charon DVT + Vouch/Dirk: NOT attesting — depend on the local optimistic beacon (503/408/"no responses"). Missing attestations until erigon validates. ❌ Self-heals when EL catches up.

**Non-crash, pre-existing warts (not urgent):**
- mainnet-tempo-1 restart-loop: tempo.yaml `compactor` field rejected by image version (config drift). Tracing only.
- Charon EL version-check points at non-existent `nethermind:8545` (cosmetic telemetry, unrelated to outage).

## RESOLVED (verified ~13:03 UTC, full recovery)

Crash recovery is complete:
- erigon EL: `eth_syncing:false` — fully synced.
- Lodestar beacon: `is_optimistic:false`, `sync_distance:0`, health 200 — at head, validated.
- Vero (main VC): attested continuously throughout (2-of-3 remote beacon fallback). ✅
- Charon/Obol DVT: recovered when beacon de-optimized — "Successfully submitted v2 attestations". ✅
- All containers up.

**Correction to earlier note — Vouch/Dirk (vouchdirk-3, "vouch2", val-1) was NOT a crash casualty:**
- Its Dirk slashing-rejections ("target epoch <= previous signed target epoch") started **07:10 UTC**, ~53 min BEFORE the 08:03 crash. Pre-existing, unrelated.
- Single account `val-1`; pubkey `0xb742...fcbe4` returns **404 "Validator pubkey not found in state"** on the mainnet beacon → NOT a registered mainnet validator. Test/lab key, nothing at stake.
- Benign standby/redundant-instance noise. No action taken (would not touch a distributed-signer stack regardless — slashing risk).

**Net:** crash was a one-off hard power/hardware reset; everything real recovered on its own. No missed mainnet attestations of consequence.
