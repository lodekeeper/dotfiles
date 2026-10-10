# Lodestar: current state relevant to a "fork choice dump"

- Repo read: `ChainSafe/lodestar` `origin/unstable` @ **`b726a05a4df34068d21b254bf5c590ea75afd169`** (2026-10-09, "feat: reject proposer data and validator registrations from gloas (#10341)"), via `git show origin/unstable:<path>` in `~/ethereum-repos/lodestar` (shallow clone; PR history via `gh`, read-only).
- All `path:line` refs below are at that SHA. Paths are relative to repo root.
- Short refs: `chain/…`, `sync/…`, `execution/…`, `api/impl/…`, `db/…`, `node/…`, `metrics/…`, `network/…` → `packages/beacon-node/src/`; bare `importBlock.ts`, `importExecutionPayload.ts`, `verifyBlocksExecutionPayloads.ts` → `packages/beacon-node/src/chain/blocks/`; bare `http.ts`, `utils.ts`, `jsonRpcTransport.ts`, `jsonRpcHttpClient.ts`, `restTransport.ts` → `packages/beacon-node/src/execution/engine/`; `persistentCheckpointsCache.ts` → `chain/stateCache/`; `archiveStore.ts` → `chain/archiveStore/`; `frequencyStateArchiveStrategy.ts` → `chain/archiveStore/strategies/`; `opPool.ts`, `proposerPreferencesPool.ts` → `chain/opPools/`; `seenPayloadEnvelopeInput.ts` → `chain/seenCache/`; `gossipHandlers.ts` → `network/processor/`; `forkChoice.ts`, `store.ts`, `safeBlocks.ts`, `fastConfirmation/*` → `packages/fork-choice/src/forkChoice/`; `protoArray.ts`, `protoArray/interface.ts` → `packages/fork-choice/src/protoArray/`; route files `debug.ts`, `lodestar.ts` → `packages/api/src/beacon/routes/`; `checkpointState.ts`, `prepareStateInitialization.ts` → `packages/cli/src/cmds/beacon/stateInitialization/`; `handler.ts`, `initBeaconState.ts`, `options.ts` (CLI) → `packages/cli/src/cmds/beacon/`.
- "UNVERIFIED" = not confirmed from code/PR text.

---

## TL;DR

