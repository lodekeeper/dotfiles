---
name: beacon-node
description: Query and analyze Ethereum beacon nodes via the Beacon API. Health checks, chain analysis, validator info, peer diagnostics, and fork monitoring.
version: 1.0.0
author: lodekeeper
tags: [ethereum, beacon, consensus, monitoring, lodestar]
related_skills: [grafana-loki, release-metrics, local-mainnet-debug]
---

# Beacon Node Interaction Skill

Query Ethereum consensus layer beacon nodes using the [Beacon API](https://ethereum.github.io/beacon-APIs/) spec. Supports health checks, chain analysis, validator lookup, peer diagnostics, and fork monitoring.

## Quick Reference

**Spec repo:** `~/beacon-APIs` (ethereum/beacon-APIs)  

Set your base URL before running commands:
```bash
BASE="http://localhost:5052"  # or any beacon node URL
```

All endpoints use `curl -s $BASE/<path>` and return JSON.

## Node Health & Status

### Basic health check
```bash
# Version
curl -s "$BASE/eth/v1/node/version" | jq '.data.version'

# Sync status (is_syncing, head_slot, sync_distance)
curl -s "$BASE/eth/v1/node/syncing" | jq '.data'

# Health (returns 200=ok, 206=syncing, 503=not initialized)
curl -s -o /dev/null -w "%{http_code}" "$BASE/eth/v1/node/health"

# Peer count
curl -s "$BASE/eth/v1/node/peer_count" | jq '.data'
```

### Full node identity
```bash
# Peer ID, ENR, p2p addresses, metadata (attnets, syncnets, custody_group_count)
curl -s "$BASE/eth/v1/node/identity" | jq '.data'
```

### Comprehensive health check (one-liner)
```bash
echo "=== $(curl -s $BASE/eth/v1/node/version | jq -r '.data.version') ===" && \
curl -s "$BASE/eth/v1/node/syncing" | jq '{syncing: .data.is_syncing, head: .data.head_slot, distance: .data.sync_distance, el_offline: .data.el_offline}' && \
curl -s "$BASE/eth/v1/node/peer_count" | jq '{peers: .data.connected}'
```

## Chain Analysis

### Current head and finality
```bash
# Head header (slot, proposer, parent root, state root)
curl -s "$BASE/eth/v1/beacon/headers/head" | jq '.data.header.message'

# Finality checkpoints (previous_justified, current_justified, finalized)
curl -s "$BASE/eth/v1/beacon/states/head/finality_checkpoints" | jq '.data'

# Genesis info (time, validators_root, fork_version)
curl -s "$BASE/eth/v1/beacon/genesis" | jq '.data'
```

### Block analysis
```bash
# Get block by slot or root (use "head", "finalized", slot number, or 0x-prefixed root)
curl -s "$BASE/eth/v2/beacon/blocks/head" | jq '.data.message | {slot, proposer_index, body_root: .body}'

# Block attestations
curl -s "$BASE/eth/v2/beacon/blocks/head/attestations" | jq '.data | length'

# Block root
curl -s "$BASE/eth/v1/beacon/blocks/head/root" | jq '.data.root'

# Block rewards
curl -s "$BASE/eth/v1/beacon/rewards/blocks/head" | jq '.data'
```

### Slot/epoch helpers
```bash
# Current slot from head
HEAD_SLOT=$(curl -s "$BASE/eth/v1/node/syncing" | jq -r '.data.head_slot')
echo "Head slot: $HEAD_SLOT"
echo "Head epoch: $((HEAD_SLOT / 32))"

# Slots per epoch = 32, seconds per slot = 12
# Time since genesis: slot * 12 seconds
```

### Fork schedule
```bash
# All fork versions and activation epochs
curl -s "$BASE/eth/v1/config/fork_schedule" | jq '.data[] | {version: .current_version, epoch}'

# Current fork at head
curl -s "$BASE/eth/v1/beacon/states/head/fork" | jq '.data'
```

### Chain config / spec
```bash
# Full spec constants (SLOTS_PER_EPOCH, SECONDS_PER_SLOT, etc.)
curl -s "$BASE/eth/v1/config/spec" | jq '.data | {SLOTS_PER_EPOCH, SECONDS_PER_SLOT, MAX_VALIDATORS_PER_COMMITTEE, TARGET_COMMITTEE_SIZE}'

# All spec values (big output)
curl -s "$BASE/eth/v1/config/spec" | jq '.data'
```

## Validator Queries

### Lookup specific validator
```bash
# By index
curl -s "$BASE/eth/v1/beacon/states/head/validators/0" | jq '.data | {index, status: .status, balance, validator: {pubkey: .validator.pubkey, effective_balance: .validator.effective_balance, slashed: .validator.slashed, activation_epoch: .validator.activation_epoch, exit_epoch: .validator.exit_epoch}}'

# By pubkey
curl -s "$BASE/eth/v1/beacon/states/head/validators/0x9334a16a781aa4c0b04e498d3e41e8ba860bbad10f96efc8d691dad9dab42e38e3ce5e6aa75c3e0e49796ad1a2e2e60b7" | jq '.data'
```

### Validator balances
```bash
# Specific validators
curl -s -X POST "$BASE/eth/v1/beacon/states/head/validator_balances" \
  -H "Content-Type: application/json" \
  -d '{"id": ["0", "1", "2"]}' | jq '.data'

# All validators (WARNING: large response on mainnet ~1M validators)
# curl -s "$BASE/eth/v1/beacon/states/head/validator_balances" | jq '.data | length'
```

### Validator duties
```bash
EPOCH=$(($(curl -s "$BASE/eth/v1/node/syncing" | jq -r '.data.head_slot') / 32))

# Proposer duties for current epoch
curl -s "$BASE/eth/v1/validator/duties/proposer/$EPOCH" | jq '.data[] | {slot, validator_index}'

# Attester duties (POST with validator indices)
curl -s -X POST "$BASE/eth/v1/validator/duties/attester/$EPOCH" \
  -H "Content-Type: application/json" \
  -d '["0", "1", "2"]' | jq '.data[] | {validator_index, slot, committee_index}'
```

### Validator liveness
```bash
# Check if validators attested in an epoch
curl -s -X POST "$BASE/eth/v1/validator/liveness/$((EPOCH - 1))" \
  -H "Content-Type: application/json" \
  -d '["0", "1", "2"]' | jq '.data'
```

## Peer Diagnostics

### List peers with details
```bash
# All connected peers
curl -s "$BASE/eth/v1/node/peers?state=connected" | jq '.data | length'

# Peer details (agent, direction, state)
curl -s "$BASE/eth/v1/node/peers?state=connected" | jq '.data[:5] | .[] | {peer_id: .peer_id[:20], agent: .agent, direction, state}'

# Count by direction
curl -s "$BASE/eth/v1/node/peers?state=connected" | jq '[.data[].direction] | group_by(.) | map({direction: .[0], count: length})'
```

### Specific peer
```bash
curl -s "$BASE/eth/v1/node/peers/<peer_id>" | jq '.data'
```

## Rewards Analysis

### Attestation rewards for an epoch
```bash
# All validators (returns total, head, source, target, inclusion_delay, inactivity rewards)
curl -s -X POST "$BASE/eth/v1/beacon/rewards/attestations/$EPOCH" \
  -H "Content-Type: application/json" \
  -d '["0", "1", "2"]' | jq '.data'
```

### Sync committee rewards
```bash
curl -s "$BASE/eth/v1/beacon/rewards/sync_committee/head" | jq '.data[:5]'
```

## Pool / Mempool

### View pending operations
```bash
# Pending attestations
curl -s "$BASE/eth/v2/beacon/pool/attestations" | jq '.data | length'

# Voluntary exits
curl -s "$BASE/eth/v1/beacon/pool/voluntary_exits" | jq '.data | length'

# Proposer slashings
curl -s "$BASE/eth/v1/beacon/pool/proposer_slashings" | jq '.data | length'

# Attester slashings
curl -s "$BASE/eth/v2/beacon/pool/attester_slashings" | jq '.data | length'

# BLS to execution changes
curl -s "$BASE/eth/v1/beacon/pool/bls_to_execution_changes" | jq '.data | length'
```

## Event Stream (SSE)

### Subscribe to real-time events
```bash
# Head updates
curl -s -N "$BASE/eth/v1/events?topics=head" | head -20

# Multiple topics
curl -s -N "$BASE/eth/v1/events?topics=head,block,attestation,finalized_checkpoint" | head -50

# Available topics: head, block, attestation, voluntary_exit, bls_to_execution_change,
# proposer_slashing, attester_slashing, finalized_checkpoint, chain_reorg,
# contribution_and_proof, light_client_finality_update, light_client_optimistic_update,
# payload_attributes, blob_sidecar
```

**Note:** SSE streams are long-lived. Use `timeout` or `head` to limit output:
```bash
timeout 30 curl -s -N "$BASE/eth/v1/events?topics=head" | while read -r line; do
  echo "$line"
done
```

## Debug Endpoints

### Fork choice dump
```bash
# Full fork choice tree (WARNING: can be very large)
curl -s "$BASE/eth/v1/debug/fork_choice" | jq '{justified_checkpoint, finalized_checkpoint, fork_choice_nodes: (.fork_choice_nodes | length)}'

# Fork choice heads
curl -s "$BASE/eth/v2/debug/beacon/heads" | jq '.data'
```

## Common Patterns

### Is the node healthy and synced?
```bash
health_check() {
  local BASE=$1
  local status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/eth/v1/node/health")
  local sync=$(curl -s "$BASE/eth/v1/node/syncing" | jq -r '.data.is_syncing')
  local distance=$(curl -s "$BASE/eth/v1/node/syncing" | jq -r '.data.sync_distance')
  local peers=$(curl -s "$BASE/eth/v1/node/peer_count" | jq -r '.data.connected')
  local version=$(curl -s "$BASE/eth/v1/node/version" | jq -r '.data.version')
  
  echo "Version:  $version"
  echo "Health:   $status (200=ok, 206=syncing, 503=error)"
  echo "Syncing:  $sync (distance: $distance)"
  echo "Peers:    $peers"
  
  if [ "$status" = "200" ] && [ "$sync" = "false" ] && [ "$peers" -gt 10 ]; then
    echo "Status:   ✅ HEALTHY"
  else
    echo "Status:   ⚠️ NEEDS ATTENTION"
  fi
}

health_check "$BASE"
```

### Compare two nodes
```bash
compare_nodes() {
  local A=$1 B=$2
  echo "=== Node A: $(curl -s $A/eth/v1/node/version | jq -r '.data.version') ==="
  echo "Head: $(curl -s $A/eth/v1/node/syncing | jq -r '.data.head_slot')"
  echo "Peers: $(curl -s $A/eth/v1/node/peer_count | jq -r '.data.connected')"
  echo ""
  echo "=== Node B: $(curl -s $B/eth/v1/node/version | jq -r '.data.version') ==="
  echo "Head: $(curl -s $B/eth/v1/node/syncing | jq -r '.data.head_slot')"
  echo "Peers: $(curl -s $B/eth/v1/node/peer_count | jq -r '.data.connected')"
}
```

### Monitor finality
```bash
check_finality() {
  local BASE=$1
  local data=$(curl -s "$BASE/eth/v1/beacon/states/head/finality_checkpoints")
  local head=$(curl -s "$BASE/eth/v1/node/syncing" | jq -r '.data.head_slot')
  local head_epoch=$((head / 32))
  local finalized=$(echo "$data" | jq -r '.data.finalized.epoch')
  local justified=$(echo "$data" | jq -r '.data.current_justified.epoch')
  local finality_distance=$((head_epoch - finalized))
  
  echo "Head epoch:      $head_epoch"
  echo "Justified epoch: $justified"
  echo "Finalized epoch: $finalized"
  echo "Finality distance: $finality_distance epochs"
  
  if [ "$finality_distance" -gt 3 ]; then
    echo "⚠️ FINALITY LAG: $finality_distance epochs behind!"
  else
    echo "✅ Finality healthy"
  fi
}
```

### Track missed slots (proposer analysis)
```bash
check_missed_slots() {
  local BASE=$1
  local EPOCH=$2
  local start_slot=$((EPOCH * 32))
  local end_slot=$((start_slot + 32))
  local missed=0
  
  for slot in $(seq $start_slot $((end_slot - 1))); do
    local status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/eth/v2/beacon/blocks/$slot")
    if [ "$status" = "404" ]; then
      missed=$((missed + 1))
      echo "Missed slot: $slot"
    fi
  done
  echo "Missed $missed/32 slots in epoch $EPOCH"
}
```

## Lodestar-Specific Endpoints

Lodestar exposes additional non-standard endpoints:

```bash
# Lodestar version details
curl -s "$BASE/eth/v1/lodestar/version" | jq '.data'

# Validator participation for an epoch
curl -s "$BASE/eth/v1/lodestar/validator/participation/$EPOCH" | jq '.data'
```

## Tips

- **state_id values:** `head`, `finalized`, `justified`, `genesis`, slot number, or `0x`-prefixed state root
- **block_id values:** `head`, `finalized`, `genesis`, slot number, or `0x`-prefixed block root
- **Large responses:** Validator queries on mainnet can return huge payloads (~1M validators). Use POST with specific indices when possible.
- **Rate limiting:** Public nodes may rate-limit. Space requests or use your own node.
- **SSE events:** Long-lived connections. Always use `timeout` or pipe through `head`.
- **Execution optimistic:** Response field `execution_optimistic: true` means the CL hasn't verified the EL payload yet. Data may change.
- **Spec reference:** Full OpenAPI spec at `~/beacon-APIs/beacon-node-oapi.yaml`
- **Validator flow:** `~/beacon-APIs/validator-flow.md` — how VC and BN interact
