# Lodestar fork choice dump: goals, past discussions, and what other clients do

Research notes by [@lodekeeper](https://github.com/lodekeeper), 2026-10-10.

Code references are pinned to the commits below. This is requirements research, not an implementation or a live interoperability/benchmark result. Items marked *(inferred)* come from reading code, not from running it. Absence findings apply only to the inspected revisions and interfaces; they are not claims about every possible external tool.

| Repo | Commit |
|---|---|
| ChainSafe/lodestar `unstable` | `b726a05a4` |
| sigp/lighthouse `unstable` | `f31adcef1` |
| OffchainLabs/prysm `develop` | `8b79bf544` |
| Consensys-Incorporated/teku `master` | `8f4cac0af` |
| status-im/nimbus-eth2 `unstable` | `5f7baa634` |
| grandinetech/grandine `develop` | `3b0a5ac45` |
| ethereum/beacon-APIs `master` | `01e99a653` |


Freshness recheck: all seven client/API branches were fetched again before publication. Lighthouse advanced to `2d17c851b` during the research; its analysis remains explicitly pinned to `f31adcef1`. Lighthouse v2 PR [#10215](https://github.com/sigp/lighthouse/pull/10215) was still open on the final recheck.

Chat quotes are from the public Eth R&D Discord archive ([ethereum/eth-rnd-archive](https://github.com/ethereum/eth-rnd-archive/tree/ae3fc7d6)), cited as `#channel YYYY-MM-DD`, and from public GitHub threads. Internal team history was also searched directly; its technical concerns are paraphrased here without private quotations, chat links or operational details.

---

## TL;DR

- **"Fork choice dump" has meant two things in past discussions.** Both can share a versioned format and loader, but need explicit fidelity profiles and state/DB dependencies rather than pretending an API tree is self-contained.
  1. Persisting fork choice across restarts, so the node resumes at its head instead of rebuilding from finalized.
  2. Exporting fork choice for debugging: devnet splits, Gloas PTC and payload-status bugs, post-mortems, visualisation.
- **Lodestar does not persist its fork-choice store and latest-message snapshot today.** It does persist related blocks, envelopes and states; those are not a restored fork-choice view.
  - On restart it boots from the finalized state and builds a one-node proto-array.
  - It deletes the previous run's checkpoint states and re-downloads every unfinalized block from peers.
  - `chain.close()` carries `// TODO: persist fork choice to disk`.
  - Open issues: [#4000](https://github.com/ChainSafe/lodestar/issues/4000) (2022) and [#8592](https://github.com/ChainSafe/lodestar/issues/8592) (2025).
- **What this costs:**
  - The head regresses to finalized on every restart.
  - Catch-up imports can send fcUs for old heads when the head/finalized checkpoint changes and import fcU is enabled. geth's reorg-depth guard (default 32) refuses sufficiently deep rewinds with `-38006 Too deep reorg`.
  - LMD votes, PTC votes, timeliness flags and equivocations are lost or only partly re-derived.
  - Pre-restart orphans can fall outside fork-choice-driven pruning and remain stranded in the hot DB.
- **Other clients:**
  - Only Lighthouse persists a full fork choice snapshot: SSZ + zstd, schema-versioned, including Gloas PTC bits.
  - Teku persists the *inputs* (votes and per-block checkpoints) and rebuilds the proto-array on start.
  - Prysm, Nimbus and Grandine do not persist a full fork-choice/latest-message snapshot; their reconstruction loses gossip-only votes.
- **The inspected debug endpoints do not provide complete per-validator latest messages/balances and applied boost state.** We did not identify a supported standalone import of an externally captured diagnostic dump into these clients' fork-choice test harnesses. This is distinct from Lighthouse's internal persistence decoder/loader and visualization tools that load API dumps.
- **No dedicated `-38006` recovery was identified in the inspected CL source revisions.** Generic RPC-error handling still exists. Catch-up behavior needs its own policy because a missing/rejected snapshot still requires recovery.

---

## 1. Why this came up

After restarting Lodestar nodes paired with geth, the beacon node logged `Too deep reorg` from `engine_forkchoiceUpdatedV3` for about 35 s, then recovered.

**What happens:**
1. On restart the Lodestar head is the finalized block.
2. Range-sync imports send fcU when the selected head root or finalized epoch changes, unless import fcU is disabled or proposer override suppresses it. There is no guard specifically based on sync state or distance to the EL head (`importBlock.ts:394-482`).
3. Those fcUs name blocks 33–62 below geth's current head.
4. geth refuses to rewind a canonical head that far.
   - The guard was added in [go-ethereum#34767](https://github.com/ethereum/go-ethereum/pull/34767), first released in v1.17.3.
   - [#35335](https://github.com/ethereum/go-ethereum/pull/35335) made it configurable via `--engine.maxreorgdepth`, default 32.
   - geth answers with JSON-RPC error `-38006`, as required by [execution-apis#786](https://github.com/ethereum/execution-apis/pull/786).
5. Once range sync climbs to within 32 blocks, geth accepts the fcU. It actually rewinds its head to our catch-up head, then moves forward again with later fcUs *(inferred from geth `eth/catalyst/api.go`)*.

**In the reported run, the refusal was transient; it is not proof that every restart-time EL error is harmless.** It surfaces as a JSON-RPC error (`ErrorJsonRpcResponse` or `HttpRpcError`, depending on geth's HTTP status), can change engine status and logs `Error pushing notifyForkchoiceUpdate()`. At the inspected Lodestar revision, fcU errors do not reach `validateLatestHash`; execution invalidation runs through the `newPayload` path. A reorg-policy refusal is not evidence that the payload itself is invalid.

**The same symptom has shown up before:**
- [#3647](https://github.com/ChainSafe/lodestar/issues/3647) (2022): restarting the beacon node "results in a flood of `error: Error pushing notifyForkchoiceUpdate()`".
- [#3717](https://github.com/ChainSafe/lodestar/issues/3717) (2022): "lodestar's fcU calls 'resets/reverts' the connected EL's head to hundereds of blocks behind".
- [#10005](https://github.com/ChainSafe/lodestar/pull/10005): an orphaned FULL leaf became head, so a stale fcU drew `Too deep reorg` (devnet-9).
- ethrex after restart, which has a 128 cap ("ethrex always unhappy after restart", `#interop 2026-08-06`).
- [#9716](https://github.com/ChainSafe/lodestar/issues/9716) (deep sync) logged the same error. The depth there was a uint64 underflow, i.e. geth's forward-update bug fixed in go-ethereum#35804, not a CL-behind-EL reorg.

A coherent persisted fork choice can avoid the finalized-head regression on a clean restart. It does not guarantee that CL and EL heads still match after downtime, independent EL recovery, or an EL change; reconcile them using normal Engine API semantics.

---

## 2. Goals: what past discussions wanted the dump for

Only goals with evidence are listed. Quotes are trimmed.

### G1. Resume at the head after a restart, not at finalized
- dapplion, [#4000](https://github.com/ChainSafe/lodestar/issues/4000) (2022): persist fork-choice state on shutdown and/or periodically, then restore it to avoid regressing the head (paraphrased).
- twoeths, [#8592](https://github.com/ChainSafe/lodestar/issues/8592) (2025): restarting from the finalized head puts the node behind its EL and peers; points to Lighthouse's `persist_fork_choice` / `load_fork_choice` (paraphrased).
- g11tech, `#interop 2022-06-30`: "each time lodestar starts it starts from the last finalized … we don't persist our forkChoice (yet)".
- #4000 also asks to evaluate the approach during prolonged non-finality. That is when the restart regression is largest *(inferred)*.

### G2. Keep track of orphans across restarts so they get pruned (hot-DB leak)
- nflaig, [#10206](https://github.com/ChainSafe/lodestar/pull/10206) (closed in favour of persistence): persist and restore fork choice to retain orphaned payload/block tracking for pruning (paraphrased).
- On #8592 he noted 17 stranded hot envelopes on glamsterdam-devnet-8 and the need to handle unclean shutdowns when fork choice has not been saved (paraphrased).

### G3. Live debugging of network splits: fork choice, or visibility?
- nflaig, `#interop 2026-06-08` (glamsterdam-devnet-5, up to 13 forks): collect dumps to distinguish fork-choice disagreement from lack of visibility of competing branches (paraphrased).
- nflaig, v2 endpoint thread `2026-10-07`: "I remember in holesky, this endpoint was very important for us".
- potuz, `#interop 2025-02-25` (Holesky): "can you give me a forkchoice dump?"
- paulhauner, `#interop 2022-08-11`: "I dumped the fork choice struct from a LH node about 10s before the merge transition block finalized and analyzed it."
- More of the same in the Goerli incidents of 2023-01 and 2023-03.

### G4. Gloas/ePBS debugging: payload status, PTC votes, `should_build_on_full`
Fork choice nodes are `(block_root, payload_status)` under Gloas, and the v1 endpoint cannot show them.
- `#epbs 2026-05-29` (Lodestar built on EMPTY at slot 22912).
  - nflaig read the weights from fork choice (`EMPTY=9504`, `FULL=15968`). They showed FULL was heavier, which pointed at `should_build_on_full`.
  - potuz asked for the PTC votes: "do you have a forkchoice dump that includes them? have the API people even agreed on a format for the forkchoice dump?" No dump carried PTC votes.
  - The root cause, a missing slot check in `notify_ptc_messages`, was found hours later from the PTC votes included in a later block.
- nflaig, `#interop 2026-06-05` (slot 7218 payload reorg):
  - Logs did not record every received PTC attestation, so reconstructing the earlier view was painful; asked for persisted v2 captures or client-internal retention (paraphrased).
- nflaig, `#interop 2026-06-10`: "I love the new v2 fork choice api, finally can see ptc votes".
- potuz, `#epbs 2026-03-04`: "how to see the full picture without Dora and the forkchoice dump endpoint".

### G5. Historical capture for post-mortems
The state is gone after a restart, and logs don't hold enough to rebuild it.
- potuz, `#consensus-dev 2025-12-19`: "Forkchoice dumps have been incredibly helpful diagnosing bugs."
- potuz, `#uncategorized 2024-08-14`: "You still have forkchoice dumps taken regularly right?"
- potuz and parithosh, `#interop 2023-03-13`: dumps were missing for the clients that mattered.
- terencechain and potuz, `#interop 2026-05-16`, about capturing before a restart:
  - terencechain: "that's why I'm hesitant to restart prysm nodes".
  - potuz: "I dumped logs and forkchoice dumps now, you can kill the node".
- etan_status, `#cl-testing 2022-10-27`: periodically poll and save the dump during a long-split test.
- Forky keeps fork choice snapshots of some ethpandaops nodes ([go-eth2-client#61](https://github.com/ethpandaops/go-eth2-client/pull/61)).
- potuz asked about Xatu retention on 2026-06-05; parithosh was unsure about current Forky coverage the next morning (paraphrased).

### G6. Visualisation and cross-client comparison through a common format
- tbenr's [protovis](https://tbenr.github.io/protovis/) loads dumps and follows live nodes. It was the origin of the standard endpoint ([beacon-APIs#231](https://github.com/ethereum/beacon-APIs/issues/231)).
- Forky consumes the standard endpoint.
- twoeths, [#5144](https://github.com/ChainSafe/lodestar/pull/5144) (Lodestar's `/eth/v0/debug/forkchoice`): "dump all proto nodes to know the current status of forkchoice to compare to other nodes/clients".
- nflaig on [#10191](https://github.com/ChainSafe/lodestar/pull/10191), on who consumes it: "manual curl users, claude using curl or other tools, or forky and similar tooling".
- Dissent, potuz, `#apis` v2 thread 2026-09-30: "an endpoint that absolutely no one uses ever, ever, ever, not even the pandaOps guys and forky". That argues for keeping the standard endpoint lean and putting the depth in a client-side dump.

### G7. Fork alerting
- potuz, `#tooling 2022-08-26`: Prysm merged its endpoint "to start getting emails when there are forks".

### G8. Invalid-branch forensics
- etan_status, `#interop 2025-03-14` (Holesky): filtered `validity=="INVALID"` out of a dump to pull those blocks from the DB.
- tbenr, `#interop 2025-01-21`: used Teku's dump to contradict an EL's `latestValidHash`.

### Historical constraints reinforced by internal discussions
The recovered 2025–2026 team discussions also raised: a dump needs a usable unfinalized state and hot blocks; it cannot help a brand-new node with no previous head; shutdown-only capture misses OOM/crash cases; a stale view must not lock a node onto the wrong branch; and asynchronous DB writes must not leave a snapshot ahead of durable blocks. Losing the last crash-window updates is different from booting into an incoherent state. These concerns are requirements below, not claims that persistence solves community recovery during non-finality.

### G9. A binary representation was discussed, not agreed
SSZ encoding of dumps was raised in `#apis 2026-06-01` and `#epbs 2025-09-26`; enum/optional representations were a concern. A client-side versioned binary format is an engineering choice, not a requirement to turn consensus-spec fork-choice internals into SSZ containers.

### Not evidenced, proposed here: dump → reproducible test
No retrieved chat explicitly asks to turn a dump into an offline repro. A loader would support G3–G5, but a snapshot alone reproduces a decision at a captured point, not necessarily the sequence of events that caused a bug. Timing/import bugs may additionally need an ordered event trace, block/state/envelope bundle and configuration (see R8). No supported standalone diagnostic-dump-to-test importer was identified in the inspected client interfaces.

---

## 3. Requirements

| # | Requirement | Source |
|---|---|---|
| R1 | **Decision fidelity:** enough to recompute the same head at the captured logical time. Include all nodes (Gloas variants), latest messages, equivocations, realized/unrealized checkpoints, PTC bits, execution/DA status, timeliness and applied proposer-boost semantics. Preserve/rebuild **both justified and unrealized-justified balances**, with required seed-state references. Queued attestations and FCR are needed for a full diagnostic capture; a reduced restart profile must declare/reset omitted state explicitly. | G1–G5; Lighthouse #7805; Lodestar store/onTick |
| R2 | **A restart checkpoint is never ahead of the DB.** Its block-backed nodes must resolve to durable hot/archived blocks or the validated anchor, and Gloas FULL nodes require their envelopes. Today `close()` *drops* pending hot-DB writes, so restart persistence must flush dependencies first. Validate on load and use coherent fallback on mismatch. An **incident diagnostic capture must still be possible when DB consistency is broken**, with missing dependencies explicitly recorded; it is not automatically eligible for production restore. | Lighthouse #2028, #9818/#9819; Teku #3124 |
| R3 | **Unclean shutdowns:** publish a coherent committed generation atomically; preserve the previous good generation on partial writes. Define the tolerated crash window and fallback. Periodic snapshots reduce data loss but do not remove it. **Reconcile hot-DB blocks/envelopes absent from the last snapshot**, or crash-tail orphans remain stranded even with an fcU guard. | G2; nflaig on #8592; internal write-consistency discussions |
| R4 | **Versioned and migratable format.** | Lighthouse #1833 (decode failure on upgrade) |
| R5 | **Cheap.** Off the block-import critical path, compressible. Size is dominated by votes, roughly 8–12 MB per 1M registry entries uncompressed. | Lighthouse #2547, #7760 |
| R6 | **Opt-out / reset.** Restart-from-finalized is a known recovery path for buggy ELs. | wemeetagain and g11tech on #4000; etan_status `#interop 2025-03-14` |
| R7 | **Two debug tiers.** The standard v2 endpoint for cross-client tools, plus a full internal dump (votes, balances, boost, equivocations, PTC bits) not provided in full by the inspected diagnostic endpoints. Serve both from memory, with no per-node DB reads. | G3–G6; Nimbus #5328 (endpoint polled every slot) |
| R8 | **Loadable and honest about coverage.** Provide inspect/head tools and a test loader. Same-time round-trip reproduces `getHead()` and weights. To reproduce an incident's event sequence, attach ordered events and needed blocks/envelopes/states; don't claim an API tree alone can replay it. | proposed extension of G3–G5 |
| R9 | **Not a DoS vector.** Use the admin namespace, write server-side like `write_heapdump`, or keep it behind the debug API. | potuz, v2 thread: "the endpoint may be dossing" |
| R10 | **Keep standard v2 lean.** Don't add storage or computation to the standard endpoint just for the API. Rich fields go to `extra_data` or the internal dump. | ajsutton `#tooling 2022-08-26`; potuz and tbenr, `#apis` v2 thread 2026-10-07 |
| R11 | **Freshness and trust:** check network/genesis identity, preset/config fingerprint, schema/fork compatibility, finalized ancestry and referenced data. Keep existing weak-subjectivity and execution/DA checks. Tick to current time, then accept new votes/blocks normally. A saved head hint cannot override fork-choice validity or force a branch. | G1; stale-view/cold-start concerns in internal history |
| R12 | **Capture one coherent instant.** Node indices, vote arrays, boost and pruning generation must refer to the same view while imports/ticks/pruning continue. Do expensive encoding/compression/I/O after a bounded consistent capture, not while blocking duties. | proposed implementation constraint for R1/R2/R5 |
| R13 | **Historical collection is separate from restart persistence.** Support timestamped/reorg-triggered captures and bounded retention; a single overwritten restart file cannot reconstruct yesterday's split. Include capture reason/time, client revision, network and head/checkpoints. | G3–G7 |
| R14 | **Bounded recovery and visibility:** report snapshot age, restore/fallback reason, write/restore duration and artifact size. Reject malformed/oversized inputs within bounds; do not silently claim success. Benchmark long non-finality as well as routine finality before choosing cadence. | G1/G5; proposed operational criteria |

### 3.1 Fidelity profiles

- **Standard diagnostic view:** beacon-APIs v2 for topology and cross-client comparison; not a restart image.
- **Internal diagnostic capture:** includes raw and derived decision state, queues and enabled optional rules at one logical instant. Can inspect/reproduce that view without mutating a running node. Full incident replay additionally needs external inputs.
- **Restart checkpoint:** keeps sufficient durable inputs to rebuild a valid current view. It may omit derivable weights/caches and discard deliberately non-durable queues, but must describe those limits. Node startup also needs DB blocks/envelopes and a usable state seed.

Sharing a container/decoder between the last two profiles is useful; claiming identical fidelity without storing all their dependencies is not.

Capture also distinguishes the **raw applied view** from a **normalized view after applying pending latest-message deltas**. Diagnostic capture should retain raw scores/current and next votes/applied boost (or explicitly declare only a normalized view). Rebuilding zeroed weights from next votes can change pre-update raw scores; it must not be presented as exact restoration of the applied view.

### 3.2 Acceptance criteria (proposed, not tests already run)

| Scenario | Required observable result |
|---|---|
| Same-time round trip, pre-Gloas and Gloas | With the same configuration and logical time, the diagnostic loader returns the same `(root, payloadStatus)`, branch weights, checkpoints, equivocations, boost behavior and PTC decisions. Explicitly test EMPTY/FULL siblings, non-adjacent FULL indices and equivocations. |
| Graceful restart | After flushing durable dependencies and committing the snapshot, reopen without peer re-download of already stored blocks; recover a usable head state and reconcile with the EL. A saved head need not stay head after elapsed time or new inputs. |
| Crash at each write boundary | Kill before/during/after block, envelope, state and snapshot writes. Select the last complete generation or coherent fallback; never reference missing durable inputs or mark rejected restore as success. |
| Crash-tail orphan cleanup | Add canonical and orphaned blocks/envelopes after the last committed snapshot, crash, restart, then finalize. Recover/reconcile and eventually prune all eligible orphans, including ones absent from the snapshot. |
| Long non-finality | Restart with an unfinalized interval longer than the current 5-epoch regeneration bound and many branches. Preserve enough seed-state data to obtain a usable head state; record startup time, capture/write cost and disk growth. |
| Stale or incompatible artifact | Test wrong network/preset/config, future slot, unknown schema, truncated file, missing state/envelope and inconsistent finalized ancestry. Explicit rejection/fallback; no bypass of chain safety or WS policy. |
| Clock catch-up | Tick across slot/epoch boundaries: expire proposer boost, apply queued messages/pull-ups correctly, preserve realized/unrealized balances, and rebuild or explicitly reset optional FCR. |
| EL policy refusal | Test `-38006`, a transport error and a genuinely invalid payload separately. Do not invalidate a branch on a reorg-policy RPC error; preserve required EL validation/sync progress during fallback catch-up. |
| Concurrent capture/prune | Capture around node pruning, vote-array growth, head changes and finalization. All root/index references belong to one generation; derived scores are not double-applied. |
| Useful post-mortem | Capture both sides of a split at comparable times; distinguish known-but-losing branches from absent branches. Absence from fork choice alone does **not** prove a block was never received: correlate import/validation/peer evidence. |
| APIs and tooling | A standard-v2 consumer can visualize variants; the internal inspect/head loader consumes the declared profile. Unsupported fields are marked unavailable, not silently synthesized as exact history. |
| Mainnet-scale cost | Measure registry length, encoded/compressed size, capture pause, write duration and startup cost under normal and non-finality conditions. Choose limits/cadence from measured results; no latency target is asserted here. |

### 3.3 Non-goals and rollout boundary

This is not first-time checkpoint sync, an alternative to weak subjectivity, arbitrary unfinalized-state trust, forced/manual finalization, or a guarantee that CL and EL never diverge. It does not replace the standard endpoint with a private format, establish that every historical bug has an offline replay, or commit the feature to v1.50. Persistence/recovery and richer diagnostics can be delivered separately against the criteria above.

---

## 4. Lodestar today

### 4.1 Restart path
- **Anchor:** `initBeaconState` loads the latest archived state.
  - On graceful shutdown, `archiveStore.persistToDisk()` writes the *finalized* checkpoint state.
  - After a crash, the anchor is the last periodically archived finalized state, up to about 32 epochs old *(inferred)*.
- **Fork choice:** `initializeForkChoice` builds a **single-node** proto-array from the anchor (`chain/forkChoice/index.ts:131-170`).
  - The node gets `executionStatus: Syncing` and timeliness flags set optimistically to `true`.
  - Gloas: `PENDING`.
- **Votes:** the `ForkChoice` constructor already says it is "useful if the existing components have been loaded from disk after a process restart". But votes are always initialized empty (`forkChoice.ts:182-187`).
- **Checkpoint states are wiped at boot:** "all checkpoint states from the last run are not trusted, remove them" (`persistentCheckpointsCache.ts:215-228`). The code comment says this was found on the mekong devnet.
- **Hot-DB blocks are not replayed.** Range sync re-downloads everything above finalized from peers. Nothing under `sync/` reads the DB.
- **Escape hatch:** `--lastPersistedCheckpointState` (hidden, [#8527](https://github.com/ChainSafe/lodestar/pull/8527)) starts from an unfinalized checkpoint state. It still doesn't restore fork choice.

### 4.2 What a restart loses

| Item | After restart |
|---|---|
| Unfinalized nodes | Rebuilt by re-importing blocks from peers |
| Unrealized checkpoints per node | Re-derived on re-import |
| `timeliness` / `ptcTimeliness` / `importedTimely` | **Lost.** Re-imported blocks are late by definition |
| LMD votes | **Partially** re-derived, only from attestations in re-imported blocks (`FORK_CHOICE_ATT_EPOCH_LIMIT = 1`). Gossip votes are lost, and gossip is off until synced |
| Equivocating indices | Partially re-derived from slashings in recent blocks. The op pool restores slashings but does not feed fork choice |
| PTC votes (Gloas) | Partially re-derived from `payloadAttestations` in re-imported blocks |
| Gloas FULL variants | Re-created as envelopes are re-downloaded |
| Execution status | Anchor `Syncing`; blocks are re-sent via `newPayload` |
| FCR store | Reset to finalized |
| Orphans from before the restart | Can become unknown to fork choice and escape its hot-DB pruning |

### 4.3 Debug surfaces
- **`GET /eth/v1/debug/fork_choice`:** deprecated by the spec.
- **`GET /eth/v2/debug/fork_choice`:** spec-aligned in [#10191](https://github.com/ChainSafe/lodestar/pull/10191). [#10297](https://github.com/ChainSafe/lodestar/pull/10297) adds `attestation_score`, `state_root` and the unrealized roots.
  - Per node: `(root, payload_status)` nodes with `parent_payload_status`, PTC counts, and `extra_data` (`attestationScore`, `executionOptimistic`, `stateRoot`, `target`, unrealized checkpoints).
  - Top-level `extra_data`: head `{root, payload_status}`, proposer boost roots and unrealized checkpoints.
- **`GET /eth/v0/debug/forkchoice`:** Lodestar-only raw proto nodes from [#5144](https://github.com/ChainSafe/lodestar/pull/5144). No Gloas fields.
- **Not exposed anywhere:** votes, balances, equivocating indices, queued attestations, PTC bitvectors, `ptcTimeliness`/`importedTimely`.
- **No standalone diagnostic-dump loader was identified** at this revision; there is no production fork-choice snapshot restore path.
- **Useful precedents:**
  - `POST /eth/v1/lodestar/write_heapdump`: writes server-side and returns the path.
  - `GET /eth/v1/lodestar/persisted_checkpoint_state`: streams SSZ.
  - `chain.persistSszObject`: debug SSZ files.
  - [#10327](https://github.com/ChainSafe/lodestar/pull/10327): proposer preferences use the `persistToDisk` / `loadFromDisk` pattern.

### 4.4 In-memory state a full dump needs
- **`ProtoArray`:** `nodes[]`, with indices derivable.
  - Identity: slot and roots.
  - FFG and unrealized checkpoints.
  - Timeliness flags.
  - Execution: hash, number, gas limit and status.
  - `dataAvailabilityStatus`.
  - Gloas: `payloadStatus` and `parentBlockHash`.
  - Weights.
- **Proto-array scalars:** `justified`/`finalized`, `previousProposerBoost`, `proposerBoostRoot`.
- **Gloas PTC bitvectors:** `payloadTimelinessVotes`, `payloadDataAvailabilityVotes`, `ptcAttested`. Their size is `PTC_SIZE` from the preset (512 mainnet, 2 minimal).
- **`ForkChoice`:** `voteCurrentIndices`, `voteNextIndices`, `voteNextSlots`, `balances`, `queuedAttestations`.
  - Votes are stored as **node indices**, which shift on `prune()`. A dump must store them as `(root, payloadStatus)` or together with the node table.
- **`ForkChoiceStore`:**
  - Justified checkpoint and balances.
  - Unrealized justified checkpoint **and its balances**, plus unrealized finalized checkpoint.
  - `equivocatingIndices`.
  - `currentSlot`.
  - FCR fields, when enabled.
- **The restore-friendly subset:**
  - **Restart profile:** nodes *without* weights, `voteNextIndices` and `voteNextSlots`, equivocations, checkpoints, PTC bits, and realized/unrealized-justified balance dependencies (unless their seed states are kept, see §7).
  - **Restore with:** weights = 0, `voteCurrentIndices = NULL`, no previous boost. The first `updateHead()` then recomputes all weights from scratch.
  - This is smaller and less fragile than restoring weights, `voteCurrentIndices`, old balances and baked-in boost consistently, but is a normalized-input rebuild proposal, **not experimentally verified here**. The full diagnostic profile retains those applied fields for exact inspection. Lighthouse had to subtract a baked-in boost in a schema migration.
- **Size:** votes cost about 8–12 B per registry entry (next node index + next slot, depending on slot width), so about 8–12 MB per 1M. Nodes and PTC bits are under 1 MB even with 200 unfinalized Gloas blocks. Vote arrays are highly repetitive and should compress very well *(not measured)*.

---

## 5. Other clients

### Lighthouse: full snapshot
- **Format:** one compressed SSZ blob (`PersistedForkChoiceV29`, zstd) in the hot DB.
  - Holds the proto-array nodes (incl. per-node unrealized checkpoints, execution status and Gloas fields: payload weights, `payload_timeliness_votes`, `payload_data_availability_votes`, `ptc_participation`).
  - Holds the votes (`VoteTracker{current_root, next_root, current_slot, next_slot, *_payload_present}`).
  - Holds store time and checkpoints, `proposer_boost_root`, and equivocating indices.
- **Not stored:** balances (recomputed from the justified state since #7805, which saved ~65 MB + ~16 MB on mainnet), queued attestations (V29), and the children index.
- **When written:** on epoch-boundary head change, on reorg, at finalization (**before** the migrator prunes, #10165), and on shutdown. Never per block.
- **Never persisted while poisoned.** A failed block DB write poisons fork choice and shuts down (#9818/#9819). For blocks, the persisted copy can lag the DB but never leads it. The Gloas envelope import path doesn't poison yet (`TODO(gloas)`, open #9978).
- **Restore:** load, tick slot by slot from the persisted time to now, `get_head`.
  - If any node is INVALID, or with `--reset-payload-statuses`, all payload statuses are reset to optimistic (#3498).
  - There is no rebuild-from-finalized fallback: `fork_revert.rs` was deleted as "dysfunctional" in #8891.
- **Startup fcU:** sent once, right after the head is restored.
- **Dumps:**
  - `/lighthouse/proto_array`: the full internal array as JSON, without votes, balances or store.
  - `lighthouse db inspect --column frk`: exports the raw blob. Lighthouse internally decodes it on startup; a supported standalone inspect/replay importer for externally captured diagnostic dumps was not identified.
  - v2 endpoint: open PR #10215.
- **Lessons from their history:**
  - #1833: a format change without a migration failed to decode.
  - #7760: the blob is big and grows during non-finality.
  - #10089: an epoch→slot vote migration let old attestations roll back latest messages (won't fix).

### Teku: persist inputs, rebuild
- **What is persisted:**
  - Hot blocks.
  - Per-block realized **and unrealized** checkpoints.
  - One `VoteTracker` per validator. Writes are batched asynchronously; "it's not an issue if the last batch isn't written" (#5903).
  - Store checkpoints, plus a `LATEST_CANONICAL_BLOCK_ROOT` hint written once per epoch.
- **Snapshots were tried and dropped.** The proto-array snapshot was added for slow startup (#2160 → #2270) and removed because it drifted from the blocks (#3124). The schema still says "7 was the protoarray snapshot variable but is no longer used."
- **Restore:**
  - Deserialize every hot block and rebuild the proto-array. Every post-merge node comes back OPTIMISTIC.
  - Apply the stored votes.
  - Add +1 weight along the canonical hint. Without the hint, a Holesky restart with all-zero weights across 815 leaves picked a head ~4 days old (#9198 → #9203).
- **Startup fcU:** after the first `processHead`.
- **Gloas:** PTC votes are not persisted and not rebuilt. FULL nodes are rebuilt only if a blinded envelope is stored.
- **Dumps:** v1 and v2. The custom `/teku/v1/debug/beacon/protoarray` was removed in favour of the standard endpoint (#6599). `debug-tools db` offers `get-variables`, `dump-hot-blocks` and `delete-hot-blocks`.

### Prysm: no fork-choice snapshot, one chain rebuilt
- **Persisted:** only the head root and justified/finalized/last-validated checkpoints.
- **Restore:**
  - Build **one chain** from the justified root (default, `--sync-from` overrides) back to finalized.
  - No attestation replay. Every node gets the store's checkpoints (#10777). Nodes start optimistic.
- **Lost:** votes, boost and PTC bits. Init sync re-executes blocks above the restored head.
- **Gloas FULL nodes:** re-derived by comparing consecutive bids.
- **Startup fcU:** none until regular sync. Post-Gloas: one per sync batch (#17273 documented an EL starved with zero fcUs).
- **Dumps:** v1 and v2 are on by default (`--disable-debug-rpc-endpoints`). v2 is still the pre-spec shape (#16862; alignment in open #17636). It has PTC counts, not votes or balances.

### Nimbus: no fork-choice snapshot, replay all heads
- **Persisted:** block summaries plus `kHeadBlocks`, a list of all DAG heads (#8590).
- **Restore:**
  - Replay the unfinalized blocks of **every** head through fork choice. Full processing applies within 256 blocks of a head; older blocks take a cheap path.
  - Votes come only from attestations in replayed blocks.
  - Unrealized checkpoints are computed only for the head.
- **Gloas:** FULL variants of already-imported blocks are not re-created *(inferred)*.
- **Startup fcU:** none until the first block import.
- **Dumps:**
  - v1 only, and it loads a block from the DB **per node per request**. On a 2023 devnet the endpoint was polled every slot (#5328).
  - Under Gloas it emits duplicate `block_root` rows.

### Grandine: no fork-choice snapshot, re-import canonical chain
- **Persisted:** unfinalized blocks are written **only on clean shutdown**, and only for the canonical chain. A crash loses all of them.
- **Restore:** the store is rebuilt from the anchor by re-importing blocks with signature checks skipped.
- **Votes:** come only from blocks.
- **Payload validity:** "There is currently no way to persist payload statuses", so they store only valid blocks.
- **Gloas:** restart replay stalls on FULL parents (#886; fix in open PR #887).
- **Startup fcU:** replay emits one fcU per block from near the anchor.
- **Dumps:** v1 only, with no `extra_data` and without the anchor node.

### Comparison

| | Lighthouse | Teku | Prysm | Nimbus | Grandine | **Lodestar** |
|---|---|---|---|---|---|---|
| Fork choice persisted | full snapshot | inputs (votes, per-block checkpoints, canonical hint) | no | no (all-heads list) | no | **no** |
| Restore | load + tick + get_head | rebuild from hot blocks + votes | one chain to justified | replay all heads | re-import canonical chain | **re-sync from peers** |
| Votes after restart | kept | kept (last batch may drop) | lost | from blocks | from blocks | from blocks |
| Validity after restart | kept (reset if any invalid) | all optimistic | optimistic | not validated | optimistic (DB holds only valid blocks) | syncing |
| Gloas PTC votes kept | **yes** | no | no | no | from blocks | from blocks |
| Startup fcU | after restore | after restore | none | none | per replayed block | per imported block |
| Dedicated `-38006` recovery identified | no | no | no | no | no | **no** |
| v2 endpoint | open PR (#10215) | yes | pre-spec shape (#17636 open) | no | no | **yes** |
| Votes / per-validator balances over HTTP | no | no | no | no | no | no |
| Standalone diagnostic dump → fork-choice test importer identified | no (internal persistence loader exists) | no (internal rebuild exists) | no | no | no | no |

---

## 6. Ideas worth taking, and pitfalls

**Take:**
1. **Persist on epoch boundary, reorg, finalization (before prune) and shutdown, not per block** (Lighthouse). Write off the import path.
2. **Version the format explicitly** with step migrations (Lighthouse superstruct). Teku's lighter alternative: keep writing the old layout until the fork activates, so downgrade still works.
3. **Avoid duplicating balances when the referenced states are durably available.** Recompute from the appropriate justified/unrealized-justified states (Lighthouse #7805). Otherwise preserve the vectors explicitly; Lodestar's current checkpoint-state deletion makes omission unsafe.
4. **Persist only what's needed to recompute, not derived weights.** Teku dropped snapshots over drift. Lighthouse had to strip a baked-in boost in a migration.
5. **Treat the dump as a cache validated against the DB.** Never write one that's ahead of the DB (Lighthouse poisoning). If validation fails, fall back to today's path instead of refusing to start (Prysm's "delete your DB" era: #15468, #12367).
6. **Tick slot by slot from the dumped time to now on load**, so pull-ups and boost resets happen as they would live (Lighthouse).
7. **Store a canonical-head hint and the list of heads** (Teku #9203, Nimbus #8590). They are cheap and fix the zero-weight tie-break problem when votes are missing.
8. **Provide recovery knobs:** ignore or reset the persisted fork choice; reset payload statuses (Lighthouse `--reset-payload-statuses`); invalidate a root at startup (Nimbus `--debug-invalidate-block-root`).
9. **Expose two dump tiers.** Standard v2 plus a full internal dump. Share a container/decoder with the restart file but declare profile/fidelity differences and dependencies (§3.1).
10. **Ship supported inspect/head/test-loader tooling.** Internal persistence loaders and visualizers exist, but the surveyed diagnostic interfaces lack a complete fork-choice replay bundle. A captured state can reproduce a decision, not automatically the event sequence that caused it.

**Avoid:**
- Format changes without a migration (Lighthouse #1833).
- Persisting a finalized checkpoint below what the archiver already pruned. Lighthouse #10142 caused a startup loop; the fix was to persist before migrating.
- Restarting with all-zero weights and no tie-break hint (Teku #9198).
- Slow startup from regenerating states at init (Teku #2160) or replaying under long non-finality (Nimbus #1910, #8578). Teku still deserializes every hot block on start.
- Writing unfinalized data only on clean shutdown (Grandine). Lodestar's `close()` currently *drops* pending hot writes, which is the same class of problem.
- Gloas restart gaps: FULL variants or envelopes not restored (Grandine #886, Prysm #17497, Nimbus *(inferred)*), and PTC votes lost.
- Recovery code that rots (Lighthouse `fork_revert`, #8891).

---

## 7. Strawman for Lodestar (for discussion, not decided)

**Artifact.** One versioned SSZ container, snappy- or zstd-compressed:
```
ForkChoiceDumpV1 {
  version, profile, fork, createdAtSlot, capturedAt, genesisValidatorsRoot
  preset, configDigest, clientRevision, enabledOptions, generation
  store:  { currentSlot,
            justified: {checkpoint, balancesOrStateRef},
            unrealizedJustified: {checkpoint, balancesOrStateRef},
            finalized, unrealizedFinalized,
            proposerBoostRoot, equivocatingIndices: List[ValidatorIndex] }
  nodes:  List[ProtoNodeDump]       # restart: omit derived weights/links; diagnostic: retain raw scores
  ptc:    List[{blockRoot, timeliness: Bits[PTC_SIZE], dataAvailability: Bits[PTC_SIZE], attested: Bits[PTC_SIZE]}]
  votes:  { nodeIndex: List[uint32], slot: List[uint64] }  # index into `nodes` of this dump, NULL=0xffffffff
  heads:  List[{root, payloadStatus}], canonicalHead: {root, payloadStatus}  # advisory hint only
  seedStates: List[{root, slot, durableReference}]  # or attached state bytes in an offline bundle
  diagnostic: {appliedVotes, appliedBalances, previousBoost, queuedAttestations, optionalFcrState}
  dependencies: {blocks, fullEnvelopes, states, missingDependencies}
}
```

This is a conceptual container, not a decided SSZ schema; optional fields/profile tags and preset-dependent bitvectors need concrete encoding. The diagnostic section is present for the full profile. Restart omits it only with explicit reset/rebuild semantics. FCR can require additional implementation-specific context beyond the small store fields; unsupported optional state must not silently masquerade as a complete reproduction.

**Writing.**
- `persistToDisk()` on shutdown, *after* flushing `unfinalizedBlockWrites` and `unfinalizedPayloadEnvelopeWrites` (today they are dropped).
- Optionally every epoch and at finalization, before archive pruning, to narrow the crash window.
- Capture a consistent generation, commit dependencies before an atomic snapshot replacement/DB transaction, and retain the last good generation on failure. Snapshot writes and pruning must be coordinated.
- On demand: `POST /eth/v1/lodestar/write_fork_choice_dump?dirpath=` returns the file path, modelled on `write_heapdump`. This covers G3–G5 without serving tens of MB over HTTP.
- Keep timestamped diagnostic history separately with bounded retention. Annotate unavailable DB dependencies rather than refusing to capture a broken live state.

**Loading.** At startup, if a dump exists, restore from it only when all of these hold:
- its network/preset/config/fork/schema is compatible and its captured time is plausible;
- its finalized/anchor ancestry and generation agree with the durable DB view;
- every referenced block/state and required FULL envelope resolves in the appropriate hot/archived store or anchor representation;
- no index, payload-variant or balance dependency is missing or inconsistent.

For the proposed reduced restart profile, initialize weights to 0, `voteCurrentIndices = NULL` and previous boost to null; rebuild the normalized view, then apply the documented tick-to-now/head-update ordering. Verify that ordering against epoch pull-ups and optional rules before implementation. On failure, log why and select a coherent fallback. **Diagnostic inspection instead stays at the captured time** and preserves/labels raw versus normalized scores.

**Crash-tail/orphan reconciliation remains necessary.** Recover or index durable blocks/envelopes written after the selected generation, or use finalization-time GC independent of the restored DAG to discover eligible orphan records. Snapshot persistence alone does not choose or implement that strategy.

**Open dependency: a seed state for the restored head.**
- Regen can replay at most 5 epochs of hot blocks from the finalized anchor (`MAX_EPOCH_TO_PROCESS`).
- Beyond that it needs persisted checkpoint states, which are currently deleted at boot.
- The dump could pin one trusted checkpoint state, or keep the newest one it references.
- It also needs both realized and unrealized-justified balance vectors, or the exact compatible states needed to rebuild them. A head seed state alone is not automatically both of those states.

**Flags.** Persistence on by default. Add `--chain.ignorePersistedForkChoice` (or similar) for the recovery path from #4000.

**Loader for tests.** `ForkChoice.fromDump(...)` used by a CLI (`lodestar dev fork-choice-dump inspect|head <file>`) and by unit tests, with explicit captured-time versus advance-to-now modes. Optionally export a full input bundle to the consensus-specs fork-choice test format. Synthesized attestations are not guaranteed to reconstruct PTC history, ordering, equivocations or implementation-only state; label approximation rather than claiming a lossless conversion.

**Independent of the dump: an fcU guard during catch-up.** Missing or rejected snapshots can still require finalized fallback. Today the only knob is the global `--chain.disableImportExecutionFcU`. Two options:
- Skip or limit fcU while range sync is behind and the EL is known to be ahead (`fromRangeSync` is already passed to import but never read).
- Send a single fcU once within a few slots of the clock.

Also, if [#9332](https://github.com/ChainSafe/lodestar/pull/9332) (fcU INVALID → invalidate) lands, it must not treat reorg-depth refusals as INVALID.
- geth sends a `-38006` error, so that is safe.
- But an EL encoding the refusal as an `INVALID` status would invalidate a valid head. Lighthouse, Teku, Nimbus and Prysm all have this exposure *(inferred)*.

### Open questions
1. **Snapshot vs inputs.**
   - Full snapshot (Lighthouse): simple restore, drift risk.
   - Inputs + rebuild from hot blocks (Teku): avoids persisting an independent proto-array snapshot, but startup is slower and needs every hot block deserialized.
   - The strawman sits in between: it stores votes and node metadata, not weights.
2. **Write cadence vs crash window.** Is shutdown + finalization enough, or every epoch? What does a write cost at mainnet scale?
3. **Checkpoint states:** stop wiping them at boot when a valid dump references them, or pin one in the dump?
4. **Should timeliness flags be restored as-is?** That would let a pre-restart late block keep `timeliness = false` instead of being re-judged.
5. **Should the internal dump be served over HTTP at all,** or only written server-side?
6. **Do we want an SSZ form of the standard v2 dump?** It is blocked on enum/optional SSZ types (`#apis 2026-06-01`). Probably not needed if the internal dump is SSZ.

---

## 8. Sources

### Direct implementation evidence (pinned)

- **Lodestar:** [restart initialization](https://github.com/ChainSafe/lodestar/blob/b726a05a4df34068d21b254bf5c590ea75afd169/packages/beacon-node/src/chain/forkChoice/index.ts#L131), [shutdown write handling](https://github.com/ChainSafe/lodestar/blob/b726a05a4df34068d21b254bf5c590ea75afd169/packages/beacon-node/src/chain/chain.ts#L563), [store/balance dependencies](https://github.com/ChainSafe/lodestar/blob/b726a05a4df34068d21b254bf5c590ea75afd169/packages/fork-choice/src/forkChoice/store.ts#L44), [unrealized balance pull-up](https://github.com/ChainSafe/lodestar/blob/b726a05a4df34068d21b254bf5c590ea75afd169/packages/fork-choice/src/forkChoice/forkChoice.ts#L2263), [fcU gating](https://github.com/ChainSafe/lodestar/blob/b726a05a4df34068d21b254bf5c590ea75afd169/packages/beacon-node/src/chain/blocks/importBlock.ts#L452).
- **Lighthouse:** [compressed SSZ persistence codec](https://github.com/sigp/lighthouse/blob/f31adcef15d7efea9433f55671027877959f139e/beacon_node/beacon_chain/src/persisted_fork_choice.rs#L58), [internal persistence loader](https://github.com/sigp/lighthouse/blob/f31adcef15d7efea9433f55671027877959f139e/beacon_node/beacon_chain/src/beacon_chain.rs#L684), [proto-array persistence](https://github.com/sigp/lighthouse/blob/f31adcef15d7efea9433f55671027877959f139e/consensus/proto_array/src/proto_array_fork_choice.rs).
- **Teku:** [durable storage schema](https://github.com/Consensys-Incorporated/teku/blob/8f4cac0afc06b969e85d89f357bc648b56af4495/storage/src/main/java/tech/pegasys/teku/storage/server/kvstore/schema/V6SchemaCombined.java), [proto-array reconstruction](https://github.com/Consensys-Incorporated/teku/blob/8f4cac0afc06b969e85d89f357bc648b56af4495/storage/src/main/java/tech/pegasys/teku/storage/protoarray/ProtoArray.java).
- **Prysm:** [startup reconstruction](https://github.com/OffchainLabs/prysm/blob/8b79bf5448f7b4aab1c23dff30027c66e69a29c5/beacon-chain/blockchain/setup_forkchoice.go).
- **Nimbus:** [fork-choice startup replay](https://github.com/status-im/nimbus-eth2/blob/5f7baa634cd2f924e179c3f9cc58eccaeb53b346/beacon_chain/consensus_object_pools/attestation_pool.nim).
- **Grandine:** [store persistence limitations](https://github.com/grandinetech/grandine/blob/3b0a5ac45ff552cffe36af72269a1476715174c6/fork_choice_store/src/store.rs), [canonical persistence/query path](https://github.com/grandinetech/grandine/blob/3b0a5ac45ff552cffe36af72269a1476715174c6/fork_choice_control/src/queries.rs), [restart mutation/re-import](https://github.com/grandinetech/grandine/blob/3b0a5ac45ff552cffe36af72269a1476715174c6/fork_choice_control/src/mutator.rs).

### Direct historical evidence (public archive)

- [Split diagnosis](https://github.com/ethereum/eth-rnd-archive/blob/ae3fc7d6/interop-%F0%9F%8C%83/2026-06-08.json).
- [Holesky investigation](https://github.com/ethereum/eth-rnd-archive/blob/ae3fc7d6/interop-%F0%9F%8C%83/2025-02-25.json).
- [PTC decision debugging](https://github.com/ethereum/eth-rnd-archive/blob/ae3fc7d6/epbs/_threads/devnet%20forkchoice%20issue/2026-05-29.json).
- [Missing historical PTC evidence](https://github.com/ethereum/eth-rnd-archive/blob/ae3fc7d6/interop-%F0%9F%8C%83/_threads/why%20was%20payload%20of%207218%20allowed%20to%20be%20reorged_/2026-06-05.json).
- [Historical capture](https://github.com/ethereum/eth-rnd-archive/blob/ae3fc7d6/consensus-dev/2025-12-19.json).
- [Invalid-branch forensics](https://github.com/ethereum/eth-rnd-archive/blob/ae3fc7d6/interop-%F0%9F%8C%83/2025-03-14.json).
- [Monitoring/cost tradeoffs](https://github.com/ethereum/eth-rnd-archive/blob/ae3fc7d6/tooling/2022-08-26.json).
- [v2 format discussion](https://github.com/ethereum/eth-rnd-archive/blob/ae3fc7d6/GET__eth_v2_debug_fork_choice_endpoint/2026-10-07.json).
- [SSZ representation discussion](https://github.com/ethereum/eth-rnd-archive/blob/ae3fc7d6/apis/2026-06-01.json).

**Lodestar:**
- Issues: [#4000](https://github.com/ChainSafe/lodestar/issues/4000), [#8592](https://github.com/ChainSafe/lodestar/issues/8592), [#3647](https://github.com/ChainSafe/lodestar/issues/3647), [#3717](https://github.com/ChainSafe/lodestar/issues/3717), [#9716](https://github.com/ChainSafe/lodestar/issues/9716), [#1526](https://github.com/ChainSafe/lodestar/issues/1526), [#911](https://github.com/ChainSafe/lodestar/issues/911).
- PRs: [#10206](https://github.com/ChainSafe/lodestar/issues/10206), [#5144](https://github.com/ChainSafe/lodestar/issues/5144), [#9444](https://github.com/ChainSafe/lodestar/issues/9444), [#10191](https://github.com/ChainSafe/lodestar/issues/10191), [#10297](https://github.com/ChainSafe/lodestar/issues/10297), [#10327](https://github.com/ChainSafe/lodestar/issues/10327), [#10287](https://github.com/ChainSafe/lodestar/issues/10287), [#10267](https://github.com/ChainSafe/lodestar/issues/10267), [#8527](https://github.com/ChainSafe/lodestar/issues/8527), [#9332](https://github.com/ChainSafe/lodestar/issues/9332), [#10005](https://github.com/ChainSafe/lodestar/issues/10005).

**beacon-APIs:** [#231](https://github.com/ethereum/beacon-APIs/issues/231), [#232](https://github.com/ethereum/beacon-APIs/issues/232), [#576](https://github.com/ethereum/beacon-APIs/issues/576), [#615](https://github.com/ethereum/beacon-APIs/issues/615) (v2, merged 2026-10-07), [#639](https://github.com/ethereum/beacon-APIs/issues/639), [#658](https://github.com/ethereum/beacon-APIs/issues/658).

**Other clients:**
- Lighthouse: [#1833](https://github.com/sigp/lighthouse/issues/1833), [#2028](https://github.com/sigp/lighthouse/issues/2028), [#2547](https://github.com/sigp/lighthouse/issues/2547), [#3498](https://github.com/sigp/lighthouse/issues/3498), [#7760](https://github.com/sigp/lighthouse/issues/7760)/[#7805](https://github.com/sigp/lighthouse/issues/7805), [#8891](https://github.com/sigp/lighthouse/issues/8891), [#9025](https://github.com/sigp/lighthouse/issues/9025), [#9818](https://github.com/sigp/lighthouse/issues/9818)/[#9819](https://github.com/sigp/lighthouse/issues/9819), [#10089](https://github.com/sigp/lighthouse/issues/10089), [#10142](https://github.com/sigp/lighthouse/issues/10142)/[#10165](https://github.com/sigp/lighthouse/issues/10165), [#10215](https://github.com/sigp/lighthouse/issues/10215).
- Teku: [#1627](https://github.com/Consensys-Incorporated/teku/issues/1627), [#2160](https://github.com/Consensys-Incorporated/teku/issues/2160)/[#2270](https://github.com/Consensys-Incorporated/teku/issues/2270), [#3124](https://github.com/Consensys-Incorporated/teku/issues/3124), [#5903](https://github.com/Consensys-Incorporated/teku/issues/5903), [#6599](https://github.com/Consensys-Incorporated/teku/issues/6599), [#9198](https://github.com/Consensys-Incorporated/teku/issues/9198)/[#9203](https://github.com/Consensys-Incorporated/teku/issues/9203), [#10800](https://github.com/Consensys-Incorporated/teku/issues/10800)/[#11448](https://github.com/Consensys-Incorporated/teku/issues/11448).
- Prysm: [#10777](https://github.com/OffchainLabs/prysm/issues/10777), [#15000](https://github.com/OffchainLabs/prysm/issues/15000)/[#15636](https://github.com/OffchainLabs/prysm/issues/15636), [#16478](https://github.com/OffchainLabs/prysm/issues/16478), [#16862](https://github.com/OffchainLabs/prysm/issues/16862), [#17273](https://github.com/OffchainLabs/prysm/issues/17273), [#17497](https://github.com/OffchainLabs/prysm/issues/17497), [#17636](https://github.com/OffchainLabs/prysm/issues/17636).
- Nimbus: [#1910](https://github.com/status-im/nimbus-eth2/issues/1910), [#5328](https://github.com/status-im/nimbus-eth2/issues/5328), [#8578](https://github.com/status-im/nimbus-eth2/issues/8578), [#8590](https://github.com/status-im/nimbus-eth2/issues/8590).
- Grandine: [#839](https://github.com/grandinetech/grandine/issues/839), [#886](https://github.com/grandinetech/grandine/issues/886)/[#887](https://github.com/grandinetech/grandine/issues/887).

**EL:**
- execution-apis#786.
- go-ethereum #34767 (guard), #35335 (`--engine.maxreorgdepth`), #35519, #35804.

**Chats** (public [eth-rnd-archive](https://github.com/ethereum/eth-rnd-archive)):
- `#interop`: 2022-06-30, 2022-08-11, 2023-03-13, 2025-01-21, 2025-02-25, 2025-03-14, 2026-05-03, 2026-05-16, 2026-06-05, 2026-06-08, 2026-06-10.
- `#epbs`: 2025-02-06, 2026-03-04, 2026-05-29.
- `#apis`: 2026-06-01, 2026-06-03, and the `GET /eth/v2/debug/fork_choice` thread (2026-09-30, 10-07, 10-09).
- `#consensus-dev` 2025-12-19, `#tooling` 2022-08-23/26, `#cl-testing` 2022-10-27, `#uncategorized` 2024-08-14.
