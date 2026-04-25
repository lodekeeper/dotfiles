# Gloas genesis bring-up — Tracker

Last updated: 2026-04-24 17:48 UTC

## Goal
Run latest Lodestar `origin/unstable` in the glamsterdam-devnet-0 minimal config with `gloas_fork_epoch: 0`, replacing Prysm, and identify the first concrete success/failure signal.

## Current request
Nico asked to run the local repro from the glamsterdam-devnet-0 note, but with Prysm replaced by a locally built Lodestar image from latest unstable.

## Artifacts
- Kurtosis config: `notes/gloas-genesis/kurtosis.yaml`
- Source note: `https://notes.ethereum.org/@ethpandaops/glamsterdam-devnet-0`
- Fresh worktree: `/home/openclaw/lodestar-gloas-genesis-unstable` @ `origin/unstable`

## Phase plan
- [x] Confirm exact config from note / Nico message
- [x] Create fresh `origin/unstable` worktree
- [x] Write local Kurtosis args file
- [x] Build local Docker image `lodestar:gloas-genesis-unstable`
- [x] Launch Kurtosis enclave
- [x] Inspect Lodestar logs / first failure or health signal
- [ ] Summarize findings back in topic #8800
- [ ] Turn repro into code fix

## Concrete findings so far
1. **Kurtosis compatibility gap on this host:** preinstalled Kurtosis was `1.15.2`, which cannot interpret the current `ethereum-package` due to missing `GpuConfig`. Fixed locally by installing CLI `1.18.1` under `~/.local/bin/kurtosis-1.18.1` and restarting the engine to `1.18.1`.
2. **Exact note config is no longer runnable as-written here:** `bbusa/checkpointz:fix` is not pullable (`pull access denied`). I used a fallback config with only one non-core deviation: `checkpointz_params.image: ethpandaops/checkpointz:latest`.
3. **Core repro succeeded:** the enclave booted with 3x geth EL + 3x Lodestar CL + 3x Lodestar VC; Lodestar peers correctly (2 connected peers on each node), validator/attestation traffic is active, and Gloas genesis is generated successfully.
4. **Actual failure mode:** the chain remains stuck at **head slot 0** while wall clock advances (e.g. current slot 9/10). Validator APIs reject proposer duties and block production with `503 Node is syncing - waiting for peers`, so no one can propose the first post-genesis block.
5. **Likely root cause in code:** `packages/beacon-node/src/sync/sync.ts` marks the node `Stalled` once `currentSlot - headSlot` exceeds tolerance and no peer is ahead; then `packages/beacon-node/src/api/impl/validator/index.ts:notWhileSyncing()` throws `NodeIsSyncing("waiting for peers")` for proposer duties / `produceBlockV4`. In a multi-node genesis network where all peers are equally at slot 0, this creates a circular deadlock: no advanced peer exists yet, but proposer duties are also denied, so the chain never leaves genesis.

## Current branch / patch status
- **Latest rerun requested by Nico (2026-04-24 19:00 UTC):** PR #9273 branch `nflaig/gloas-genesis` (`e81c1e2321`) built locally as `lodestar:gloas-genesis-pr9273` and launched with the same Kurtosis args file shape (`notes/gloas-genesis/kurtosis-pr9273.yaml`).
- **Observed behavior on PR #9273 branch (before local patching):** this branch still hits the *earlier* genesis deadlock stage.
  - head remains at slot 0 while peers are connected (`connected=2` on each CL)
  - validator APIs still return `503 Node is syncing - waiting for peers`
  - example logs:
    - `getProposerDuties failed with status 503: Node is syncing - waiting for peers`
    - `produceBlockV4` called at slots 9/10, but returns status 503 rather than the later proto-array error
  - per Nico instruction, the enclave was stopped immediately after this early failure was triaged rather than being left running for more epochs
- **Latest local patch stack on top of PR #9273 (2026-04-24 20:05+ UTC):**
  1. kept the minimal validator sync-gate exception for stalled-at-genesis with connected peers
  2. changed post-Gloas parent-hash selection in
     - `packages/beacon-node/src/chain/prepareNextSlot.ts`
     - `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts`
     to use `state.latestBlockHash` directly (spec-aligned with `prepare_execution_payload`) instead of deriving from `latestExecutionPayloadBid.parentBlockHash`
  3. patched `packages/fork-choice/src/protoArray/protoArray.ts::ProtoArray.initialize()` to call `onExecutionPayload(...)` immediately for a valid Gloas anchor block, materializing a FULL variant at initialization so the genesis anchor is treated as a real full parent by `shouldExtendPayload()` / parent-status lookup
