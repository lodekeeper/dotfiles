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
