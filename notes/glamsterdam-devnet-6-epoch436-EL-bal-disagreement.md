# ⚠️ CORRECTED 2026-06-28 — ROOT CAUSE IS CL (PRYSM), NOT EL

**The original verdict in this file ("EL BAL non-interop") was WRONG.** Corrected:
- pk910 (ethpandaops, 2026-06-27 ~20:00 UTC, #interop-🌃 "Flamingos or beavers?") identified the real cause: **Prysm sent `engine_newPayload` to its EL with an EMPTY block access list (BAL)**. The EL then *correctly* rejected it (besu: "Invalid block access list encoding"; geth: "failed to decode BAL: EOF"). An empty byte-list BAL explains BOTH signatures — far more parsimoniously than "two ELs independently disagree." barnabasbusa + pk910 were right.
- So EL rejections were the SYMPTOM; the CL (Prysm) emptying the BAL before newPayload was the CAUSE.
- My analytical error: I attributed cause by which EL *built* each block (extraData "bes…"/ethrex), not by which CL *relayed* it. Rejections actually clustered on the common relaying CL (Prysm) — the tell I missed. I also explicitly flagged the CL-envelope hypothesis then deprioritized it because it "didn't implicate Lodestar" — letting "not our client" bias me off the right answer.
- **Lodestar is NOT affected** (source-audited, branch `review/alpha.11`): carries BAL end-to-end as an opaque ByteList passthrough (gossip decode → PayloadEnvelopeInput → importExecutionPayload → notifyNewPayload → serializeExecutionPayload populates `blockAccessList` from real bytes → `engine_newPayloadV5`); `parseExecutionPayload` hard-errors if a gloas payload lacks a BAL. Prysm's bug came from re-encoding a *structured* BAL container into the engine request; Lodestar's opaque-passthrough makes that class unreachable. Proof: types/src/gloas/sszTypes.ts:208-217; beacon-node/src/execution/engine/types.ts:315-319 & 416-422; engine/http.ts:219-257; chain/blocks/importExecutionPayload.ts:170-176.
- CAVEAT: could NOT independently re-pull the otel logs to show the empty-BAL line myself — panda/ClickHouse auth down (ethpandaops authentik 503 + expired local creds owned by `nico`). Confidence rests on pk910+barnabasbusa (full data access) + the corroborating Lodestar source audit, not my own log pull. Capture the smoking-gun line when panda recovers.

## devnet-6 Lodestar footprint (from ethpandaops/glamsterdam-devnets k8s config, pulled 2026-06-28 while panda down)
Lodestar nodes on glamsterdam-devnet-6 (4):
- **lodestar-besu-1** (Lodestar + Besu)
- **lodestar-geth-1** (Lodestar + Geth)
- **lodestar-ethrex-1** (Lodestar + Ethrex; image `ethpandaops/lodestar:deathstar-devnet-6`; ethrex-paired → likely caught in the SEPARATE ethrex desync = ethrex's bug, not ours)
- **buildoor-lodestar-besu-1** (Lodestar + Besu, ePBS builder/"buildoor")

Full CL roster: {lighthouse,lodestar,nimbus,prysm,teku} × {besu,ethrex,geth} + buildoors {lighthouse-geth, lodestar-besu, prysm-ethrex} + bootnode-1.

So Lodestar WAS on devnet-6 — my earlier "no lodestar node involved" rationale was wrong. Correct basis for "not affected" = the source audit + (pending) absence of lodestar-besu BAL-rejects in the wild.

WILD TEST when panda recovers (turns the source-audit into empirical proof):
1. `lodestar-besu-1` besu (container.name=execution): expect ZERO "Invalid block access list encoding" around epoch 436 — prysm-besu-1 had them; lodestar-besu-1 should not.
2. `buildoor-lodestar-besu-1`: blocks it BUILT should carry a non-empty BAL and be accepted network-wide.
3. Confirm the empty-BAL rejections trace to prysm-* relays.
CAVEAT: source audit was branch `review/alpha.11`; deployed devnet-6 image is `deathstar-devnet-6` — the wild check closes that code-identity gap.

## 2026-06-28 ~22:00 — SSH RE-VERIFICATION (panda still down; went to the boxes directly via devops@<node>.srv.glamsterdam-devnet-6...)
- **Images (ground truth ≠ config):** all 3 reachable Lodestar nodes run `ethpandaops/lodestar:glamsterdam-devnet-6` — NOT the `deathstar-devnet-6` in ansible host_vars (watchtower auto-updates; the config tag is stale). ELs: besu/geth/ethrex:glamsterdam-devnet-6. `buildoor-lodestar-besu-1`: SSH publickey denied (not checked).
- **Lodestar is NOT the cause — EMPIRICAL proof (closes the source-audit caveat):** `lodestar-besu-1` besu logged **ZERO** BAL/payload rejects in 60h while its EL advanced to **block 13556** (past the incident). Lodestar fed besu valid BALs the whole time → no Prysm-class empty-BAL bug on the *deployed* image.
- **Per-node "fell out of sync" (all downstream; none a Lodestar bug):**
  - `lodestar-geth-1`: **geth** rejected besu-built blocks `failed to decode BAL: EOF` — **10,369×** over 06-27 15:30→06-28 09:02, blocks 9940–11072 → couldn't import → wedged at slot 12671 / exec block 11435; beacon restarted ~06-28 09:02, now stuck re-syncing (finalized 393). Separate minor geth bug: 211× "Failed to decode blob limbo entry" (BlobTxCellSidecar RLP).
  - `lodestar-besu-1`: besu clean but **peer-starved (1–3 peers)** → stuck at slot 16098 (epoch 503). Post-collapse fragmentation, not an EL/CL error.
  - `lodestar-ethrex-1`: healthiest — at chain tip (head slot−1/−2, finalized 435, ethrex block 18018); only fails `producePayloadAttestationData` ("No canonical block found") because the net isn't producing canonical blocks.
- **Refined root cause (two layers):** (1) TRIGGER — empty/truncated BAL in gossiped payloads [pk910: Prysm]; (2) FORK MECHANISM — ELs disagree on the bad BAL: **geth strict-rejects ("EOF"), besu tolerates** (besu node reached block 13556 / 0 rejects; geth node wedged at 11435). The besu↔geth split fractured the net — downstream of the CL trigger, not the cause. My original "EL disagreement" sensed layer (2) but missed the CL trigger (1).

## 2026-06-28 ~22:30 — CROSS-CLIENT CHECK walks back "none a Lodestar bug"
`/eth/v1/node/syncing` across clients (bn-basic-auth, user `eth`; cred file has a comment header — parse non-`#` lines). Clock slot ~24848:
- **SYNCED to tip (dist 0):** lighthouse-{geth,besu,ethrex}, teku-geth, nimbus-geth, **lodestar-ethrex**.
- **STUCK (syncing, far behind):** lodestar-geth (12671, dist 12177), lodestar-besu (16098, dist 8750), prysm-geth (18653, dist 6195).
=> **NOT network-wide and NOT "Lodestar just follows the EL".** Lighthouse/Teku/Nimbus reached the tip on the SAME geth/besu ELs while Lodestar+geth, Lodestar+besu, and Prysm+geth did not. Lodestar nodes are specifically failing to recover. (My "all downstream; none a Lodestar bug" above was too strong.)
- STILL DEFENSIBLE: Lodestar BAL *serialization* is fine (lodestar-besu besu = 0 BAL rejects; snooper shows geth returning VALID to Lodestar newPayloads) — not emptying BALs wholesale.
- OPEN LODESTAR QUESTION (do NOT hand-wave as "not our client"): why can't Lodestar+geth / Lodestar+besu resync past the bad-BAL region when Lighthouse can? Hypotheses: (a) ops checkpoint-resynced LH/teku/nimbus (skip the bad region) while Lodestar/Prysm forward-sync and wedge on the EL-rejected historical block; (b) a Lodestar (and Prysm?) sync/fork-choice recovery issue. lodestar-ethrex at the tip => EL-interaction-specific, not a blanket Lodestar bug.
- NEXT: compare lodestar-geth-1 (forward-wedged 12671) vs lighthouse-geth-1 (tip) — checkpoint vs forward sync; is Lodestar fork-choice stuck on the bad fork / can it abandon it.

## 2026-06-28 ~23:10 — ROOT-CAUSE INVESTIGATION (per Nico) + Lodestar fix PR #9560
Q: why did the Lodestar nodes fall out of sync — Lodestar bug or not? Analyzed on-disk debug logs (`/data/lodestar/beacon-2026-06-27.log`, 14M lines, sudo-readable).
- **Wedge cause = PEER STARVATION, not the EL.** geth-1 ran at **0–2 peers almost all of 06-27** (peers:0 ×2907, :1 ×2606, :2 ×1406; rarely >3). No peers → can't sync. Churn was massive: 40,517 Connected / 29,230 goodbye / **3,406 "reason=Peer banned this node"** + reqresp DIAL_ERROR/TIMEOUT/EMPTY_RESPONSE.
- **Lodestar BUG found + FIXED → PR https://github.com/ChainSafe/lodestar/pull/9560.** `PeerDiscovery` constructor init-order: `this.transports` is read by `handleDiscoveredPeer()` but assigned at the END of the constructor; with `--network.connectToDiscv5Bootnodes` (set on these supernodes), every bootENR is processed first → `this.transports` undefined → throws `Cannot read properties of undefined (reading 'includes')` → **node never dials its bootnodes on startup** (worst right after a restart). Reproduced: every restart I did left the node stuck at 1 peer. Fix moves the init above the bootENR loop. Present in `unstable` too.
- **Honest scope:** #9560 explains the post-restart peer-bootstrap failure but is likely not the complete story — the 3,406 "peer banned this node" events suggest peers also actively banned our node (plausibly a far-behind supernode failing to serve data-column reqresp → downscored = spiral once behind). Fully attributing the bans needs deeper reqresp/gossip analysis.
- onDiscovered TypeError = only 12× steady 06-27 but spams on every restart (bootENR loop) — consistent with the init-order cause.
- **Recovery:** all 3 reachable nodes checkpoint-synced back to head via `--unsafeCheckpointState` from ethrex-1's head (geth/besu/ethrex dist 0, peers 16/13/10). `buildoor-lodestar-besu-1` still stuck (no SSH access). NOTE: deployed image still has the bug + my temp containers carry checkpoint flags, so a restart may re-wedge until #9560 ships in the devnet image. Lesson: don't swap back to the original container during non-finality (it reloads an old archived state → reverts far behind).

--- ORIGINAL (WRONG) ANALYSIS BELOW, kept for audit trail ---

# glamsterdam-devnet-6 — participation collapse epoch 436 — ROOT CAUSE: EL BAL disagreement

Investigated 2026-06-27 (Nico asked in Discord thread, then pointed at "ELs not agreeing").
Network: glamsterdam-devnet-6 (12s slots, 32 slots/epoch, genesis 1782387000, Gloas/ePBS active since epoch 30).

## Verdict
Nico was right: **execution clients disagree on EIP-7928 Block-Level Access List (BAL) encoding.**
- **besu** rejects payloads with `validationError: Invalid block access list encoding`.
- **geth** and **ethrex** ACCEPT the same blocks as valid.
This cross-client split fractured ePBS payload-attestation (PTC) → payloads never confirmed → finality halted → chain forked into many competing heads. The earlier CL-side "PTC / UNKNOWN_PAYLOAD_STATUS / data unavailable" symptoms are DOWNSTREAM of this EL split.

## Hard evidence (panda otel-logs, container.name='execution')
SPLIT TEST — same blocks, opposite verdicts (09:43–09:59):
- blocks 12531 / 12565 / 12589: **besu = INVALID**, **geth = IMPORTED**, **ethrex = EXEC'd**.
Window totals 09:00–11:30: besu = 8 "Invalid block access list encoding" rejects; geth = 0 BAL rejects; ethrex = 0.

besu reject cadence (block #, all on prysm-besu-1), ACCELERATING into epoch-436 boundary (slot 13952 @ 10:00:24Z):
12398 (09:16) · 12430 (09:23) · 12474 (09:32) · 12531 (09:44) · 12536 (09:45) · 12565 (09:52) · 12589 (09:57) · 12609 (10:02:27).

Block 12609 (slot 13961, hash e52da8..f491fa, parent 69379d..9c31c4, extraData "bes…" = besu-built):
- besu newPayload → INVALID "Invalid block access list encoding"
- geth newPayload → INVALID "Invalid NewPayload params" (declared blockHash ≠ geth-computed → BAL bytes differ) — i.e. a besu-built block that geth also can't reconstruct.

## Current state (11:2x, epoch 449)
finalized epoch 435 (unchanged), justified 436, **14 epochs without finality**, finalizing=False,
global participation ~23% (was ~95%). besu nodes currently on DIFFERENT heads than geth nodes
(e.g. 986d3 / e09ac / 64202 / a50c3 / 56bd1 at block ~12,777) — sustained fork, no convergence.

## Two distinct problems found
1. **(root cause of collapse)** besu ⟷ geth/ethrex BAL encoding disagreement (EIP-7928). One side has a spec/encoding bug.
2. **(separate, pre-existing)** ethrex is fully desynced since before 09:00 — full-sync fails with `Invalid Block: Invalid transaction: Nonce mismatch`, `post-state for block N absent … datadir needs a fresh resync`. Independent ethrex bug; was already down while network was still at 95%, so NOT the trigger.

## Open question / next step
Who is spec-correct — is besu strictly enforcing the EIP-7928 BAL SSZ encoding (geth/ethrex too lenient), or is besu's BAL decoder buggy (rejecting valid BALs)? Needs side-by-side compare of the BAL SSZ bytes for one rejected block (e.g. 12589) against the EIP-7928 encoding, looped in with besu + geth teams. Lodestar relevance: as a CL we re-serialize the payload/BAL in the ePBS envelope path — verify Lodestar isn't mangling the BAL on encode/decode (check the besu-rejected blocks that transited a lodestar-besu node).

panda session used: ef9a55d299b5. Table external.otel_logs (clickhouse-raw). Keys: container.name (beacon/execution/validator/buildoor), ethereum_el, ethereum_cl, host.name (<cl>-<el>-N). NOTE: log.file.name is NULL on this network — use container.name to split CL/EL.

## 2026-06-27 ~12:35 UTC update — slot 13965 worked example + geth ALSO fails BAL decode
Nico asked in Discord thread channel:1520396387999682753 ("Who is to blame? Flamingos or beavers?"): CL or EL, specifically slot 13965.

SHARPENED ROOT CAUSE: it is **not** "besu strict vs geth/ethrex lenient" — it's a genuine **EIP-7928 BAL non-interoperability**. The same block is rejected by TWO different ELs for the BAL:
- Block 12609 `0xe52da835..f491fa` (besu-built, extraData "bes…", slot 13961, 174 tx), at 10:02:27Z:
  - **besu** (prysm-besu-1): `status: INVALID, validationError: Invalid block access list encoding`
  - **geth** (bootnode-1): `Invalid NewPayload params … error="failed to decode BAL: EOF"`
  Two independent ELs can't decode the same block's BAL → the BAL bytes are malformed / encoding disagreement, NOT one strict client.

EL fork is severe: at height **12609** there are ≥5 competing imported blocks (geth bootnode view):
  e0f2bc (156tx) · e52da8 (174tx, besu, INVALID×2) · f66751 (3tx) · fea449 (47tx, ethrex=slot 13965) · 8be1fe (299tx).
besu fork-choice oscillates back to common parent `0x69379d` (block 12608) → besu nodes can't settle on any 12609.

### slot 13965 specifically
- Proposer: **prysm-ethrex-1** (proposer_index 83). CL block root `0xc167a6aa6f57…`. EL payload = block 12609 `0xfea44960933e…` (47 tx, 25 Mgas, ethrex-built).
- Accepted by **geth** (bootnode-1 + buildoor-lighthouse-geth-1 both "Chain head updated → fea449") and **ethrex** (all 4 ethrex nodes ran the block: prysm/lighthouse/nimbus/teku-ethrex-1).
- Re-org'd **all 3 lighthouse nodes** (besu/ethrex/geth): "Beacon chain re-org previous_head 0x49fe343d" → head 0xc167a6aa (slot 13965).
- **besu-paired nodes never followed it** (stuck at parent 12608) → nimbus-besu-1 "Dropping attestation … AttestationData: block not found".
- => 13965 is ONE of the ≥5 competing 12609s — a symptom of the EL split, not its cause.

VERDICT for Nico: **EL, not CL.** Every CL (Lodestar/LH/Prysm/Nimbus/Teku) faithfully follows its paired EL's validity verdict; the CL chaos (re-orgs, block-not-found, PTC/payload-attestation failures, finality halt) is downstream. Lodestar not implicated (the geth-EOF block never transited a Lodestar node). Follow-up is on besu+geth EL teams: diff the BAL SSZ bytes of a rejected 12609 (e.g. e52da8) vs EIP-7928 — "EOF" => truncated/over-long BAL field.