- **Result so far:**
  - patch (2) removed `PROTO_ARRAY_ERROR_UNKNOWN_PARENT_BLOCK`
  - remaining hypothesis is that genesis was still inconsistently treated as empty vs full after (2), leading to the later EL-side rejection
  - patch (3) is intended to remove that full/empty classification inconsistency before the next short rerun
- **Current state after short rerun (2026-04-24 ~20:21 UTC):**
  - with the FULL-anchor patch applied, the previous concrete errors did **not** recur in the short window:
    - no `PROTO_ARRAY_ERROR_UNKNOWN_PARENT_BLOCK`
    - no EL `block header access list hash mismatch`
  - however the chain still remained stuck at `headSlot=0`
  - new visible behavior: CL logs repeatedly emit `Skipping PrepareNextSlotScheduler - head slot is too behind current slot` while VCs continue attesting to the genesis head (`head=0x4cc3...552f` at slot 22)
  - I did **not** observe a new concrete block-publication error before stopping the enclave per Nico's instruction to stop once the early failure mode is clear
- **Interpretation:** the latest patch stack changed the failure mode again, but a tighter capture around the first proposer window exposed the real next blocker before any head advance:
  - `getProposerDuties` succeeds
  - `produceBlockV4` is called at slot 14
  - block production now fails with `Parent execution payload envelope not found slot=0, root=<genesis root>`
- **Root cause of this blocker:** once genesis is treated as a FULL parent, Lodestar tries to fetch `parentExecutionRequests` from a parent execution payload envelope for the slot-0 Gloas anchor. But there is no envelope for genesis; instead `upgradeStateToGloas()` initializes `latestExecutionPayloadBid.executionRequestsRoot` to `hash_tree_root(ExecutionRequests.defaultValue())`. So the first child of genesis should use default/empty execution requests for the parent.
- **Latest local patch (after this finding):**
  - patched `packages/beacon-node/src/chain/chain.ts::getParentExecutionRequests()` to return `ssz.electra.ExecutionRequests.defaultValue()` when `parentBlockSlot === GENESIS_SLOT`
  - rationale: align the runtime parent-request lookup with the fork-upgrade initialization / spec expectations for a Gloas-from-genesis anchor
- **Current state after final short rerun (2026-04-24 ~20:32 UTC):**
  - after patching `getParentExecutionRequests()` to return default/empty `ExecutionRequests` for a slot-0 Gloas parent, the chain successfully advanced past genesis
  - observed on `cl-2-lodestar-geth`:
    - `head_slot = 3`
    - `is_syncing = false`
  - none of the earlier first-post-genesis blockers appeared in the captured window:
    - no `503 Node is syncing - waiting for peers`
    - no `PROTO_ARRAY_ERROR_UNKNOWN_PARENT_BLOCK`
    - no EL `block header access list hash mismatch`
    - no `Parent execution payload envelope not found slot=0`
  - enclave was stopped immediately after confirming head advancement
- **Interpretation:** the combined local patch stack is sufficient to get the mixed geth + Lodestar Gloas-from-genesis devnet past the genesis deadlock and through the first post-genesis blocks.

## Reduction pass update (2026-04-24 ~20:43 UTC)
- reran the repro **without** the local `packages/fork-choice/src/protoArray/protoArray.ts` FULL-anchor patch
- result: genesis still advances, so the proto-array patch is **not required** for the early deadlock fix
- concrete evidence from validator logs in the reduced variant:
  - `publishExecutionPayloadEnvelope` succeeded for slot 1
  - `publishExecutionPayloadEnvelope` succeeded again for slot 4
- after that, a **later** blocker remains: from slot 6 onward, `publishExecutionPayloadEnvelope` starts failing again with `PAYLOAD_ERROR_EXECUTION_ENGINE_INVALID`
- EL-side reason is still the same class of error as before:
  - repeated `engine_newPayloadV5` rejection with `block header access list hash mismatch`
