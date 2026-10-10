# Fork choice persistence and dumps in other CL clients

Research date: 2026-10-10. Read-only source study, done to inform a Lodestar "fork choice dump" design. Lodestar itself is out of scope here.

## Pinned sources

| Repo | Ref | SHA | Notes |
|---|---|---|---|
| sigp/lighthouse | origin/unstable | `f31adcef15d7efea9433f55671027877959f139e` | Gloas fork choice is on unstable (PR #9025). `origin/gloas-fork-choice` is an old prototype and was not read. |
| prysmaticlabs/prysm (now OffchainLabs/prysm) | origin/develop | `8b79bf5448f7b4aab1c23dff30027c66e69a29c5` | |
| Consensys/teku (now Consensys-Incorporated/teku) | origin/master | `8f4cac0afc06b969e85d89f357bc648b56af4495` | |
| status-im/nimbus-eth2 | origin/unstable | `5f7baa634cd2f924e179c3f9cc58eccaeb53b346` | `stable` `657beb3d6` has the same persistence and restart code |
| grandinetech/grandine | origin/develop | `3b0a5ac45ff552cffe36af72269a1476715174c6` | |
| ethereum/beacon-APIs | origin/master | `01e99a6530b22941f619bde525cbf8bb61991d42` | |
| ethereum/execution-apis | origin/main | `34151926fbf395e66797add1f60fd759681678e6` | context for the "Too deep reorg" error |
| ethereum/go-ethereum | master via `gh api` | `3a6c2e3b35ef8caa3d39dcbea3fe9f09099cca8c` | context only; not cloned locally |

Caveats:
- All local clones are shallow. PR and issue history comes from `gh`, not `git blame`.
- The GitHub search API was rate-limited during the run, so some searches went through GraphQL. Searches for PRs/issues may be incomplete; "not found" claims are flagged.
- Line refs are at the pinned SHA. Some paths are abbreviated with `.../`; resolve them with `git ls-tree -r --name-only <SHA> | grep <File>`.
- Prysm abbreviations: `doubly-linked-tree/` = `beacon-chain/forkchoice/doubly-linked-tree/`. `blockchain/` = `beacon-chain/blockchain/`.
- Items marked "inferred" were derived from reading the code, not from running it.

Spot-checked by me against the source, beyond the per-client research:
- **Lighthouse:**
  - `persist_fork_choice` call sites and the poisoned guard
  - startup fcU in `client/src/builder.rs:762-796`
  - `ExecutionStatus::NotYetRevealed`
  - `fork_revert.rs` is absent
  - the `VoteTrackerV28` known-issue comment
- **Prysm:** `setup_forkchoice.go:20-115`; the `--disable-debug-rpc-endpoints` flag.
- **Teku:** `V6SchemaCombined.java:55-92`; `ProtoArray.java:175-232`.
- **Nimbus:** `attestation_pool.nim:124-233`; `proto_array.nim:836-876`.
- **Grandine:** `queries.rs:54-57,225-254`; `mutator.rs:3149-3177`; `store.rs:150-158`.
- **Cross-cutting:** a grep for too-deep-reorg handling across all five clients.

---

## 0. Standard API: `debug/fork_choice` (beacon-APIs @ 01e99a6)

### v1: `GET /eth/v1/debug/fork_choice`, now deprecated
- Spec files: `apis/debug/fork_choice.yaml:1-35` and `types/fork_choice.yaml:1-32`.
- Marked `deprecated: true` with the note "Use `GET /eth/v2/debug/fork_choice` for Gloas and later forks" (`fork_choice.yaml:4-8`).
- There is no `data` wrapper.
- Top level:
  - `justified_checkpoint`, `finalized_checkpoint`, and `fork_choice_nodes` are required.
  - `fork_choice_nodes` has `minItems: 1` (#474).
  - `extra_data` is optional.
- Each `Node` requires `slot, block_root, parent_root, justified_epoch, finalized_epoch, weight, validity, execution_block_hash` (`types/fork_choice.yaml:4`).
- `validity` is the enum `[valid, invalid, optimistic]`; it was lowercased in #303.
- Per-node `extra_data` is optional and free-form ("may differ between clients").
- History:
  - Issue #231 asked for "Standard debug API for Fork Choice" for tools like protovis.
  - PR #232 (merged 2022-10-29) added the endpoint.
  - #303 lowercased the enum.
  - #474 made the nodes required.

### v2: `GET /eth/v2/debug/fork_choice`, merged
Added by PR **#615** (potuz, merged 2026-10-07) and shipped in tag `v5.0.0-beta.0` (published 2026-10-08). Spec files: `apis/debug/fork_choice.v2.yaml:1-39` and `types/fork_choice.yaml:34-91`.

- **Response:** `{ data: { justified_checkpoint, finalized_checkpoint, fork_choice_nodes: NodeV2[], extra_data } }`. All four fields are required and `extra_data` is free-form.
- **Node identity:** there is one node per `(block_root, payload_status)` pair. Parent links follow the spec's `get_node_children` tree. A pre-Gloas block has a single `full` node (`fork_choice.v2.yaml:5-10`).
- **Required `NodeV2` fields** (`types/fork_choice.yaml:37`):
  - `slot`, `block_root`
  - `payload_status`: `pending|empty|full`
  - `parent_root`: for Gloas `empty`/`full` nodes this equals `block_root`, pointing at the same block's `pending` node. Otherwise it is the beacon block's `parent_root`.
  - `parent_payload_status`: `pending|empty|full`, or `null` if the parent was pruned from the tree.
  - `justified_checkpoint`, `finalized_checkpoint`: full `Checkpoint` objects, not epochs.
  - `weight`: Gwei, "the raw stored weight of this fork choice node".
  - `validity`: `valid|invalid|optimistic`.
  - `execution_block_hash`: the payload hash for `full` nodes; the bid's `parent_block_hash` for Gloas `pending`/`empty` nodes.
  - `payload_attester_count`, `payload_availability_yes_count`, `payload_data_availability_yes_count`: PTC counts per committee position, including repeated validator indices. They are the same for every node of a block and zero before Gloas.
  - `extra_data`
- **Design discussion in #615 review comments:**
  - nflaig asked for the `data` wrapper and for deprecating v1, and asked whether head (`block_root` + `payload_status`) should be top level. Head was not added; clients put it in `extra_data`.
  - tbenr pushed for the `Checkpoint` type. nflaig argued to keep per-node checkpoints "for debugging purposes in general should dump as much data as possible".
  - `(parent_root, parent_payload_status)` was chosen to simplify tree traversal.
  - rolfyone: "because it's a debug endpoint, thats our internal representation… The more we abstract the structures away, the more interpretation is needed".
  - Savid observed that Prysm's pending node carried `bid.block_hash` while Teku's carried `bid.parent_block_hash`. The spec settled on `parent_block_hash`.
- **Closed or superseded:**
  - Issue #576 (nflaig, "Update forkchoice endpoint for gloas") closed by #615.
  - PR #658 (eserilev, add `not_yet_revealed` to v1 `validity`) closed in favour of v2.
  - Issue #639 (qu0b) closed. On glamsterdam-devnet-9, Lighthouse emitted `null` validity/hash for Gloas nodes while Teku emitted `optimistic`, which breaks strict decoders such as go-eth2-client.
- **Client implementation status:**

| Client | Status |
|---|---|
| Prysm | Done (OffchainLabs/prysm#16862, merged 2026-06-03) |
| Teku | Done (#10800, merged 2026-06-24; aligned with final spec in #11448) |
| Lighthouse | Open PR #10215 |
| Nimbus, Grandine | No v2 route at the pinned SHAs (grep `debug/fork_choice`) |

### EL context: "Too deep reorg" (needed for question C)
- **execution-apis spec** (`src/engine/paris.md:221,243` @ 34151926):
  - "Client software **MUST** return `-38006: Too deep reorg` error if the depth of reorg to `forkchoiceState.headBlockHash` exceeds the limitation specific to the client software."
  - Skip rule 2 (`:213`) was narrowed to "ancestor of the latest known finalized block" by execution-apis#786 (merged 2026-04-23).
  - execution-apis#770 (closed) explains why: Gloas late payloads require reorgs to the head's ancestor. The original skip logic existed "when EL is much closer to the head state than the CL (consider CL restart)". 32 blocks was proposed as the cap.
- **geth `eth/catalyst/api.go:338-346`** (master 3a6c2e3b): the depth check only runs when the fcU target is **already canonical in the EL and below the EL's current head**. That is exactly the "CL restarted behind the EL" case.
  ```go
  if current := api.eth.BlockChain().CurrentBlock().Number.Uint64(); block.NumberU64() < current {
      depth := current - block.NumberU64()
      if api.maxReorgDepth > 0 && depth > api.maxReorgDepth {
          log.Warn("Refusing too deep reorg", "depth", depth, "head", update.HeadBlockHash)
          return engine.STATUS_INVALID, engine.TooDeepReorg.With(fmt.Errorf("reorg depth %d exceeds limit %d", depth, api.maxReorgDepth))
  ```
  - Default `EngineMaxReorgDepth: 32` (`eth/ethconfig/config.go:78`). `TooDeepReorg = -38006` (`beacon/engine/errors.go:84`).
  - The method returns a non-nil error, so the CL sees a **JSON-RPC error -38006**, not a `payloadStatus: INVALID`. This follows from how geth's RPC layer turns a returned error into an error response; I did not test it end-to-end.
  - Targets below the EL's finalized block are skipped earlier with `VALID` ("Skipping beacon update to finalized ancestor", `:334-337`).
  - Related geth PRs:
    - #34767: allow reorging the head to a parent.
    - #35391: `>` instead of `>=`.
    - #35519: allow reorg down to finalized.
    - **#35804** (merged 2026-10-08): fixes a uint64 underflow. After an **unclean geth shutdown**, a forward update onto a still-canonical block above the rewound head computed depth `2^64-784` and was refused forever.
- **CL handling:** a grep across all five CL clients for `too deep reorg|toodeepreorg|38006|maxreorgdepth|max_reorg_depth|reorg depth` finds **no handling in any of them**. The only hits are unrelated metrics, comments, or hex noise in Teku test JSON.

---

## 1. Lighthouse (sigp/lighthouse @ f31adcef1, unstable)

### A. Persistence: yes, a full snapshot
- **Storage location:** one key-value entry, column `DBColumn::ForkChoice` (tag `"frk"`, `beacon_node/store/src/lib.rs:326-327`), key `FORK_CHOICE_DB_KEY = Hash256::ZERO` (`beacon_node/beacon_chain/src/beacon_chain.rs:175`). Fast-confirmation (FCR) roots live in the same column under key `0x01…01` (`beacon_chain.rs:176-177`, `persisted_fast_confirmation.rs:17-20`).
- **Nested, superstruct-versioned layers:**
  - `PersistedForkChoiceV29 { fork_choice: fork_choice::PersistedForkChoiceV29, fork_choice_store: PersistedForkChoiceStoreV28 }` (`beacon_node/beacon_chain/src/persisted_fork_choice.rs:9-23`).
  - `fork_choice::PersistedForkChoiceV29 { proto_array: SszContainerV29 }`. V28 also had `queued_attestations_v28`, which V29 drops (`consensus/fork_choice/src/fork_choice.rs:2087-2121`).
  - `SszContainerV29 { votes: Vec<VoteTracker>, prune_threshold, nodes: Vec<ProtoNode>, indices: Vec<(Hash256, usize)> }` (`consensus/proto_array/src/ssz_container.rs:17-43`). V28 also had deprecated `justified_checkpoint`, `finalized_checkpoint` and `previous_proposer_boost`.
  - `PersistedForkChoiceStoreV28 { time, finalized_checkpoint, justified_checkpoint, justified_state_root, unrealized_justified_checkpoint, unrealized_justified_state_root, unrealized_finalized_checkpoint, proposer_boost_root, equivocating_indices: BTreeSet<u64> }` (`beacon_fork_choice_store.rs:394-408`).
- **What is and isn't stored:**
  - **Persisted:**
    - Nodes: slot, state_root, target_root, shuffling ids, parent, justified/finalized, **weight**, execution_status, and per-node unrealized checkpoints (`proto_array.rs:79-181`).
    - `indices`.
    - Votes: `VoteTracker{current_root,next_root,current_slot,next_slot,current_payload_present,next_payload_present}` (`proto_array_fork_choice.rs:26-34`).
    - Store checkpoints, time, `proposer_boost_root`, and equivocating indices.
    - All Gloas node fields (see E).
  - **Not persisted:**
    - The `children` index, rebuilt on load (`ssz_container.rs:68`).
    - Justified balances, recomputed from the justified state in the hot DB (`beacon_fork_choice_store.rs:216-225`).
    - The balances cache (removed in #7805).
    - Queued attestations (V29).
    - Proposer boost score (computed on the fly).
    - Head: recomputed by `get_head`. `PersistedBeaconChain` holds only `genesis_block_root` (`persisted_beacon_chain.rs:6-9`).
- **Encoding:** SSZ, then zstd at `StoreConfig` compression level (default 1; `persisted_fork_choice.rs:65-74`, `store/src/config.rs:25,197-213`).
  - `ProtoNode` is an SSZ union of V17/V29 (`proto_array.rs:79-84`).
  - `ExecutionStatus` is an SSZ union (`proto_array_fork_choice.rs:105-127`).
- **Versioning and migration:**
  - DB `CURRENT_SCHEMA_VERSION = 31` (`store/src/metadata.rs:7`).
  - `migrate_schema` steps one version at a time, up or down. Each step is atomic with its version bump (`schema_change.rs:15-75`). Pre-v28 migrations are no longer supported (`:17`).
  - `migration_schema_v29.rs` handles fork choice:
    - Refuses if any V17 node is at or after the Gloas fork slot (`:35-52`).
    - **Subtracts the proposer boost that V28 had baked into node weights** (`:54-96`).
    - Writes V29 (`:98-100`).
    - Downgrade is refused once any V29 node exists (`:129-143`).
- **When written (never per block):**
  1. In `after_new_head`, only when the new head crosses an epoch boundary or there was a reorg (`canonical_head.rs:1565-1568`).
  2. In `after_finalization`, **before** the store migrator advances the split (`canonical_head.rs:1719-1729`; fix #10165). Pruning happens after (`:1739`).
  3. On graceful shutdown via `impl Drop for BeaconChain` (`beacon_chain.rs:8021-8043`).
  4. At startup in `build()`, in the same batch as `PersistedBeaconChain` (`builder.rs:909-928`).
- **Write path** (`canonical_head.rs:1747-1764`):
  ```rust
  if self.canonical_head.fork_choice_poisoned() { crit!(...); return Err(Error::ForkChoicePoisoned); }
  let mut batch = vec![self.persist_fork_choice_in_batch()?];
  batch.extend(self.persist_fast_confirmation_roots_in_batch()); // same batch
  self.store.hot_db.do_atomically(batch)?;
  ```
  Metrics: `beacon_persist_fork_choice` (`metrics.rs:686-691`), `FORK_CHOICE_ENCODE_TIMES`, `FORK_CHOICE_COMPRESS_TIMES` (`:644,650`).
- **Crash consistency:**
  - The snapshot is **not** in the block-write batch.
  - Block import runs `on_block` under the fork choice write lock. It then writes the block, state and blobs atomically, and only releases the lock after the DB write (`beacon_chain.rs:4446-4478,4669-4702`). So in-memory fork choice never exposes a block that isn't on disk.
  - If the DB write fails, fork choice is **poisoned** and a shutdown is sent (`beacon_chain.rs:4769-4800`; `canonical_head.rs:474-475,562-570`; PRs #9818/#9819). Poisoned fork choice is never persisted (test `tests/store_fault_tests.rs:184-228`).
  - The Gloas envelope import path doesn't poison yet (`TODO(gloas)` at `payload_envelope_verification/import.rs:292-304`; open PR #9978).
  - Net effect: the persisted fork choice can lag the DB by up to about an epoch, or back to the last reorg/finalization. It is never ahead.
  - Pruned fork blocks may remain in the persisted proto-array; this is tolerated (`beacon_chain/src/invariants.rs:29-33`).

### B. Startup and restore: load the snapshot, no block replay
- **Entry point:**
  - An existing DB means `ClientGenesis::FromStore`. Checkpoint sync is refused with "use --purge-db to force checkpoint sync" (`client/src/builder.rs:273-299`).
  - `resume_from_db` calls `BeaconChain::load_fork_choice` (`beacon_chain.rs:684-708`): decompress, SSZ-decode, then `BeaconForkChoiceStore::from_persisted`, which loads the justified state to rebuild balances (`beacon_fork_choice_store.rs:212-241`). Then `ForkChoice::from_persisted` (`fork_choice.rs:2017-2071`).
  - A missing record is a hard error, "Fork choice not found in store" (`beacon_chain/src/builder.rs:252`).
- **Head computation:** `build()` calls `fork_choice.get_head(current_slot)` (`builder.rs:781-790`). `update_time` ticks `on_tick` **slot by slot** from the persisted `time` to wall clock (`fork_choice.rs:579-587,1521-1582`). This resets `proposer_boost_root` and pulls up unrealized checkpoints at epoch boundaries. For a FULL Gloas head, the envelope summary is loaded (`builder.rs:799-807`).
- **Votes:** restored from `SszContainer.votes`. Queued current-slot attestations are lost. Proposer boost is effectively lost, because `on_tick` zeroes it.
- **Validation and fallbacks:**
  - **Invalid payloads:** `ResetPayloadStatuses` defaults to `OnlyWithInvalidPayload`. If any node is `Invalid`, every status is reset to `Optimistic` and weights are rebuilt by replaying votes (`fork_choice.rs:115-133,1969-2013`; `proto_array_fork_choice.rs:957-1048`).
    - `--reset-payload-statuses` forces this reset on every start (`beacon_node/src/cli.rs:1518-1526`).
    - Origin: #3498, recovery from a Geth consensus fault that wrongly returned INVALID.
  - If `get_head` fails on the persisted fork choice, Lighthouse logs "Could not find head on persisted FC", resets payloads to optimistic and retries once; a second failure is a hard error (`fork_choice.rs:2049-2068`).
  - **Corruption check:** fork choice finalized < head-state finalized gives "Database corrupt: fork choice is finalized at … whilst head is finalized at …" (`builder.rs:821-833`).
  - A weak-subjectivity check runs, overridable with `--ignore-ws-check` (`builder.rs:835-861`).
  - **No rebuild-from-finalized fallback.** `fork_revert.rs` (`revert_to_fork_boundary` / `reset_fork_choice_to_finalization`, #2529) was deleted as "dysfunctional" in **#8891** (merged 2026-02-24; issue #4198). I confirmed the file is absent at the SHA.
  - **No unclean-shutdown flag.** A grep for `unclean|dirty shutdown|ungraceful` finds nothing related.
- **On-demand invariants:** `GET /lighthouse/database/invariants` (`http_api/src/lib.rs:3157-3168`; `beacon_chain/src/invariants.rs:18-82`; `store/src/invariants.rs:77-86,264-272,338-355`) checks:
  - fork choice blocks descending from finalized are in the hot DB;
  - every received Gloas payload has a summary;
  - fork choice finalized ≥ the split.
- **Flags:** `--purge-db` / `--purge-db-force`, `--reset-payload-statuses`, `--ignore-ws-check`. Offline migration: `lighthouse db migrate --to N` (`database_manager/src/cli.rs:85-95`).
- **UNVERIFIED:** how blocks imported after the last snapshot (present in the DB, absent from the restored fork choice) get back into fork choice after a crash. Presumably they come back via sync; not traced.

### C. EL interaction on restart
- The first fcU is sent **after** the head is restored. It is spawned fire-and-forget only if the head hash is non-zero, and a failure only produces `warn!("Failed to update head on execution engines")` (`client/src/builder.rs:762-796`, verified).
- `spawn_watchdog_routine` runs an upcheck immediately and every slot (`execution_layer/src/lib.rs:706-727`). When the engine becomes Synced, it re-sends the cached last `ForkchoiceState` and refreshes `exchangeCapabilities` (`engines.rs:197-226,240-300`).
- `prepare_beacon_proposer` runs once per slot (`proposer_prep_service.rs:14-54`).
- **fcU response handling** (`beacon_chain.rs:6928-7133`):
  - `VALID` marks the chain valid.
  - `SYNCING` and `ACCEPTED` are no-ops.
  - `INVALID` / `INVALID_BLOCK_HASH` call `process_invalid_execution_payload` (`InvalidateOne`/`InvalidateMany`), which mutates fork choice and re-runs head selection (`:6535-6600`).
- **Too-deep reorg:** no handling. There are no engine error-code constants except -38001 in a test mock (`execution_layer/src/test_utils/handle_rpc.rs:13`). Inferred consequences:
  - geth's JSON-RPC -38006 surfaces as `ExecutionForkChoiceUpdateFailed`; at startup that is only a warning.
  - An EL that answered with `INVALID` status instead would get the head invalidated in fork choice. The default load-time reset only clears that on the next restart.

### D. Debug and dump surfaces
- **`GET /eth/v1/debug/fork_choice`** (`http_api/src/lib.rs:2177-2260`; types `common/eth2/src/types.rs:1746-1779`):
  - Standard fields. `validity` comes from `ExecutionStatus`: `valid|invalid|optimistic|not_yet_revealed`, or omitted/`null` for `irrelevant` (`proto_array_fork_choice.rs:236-246`, verified).
  - Per-node `extra_data` (#7845): `target_root`, `justified_root`, `finalized_root`, `unrealized_{justified,finalized}_{root,epoch}`, `execution_status`, `best_child`, `best_descendant`.
  - `best_child` and `best_descendant` are **always null now**: V29 nodes don't have them and the V28→V29 migration clears them (`ssz_container.rs:88-91`).
- **`GET /lighthouse/proto_array`** (`http_api/src/lib.rs:3072-3092`; client `common/eth2/src/lighthouse.rs:222-232`):
  - serde JSON of the whole `ProtoArray { prune_threshold, nodes, indices }`, including all V29 fields: payload weights, PTC bitfields, `payload_received`, timeliness flags.
  - **Excludes** votes, balances and the store (time, checkpoints, boost root, equivocations).
  - UNVERIFIED: whether the node enum serializes externally tagged (`{"V29":{…}}`).
- **Other endpoints:** `/lighthouse/database/{invariants,info}`; `POST /lighthouse/finalize` (manual finalization that only affects the migrator; disabled with FCR, #10166); `/eth/v{1,2}/debug/beacon/heads`.
- **v2:** open PR **#10215** adds `debug_fork_choice.rs`, which expands each proto node into the spec's `(root, payload_status)` nodes.
  - Node `extra_data`: `{target_root, state_root, unrealized_*, execution_status, payload_received}`.
  - Top-level `extra_data`: `{head_root, head_payload_status, proposer_boost_root, unrealized_justified/finalized_checkpoint}`.
- **Offline tooling:**
  - `lighthouse db inspect --column frk --output values` dumps the raw **zstd-compressed SSZ** to `frk_<hexkey>.ssz` (`database_manager/src/cli.rs:97-140`, `lib.rs:134-215`).
  - **No decoder exists:** `lcli parse-ssz` handles only blocks, states and BlobSidecar (`lcli/src/parse_ssz.rs:66-119`), and there is no `lcli` fork choice subcommand.
  - No code path loads a dump into a node or harness.
  - The proto_array test DSL serializes to YAML (`consensus/proto_array/src/bin.rs:1-26`), and its tests round-trip SSZ after each op (`fork_choice_test_definition.rs:702-710`).
  - Restart tests: `tests/fast_confirmation_restart.rs`, `store_tests.rs:539`, `payload_invalidation.rs:1455`.
  - No visualizer. Issue #4332 was diagnosed from a user's fork choice DB dump plus Forky.

### E. Gloas / ePBS (on unstable, #9025)
- **Node model:** one `ProtoNode::V29` per block, in the same array as pre-Gloas V17 nodes (`proto_array.rs:601-700`). V29 fields (`proto_array.rs:135-180`):
  - `parent_payload_status` (Empty=0/Full=1/PreGloas=2)
  - `empty_payload_weight`, `full_payload_weight`
  - `execution_payload_block_hash`, `execution_payload_parent_hash`
  - `block_timeliness_attestation_threshold`, `block_timeliness_ptc_threshold`
  - `payload_timeliness_votes`, `payload_data_availability_votes`, `ptc_participation` (each a `BitVector<U512>`)
  - `payload_received`, `proposer_index`, `equivocating_attestation_score`
- **Variants:** `weight` is the PENDING (attestation-only) weight. PENDING/EMPTY/FULL are **virtual**: `IndexedForkChoiceNode { root, proto_node_index, payload_status }` (`proto_array_fork_choice.rs:159-164`).
  - `get_node_children` expands PENDING into EMPTY, and also FULL only if `payload_received` and the payload is not invalid (`proto_array.rs:1822-1879`).
  - `PayloadStatus` SSZ tag: Empty=0, Full=1, Pending=2 (`proto_array_fork_choice.rs:130-138`, verified).
  - `ExecutionStatus::NotYetRevealed(bid_block_hash)` covers the time before the envelope arrives (`:122-126`, verified).
- **Votes:** PTC votes write the bitfields directly (`proto_array_fork_choice.rs:711-750`). LMD votes carry `payload_present`.
- **Persistence:** everything above is persisted inside `SszContainerV29.nodes`. Lighthouse is the only client that persists PTC votes and payload weights.
- **Dumps:** v1 shows one row per block with `execution_block_hash` = the bid hash. The full V29 data is visible only via `/lighthouse/proto_array`. Per-variant rows arrive with v2 (#10215).

### F. Notable PRs and issues
- **#647/#650:** the original "Persist fork choice" (2019).
- **#851:** persist head and fork choice only when the head changes epoch; op pool and eth1 only on drop.
- **#2547:** persist after setting the canonical head; moved off the critical path (~200 ms).
- **#1833:** "Failed to decode ProtoArrayForkChoice: InvalidByteLength" after upgrading to v0.3.1. The on-disk format changed without a migration.
- **#2028** "Head block not found in store": fork choice got ahead of disk. Fixed by #2068 (revert fork choice to disk on write failure). Superseded by **#9818/#9819** (poison and shut down; never persist a diverged fork choice).
- **#2128 / #3601 / #4332:** `InvalidBestNode` / "find_head failed" on startup.
  - #4332 was root-caused from a user's fork choice DB dump plus Forky, and fixed by #4357.
  - #9364 (2026-06) deleted the "bogus" `InvalidBestNode` error after Glamsterdam devnet nodes failed to start.
- **#2529 → #8891:** `fork_revert` added, then deleted as dysfunctional after Altair (#4198).
- **#3498:** reset payload statuses on resume (Geth consensus fault). Origin of `--reset-payload-statuses`.
- **#4233/#4265:** fork choice cleanup migration (dropped `best_justified_checkpoint`).
- **#7760/#7805** (schema V28, 2025-08): "FC is persisted often and it's big… grows during non-finality".
  - Removed `balances_cache` (~65 MB on mainnet) and `justified_balances` (~16 MB), and added zstd.
  - #7760 also floated not persisting nodes and rebuilding them from blocks; not done.
- **#9025** (schema V29, Gloas redux): drops deprecated checkpoints and `previous_proposer_boost`, subtracts the baked-in boost, moves votes from epoch to slot, makes nodes an enum, drops queued attestations ("New attestations will quickly replace any attestations that are one slot old").
- **#10089** (won't fix): the V29 migration zeroes vote slots, so an older attestation can roll back a latest message for up to one epoch per validator. Fix PR #10095 was closed. Documented at `proto_array_fork_choice.rs:64-70` (verified).
- **#10142 → #10165:** FCR startup loop when the persisted fork choice finalized checkpoint was below the hot/cold split. Fixed by persisting before migration, plus invariant 14.
- **#8147** (open): the fork choice write lock is held during the DB write.
- **#9978** (open): revert `payload_received` when the envelope DB write fails.
- Debug API history: #3669 → #4003 (v1), #7829 → #7845 (`extra_data`), #10215 (v2, open).

---

## 2. Prysm (prysmaticlabs/prysm @ 8b79bf5448, develop)

### A. Persistence: not persisted
- **No fork choice bucket.** `beacon-chain/db/kv/schema.go:9-89` lists the buckets. The only fork-choice-adjacent keys are `head-root`, `justified-checkpoint`, `finalized-checkpoint`, `last-validated-checkpoint` (`:41-47`), `origin-checkpoint-block-root` (`:69`), and Gloas `execution-payload-envelopes` (`:20`).
- **In-memory store** (`doubly-linked-tree/types.go:15-101`):
  - `ForkChoice{votes []Vote, balances, justifiedBalances}`.
  - `Store{justified/unrealized/prev/finalized checkpoints, proposerBoostRoot, previousProposerBoostScore, emptyNodeByRoot, fullNodeByRoot, slashedIndices, ...}`.
  - There is no serialize method for any of it.
- **Lost on restart:** votes, balances, proposer boost, equivocating indices, PTC bitvectors, per-node unrealized checkpoints, queued attestations (in-memory pool, `operations/attestations/kv/kv.go:19-30`), and the full/empty node maps (partly re-derived; see B/E).
- **What is written:**
  - Head root on every head change in regular sync (`blockchain/head.go:168`), but not during init sync (`saveHeadNoDB`, `head.go:189-192`).
  - The justified checkpoint (`receive_block.go:587-599`, `process_block.go:455-460`).
  - Finalized and last-validated checkpoints (`process_block_helpers.go:318-362`). Last-validated is written only if the finalized block is not optimistic (`:343-351`).
  - Checkpoint encoding is protobuf (`db/kv/checkpoint.go:92-115`).
- **Ordering:**
  - The block and state are saved before fork choice insert (`process_block.go:685-698` and then `InsertNode` at `:79`).
  - If insert fails, `rollbackBlock` deletes the block (`:80-84`).
  - Init-sync blocks are cached in memory and flushed every `2*SLOTS_PER_EPOCH` blocks (`init_sync_process_block.go:13-25`), at finalization, or on clean `Stop()` (`service.go:241-249`).
  - Each write is its own bbolt transaction.
- **Rationale for not persisting: UNVERIFIED.** Closest discussion is #10777, where potuz noted that Teku saves per-block justified checkpoints; Prysm did not adopt it.

### B. Startup and restore: rebuild a single chain, no attestation replay
Call chain: `StartFromSavedState` (`blockchain/service.go:274-309`) → `setupForkchoice` (`blockchain/setup_forkchoice.go:20-31`, verified), which runs three steps.

1. **`setupForkchoiceCheckpoints`** (`:227-256`): loads the justified and finalized checkpoints. Errors are only logged since #16478 ("Balances will be wrong, but they self-heal on 2 epochs"). Before that, they were fatal and the "fix" was deleting the DB (#15468, #12367, #13153).
2. **`setupForkchoiceTree`** (`:57-92`):
   - Inserts the finalized block. It is marked VALID only if it equals `LastValidatedCheckpoint`, unless `--startup-optimistic` is set (`:147-157`).
   - Builds **one chain** from `startupHeadRoot()` back to finalized and calls `InsertChain`. The default startup head is the **justified root**; `--sync-from=head|<root>` overrides it:
     ```go
     headStr := features.Get().ForceHead
     jp := s.CurrentJustifiedCheckpt()
     jRoot := s.ensureRootNotZeros([32]byte(jp.Root))
     if headStr == "" { return jRoot }
     ```
     (`setup_forkchoice.go:33-55`; #15000 added the flag; #15636 made justified the default.)
   - Every block in the chain gets the *store's* justified and finalized checkpoints (`:108-112`); the code comment admits this is approximate (#10777).
   - **No attestations are re-processed and no state transition runs.** `InsertChain` just calls `store.insert` (`doubly-linked-tree/forkchoice.go:597-637`).
   - Restored nodes start optimistic (`store.go:148-151,162-171`).
   - Any failure (head block missing or nil, older than finalized, not a descendant) falls back to finalized only (`setup_forkchoice.go:67-84`; #17087/#17110).
3. **`initializeHead`** (`service.go:340-368`): head = highest received block root, with its state regenerated.

After setup:
- Init sync re-downloads and re-executes blocks above the restored head even if they are already in the DB (`sync/initial-sync/round_robin.go:585-602`).
- `fillInForkChoiceMissingBlocks` inserts DB-only ancestors without votes (`process_block_helpers.go:390-455`).
- Votes rebuild only from new gossip and blocks.
- There is no unclean-shutdown handling beyond the fallbacks above and `CleanUpDirtyStates` (`stategen/service.go:165-169`).

### C. EL interaction on restart
- **No fcU at startup.** None of `StartFromSavedState`, `setupForkchoice` or `initializeHead` calls the engine.
- **During init sync:**
  - Pre-Gloas: `newPayload` only. fcU is gated on `inRegularSync()` (`forkchoice_update_execution.go:82-84`; `receive_attestation.go:89,156-158`; `process_block.go:1211-1214`).
  - Post-Gloas: an attribute-less fcU to the bid's `parentBlockHash` after each successful batch (`head.go:211-222`).
  - #17273/#17275 (closed, unmerged) documented an EL starved with "285 newPayload / zero FCUs" on glamsterdam-devnet-7.
- **Optimistic state:** all non-finalized restored nodes are optimistic. `--startup-optimistic` also leaves finalized optimistic (#11303).
- **Too-deep reorg:** no handling (grep only finds the reorg-depth metric at `head.go:132`).
  - fcU `INVALID` maps to `ErrInvalidPayloadStatus` (`execution/engine_jsonrpc.go:271-272`). That triggers `SetOptimisticToInvalid`, `removeInvalidBlockAndState`, head recompute and a recursive fcU (`execution_engine.go:97-157`).
  - So an `INVALID` *status* would be treated as a real invalid chain (inferred).
  - The handling of a JSON-RPC -38006 error was not traced: UNVERIFIED.

### D. Debug and dump surfaces
- **Routes:** `/eth/v1/debug/fork_choice`, `/eth/v2/debug/fork_choice` and `/eth/v2/debug/beacon/heads` (`beacon-chain/rpc/endpoints.go:1173-1202`). They are **on by default**; disable with `--disable-debug-rpc-endpoints` (`cmd/beacon-chain/flags/base.go:280-284`, `rpc/endpoints.go:108-110`, verified).
- **v1** (`rpc/eth/debug/handlers.go:192-236`; structs `api/server/structs/endpoints_debug.go:24-58`):
  - Node `extra_data`: `{unrealized_justified_epoch, unrealized_finalized_epoch, balance, execution_optimistic, timestamp (Go time.String()), target}`.
  - Top-level `extra_data`: `{unrealized_justified/finalized_checkpoint, proposer_boost_root, previous_proposer_boost_root, head_root}`.
  - `validity` is only ever `valid|optimistic`, because invalid nodes are pruned (`doubly-linked-tree/gloas.go:369-373`).
- **Internal types:** plain Go structs (`consensus-types/forkchoice/types.go:52-111`, `Dump`/`Node`/`DumpV2`/`NodeV2`), built by a pre-order DFS under RLock (`forkchoice.go:675-757`, `gloas.go:331-475`).
  - The dump has **no** votes, balance arrays, slashed indices, PTC bitvectors (counts only) or builder index.
- **gRPC:** the old `GetForkChoice` gRPC method is removed (`CHANGELOG.md:4269`).
- **Tooling:** no tool loads a dump. `tools/blocktree` renders DB blocks as graphviz; `tools/forkchecker` and `tools/exploredb` don't read fork choice.

### E. Gloas / ePBS (on develop)
- **Node model:** one consensus `Node` per block acts as PENDING and carries weight, balance and the PTC bitvectors. Two `PayloadNode`s hang off it: EMPTY (`emptyNodeByRoot`) and FULL (`fullNodeByRoot`, created only when a payload exists). Children attach to a specific `PayloadNode` (`types.go:42-43,54-86`).
- **Parent variant:** chosen by matching the bid's `parentBlockHash` (`gloas.go:44-72`).
- **Votes:** carry a payload-status bool (`types.go:94-101`).
- **PTC:** `SetPTCVote` sets attester, availability and data-availability bits (`gloas.go:549-560`).
- **v2 dump** (`handlers.go:239-293`, `gloas.go:388-475`; #16862):
  - `pending` carries target, justified/finalized/unrealized epochs and the PTC counts.
  - `empty` carries weight, balance and optimistic.
  - `full` adds `gas_limit`.
- **Restart:**
  - FULL nodes are re-derived by comparing consecutive bids (`resolveChainPayloadStatus`, `setup_forkchoice.go:167-192`; #16599).
  - The tip uses the DB envelope (#17508). The finalized root uses `MarkFullNode` (`:199-225`; #17093).
  - PTC bitvectors restart empty (`store.go:133-135`).
  - #17497 (closed) documents envelopes in the DB not being re-imported after restart.

### F. Notable PRs and issues
- **#10777 / #10782:** replay gave every block the store's justified checkpoint; justification was wrong after INVALID pruning.
- **#11455:** protoarray removed; doubly-linked-tree is the only implementation.
- **#14997 → #15000 → #15636 (+#15684, #15688, #15639):** startup seeding evolved from finalized-only to `--sync-from`, then to justified by default.
- **#16478:** don't fail on checkpoint setup (previously "delete your DB": #15468, #12367, #13153).
- **#17087 / #17110:** nil head block at startup → fall back to finalized.
- **#17536:** dependent root unresolvable at startup because the tree is rooted at the anchor.
- **#15352** (open): nil-pointer panic in `setOptimisticToInvalid` after a devnet restart following long downtime.
- **#17273 / #17275:** no fcU during Gloas init sync starves the EL.

---

## 3. Teku (Consensys/teku @ 8f4cac0a, master)

### A. Persistence: inputs persisted, protoarray rebuilt
- **Approach:** Teku persists the *inputs* to fork choice and rebuilds the protoarray on every start. The old snapshot variable is retired:
  ```java
  // 7 was the protoarray snapshot variable but is no longer used.   // V6SchemaCombined.java:83 (verified)
  ```
- **Schema** (`storage/.../kvstore/schema/V6SchemaCombined.java`; default DB version V6, `DatabaseVersion.java:22-33`):
  - col 1 `HOT_BLOCKS_BY_ROOT`: full hot blocks (`:108`).
  - col 7 `HOT_BLOCK_CHECKPOINT_EPOCHS_BY_ROOT`: per-block realized **and unrealized** justified/finalized checkpoints (`:65-67`).
  - col 3 `VOTES`: one `VoteTracker` per validator index (`:59,121-123`).
  - Variables (`:72-91`): `GENESIS_TIME`, `JUSTIFIED_CHECKPOINT`, `BEST_JUSTIFIED_CHECKPOINT`, `FINALIZED_CHECKPOINT`, `ANCHOR_CHECKPOINT`, `LATEST_CANONICAL_BLOCK_ROOT`.
  - Gloas blinded payload envelopes (`:280-282`).
- **`VoteTracker`** (`ethereum/spec/.../forkchoice/VoteTracker.java:34-43`) holds:
  - `currentRoot` (applied) and `nextRoot` (latest message);
  - `next/currentEquivocating`;
  - Gloas `next/currentSlot` and `next/currentFullPayloadHint`.
  - Equivocations exist only as these flags (`ForkChoice.java:1359-1368`); there is no separate set.
- **Vote encoding:** key = 8-byte big-endian index. The value format is detected from its length:
  ```java
  // Legacy: currentRoot(32)|nextRoot(32)|epoch(8)[|nextEquiv(1)|curEquiv(1)]
  // Gloas:  currentRoot|nextRoot|nextSlot(8)|nextEquiv|curEquiv|nextFullHint|curSlot(8)|curFullHint
  // Before Gloas activation we intentionally keep writing the legacy epoch-based format so rollback remains possible.
  ```
  (`storage/.../serialization/VoteTrackerSerializer.java:26-38,63-76,127-170`; #10573.) Per-block checkpoints use 4 epochs + 4 roots, and the legacy 2-epoch format is still readable (`BlockCheckpointsSerializer.java:32-37,53-65`).
- **Not persisted:**
  - protoarray nodes, weights, best child/descendant;
  - validity (recomputed at insert, `ProtoArray.java:185`, verified);
  - proposer boost (in memory only, `StoreTransactionUpdates.java:165-167`);
  - store time (`max(finalized slot time, now)` at load, `KvStoreDatabase.java:879-883`);
  - pulled-up flags (`StoreTransactionUpdates.java:174-182`);
  - deferred attestations (`ForkChoice.java:128`);
  - justified balances (start empty, `ForkChoiceStrategy.java:92-95`);
  - Gloas PTC votes.
- **When written:**
  - **Store transactions:** `StoreTransaction.commit()` applies to the in-memory store without waiting for the DB (`StoreTransaction.java:211-240`). The write goes through `RetryingStorageUpdateChannel`, which retries for up to 1 minute and then **crashes** so a restart reverts to the on-disk state (`RetryingStorageUpdateChannel.java:43-62`). `KvStoreDatabase.doUpdate` writes finalized data first, then hot blocks, checkpoint epochs and the justified/best-justified/finalized/latest-canonical variables in **one** hot transaction (`:1580-1666`, `:1618-1651`).
  - **Votes:** `StoreVoteUpdater.commit()` publishes to `VoteUpdateChannel` (`StoreVoteUpdater.java:97-105`). `BatchingVoteUpdateChannel` merges batches on its own thread (`BatchingVoteUpdateChannel.java:39-58`), then `KvStoreDatabase.storeVotes` writes them in a separate transaction (`:1251-1256`). Commits are triggered from `onBlock`, `processHead` and the attestation paths (`ForkChoice.java:337,359,384,526-553,837-843`).
    - #5903: "it's not an issue if the last batch isn't written as we regenerate the protoarray based on the stored votes".
  - **`LATEST_CANONICAL_BLOCK_ROOT`:** once per epoch at `slot % slotsPerEpoch == 1` (`StoredLatestCanonicalBlockUpdater.java:38-46`; #9203).
- **Atomicity:**
  - One LevelDB `WriteBatch` or one RocksDB transaction per updater (`LevelDbTransaction.java:39,97`; `RocksDbTransaction.java:53-54,146-157`), with default `WriteOptions` and no `setSync`.
  - Votes are never in the block transaction. A vote whose block was lost resolves to no node, so it contributes no weight (`ForkChoiceModelPhase0.java:122-129`; inferred).
- **Migration:**
  - #1627: votes on disk.
  - #2270/#2319: a protoarray snapshot every epoch, to fix the slow startup in #2160.
  - #3124: drop snapshots and rebuild from hot blocks plus per-block checkpoints, because snapshots could drift from the blocks.
  - #4682: legacy snapshot removed.
  - Hot blocks without checkpoints cause a hard failure: "Incompatible database version detected… A re-sync will be required" (`Store.java:427-430`).

### B. Startup and restore: rebuild from hot blocks plus stored votes
1. `StorageBackedRecentChainData.create` calls `initializeFromStorage().join()`. It retries only on timeout (`:169,212-231`).
2. `KvStoreDatabase.createMemoryStore` (`:834-898`):
   - Missing justified, finalized, best-justified or finalized state → throw.
   - Votes are loaded with `getAll` (`:849`).
   - A missing anchor block is synthesized from the finalized state (`:853-867`).
   - Gloas anchor enrichment runs (`:868,900-977`).
3. `buildHotBlockMetadata` (`:336-363`) **streams and fully deserializes every hot block**. It collects slot, root, parent, state root, execution block number/hash/gas limit, checkpoints, and Gloas rebuild data from the stored blinded envelope.
4. `Store.buildProtoArray` (`Store.java:339-392,406-458`) sorts blocks by slot and calls `forkChoiceModelFactory.rebuildBlockNodesFromMetadata(...)`.
   - **Every post-merge node, including the finalized anchor, comes back OPTIMISTIC** (`ProtoArray.java:185`, verified).
   - EL-INVALID blocks are not deleted from the hot DB, so they return as OPTIMISTIC until pruned (inferred).
   - A block with a missing parent silently becomes a root (`ProtoArray.java:177`).
5. **Canonical-head tie-break:** `setInitialCanonicalBlockRoot` adds +1 weight along the stored canonical chain from its best descendant to the root (`ProtoArray.java:200-232`, verified). Hidden override flag: `--Xstore-initial-canonical-block-root` (`StoreOptions.java:63-69`).
   - Origin: incident **#9198** (Holesky Pectra non-finality). After a restart all weights were 0 across 815 leaf heads and the tie-break picked a head about 4 days old. Diagnosed from a `/eth/v1/debug/fork_choice` dump; fixed by #9203.
6. **Votes:** loaded into an array (`Store.java:183-187`). Balances start empty, so the first `applyPendingVotes` sees `oldBalance = 0` for every vote and adds full weight to `nextRoot` (`ProtoArrayScoreCalculator.java:96-104,139-158`). Inferred side effect: nearly every vote is rewritten to the DB in the first batch.
7. **First head:** `ForkChoice.onStoreInitialized` calls `processHead().join()` (`ForkChoice.java:446-453`). If the justified state is unavailable, the head is simply not updated (`:492-497`).
8. **Other checks:** weak-subjectivity checks at load (`BeaconChainController.java:712-714,2698-2716`). There is no unclean-shutdown detection.

### C. EL interaction on restart
- **Order:** `initExecutionLayer`, then `initForkChoiceNotifier`, then `initForkChoice` (`BeaconChainController.java:750-811`). The first `processHead`, after rebuild and vote application, calls `notifyForkChoiceUpdatedAndOptimisticSyncingChanged` (`ForkChoice.java:510-513,1249-1268`). That leads to `ForkChoiceNotifierImpl.onForkChoiceUpdated` (`:115-119,261-311`).
  - The **first fcU is sent after the head is restored**, before `timerService.start`.
  - A zero head hash is skipped, and an unchanged state is re-sent only after 30 s (`ForkChoiceUpdateData.java:33,131-135,210-218`).
- **Results** (`ForkChoice.java:1094-1156`):
  - `VALID` → `markNodeValid` walks ancestors, so one VALID re-validates the whole restored chain (`ProtoArray.java:351-370`).
  - `INVALID` → `markNodeInvalid`, which invalidates the node and its descendants (`:403-449`). An invalid justified node is fatal: `FatalServiceFailureException("Finalized block was found to be invalid.")` (`:243-250,306-308`).
  - `SYNCING` / `ACCEPTED` are ignored.
  - JSON-RPC errors are logged as "Failed to update fork choice." (`ForkChoice.java:230-238`).
- **Too-deep reorg:** zero grep hits; no handling. Inferred consequences:
  - geth's -38006 error is only logged and the nodes stay OPTIMISTIC.
  - An `INVALID` status instead would invalidate in memory only, and a restart would bring the nodes back as OPTIMISTIC.

### D. Debug and dump surfaces
- **v1** `GET /eth/v1/debug/fork_choice` (`data/beaconrestapi/.../v1/debug/GetForkChoice.java:43`; deprecated at `:150-153`):
  - Top-level `extra_data: {}`.
  - Node `extra_data`: `state_root`, `justified_root`, `unrealised_justified_epoch`, `unrealized_justified_root`, `unrealised_finalized_epoch`, `unrealized_finalized_root` (`:48-136`).
  - Iterates **all** `protoArray.getNodes()`, including nodes already removed from the indices (`ForkChoiceStrategy.java:799-806`; `ProtoArray.java:58-66,827-829`).
- **v2** `GET /eth/v2/debug/fork_choice` (`v2/debug/GetForkChoiceV2.java:48`; #10800, #11448):
  - Implements the spec's `data` wrapper with full NodeV2. Node `extra_data` carries `state_root` plus the unrealised fields (`:58-129,148-152,186-203`).
  - Pre-Gloas nodes are reported as `full`. Parent pairing happens under the protoarray lock (`ChainDataProvider.java:361-398`; `ForkChoiceStrategy.java:809-824`).
  - PTC counts are per block root (`GetForkChoiceV2.java:165-170`).
- **Teku-specific:** `/teku/v1/debug/beacon/protoarray` (#4846, "purely intended for debugging… output may change at any time") was **removed** in favor of the standard v1 endpoint in #6599. There are no `/teku/v1` fork choice routes at this SHA.
- **Not exposed anywhere:** votes, proposer boost root, balances, best child/descendant, execution block number and gas limit (present in `ProtoNodeData.java:29-31` but never serialized).
- **Offline:** `teku debug-tools db …` (`teku/.../debug/DebugDbCommand.java`):
  - `get-variables` (`:369`) prints justified, best-justified, finalized, anchor and latest-canonical.
  - `get-column-counts` (`:340`) includes VOTES.
  - `dump-hot-blocks` (`:471-507`) produces a zip of SSZ blocks.
  - `get-hot-block-slot-to-root` (`:510`).
  - `delete-hot-blocks [--delete-all]` (`:947-1020`) is a recovery tool.
  - The old `get-forkchoice-snapshot` (#2561, #3598) is gone; the PR that removed it is UNVERIFIED.
  - No dump loader and no visualizer. `DebugDataDumper` (`--Xdebug-data-dumping-enabled`) dumps invalid blocks and gossip messages, not fork choice (`DebugDataDumper.java:58-75`).

### E. Gloas / ePBS (on master)
- **Node identity:** `ForkChoiceNode(blockRoot, payloadStatus)` (`ForkChoiceNode.java:26-38`; `EMPTY=0, FULL=1, PENDING=2` in `ForkChoicePayloadStatus.java:22-25`). Each variant is a **separate ProtoNode** in one array, indexed by identity (`ProtoArray.java:131-189`). `BlockNodeVariants(slot, base, empty?, full?)` groups them (`BlockNodeVariants.java:29-57`).
- **On block** (`ForkChoiceModelGloas.java:76-146,211-293`):
  - A PENDING node is added under the parent's FULL node if the bid's `parent_block_hash` matches, otherwise under the parent's EMPTY node.
  - An EMPTY child is added immediately. FULL is added only in `onExecutionPayload`.
- **Votes:** slot-aware with a FULL hint. `getSupportedNode` resolves to PENDING if the vote slot ≤ block slot, else FULL if the hint is set, else EMPTY (`:397-418`).
- **PTC votes:** an in-memory map (`PayloadTimelinessCommitteeVoteTracker.java:38-63`). **Not persisted and not rebuilt**: `rebuildBlockNodesFromMetadata` (`:312-358`) never calls `onPtcVote`.
- **Restart:**
  - PENDING/EMPTY are rebuilt from the stored block's bid.
  - FULL is rebuilt only if a blinded envelope is stored (`KvStoreDatabase.java:345-347,865-879`; `StoredBlockMetadata.java:204-239`).
  - fcU verdicts apply to the exact variant that was sent (`ForkChoiceModelGloas.java:574-601`).

### F. Notable PRs and issues
- **#1627:** votes saved to disk.
- **#2160 → #2270/#2319:** slow startup (all states regenerated; 5 GB heap reported after non-finality), fixed with an epoch snapshot.
- **#3124:** snapshots dropped in favor of rebuilding from blocks plus checkpoints, because of drift.
- **#4682:** legacy snapshot removed.
- **#5903:** batched async vote writes.
- **#6245:** separate vote lock.
- **#9198 → #9203:** head regressed about 4 days on restart (zero weights, tie-break across 815 leaves); fixed with the latest-canonical-root hint.
- **#5397:** equivocation flags.
- **#10553 → #10573:** slot-aware vote format with rollback-safe writes.
- **#11058:** non-deterministic deferred equivocating votes.
- **#10556 / #10610:** Gloas model and restart rebuild.
- **#10719 → #10772:** protoarray uint64 underflow under heavy Gloas forks; FULL-hint attestations are deferred.
- **#11333:** Gloas invalidation fixes.
- Dump endpoint history: #2561/#3598 (CLI dump), #4846 (`/teku/v1/debug/beacon/protoarray`), #6599 (standard v1), #10800/#11448 (v2).

---

## 4. Nimbus (status-im/nimbus-eth2 @ 5f7baa634, unstable)

### A. Persistence: not persisted
- **No DB access:** `beacon_chain/fork_choice/*` makes no DB calls, and `beacon_chain_db.nim` has no fork choice, vote or proto-array key.
- **In-memory only:**
  - `ForkChoice{backend, checkpoints, queuedAttestations}` (`fork_choice_types.nim:194-197`).
  - `ForkChoiceBackend` holds `proto_array`, `votes`, `balances`, `ptc_votes`, `timely_proposer_blocks`, the FCR `confirmed` block and Heze IL satisfaction (`:172-186`).
  - `ProtoArray` holds `nodes`, `indices`, `fullBlockIndices`, `unrealized`, and the previous proposer boost root/score (`:110-119`).
- **Lost or re-derived on restart:**
  - Checkpoints are re-derived from the head state and EpochRefs (`fork_choice.nim:75-94`).
  - Balances come from `EpochRef.fork_choice_balances`.
  - Proposer boost resets to zero.
  - Equivocations are stored only as `vote.slot = FAR_FUTURE_SLOT` (`fork_choice.nim:424-434`).
  - Time is set to wall clock (`attestation_pool.nim:209-211`).
  - Unrealized checkpoints, queued attestations, the FCR confirmed block (reset to finalized, `fork_choice.nim:67-69`), Gloas FULL nodes and PTC tallies are all lost.
- **What is persisted (SQLite `nbc.sqlite3`):**
  - Blocks, blobs/columns, envelopes, `stateRoots`, `statesNoVal` plus immutable validators.
  - Block `summaries` `{slot, parent_root}` "for fast startup" (`beacon_chain_db.nim:112-162,192,212-218`) and `finalizedBlocks`.
  - Pointers in `keyValues`: `kHeadBlock`, `kTailBlock`, `kGenesisBlock`, and **`kHeadBlocks`**, "List of pointers to all head blocks in the fork choice. v26.7.0+" (`:164-210`):
    ```nim
    proc putHeadBlocks*(db: BeaconChainDB, keys: seq[Eth2Digest]) =   # beacon_chain_db.nim:1114-1116
      doAssert keys.len > 0
      db.keyValues.putSSZ(subkey(kHeadBlocks), keys)
    ```
  - States are stored at epoch boundaries only; after finality, one snapshot every 32 epochs (`blockchain_dag.nim:59-62,817-830`).
- **Encoding:** snappy-framed SSZ (`beacon_chain_db.nim:75-76`). `DbKeyKind` is append-only ("You should never remove entries", `:165-166`). There is no fork choice schema. #8590 notes that `kHeadBlocks` must tolerate stale entries after upgrade → downgrade → upgrade.
- **Write timing:**
  - Block import does `dag.putBlock` then `dag.registerHead`, which leads to `putHeadBlocks` (`block_clearance.nim:97-99`; `blockchain_dag.nim:73-74,1171-1181`).
  - A head change writes `putHeadBlock` after the head state update (`:2836-2848`).
  - Finalization rewrites the head list (`:2282-2283,2925-2940`).
  - The WAL is checkpointed at the end of every slot (`nimbus_beacon_node.nim:1606-1608`; `manualCheckpoint = true`, `beacon_chain_db.nim:702-703`).
- **Crash model:** explicitly "mostly-consistent". Sqlite autocommits, and the rule is "write bulk data first, then update pointers like the `head root` entry" (`beacon_chain_db.nim:84-98`). `withManyWrites` is only a speed optimisation: "We don't enforce strong ordering or atomicity requirements" (`:461-470`). DB errors panic (`expectDb`, `:273-276`).

### B. Startup and restore: replay non-finalized blocks of every head through fork choice
- **`ChainDAGRef.init`** (`consensus_object_pools/blockchain_dag.nim:1384-1572`):
  - Missing tail or head → `expect("head root, database corrupt?")` (`:1400-1407`).
  - `loadHead` walks block summaries from the head back to finalized, then replays from the newest stored state (`:1183-1312`).
    - A missing block moves the head back (`:1243-1262`).
    - `--debug-invalidate-block-root` resets the head to the parent (#8582; `:1225,1268-1269`).
  - Extra heads come from `kHeadBlocks` (`:1550-1557`), and orphaned ancestors are pruned (`:1341-1353,1561-1570`).
  - Fatal: "Head does not lead to finalized block, database corrupt?" (`:1510-1517`) and "Could not load head state" (`:1288-1292`).
  - The only crash-specific repair: finalized blocks are topped up if "the application might have crashed between the head and finalized blocks updates" (`:1495-1505`).
- **Fork choice rebuild** (`attestation_pool.nim:199-233`, verified):
  ```nim
  var forkChoice = ForkChoice.init(dag.cfg.CONFIRMATION_BYZANTINE_THRESHOLD,
    finalizedEpochRef, dag.finalizedHead.blck, currentSlot, wallTime)
  ...
  forkChoice.loadHead(dag, dag.head, shallow)
  for additionalHead in dag.heads:
    forkChoice.loadHead(dag, additionalHead, shallow)
  ```
  - `ForkChoice.init` seeds only the finalized block, with justified = finalized (`fork_choice.nim:75-94`).
  - `loadHead` (`attestation_pool.nim:142-197`) replays from oldest to newest:
    - Blocks within `ForkChoiceHorizon = 256` ancestors of any head (`:124-140`) go through full `forkChoice.process_block` with the block body.
    - Older blocks get a cheap `backend.process_block(bid, parent, epochRef.checkpoints)` with a stale EpochRef, refreshed every 1024-slot interval (`:163-171`; #8578, evolved from #1910).
- **Votes:** gossip votes are lost. They are reconstructed only from attestations in replayed blocks within the 256-block horizon (`fork_choice.nim:498-515`, target must match).
  - Attester slashings in those blocks become equivocations (`:492-496`).
  - Gloas `payload_attestations` are kept only from the last slot (`:519-529`).
- **Unrealized checkpoints:** computed only for `dag.head`; every other block gets `default(FinalityCheckpoints)` (`attestation_pool.nim:178-191`, verified). Store time is already wall time, so a head from an earlier epoch is pulled up immediately (`fork_choice.nim:552-562`).
- **Hard failures, no fallback:** `getEpochRef(...).expect`, `getForkedBlock(...).expect`, and `doAssert status.isOk(), "Error preloading the fork choice"` (`attestation_pool.nim:173-177,197`).
- **Execution validity:** not restored. Blocks come back `notValidated` (Gloas: `missing`) until the first VALID fcU (`block_dag.nim:89-108,319-333`). `headPayloadFull` defaults to false (`blockchain_dag.nim:2959-2970`).

### C. EL interaction on restart
- **No startup fcU.**
  - `elManager.start()` runs after networking init (`nimbus_beacon_node.nim:2285-2287`).
  - `onSlotStart` only does a DAG head update (`:1849`; `consensus_manager.nim:249-264`).
  - `updateExecutionHead` is called only after a block import (`block_processor.nim:841`) or a Gloas envelope import (`:1100`, #8956).
  - The light-client fcU path runs only when the LC head is ≥64 slots ahead (`consensus_manager.nim:175-190`).
  - The proposal fcU is gated on `isSynced`, which requires `dag.head.executionValid` (`:266-278,290-291,341-450`).
  - `safeBlockHash` is the finalized hash until FCR re-advances (`attestation_pool.nim:969-984`).
- **INVALID handling** (`consensus_manager.nim:606-625`):
  - Pre-Gloas: `mark_root_invalid` plus unviable quarantine.
  - Gloas: `mark_payload_invalid`, which marks only the FULL variant.
  - `latestValidHash` is discarded (`:503`).
  - With multiple ELs, any disagreement counts as invalid (`el_manager.nim:1039-1042`).
- **Too-deep reorg:** no handling. Inferred: an `INVALID` *status* would put the head in unviable quarantine; -38006 error handling was not traced (UNVERIFIED).
- **Manual knob:** `--debug-invalidate-block-root`, with a documented restart procedure (`conf.nim:583-609`).

### D. Debug and dump surfaces
- **v1** `GET /eth/v1/debug/fork_choice` (`beacon_chain/rpc/rest_debug_api.nim:113-174`; types `rest_types.nim:667-701`). **No `data` wrapper** (#4810; format updated in #4802).
  - Top-level `extra_data`: `confirmed_root`, `current_epoch_observed_justified_checkpoint`, `previous_epoch_greatest_unrealized_checkpoint`, `previous_slot_head`, `current_slot_head` (`:120-127`).
  - Node `extra_data`: `justified_root`, `finalized_root`, `u_justified_checkpoint` / `u_finalized_checkpoint` (only when they differ), `best_child`, `best_descendant`.
  - `weight` includes the proposer boost (`proto_array.nim:279-294,873`).
  - `execution_block_hash` **loads the block from the DB for every node on every request** (`rest_debug_api.nim:165`; `blockchain_dag.nim:1113,2573-2574`).
  - The data source is `iterator items(ProtoArray)` (`proto_array.nim:836-876`, verified).
- **Other endpoints:** no v2 and no Nimbus-specific fork choice dump.
  - `rest_nimbus_api.nim` has `/nimbus/v1/chain/head` (`:160-174`), `/nimbus/v1/debug/chronos/*`, `/nimbus/v1/debug/gossip/peers`, `/nimbus/v1/debug/sync/*`, and `/nimbus/v1/debug/struct/{sidecarless|missing|orphans|unviables|…|envelope_quarantine}` (`:674-697`).
  - `--dump` writes SSZ blocks and states (`conf.nim:578-581`).
- **Offline:** `ncli_db` has `bench`, `dumpState`, `putState`, `dumpBlock`, `putBlock --set-head/--set-tail/--set-genesis` (the only offline head-pointer repair), `rewindState`, `verifyEra`, `exportEra`, `importEra`, `validatorPerf`, `validatorDb` (`ncli_db.nim:41-52,117-133,472-497`).
  - No fork choice dump loader.
  - The test harness only reads EF spec tests (`anchor_state.ssz_snappy` + `steps.yaml`, `tests/consensus_spec/test_fixture_fork_choice.nim:100-119,615-642`).

### E. Gloas / ePBS (on unstable)
- **Node model:** there is no separate PENDING node. The base node in `indices` is EMPTY. A FULL sibling is appended by `onPayloadVerified` and indexed in `fullBlockIndices` (`proto_array.nim:413-441`), called only from `on_execution_payload` (`fork_choice_epbs.nim:257-282`).
  - PENDING is implicit: `findHead` chooses between the two variants (`proto_array.nim:462-482`).
  - `pendingWeight` tracks same-slot votes for the tiebreak (`fork_choice_types.nim:127`).
  - A child attaches to the parent's FULL or EMPTY node by `parent_payload_status`, derived from `bid.parent_block_hash` (`fork_choice.nim:544-550`).
- **PTC:** `ptc_votes` is a 2-slot ring of `Table[root, PtcVoteTally{voted, present, available: BitArray[PTC_SIZE]}]` (`fork_choice_types.nim:158-161,182-183`; `fork_choice_epbs.nim:20-107`).
- **Dump:** `items` yields EMPTY and FULL with the same `bid`, so **v1 emits duplicate `block_root` rows with no payload-status field**. `best_child` and `best_descendant` are variant-ambiguous, and PTC tallies are not exposed.
- **Restart gap (inferred, not tested):** `on_execution_payload` is called only at envelope import (`block_processor.nim:1089`), and an envelope already in the DB is rejected as `Duplicate` (`:1044-1045`). So FULL variants of already-imported non-finalized blocks are not re-created, and children that built on FULL attach to EMPTY. No issue found (search was rate-limited).

### F. Notable PRs and issues
- **#8590 / #8656 / #8679:** persist all DAG heads (`kHeadBlocks`); reverted then re-landed in June 2026. The reason for the revert is UNVERIFIED.
- **#8578:** EpochRef refreshed every 1024 slots so checkpoints are monotonic; slower startup under long non-finality.
- **#1910:** fork choice init horizon, for slow startup on non-finalizing chains.
- **#3320:** finalized block roots table; mainnet startup took 3 s.
- **#1899:** avoid DB hits during replay.
- **#6109:** only the canonical chain is loaded at startup (predates #8590).
- **#8582:** honor `--debug-invalidate-block-root` at init.
- **#3954:** restart crash loop when a block between head and finalized was missing after an EL INVALID.
- **#5328:** `getDebugForkChoice` crash. Hit on devnet-8, where the endpoint is **polled every slot**.
- **#4802 / #4810:** v1 format aligned with the spec.
- **#7457:** CL head first, EL lazily. **#8956:** fcU on envelope import.
- **#8430 / #8543:** Gloas dual EMPTY/FULL; prune rebuilds the array because late FULL nodes broke the index invariant.
- **#6425:** malformed DB after a crash (attributed to the environment).
- No issues found for votes lost or a different head after restart (search was rate-limited).

---

## 5. Grandine (grandinetech/grandine @ 3b0a5ac, develop)

### A. Persistence: no store snapshot; anchor plus canonical blocks
- **Store is memory-only:** `Store` (`fork_choice_store/src/store.rs:130-307`) is never serialized. The comment at `:155-157` still says "when persistence is implemented" (verified). Persistence goes through `fork_choice_control/src/storage.rs`.
- **Keys** (string-prefixed, in one libmdbx DB):

| Key | Content | Ref |
|---|---|---|
| `cstate2` | `StateCheckpoint{block_root, head_slot, state}` | `storage.rs:1562-1579` |
| `cblock` | anchor block | `:1581-1599` |
| `r{slot}` | root by slot | `:1601-1625` |
| `b{root}[b]` | finalized blocks, optionally blinded | `:1627-1687` |
| `b_nf{root}` | unfinalized blocks | `:1709-1715` |
| `s{root}`, `t{root}` | states / slot by state root | `:1717-1731` |
| `finalized_validators` | pubkey list used to re-inflate states | `:1733-1755` |
| `e`, `v` | Gloas envelopes | `:1799-1884` |

- **Not persisted** (`Store::new`, `store.rs:365-425`):
  - latest messages, proposer boost, equivocating indices;
  - justified/finalized/unrealized checkpoints (reset to the anchor);
  - balances, tick, queued attestations, `checkpoint_states`;
  - all Gloas `payloads`, `timely_payloads` and PTC vote maps;
  - **per-block payload validity.** From `queries.rs:54-57` (verified):
    ```rust
    // TODO(Grandine Team): There is currently no way to persist payload statuses.
    //                      We previously treated blocks loaded from the database as optimistic.
    //                      Doing so is safe but produces misleading API responses for finalized blocks.
    //                      We now store only valid blocks in the database.
    ```
- **`Storage::append` (`storage.rs:330-465`)** stores only the **canonical chain**, filtered to valid links (`:345-351`), so side forks are lost.
  - The `cstate2` checkpoint is the first finalized epoch-start link (`:400-430`; #607/#609).
  - Archival states are written every `--archival-epoch-interval` epochs (default 32).
  - In `--prune-storage` mode, unfinalized blocks are not written, which contradicts `book/src/storage.md:15`.
- **When written:**
  1. **Unfinalized blocks only at clean shutdown:** `handle_stop` (`mutator.rs:3149-3177`, verified), triggered by SIGINT/SIGTERM or by `Drop` with `save_to_storage = !std::thread::panicking()` (`controller.rs:104-109,1160-1163`).
  2. **At finalization:** `archive_finalized` (`mutator.rs:5207-5297`) runs on a detached thread; failures are only logged. Pruning is a separate transaction.
  3. **Under long non-finality:** evicted states are persisted (`mutator.rs:3311-3365`).
  4. **Gloas envelopes:** written eagerly (`mutator.rs:3688-3696`).
- **Encoding:** SSZ + snappy (`storage.rs:1934-1939`), zstd for blinded blocks, payloads and envelopes. Persisted states have pubkeys zeroed and restored on load (`:1962-1976,1298-1327`; #611/#907).
- **Versioning:** `meta.json` `SCHEMA_VERSION = "0.2.3"` with no migration code (`runtime/src/schema.rs:13-115`); the `cstate` → `cstate2` rename was done for compatibility.
- **Atomicity:**
  - Each `append` is one libmdbx RW transaction (`storage.rs:456`; `database/src/lib.rs:618-660`).
  - `MapFull` triggers a restart (`database/src/lib.rs:833-847`; #197).
  - On unclean exit (SIGKILL, OOM, mutator panic), **every unfinalized block since the last clean stop is absent** from the DB.

### B. Startup and restore: anchor state plus full re-import of persisted canonical blocks
- **Strategy:** local state first, then checkpoint sync. `--force-checkpoint-sync` overrides. `--force-reset-beacon-db` is the only corrupt-DB escape hatch (`runtime.rs:1084-1104,1181-1194`; `storage.rs:173-208`).
- **`Storage::load`** (`storage.rs:149-309`):
  - Reads `cstate2` and `cblock`, then checks `CheckpointBlockRootMismatch` and that the state is at epoch start (`:1152-1169`).
  - Blocks to replay are all `r{slot}` entries after the state slot (`:1171-1184`).
  - Without a checkpoint it falls back to iteration (`:311-327,1192-1242`; `--state-slot N`).
  - A blinded block in the replay set is a hard `PayloadPruned` error (`:299-304`).
- **Rebuild** (`Controller::new`, `controller.rs:119-231`):
  - `Store::new(anchor)` runs, then `apply_tick(now)`.
  - Then `process_unfinalized_blocks` runs synchronously, before any service starts (`:196`).
  - Blocks are re-imported as `BlockOrigin::Persisted` with `StateRootPolicy::Trust`, `DataAvailabilityPolicy::Trust` and `NullVerifier`, so signatures are skipped (`mutator.rs:428-480`; `fork_choice_store/src/misc.rs:391-415`).
  - Errors abort startup; there is no fallback.
- **Votes:**
  - Block-included attestations are re-applied with the previous-epoch cutoff bypassed for `is_from_block` (`mutator.rs:3485,5058-5080`; `store.rs:5523`).
  - Attester slashings in blocks are re-applied (`mutator.rs:3505-3520`).
  - Gossip votes and proposer boost are lost.
- **Validity:** pre-Gloas replayed blocks come back `Optimistic` (`store.rs:6261-6295`).
- **Unclean shutdown:** no special handling. The node resumes from the last finalization-time `cstate2` and range-syncs.

### C. EL interaction on restart
- **No dedicated startup fcU.** Only `exchange_capabilities` runs at startup (`runtime.rs:247-250`).
- **Replay drives the EL:** it uses the real execution engine, so each pre-Gloas block emits `notify_new_payload`, and each canonical extension emits `notify_forkchoice_updated` (`mutator.rs:3547-3577`).
  - These calls enqueue onto an unbounded channel that drains only once `ExecutionService::run` starts (`eth1_api/src/eth1_execution_engine.rs:58-92`; `runtime.rs:842-860`).
  - So the head is restored first, then the EL receives `newPayload`/`fcU` in replay order, **starting from blocks near the anchor**.
- **Duplicate fcU pre-Gloas** (`mutator.rs:3566-3573`).
- **Responses:**
  - fcU `INVALID` or `SYNCING` is only logged; `latest_valid_hash` is only used to mark blocks valid (`execution_service.rs:189-207`; `mutator.rs:3023-3040`).
  - `newPayload` `INVALID` invalidates the payload and its descendants (`mutator.rs:3083-3085`).
- **Too-deep reorg:** no handling. Inferred: early replay fcUs for blocks >32 behind geth's head get -38006 and are only logged.

### D. Debug and dump surfaces
- **v1 only** (`http_api/src/routing.rs:538`; `standard.rs:2580-2588`; builder `fork_choice_control/src/queries.rs:225-254`, verified):
  - **Unfinalized nodes only** (the anchor is absent).
  - **No `extra_data`**.
  - `weight` is the PENDING balance.
  - `execution_block_hash` defaults to `0x00` "for protovis" (`queries.rs:1451-1455`).
- **Other endpoints:**
  - `/eth/v2/debug/beacon/heads` includes non-viable tips (`queries.rs:206-223`).
  - Tracing level via `/eth/v2/debug/tracing/*`.
  - `GET/PATCH /features` runtime toggles, `/system/stats`.
  - Prometheus gauges for store collection lengths (`store.rs:6863-6975`).
  - `Feature::Dump*` writes SSZ blocks, states, sidecars and aggregates (`data_dumper/src/lib.rs:19,151-156`).
- **Offline commands** (`runtime/src/commands.rs:16-73`): `db-info`, `db-stats`, `export --from --to` (finalized blocks and states), and `replay` (re-execute exported blocks, assert the state root) (`fork_choice_control/src/storage_tool.rs:29-144`). None of them touch the fork choice store, and there is no dump loader.

### E. Gloas / ePBS (on develop)
- **Model:** one `ChainLink` per block with `payload_status` (validity) and `parent_payload_presence` (Grandine's name for the spec's PayloadStatus) (`fork_choice_store/src/misc.rs:56-169`).
  - `AttestingBalances { empty, full, pending }` (`:182-187,247-251`).
  - `LatestMessage.payload_present` (`:1685-1691`).
  - PTC votes are three `HashMap<H256, BitVector<PtcSize>>` (`store.rs:208-213,4708-4750`).
  - Head EMPTY/FULL is resolved at query time (`:965-1032`).
- **Persistence:** envelopes only. PTC votes from blocks' `payload_attestations` are re-applied on replay (`mutator.rs:3486,5082-5106`).
- **Known restart gap:** envelopes are not replayed, so a child of a FULL parent hits `DelayUntilPayload` (`store.rs:2152-2156`) and the node has to range-sync. Issue **#886**; fix in open PR **#887**, which also adds a `TimelyEnvelopeByBlockRoot` key.
- **Dump:** no Gloas fields.

### F. Notable PRs and issues
- **#886 / #887:** envelopes not loaded at restart; fix open.
- **#708:** MDBX durable sync; multiple transactions per finalization.
- **#50:** MapFull after about 4 months of uptime. **#197:** restart on storage-save failure.
- **#956 → #954:** fork choice stuck for 2 days, recovered only by restart.
- **#839:** mutator panic → `save_to_storage = false` → unfinalized blocks not saved.
- **#145:** prune unfinalized blocks on finalization.
- **#607 / #609:** checkpoint state cadence during sync.
- **#611 / #907:** pubkey stripping and its fix.
- **#851** (open): sync from a non-finalized checkpoint, since Grandine assumes a finalized anchor.
- No issues found for votes lost or a different head after restart: UNVERIFIED (search was rate-limited).

---

## 6. Comparison summary

| | Lighthouse | Prysm | Teku | Nimbus | Grandine |
|---|---|---|---|---|---|
| Fork choice persisted? | **Yes, full snapshot** (proto-array, votes, store scalars) | No | **Inputs only:** votes, per-block realized and unrealized checkpoints, store checkpoints, canonical-root hint | No (head pointers plus all-heads list) | No (finalized anchor state plus canonical unfinalized blocks) |
| Format | SSZ + zstd, superstruct V28/V29, DB schema v31 with up/down migrations | n/a | Custom fixed-width serializers; vote format detected by length | n/a (SSZ head-root list) | n/a (SSZ + snappy blocks/states) |
| Write cadence | Epoch change, reorg, finalization (before migration), shutdown | n/a | Every store transaction; votes batched async | n/a | Finalization, plus clean shutdown for unfinalized blocks |
| Atomic with block DB? | No. Fork choice lags the DB, never leads it (lock held across the block write; poison on failure) | n/a | Hot data in one transaction; votes separate | Pointer-after-data ordering, no atomicity | Per-append transaction; unfinalized blocks lost on crash |
| Restore | Load snapshot, tick to now, `get_head` | Finalized + **one chain to justified** (default), no attestation replay | Rebuild protoarray from all hot blocks, apply votes, canonical +1 hint | Replay non-finalized blocks of **all heads** (256-block full horizon) | Full block re-import of persisted canonical chain (signatures skipped) |
| Votes after restart | Persisted (queued attestations lost) | Lost | Persisted (last batch may be lost) | From block attestations within horizon | From block attestations |
| Validity after restart | Persisted; reset to optimistic if any invalid, or with `--reset-payload-statuses` | Optimistic (finalized VALID if it matches the last-validated checkpoint) | **All OPTIMISTIC**, including the anchor | Not validated | Optimistic pre-Gloas; DB only holds valid blocks |
| Startup fcU | After head restore, fire-and-forget | **None** until regular sync (Gloas: per batch) | After first `processHead` | **None** until first import | Implicit, in replay order once the EL service runs |
| -38006 / too-deep handling | None | None | None | None | None |
| v1 `extra_data` | Rich (unrealized, target, `execution_status`, …) | Rich (+ balance, timestamp, boost roots, head) | Unrealized + state root | Rich (+ confirmed root, prev/current slot head) | **None**; anchor omitted |
| v2 endpoint | Open PR #10215 | Yes (#16862) | Yes (#10800, #11448) | No | No |
| Client-specific dump | `/lighthouse/proto_array` (full internal array) | None (gRPC removed) | None (`/teku/v1/debug/beacon/protoarray` removed in #6599) | None | None |
| Offline tooling | `db inspect --column frk` (raw blob, **no decoder**) | None for fork choice | `debug-tools db get-variables / dump-hot-blocks / delete-hot-blocks` | `ncli_db` (blocks/states only) | `export` / `replay` / `db-stats` |
| Load a dump into node or harness | No | No | No (the restart path is effectively a loader for its own DB) | No (spec-test format only) | No |
| Gloas PTC votes persisted | **Yes** (bitvectors in V29 nodes) | No | No | No | No (re-applied from block `payload_attestations`) |
| Gloas FULL variant after restart | Persisted | Re-derived from bids + DB envelope | Rebuilt if a blinded envelope is stored | **Not re-created** (inferred gap) | **Replay stalls** (#886) |
| Gloas variant model | One node per block, virtual PENDING/EMPTY/FULL | PENDING node + EMPTY/FULL `PayloadNode`s | Three separate ProtoNodes keyed by `(root, status)` | EMPTY base + appended FULL, implicit PENDING | One `ChainLink`, per-status balances |

Other points:
- **Nobody exposes votes, balances or proposer boost over HTTP.** Lighthouse's on-disk blob is the only artifact containing votes plus PTC bitvectors, and it has no decoder.
- **Nobody can load a fork choice dump back into a node or test harness.** The only cross-client loadable format is the EF spec-test fixture (`anchor_state` + `steps.yaml`).
- **The v1 endpoint is broken or ambiguous for Gloas in practice:**
  - Nimbus emits duplicate `block_root` rows.
  - Lighthouse emits `null` / `not_yet_revealed` validity.
  - Teku emits `optimistic`.
  - That is beacon-APIs #639, and the reason v2 exists.

---

## 7. Ideas worth stealing for Lodestar

Each idea cites its source. These are suggestions, not decisions.

1. **Persist inputs, not derived state; rebuild deterministically** (Teku #3124, `Store.java:406-458`). The inputs are: blocks + per-block realized/unrealized checkpoints + votes + store checkpoints. Teku moved away from snapshots because they drifted from the blocks.
   - If a full snapshot is also kept (Lighthouse style), treat it as a cache that can be validated against the block DB.
2. **Version and compress the format explicitly** (Lighthouse superstruct `V28`/`V29` + zstd, `persisted_fork_choice.rs:65-74`; `schema_change/README.md`). Use a version tag and step migrations that are atomic with the version bump (`schema_change.rs:15-75`).
   - Teku's length-detected vote format, which keeps writing the legacy layout before the fork so rollback stays possible (`VoteTrackerSerializer.java:26-38`), is a lighter alternative.
3. **Don't persist balances; recompute them from the justified state** (Lighthouse #7805: dropping the balances cache saved ~65 MB on mainnet, plus ~16 MB for justified balances).
4. **Persist on epoch boundary, reorg, finalization and shutdown, not per block** (Lighthouse `canonical_head.rs:1565-1568,1719-1721`, `beacon_chain.rs:8021-8043`; #851). Persist **before** finalization pruning or migration (#10165).
5. **Never persist a fork choice that diverged from the DB.** Use a "poisoned" flag set on DB write failure, then shut down (Lighthouse #9818/#9819, `canonical_head.rs:1750-1757`). Teku's equivalent is retrying the write for 1 minute and then crashing (`RetryingStorageUpdateChannel.java:43-62`).
6. **Batch vote persistence asynchronously; losing the last batch is acceptable** (Teku #5903, `BatchingVoteUpdateChannel.java:39-58`).
7. **Store a canonical-head hint to break zero-weight ties on restart** (Teku #9203, `ProtoArray.java:200-232`). Without it, Teku restarted onto a head about 4 days stale during Holesky non-finality (#9198).
8. **Persist the list of all DAG heads** so side branches survive restarts (Nimbus `kHeadBlocks`, #8590, `beacon_chain_db.nim:1114-1116`).
9. **On load, tick slot by slot from the persisted time to now**, so pull-ups and proposer-boost resets happen as they would have live (Lighthouse `fork_choice.rs:579-587,1521-1582`).
10. **Provide recovery knobs:**
    - reset all payload statuses to optimistic (Lighthouse `--reset-payload-statuses`, #3498);
    - manually invalidate a root at startup (Nimbus `--debug-invalidate-block-root`, #8582);
    - delete hot blocks (Teku `debug-tools db delete-hot-blocks`).
11. **Offer an on-demand invariants endpoint** for fork choice vs DB consistency (Lighthouse `/lighthouse/database/invariants`, `beacon_chain/src/invariants.rs:18-82`).
12. **Expose two dump tiers:**
    - (a) the standard v2 endpoint (`(root, payload_status)` nodes, `parent_payload_status`, Checkpoint objects, PTC counts). Put head root + head payload status, proposer boost root and unrealized checkpoints in top-level `extra_data` (Lighthouse #10215, Prysm v1 `extra_data`, Nimbus `current_slot_head` / `previous_slot_head`).
    - (b) a full internal dump, like Lighthouse `/lighthouse/proto_array`. It should go beyond what any client exposes today: votes, balances, proposer boost root/score, equivocating indices, PTC bitvectors, queued attestations and store time.
13. **Close the gap nobody has closed: make the dump loadable.** Ship an offline decoder/loader (Lighthouse has a raw `frk` dump but no decoder: `lcli/src/parse_ssz.rs:66-119`) so a dump can be loaded into a fork choice instance in tests or a CLI to reproduce `get_head`. #4332 was debugged from a user's DB dump plus Forky; a loader would make that routine.
14. **Keep the debug endpoint cheap.** Nimbus does one DB read per node per request (`rest_debug_api.nim:165`), and devnets poll it every slot (#5328). Serve it from in-memory node data.

## 8. Pitfalls seen in other clients

- **Format changes without a migration** fail to decode on upgrade (Lighthouse #1833, "InvalidByteLength").
- **Snapshot drift.** Snapshots drifting from the block DB led Teku to drop them (#3124). Fork choice ahead of disk caused "Head block not found in store" (Lighthouse #2028).
- **Snapshot size.** The fork choice blob is big and grows during non-finality (Lighthouse #7760/#7805).
- **Semantics changing in a migration:**
  - Epoch→slot votes zeroed slots, so older attestations could roll back latest messages (Lighthouse #10089, won't fix, `proto_array_fork_choice.rs:64-70`).
  - Proposer boost was baked into persisted weights and had to be subtracted at migration (`migration_schema_v29.rs:54-96`).
- **Ordering versus finalization:** a persisted finalized checkpoint below the split caused a startup loop (Lighthouse #10142 → #10165).
- **Zero weights after restart** led to an arbitrary tie-break and a stale head (Teku #9198).
- **Votes lost on restart** (Prysm: all; Nimbus and Grandine: everything not included in blocks). Prysm's default restart head is the justified checkpoint (`setup_forkchoice.go:33-39`), and every restored block gets the store's justified checkpoint (#10777).
- **Validity not persisted:** everything is OPTIMISTIC until the EL answers (Teku `ProtoArray.java:185`; Prysm; Nimbus). Grandine gave up and stores only valid blocks (`queries.rs:54-57`).
- **Slow startup from replay or state regeneration** (Teku #2160; Nimbus #1910, #8578). Teku deserializes every hot block on startup (`KvStoreDatabase.java:336-363`).
- **Crash windows:** Grandine writes unfinalized blocks only on clean shutdown (`mutator.rs:3149-3177`), and on a mutator panic it skips the save (#839).
- **Recovery code rots:** Lighthouse `fork_revert` became dysfunctional after Altair and was deleted (#4198, #8891).
- **"Delete your DB" as the fix** for fatal fork choice setup errors (Prysm #15468/#12367/#13153 until #16478).
- **Gloas restart gaps:**
  - FULL variants or envelopes not restored: Nimbus (inferred), Grandine #886 (open), Prysm #17497.
  - PTC votes lost everywhere except Lighthouse.
- **Gloas v1 dump ambiguity:**
  - duplicate `block_root` rows (Nimbus);
  - `null` validity (Lighthouse, beacon-APIs #639);
  - different `execution_block_hash` for pending nodes (Prysm used `bid.block_hash`, Teku `bid.parent_block_hash`; the spec settled on `parent_block_hash` in #615).
- **No fcU during init sync starves the EL** post-Gloas (Prysm #17273/#17275).
- **Deep-reorg guard (geth `EngineMaxReorgDepth=32`, execution-apis `-38006`):**
  - **No CL handles it.**
  - Restart paths that send fcU for a head well behind the EL are exposed:
    - Grandine replays from the anchor and emits fcU per block.
    - Prysm's default head is the justified checkpoint.
    - Lighthouse after a crash may restore a snapshot up to about an epoch old.
    - All of this is inferred from code, not reproduced.
  - geth returns a JSON-RPC error, which Lighthouse, Teku and Grandine only log.
  - If an EL instead returned `INVALID` *status*, Lighthouse, Teku, Nimbus and Prysm would invalidate the head as if it were a real invalid payload (inferred).
  - geth itself had an underflow bug on forward updates after an unclean EL shutdown (#35804, fixed 2026-10-08).
