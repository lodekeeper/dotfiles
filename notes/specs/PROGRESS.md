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

### 2026-07-17 — phase0 p2p QUIC-primary mandate (#5330) [Lodestar: packages/beacon-node/src/network/libp2p/index.ts, network/options.ts]
- Re-verified vs `origin/master`. **#5330** (Cayman, merged 2026-07-06) makes QUIC (UDP)
  **MUST-support** (was MAY) and the *primary* transport; TCP downgraded to a SHOULD fallback;
  mplex MUST→MAY (TCP-fallback only, QUIC muxes natively); ENR entry order lists `quic` before `tcp`;
  "clients SHOULD prioritise peer's QUIC addresses" when reachable over both.
- ✅ **Lodestar already fully in sync.** Verified against `origin/unstable`:
  - `defaultNetworkOptions.quic: true` + `tcp: true` (options.ts:77-78); default listen addrs ship
    both `/udp/9001/quic-v1` and `/tcp/9000` for v4+v6 (options.ts:59-62).
  - Dial path prefers QUIC: `getDiscv5Multiaddrs` uses `quicMultiaddr ?? tcpMultiaddr` (index.ts:29-32,
    comment "Prefer QUIC over TCP when available") → matches the new SHOULD-prioritise-QUIC clause.
  - CLI refuses to disable both transports (`Cannot disable both TCP and QUIC`, network.ts:93-94);
    quicPort defaults to port+1 / 9001.
- No PR needed. Spec change is normative-text only (capability + priority already implemented years ago).
  ENR field ordering is cosmetic in the spec; Lodestar sets both keys, order-independent.

### 2026-07-24 — Electra/Capella withdrawal-sweep refactor re-verify (get_balance_after_withdrawals) [Lodestar: packages/state-transition/src/block/processWithdrawals.ts]
- Trigger: master churn survey found the withdrawal sweep refactored into helpers
  `get_pending_partial_withdrawals` + `get_validators_sweep_withdrawals`, both delegating balance
  math to a new Capella helper `get_balance_after_withdrawals(state, i, withdrawals)` =
  `state.balances[i] - sum(w.amount for w in withdrawals if w.validator_index == i)`, and
  `get_expected_withdrawals` now returning an `ExpectedWithdrawals` container with explicit
  `processed_partial_withdrawals_count` / `processed_validators_sweep_count`.
- **Behavior-preserving vs stable v1.6.1.** Confirmed by diffing the function against
  `git show v1.6.1:specs/electra/beacon-chain.md`: v1.6.1 already subtracted the inline
  `total_withdrawn = sum(w.amount ... if w.validator_index == idx)` in **both** the partial-phase
  loop AND the validator-sweep loop. The refactor just extracts that inline sum into
  `get_balance_after_withdrawals` and splits the monolith into two helpers. Limits identical on
  mainnet (partial cap `min(MAX_PENDING_PARTIALS=8, MAX_WITHDRAWALS-1=15)=8`; sweep cap
  `MAX_WITHDRAWALS_PER_PAYLOAD=16`). No consensus change → no spec-drift PR.
- ✅ **Lodestar already in sync** (verified vs `origin/unstable`, read via `git show` — ~/lodestar was
  on a feature branch). `getExpectedWithdrawals` uses a shared `validatorBalanceAfterWithdrawals`
  Map (comment cites `get_balance_after_withdrawals` @ v1.7.0-alpha.0), split into
  `getPendingPartialWithdrawals` + `getValidatorsSweepWithdrawals`. **Substantive correctness check:**
  both phases `.get(idx)` from the map, seed from `state.balances.get(idx)` on first touch, and
  `.set()` the reduced balance after each append (partial: `balance-withdrawableBalance`; sweep full:
  `0`, sweep partial: `balance-partialAmount`). The map is passed in from `getExpectedWithdrawals`, so
  it's **shared across phases** — a validator withdrawn in the partial phase carries its reduced
  balance into the sweep phase, exactly matching `prior_withdrawals + withdrawals` in the spec. This is
  the subtle property preventing double-counting one validator's balance in a single block; Lodestar's
  Map is O(1)/lookup vs the spec's O(n) re-sum, correct and faster. No PR needed.
- Note: full-withdrawal path `.set(idx, 0)` is a nice micro-opt (skips re-derivation; enables the
  `balance === 0` early-skip at sweep L43). Gloas adds parallel builder tracks
  (`getBuilderWithdrawals` / `getBuildersSweepWithdrawals` + `builderBalanceAfterWithdrawals` map) —
  same shape, Nico's active area, not re-audited here.

