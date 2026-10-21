# Bounded defaults / identity verification

Read-only source verification at `119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b` (`origin/pr10379-review20261020`). No code edits, pushes, or posts.

## 4330036023 — revealer.ts:14

- Public option is `reveal.cutoffBps`; builder.ts:64–65 documents network PAYLOAD_ATTESTATION_DUE_BPS fallback; builder.ts:211 implements `opts.reveal.cutoffBps ?? config.PAYLOAD_ATTESTATION_DUE_BPS`. CLI options.ts:180–182 already describes fallback; handler.ts:145 passes optional override.
- mainnet.ts:110 and minimal.ts:102 use7500:75% of slot. Mainnet12000ms (mainnet.ts:72,74) means9000ms. It is a network config value, not a hardcoded universal9s. Slot duration comes from the observed slot's fork; forkConfig/index.ts:263–268 chooses SLOT_DURATION_MS_HEZE post-Heze, otherwise SLOT_DURATION_MS, and rounds `bps*slotDurationMs/10000`.
- revealer.ts:36–71 runs immediately on observed matching imported block with retained payload; this is a last-start cutoff, not a timer targeting75%. `msFromSlot > cutoffMs` skips, so equality is allowed. No budget reserved for envelope construction/signing/API transfer; near deadline a started reveal may finish after deadline. Do not claim cutoff enforces completion by PTC deadline.
- Distinguish from BN's PAYLOAD_DUE_BPS5000 (mainnet.ts:112) payload wait/safety timing: gossipHandlers.ts:162–163 times waiting for envelope/data with `getPayloadDueMs`. That is not this7500 builder decision. Envelope API invokes validateApiExecutionPayloadEnvelope (blocks/index.ts:813); validation/executionPayloadEnvelope.ts:13–24 shares gossip validation. No intra-slot7500 rejection found there; do not claim BN rejects all reveals past7500.

Suggested concise response:
“Yep — `reveal.cutoffBps` falls back to the network's `PAYLOAD_ATTESTATION_DUE_BPS` (7500 in the default configs:75% of the slot,9s for12s slots). It reveals immediately when our bid's block is observed; this only stops starting a late reveal. The public option/CLI already mention the fallback, but making it explicit here would help too.”

## 4330028816 — identity.ts:102

- Exact head already polls every next slot for pending/unknown identity (identity.ts:100–105,151–152), unlike earlier epoch-only approach. Pre-Gloas waiting alone uses epoch polling (:65–73,147–149); transient400 at fork uses slot polling (:80–89).
- Explicit `stateId:"head"` at identity.ts:116–118; NEVER describe as default-finalized endpoint. state API index.ts:165–169 uses requested state's finalizedCheckpoint.epoch; types/utils/validatorStatus.ts:64–72 says active iff withdrawableEpoch FAR_FUTURE and depositEpoch < finalizedEpoch. Equality is pending. state-transition/util/gloas.ts:79–80 matches.
- state/utils.ts:70–79 normally returns cached head block post-state by head.stateRoot (fallback chain.getHeadState only if absent). Wall clock reaching epoch slot0 does not guarantee new-epoch head imported. Thus epoch-start poll can see old finalization and delay discovery a whole epoch in epoch-only strategy; slot1 is a reasonable reduced polling alternative when head has advanced, but no unconditional guarantee if slots are skipped or head/import delayed. Once-per-epoch poll at slot1 is not intrinsically wrong, nor per-slot intrinsically necessary.
- New builder registry entry itself can appear at an arbitrary block/deposit slot: state-transition/util/gloas.ts:249–250 pushes builder with depositEpoch computed from processing slot. Activity changes when finalized checkpoint crosses depositEpoch, normally epoch processing, and only visible when head state reflects it. No separate activation queue flag/sweep is used by API status.
- Withdrawal sweep is different: processWithdrawals.ts:188–247 sweeps up to configured builder limit, withdrawing full balance only when withdrawableEpoch <= current epoch (:231–241). It does not turn pending builders active.

Suggested concise response:
“Agreed — polling right at slot0 can still read the previous head's post-state, so an epoch-only retry can miss the updated status until the next epoch. A slot1 poll after the head advances would avoid that usual boundary race without polling every slot. This head currently retries each slot; it explicitly requests `head`, with active determined by `depositEpoch < state.finalizedCheckpoint.epoch`.”

## Optional balance check

Default minOperatingBalanceGwei1_100_000_000 (defaults.ts:14–15) is1.1ETH admission threshold; bidder.ts:127–138 only declines below it then caps affordability using balance minus MIN_DEPOSIT_AMOUNT minus unsettled bids. Thus not a reserved1.1ETH post-bid floor. Withdrawals sweep is exit-based rather than draining active balances automatically to1ETH. No claim about10500 versus10000 investigated/proven.
