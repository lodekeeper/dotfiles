# v1.50.0-rc.0 metrics sweep (Prometheus), 2026-10-12 ~09:15 UTC

**Verdict: no rc.0 regression in health, block processing, validator or engine metrics.** I found one small regression that the code explains (getBlobsV2 decode, P2) and one memory item to watch (mainnet-fcr RSS). Every other difference is either a restart decay or a network-wide event that stable shows too.

Windows used:
- beta-pre: 10-09 12:00–21:50.
- beta-post and stable: 10-10 00:00 → 10-12 09:00 (57h).
- unstable: 10-10 10:00 → 10-11 15:50, on **b726a05**. b726a05 is the same code as rc.0 (`78b217e` only adds a version bump on top). Unstable has run 9203d3d since 10-11 16:00 restart, so the brief's "currently b726a05" is stale.
- beta-pre is on b1dee24, which has the same tree as stable 0e1dc85. So beta-pre vs stable shows the effect of the host, not of the code.

Cells are `beta-pre / beta-post / unstable / stable`. There is no unstable-solo (stale v1.41.0).

## Ranked findings
1. **P2: `getBlobsV2` now spends about +8–17ms per call inside the beacon node (code-confirmed).**
   - `beacon_engine_getBlobsV2_request_duration` mean (ms):
     - super 31/39/44/33
     - semi 28/39/40/28
     - solo 35/52/–/37
     - mainnet-fcr 9.5/21/20/11
     - mainnet-super 10/19/18/12
   - The EL HTTP time (`http_client_request_time{routeId=getBlobsV2}`) did not change or went down: super 27/23/24/29, mainnet-fcr 7.9/8.5/8.3/9.2.
   - The extra time (call duration minus HTTP time) steps up on unstable from 3–4ms to 16–23ms at 09-29 12:00. That is the first build after #10203, which was merged 09-28 20:04.
   - Cause: #10203 now passes the preallocated buffers to `getBlobsV2`, so responses are decoded through `deserializeBlobAndProofsV2IntoBytes`. That uses `dataIntoBytes`, which calls `fromHexInto`, a synchronous JS loop over the hex string. Before, the decode used native `fromHex` / `Buffer.from(hex)`. `utils/bytes/nodejs.ts` itself notes that "fromHexInto using a preallocated buffer is very bad".
   - Impact: about 10–20ms of main-thread work per block with blobs. It does not show up in block→head times or event-loop lag.
   - Fix idea: decode natively into the preallocated memory, e.g. `Buffer.from(buf.buffer, off, len).write(hex.slice(2), "hex")`.
2. **P3 watch: mainnet-fcr memory (RSS).**
   - At 10-12 09:00, beta-mainnet-fcr RSS is 10.19 GB vs stable 9.77 GB (+4%).
   - 57h growth rate (deriv): beta +427 MB/day, stable +274 MB/day, unstable +535 MB/day.
   - Heap used is flat (-7 MB/day), so the growth is outside the V8 heap.
   - At equal uptime, the rc-code runs (beta rc.0, unstable b726a05 and 9203d3d) sit +0.7–1.3 GB above the v1.49 runs at 2–24h. This is confounded: every mainnet node restarted 10-07 14:04 and stable itself grew from 7.6 to 9.8 GB since then. unstable-mainnet-fcr also crept up across builds from 10-08 on (7.3 → 8.1 → 8.4 GB at 2h).
   - Not seen on mainnet-super or Hoodi, where rc.0 RSS at equal uptime is at or below the previous beta run (arm64 settles at 8 GB vs 14 GB before).
   - Within ±20%. A heap/smaps check is needed if it keeps growing.