- practical outcome:
  - drop the proto-array patch from the candidate fix set
  - keep the reduced local patch set focused on:
    1. relaxed proposer-duty sync gate at genesis with peers connected
    2. `state.latestBlockHash` parent-hash selection in Gloas paths
    3. slot-0 Gloas parent fallback for `ExecutionRequests`

## Current deeper hypothesis (2026-04-24 ~20:52 UTC)
- fetched a live failing envelope from the reduced stack via the Lodestar REST API:
  - slot `26`
  - block root `0x77923eb70fd785aab1b41da632f3440812d41cee8d283d8e7c228b569ce7b81f`
  - payload block hash `0x409df3b815177444e0a59041f77a3e8b88bdfcdd684be64ecbb8c255546289a9`
  - `transactions=9`, `withdrawals=4`, `blockAccessList` length ≈ `33454` bytes
- Lodestar evidence suggests the payload is being relayed, not recomputed:
  - `getExecutionPayloadEnvelope` returns `200`
  - Lodestar logs `Produced execution payload envelope ... blockHash=...`
  - immediately afterward `publishExecutionPayloadEnvelope` fails during `importExecutionPayload` with `PAYLOAD_ERROR_EXECUTION_ENGINE_INVALID`
- Geth evidence suggests the failing check is **inside EL validation of the payload itself**:
  - repeated `engine_newPayloadV5` rejection
  - repeated `BAD BLOCK` log with `block header access list hash mismatch (remote=<hash> local=<hash>)`
  - Geth labels every failing candidate as `Block: 1`, which is consistent with repeatedly trying to build the first post-genesis execution block and then rejecting it
- working hypothesis:
  - after the CL-side genesis deadlock is fixed, the remaining issue is likely an EL-side `blockAccessList` / header-hash inconsistency in geth's Gloas payload production or validation path, not the earlier Lodestar proto-array/parent-hash bug.

## Additional source-level evidence (2026-04-24 ~21:05 UTC)
- decoded the captured slot-26 `block_access_list` with the **exact** EL fork source used by the image (`mariusvanderwijden/go-ethereum`, commit `2f6a1a406a1d37794264842ffce107e787a769f0`, branch/tag context `bal-devnet-4`)
- result from the fork's own BAL decoder/hash implementation:
  - RLP bytes: `33454`
  - BAL items: `898`
  - decoded hash: `0xb3a30caf3cbda1f55176c75354b2f6426b5fdcf4c637217a11a57646f689913a`
- implication: the Lodestar-captured `block_access_list` blob is structurally valid for the EL fork and hashes cleanly after decode; this is strong evidence **against** CL transport corruption / JSON mangling as the primary cause
- also confirmed from the EL image labels + source checkout:
  - image branch/ref: `bal-devnet-4`
  - image revision: `2f6a1a4...`
  - merge title at that revision: `fix-amsterdam-genesis-block-access-list-hash-bal-devnet-4` / `bring bal-devnet-4 back to life`
- interpretation:
  - the exact EL build already contains a prior Amsterdam/genesis BAL-hash fix
  - the remaining tx-bearing block-1 rejection looked like a plausible **second**, later-stage BAL bug in the same experimental geth fork — but the next reduction pass materially changed that assessment.

## Offline fork-local repro results (2026-04-24 ~21:25 UTC)
- built tx-bearing Amsterdam/Gloas payloads directly through the fork's **beacon-engine miner path** (`miner.BuildTestingPayload`) and then imported them back through the same fork's validator path (`engine.ExecutableDataToBlock` + `InsertChain`)
- results:
  - generic tx-bearing cases all passed
  - importantly, these also passed for high-slot / block-number-1 shapes matching the live repro, e.g.:
    - `slot=26`, `timestamp=312`, `txs=9`, `withdrawals=4`
    - `slot=30`, `timestamp=360`, `txs=9`, `withdrawals=4`
- stronger replay:
  - decoded the **exact raw tx sequence** from the captured live slot-26 envelope
  - tx mix is not simple transfers: one contract creation followed by eight large contract calls to the freshly deployed contract
  - sender recovered from signatures: `0x4d1CB4eB7969f8806E2CaAc0cbbB71f88C8ec413`
  - chain ID in the live txs: `3151908`
  - replayed that exact tx sequence plus the live withdrawal set through `BuildTestingPayload`
  - result: **IMPORT_OK** on the fork-local chain