1. **Restart = re-sync from the finalized checkpoint.** On shutdown Lodestar archives the *finalized* checkpoint state (`archiveStore.persistToDisk()`), on startup it boots from the latest archived state (`isFinalized: true`), builds a 1-node ProtoArray from it, **deletes all persisted checkpoint states from the previous run**, and re-downloads every unfinalized block (+ Gloas envelopes) from peers via range sync. Unfinalized blocks already in the hot DB are **not** replayed into fork choice. `chain.close()` literally says `// TODO: persist fork choice to disk` (`packages/beacon-node/src/chain/chain.ts:569-571`).
2. **fcU on catch-up:** every block import that changes head sends `engine_forkchoiceUpdated` (no sync/optimistic/distance gating). Head starts at the finalized block (~2-3 epochs behind tip), so the first fcUs point well behind the EL's head. geth (guard since v1.17.3 per PR/release metadata, default 32, `--engine.maxreorgdepth`) answers with a **JSON-RPC error `-38006 "Too deep reorg"`**, not a `payloadStatus: INVALID` result (geth's Go handler returns `STATUS_INVALID` *and* a non-nil error; the error wins on the wire). Lodestar therefore never reaches its `INVALID` branch: the transport throws `ErrorJsonRpcResponse`/`HttpRpcError`, engine state flaps to `SYNCING`, and the import path logs `"Error pushing notifyForkchoiceUpdate()"`. **Fork choice is not touched** on unstable (invalidation only happens on the `newPayload` path). Open PR **#9332** would add fcU-`INVALID` → `validateLatestHash` invalidation; it keys off `payloadStatus.status === INVALID`, so geth's error form would not trigger it, but an EL that reports reorg-depth refusal as a `payloadStatus` `INVALID` would (risk, see §2.3). No reorg-depth guard exists in Lodestar.
3. **Nothing fork-choice-related is persisted today.** Persisted: finalized/archived states, hot (unfinalized) blocks + envelopes + sidecars, checkpoint states (but wiped at boot), op pool, proposer preferences (#10327), earliest available slot (#10267). Not persisted: ProtoArray, votes, balances, equivocating indices, proposer boost, PTC votes, FCR store, timeliness flags.
4. **Debug surfaces:** `/eth/v1/debug/fork_choice`, `/eth/v2/debug/fork_choice` (Gloas variants + PTC counts + #10297 extras), `/eth/v0/debug/forkchoice` (raw proto nodes, no Gloas fields). None expose votes/balances/equivocations/queued attestations. Nothing in the repo loads a dump.
5. **Size:** dump is dominated by per-validator vote arrays (~12 B/validator → ~12 MB per 1M registry entries) + optional balances (2 B/validator per distinct array). Proto nodes / PTC bitvectors are < 1 MB even for 200 unfinalized Gloas blocks.

---

## 1. Startup: anchor state, fork-choice init, what is lost

### 1.1 Anchor state selection (CLI)

Entry: `packages/cli/src/cmds/beacon/handler.ts:78-99` → `initBeaconState()` then `BeaconNode.init({... anchorState, isAnchorStateFinalized: isFinalized, earliestAvailableSlot})`.

`packages/cli/src/cmds/beacon/initBeaconState.ts`:
- `:62` `const archived = await readLatestArchivedStateBytes(context);` — reads `db.stateArchive.lastKey()` / `getBinary(slot)` (`:105-106`).
- `:76-83` if a DB state exists and (no checkpoint source OR DB state is within WS period) and no `--forceCheckpointSync` → `prepareArchivedStateInitialization(archived)` (**the default restart path**).
- `:85-92` else try checkpoint sources (`prepareCheckpointSourceInitialization`), falling back to DB state, then genesis.

`packages/cli/src/cmds/beacon/stateInitialization/prepareStateInitialization.ts:12-62` — archived DB state → `isFinalized: true` (`:20`), `persist: null` (`:51`), logs `"Initialized state from db"` (`:53`).

Checkpoint-source ordering (`prepareStateInitialization.ts:64-79`): `--checkpointState` file → `--checkpointSyncUrl` → `--lastPersistedCheckpointState` / `--unsafeCheckpointState`.
- `checkpointState.ts:160-166`: if the DB state is *ahead* of the provided checkpoint state, the DB state is used instead.
- `--lastPersistedCheckpointState` is a **hidden** flag (`packages/cli/src/cmds/beacon/options.ts:70-75`, "Use the last safe persisted checkpoint state to start syncing from"). It reads the newest unambiguous epoch-boundary state from the checkpoint-state datastore (`checkpointState.ts:99-110` → `readLatestSafe()` → `getLatestSafeDatastoreKey`, `packages/beacon-node/src/chain/stateCache/datastore/db.ts:61-124`: only epochs with exactly 1 persisted checkpoint, CRCS/PRCS, slot = epoch start) and boots with `isFinalized: false` (`checkpointState.ts:117-130`, warns "unsafe and may cause the node to follow a minority chain").

**What is in `stateArchive` at restart?** On graceful shutdown `BeaconNode.close()` calls `chain.persistToDisk()` (`packages/beacon-node/src/node/nodejs.ts:386`) → `archiveStore.persistToDisk()` → `statesArchiverStrategy.archiveState(forkChoice.getFinalizedCheckpoint())` (`packages/beacon-node/src/chain/archiveStore/archiveStore.ts:184-186`), which writes the **finalized checkpoint state** keyed by slot (`frequencyStateArchiveStrategy.ts:107-137`). During runtime, finalized states are archived every `min(PERSIST_TEMP_STATE_EVERY_EPOCHS=32, archiveStateEpochFrequency=1024)` epochs (`frequencyStateArchiveStrategy.ts:18, 58-69`; default `archiveStateEpochFrequency: 1024`, `packages/beacon-node/src/chain/options.ts:116`). So:
- graceful restart → anchor = finalized checkpoint state at shutdown (typically 2-3 epochs behind head on a healthy network);
- crash (no `persistToDisk`) → anchor = last periodically archived finalized state (up to ~32 epochs old) (inferred from the above; UNVERIFIED in practice).
- `--chain.archiveMode` only supports `Frequency` (`archiveStore.ts:78-88`). There is no `stateArchiveMode` and no `--chain.persistCheckpointStates` flag on unstable (`git grep` finds neither); checkpoint-state options are `--chain.nHistoricalStatesFileDataStore`, `--chain.maxCPStateEpochsInMemory`, `--chain.maxCPStateEpochsOnDisk` (`packages/cli/src/options/beaconNodeOptions/chain.ts:38-42, 83-87`).

### 1.2 Fork-choice initialization

`packages/beacon-node/src/chain/chain.ts:385-430` (BeaconChain constructor):
- `:392-404` always uses `PersistentCheckpointStateCache` (file datastore by default, `:388`).
- `:406-409` anchor state seeded into `blockStateCache` (+ head state) and `checkpointStateCache`.
- `:419-430` `initializeForkChoice(config, emitter, clock.currentSlot, anchorState, isAnchorStateFinalized, ...)`.
- `:479-493` Gloas: seeds `seenPayloadEnvelopeInputCache` from the anchor state's `latestExecutionPayloadBid` (so the anchor block's envelope can be fetched later).

`packages/beacon-node/src/chain/forkChoice/index.ts`:
- `:42-77` dispatches on `isFinalizedState`.
- **Finalized anchor** (`:82-176`): `computeAnchorCheckpoint()`; finalized = anchor cp, justified = anchor cp with `epoch + 1` unless genesis (`:93-102`); `justifiedBalances = state.getEffectiveBalanceIncrementsZeroInactive()` (`:104`); `ProtoArray.initialize(...)` with a **single node** (`:131-170`): `timeliness: true`, `ptcTimeliness: true`, `importedTimely: true` ("optimistically assume timely"), `executionStatus: Syncing` (Valid only at genesis, `:161`), `dataAvailabilityStatus: PreData`, `payloadStatus: PENDING` post-Gloas else `FULL` (`:165-166`), Gloas `executionPayloadNumber/GasLimit = 0` (TODO, `:156-160`).
- **Unfinalized anchor** (`:181-328`): builds a 4-node dummy chain finalized → justified → parent → head with `stateRoot: ZERO_HASH` dummies (`:278-319`); justified balances taken from the unfinalized state itself ("not the justified state, but there is no other ways", `:209-210`).

`ForkChoice` constructor (`packages/fork-choice/src/forkChoice/forkChoice.ts:167-206`): docstring already says *"Instantiates a Fork Choice from some existing components. This is useful if the existing components have been loaded from disk after a process restart."* — store + protoArray are injectable, **but votes are always fresh**: `voteCurrentIndices`/`voteNextIndices` filled with `NULL_VOTE_INDEX`, `voteNextSlots` with 0 (`:183-187`). FCR is constructed fresh if `opts.fastConfirmation` (`:192-196`).

`ForkChoiceStore` constructor (`packages/fork-choice/src/forkChoice/store.ts:78-120`): justified/unrealized = given cp; `equivocatingIndices = new Set()` (`:60`); FCR fields all initialized to the finalized checkpoint/root (`:105-119`).

### 1.3 Previous-run data wiped / not replayed

- `PersistentCheckpointStateCache.init()` (called from `chain.init()` → `loadFromDisk()` → `regen.init()`; `chain.ts:560-563, 620-624`; `regen/queued.ts:60-64`) **removes every persisted checkpoint state from the last run**: `persistentCheckpointsCache.ts:215-228` ("all checkpoint states from the last run are not trusted, remove them ... see https://github.com/ChainSafe/lodestar/pull/7255"). Order: `initBeaconState` (reads `readLatestSafe` for `--lastPersistedCheckpointState`) runs **before** `BeaconNode.init` → `chain.init()` (`handler.ts:83-85`, `nodejs.ts:289`), so that flag still works.
- **Hot-DB blocks are not replayed into fork choice, and sync never reads the local DB** (`git grep "\.db\.|chain\.db"` over `packages/beacon-node/src/sync` → no hits). `db.block` is only read on demand (regen replay `regen/regen.ts:199-202`, API/getBlock paths `chain.ts:852,878,917`, archiver, envelope reload `seenPayloadEnvelopeInput.ts:220`, reqresp). No startup code iterates `db.block` (checked with `git grep "db\.block\.(values|entries|keys|...)"`).
- `chain.close()` (`chain.ts:565-576`): *"Since we don't persist unfinalized fork-choice, we can abort any ongoing unfinalized block writes. TODO: persist fork choice to disk and allow unfinalized block writes to complete."* → `unfinalizedBlockWrites.dropAllJobs()` and `unfinalizedPayloadEnvelopeWrites.dropAllJobs()`. So the hot DB may be **missing the last few imported blocks/envelopes** at shutdown — relevant to any dump that references hot-DB blocks.

### 1.4 How the node gets back to head

Sync (`packages/beacon-node/src/sync/utils/remoteSyncType.ts`):
- Peers with same finalized epoch and head > `local.headSlot + slotImportTolerance` (default `SLOTS_PER_EPOCH`, `sync/sync.ts:41`) → `PeerSyncType.Advanced` (`:70-77`).
- `getRangeSyncTarget` (`:104-163`): head sync starting at `min(epoch(local.headSlot), max(remote.finalizedEpoch, epoch(anchorStateLatestBlockSlot)))` — i.e. from the finalized epoch (`:142-157`). If remote finalized > local and unknown → Finalized sync (`:112-137`).
- Batches: `EPOCHS_PER_BATCH = 1` (`sync/constants.ts:54`), `BATCH_BUFFER_SIZE = 10` (`:63`).
- Gloas: envelopes are fetched alongside via `ExecutionPayloadEnvelopesByRange` (`sync/utils/downloadByRange.ts:52, 446`), then imported per slot right after each block (`chain/blocks/index.ts:155-178`).
- Range sync opts (`sync/range/range.ts:194-210`): `importAttestations: Skip` only for Finalized sync; `fromRangeSync: true` (declared `blocks/types.ts:74`, **not read anywhere** else).
- Gossip core topics are subscribed only once `SyncState.Synced` (`sync/sync.ts:231-255`), and unsubscribed if behind by > `2 * slotImportTolerance` (`:257-275`). Synced = head within `slotImportTolerance` of clock and ≥1 peer (`:145-162`). So **no gossip attestations / PTC messages / slashings are received during catch-up**.

**Duration:** not measured in code. Rough model: (time to get peers) + (~64-96 blocks from finalized to head, 1 epoch per batch, full block + DA + newPayload verification). The incident's "~35 s of fcU INVALID" is consistent with that order of magnitude. UNVERIFIED (no metrics pulled for this note).

### 1.5 What is lost vs re-derived after restart

| Item | After restart | Ref |
|---|---|---|
| Unfinalized ProtoArray nodes | Rebuilt by re-importing blocks from peers (not from hot DB) | §1.3, §1.4 |
| Unrealized justified/finalized per node | **Re-derived** on re-import (`state.computeUnrealizedCheckpoints()` or parent reuse) | `forkChoice.ts:845-872` |
| `timeliness` / `ptcTimeliness` / `importedTimely` | **Lost** — re-imported blocks are computed from `seenTimestampSec` at re-import time (late); anchor optimistically `true` | `importBlock.ts:108-109,151-160`; `forkChoice.ts:815,885-887`; `forkChoice/index.ts:137-139` |
| LMD votes (VoteTracker) | **Partially re-derived**: only from attestations in re-imported blocks with `blockEpoch >= currentEpoch - 1` (`FORK_CHOICE_ATT_EPOCH_LIMIT = 1`) and target epoch in [current-1, current]; gossip/unaggregated votes not yet included in a block are lost; gossip is off until synced | `importBlock.ts:54-66,169-255`; `forkChoice.ts:2014-2038`; `sync.ts:231-275` |
| Queued (current-slot) attestations | Lost (ephemeral anyway) | `forkChoice.ts:136-138` |
| Proposer boost (`proposerBoostRoot`, `previousProposerBoost`) | Lost; reset every slot anyway; re-imported late blocks never get boost | `forkChoice.ts:158,816-824`; `protoArray.ts:99-101`; `forkChoice.ts:2252-2256` |
| `equivocatingIndices` | **Partially re-derived**: from attester slashings in re-imported blocks with `blockEpoch >= currentEpoch - 1 - 1 - MAX_SEED_LOOKAHEAD`, plus gossip after sync. Older ones are lost. Attester slashings persisted in the op pool (`opPool.toPersisted`) are restored into the **op pool only**, *not* fed to `forkChoice.onAttesterSlashing` | `importBlock.ts:257-275`; `gossipHandlers.ts:1088`; `opPool.ts:87-110`; `chain.ts:620-624` |
| Justified balances | Anchor: from anchor state (finalized case: anchor state is not the justified state when justified = anchor epoch+1). `checkpointBalancesCache` empty → `justifiedBalancesGetter` falls back to closest state | `forkChoice/index.ts:104,209-210`; `chain.ts:1686-1716`; `importBlock.ts:132` |
| PTC votes (Gloas) | **Partially re-derived** from `payloadAttestations` in re-imported block bodies (block N+1 carries PTC for N); gossip `PayloadAttestationMessage`s not aggregated into a block are lost | `importBlock.ts:277-303`; `protoArray.ts:587-591` |
| Gloas FULL variants | Re-created when envelopes are re-downloaded and imported (`onExecutionPayload`); anchor starts PENDING(+EMPTY) only | `chain/blocks/index.ts:166-178`; `protoArray.ts:517-591, 629-690`; `forkChoice/index.ts:166` |
| Execution status | Anchor = `Syncing`; re-imported blocks re-sent via `newPayload` | `forkChoice/index.ts:161`; `verifyBlocksExecutionPayloads.ts:180-245` |
| FCR store (`confirmedRoot`, observed/greatest-unrealized checkpoints + balances, prev/curr slot head) | **Reset** to finalized; FCR is paused until synced | `store.ts:105-119`; `sync.ts:79-82, 236, 262` |
| `irrecoverableError`, `lvhError` | Reset | `forkChoice.ts:113`; `protoArray.ts:97` |
| Checkpoint states | Deleted at boot | `persistentCheckpointsCache.ts:215-228` |

---

## 2. EL interaction on restart (engine_forkchoiceUpdated)

### 2.1 Where fcU is sent

`git grep notifyForkchoiceUpdate` in `packages/beacon-node/src` → only three producers:
1. **Block import** — `chain/blocks/importBlock.ts:394-482`:
   ```ts
   if (
     !this.opts.disableImportExecutionFcU &&
     (newHead.blockRoot !== oldHead.blockRoot || currFinalizedEpoch !== prevFinalizedEpoch) &&
     !shouldOverrideFcu
   ) {
     const headBlockHash = this.forkChoice.getHead().executionPayloadBlockHash ?? ZERO_HASH_HEX;
     ...
     this.executionEngine.notifyForkchoiceUpdate(fork, headBlockHash, safeBlockHash, finalizedBlockHash)
       .catch((e) => { ... this.logger.error("Error pushing notifyForkchoiceUpdate()", {headBlockHash, finalizedBlockHash}, e); });
   ```
   `shouldOverrideFcu` is only evaluated when `blockSlot >= currentSlot` (`:405`), i.e. never during catch-up. **No check for sync state, optimistic status, or distance to the clock/EL head.** `disableImportExecutionFcU` is a CLI option `--chain.disableImportExecutionFcU` (`cli/src/options/beaconNodeOptions/chain.ts:24,67,221`) that disables it globally.
2. **Gloas payload import** — `chain/blocks/importExecutionPayload.ts:264-274`: fcU with the envelope's `blockHash` if the payload's block is the current head.
3. **Block production / prepare-next-slot** — `chain/produceBlock/produceBlockBody.ts:795` via `prepareExecutionPayload` (with payload attributes). `PrepareNextSlotScheduler` only calls it if we propose next slot (`prepareNextSlot.ts:283-302`) and **skips entirely** if head is > `PREPARE_EPOCH_LIMIT = 1` epoch behind (`prepareNextSlot.ts:46, 119-128`).

**No fcU at startup**: nothing in `BeaconNode.init`/`chain.init`/sync issues one (grep above). The first fcU after restart is from the first block import that changes head.

Hashes: `headBlockHash` = head's `executionPayloadBlockHash` (Gloas PENDING/EMPTY = parent's payload hash, FULL = own; `forkChoice.ts:899-925`); `safeBlockHash` = FCR confirmed block (falls back to justified root when FCR disabled, `forkChoice.ts:238-240`), Gloas = bid `parent_block_hash` (`packages/fork-choice/src/forkChoice/safeBlocks.ts:18-41,53-56`); `finalizedBlockHash` same rule for finalized block (`safeBlocks.ts:49-51`).

