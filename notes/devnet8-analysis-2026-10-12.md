# glamsterdam-devnet-8 — Lodestar node analysis (2026-10-12)
Ask: Nico, Discord #devnet-8-analysis, 10:28 UTC — "check our devnet-8 nodes, anything off in the last ~3 days".
Builds on `notes/rc-sweep-2026-10-12/{logs,metrics}.md` (window 10-09 12:00 → 10-12 09:08).

## ax41-0..3 (ChainSafe) — live snapshot ~10:33 UTC
- head 431544-5 on all four, finalized 13483 (distance 2), peers 91-97. 0 warn/error-level lines in last 3h.
- versions: ax41-1/2/3 b726a05; ax41-0 cde39f9 (PR #10345 gloas-native-integration).
- no VCs on ax41 (validator_monitor_validators=0; job=validator on ax41-0/3 never up in 30d → stale scrape targets).
- job=execution down on the 3 nethermind nodes (since 10-10 EL restarts) → no nethermind EL metrics.
- disk: 685-745 GB free, ax41-3 freed 23 GB in 3d, others ±3 GB.

## Payload-envelope fetch storm — root cause
Code @ b726a05: `gossipHandlers.ts` ~L905 — each gossip column whose PayloadEnvelopeInput is incomplete arms
`waitForEnvelopeAndAllData(BLOCK_AVAILABILITY_CUTOFF)`; on timeout each one emits `incompletePayloadEnvelope`.
`unknownBlock.ts` `addByPayloadInput` → `toPendingPayloadInput` rebuilds the entry with `status: pending`
(L755), discarding an in-flight `fetching` status, so each emit starts another `downloadPayload()`.

Evidence slot 431363 (ax41-1, payload revealed, lodestar-erigon-2 proposer):
- block +0.7s, columns +0.8s, cutoff +3.0s → 128 emits → 128 concurrent downloadPayload() for one root
- ~730 failed EnvelopesByRoot (envelope not revealed yet; peers answer empty — Lodestar peers log "Cannot serve … not found")
- first success +6.5s → payload imported via unknown sync; 78 more concurrent downloads succeed and are dropped ("entry pruned during fetch")

Evidence slot 431280 (ax41-1, payload never revealed, grandine-besu-2 proposer, orphaned, Dora exec_block=0):
- block +4.3s (late), 128 columns, 268 downloadPayload() / 141 failed rounds from 09:36:14 to 09:52:03 (~16 min), stops only at
  finalization prune (`removed_payloads{reason=below_finalized}` ≈ 80/day/node).
- slots with exec_block=0 in the last hour: 3-4.4k failed requests per root per node (431280, 431316, 431434, 431455).

Rate now: ~55-65k "Missing execution payload envelope" log lines/h per node (~10% of all log volume);
`unknown_payload_download_result{failed}` 22-31k/24h vs `{resolved}` 8.7-21k/24h per node.

Fix status: draft PR #10289 (wemeetagain, opened 10-06, closes #10114) schedules one notification per input at the
payload deadline and keeps the in-flight entry. That covers the fan-out and early trigger. It does NOT obviously
cover the unrevealed-payload case (root retried until finalization). Related: issue #9921.

## Other ax41 checks
- req/resp (ax41-1, 1h): outbound execution_payload_envelopes_by_root 66.8k/h (~223/slot, 10x pings); inbound 16.5k/h.
  24h outgoing errors all nodes: RESPONSE_ERROR_RATE_LIMITED 557, SELF_RATE_LIMITED 1473.
- head lag ≥3 slots (1m samples, last 38h): 19-51 min/node, max 5 slots, co-occurring across nodes → missed-slot runs, network-level.
- ax41-0 = #10345 (nflaig, native gloas transitions) @ cde39f9 (PR head now 3f4f612). 24h vs ax41-1/2/3:
  epoch transition 68ms vs 133-135ms; heap 0.17 vs 0.36-0.38 GB; gossip block→processed 1.10 vs 1.13-1.15s; CPU 0.56 same; ELP99 13 vs 11-12ms.
  Same head/finality/lag pattern. No regression seen.

## Hosted ethpandaops Lodestar nodes (16) — subagent panda sweep + my spot checks
- All v1.49.0/9203d3d (`ethpandaops/lodestar:unstable`), 15/16 at head; redeploy of all 16 at 10-12 07:53-08:01; no crashes/OOM.
- buildoor-lodestar-besu-1 frozen 10-10 15:55 → 10-12 08:00: besu rejected canonical EL block 357508 (BAL hash mismatch) → "known bad block" ×1137. Besu-side. Resyncing.
- Block publish latency: spot-checked lodestar-geth-1 slots 431473/431486/431609/431645 → Publishing block at +753/+651/+635/+619ms. Dora median arrival geth: LS 754ms vs others 198-494ms; nimbusel 163/211 at +2001ms engine_pending fallback. Cause (waiting on engine race despite cached bid) = subagent hypothesis, unverified.
- Storm present on hosted nodes too: lodestar-geth-1 since 08:00:59 restart → 114k outbound envelopes_by_root (~41k/h), download failed 3620 / resolved 6332. Not visible in otel (debug level).
- Lodestar: missed 3.0% / orphaned 5.2%; attestation inclusion 99.2% (best CL). Finality on time every epoch 12809-13485.
- nimbusel pairs: EL timeouts dominate our errors; inclusion 96.6/97.4% vs 98.2-99.8% for other CLs on nimbusel (unexplained).
- erigon pairs: "EL syncing" flaps ~630×, inclusion 98.8%.
- Noise: 1.23M `execution_proofs` route-not-found warns (external poller).

## Follow-up: Nico asked if #10347 fixes it (10:51 UTC)
- Verdict: yes for the per-column fan-out (entry keeps `fetching`; downloadPayload sets fetching before first await). Fact-checked by second reviewer.
- Not covered: 3s trigger before envelope (#10289 covers); never-revealed payload retries — 431280 on ax41-1: 3574 failed requests, ~824 in the burst minute, ~2.75k serialized retries (~10 rounds/min) until finalization prune.
- Review posted: https://github.com/ChainSafe/lodestar/pull/10347#pullrequestreview-5489749891
- 10:52 Nico: "or alternative #10289" → #10289 fixes more: same dedup + trigger moved to payload deadline (devnet-8 PAYLOAD_DUE_BPS 5000 = +6s; 431363 first successful fetch +6.5s) + envelope-only arm. CI green, still draft. Neither fixes never-revealed retries.
- Review posted: https://github.com/ChainSafe/lodestar/pull/10289#pullrequestreview-5489770036
- 11:01 Nico closed #10347, asked for inline comments on what to port to #10289. Posted https://github.com/ChainSafe/lodestar/pull/10289#pullrequestreview-5489842631:
  (1) identity checks in reconcilePayloadEnvelope — concurrent reconciles of the same envelope entry can overwrite an active fetching/processing entry (verified by second reviewer); (2) optional: identity check instead of has() in downloadPayload/processPayload for prune+re-admit. Tests to adapt named. Nico wants #10289 deployed on a group to verify spam drop.