- implication:
  - this is **not** a generic self-build/self-import mismatch inside the experimental geth fork
  - it is also **not** caused by the live tx mix alone
  - the live failure therefore depends on additional runtime context that is absent from the isolated fork-local replay

## Refined hypothesis after replay
Most likely remaining classes are now:
1. **CL↔EL round-trip/context mismatch** on the live path
   - payload body itself can be self-consistent offline
   - the discrepancy may live in what accompanies it at `engine_newPayloadV5` time (for example parent beacon root / request context / other live block context), or in JSON-RPC round-tripping of the post-Gloas fields
2. **Live parent-state/context divergence**, not the txs themselves
   - e.g. something about the real devnet prestate, parent block context, or multi-node runtime conditions differs from the minimal offline genesis harness

## Additional static checks
- Lodestar → geth JSON field names line up for the Gloas payload shape:
  - `blockAccessList`
  - `slotNumber`
  - `parentBeaconBlockRoot`
- Lodestar's `processExecutionPayload()` does **not** pass `envelope.beaconBlockRoot` into `notifyNewPayload()`.
  - It passes `fromHex(protoBlock.parentRoot)` as `parentBeaconBlockRoot`, which matches the intended Engine API shape.
- The REST envelope's top-level `data.beacon_block_root` is **not sufficient** by itself to reconstruct the original execution block hash via `ExecutableDataToBlock(...)`.
  - Using it as the EL `parentBeaconBlockRoot` produced a block-hash mismatch during offline replay.
  - That is consistent with this API field representing the current beacon block root rather than the exact EL header aux input needed for `newPayload` reconstruction.

## Boundary instrumentation result (2026-04-24 ~21:26 UTC)
- added temporary Lodestar logging at:
  1. `processExecutionPayload(...)` boundary
  2. `ExecutionEngineHttp.notifyNewPayload(...)` right before `engine_newPayloadV5`
- short rerun result:
  - the instrumentation shows the live `engine_newPayloadV5` context is internally coherent on the Lodestar side
  - for each tx-bearing slot, Lodestar logs a consistent tuple of:
    - `blockHash`
    - `parentHash`
    - `blockNumber=1`
    - `slotNumber`
    - `transactions=9`
    - `withdrawals=4`
    - `parentBeaconBlockRoot` = previous beacon block root
    - `executionRequestsCount=0`
    - `blockAccessListBytes=33454`
    - stable `serializedTransactionsSha256=6372a61d4ebaa456834c77f0b3809a6ca7a16d45e8ffcb1e057e70ba56ce79a1`
  - importantly, the tx-bearing `blockAccessListSha256` changes every slot as the beacon-root context changes, which is expected if BAL construction depends on beacon/system-call context
- concrete tx-bearing samples from Lodestar logs:
  - slot 5 → block hash `0x94622961db43ed1ea7108384bb35b9bb8c69a4b366c4eab9277a6e07034a0695`, BAL sha256 `554e5dbe...`
  - slot 6 → block hash `0xcd3a3b341585f21ff67987c9ea5f37c303d68ac5c5f7940b96c0e50ae7eb902f`, BAL sha256 `fa75be0e...`
  - slot 7 → block hash `0x3ab93e5f0c88d64c236e167dfac6615a39d1fb9756bde33d01eaf3bff82acca2`, BAL sha256 `eecf4ae1...`
  - slot 8 → block hash `0x79ebea90b170b197f07da1b6a0732f393d33550e47b26f6f406337524dd463a8`, BAL sha256 `75ce2dc1...`
  - slot 9 → block hash `0xa81f9a876663ed9bace0ce1dcf9db990bc66bbe8cc6110c3bee8e5dc4cb3e2ac`, BAL sha256 `822bccaf...`
- matching EL failures on the same run:
  - slot 7 / block `0x3ab93e5f...` → `remote=c9407f04... local=cd3d9c62...`
  - slot 8 / block `0x79ebea90...` → `remote=40eb7ce1... local=c5e376cb...`
  - slot 9 / block `0xa81f9a87...` → `remote=b990a8f6... local=8db571d8...`
  - slot 10 / block `0x85b39dc3...` → `remote=53dc1004... local=ad2b1861...`
  - slot 11 / block `0xa5ad41db...` → `remote=bdeef610... local=94a94172...`
  - slot 12 / block `0x8c667283...` → `remote=c70670d3... local=3d887149...`