### 2.2 Catch-up sequence (why geth sees "Too deep reorg")

Range sync imports one block at a time inside a segment (`chain/blocks/index.ts:158-181`, `await importBlock.call(...)` per slot), so **each imported block moves head and emits one fcU** (the first fcU after restart is for the first imported child of the anchor, not the anchor itself, since nothing sends fcU at boot). Engine calls are serialized in one queue (`execution/engine/http.ts:108-112, 141-168`, `maxConcurrency: 1`, `QUEUE_MAX_LENGTH = EPOCHS_PER_BATCH * SLOTS_PER_EPOCH * 2`). Head starts at the finalized anchor block (~64-96 slots behind tip) while the EL kept its pre-restart head and finalized block → each fcU names an **already-canonical ancestor** of geth's head that is at/above geth's finalized block → geth's depth check (§2.3) refuses every head > 32 blocks below its head until range sync climbs within 32. Matches "heads 33-62 behind, ~35 s". Heads strictly below geth's finalized are silently answered `VALID` ("Skipping beacon update to finalized ancestor"); per #35519 (geth v1.17.6) a head *equal* to geth's finalized now also goes through the depth check (from PR metadata, see §6).

### 2.3 How fcU errors / `INVALID` are handled — **does not touch fork choice**

**What geth actually sends** (go-ethereum `eth/catalyst/api.go` @ `acdb0c66` master 2026-10-08, fetched via `gh api`, lines 324-354):
```go
} else {
    if finalized := api.eth.BlockChain().CurrentFinalBlock(); finalized != nil && block.NumberU64() < finalized.Number.Uint64() {
        log.Info("Skipping beacon update to finalized ancestor", ...)
        return valid(nil), nil
    }
    // A canonical block above the current head (...) is a forward move, not a reorg.
    if current := api.eth.BlockChain().CurrentBlock().Number.Uint64(); block.NumberU64() < current {
        depth := current - block.NumberU64()
        if api.maxReorgDepth > 0 && depth > api.maxReorgDepth {
            log.Warn("Refusing too deep reorg", "depth", depth, "head", update.HeadBlockHash)
            return engine.STATUS_INVALID, engine.TooDeepReorg.With(fmt.Errorf("reorg depth %d exceeds limit %d", depth, api.maxReorgDepth))
        }
    }
    if !api.eth.Synced() { ... return valid(nil), nil }
    if latestValid, err := api.eth.BlockChain().SetCanonical(block); err != nil { ... }
}
```
`TooDeepReorg = &EngineAPIError{code: -38006, msg: "Too deep reorg"}` (`beacon/engine/errors.go:84`). The check only applies when the requested head is already **canonical** in geth, not geth's current head, and not below geth's finalized block. Non-canonical heads go straight to `SetCanonical` (`api.go:324-328`). Once the CL head is within the limit, geth `SetCanonical`s the old block, i.e. actually rewinds its head to the CL's catch-up head (`api.go:351`), then moves forward again with later fcUs. Because the Go method returns a non-nil error, the JSON-RPC response is an error object; the `STATUS_INVALID` body is not delivered (standard geth RPC behaviour, not re-verified in `rpc/` here; UNVERIFIED but consistent with the `Served engine_forkchoiceUpdatedV3 err="Too deep reorg" errdata=...` log quoted in #9716).

