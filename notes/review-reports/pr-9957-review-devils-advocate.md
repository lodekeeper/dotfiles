# PR #9957 — Devil's Advocate Review

Reviewer: review-devils-advocate
Reviewed commit: 258d7d1ca8e6f170adc0c8c9330c07e1fd8a19c0

PR: ChainSafe/lodestar#9957 "chore: remove blob related code" (base `origin/unstable` 0586e6e617)

## Devil's Advocate Review

### Overall Assessment
The approach is sound. This is spec-sanctioned removal of code that can no longer run on any supported network. I found **no concrete regression** for (a) post-Fulu operation (current mainnet) or (b) Gloas (payload envelope / column paths).

### Objections (max 3)

**None (no findings).** I tried to make the case against the PR on each axis below, and none of those attempts held up.

### Premise checks (why there's no objection)

1. **Necessity / spec interpretation.** The Fulu p2p spec (`specs/fulu/p2p-interface.md`) says:
   - "`blob_sidecar_{subnet_id}` is deprecated."
   - BlobSidecarsByRange v1 / BlobSidecarsByRoot v1: "Deprecated as of `FULU_FORK_EPOCH + MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`." The MUST-serve obligation only applies "During the deprecation transition period".

   I checked the deprecation date for every network in `packages/config/src/chainConfig/networks/*.ts` against today (2026-11-05):
   - mainnet: Fulu 2025-12-03, plus 4096 epochs × 384 s ≈ 18.2 d → ended ~2025-12-22
   - sepolia: Fulu epoch 272640 → ended ~2025-11
   - hoodi: Fulu epoch 50688 → ended ~2025-11
   - gnosis: Fulu 2026-04-14, plus 16384 epochs × 80 s ≈ 15.2 d → ended ~2026-04-29
   - chiado (inherits gnosis window): Fulu 2026-03-16 → ended ~2026-03-31
   - ephemery and plataberget: Fulu at genesis

   The obligation to serve or request blobs is over on every network Lodestar ships. Unregistering the protocols (`ReqRespBeaconNode.ts`, old `ForkSeq >= deneb` block) and dropping the topics (`topic.ts` `getCoreTopicsAtFork`, old `deneb <= fork < fulu` block) is correct. Notably, on unstable the req/resp handlers were still registered for Fulu and Gloas forks; that is now cleaned up.

2. **Simpler alternative?** Keeping the code behind a flag would mean maintaining a `DAType.Blobs` variant in every `IBlockInput` switch for gloas → heze, which the fork-forward guidance argues against. Collapsing deneb..electra into `BlockInputPreData` (`seenGossipBlockInput.ts:247`) is the lowest-branching option. Deleting the code is the simpler path.

3. **Root cause vs. symptom.** This is not a bug fix, so the angle doesn't apply. The one new branch, `verifyBlocksDataAvailability.ts:48` (deneb+ `PreData` → `NotRequired`), is needed because the state transition rejects `PreData` for post-deneb forks. It only affects pre-Fulu blocks.

### Regression hunt: post-Fulu and Gloas paths checked

Each item lists the file:line in the PR head and why it is equivalent to unstable for Fulu/Gloas inputs.

- **Versioned hashes for engine_newPayload**, `chain/blocks/verifyBlocksExecutionPayloads.ts:170-174`
  - Now derived from `block.message.body.blobKzgCommitments`. Before, Fulu used `BlockInputColumns.getVersionedHashes()`, which is built from the same commitments (`blockInput.ts:331`), or from column `kzgCommitments` that gossip/inclusion-proof validation binds to the block body.
  - This matches the spec's `NewPayloadRequest` construction exactly.
  - Gloas still short-circuits on `isBlockInputNoData` at line 150, before this code runs.
  - Cost is about 1 sha256 per blob per block, which is negligible.

- **publishBlockV2**, `api/impl/beacon/blocks/index.ts:137`
  - The condition `isDenebBlockContents && isForkPostFulu && !isForkPostGloas` gives the same results as the old if/else chain for Fulu (compute columns) and Gloas (empty, columns ride on the envelope).
  - The only difference is for pre-deneb contents, which used to throw and are now accepted. That case is pre-Fulu and intended.

