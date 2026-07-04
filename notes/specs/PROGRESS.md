# Consensus Specs Study — Progress Tracker

## Plan
Read specs alongside Lodestar code. Document learnings. Open PRs for any issues found.

## Priority Order
1. **Gloas/EPBS** (active work area)
2. **Phase0** (foundation)
3. **Altair** (sync committees, light client)
4. **Bellatrix** (the merge, execution payloads)
5. **Capella** (withdrawals)
6. **Deneb** (blobs, KZG)
7. **Electra** (current mainnet fork)
8. **PeerDAS/Fulu** (next fork)

## Additional Resources
- **Beacon APIs** (`~/beacon-APIs`) — OpenAPI spec for beacon node REST API, includes `validator-flow.md` (implementation reference for validator client ↔ beacon node interaction)

## Format per section
- Spec file: `consensus-specs/specs/<fork>/<topic>.md`
- Lodestar impl: `packages/<pkg>/src/...`
- Spec tests: `packages/beacon-node/test/spec/...`
- Notes: `notes/specs/<fork>-<topic>.md`
- Cross-reference: Lighthouse (Rust), Prysm (Go), Teku (Java) when useful
- Verify findings with gpt-advisor / Codex CLI before opening PRs

## Progress

### Gloas/EPBS
- [x] Beacon chain changes (`specs/gloas/beacon-chain.md`) — notes in `gloas-beacon-chain.md`
- [x] Fork choice (`specs/gloas/fork-choice.md`) — notes in `gloas-fork-choice.md`
- [x] Builder (`specs/gloas/builder.md`) — notes in `gloas-builder.md`
- [x] P2P networking (`specs/gloas/p2p-interface.md`) — notes in `gloas-p2p-interface.md`
- [x] Validator (`specs/gloas/validator.md`) — notes in `gloas-validator.md`
- [x] Fork logic (`specs/gloas/fork.md`) — notes in `gloas-fork.md`

### Phase0
- [x] Beacon chain state transition (`specs/phase0/beacon-chain.md`) — notes in `phase0-beacon-chain.md`
- [x] Fork choice (`specs/phase0/fork-choice.md`) — notes in `phase0-fork-choice.md`
- [x] P2P networking (`specs/phase0/p2p-interface.md`) — notes in `phase0-p2p-interface.md`
- [x] Validator (`specs/phase0/validator.md`) — notes in `phase0-validator.md`
- [x] Weak subjectivity (`specs/phase0/weak-subjectivity.md`) — notes in `phase0-weak-subjectivity.md`

### Altair
- [x] Beacon chain changes (`specs/altair/beacon-chain.md`) — notes in `altair-beacon-chain.md`
- [x] Light client sync protocol (`specs/altair/light-client/`) — notes in `altair-light-client.md`
- [x] Fork choice updates (`specs/altair/fork-choice.md`) — minimal (timing helpers only)

### Bellatrix
- [x] Beacon chain (execution payloads) — notes in `bellatrix-beacon-chain.md`
- [x] Fork choice (POS transition, Engine API, proposer reorgs) — notes in `bellatrix-fork-choice.md`

### Capella
- [x] Beacon chain (withdrawals, BLS-to-execution changes, historical summaries) — notes in `capella-beacon-chain.md`

### Deneb
- [x] Beacon chain (blob sidecars, KZG commitments, EIP-4844/4788/7044/7045/7514) — notes in `deneb-beacon-chain.md`
- [x] Fork choice (is_data_available, PayloadAttributes with beacon root)
- [x] P2P (blob subnets, BlobSidecarsByRange/Root, gossip validation)
- [x] Validator (BlobsBundle, sidecar construction, subnet assignment)
- [x] Polynomial commitments (KZG proof system, trusted setup — delegated to c-kzg native lib)

### Electra
- [x] Beacon chain (5 EIPs: EIP-6110 on-chain deposits, EIP-7002 EL exits, EIP-7251 MaxEB/consolidations, EIP-7549 attestation format, EIP-7691 blob increase) — notes in `electra-beacon-chain.md`
- [x] P2P (SingleAttestation gossip, 9 blob subnets, updated limits)
- [x] Validator (SingleAttestation construction, execution requests, compute_on_chain_aggregate)
- [x] Fork upgrade (upgradeStateToElectra — complex migration)

