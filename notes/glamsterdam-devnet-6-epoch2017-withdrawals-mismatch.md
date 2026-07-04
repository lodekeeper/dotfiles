# glamsterdam-devnet-6 — ePBS withdrawals-mismatch at slot 64575 (epoch 2017)

Investigated 2026-07-04 ~10:55 UTC (Nico asked in Discord thread channel:1522918321824206968:
"don't get that, it's likely the proposer fault, was the payload canonical?").

## Verdict (Nico right on both counts; my devnet-health alert over-claimed)
- **Payload was NOT canonical.** Beacon block 64575 `0x563d25b70ae0…72e3` IS canonical (valid bid),
  but the execution **payload envelope** was rejected by **every CL** (Lodestar/LH/Prysm/Teku/Nimbus)
  with the identical mismatch → payload stays EMPTY/withheld. Unanimous reject = consensus working, NOT a fork.
  - payload withdrawals root `0x792930bbd5baac43…4bb535` (0 withdrawals) vs state-expected `0xe037022065743b…0d0b`.
  - `builderIdx=18446744073709551615` (2^64-1) = self-built.
- **Root cause = Nimbus-eth1 EL ("nimbusel") builds payloads with EMPTY withdrawals when state expects some.**
  - Every affected, resolvable slot is nimbusel-paired: 64305/64309/64575 = teku-nimbusel-1; 64313/64353 = grandine-nimbusel-1.
  - Smoking gun: `nimbus-nimbusel-1` CL caught its OWN EL 12× today (09:02→10:41):
    `Execution client returned unexpected payload withdrawals … withdrawals_from_cl_len=1 withdrawals_from_el_len=0`
    → `Failed to get execution payload from EL reason="Execution client returned mismatching withdrawals"`.
  - Nimbus-CL pre-validates the EL's getPayload output and REFUSES to propose the bad payload;
    Teku/Grandine do NOT pre-validate → they reveal the bad envelope → network-wide reject.
- **Not a finality problem.** Dora overview: finalized=2017, justified=2018, current=2019, finalizing=true,
  epochs_since_finality=2 (normal lag). Epoch 2017 finalized:true, 0 orphaned. The alert's
  "not finalizing since epoch 2017 / network fragmentation" was a boundary misread + reading the unanimous
  reject as a split. TODO: fix devnet-health heuristic (don't treat unanimous envelope-reject as fragmentation;
  don't treat normal 2-epoch finality lag as "not finalizing").
- **Lodestar is CLEAN.** lodestar-erigon-1 + lodestar-nimbusel-1 rejected the bad envelope exactly like everyone else
  ("Envelope verification error: Withdrawals mismatch between payload and expected payload=0x792930… expected=0xe037…").
  Optional hardening (NOT a bug): add Nimbus-CL-style pre-reveal EL-withdrawals sanity check so Lodestar would never
  reveal a buggy EL's payload if paired with one.

## Impact
Low-grade: nimbusel-proposed slots produce empty/withheld payloads (Dora wd=0) or miss (64214/64232/64384/64421 = Missing).
~handful of slots/epoch; network still finalizes. Follow-up belongs with the Nimbus-eth1 team, not Lodestar.

## Data sources
panda dora slot/overview/epoch glamsterdam-devnet-6; panda clickhouse `external.otel_logs`
(ResourceAttributes['network']='glamsterdam-devnet-6', container.name='beacon', match Body).
