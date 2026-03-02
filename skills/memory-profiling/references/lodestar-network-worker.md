# Lodestar network-worker profiling notes

## Start node for profiling

```bash
node --expose-gc packages/cli/bin/lodestar.js beacon \
  --network mainnet \
  --checkpointSyncUrl https://beaconstate-mainnet.chainsafe.io \
  --forceCheckpointSync \
  --execution.engineMock true \
  --rest true --rest.port 19597 --rest.namespace all \
  --metrics true --metrics.port 18008 \
  --port 19771 \
  --dataDir ./beacon-data
```

## Useful metrics

```bash
curl -s http://127.0.0.1:18008/metrics | grep -E \
  "network_worker_nodejs_heap_size_used_bytes|network_worker_process_resident_memory_bytes|libp2p_peers|gossipsub_cache_size"
```

## Snapshot cadence

- T0 after sync stabilizes
- T1 after 10-15 min
- T2 after 25-30 min (if leak is slow)

## Common leak signatures

- `MplexStream`, `InboundStream`, `OutboundStream` keep growing
- `Listener` chains grow (`next` / `previous` linked list)
- `Timeout` and `AbortSignal` counts rise with churn
- `gossipsub_cache_size{cache="streamsInbound|streamsOutbound"}` diverges from `libp2p_peers`
