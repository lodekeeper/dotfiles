# Loki log sweep: v1.50.0-rc.0 (beta) vs unstable vs stable, plus devnet ax41
Window: 2026-10-09 12:00 to 2026-10-12 09:08 UTC. Beta pre-upgrade = 12:00–21:53 (v1.49.0). Upgrade window = 21:53–22:05. Post = 22:05 onward (~59h).
Level = ANSI warn/error marker. Debug/verbose comparisons were aggregated server-side by message prefix.

**Verdict: I found no rc.0 regression at warn/error level.** Beta logged no warn/error lines that stable doesn't also log.

## Ranked findings
1. **MEDIUM, devnet only (Gloas): a retry storm fetching payload envelopes, running on all 4 ax41 nodes.**
   - Debug line `Error downloading payload in BlockInputSync.fetchPayloadInput ... attempt=N ... Missing execution payload envelope for root=…`.
   - Volume: 3.75M lines in the last 38h, about 50–100k per node per 3h.
   - It has been constant since at least 10-09 12:00 and survived the 10-10 restarts.
   - Per root: slot 431068 was retried from 08:53:44 to 09:07:12 (~13.5 min). That is 2.7k–3.9k failed requests per node for one root.
   - The attempt counter runs 1..20 and then starts over.
   - About 24 roots per hour are affected. These are blocks whose columns arrived but whose envelope never did (`hasPayload=false`).
   - The other side of the storm: `Cannot serve ExecutionPayloadEnvelopesByRoot: envelope not found` appeared 1.22M times in 38h. In a 2-min sample, 890 of 901 of those requests came from Lodestar peers, so the Lodestar nodes are hammering each other.
   - Consensus is unaffected: all 4 nodes are at the same head (slot 431142), finalized epoch 13471, with 89–97 peers.
2. **MEDIUM, cause unknown: unstable-super had one unplanned restart on b726a05 (which is newer than rc.0).**
   - The log stops mid-stream at 10-10 01:54:25.4 and the node restarts at 01:54:29.
   - There is no "Stopping gracefully" line and no uncaughtException, OOM or heap text.
   - Prometheus shows nothing unusual: node_exporter oom_kill counter is 0, RSS was flat at 11.8 GB, heap ~2.8 GB, event-loop lag normal.
   - The beacon container's stderr is not shipped to Loki, so a native crash would not show up there. Check the host with `docker inspect` / dmesg.
   - Resync took ~6 min, versus ~1 min for planned restarts.
   - Validator impact: 27 "produceAttestationData failed: Node is syncing", 3 SyncCommitteeMessage publish errors (ECONNREFUSED), 1 skipped slot.
   - This is the only unplanned restart in any group. Beta and stable had none.
3. **LOW, rc.0 behaviour change at debug level only: more dials to discovered peers.**
   - `Error dialing discovered peer`, beta/stable ratio: 0.90 before the upgrade, 6.13 after (per 9h: beta 1299 vs stable 212).
   - Dial attempts (`Dialing discovered peer`, per 9h): beta-super 60→649, beta-semi 108→389. Stable is flat.
   - Unstable shows the same elevated level, which points to a code change rather than deploy noise.
   - Related beta/stable ratios, pre→post: `invalid requestStatus` 1.03→1.93, `Req error` 1.11→1.33, `peer score adjusted` 1.04→1.32, goodbye received 1.28→1.86.
   - Peer counts are unaffected: about 200 on all Hoodi nodes, and the 24h averages are identical between beta and stable.
4. **LOW, probably noise: beta-sas has many ping failures.**
   - `invalid requestPing` with REQUEST_ERROR_REQUEST_ERROR ("Cannot write to a stream that is closed"), last 6h: beta-sas 7,730, stable-sas 78, unstable-sas 578.
   - But beta-sas already logged 2,495 per 3h before the upgrade, and stable-sas bursts to 1.6k per 3h. I can't attribute this to rc.0; worth watching.

## 1. Beacon warn/error per node (excluding unstable-solo)
- **Beta, before upgrade:** 0 lines on all 7 nodes.
- **Beta, upgrade window:** only restart artifacts.
  - mainnet-fcr 31 errors + 3 warns; mainnet-super 31 + 2; sas 10 + 3; semi 11 + 2; solo 10 + 2; super 10 + 2; arm64 0.
  - Errors: 103× `Error pushing notifyForkchoiceUpdate() … JSON RPC error: Too deep reorg, engine_forkchoiceUpdatedV3`.
  - Warns: 12× `Execution client request failed SYNCED→SYNCING`, 1 `Low peer count`, 1 `Reset fast confirmation`.
  - This is not new. stable v1.49.0 logged the same at its last restart (10-07: mainnet-fcr 36 lines, mainnet-super 40), and unstable logs it at every redeploy (241 errors).
- **Post window, 0 errors anywhere:**

| Node | beta warn | stable warn |
|---|---|---|
| arm64 | 4 | 4 |
| sas | 4 | 3 |
| semi | 3 | 3 |
| solo | 3 | 3 |
| super | 3 | 3 |
| mainnet-fcr / mainnet-super | 0 | 0 |

  - stable-super also logged 1 error: `publishBlindedBlockV2 … no payload from relays`.