- interpretation:
  - the failure is **not** explained by a static or mangled outbound request object on the Lodestar side
  - Lodestar is submitting coherent, slot-specific BAL blobs whose size and tx fingerprint are stable and whose beacon-root context advances correctly
  - the mismatch survives across multiple slots with fresh BAL blobs, so the remaining bug is now most plausibly in **geth's BAL recomputation under live beacon-root/system-call context**, not in a one-off CL serialization mistake

## Build-vs-import boundary comparison (2026-04-24 ~21:32 UTC)
- added one more temporary Lodestar log point at the **build side**: `notifyForkchoiceUpdate(...)` right before `engine_forkchoiceUpdatedV4`
- reran a short repro and compared build-side payload attributes to later import-side `newPayload` context for the same slots
- result: the CL-side aux context matches across build and import
  - example slot 7:
    - build side (`engine_forkchoiceUpdatedV4`):
      - `headBlockHash = genesis EL hash`
      - `slotNumber = 0x7`
      - `parentBeaconBlockRoot = 0xd1194b9b66f0b8a49d740047ce0f1547f94cef1ed10e34b78c43118c0b6defa6`
      - `withdrawals = 4`
    - produced payload:
      - `blockHash = 0x17c2e98841623f5a9233b332c0d8ea673f857d0a6930c8628f6d688d6f32a4fa`
      - `transactions = 9`
    - import side (`engine_newPayloadV5`):
      - `slotNumber = 7`
      - `parentBeaconBlockRoot = 0xd1194b9b66f0b8a49d740047ce0f1547f94cef1ed10e34b78c43118c0b6defa6`
      - same block hash / tx count / withdrawal count
  - same pattern holds for later failing slots too:
    - slot 10 build side: `parentBeaconBlockRoot = 0xbcc36768...`, slot `0xa`
    - slot 10 import side: same `parentBeaconBlockRoot`, same block hash `0xe495b8d4...`
    - slot 11 build side: `parentBeaconBlockRoot = 0x88358001...`, slot `0xb`
    - slot 11 import side: same `parentBeaconBlockRoot`, same block hash `0x2c851e8f...`
- implication:
  - the failure is **not** explained by a mismatch between the EL build request (`forkchoiceUpdatedV4`) and the later import request (`newPayloadV5`) on the Lodestar side
  - both sides agree on the changing beacon-root context, slot number, and payload identity
  - this further narrows the live failure to the geth fork’s handling of these repeated block-number-1 / changing-parent-beacon-root payloads, rather than a CL-side context mix-up

## Clean-source catalyst repro result (2026-04-24 ~21:48 UTC)
- implemented a focused temporary test in the clean fork checkout (`eth/catalyst/gloas_repeated_fixed_head_test.go`) that models the live pattern much more closely:
  - fixed EL head at genesis
  - repeated `ForkchoiceUpdatedV4 -> getPayload -> NewPayloadV5` cycles
  - exact live slot-26 txs + withdrawals loaded from the captured REST envelope
  - real live slot/timestamp/parent-beacon-root progression from the instrumented CL run (slots 1-12)
  - zero-tx warmup for slots 1-5, tx-bearing payloads for slots 6-12
- result in the **clean source tree**:
  - zero-tx slots 1-5: `VALID`
  - tx-bearing slots 6-12: also all `VALID`
  - no `block header access list hash mismatch`
- stronger follow-up:
  - JSON-roundtripped the built `ExecutableData` through the fork's own `encoding/json` codec before calling `NewPayloadV5`
  - result: still all tx-bearing slots `VALID`
  - `origBalHash == rpcBalHash` for every tested slot, so a plain `ExecutableData` JSON marshal/unmarshal roundtrip does **not** corrupt the BAL blob in the clean fork
