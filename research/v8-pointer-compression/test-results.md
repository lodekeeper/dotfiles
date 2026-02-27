# V8 Pointer Compression — Lodestar Test Results

## Setup
- **Image:** lodestar-ptr-compress:test (based on platformatic/node-caged:25-slim)
- **Lodestar:** v1.40.0 (unstable branch)
- **Node:** v25.6.1, V8 14.1.146.11-node.19
- **Pointer compression:** ENABLED (4GB cage confirmed)
- **Network:** Mainnet
- **Sync:** Checkpoint sync from beaconstate-mainnet.chainsafe.io
- **Execution:** engineMock
- **Host:** server2 (62.45GB RAM)

## Timeline

### T+0 (16:40:22) — Start
- Checkpoint state download: 305.92 MB, slot 13774912
- Heap limit warning: "Node.js heap size limit is too low at 4.00 GB"

### T+20s (16:40:48) — State initialized
- Checkpoint state loaded and initialized
- RSS: ~3.1GB during deserialization

### T+1m30s (16:41:52) — Peak initialization
- RSS: 3.975GB (peak during shuffling computation)
- CPU: 101%

### T+2m (16:42:17) — Synced to head
- Slot: 13775009, peers: 35
- RSS: 5.18GB (steady state)
- CPU: 27%
- Finalization working normally

## Memory Comparison (from Grafana production data)
| Metric | Production (Node 24, no compression) | Pointer Compression (Node 25) |
|--------|--------------------------------------|-------------------------------|
| RSS at steady state | 10.9–26.9 GB (production nodes) | 5.18 GB (test, engineMock) |
| V8 heap used | 3.8–6.2 GB (production nodes) | ~1.9–3.1 GB (estimated 50% of production) |
| Heap limit | 8192 MB | 4096 MB |
| Peer count | varies | 35-41 |

### Production heap breakdown (Grafana, live mainnet nodes)
- feat4-sas: 6.18 GB heap
- feat4-super: 5.41 GB heap  
- Lido prod nodes: 3.8–4.0 GB heap (typical)
- Public mainnet: 3.8–3.9 GB heap

**With 50% pointer compression, production heap would be 1.9–3.1 GB → fits in 4GB cage.**

## Observations
1. ✅ Node synced successfully with checkpoint sync
2. ✅ Peers connected normally (35-41)
3. ✅ Finalization working
4. ✅ engineMock producing valid blocks
5. ⚠️ Expected heap warning (4GB < 8GB recommendation)
6. 🔍 Need longer run to verify stability and GC behavior
