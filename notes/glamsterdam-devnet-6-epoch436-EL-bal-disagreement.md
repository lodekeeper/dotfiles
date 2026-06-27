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