**Lodestar side**, JSON-RPC transport:
- `forkchoiceUpdated` uses `retries: 0` when no payload attributes (`execution/engine/jsonRpcTransport.ts:124-131`).
- An error object in a 200 response → `parseRpcResponse` throws `ErrorJsonRpcResponse` with message `JSON RPC error: Too deep reorg, engine_forkchoiceUpdatedV3` (`jsonRpcHttpClient.ts:319-325, 349-366`). A non-2xx response → `HttpRpcError` (`:289-293`). #9716 describes it as `HttpRpcError`; which one geth produces depends on its HTTP status for method errors (UNVERIFIED).
- Either way the client emits `JsonRpcHttpClientEvent.ERROR` (`jsonRpcHttpClient.ts:204-213`) → `updateEngineState(getExecutionEngineState({payloadError}))` (`http.ts:180-182`) → both error classes map to `ExecutionEngineState.SYNCING` (`utils.ts:199-207`) → `warn "Execution client request failed" {oldState, newState}` on the transition (`http.ts:593-596, 619-625`). The next `VALID` `newPayload` flips it back → `info "Execution client is synced"` (`http.ts:616-618`) — the SYNCING↔SYNCED log flap described in #9716 Problem C.
- `notifyForkchoiceUpdate` throws before its status handling, so `lodestar_execution_engine_notify_forkchoice_update_result_total` is **not** incremented for these (the `inc` is at `http.ts:340`, after the awaited call).
- Call site logs `error "Error pushing notifyForkchoiceUpdate()" {headBlockHash, finalizedBlockHash}` + error (`importBlock.ts:476-480`; payload path `importExecutionPayload.ts:269-273`).
- REST/SSZ engine transport (`execution/engine/restTransport.ts:226-271`): how a reorg-depth refusal is encoded there is UNVERIFIED.

If an EL instead returns a **result** with `payloadStatus.status = INVALID`, `execution/engine/http.ts:323-373` applies:
```ts
this.updateEngineState(getExecutionEngineState({payloadStatus: status, oldState: this.state}));
this.metrics?.engineNotifyForkchoiceUpdateResult.inc({result: status});
switch (status) {
  ...
  case ExecutionPayloadStatus.INVALID:
    throw Error(`Invalid ${payloadAttributes ? "prepare payload" : "forkchoice request"}, validationError=${validationError ?? ""}`);
```
- Engine state: `INVALID` → `ExecutionEngineState.SYNCING` (`execution/engine/utils.ts:164-176`), logged `warn "Execution client is syncing"` on transition (`http.ts:619-625`). `SYNCING` has no functional effect: only `OFFLINE`/`AUTH_FAILED` are checked (`sync/sync.ts:95-97`, `node/notifier.ts:61-63`).
- Throws a bare `Error("Invalid forkchoice request, validationError=...")`, caught + logged at the call site as above; metric `...notify_forkchoice_update_result_total{result="INVALID"}` (`metrics/metrics/lodestar.ts:1175-1179`). `latestValidHash` is discarded (destructuring at `http.ts:330-332` only takes `status, validationError`).
- Block production: `INVALID` with payload attributes throws `Invalid prepare payload ...` (`http.ts:363-368`).

**Fork choice invalidation only happens on the `newPayload` path** (on unstable): `verifyBlocksExecutionPayloads.ts:195-208` builds an `LVHInvalidResponse` from `engine_newPayload` `INVALID`, `getSegmentErrorResponse` (`:247-291`) → `forkChoice.validateLatestHash(...)` (`chain/blocks/index.ts:122-129`), which may set `irrecoverableError` → process shutdown at next slot (`forkChoice.ts:1571-1579`, `chain.ts:1816-1818`). `git grep validateLatestHash` → `blocks/index.ts:126` is the only caller. **fcU errors/INVALID never call it**, so "Too deep reorg" cannot mark blocks invalid today.