- implication:
  - the public clean source at `2f6a1a4` still does **not** reproduce the live devnet failure, even under a much tighter API-sequence simulation
  - this materially raises the probability that the failing runtime behavior depends on something **outside** the clean checked-out source path we tested
  - strongest candidates now:
    1. a difference between the running devnet EL image and the clean GitHub branch/source checkout we tested
    2. an engine-RPC-layer/runtime path not exercised by the in-process catalyst test harness
    3. some remaining live environment difference in genesis/state/config not captured by the local harness

## Additional source inconsistency found
- in the clean source checkout, `eth/catalyst/api.go::GetPayloadV4` is still gated as if it were a Prague/`PayloadV3` method:
  - allowed payload versions: `[]engine.PayloadVersion{engine.PayloadV3}`
  - allowed forks: `[]forks.Fork{forks.Prague}`
- that is visibly stale/inconsistent with `ForkchoiceUpdatedV4` using `PayloadV4` for Amsterdam slot-number payloads
- this did not block the local repro because the test used the package-internal `getPayload(...)` helper after noticing the mismatch, but it is another data point that the clean public source may not match the exact runtime path/image used on the devnet.

## Updated best next step
- move one level closer to the actual failing runtime:
  1. exercise the engine methods over the real RPC server/client path (not just in-process method calls), **or**
  2. obtain / reconstruct the exact dirty EL source state used to build the devnet image.