- **Top post patterns are identical on beta, stable and unstable** (network-wide invalid blocks from peers):
  - 10× `Error processing block … BLOCK_ERROR_INVALID_STATE_ROOT` (10-10 06:07 and 23:32)
  - 5× `BLOCK_ERROR_INVALID_SIGNATURE` (10-11 12:05)
  - 1× `BLOCK_ERROR_BEACON_CHAIN_ERROR FORKCHOICE_ERROR_INVALID_BLOCK` on arm64 (10-10 07:09)
- **Only on beta:** 1 warn on beta-sas, 10-10 04:05: `Published data columns to 0 peers, increased risk of reorg … columns=2`. The block was published normally to 8–12 peers per column; this one is benign.
- **Unstable, whole window:** most lines are at restarts.
  - Too-deep-reorg: 241 errors and 24 warns.
  - `FORKCHOICE_ERROR_INVALID_ATTESTATION UNKNOWN_HEAD_BLOCK`: 21 at the 10-09 16:01 restart, 1 on semi 10-10 23:36.
  - Outside restarts: 3× `no payload from relays` errors (super 10-10 04:17, sas 10-11 05:06, sas 10-11 23:01).
- **Startup-only debug line, not new:** `Error emitting head/head_v2 event … No block for root` (8–10 lines per restart). It appears on beta, on unstable, and on stable's 10-07 restart.

## 2. Restarts and crashes
- **Beta:** one restart per node at the planned upgrade, 21:53:58–22:00:03, all graceful. Nothing since.
- **Stable:** no restarts in the window.
- **Unstable:** graceful redeploys at 10-09 16:00, 10-10 00:00 or 08:00, and 10-11 16:00, plus the unstable-super crash in finding 2.
- **Context correction: unstable is now on 9203d3d**, deployed 10-11 16:00. b726a05 only ran from 10-10 00:00/08:00 until 10-11 16:00.
- No uncaughtException, unhandledRejection, FATAL, heap/OOM or SIGTERM text on any beta, stable, unstable or devnet node. The one exception is the stale unstable-solo (v1.41.0, ignored): `uncaughtException: Cannot write to a stream that is closing` at 10-12 07:09.
- **Devnet:** all restarts graceful, at these times on 10-10:
  - ax41-3: 10:37
  - ax41-1: 14:16 and 18:25
  - ax41-2: 14:16
  - ax41-0: 14:36, 15:10 and 15:53
  - ax41-2's 14:16 restart never logged a "Lodestar network=" line, so start-line detection misses it. I found it from `libp2p worker started` and the head being 73 slots behind at startup.

## 3. Validator client (sas, semi, solo, super)
- **Before the upgrade:** beta and stable identical, 24 warns each (duty re-org at 10-09 12:10).
- **Beta upgrade window:** only restart lines.
  - 14× `Failed to check syncing status … ECONNREFUSED`
  - 11× `Node is syncing`
  - 7× `Error on attestation routine`
  - 4× `Failed to receive validator event`
  - 6× `Node is syncing - produceAttestationData/getProposerDuties failed`
- **Post window:** beta had **0 warn/error**. Stable had 1 error (stable-super, 10-10 19:27, `Error proposing block … publishBlindedBlockV2 … no payload from relays`).
- **Unstable:** restart lines plus the 01:54 crash fallout, and 3 blinded-block proposal failures with "no payload from relays" (relay side).

## 4. Devnet ax41 (glamsterdam-devnet-8)
- **Timing:** 394 warn/error lines, all between 10-10 10:35 and 18:26 (the restart window). There were 0 lines from 10-09 12:00 to 10-10 10:35, and 0 since 10-10 18:26 (~39h).
- **Breakdown of the 394:**
  - 290× `getBlockHeader failed reason=Block not found for id '<slot>'` on ax41-0 and ax41-3 (10-10 15:23–17:34). These are external REST queries for empty slots, not a node problem.
  - 49× attestations with UNKNOWN_HEAD/TARGET, only at restarts.
  - Too deep reorg: 10 errors + 6 warns each on ax41-1 (nethermind) and ax41-2 (geth), both at the 14:16 restart. Both EL types return it, so it is a restart artifact.
- **Engine API:** ~14k newPayload calls per node.
  - The only errors are `Execution engine error while processing payload`: 7 on ax41-0, 1 on ax41-1, 8 on ax41-3. All are on nethermind nodes, all during the 18:24–18:27 EL restart.
  - The geth node (ax41-2) had 0.
- **Sync:** nodes only showed "Syncing" at restarts.
- **Reorgs (72h, 4 nodes):** depth 2 ×738, depth 3 ×20, depth 4 ×8, depth 5 ×4. No Too-deep-reorg outside restarts.
- **Envelope gossip errors:** 893, all `ALREADY_KNOWN`.
- **Peer rejections:** Prysm invalid proposal signature ×2 (10-09 14:42, 10-11 07:26). Grandine ATTESTER_NOT_IN_COMMITTEE ×7 (10-12 01:02–01:06).
- **Known/expected, counted only — RESOURCE_UNAVAILABLE "Requested range is before earliestAvailableSlot":** 5,797 responses over 69h.
  - Per node: ax41-0 1,511, ax41-1 1,329, ax41-2 1,316, ax41-3 1,641.
  - By client: erigon 2,275, Prysm 2,258, Nimbus 1,154, Lighthouse 92, other 18.
  - Prysm and Nimbus hit this too, not only erigon/caplin.
