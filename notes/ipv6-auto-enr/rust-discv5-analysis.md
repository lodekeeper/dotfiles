# Rust sigp/discv5 IPv6 Auto-Discovery Analysis

## How Lighthouse discovers IPv6 in dual-stack mode

The Rust discv5 has **4 mechanisms** working together that our JS implementation lacks:

### 1. Separate vote pools (already in PR #334)
- `ipv4_votes: HashMap<NodeId, (SocketAddrV4, Instant)>`
- `ipv6_votes: HashMap<NodeId, (SocketAddrV6, Instant)>`
- `majority()` returns `(Option<SocketAddrV4>, Option<SocketAddrV6>)` — each computed independently
- IPv4 winning never clears IPv6 votes
- ✅ Our PR #334 implements this

### 2. Immediate PING on outgoing session establishment
In `connection_updated()` when a peer is newly inserted with `direction == Outgoing`:
```rust
InsertResult::Inserted => {
    self.peers_to_ping.insert(node_id);
    // PING immediately if the direction is outgoing
    if direction == ConnectionDirection::Outgoing {
        self.send_ping(enr, None);
    }
}
```
This means PONGs (and therefore votes) arrive within seconds of connecting, not after the 5-minute `ping_interval`.

In our JS discv5, pings only happen on the `setInterval(pingInterval)` timer (300s default). No immediate ping on connect. This is why our test took 5+ min to get the first votes.

### 3. `require_more_ip_votes()` — bootstrap from ANY peer
```rust
fn require_more_ip_votes(&mut self, is_ipv6: bool) -> bool {
    // ONLY applies in DualStack mode
    if !matches!(self.ip_mode, IpMode::DualStack) { return false; }
    
    match (ip_votes.has_minimum_threshold(), is_ipv6) {
        // Have enough IPv4 but NOT enough IPv6 → accept IPv6 from ANY peer
        ((true, false), true) => true,
        // Not enough of either → accept from ANY peer
        ((false, false), _) => true,
        // Both satisfied → stop
        _ => false,
    }
}
```

This is used in `handle_ip_vote_from_pong()`:
```rust
// Accept vote if peer is connected+outgoing OR if we need more votes
if !(is_connected_and_outgoing | self.require_more_ip_votes(socket.is_ipv6())) {
    return;
}
```

**Key effect:** Normally, only connected+outgoing peers' votes count (to prevent malicious inbound nodes from spoofing our IP). But when we're below the vote threshold for a given family (e.g., IPv6), we accept votes from ALL peers (including inbound). This dramatically increases the pool of IPv6 voters.

### 4. Ping on routing table insertion failure (for IPv6 vote gathering)
```rust
InsertResult::Failed(reason) => {
    // "On large networks with limited IPv6 nodes, it is hard to get enough
    //  PONG votes in order to estimate our external IP address."
    if direction == ConnectionDirection::Outgoing
        && self.require_more_ip_votes(enr.udp6_socket().is_some())
    {
        self.send_ping(enr, None);
    }
}
```

Even when the routing table is FULL and can't accept a new peer, if we need more IPv6 votes and the peer has `udp6`, we still ping them just to get the vote. The peer doesn't need to be in our kbuckets.

### 5. Vote time-based expiry (not threshold-based clearing)
Votes expire after `vote_duration` (default 30 min). They are NEVER cleared by a winning vote.
In our JS version, `AddrVotes.addVote()` calls `this.clear()` when a vote wins, wiping ALL accumulated votes. This is the original bug that PR #334 fixes.

### 6. 30% clear majority requirement
```rust
const CLEAR_MAJORITY_PERCENTAGE: f64 = 0.3;
```
A candidate must win by at least 30% over the second-highest to be accepted. This prevents flapping between competing addresses (e.g., NAT round-robin ports).

### 7. ConnectivityState — per-family NAT checking
After updating ENR with a new address:
1. Sets a timer waiting for inbound connections
2. If 2+ inbound connections arrive → "We are contactable" → keep advertising
3. If timer expires with no inbound → "Not contactable" → remove address from ENR
4. Wait 6 hours before trying again

This prevents advertising an address we can't actually receive traffic on.

## What we need to implement (priority order)

### Must-have for the current PR #334:
1. ✅ Separate vote pools (done)
2. **Immediate PING on outgoing session establishment** — without this, votes take 5+ min

### Should-have (follow-up PR):
3. **`require_more_ip_votes()` bootstrap** — accept votes from ANY peer when below threshold
4. **Ping on routing table insertion failure** for IPv6 vote gathering

### Nice-to-have (future):
5. 30% clear majority requirement
6. Vote time-based expiry instead of threshold-based clearing
7. ConnectivityState (per-family NAT validation)

## Test results confirming the analysis

IPv6-only test on mainnet:
- 8 unique IPv6 voters (from 5 IPv6 bootnodes + FINDNODE discoveries)
- Votes only arrived after 5-minute `pingInterval` (no immediate ping)
- Threshold is 10, stuck at 8 unique voters
- If we add immediate ping on connect + `require_more_ip_votes`, the node would:
  1. Immediately ping IPv6-capable peers on connect → get votes in seconds
  2. Accept votes from inbound peers too → more IPv6 voters
  3. Ping peers even when routing table is full → more IPv6 voters