- if neither is immediately available, the best near-term action is to treat the BAL mismatch as likely image/runtime-specific rather than proven against the clean source branch.
- **Interpretation:** PR #9273 branch does **not** include the local stalled-at-genesis validator-gate workaround that moved the repro forward to `PROTO_ARRAY_ERROR_UNKNOWN_PARENT_BLOCK`.
- **Previous local experimental patch stack (not in PR #9273):**
  - Patch 1: `packages/beacon-node/src/api/impl/validator/index.ts`
    - allow validator APIs past `SyncState.Stalled` when the node is still on the genesis block **and** already has connected peers
    - this successfully removed the original `503 Node is syncing - waiting for peers` deadlock for proposer duties
  - Observed next blocker after Patch 1: validators fetch proposer duties and attempt `produceBlockV4`, but block production fails with `PROTO_ARRAY_ERROR_UNKNOWN_PARENT_BLOCK`
  - Patch 2 (attempted): proto-array/bootstrap fixes for initialized Gloas FULL variants (`packages/fork-choice/src/protoArray/protoArray.ts`, `packages/beacon-node/src/chain/forkChoice/index.ts`)
    - result: fork-choice shows three genesis-root variants instead of two, but block production still fails with the same unknown-parent error
  - Patch 3 (attempted): genesis-aware parent-hash selection in
    - `packages/beacon-node/src/chain/prepareNextSlot.ts`
    - `packages/beacon-node/src/chain/produceBlock/produceBlockBody.ts`
    - intent: when `latestExecutionPayloadBid.parentBlockHash` is zero at genesis, use `latestExecutionPayloadBid.blockHash` as the parent execution hash for the first extension
    - result: proposer duties still succeed, but `produceBlockV4` still returns `PROTO_ARRAY_ERROR_UNKNOWN_PARENT_BLOCK`

## Concrete runtime findings after latest rerun
1. Mixed geth + Lodestar devnet still boots reliably on latest `origin/unstable` with the fallback `checkpointz` image.
2. Validators now reach the proposer path: example `vc-3-geth-lodestar` at slot 14 logs `Producing block ...` and calls `produceBlockV4`.
3. The chain remains stuck at `head_slot=0` because `produceBlockV4` still fails with `PROTO_ARRAY_ERROR_UNKNOWN_PARENT_BLOCK`.
4. Head-state inspection shows:
   - `latest_block_hash = 0x...EL_genesis_hash`
   - `latest_execution_payload_bid.block_hash = 0x...EL_genesis_hash`
   - `latest_execution_payload_bid.parent_block_hash = 0x00...00`
   This zero parent hash is still involved in the first post-genesis block path somehow.


- **Minimization state update (2026-04-24 later):** the *current* `~/lodestar-gloas-genesis-pr9273` working tree no longer carries any live diff in `packages/fork-choice/src/protoArray/protoArray.ts` or `packages/beacon-node/src/chain/forkChoice/index.ts`. So the currently testable stack is already smaller than the historical narrative suggests: (1) narrowed proposer-only validator sync-gate exemption, (2) `latestBlockHash`-based parent-hash selection in `prepareNextSlot.ts` / `produceBlockBody.ts`, and (3) slot-0 `ExecutionRequests.defaultValue()` fallback in `chain.ts`. Next validation step is a short rerun on this reduced stack.

## Next immediate steps
1. Minimize the local patch stack by reverting one patch at a time and re-running the same short Kurtosis repro.
2. Separate truly required fixes from incidental/debugging changes (especially the proto-array FULL-anchor patch).
3. Once reduced, summarize the minimal fix set and decide whether to convert it into a clean PR / review response.

## Latest live rerun check (2026-04-24 late)

Using the currently reduced `~/lodestar-gloas-genesis-pr9273` stack (no live `protoArray.ts` / `forkChoice/index.ts` diff, narrowed proposer-only stalled-sync exemption still present), the running `gloas-genesis-pr9273` enclave is now healthy past genesis:

- CL chain is advancing and all three nodes report synced, non-optimistic heads
  - `/eth/v1/node/syncing` reports `head_slot=6`, `is_syncing=false`, `el_offline=false` on all three CLs
  - `/eth/v2/debug/beacon/heads` shows canonical non-optimistic heads through slots `1,2,3,4,6`
- Validators are actively producing blocks on the reduced stack
  - current `vc_block_produced_total` values are `2`, `1`, and `3` across the three validator clients
- The earlier EL-side rejection signal is **not reproducing on the current live run**
  - recent EL logs show repeated successful `engine_newPayloadV5` imports (`Imported new potential chain segment number=1 ...`)
  - recent CL/EL log scans show none of the earlier concrete blockers: no `Node is syncing - waiting for peers`, no `UNKNOWN_PARENT_BLOCK`, and no fresh `access list hash mismatch` / `PAYLOAD_ERROR_EXECUTION_ENGINE_INVALID` lines in the live tail

Current interpretation:
- the reduced local stack is sufficient to get the devnet **past genesis and into healthy post-genesis block production**
- the previously observed access-list-hash mismatch now looks non-sticky / not present in the current live run, so it should not be treated as the standing blocker without a fresh reproduction

Next useful step:
- turn this into a clean minimization/proof artifact: record the reduced patch set precisely, capture the successful enclave state, and decide which remaining patch bucket(s) can be reverted without losing healthy post-genesis progression

## Paused / cleanup
- 2026-04-24 ~21:25 UTC: Nico asked to stop working on this for now and remove the Kurtosis instance.
- cleanup completed:
  - ran `kurtosis enclave rm -f gloas-genesis-pr9273`
  - `kurtosis enclave ls` is empty afterward
  - no leftover Docker containers match `gloas-genesis-pr9273`
- investigation is paused with the current hypothesis + repro artifacts preserved.
- 2026-04-24 ~22:13 UTC: Nico said to consider this done, so this tracker is now closed unless explicitly reopened later.

## Late refinement — canonical vs rejected block-1 candidates

Follow-up log correlation showed the live issue is more specific than a generic EL/import failure:

- The canonical slot-1 beacon block on CL-1 commits to execution `block_hash = 0x12445076c8d85d6083402b4f58efd529f3279877c1a5b87c1be78416e442d55e` via `signed_execution_payload_bid.message.block_hash`.
- `el-2-geth-lodestar` and `el-3-geth-lodestar` never show an import of that canonical execution hash, and their logs never mention it directly.
- Instead, they repeatedly reject a *series of different execution block-1 candidates* with `block header access list hash mismatch`.
  - Example bad block hashes on EL-2: `0x94bed254...`, `0xa8341b6f...`, `0x789b5cb4...`
  - Example bad block hashes on EL-3: `0x491764a1...`, `0x409df3b8...`, `0x64be04bd...`, `0xefb8d095...`
- A tight count on both EL-2 and EL-3 shows every BAD BLOCK in the current live run is still **execution block number 1**.

Interpretation:
- one branch can clearly progress the CL chain past genesis
- but at least two EL/CL pairs remain stuck with execution head at genesis and keep cycling through alternate block-1 payload candidates that fail EL validation
- so the next debugging lane is specifically **why non-canonical nodes keep building / validating divergent execution block-1 candidates instead of converging onto the canonical imported block-1 payload**
