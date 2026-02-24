# Feature: EPBS devnet peer-status bootstrap fix (LH+LS 2-node)

## Problem
In Nico's 2-node EPBS devnet config (LH + LS, minimal preset, Gloas epoch 1), Lodestar receives and validates gossip blocks immediately, but reports `is_syncing=true` for ~5 minutes after startup.

Observed behavior:
- LS receives gossip blocks and imports envelopes from LH starting around slot 1.
- VC requests (`getAttesterDuties`, `getProposerDuties`, `publishContributionAndProofs`) return 503 while LS is marked syncing.
- Attestations are missed for early epochs; chain justification/finalization is delayed.
- `onPeerConnected` event in LS is emitted only after first STATUS request/response at ~5 min (`STATUS_INTERVAL_MS` cadence), not when gossip is already flowing.

Root-cause hypothesis:
- `SyncState` uses `network.getConnectedPeerCount()`.
- `Network.getConnectedPeerCount()` currently reads `connectedPeersSyncMeta.size`, which is only populated on `NetworkEvent.peerConnected`.
- `NetworkEvent.peerConnected` is emitted from `PeerManager.onStatus()` (after STATUS exchange), not directly on libp2p connection establishment.
- For pre-existing/already-connected peers at startup, STATUS can be delayed, so connected peer count appears as 0 despite an active libp2p connection.

## Approach
Bootstrap peer sync metadata for already-open libp2p connections during PeerManager startup so STATUS is requested immediately and `peerConnected` is emitted promptly.

Candidate fix:
1. On PeerManager init, after registering listeners, scan existing open libp2p connections.
2. For each peer not present in `connectedPeers` map, seed `PeerData` similarly to `onLibp2pPeerConnect`.
3. For seeded outbound peers, immediately request `ping` + `status`.
4. Keep existing event flow intact (relevance checks still happen in `onStatus`).
5. Add defensive logging/metrics for seeded peers to make startup races visible.

Alternative considered:
- Change sync-state peer check to use raw libp2p connection count instead of sync metadata count.
  - Pros: simpler immediate effect.
  - Cons: bypasses relevance gating and could treat irrelevant/unhealthy peers as sufficient for synced state.

Preferred: startup seeding in PeerManager to preserve existing relevance model.

## Implementation Details
Likely files:
- `packages/beacon-node/src/network/peers/peerManager.ts`
  - Add helper to hydrate `connectedPeers` from existing libp2p open connections.
  - Call helper during constructor startup path.
  - Reuse current initialization logic from `onLibp2pPeerConnect` for consistency.
- (Optional) small utility extraction to avoid duplicating `PeerData` construction.

## Edge Cases & Security
- Duplicate connect events (inbound + outbound) are already possible; seeding must avoid double-registration.
- Seeded peers may disconnect immediately; request methods already catch errors.
- Ensure secp256k1 peer type checks still apply.
- Preserve relevance filtering in `onStatus` before emitting sync-level connected events.

## Test Plan
Unit/integration (targeted):
- PeerManager with pre-open connection before startup listeners:
  - Assert STATUS is requested promptly.
  - Assert `NetworkEvent.peerConnected` occurs without waiting full status interval.
- No regressions for normal new outbound/inbound connections.

Devnet validation (Nico acceptance):
- 2-node LH+LS with local LS image (this environment)
- Verify from genesis onward:
  - No extended `is_syncing=true` period on LS once head is within tolerance.
  - VC duty endpoints do not return startup 503 sync errors beyond transient startup window.
  - No missed attestations attributable to startup sync misclassification.
  - Blocks continue to flow, no peering dropouts, chain finalizes.

## Acceptance Criteria
- [ ] LS no longer waits ~5 minutes for first STATUS before counting connected peer for sync-state gating.
- [ ] LS transitions to synced promptly when head is within tolerance and peer is connected.
- [ ] VC duty APIs avoid prolonged 503 "Node is syncing" due to peer-status bootstrap lag.
- [ ] 2-node devnet passes: stable peering, no missed attestations, block production healthy, finalization advances.