**Risk — open PR [#9332](https://github.com/ChainSafe/lodestar/pull/9332)** (lodekeeper, opened 2026-05-06, still open): makes `http.ts` throw a typed `ForkchoiceUpdateError{code: INVALID, headBlockHash, latestValidHash, validationError}` on `status === INVALID` and, in `importBlock`/`importExecutionPayload`, calls a new `invalidateForkchoiceHeadFromFcuInvalid()` → `forkChoice.validateLatestHash({executionStatus: Invalid, latestValidExecHash: e.latestValidHash, invalidateFromParentBlockRoot: headBlockRoot, ...})` + head recompute (from `gh pr diff 9332`). geth's `-38006` arrives as a JSON-RPC **error**, not a `ForkchoiceUpdateError`, so it would not trigger this path. But any EL/transport that encodes a reorg-depth refusal as a `payloadStatus` `INVALID` result (e.g. `latestValidHash: null`, `validationError: "too deep reorg"`) would get a **valid** head + descendants invalidated under #9332. If #9332 lands, it should special-case reorg-depth refusals (and `-38006`). Other ELs' encodings (Erigon `MAX_REORG_DEPTH`, Nethermind, Besu, Reth) UNVERIFIED.

### 2.4 Existing guards / prior reports

- `git grep -i "too deep\|maxreorg\|reorg depth\|reorgdepth"` over `packages/` at this SHA → **no hits**. No reorg-depth guard, no "skip fcU while syncing", no "don't send fcU behind EL head". The `fromRangeSync` import flag is set by range sync but never read (`blocks/types.ts:74`, `sync/range/range.ts:206`). Only global kill-switch: `--chain.disableImportExecutionFcU`.
- Prior reports: #9716 Problem C (same geth refusal during a deep historical sync; suggested "skip per-block fcU during finalized range sync" / suppress the state-flap logging — not implemented), #10005 (orphaned FULL leaf → stale fcU head → `Too deep reorg` on devnet-9; fixed the orphan import, not the fcU behaviour). See §6.

---

## 3. Existing persistence (fork-choice-adjacent)

DB buckets (`packages/beacon-node/src/db/buckets.ts`):
- `allForks_stateArchive = 0` finalized states (anchor source).
- `allForks_block = 1` **unfinalized (hot) blocks** — written async on import (`importBlock.ts:118-127`), dropped-on-close (§1.3).
- `allForks_checkpointState = 17` checkpoint states (DB datastore; default is the **file** datastore under `<dataDir>/checkpoint_states`, `stateCache/datastore/file.ts:8-21`, `chain.ts:388-392`).
- `gloas_executionPayloadEnvelope = 59` (hot, by block root) / `gloas_executionPayloadEnvelopeArchive = 60`.
- `earliestAvailableSlot = 61` singleton (#10267).
- `gloas_proposerPreferences = 62` (#10327).
- `index_chainInfo = 7` ("justified, finalized state and block hashes") — enum value only, **no repository/usages** on unstable (`git grep chainInfo` hits only `buckets.ts:18`).

Persisted on shutdown / loaded on startup (`chain.ts:619-631`):
```ts
async loadFromDisk(): Promise<void> {
  await this.regen.init();                                  // wipes previous-run checkpoint states
  await this.opPool.fromPersisted(this.db, this.getHeadState(), this.bls, this.clock.currentSlot);
  await this.proposerPreferencesPool.fromPersisted(this.db, this.clock.currentSlot);
}
async persistToDisk(): Promise<void> {
  await this.archiveStore.persistToDisk();                  // finalized checkpoint state -> stateArchive
  await this.opPool.toPersisted(this.db);
  await this.proposerPreferencesPool.toPersisted(this.db);
}
```

`PersistentCheckpointStateCache` (`chain/stateCache/persistentCheckpointsCache.ts`):
- Keeps `maxCPStateEpochsInMemory` (default 3) epochs in memory, persists older checkpoint states to disk (`:56-61, 86-117`); tiered on-disk retention (default `Infinity` → tiers of base 16, `:63-81, 131-141`).
- Purpose = regen + archive of finalized state; **wiped at boot** (`:215-228`). Read back only via `--lastPersistedCheckpointState` (CLI) or `GET /eth/v1/lodestar/persisted_checkpoint_state` (`api/src/beacon/routes/lodestar.ts:605-623`, impl `api/impl/lodestar/index.ts:245-262`, `chain.ts:782-796` — note "TODO GLOAS: Need to revisit ... retrieve FULL state").

Recent persistence PRs (all merged; dates from commits in clone):
- **#10267** `feat: persist earliest available slot` (0edec865c, 2026-10-08): new `earliestAvailableSlot` bucket; CLI owns initial value per init path (`prepareStateInitialization.ts:37-50`), `archiveStore.advanceEarliestAvailableSlot` persists before pruning (`archiveStore.ts:143-153`).
- **#10287** `feat: optionally persist produced execution payload envelopes` (45e426033, 2026-10-07): **debug-only** SSZ file dump of *produced* envelopes, hidden flag `--chain.persistProducedPayloadEnvelopes` → `chain.persistExecutionPayloadEnvelope` → `persistSszObject(...)` into `persistInvalidSszObjectsDir/<date>/` (`chain.ts:1770-1786`). Not a restart-persistence feature, but a model for "write an SSZ blob to disk for debugging".
- **#10327** `feat: persist proposer preferences across beacon node restarts` (0837ebd40, 2026-10-09): `ProposerPreferencesPool.toPersisted/fromPersisted` (`opPools/proposerPreferencesPool.ts:70-85`), shared `persistDiff` helper moved to `opPools/utils.ts`. Pattern: persist on `persistToDisk`, restore filtered by current slot in `loadFromDisk`.

Fork-choice/proto-array persistence attempts: see §6.

---

## 4. Existing dump / debug surfaces

### 4.1 Beacon API debug routes (`packages/api/src/beacon/routes/debug.ts`, impl `packages/beacon-node/src/api/impl/debug/index.ts`)

| Route | Def | Impl | Content |
|---|---|---|---|
| `GET /eth/v1/debug/fork_choice` | `debug.ts:244-261` | `index.ts:56-73` | justified/finalized cp; per node: slot, blockRoot, parentRoot, justifiedEpoch, finalizedEpoch, weight, validity, executionBlockHash |
| `GET /eth/v2/debug/fork_choice` | `debug.ts:81-140, 262-271` | `index.ts:75-129` | per **(root, payloadStatus)** node: `payloadStatus` (pending/empty/full), `parentRoot` (for EMPTY/FULL = own root), `parentPayloadStatus`, justified/finalized cp, `weight`, `validity`, `executionBlockHash`, `payloadAttesterCount`, `payloadAvailabilityYesCount`, `payloadDataAvailabilityYesCount` (PTC tallies from `getPTCVoteCounts`), `extraData{attestationScore, executionOptimistic, gasLimit (FULL only), timestamp, stateRoot, target, unrealizedJustified{Epoch,Root}, unrealizedFinalized{Epoch,Root}}`; top-level `extraData{head{blockRoot,payloadStatus}, proposerBoostRoot, previousProposerBoostRoot, unrealizedJustifiedCheckpoint, unrealizedFinalizedCheckpoint}` |
| `GET /eth/v0/debug/forkchoice` (Lodestar-specific) | `debug.ts:24-49, 272-281` | `index.ts:131-142` | raw ProtoNode fields: executionPayloadBlockHash/Number, executionStatus, slot, blockRoot, parentRoot, stateRoot, targetRoot, timeliness, justified/finalized/unrealized epochs+roots, parent, weight, bestChild, bestDescendant. The response container has **no** `payloadStatus`, `parentBlockHash`, `proposerIndex`, `ptcTimeliness`, `importedTimely`, `dataAvailabilityStatus`, `attestationScore`, `executionPayloadGasLimit` fields, so those are not exposed (assuming the SSZ/JSON codec only emits declared fields — UNVERIFIED at runtime). |
| `GET /eth/v2/debug/beacon/heads` | `debug.ts:235` | `index.ts:45-54` | leaves |

**#10297** `feat: add fork choice v2 debug fields` (d23dd6295, 2026-10-07): diff adds exactly 4 fields to `ForkChoiceNodeV2ExtraDataType` + impl: `attestationScore`, `stateRoot`, `unrealizedJustifiedRoot`, `unrealizedFinalizedRoot` (`git show d23dd6295`: `debug.ts` +4, `index.ts` +4, test data +8). The v2 endpoint with per-`(root, payload_status)` nodes was added in **#9444** `chore: implement forkchoice debug endpoint v2` (merged 2026-06-02); **#10191** `fix: align fork choice v2 with beacon api spec` (3b56ef3d9, merged 2026-10-07; beacon-APIs #615) added `data` wrapping, `parent_root`+`parent_payload_status`, per-node checkpoints, PTC counts and head `{root, payload_status}` in `extra_data` (PR body). PTC quorum events: **#10274** (f23b93e9e). Codex review on #10297 noted the client decoder now requires the 4 new keys (older servers would fail to decode) — per subagent read of the thread, unresolved. The v2 endpoint exposes PTC **counts**, not the per-member bitvectors (`timeliness`/`DA`/`attended`).

**Not exposed by any endpoint:** votes (current/next indices, next slots), justified balances / `ForkChoice.balances`, `equivocatingIndices`, `queuedAttestations`, PTC bitvectors, `ptcTimeliness`/`importedTimely`, `proposerIndex`, FCR balances, `previousProposerBoost.score`, `fastConfirmationPaused`.

### 4.2 Lodestar admin routes (models for a dump endpoint) — `packages/api/src/beacon/routes/lodestar.ts`

- `POST /eth/v1/lodestar/write_heapdump?thread=&dirpath=` (`:444-453`; impl `api/impl/lodestar/index.ts:39-63`): writes a file **server-side** to `dirpath`, returns `{filepath}`, guarded by a `writingHeapdump` flag. Closest existing model for "POST → write fork-choice dump to disk".
- `POST /eth/v1/lodestar/write_profile` (`:454-463`).
- `GET /eth/v1/lodestar/persisted_checkpoint_state?checkpoint_id=` (`:605-623`): returns SSZ `BeaconState` bytes with 5-min timeout — model for streaming a large binary dump.
- `GET /eth/v1/lodestar/fast_confirmation` (`:658-666`; impl `index.ts:282-307`): FCR store checkpoints/heads (no balances).
- `GET /eth/v1/debug/dump_db_bucket_keys/:bucket`, `GET /eth/v1/debug/dump_db_state_index` (`:636-651`), `GET /eth/v1/lodestar/state_cache_items` (`:499`), `POST /eth/v1/lodestar/drop_state_cache` (`:523`).
- `chain.persistSszObject` (`chain.ts:1770-1786`): `<persistInvalidSszObjectsDir>/<yyyy-mm-dd>/<prefix>_<root>.ssz`, `writeIfNotExist`.

### 4.3 Tooling that loads a dump

None. `git grep` for `getProtoArrayNodes|getDebugForkChoice|debug/fork_choice|forkchoice.json` outside the API package/impl only finds API test data and a unit test (`packages/api/test/unit/beacon/testData/debug.ts`, `packages/beacon-node/test/unit/api/impl/debug/forkChoice.test.ts`). `dashboards/lodestar_fork_choice.json` is a Grafana dashboard. No CLI command consumes a fork-choice dump.

### 4.4 Fork-choice spec-test runner (dump → reproducible test)

`packages/beacon-node/test/spec/presets/fork_choice.test.ts:9-10` → `forkChoiceTestRunner` (`packages/beacon-node/test/spec/utils/forkChoiceTestRunner.ts`), used for both `fork_choice` and `sync` handlers.

Inputs (`forkChoiceTestRunner.ts:766-835, 971-986`):
- `anchor_state.ssz_snappy` (`ssz[fork].BeaconState`), `anchor_block.ssz_snappy` (`ssz[fork].BeaconBlock`), `meta.yaml`, `steps.yaml`;
- referenced objects: `block_<root>`, `blobs_<id>`, `column_<id>`, `execution_payload_envelope_<id>`, `attestation_<root>`, `attester_slashing_<root>`, `payload_attestation_message_<root>` (`:80-88, 771-781`).
- Step kinds (`:856-964`): `tick` (seconds), `attestation`, `attester_slashing`, `payload_attestation_message`, `block` (+ `blobs`/`proofs`/`columns`), `execution_payload` (envelope), `block_hash`+`payload_status` (predefined EL responses), `checks` {`head{slot,root,payload_status}`, `time`, `justified_checkpoint`, `finalized_checkpoint`, `proposer_boost_root`, `get_proposer_head`, `should_override_forkchoice_update`, `payload_timeliness_vote`, `payload_data_availability_vote`, `viable_for_head_roots_and_weights[{root,weight,payload_status}]`}.

Harness (`:95-180`): real `BeaconChain` with `ClockStopped(anchorState.slot)`, mocked DB, `ExecutionEngineMockBackend`, `isAnchorStateFinalized: true`, `disablePrepareNextSlot`, `proposerBoost/proposerBoostReorg: true`. Ticks emit `ClockEvent.slot` (`:183-189`). Attestations: runner enforces the 1-slot delay itself (`:199-217`), resolves shuffling via regen, then calls `chain.forkChoice.onAttestation(indexed, attDataRoot)` **directly** (no signature check) (`:224-241`).

Implications for "dump → test": the anchor is the finalized state+block (available from `stateArchive`/`blockArchive`); blocks/envelopes come from the hot DB; `checks` can assert the dumped head/justified/finalized/boost/weights. **Votes cannot be expressed directly** — they'd have to be synthesized as single-validator `attestation_*` objects (data `{slot, index (0/1 Gloas payload), beacon_block_root, source, target}` per validator's committee at `voteNextSlot`) — feasible since the runner skips attestation signature verification, but the format has no "latest message" input. Timeliness has to be reproduced via `tick` timing before each `block` step. Equivocations via `attester_slashing` steps. (Design inference — UNVERIFIED by implementation.)

---

## 5. Data model to dump for a full restore

### 5.1 `ForkChoice` (`packages/fork-choice/src/forkChoice/forkChoice.ts`)

| Field | Type | Ref | Needed? |
|---|---|---|---|
| `voteCurrentIndices` | `VoteIndex[]` (node index or `NULL_VOTE_INDEX=0xffffffff`) | `:125`, `protoArray/interface.ts:13` | yes (or re-derive: see 5.4) |
| `voteNextIndices` | `VoteIndex[]` | `:126` | **yes** — the latest messages |
| `voteNextSlots` | `Slot[]` (Gloas compares slots, pre-Gloas epochs of slots) | `:127, 2189-2198` | **yes** |
| `queuedAttestations` | `Slot → Root → ValidatorIndex → PayloadStatus` | `:136-138` | optional (current slot only, applied on next tick `:2206-2226`) |
| `queuedAttestationsPreviousSlot` | number (metrics) | `:144` | no |
| `head` | cached `ProtoBlock` | `:152` | no (recompute `updateHead()`) |
| `validatedAttestationDatas` | `Set<string>` per-slot cache | `:156, 1168` | no |
| `proposerBoostRoot` | `RootHex \| null` | `:158` | optional (current slot only) |
| `justifiedProposerBoostScore` | `bigint \| null` lazy | `:160` | no |
| `balances` | `EffectiveBalanceIncrements` (= `Uint16Array`, `packages/state-transition/src/cache/effectiveBalanceIncrements.ts:7`) — the balances the current weights were computed with (`oldBalances` in `computeDeltas`) | `:162, 598-628` | only if weights/`voteCurrentIndices` are dumped |
| `fastConfirmationPaused` | boolean | `:166` | no (sync re-decides) |
| `irrecoverableError` | `Error?` | `:113` | probably no |

**Votes are node indices**, not roots: `addLatestMessage` resolves `(root, payloadStatus)` → index (`:2168-2200`), `prune()` shifts all indices by `prunedCount` (`:1355-1382`). A dump must either keep node order identical or store votes as `(root, payloadStatus)` / `(nodeIndex + node table)`.

### 5.2 `ForkChoiceStore` (`packages/fork-choice/src/forkChoice/store.ts:39-120`)

- `currentSlot` (`:62`) — on restore, `updateTime()` replays `onTick` per elapsed slot incl. epoch-boundary unrealized pull-up (`forkChoice.ts:1149-1170, 2239-2269`).
- `justified: {checkpoint, balances, totalBalance}` (`:56, 95-101, 122-128`).
- `unrealizedJustified: {checkpoint, balances}` (`:57`).
- `finalizedCheckpoint`, `unrealizedFinalizedCheckpoint` (`:58-59`).
- `equivocatingIndices: Set<ValidatorIndex>` (`:60`).
- FCR spec fields: `confirmedRoot`, `previousEpochObservedJustifiedCheckpoint`, `currentEpochObservedJustifiedCheckpoint`, `previousEpochGreatestUnrealizedCheckpoint`, `previousSlotHead`, `currentSlotHead` (`:64-70`).
- FCR aux: `previousEpochObservedJustifiedBalances`, `currentEpochObservedJustifiedBalances`, `previousEpochGreatestUnrealizedBalances` (`:72-75`). The rest of FCR (`FastConfirmationCache`) is rebuilt per run (`fastConfirmation/fastConfirmationRule.ts:39-51`, `types.ts:107-117`). FCR is off by default (`chain/options.ts:112`).
- Callbacks/getters (`justifiedBalancesGetter`, `stateGetter`, `events`) — not data.

### 5.3 `ProtoArray` (`packages/fork-choice/src/protoArray/protoArray.ts:77-124`)

- `pruneThreshold`, `justifiedEpoch/Root`, `finalizedEpoch/Root` (`:80-84`).
- `nodes: ProtoNode[]` (`:85`) — fields (`protoArray/interface.ts:81-182`):
  - identity: `slot`, `blockRoot`, `parentRoot`, `stateRoot`, `targetRoot`, `proposerIndex`;
  - FFG: `justifiedEpoch/Root`, `finalizedEpoch/Root`, `unrealizedJustifiedEpoch/Root`, `unrealizedFinalizedEpoch/Root`;
  - timeliness: `timeliness`, `ptcTimeliness`, `importedTimely`;
  - execution: `executionPayloadBlockHash` (Gloas PENDING/EMPTY = parent payload hash, FULL = own), `executionPayloadNumber`, `executionPayloadGasLimit`, `executionStatus` (Valid/Syncing/PreMerge/Invalid), `dataAvailabilityStatus`;
  - Gloas: `payloadStatus` (PENDING=0/EMPTY=1/FULL=2), `parentBlockHash` (non-null ⇔ Gloas);
  - tree: `parent?`, `bestChild?`, `bestDescendant?` (indices), `weight: bigint`, `attestationScore: bigint`.
- `indices: Map<RootHex, number | [p,e] | [p,e,f]>` (`:67-96`) — derivable from nodes. Gloas block = PENDING + EMPTY at `onBlock`, FULL appended at `onExecutionPayload` (`:517-591, 629-690`) → **FULL node is not adjacent to its PENDING/EMPTY** in `nodes`.
- `lvhError?` (`:97`).
- `previousProposerBoost: {root, score: bigint} | null` (`:99`) — the boost currently baked into weights (needed only if weights are restored as-is).
- `proposerBoostRoot` (`:101`).
- PTC (Gloas): `payloadTimelinessVotes`, `payloadDataAvailabilityVotes`, `ptcAttested`: `Map<RootHex, BitArray(PTC_SIZE)>` (`:103-124`), created per Gloas block (`:587-591`), quorum via `majorityVote` (`:42-60`).

### 5.4 Restore-consistency note (design inference, UNVERIFIED)

`updateHead()` applies `computeDeltas(nodes.length, voteCurrentIndices, voteNextIndices, oldBalances=this.balances, newBalances=fcStore.justified.balances, equivocatingIndices)` (`forkChoice.ts:598-628`) on top of existing node `weight`s and subtracts `previousProposerBoost`. So either dump **all of** {node weights/attestationScore, `voteCurrentIndices`, `ForkChoice.balances`, `previousProposerBoost`} consistently, or dump only **{nodes without weights, `voteNextIndices`+`voteNextSlots`, justified balances, equivocations}** and restore with weights = 0, `voteCurrentIndices = NULL`, `previousProposerBoost = null` so the first `updateHead()` recomputes everything from scratch. The second is smaller and less fragile.

### 5.5 Outside the ForkChoice object (needed for a *working* restored node)

- **States**: proto nodes are useless without a seed state to regen from. Regen walks ancestors, uses `blockStateCache` / `checkpointStateCache.getOrReloadLatest`, and replays hot-DB blocks (`regen/regen.ts:150-222`), **max 5 epochs** of blocks (`MAX_EPOCH_TO_PROCESS = 5`, `:182-189`). The finalized anchor state is seeded into the cp cache (`chain.ts:406-409`), so a restored fork choice + hot-DB blocks works for ≤5 epochs of non-finality; beyond that it needs the persisted checkpoint states — which are currently **deleted at boot** (`persistentCheckpointsCache.ts:215-228`).
- **Hot-DB completeness**: last blocks/envelopes may be missing due to `dropAllJobs()` on close (`chain.ts:569-573`).
- `checkpointBalancesCache` (`chain.ts:1692`, populated `importBlock.ts:132`), shuffling cache, `seenPayloadEnvelopeInputCache` (Gloas anchor seeding `chain.ts:479-493`).

### 5.6 Size estimates (mainnet)

Let N = validator **registry length** (vote/balance arrays are indexed by validator index and sized from `state.validatorCount`, `forkChoice.ts:177-187`, grown in `addLatestMessage` `:2181-2187`). Mainnet N is UNVERIFIED here — numbers given per 1M.

| Component | Per unit | 1M validators | 2M validators |
|---|---|---|---|
| `voteNextIndices` (u32) | 4 B/val | 4 MB | 8 MB |
| `voteNextSlots` (u32) | 4 B/val | 4 MB | 8 MB |
| `voteCurrentIndices` (u32; skippable per 5.4) | 4 B/val | 4 MB | 8 MB |
| justified balances (Uint16) | 2 B/val per **distinct** array | 2 MB | 4 MB |
| + unrealizedJustified / `ForkChoice.balances` / 3 FCR balance arrays | 2 B/val each if distinct (often same reference) | 0-10 MB | 0-20 MB |
| `equivocatingIndices` | 4 B each | < 10 KB (slashing count, UNVERIFIED) | same |
| `queuedAttestations` | ~5 B × attesters/slot | ~0.2 MB | ~0.3 MB |
| ProtoNodes | ~430 B raw/node (10 roots ×32 B + ~11 numbers + 2 bigints + flags); Gloas ≈ 2-3 nodes/block | 64 blocks ≈ 55-80 KB; 200 blocks ≈ 170-260 KB (JSON ~2-3×) | same |
| PTC bitvectors (Gloas, PTC_SIZE=512) | 3 × 64 B = 192 B/block | 200 blocks ≈ 38 KB | same |

Total ≈ **8-12 MB per 1M validators** minimal (next votes + 1 balances array), up to ~25 MB per 1M with everything uncompressed. Votes dominate by ~2 orders of magnitude over nodes. `voteNextSlots` and `voteNextIndices` are highly repetitive (most validators voted in the last ~2 epochs for a handful of nodes) so they should compress very well (UNVERIFIED — not measured). Balances can be dropped if the justified/unrealized checkpoint states are also preserved (they're derivable via `getEffectiveBalanceIncrementsZeroInactive()`), but those states are currently wiped at boot.

---

## 6. GitHub history (issues / PRs)

From read-only `gh search`/`gh issue|pr view` (2026-10-10). State/dates re-checked for the starred items; summaries of the other thread contents are from a subagent's reads, not re-read line by line.

### 6.1 Fork-choice persistence — never implemented, two open issues

| # | State | Summary |
|---|---|---|
| ★ [#8592](https://github.com/ChainSafe/lodestar/issues/8592) "Persist fork_choice on stop and load on restart" | **open**, 2025-10-31 (twoeths) | Restart ignores the old fork choice and starts from the finalized-state head → behind EL and peers. Points to Lighthouse load (`beacon_chain.rs#L608` @e5b4983) / persist (`#L7503` @af9cae4). nflaig (2026-09-28): would also fix a **hot-DB leak** (pre-restart orphans unknown to the rebuilt fork choice are never deleted by `archiveBlocks`; 17 stranded envelopes on glamsterdam-devnet-8); unclean shutdowns still need a fallback, e.g. #10206's "delete hot entries whose root isn't in fork choice". |
| ★ [#4000](https://github.com/ChainSafe/lodestar/issues/4000) "Persist fork-choice state > start from head" | **open**, 2022-05-10 (dapplion) | Restart-from-finalized reverts the head; caused #3647/#3717. Comments: restart-from-finalized is a useful recovery path for buggy ELs (g11tech); needs an enable/disable flag (wemeetagain). |
| [#3717](https://github.com/ChainSafe/lodestar/issues/3717) | closed 2022-05-10 → #4000 | Restart from finalized makes fcU revert the EL head by hundreds of blocks. |
| [#3647](https://github.com/ChainSafe/lodestar/issues/3647) | closed 2022-05-10 → #4000 | "Error pushing notifyForkchoiceUpdate" flood after restart (kintsugi, besu). |
| [#1526](https://github.com/ChainSafe/lodestar/issues/1526) / [#1527](https://github.com/ChainSafe/lodestar/pull/1527) | closed 2020-09 | Origin of current behaviour: stop replaying unfinalized blocks on restart, rebuild from finalized. wemeetagain then: preferred long-term = persist/restore fork choice. |
| [#911](https://github.com/ChainSafe/lodestar/issues/911) | closed 2020-05 | Early proposal to persist state cache + fork choice; "don't persist the state cache, rebuild it". |
| ★ [#10206](https://github.com/ChainSafe/lodestar/pull/10206) | **closed unmerged**, 2026-09-28 (nflaig) | Delete hot envelopes whose root isn't in fork choice on finalization (cleanup for pre-restart orphans). |
| ★ [#8527](https://github.com/ChainSafe/lodestar/pull/8527) "feat: sync from unfinalized checkpoint state" | merged 2025-10-22 (v1.36.0 per release metadata, UNVERIFIED) | Added `--lastPersistedCheckpointState`, `--unsafeCheckpointState`, `GET /eth/v1/lodestar/persisted_checkpoint_state`. Start-from-unfinalized-anchor escape hatch; does not persist fork choice. Predecessor API: [#7541](https://github.com/ChainSafe/lodestar/pull/7541) (holesky rescue, 2025-03). |
| [#7255](https://github.com/ChainSafe/lodestar/pull/7255) | (referenced in code) | Reason persisted checkpoint states are deleted at boot (`persistentCheckpointsCache.ts:220-222`, found on mekong devnet). |

No search hits for: "proto array persist", "persist votes", "fork choice snapshot", "forkchoice dump", "persistCheckpointStates", "replay blocks on startup".

### 6.2 Recent persistence PRs (requested refs)

- ★ [#10267](https://github.com/ChainSafe/lodestar/pull/10267) persist earliest available slot — merged 2026-10-08. Single-value bucket; CLI-owned initial value per init path; written before prune deletes. Context: #10181, #10185.
- ★ [#10287](https://github.com/ChainSafe/lodestar/pull/10287) optionally persist produced execution payload envelopes — merged 2026-10-07, closes #9708. **Debug SSZ file dump of self-produced envelopes** (`--chain.persistProducedPayloadEnvelopes`), not restart persistence. Follow-up #10305 (open): persist orphaned envelopes.
- ★ [#10297](https://github.com/ChainSafe/lodestar/pull/10297) add fork choice v2 debug fields — merged 2026-10-07; exactly `attestationScore`, `stateRoot`, `unrealizedJustifiedRoot`, `unrealizedFinalizedRoot` in node `extraData` (verified from `git show d23dd6295`). No Gloas/PTC additions (those are #9444 / #10191).
- ★ [#10327](https://github.com/ChainSafe/lodestar/pull/10327) persist proposer preferences across restarts — merged 2026-10-09. Persist-on-`persistToDisk` / restore-in-`loadFromDisk` pattern (same as op pool); crash = nothing persisted. **Closest precedent for a persist-on-shutdown fork-choice dump.**

### 6.3 fcU on restart / "Too deep reorg"

| # | State | Summary |
|---|---|---|
| ★ [#9716](https://github.com/ChainSafe/lodestar/issues/9716) | closed 2026-07-31 | Problem C: geth `Refusing too deep reorg` / `Served engine_forkchoiceUpdatedV3 err="Too deep reorg" errdata={"err":"reorg depth 18446744073684134506 exceeds limit 32"}` on every fcU during deep catch-up; Lodestar engine state flaps SYNCING↔SYNCED. Suggested: suppress flap logging during sync and/or skip per-block fcU during finalized range sync. (The 1.8e19 depth is the uint64 underflow later fixed in geth #35804.) Not implemented. |
| ★ [#10005](https://github.com/ChainSafe/lodestar/pull/10005) | merged 2026-09-04 | Orphaned FULL leaf from range-synced old envelopes became head → stale fcU → `Too deep reorg` (devnet-9). Fix: don't import orphaned envelopes of old blocks. Remaining gap #10008 (open). |
| ★ [#9332](https://github.com/ChainSafe/lodestar/pull/9332) | **open**, 2026-05-06 (lodekeeper) | fcU `INVALID` → typed error with `latestValidHash` → `validateLatestHash` + head recompute. See §2.3 risk note. |
| [#9243](https://github.com/ChainSafe/lodestar/issues/9243) | open | When to send fcU in Gloas (tangential). |
| [#8895](https://github.com/ChainSafe/lodestar/pull/8895) / [#8952](https://github.com/ChainSafe/lodestar/pull/8952) | merged 2026-02 | fcU result metrics / dashboard panel. |

No Lodestar hits for "maxreorgdepth", "38006", "TooDeepReorg".

### 6.4 go-ethereum reorg-depth guard (premise check)

Merge dates verified with `gh pr view`; release attribution is from PR/release metadata read by the subagent (UNVERIFIED by me).

| PR | Merged | Release | Change |
|---|---|---|---|
| [#34767](https://github.com/ethereum/go-ethereum/pull/34767) allow reorging the head block to a parent | 2026-05-06 | v1.17.3 | Introduces `-38006 Too deep reorg` (execution-apis #786), cap 32. |
| [#35335](https://github.com/ethereum/go-ethereum/pull/35335) configurable max reorg depth | 2026-07-14 | v1.17.5 | `--engine.maxreorgdepth` (default 32, 0 = unlimited). |
| [#35391](https://github.com/ethereum/go-ethereum/pull/35391) allow depth == max | 2026-07-23 | v1.17.5 | `>=` → `>`. |
| [#35519](https://github.com/ethereum/go-ethereum/pull/35519) make headBlock reorging to finalized possible | 2026-08-12 | v1.17.6 | Finalized-ancestor shortcut `<=` → `<`: head == geth finalized now hits the depth check instead of silent `VALID`. |
| [#35804](https://github.com/ethereum/go-ethereum/pull/35804) don't treat a forward canonical update as a reorg | 2026-10-08 | v1.17.8 | Fixes uint64-underflow false positives after unclean geth shutdown. |

So the guard predates 1.17.8 (since 1.17.3); "≥1.17.8" in the incident description is not where the behaviour started. Which geth change made this particular restart incident newly visible is UNVERIFIED (candidates: #35519 for head == finalized; the guard itself for heads above finalized).