### PeerDAS/Fulu
- [x] DAS core (custody groups, column assignment, reconstruction, sampling) — notes in `fulu-peerdas.md`
- [x] Beacon chain (EIP-7917 proposer lookahead, EIP-7892 blob schedule, modified process_execution_payload)
- [x] Fork choice (simplified is_data_available for columns)
- [x] P2P (128 column subnets, DataColumnSidecarsByRange/Root, Status v2, MetaData v3, ENR cgc/nfd)
- [x] Validator (validator custody scaling, sidecar construction, distributed blob publishing)

---

## Re-verification passes (post-completion)

Forks are surface-read; Gloas/EPBS keeps churning, so spot-re-verify the hot areas
against **`origin/master`** (never a stale local checkout — `~/consensus-specs` was
detached 18 days behind on 2026-06-19 and faked a discrepancy).

### 2026-06-19 — Gloas fork-choice (proposer boost + payload build) [notes: gloas-fork-choice.md]
- ✅ `should_build_on_full` (post #5210 timeliness change) — **in sync**, no action.
- ⚠️ `update_proposer_boost_root` missing `is_same_dependent_root` guard from **#5306** —
  candidate gap, but future-fork lag in Nico's active area. Documented, no PR/no ping.

### 2026-06-26 — phase0 fast-confirmation `is_confirmed_chain_safe` (#5288) [Lodestar: packages/fork-choice/src/forkChoice/fastConfirmation/utils.ts]
- Context: re-verified against `origin/master` (local consensus-specs is on my own monotonicity
  proposal branch `ab546e161`, 65 behind master — intentional for the open proposal PR).
- **#5288** (Mikhail Kalinin, 2026-05-29) changed `is_confirmed_chain_safe`: instead of
  `is_ancestor(confirmed_root, GU.root)`, it now checks
  `GU == get_checkpoint_for_block(confirmed_root, GU.epoch)` — verifies the (root, epoch) pair,
  not just root ancestry.
- ✅ **Lodestar already in sync.** `isConfirmedChainSafe` (utils.ts:760) uses
  `getCheckpointForBlock(confirmedRoot, GU.epoch)` + `equalCheckpointWithHex` against
  `currentEpochObservedJustifiedCheckpoint` — exactly the post-#5288 form. `getCheckpointForBlock`
  (utils.ts:72) matches `get_checkpoint_for_block` (ancestor at epoch-start slot). No PR needed.
- Note: master's `get_latest_confirmed` keeps the epoch-boundary `is_confirmed_chain_safe` revert;
  my open monotonicity-guard proposal (consensus-specs branch + Lodestar PR) is the divergence,
  not adopted upstream. Consistent with prior understanding — see [[project-fast-confirmation-resets]].

### 2026-07-03 — Gloas builder constants [notes: gloas-builder-constants-drift.md]
- Re-verified vs `origin/master` (batch of gloas constant PRs all merged 2026-07-03).
- ⚠️ **3 stale constants on Lodestar `unstable`** (Nico's active area — documented, no autonomous PR):
  - `BUILDER_WITHDRAWAL_PREFIX` `0x03` → spec `0xB0` (#5416)
  - `MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD` `256` → spec `64` (#5420, mainnet+minimal preset)
  - `MIN_BUILDER_WITHDRAWABILITY_DELAY` mainnet `8192` → spec `64` (#5426); minimal `2` ✅ matches
- No live-devnet break (spec pins lag today's master); forward-alignment work. Captured in BACKLOG for next main-session sweep (cron blocked from #347); PR only on Nico's go.

---
*Started: 2026-02-15*
*Last updated: 2026-07-03 — Gloas builder-constants re-verify: 3 stale constants (prefix 0x03→0xB0, deposit-req 256→64, withdrawability-delay 8192→64) all from spec PRs merged same day; documented, flagged to Nico, no autonomous PR (his active area)*
*🎉 ALL FORKS COMPLETE (surface read 2026-02-18); now in spot-re-verify mode*