### 2026-07-31 — phase0 proposer-reorg helpers `is_head_weak`/`is_parent_strong` (#5401 backport) [Lodestar: packages/fork-choice/src/forkChoice/forkChoice.ts:1581,1643]
- Trigger: master churn survey since 2026-07-24. **#5401** (Mikhail Kalinin, merged 2026-07-27, in v1.7.0-alpha.13) **backports the Gloas `is_head_weak`/`is_parent_strong` changes to phase0**, so they now apply to every fork incl. mainnet Electra. Phase0 `get_weight` is now defined as `get_attestation_score(store, node, justified_state) + proposer_boost` (boost only if `proposer_boost_root` is an ancestor). The two reorg helpers were switched off `get_weight` (boost-**inclusive**) onto `get_attestation_score` (boost-**excluded**), and `is_head_weak` additionally adds back the effective balance of any **equivocating** validators in the head-slot committees. Spec note: this makes the output monotonic — more attestations can only flip `True`→`False`, never the reverse. After #5401 the phase0 and gloas bodies are byte-identical **except** the gloas `ForkChoiceNode` carries `payload_status=PAYLOAD_STATUS_PENDING` (measures support for the beacon-block-root regardless of payload status).
- ⚠️ **Lodestar pre-Gloas path has drifted** (verified vs `origin/unstable`, read via `git show` — ~/lodestar was on branch `test/beacon-api-array-compliance-e2e`):
  - `isHeadWeak` (forkChoice.ts:1581): pre-Gloas branch does `return node.weight < reorgThreshold` and **omits the equivocator loop**. Post-#5401 phase0 wants `node.attestationScore` (not `.weight`) **plus** the equivocator-committee weight — which is exactly what the *Gloas* branch a few lines below already does.
  - `isParentStrong` (forkChoice.ts:1643): pre-Gloas branch uses `node.weight`; post-#5401 phase0 wants `node.attestationScore`.
  - Confirmed the semantic gap is real: protoArray.ts:437-438 sets `node.attestationScore += attestationDelta` and `node.weight += attestationDelta + boostDelta`, and line 431-432 comments `old boost = weight - attestationScore`. So `node.weight === node.attestationScore + proposerBoost`, matching the spec's `get_weight` exactly → the pre-Gloas branch genuinely includes proposer boost that the new spec excludes.
- **Clean fix:** since phase0 and gloas logic are now identical (and `getNodeDefaultStatus` already returns the PENDING variant for gloas / FULL pre-gloas, so `node.attestationScore` is already the right per-fork score), the `isForkPostGloas(...)` branch can be **dropped** in both functions — always use `node.attestationScore` + (for head) the equivocator loop. Net: less code, spec-faithful on all forks.
- **Practical impact: low.** (1) In the real `get_proposer_head` flow the proposer runs at slot start *after* `on_tick` clears `proposer_boost_root`, so `weight ≈ attestationScore` in the common case → the boost term is usually 0. (2) Equivocators are extremely rare (Lodestar's own comment: "none in normal operation"). So this is spec-conformance / monotonicity alignment + a simplification, **not** a live mainnet reorg bug. Also a just-merged alpha.13 change (unstable's doc comments still cite alpha.11/alpha.12), so it may land as part of the normal spec-version bump.
- **Impact re-verified (2026-07-31, independent read of `origin/unstable`):** stronger than "usually 0". The caller (`getPreliminaryProposerHead`, forkChoice.ts:~495) has an explicit `isProposerBoostWornOff` early-return **before** `isHeadWeak`/`isParentStrong` are called, so the head provably carries no boost at that point; the parent is ≥2 slots old (`headBlock.slot+1===slot`) so it never holds current-slot boost either. ⇒ `node.weight === node.attestationScore` for both nodes in the real call path → the `get_weight`→`get_attestation_score` switch is a **functional no-op pre-Gloas**. The *only* live behavioral delta is the equivocator add-back in `is_head_weak`, and only when equivocators sit in the head-slot committees (attester-slashed → rare). Pinned spec-tests = `v1.7.0-alpha.12` (spec-tests-version.json), so **no current CI/conformance gap** — the drift only activates at the alpha.13+ bump.
- **Decision:** documented + flagged to Nico (#347); **no autonomous PR.** Fork-choice reorg logic is consensus-sensitive and per workflow needs gpt-advisor/Codex verification before any PR — will open only on Nico's go. Matches the 2026-06-19 proposer-boost-gap and 2026-07-03 builder-constants precedents.

---
*Started: 2026-02-15*
*Last updated: 2026-07-03 — Gloas builder-constants re-verify: 3 stale constants (prefix 0x03→0xB0, deposit-req 256→64, withdrawability-delay 8192→64) all from spec PRs merged same day; documented, flagged to Nico, no autonomous PR (his active area)*
*Last updated: 2026-07-17 — phase0 p2p QUIC-primary re-verify (#5330): Lodestar already in sync (quic default-on, dial-prefers-QUIC, both transports mandatory-by-default), no PR. Note: recent consensus-specs master churn is ~90% Gloas/Heze (ePBS, inclusion lists, builder constants) = Nico's active area, no autonomous PRs there.*
*Last updated: 2026-07-24 — Electra/Capella withdrawal-sweep refactor (get_balance_after_withdrawals + 2-helper split, ExpectedWithdrawals container) re-verify: behavior-preserving vs stable v1.6.1 (both phases already subtracted inline total_withdrawn); Lodestar already in sync via shared validatorBalanceAfterWithdrawals Map threaded through partial+sweep phases. No PR. Recent non-Gloas master activity otherwise = cosmetic pyspec renames (boolean→Boolean, byte→Byte, uint*→Uint*, remove bit) + FCR test-vector generation (#5449) = no settled-fork drift.*
*Last updated: 2026-07-31 — phase0 proposer-reorg helper re-verify (#5401, alpha.13): is_head_weak/is_parent_strong backported from Gloas to phase0 (get_weight→get_attestation_score, boost-excluded + equivocator weight for head). Lodestar pre-Gloas branch drifted (still uses node.weight, no equivocator loop @ forkChoice.ts:1581/1643); Gloas branch already matches. Clean fix = drop the isForkPostGloas branch. Low practical impact (boost cleared by on_tick at proposer time; equivocators rare). Documented, flagged to Nico, no autonomous PR (fork-choice = sensitive).*
*🎉 ALL FORKS COMPLETE (surface read 2026-02-18); now in spot-re-verify mode*
