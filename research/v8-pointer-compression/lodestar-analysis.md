# Lodestar V8 Pointer Compression — Feasibility Analysis

## 1. Memory Usage Profile

### Heap Requirements
- **Official docs:** "Lodestar beacon node requires **at least 8GB of heap space**"
- Default launch sets `--max-old-space-size=8192` via NODE_OPTIONS
- CLI warns if `heap_size_limit < 8GB` (packages/cli/src/cmds/beacon/handler.ts:46)

### What's in the heap
- **CachedBeaconState:** ~240MB serialized per state (comment in persistentCheckpointsCache.ts:724)
  - Uses BufferPool to reuse memory: "It's not sustainable to allocate ~240MB for each state every epoch"
- **Block state cache:** Up to 64 states in FIFO cache (DEFAULT_MAX_BLOCK_STATES = 64)
  - These share tree structure via persistent merkle trees (not 64 × 240MB)
- **Checkpoint state cache:** 3 epochs in memory (DEFAULT_MAX_CP_STATE_EPOCHS_IN_MEMORY = 3)
  - Persistent states spill to disk
- **Shuffling cache:** Computed per epoch, expensive to recalculate
- **Fork choice proto-array:** All blocks since finalization
- **Attestation/sync committee pools**
- **Network state:** Peer data, gossip caches

### Key question: Actual heap usage on mainnet
- 8GB is the **configured limit**, not necessarily actual usage
- Typical mainnet nodes likely use 3-6GB heap depending on validator count and cache settings
- With pointer compression, this would be 1.5-3GB → fits comfortably in 4GB cage
- **BUT**: During state transitions and epoch processing, temporary allocations spike
- The 8GB limit provides headroom for GC and spikes

### Native memory (outside V8 heap, NOT affected by 4GB limit)
- classic-level (LevelDB) — native memory for DB operations
- snappy (via @napi-rs) — native compression buffers
- blst — BLS signature verification (native)
- libp2p — networking buffers
- Node.js Buffers backed by ArrayBuffer (outside cage per article)

## 2. Native Addon Compatibility ✅

All native addons use Node-API (NAPI), not NAN:
- **@chainsafe/blst@2.2.0:** napi-rs based (confirmed in package.json build scripts)
- **snappy@7.2.2:** @napi-rs/snappy (NAPI prebuilds)
- **classic-level@1.4.1:** NAPI prebuilds (node.napi.glibc.node)
- **No NAN dependencies found** (`npm ls nan` would be clean)

## 3. Worker Thread Usage

Lodestar spawns 4 worker threads:
1. **BLS verification pool** (chain/bls/multithread/) — CPU-intensive signature verification
2. **Network core worker** (network/core/networkCoreWorkerHandler.ts) — libp2p networking
3. **Discv5 worker** (network/discv5/) — peer discovery
4. **Historical state regen worker** (chain/archiveStore/) — state reconstruction

With IsolateGroups, each worker gets its own 4GB cage (not shared with main thread).
Worker heaps are typically small (<500MB each) — well within 4GB.

## 4. Node.js Version Compatibility

- **Current engines:** `"node": "^24.13.0"` (package.json)
- **Pointer compression requires:** Node.js 25 with compile-time flag
- Node 25 is current (non-LTS). Node 24 is LTS.
- **Gap:** Would need to either:
  a. Bump engines to support Node 25 (may have breaking changes)
  b. Wait for pointer compression to land in a future LTS
  c. Test as an experimental/optional Docker image variant

## 5. GC Sensitivity — High Value

Lodestar has tight timing deadlines:
- **Attestation due:** 33% of slot (4 seconds into 12-second slot)
- **Aggregate due:** 67% of slot (8 seconds)
- **Gloas timing tighter:** 25% / 50% / 75% thresholds
- **Block processing:** Must complete within slot time

GC pauses during attestation production = missed attestations = penalties.
**Pointer compression benefits:**
- Smaller heap → less GC work → shorter pauses
- Fewer major GC events → less stop-the-world impact
- Could meaningfully reduce missed attestation rate

## 6. Risk Assessment

### 4GB Heap Limit — MEDIUM RISK
- Lodestar recommends 8GB heap, but actual usage is typically 3-6GB
- With 50% compression, 6GB → 3GB (fits), 8GB → 4GB (tight at limit)
- Heavy operations (state regen, epoch processing) may spike temporarily
- **Mitigation:** Monitor actual heap usage during testing
- **Note:** ArrayBuffer backing stores and native allocations are OUTSIDE the cage

### Node 25 Stability — LOW-MEDIUM RISK
- Node 25 is the current release, not LTS
- Lodestar targets Node 24 LTS
- Could test without committing to production use

### Performance Overhead — LOW RISK
- 2-4% avg latency increase per article benchmarks
- For beacon nodes, most time is I/O (networking, DB) not pointer chasing
- GC improvement likely outweighs the decompression overhead

## 7. Recommendation

**PROCEED with testing.** The risk-reward is favorable:
- 50% heap reduction would be transformative for home stakers (8GB → 4GB RAM requirement)
- GC improvements could reduce missed attestations
- All native deps are compatible
- 4GB limit is tight but likely sufficient for most configurations

### Testing Plan
1. Pull `platformatic/node-caged:25-slim` Docker image
2. Build Lodestar against Node 25 (may need minor compat fixes)
3. Run beacon node with checkpoint sync + engineMock
4. Compare: RSS, heap usage, GC pauses, attestation timing
5. If stable: push to branch on lodekeeper/lodestar