- **GetBlobsTracker**, `chain/GetBlobsTracker.ts:75`
  - `!isBlockInputColumns(input)` now also returns early for Gloas `BlockInputNoData`.
  - On unstable, a NoData input fell through: it allocated or reserved a blobs buffer, called `getDataColumnSidecarsFromExecution`, which immediately returned `DataColumnEngineResult.PreFulu`, and then released the buffer.
  - Behavior is unchanged: Gloas getBlobs is still triggered via `PayloadEnvelopeInput` (`gossipHandlers.ts:619`, `unknownBlock.ts:1186`). The only visible difference is that the `dataColumnEngineResult{result="pre_fulu"}` counter stops ticking for Gloas blocks. No dashboard depends on that label for Gloas.

- **Range sync requests**, `sync/range/batch.ts:250-256, 335`
  - The Fulu column request and the Gloas envelope and column logic are unchanged. The merged condition `isForkPostFulu && withinValidRequestWindow && neededColumns.size > 0` is equivalent to the old nested `if`.

- **Range response validation**, `sync/utils/downloadByRange.ts:470` onward
  - `dataRequest = blobsRequest ?? columnsRequest` became `columnsRequest`. The early return, the envelope-only path, and parent-payload column validation keep the same order and the same guards.

- **By-root sync**, `sync/utils/downloadByRoot.ts:198`
  - Same column fetch, minus the blob branch.

- **DB write**, `chain/blocks/writeBlockInputToDb.ts`
  - The block put is now awaited directly instead of through `Promise.all([put])`. Column writes still run in parallel via `writeDataColumnsToDb`. Same durability semantics.

- **Removed metrics**
  - `beacon_get_blobs_v1_*`, `lodestar_gossip_blob_published_from_engine_total` and `lodestar_import_blobs_by_source_total` are no longer referenced by any file under `dashboards/`.

- **Remaining blob DB readers** (`chain.ts:934`, `archiveBlocks.ts:212/257/400-415`)
  - These still serve and prune existing pre-Fulu DB data. They are only reached for `isForkPostDeneb && !isForkPostFulu` blocks (`api/.../blocks/index.ts:1169, 1251`). The post-Fulu API reconstructs blobs from columns, unchanged.

- **SSE `blob_sidecar` event**
  - Every emitter on unstable was in a pre-Fulu-only path: BlockInputBlobs, the gossip blob handler, the by-root blob path and getBlobsV1. Removing them changes nothing post-Fulu.

- **Spec tests**
  - The new skip regex (`specTestIterator.ts`) only matches `deneb|electra` fork_choice blob-negative vectors.
  - The old runner-level `shouldSkip(name.includes("invalid_incorrect_proof"))` covered all forks. Removing it means the Fulu/Gloas variants now run, which is a net gain in coverage.

### Informational (outside the question's scope, not findings)

1. **Pre-Fulu epochs on custom or multi-client devnets degrade silently.** If a devnet starts at electra with Fulu at epoch > 0:
   - Lodestar imports deneb..electra blocks with `NotRequired`, i.e. no DA check.
   - `publishBlockV2` drops the blobs of its own proposals (`index.ts:137`), so other clients see Lodestar-proposed blocks as unavailable while Lodestar builds on them.
   - Per the task this pre-Fulu behavior is intended. **Counter-proposal (optional, cheap):** log a single `warn` at startup, or return a 400 from `publishBlockV2` with deneb..electra contents, when `clock.currentEpoch < FULU_FORK_EPOCH`. The misconfiguration then shows up explicitly instead of as orphaned proposals. About 5 lines; no new state.
   - Severity: info.

2. **Hidden cost: half-removed storage.** The `blobSidecars` / `blobSidecarsArchive` repositories and the archiver's hot→archive blob migration (`archiveBlocks.ts:400-415`) stay. They're now only needed to drain existing DB data, since nothing new is written.
   - A follow-up could delete the migration once `blobSidecarsArchive` pruning (`archiveBlocks.ts:257`) has cleared everything older than the retention window. Not needed for this PR.

### Verdict
**SOUND — no fundamental issues.** No post-Fulu or Gloas regression found.
