# Gloas builder circuit breaker for Lodestar (Prysm model)

Status: draft for discussion, 2026-10-20
Author: lodekeeper, for Nico

## TL;DR

- Prysm replaced "count missed slots" with **per-builder accountability**. A builder that wins a bid, gets a well-attested block (more than 60% of the slot committee weight, the same quorum at which the spec makes it pay anyway) and then does not reveal its payload is **blacklisted locally**. Its bids are not propagated on gossip, not requested and not selected.
- A **relay (direct-connection endpoint) is banned with its builder.** Prysm learns which builder indices each builder-API URL serves from verified bids. When one of them fails, every endpoint that served it is banned and stops being contacted. Every other index behind those endpoints is collaterally blacklisted.
- **Systemic fallback.** Once 7 or more builders are directly blacklisted at the same time, the node stops taking foreign bids and self-builds.
- For Lodestar I propose a `BuilderBlacklist` component that sits next to the existing aggregate EMPTY-rate breaker from #9598 and does not replace it. It needs two small fork-choice additions: `builderIndex` on `ProtoBlock` and a same-slot attestation score accessor. Hooks go in `importBlock` (charge), `importExecutionPayload` (clear), bid gossip validation, `publishExecutionPayloadBid`, `BuilderApiClient` and `produceBlockV4`.
- Three to four PRs. Most of the logic is a pure state machine that we can port almost 1:1, including Prysm's test cases. Being single-threaded removes all of Prysm's lock juggling (their #17714 race does not exist for us).
- I found a few things to decide or improve on, see "Deviations" and "Open questions". The biggest: Prysm's first-offense "1 epoch" ban is really "until the end of the current epoch", which can be zero slots.

## Sources

- potuz, "Gloas circuit breaker" (2026-07-28): https://www.potuz.net/posts/gloas-circuit-breaker/
- Prysm (all by potuz, all merged):
  - #17294 single builder tracking: https://github.com/OffchainLabs/prysm/pull/17294
  - #17419 hidden `--submit-blacklisted-builder-bids` test flag: https://github.com/OffchainLabs/prysm/pull/17419
  - #17540 relay circuit breaker, flags and metrics: https://github.com/OffchainLabs/prysm/pull/17540
  - #17714 relay-link race fix in `DropInactiveBuilders`: https://github.com/OffchainLabs/prysm/pull/17714
- Related open Prysm PRs that do not touch the breaker state machine:
  - #17723 multiple bid requests per proposal (their version of our #10425): https://github.com/OffchainLabs/prysm/pull/17723
  - #17080 builder-API fallback when the local payload is unavailable: https://github.com/OffchainLabs/prysm/pull/17080
  - The only open PR that touches `cache/builder_circuit_breaker.go` is the glamsterdam-devnet-8 branch (#17354), a devnet merge branch, not new design.
- Code read at Prysm `develop` @ `636c6e8` (2026-10-20): `beacon-chain/cache/builder_circuit_breaker.go` (580 lines), `beacon-chain/blockchain/builder_circuit_breaker.go`, `forkchoice/doubly-linked-tree/gloas.go`, `rpc/.../proposer_bid.go`, `proposer_gloas.go`, `proposer_submit_bid.go`, `sync/validate_execution_payload_bid.go`, `node/config.go`.
- Lodestar read at `unstable` @ `708700cdf6`.

## 1. What Prysm actually implements

### 1.1 State (one in-memory object, shared by blockchain, sync and RPC services)

```go
type builderFailure struct {
    failed              uint64           // consecutive failures, reset by back-off
    blacklistUntilEpoch Epoch            // banned while queryEpoch < this
    backOffEpoch        Epoch            // failed resets to 0 once epoch >= this
}
type relayRecord struct {
    members       map[BuilderIndex]Epoch // index -> last epoch this endpoint served a verified bid from it
    bannedUntil   Epoch
    lastSeenEpoch Epoch
}
BuilderCircuitBreaker {
    failures      map[BuilderIndex]*builderFailure // only DIRECTLY charged builders
    recorded      map[[32]byte]Epoch               // parent roots already charged (dedupe)
    relays        map[string]*relayRecord          // normalized endpoint -> record
    relaysByIndex map[BuilderIndex][]string        // reverse index, kept as a mirror of members
}
```

Nothing is persisted. A restart clears everything.

### 1.2 When a builder is charged

This runs in `postBlockProcess` on **every imported Gloas block** (canonical or not, "a block that lost the head race is still valid evidence about its parent"). It runs right after fork choice recomputed the head, so the weights are fresh. The block being imported is the *child* and the *parent* is the one being judged. The builder is charged only if all of these hold:

1. No FULL node exists for the parent (we never imported its payload).
2. `parent.slot + 1 == child.slot`. Skipped slots in between are ambiguous, so no charge.
3. The parent's builder index is known and is not `BUILDER_INDEX_SELF_BUILD`.
4. `!CouldBuilderWithhold(parent)`: the parent's own node balance, which holds the same-slot votes and no proposer boost, is **> 60%** of the committee weight (`BuilderFailureWeightThreshold = 60`). This mirrors the spec's builder payment quorum (`BUILDER_PAYMENT_THRESHOLD = 6/10`): above it the builder pays regardless, so withholding is not a legitimate move.
5. The parent root has not been charged already, since several children of one empty parent count once.

Every bail-out is logged at debug, so "why was builder X not charged for slot N" can be answered after the fact. That is worth copying.

### 1.3 Ban rules (single builder)

`RecordFailure(idx, parentRoot, epoch)`, where `epoch` is the **child's** epoch:

```
if record exists and epoch >= backOffEpoch: failed = 0
failed++ ; backOffEpoch = epoch + BackOffPeriod
if failed <= AllowedFailures: not blacklisted
period = failed >= CriticalFailures ? CriticalBlacklistPeriod : BlacklistPeriod
blacklistUntilEpoch = max(blacklistUntilEpoch, epoch + period)
ban every relay serving idx until min(blacklistUntilEpoch, epoch + RelayBlacklistPeriod)
```

Prysm mainnet defaults (beacon-node config, not spec):

| param | default | meaning |
|---|---|---|
| BuilderAllowedFailures | 0 | first failure bans |
| BuilderCriticalFailures | 2 | 2nd failure inside the back-off window gets the long ban |
| BuilderBlacklistPeriod | 1 epoch | first offense (see 4.1, effectively "rest of the epoch") |
| BuilderCriticalBlacklistPeriod | 256 epochs | about 27h, potuz's "until restart" made finite |
| BuilderFailureBackOffPeriod | 5 epochs | failure counter resets after 5 epochs without a failure |
| BuilderCriticalFailedBuilders | 7 | concurrently, directly blacklisted builders before forced self-build |
| BuilderFailureWeightThreshold | 60 % | committee-weight share needed to charge |
| BuilderRelayBlacklistPeriod | 32 epochs | cap on a relay ban, never longer than the offender's own ban |
| BuilderRelayAssociationTTL | 64 epochs | an unseen endpoint to index link expires |
| BuilderMaxTrackedRelays | 64 | LRU by lastSeen, banned relays are never evicted |
| BuilderMaxIndicesPerRelay | 16 | bounds the collateral blast radius, failing members are never evicted |

### 1.4 Relay tracking

- **Learning links.** `ObserveRelayBid(url, idx, epoch)` is called for builder-API bids only, *after* the bid passed validation including signature, and only if that exact signature was not returned by more than one endpoint in the same request ("the signature proves the builder authored the bid, not that this endpoint serves it"). The goal is to stop an endpoint from claiming indices it does not serve and turning the collateral ban against them.
- **Identity.** The URL is normalized to `scheme://host[:port]/path`, lowercased, trailing `/` stripped, **credentials dropped and never stored**, at most 256 printable ASCII characters.
- **Collateral.** A banned relay blacklists all its members through `Blacklisted(idx) = directlyBlacklisted || anyServingRelayBanned`. Collateral members get **no** failure record. That keeps them out of the `SelfBuildOnly` count ("or a single endpoint serving many builders would trip the fallback on its first failure"). It also stops propagation after one hop: only a directly charged index bans endpoints.
- **Release.** A relay ban lifts early once none of its members has `failed > 0` (see 1.5), otherwise at `bannedUntil`.
- `--disable-builder-relay-circuit-breaker` turns off link learning, which disables relay bans.

### 1.5 Clearing

`RecordSuccess(envelope.builderIndex)` runs on **every** imported payload envelope:

- A builder with no relay links has its record deleted, which unbans it immediately.
- A builder with relay links has `failed = 0` and its ban cleared, but the zeroed record is kept as evidence. Then every serving relay that has no failing member left is released.

### 1.6 Upkeep (every Gloas block import)

- `Prune(epoch)` drops failure records whose ban and back-off have both elapsed, `recorded` roots older than 1 epoch, stale relay members and empty or stale relays.
- `DropInactiveBuilders(epoch, state.IsActiveBuilder)` handles **builder index reuse**. Once an index is no longer an active builder (exit sets `withdrawable_epoch`), its record and links are dropped so a newcomer on a recycled index is not punished. terencechain raised this on #17294, and #17714 fixed a lock race inside it.
- Gauges are updated at the same time.

### 1.7 Enforcement points

| where | rule |
|---|---|
| gossip `execution_payload_bid` validation | `[IGNORE]` (local policy) if the builder is blacklisted, checked before signature verification and the seen-tuple check, so the bid is not forwarded |
| `SubmitSignedExecutionPayloadBid` (a builder's own BN) | reject `builder N is blacklisted by the circuit breaker`, bypassable with the hidden test flag `--submit-blacklisted-builder-bids` (#17419) |
| builder-API request fan-out | banned endpoints are **not contacted** (`allowedBuilderEntries`) |
| builder-API responses | bids from blacklisted builders are discarded before validation, logged as `discarded: blacklisted` |
| cached p2p bid at selection | dropped if the builder got blacklisted after the bid was cached |
| proposal | `SelfBuildOnly` skips the builder-API round trip and p2p bids, so the node self-builds |
| local payload unavailable | `setRemoteBidFallback` does **not** consult the breaker for the p2p bid on purpose: "with no local payload, a risky bid beats a missed slot" |

Envelopes are never filtered. A blacklisted builder's payload must still be processed, because that is how it gets cleared.

### 1.8 Flags, validation, metrics

- Flags: `--builder-allowed-failures`, `--builder-critical-failures`, `--builder-blacklist-period`, `--builder-critical-blacklist-period`, `--builder-relay-blacklist-period`, `--builder-failure-backoff-period`, `--builder-critical-failed-builders`, `--disable-builder-relay-circuit-breaker`, and the hidden `--submit-blacklisted-builder-bids`.
- Startup validation: `blacklistPeriod > 0`, `criticalBlacklistPeriod >= blacklistPeriod`, `criticalFailures > allowedFailures` (otherwise the critical ban is unreachable), `criticalFailedBuilders > 0`, `backOffPeriod > 0`, `relayBlacklistPeriod > 0`. Any override prints a warning that too tolerant a config exposes the node.
- Metrics: `builder_payload_failures_total` (counter, incremented only when the failure blacklisted), `builder_blacklisted_count`, `builder_self_build_only`, `builder_relays_banned_count`, `builder_collateral_blacklisted_count`.

### 1.9 Article vs Prysm: what is NOT implemented (yet)

- **Trusted/untrusted tiers.** The article has a `CriticalFailedUntrustedBuilders = 3` step that first drops p2p bids and keeps trusted builders, and only falls back to self-build at 7. Prysm has only the self-build step. #17294 says "trusted vs untrusted distinction left for a follow-up".
- **Operator allow/deny lists.** #17294's description mentions `--builder-index-denylist`, but it is not on `develop`. potuz said on #17294 that the allowlist "comes in a future PR" and is meant for different treatment, not immunity.
- **Operator-supplied relay to index lists.** The article suggests community-maintained lists. Prysm only learns links from observed bids.

## 2. Lodestar today

- **Aggregate post-gloas breaker** (#9598, plus #9815, #9780, #10254, #10318): `chain/builderCircuitBreaker.ts` counts canonical FULL vs EMPTY over a random 32 to 63 slot window and activates when the EMPTY rate exceeds `allowedFaults / faultInspectionWindow` (capped at 25%). `produceBlockV4` treats `isActive` as "no builder-API requests, no p2p bid, select local". It does not attribute anything to a builder.
- **Builder API** (`execution/builder/apiClient.ts`): builder entries come from the VC on every `produceBlockV4` call (`BuilderConfig.builders`, each with `url`, `auth`, `maxExecutionPayment`, `builderBoostFactor` and so on). Clients are dialed on demand per URL. Bids are validated, including signature, in `validateBuilderApiExecutionPayloadBid`.
- **P2P bids**: `validateGossipExecutionPayloadBid` feeds `ExecutionPayloadBidPool`, which keeps only the **single best bid** per (slot, parentRoot, parentHash).
- **Fork choice**: Gloas blocks are `PENDING -> {EMPTY, FULL}` nodes with EMPTY and FULL as children of PENDING. Same-slot attestations are attributed to PENDING (`forkChoice.ts` ~L1036). `attestationScore` excludes boost but **back-propagates to parents**. `ProtoBlock` has **no `builderIndex`**.
- Single-threaded, so none of Prysm's lock ordering (forkchoice, breaker and state locks) applies.

## 3. Proposed design for Lodestar

### 3.1 New component `chain/builderBlacklist.ts`

A pure state machine, a port of Prysm's `cache/builder_circuit_breaker.go` without the locks. Every query takes an explicit epoch or slot, so it is trivial to test.

```ts
export type BuilderBlacklistOpts = {
  allowedFailures: number;         // 0
  criticalFailures: number;        // 2
  blacklistPeriod: number;         // epochs, 1 (see 4.1)
  criticalBlacklistPeriod: number; // epochs, 256
  backOffPeriod: number;           // epochs, 5
  criticalFailedBuilders: number;  // 7
  relayBlacklistPeriod: number;    // epochs, 32
  relayTracking: boolean;          // true
};

export type FailureOutcome = {blacklisted: boolean; bannedRelays: string[]; collateral: number};

export class BuilderBlacklist {
  recordFailure(builderIndex: BuilderIndex, blockRoot: RootHex, epoch: Epoch): FailureOutcome;
  recordSuccess(builderIndex: BuilderIndex, blockRoot: RootHex): void;
  observeRelayBid(url: string, builderIndex: BuilderIndex, epoch: Epoch): void; // only after signature verification
  isBlacklisted(builderIndex: BuilderIndex, epoch: Epoch): boolean;              // direct || via banned relay
  isRelayBanned(url: string, epoch: Epoch): boolean;
  isSelfBuildOnly(epoch: Epoch): boolean;                                        // direct bans only
  prune(epoch: Epoch): void;
  dropInactiveBuilders(isActive: (builderIndex: BuilderIndex) => boolean): void;
  getStatus(epoch: Epoch): BuilderBlacklistStatus;                               // for metrics and debug API
}
```

Ownership: `BuilderCircuitBreaker` (existing) owns a `BuilderBlacklist`, and `isActive(slot, head)` becomes `aggregateActive || blacklist.isSelfBuildOnly(epoch)`. `produceBlockV4` keeps its single `circuitBreakerActive` branch. Add a separate block-selection reason (for example `builder_blacklist_critical`) so Grafana shows which layer tripped.

### 3.2 Fork choice additions (`@lodestar/fork-choice`)

1. `ProtoBlock.builderIndex: BuilderIndex | null`, set in `onBlock` from `body.signedExecutionPayloadBid.message.builderIndex` (Gloas) and `null` before Gloas. Self-build is `BUILDER_INDEX_SELF_BUILD` (`Infinity` in our params). It also has to be set for the anchor block on checkpoint init.
2. A same-slot support accessor, the equivalent of Prysm's `node.balance`:

```ts
/** Attestation weight from the block's own slot, ie. votes on PENDING itself, excluding descendants and proposer boost */
getSameSlotAttestationScore(blockRoot: RootHex): bigint {
  const pending = node(blockRoot, PENDING), empty = node(blockRoot, EMPTY), full = node(blockRoot, FULL);
  return pending.attestationScore - empty.attestationScore - (full?.attestationScore ?? 0n);
}

/** Spec builder payment quorum (6/10 of the per-slot committee weight) reached in our fork-choice view */
isBuilderPaymentQuorumReached(blockRoot: RootHex): boolean {
  const committeeWeight = justifiedTotalActiveBalance / SLOTS_PER_EPOCH; // same basis as getCommitteeFraction()
  return score * BUILDER_PAYMENT_THRESHOLD_DENOMINATOR > committeeWeight * BUILDER_PAYMENT_THRESHOLD_NUMERATOR;
}
```

The subtraction is needed because our `attestationScore` back-propagates. Use the params constants rather than a separate 60, so the rule stays tied to the spec quorum.

### 3.3 Charging: `importBlock`, right after `recomputeForkChoiceHead` (step 5)

```ts
if (fork >= ForkSeq.gloas && isRecent(block.slot)) {
  const parent = this.forkChoice.getBlockHexDefaultStatus(parentRootHex);
  const reason =
    !parent || !isGloasBlock(parent) ? "pre_gloas_parent"
    : this.forkChoice.hasPayloadHexUnsafe(parent.blockRoot) ? null            // revealed, nothing to charge
    : parent.slot + 1 !== block.slot ? "skipped_slots"
    : parent.builderIndex === null ? "unknown_builder"
    : parent.builderIndex === BUILDER_INDEX_SELF_BUILD ? "self_build"
    : !this.forkChoice.isBuilderPaymentQuorumReached(parent.blockRoot) ? "below_quorum"
    : "charge";
  // debug-log every non-null, non-charge reason with slot, parentRoot and builderIndex
  if (reason === "charge") {
    const outcome = blacklist.recordFailure(parent.builderIndex, parent.blockRoot, computeEpochAtSlot(block.slot));
    if (outcome.blacklisted) warn("Builder failed to reveal payload, blacklisting it", {...});
  }
}
```

- Run it for non-canonical children too, as Prysm does.
- `isRecent`: skip during range sync or when the block is more than about 1 epoch behind the clock. Historical fork-choice weights do not reflect what we saw live, and bans computed against old epochs would be expired on arrival anyway. Prysm does not gate this, but it is free for us.
- Upkeep (`prune`, `dropInactiveBuilders` against the head state's `isActiveBuilder`, gauges) runs on the clock epoch event and in `prepareNextSlot`, not on every block. That is cheaper, and there are no locks to worry about.

### 3.4 Clearing: `importExecutionPayload`

After the envelope is imported into fork choice: `blacklist.recordSuccess(envelope.builderIndex, blockRootHex)`. See 4.2 for the late-reveal guard.

### 3.5 Enforcement

| where (Lodestar) | change |
|---|---|
| `validateGossipExecutionPayloadBid` (`chain/validation/executionPayloadBid.ts`) | `[IGNORE]` local policy if `isBlacklisted(bid.builderIndex, epochOf(bid.slot))`. It has to run before `executionPayloadBidPool.add`, otherwise a blacklisted high bid occupies the single best-bid slot and our node then IGNOREs honest lower bids under the highest-bid rule. Put it before BLS verification, since it is cheap. Only an IGNORE, so peer scores are untouched. |
| `publishExecutionPayloadBid` (`api/impl/beacon/blocks`) | 400 "builder N is blacklisted by the circuit breaker". Optionally a hidden `--builder.blacklist.publishBlacklistedBids` for devnet testing, like Prysm #17419 |
| `BuilderApiClient.getExecutionPayloadBids` | skip entries whose normalized URL `isRelayBanned` before dialing. Pass a predicate in, so the client does not depend on chain. Count them in a metric |
| `produceBlockV4` builder-API candidates | discard `isBlacklisted` bids before `validateBuilderApiExecutionPayloadBid`. After validation succeeds, `observeRelayBid(url, builderIndex, epoch)` unless the same signature came back from more than one URL. `bidsDiscarded` gets a `reason` label |
| `produceBlockV4` p2p bid read | drop the pooled bid if it became blacklisted after insertion |
| `produceBlockV4` with #10425 rounds | the same filters per round, and observe once per (url, signature) |
| envelope gossip and import | **unchanged**, never filter payloads |

### 3.6 Relay identity in Lodestar

Builder URLs come from the VC per request, so the relay key is `normalizeBuilderUrl(decodeBuilderUrl(entry.url))`: lowercase scheme and host, strip userinfo, strip the trailing `/`, keep the path, length at most 256. Logs use `toPrintableUrl`. The same bounds as Prysm apply (64 relays, 16 indices per relay, 64-epoch association TTL, 32-epoch relay ban cap).

### 3.7 Options / CLI

These are beacon-node options, not chain config, matching Prysm's split. They are hidden or advanced, since almost nobody should touch them. I am naming them under `builder.blacklist.*` so they do not get confused with the existing `builder.allowedFaults`:

```
--builder.blacklist.allowedFailures          0
--builder.blacklist.criticalFailures         2
--builder.blacklist.period                   1     (epochs)
--builder.blacklist.criticalPeriod           256   (epochs)
--builder.blacklist.backOffPeriod            5     (epochs)
--builder.blacklist.criticalBuilders         7
--builder.blacklist.relayPeriod              32    (epochs)
--builder.blacklist.relayTracking            true
```

Use the same startup validation as Prysm (1.8), plus a warning when any value is overridden.

### 3.8 Observability

- Metrics: `beacon_builder_blacklist_failures_total`, `beacon_builder_blacklist_blacklisted_count`, `beacon_builder_blacklist_collateral_count`, `beacon_builder_blacklist_relays_banned_count`, `beacon_builder_blacklist_self_build_only`, `beacon_builder_blacklist_not_charged_total{reason}` (the not-charged counter is ours), and a `reason` label on `builderApi.bidsDiscarded`. Add panels next to the #10318 circuit breaker row.
- Optional `GET /eth/v1/lodestar/builder_blacklist`: blacklisted indices with expiry and failure count, plus banned relays (masked) with members. Useful for operators and for devnet testing.

## 4. Deviations from Prysm I would propose (please weigh in)

### 4.1 Ban duration is epoch-boundary based in Prysm

The query is `blacklistUntilEpoch > queryEpoch` with `until = chargeEpoch + 1`, so a first offense bans only **for the rest of the epoch in which the child was imported**. A failure charged at the last slot of an epoch bans for about 0 slots, and one charged at the first slot bans for about 32. The critical ban has the same slack (255 to 256 epochs), which does not matter there. Options:
- (a) keep epoch semantics for parity, or
- (b) store `blacklistUntilSlot = chargeSlot + period * SLOTS_PER_EPOCH`, so the first ban is always 32 slots.

I lean to (b), and it is probably worth mentioning to potuz as well.

### 4.2 Late reveal clears the record

Prysm calls `RecordSuccess` on every imported envelope, including a late envelope for the very slot that was just charged, for example one fetched later or one that arrived after N+1 built on EMPTY. A withholding builder can therefore clear its ban by revealing late. Guard: in `recordSuccess(builderIndex, blockRoot)`, ignore the success if `blockRoot` is in `recorded`, meaning this exact payload was charged.

### 4.3 Index reuse

Mirror Prysm (drop the records of inactive indices). Run it once per epoch against the head state rather than per block.

### 4.4 Collateral weaponization hardening (optional)

An endpoint can return another builder's *gossip* bid verbatim. That bid is signature-valid and not duplicated across endpoints in the same request, so Prysm still links the victim to that endpoint. Cheap mitigation: keep a small 2-slot set of bid signatures seen on gossip, and do not link indices whose builder-API bid matches one. The impact without it is bounded (collateral bans never count toward self-build and are capped at 32 epochs), so this can wait.

### 4.5 Coexistence with the aggregate breaker

potuz argues that missed-slot or EMPTY-rate counting is superseded by "number of banned builders". I would **keep** #9598 as a coarse backstop. It catches what attribution cannot: failures below the 60% quorum, skipped-slot cases and unknown causes. I would consider loosening its default only once the per-builder layer has run on devnets.

## 5. Later phases (not in Prysm yet)

- **Trusted tier** (article's middle step). Trusted means indices learned from VC-configured builder-API entries plus an operator `--builder.trustedIndices`. Untrusted means p2p-only indices. With at least 3 untrusted builders directly blacklisted, stop reading p2p bids and keep the builder API. With at least 7, self-build. This is local policy, so being ahead of Prysm is fine.
- **Operator denylist** `--builder.denylist <indices>`: a permanent ban that success never clears. It is small and matches your "blacklisting" ask. Relay URLs are already operator-controlled through the VC builder config.
- **Persistence across restarts**: no. Prysm and the article both treat restart as the reset button.

## 6. PR plan

1. **fork-choice**: `ProtoBlock.builderIndex` plus `getSameSlotAttestationScore` / `isBuilderPaymentQuorumReached`, with unit tests (same-slot votes counted, later EMPTY/FULL votes and boost excluded).
2. **Single-builder blacklist**: `BuilderBlacklist` without relays, the charge hook in `importBlock`, the clear hook in `importExecutionPayload`, the gossip IGNORE, the publish-API reject, the `produceBlockV4` filters, `isSelfBuildOnly` folded into the breaker, options, CLI, metrics.
3. **Relay tracking**: observe, ban, collateral, release, bounds, normalization, skipping banned URLs in `BuilderApiClient`, the `relayTracking` toggle.
4. **Optional**: trusted tier, denylist, debug API, the 4.4 hardening.

## 7. Test plan

- Port Prysm's `cache/builder_circuit_breaker_test.go` cases to the pure class: first offense, critical, back-off reset, success clears, relay collateral, release once no failing member is left, eviction bounds (never evict banned relays or failing members), prune, inactive drop, and an invariant check that `relays` and `relaysByIndex` stay mirrors.
- importBlock charge: one test per bail-out reason, plus a dedupe test with two children of the same empty parent.
- `produceBlockV4`: a blacklisted p2p bid is dropped, a banned relay is not contacted, a blacklisted builder-API bid is discarded, self-build-only forces local.
- Gossip: an IGNOREd blacklisted bid is not inserted into the pool, and an honest lower bid is still accepted afterwards.
- Devnet: a kurtosis run with a builder that withholds on demand, checking the ban, the relay ban, recovery, metrics and that our node stops forwarding its bids.

## 8. Open questions for you

1. Keep the #9598 aggregate breaker as a backstop (my recommendation), or replace it as potuz suggests?
2. Should gossip IGNORE blacklisted builders' bids, which means we stop propagating them, network-visible? That is Prysm parity and the article's intent. I'd say yes.
3. Ban granularity: slot-based (4.1b) or epoch parity?
4. Defaults: adopt Prysm's as-is (`allowedFailures = 0`)? vladimir-ea raised on #17294 that a builder decides to reveal before it sees all attestations, so an honest builder that saw less than 40% while aggregators saw at least 60% gets a first-offense ban. The short first ban limits the damage, but this is the main false-positive path.
5. When the local payload fails while self-build-only is active, should we still fall back to non-blacklisted bids? Prysm does this for the p2p bid. Today we would miss the slot.
6. Trusted tier and denylist in the first round, or later?
