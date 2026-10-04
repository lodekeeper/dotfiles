# Grafana Dashboards Reference

**Base URL:** `https://grafana-lodestar.chainsafe.io`

## Primary Release Dashboards

These dashboards are the most important for release evaluation, listed in priority order.

### Lodestar (Summary)
- **UID:** `lodestar_summary`
- **URL:** `/d/lodestar_summary`
- **Use for:** Quick overview of node health — sync status, peer count, finalization
- **Key panels:** Slot chart, peer count, finalized epoch, Sync status, head drift (clock − head slot),
  Reorgs, Import head late (> 4 sec) rate, Uptime since

### Lodestar - VM + host
- **UID:** `lodestar_vm_host`
- **URL:** `/d/lodestar_vm_host`
- **Use for:** Memory, CPU, GC, disk — the resource regression dashboard
- **Key panels:**
  - Heap used + external memory (memory leak detection)
  - Process RSS (overall memory footprint)
  - Process heap bytes
  - CPU usage
  - GC pause time / rate
  - Event loop lag (p50, p99)
  - Disk usage percentage

### Lodestar - validator monitor
- **UID:** `lodestar_validator_monitor`
- **URL:** `/d/lodestar_validator_monitor`
- **Use for:** Attestation quality — the primary "is the node performing well" dashboard
- **Key panels:**
  - Prev epoch miss ratio (attester, target, head)
  - Wrong head ratio
  - Inclusion distance
  - Correct head percentage

### Lodestar - block processor
- **UID:** `lodestar_block_processor`
- **URL:** `/d/lodestar_block_processor`
- **Use for:** Block processing performance, epoch transitions, import pipeline — where time is spent
- **Key panels:**
  - Process block avg time, Epoch transition avg time
  - Process block / Epoch transition utilization rate
  - process block / slot, Epoch transitions / epoch, Epoch transition by reason
  - Gossip Block row: block recv / process / state transition / import delays (heatmap + avg)
  - Block processor queue (length, job time, dropped jobs %)

### Lodestar - BeaconChain
- **UID:** `lodestar_beacon_chain`
- **URL:** `/d/lodestar_beacon_chain`
- **Use for:** Finalized-checkpoint/archive tasks and chain caches (no block-processing panels anymore)
- **Key panels:**
  - Process Finalized Checkpoint: duration by tasks (archive blocks etc.)
  - Seen Cache (Block Input, attestation data), Shuffling Cache, BufferPool
  - Unfinalized Block Writes Queue (length, job time)

## Secondary Dashboards

### Lodestar - networking
- **UID:** `lodestar_networking`
- **URL:** `/d/lodestar_networking`
- **Use for:** Gossip queue health, peer connections
- **Key panels:**
  - Gossip validation queue: job time, wait time, dropped jobs
  - Gossip Block Received Delay (also time till processed / become head, from slot start)
  - Req/resp success/error rates
  - Connect/disconnect events

### Lodestar - debug gossipsub
- **UID:** `lodestar_debug_gossipsub`
- **URL:** `/d/lodestar_debug_gossipsub`
- **Use for:** Mesh quality, peer scoring
- **Key panels:**
  - Peer count per gossip score threshold
  - Attnet count with >0 mesh peers
  - Mesh peers per topic
  - Gossip RPCs transmitted / sec

### Lodestar - PeerDAS
- **UID:** `lodestar_peerdas`
- **URL:** `/d/lodestar_peerdas`
- **Use for:** Data availability sampling metrics (post-Fulu)
- **Key panels:**
  - Custody group count
  - Missing custody columns
  - Reconstructed columns
  - Receiving delay (avg / heatmap)

### Lodestar - state cache + regen
- **UID:** `lodestar_state_cache_regen`
- **URL:** `/d/lodestar_state_cache_regen`
- **Use for:** State management performance
- **Key panels:**
  - Cache hit/miss rates
  - Regen time
  - Checkpoint state operations

### Lodestar - libp2p
- **UID:** `lodestar_libp2p`
- **URL:** `/d/lodestar_libp2p`
- **Use for:** Low-level networking
- **Key panels:**
  - Transport bytes in/out
  - Connection counts by transport
  - Stream metrics

### Nodes overview (Group comparison)
- **UID:** `lodestar_multinode`
- **URL:** `/d/lodestar_multinode`
- **Use for:** Side-by-side comparison across all nodes in a group

### Nodes overview $GROUP_BY
- **UID:** `lodestar_multinode_groupby`
- **URL:** `/d/lodestar_multinode_groupby`
- **Use for:** Comparing metrics grouped by label (e.g., by group)

## URL Parameters for Comparison

To compare RC vs stable in Grafana dashboards, use filter variables:

```
?var-Filters=group|=|beta    → show beta group
?var-Filters=group|=|stable  → show stable group
?var-Filters=instance|=~|beta-super|stable-super  → specific instances
&from=now-3d&to=now          → last 3 days
&var-rate_interval=6h        → smooth rate interval
```

## Dashboard Review Workflow

1. **Start with Summary** (`lodestar_summary`) — quick health check
2. **VM + host** (`lodestar_vm_host`) — resource regression scan
3. **Validator monitor** (`lodestar_validator_monitor`) — performance quality
4. **Block processor** (`lodestar_block_processor`) — block processing, epoch transitions
5. **Networking** (`lodestar_networking`) — gossip/peer health
6. **PeerDAS** (`lodestar_peerdas`) — if PeerDAS is active
7. **BeaconChain** (`lodestar_beacon_chain`) — archive/caches deep dive if issues found