3. **P3, devnet only, unclear: unknown-payload sync.**
   - `lodestar_sync_unknown_payload_download_result{resolved}` fell from about 1.1–1.3k/h to 365–420/h on the nethermind nodes, and to 859/h on ax41-2 (geth). Each node dropped right at its own restart; ax41-2 dropped later, at 10T20.
   - `failed` went from 820–970/h to 1.0–1.4k/h (last 6h: 1.1–1.6k/h). Deferred `imported_before_search` went up.
   - Outgoing `RESOURCE_UNAVAILABLE` (our requests being refused) went from 3/h to 41–46/h in the last 6h on ax41-1, 2 and 3. `SELF_RATE_LIMITED` went from 6/h to 25–29/h on the nethermind nodes only (ax41-2: 6/h).
   - Outgoing `execution_payload_envelopes_by_root` runs at 100–240 requests per slot per node. That predates this restart (it was already there on 10-07) but is very high.
   - The nethermind master upgrade happened at the same time, so I can't attribute this to the build. A log look is the next step.
4. **Restart decay, not a regression.**
   - Hoodi outgoing `status` error % went from 1.2–1.9 to 3.2–3.9 over the post window (stable 0.9–1.6). In 6h buckets it starts at 4.5–7.7% and is back to 0.9–3.4% by 10-12.
   - The previous beta restart (09-25) decayed the same way, 7.4% → 2.0%. Metadata errors, goodbye-received "too many peers" (329 → 95/h; previous restart 554 → 107/h) and `DIAL_ERROR` (1175 → 823/h, pre 670) follow the same curve.
   - Unstable is high all the time because it restarts every 8h.
5. **Changes expected from rc.0 PRs or harmless.**
   - New `GOSSIP_ERROR_FATAL_PEER` gossip errors (#10239), summed over the group: data_column 13.5/h, aggregate 5.9/h, block 1.3/h.
   - Exactly one `getCapabilities` engine error per beta/unstable node at startup.
   - All engine calls still go over json-rpc (REST/SSZ from #10204 is never chosen; `engine_api_requests{transport}` = json-rpc only).
   - Incoming `data_column_sidecars_by_range` error % on super is 12/62/70/17 and on sas 10/46/22/8. This is driven by request volume collapsing (super 401 → 151/h, sas 984 → 103/h). Absolute error counts are no higher than stable, and the ratio was already noisy before rc.0.
6. **Network-wide events, all groups hit equally.**
   - Hoodi `blocks_by_root` rate-limit floods (10-09 ~10–12h, 10-10 07–14h, 10-11 10–12h): `rate_limit_rpc` peer reports went from 155 to 12.4k/h on beta and from 86 to 11.0k/h on stable.
   - `ATTESTATION_ERROR_TOO_MANY_SKIPPED_SLOTS` went from 20 to 344/h on both beta and stable.
7. **Already explained, not re-checked:** `notifyNewPayload` −100ms (timer moved, #10204); beta-sas GC drop; devnet incoming `RESOURCE_UNAVAILABLE` for by_range requests (60–70% of `blocks_by_range`, 20–55% of `envelopes_by_range`).
8. **Host quirks unrelated to rc.0.**
   - unstable-arm64 shows a constant ~1.1-slot head lag since at least 10-03. Its block→head time is a normal 1.57s, so this looks like a metric artifact.
   - stable-mainnet-fcr event-loop lag p99 is about 38ms vs 11.5ms on beta, and beta-pre (same code) was also 11.4ms, so it's the host.

## 1. Health
- Sync is a flat 3 (min 3) in every window and every group; `up` = 1.000.
- Finality distance max is 2 everywhere. Reorgs per 6h: beta 2.4–3.7 → 1.8–2.7, the same as stable.
- Restarts: beta has one (the deploy, 21:53–22:00, beacon + VC) and none since. Stable has none. Unstable has 3–4 (rolling).

| role | head lag avg (slots) | peers avg |
|---|---|---|
| solo | .105/.128/–/.635 | 201.0/201.1/–/201.0 |
| semi | .169/.169/.127/.342 | 201.1/201.2/201.1/200.8 |
| super | .100/.127/.134/.121 | 201.0/201.1/201.0/201.2 |
| sas | .102/.127/.134/.127 | 201.0/200.9/200.8/201.0 |
| arm64 | .110/.121/1.13*/.122 | 201.0/201.0/201.3/200.9 |
| mainnet-fcr | .003/.003/.001/.516 | 207.5/207.2/203.8/206.2 |
| mainnet-super | .003/.001/.001/.003 | 206.3/207.3/204.1/208.0 |

Max head lag: beta-post ≤3 slots, stable ≤4. Minimum peers on beta-post: 187–199.

## 2. Block processing (all flat or better post-upgrade)

| role | recv→processed ms | blk-proc job ms | stfn block ms | epoch trans ms | % head >4s |
|---|---|---|---|---|---|
| solo | 370/350/–/381 | 196/182/–/200 | 74/69/–/78 | 793/742/–/943 | .76/.53/–/.73 |
| semi | 398/368/363/416 | 204/188/187/214 | 66/64/64/67 | 705/722/704/816 | 1.06/.48/.60/.71 |
| super | 446/444/441/444 | 230/226/226/230 | 68/69/69/70 | 891/828/840/894 | 1.37/.89/.83/.93 |
| sas | 572/531/424/564 | 282/265/215/282 | 72/72/67/73 | 980/874/752/975 | 2.28/1.62/1.14/1.96 |
| arm64 | 401/399/416/419 | 206/204/212/214 | 87/84/96/102 | 1212/1162/1169/1253 | .72/.49/.52/.54 |
| mainnet-fcr | 287/286/273/285 | 202/199/189/200 | 69/64/62/65 | 848/852/827/862 | .44/.31/.24/.26 |
| mainnet-super | 300/294/311/330 | 198/199/211/227 | 66/62/64/69 | 889/911/903/970 | .71/.79/.77/.91 |

Also clean:
- Epoch transitions per epoch: 1.00–1.01.
- Regen queue, block-processor queue and gossip-validation queue: no dropped jobs.
- Checkpoint-state cache: 0 reloads. State cache hit rate 1.000.
- `set_head_after_cutoff` per 6h: beta 7.7–26, stable 4.6–31.
- Regen calls are higher only for `validateGossipDataColumn` on supers, which was already the case pre-upgrade.

## 3. Resources

| role | RSS GB | CPU cores | EL p99 ms | GC main % | GC netw % |
|---|---|---|---|---|---|
| solo | 7.42/6.78/–/8.93 | .55/.51/–/.61 | 11.1/11.0/–/12.5 | .19/.16/–/.20 | .24/.22/–/.27 |
| semi | 7.93/7.48/14.2/24.0 | .75/.69/.71/.77 | 13.2/13.1/12.5/12.8 | .21/.17/.17/.21 | .33/.29/.30/.31 |
| super | 8.48/8.49/11.1/8.95 | 1.08/1.06/1.09/1.19 | 12.7/12.7/14.0/11.1 | .28/.27/.24/.31 | .57/.57/.61/.71 |
| sas | 10.4/10.2/9.3/21.1 | 3.23/3.20/3.03/3.10 | 39.6/37.4/31.9/32.9 | .89/.69/.52/.74 | 2.35/2.31/2.17/2.42 |
| arm64 | 14.3/8.8/8.9/14.4 | 1.17/1.06/1.13/1.30 | 12.8/12.6/18.1/14.6 | .25/.21/.23/.29 | .33/.31/.35/.36 |
| mainnet-fcr | 8.89/9.38/9.15/9.19 | .57/.54/.47/.54 | 11.4/11.5/11.4/37.8 | .14/.13/.14/.14 | .22/.20/.17/.20 |
| mainnet-super | 9.06/8.72/8.68/9.81 | .60/.60/.61/.65 | 11.8/11.8/14.9/11.3 | .15/.14/.14/.15 | .31/.29/.29/.33 |

- Heap used: Hoodi 2.75–2.88 GB, mainnet 3.71–3.82 GB, the same as stable.
- Leak check over the 57h beta-post window:
  - Heap used: −7 to +1 MB/day, i.e. flat.
  - External memory: +1 to +5 MB/day.
  - RSS: −1420 MB/day (arm64 settling down) to +427 MB/day (mainnet-fcr, see P3).
- Stable semi and sas RSS (24/21 GB) reflect 13.7 days of uptime, not code.

## 4. Network
- Gossip validation by topic: the only new error type is `FATAL_PEER` (by design, #10239).
- Data column `INVALID_SERIALIZED_BYTES`: 2.9/h on beta vs 1.6/h on stable, which is negligible.
- Average mesh peers per attestation subnet: 0.34–0.36 on beta, the same as stable (sas about 6). Per data-column subnet: 9.4–10.3 everywhere.
- Peers with negative score: beta-post 8.9–17 vs stable 8.5–20, so no rise.
- Outgoing request errors by reason, beta-post vs stable (per hour): `RESP_TIMEOUT` 62 vs 60, `SERVER_ERROR` 8 vs 6, `RATE_LIMITED` 1 vs 1.

## 5. Execution engine
- Engine HTTP errors: 0 in every window. `newPayload` and forkchoice-update results are VALID only (no SYNCING/UNAVAILABLE).
- There is no engine-state metric. Based on the counters above, no flaps are visible.
- `data_column_engine_result` split is unchanged: `null_response` is 40–43% on super/sas vs 33–37% on stable, which depends on the EL mempool.
- `getBlobsV2` overhead: see P2.

## 6. Validators (beta vs stable)

| metric | beta-pre / beta-post / unstable / stable |
|---|---|
| head hit % (super; sas) | 88.6/88.5/88.4/88.5; 87.8/88.1/88.1/87.9 (~88% is Hoodi-wide) |
| target / source hit % | ≥99.95 / ≥99.92 everywhere |
| inclusion distance | 1.000–1.012 everywhere; beta ≤ stable |
| wrong-head % (super; sas) | .63/.41/.30/.50; 1.57/.95/.67/1.13 |
| sync committee hit % (super; sas) | 98.8/99.1/99.3/98.7; 97.9/98.6/–/98.2 |

- Proposals since the upgrade: beta 27 canonical, 0 missed. Stable had 1 `not_submitted` in the same window.
- VC error counters on beta-post are all 0: attestation service, block proposing, signing, slashing protection, REST client.

## 7. Devnet ax41 (glamsterdam-devnet-8)
Windows: pre = 10-09 12:00 → 10-10 10:30; post = 10-10 20:00 → now.

**Heads-up: ax41-0 runs cde39f9 (PR #10345, gloas-native-integration), not b726a05.** Its heap is 0.17 GB vs 0.37 GB on the other three.

- **Health:**
  - All four are synced, finalizing at distance 2 (finalized epoch 13473 at clock epoch 13475).
  - Head lag avg 0.29–0.36 slots, max 5 (pre: max 4).
  - Peers went from 68–73 to 90–96.
  - Reorgs are about 18.7 per 6h, identical on all four nodes, so it's the network.
- **Engine:**
  - 0 HTTP errors. `newPayload` results are VALID only.
  - Nethermind `newPayload` mean dropped from 1.9s to 0.5s after its upgrade. Geth master is steady at about 1.8s.
- **Payload envelopes:**
  - One `PAYLOAD_ERROR_EXECUTION_ENGINE_ERROR` on each nethermind node at 10-10 18:25–18:30, when the EL restarted, and none since.
  - Reconstruction engine errors 0, block payload errors 0. Builder circuit breaker never active.
- **PTC:** about 224 quorums per hour. `verdict=false` is 6.6% post vs 5.5% pre, 5.55% in the last 6h. It's identical on all four nodes, so it's network-level.
- **Gossip:** data-column `PAST_SLOT` bursts (11T06, 12T08, about 108/h per node) appear on all four nodes on both ELs, so network-wide.
- **Resources:** RSS 3.0–4.0 GB (pre 4.3–5.0), CPU 0.52–0.56 cores, GC <0.1%, event-loop p99 about 11ms.
- **Monitoring gaps:**
  - The EL scrape (`job=execution`) on all three nethermind nodes has been down since their restarts on 10-10 (11:00, 15:00, 18:30), so there are no nethermind EL metrics.
  - `job=validator` on ax41-0 and ax41-3 has been down for the whole window.
