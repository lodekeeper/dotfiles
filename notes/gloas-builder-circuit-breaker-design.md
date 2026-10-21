# Gloas builder circuit breaker for Lodestar (Prysm + Lighthouse models)

Status: draft for discussion, 2026-10-20
Author: lodekeeper, for Nico

Updated 2026-10-20: Lighthouse implementation and open-PR review added in **sections 9–11**, with a side-by-side comparison and proposed adjustments to the Lodestar design. Sections 1–8 retain the original Prysm-based proposal; section 11 offers recommendations for discussion, not an agreed change of scope.

## TL;DR

- Prysm replaced "count missed slots" with **per-builder accountability**. A builder that wins a bid, gets a well-attested block (strictly more than 60% of the slot committee weight) and then does not reveal its payload is **blacklisted locally**. Its bids are not propagated on gossip, not requested and not selected. Boundary detail: the spec charges at `>=` its integer payment quorum, whereas Prysm uses strict `>`; Lighthouse follows the spec boundary (section 9.2).
- A **relay (direct-connection endpoint) is banned with its builder.** Prysm learns which builder indices each builder-API URL serves from verified bids. When one of them fails, every endpoint that served it is banned and stops being contacted. Every other index behind those endpoints is collaterally blacklisted.
- **Systemic fallback.** Once 7 or more builders are directly blacklisted at the same time, the node stops taking foreign bids and self-builds.
- For Lodestar I propose a `BuilderBlacklist` component that sits next to the existing aggregate EMPTY-rate breaker from #9598 and does not replace it. It needs two small fork-choice additions: `builderIndex` on `ProtoBlock` and a same-slot attestation score accessor. Hooks go in `importBlock` (charge), `importExecutionPayload` (clear), bid gossip validation, `publishExecutionPayloadBid`, `BuilderApiClient` and `produceBlockV4`.
- Three to four PRs. Most of the logic is a pure state machine that we can port almost 1:1, including Prysm's test cases. Being single-threaded removes all of Prysm's lock juggling (their #17714 race does not exist for us).
- I found a few things to decide or improve on, see "Deviations" and "Open questions". The biggest: Prysm's first-offense "1 epoch" ban is really "until the end of the current epoch", which can be zero slots.
- **Lighthouse already has a merged Gloas breaker** (#10162, October 15). It combines quorum-qualified missed-payload counts with fixed-duration, chain-specific builder bans. It excuses locally timely envelopes or healthy PTC evidence, also bans definitive EL-invalid payloads, filters at proposal selection rather than gossip, and has no relay collateral bans or escalating penalty. A tripped aggregate breaker demotes external bids but retains unbanned direct/gossip bids if local building fails. See sections 9–11 before choosing which client behavior to copy.

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
4. `!CouldBuilderWithhold(parent)`: the parent's own node balance, which holds the same-slot votes and no proposer boost, is **> 60%** of the committee weight (`BuilderFailureWeightThreshold = 60`). This approximates the spec's builder payment quorum (`BUILDER_PAYMENT_THRESHOLD = 6/10`): above it the builder pays regardless, so withholding is not a legitimate move. The exact equality/rounding difference from the spec and Lighthouse is documented in section 9.2.
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

## 9. What Lighthouse actually implements

### 9.1 Provenance and scope

- **Merged:** [sigp/lighthouse#10162, Gloas builder circuit breaker](https://github.com/sigp/lighthouse/pull/10162), by ethDreamer, merged **2026-10-15 00:03:50 UTC**, merge commit `9f36db580edd0df7c8e541c1040e54a259796026`.
- **Source inspected:** freshly fetched `origin/unstable` at **`7168f324a0458674333a25e9d3fd64de3885183c`**, commit time **2026-10-20 19:05:26 UTC**. All Lighthouse code links below pin that commit, not the moving branch or PR description.
- Main files: [the breaker state machine][lh-breaker], [slot-boundary detection][lh-detection], [Gloas candidate acquisition/filtering][lh-selection], [candidate ranking][lh-ranking], [envelope import][lh-envelope], and [integration tests][lh-tests]. This is node-local proposal policy: it does not make an otherwise valid block or envelope invalid.
- The original Prysm analysis above remains its earlier snapshot. For this comparison I also checked the core cache, charging hook and weight predicate at freshly fetched `develop` **`9c7f9f9b711f00c9ce933812f26a7252897658f2`**, commit time 2026-10-20 20:05:23 UTC. The core distinctions below match that source: [cache][prysm-cache], [charging hook][prysm-charge], [weight predicate][prysm-weight].

**Do not use #10162's description as the behavioral specification.** It still says direct builders are not queried when the breaker trips, that a missing self-built payload counts toward the skip rules, and describes the local excuse as “never received”. The merged source instead queries direct builders, excludes zero-value payments from skip counts, and checks envelope observation against the PTC deadline. It also checks PTC data availability and adds EL-invalid bans. The code and tests below take precedence.

### 9.2 Two mechanisms, with different evidence

**A. Aggregate skip rules, evaluated for each proposal.** `evaluate_skips_for_state` reads the **production state on the parent being extended**, advanced to the proposal slot, including the parent's payload-availability bit if building on FULL.

1. Compare adjacent historical `block_roots` to distinguish a missing beacon block from a block with a missing payload. Read `execution_payload_availability` for whether its payload was applied to this chain.
2. A missing payload counts only when the corresponding pending payment has **non-zero amount** and its attestation weight has reached the builder payment quorum. Self-builds have zero bid value; a zero-value external bid is excluded too.
3. For the immediately previous slot only, fork-choice support can substitute for payment weight: no later block has yet included that slot's attestations. Older slots use on-chain payment weights, not accumulated fork-choice subtree weight. Payments only survive for the current/previous epoch, which bounds the consecutive scan.
4. The consecutive scan skips missing beacon blocks **and uncharged missing payloads**; neither resets the run. It stops at the first present payload, once the configured limit is exceeded, or at the previous epoch's start. The rolling rule counts eligible misses in the last `SLOTS_PER_EPOCH` slots.
5. Defaults: `--builder-fallback-skips=3` and `--builder-fallback-skips-per-epoch=8`. The comparisons are **strictly `>`**, so these mean “tolerate 3 / tolerate 8”: the **4th consecutive** or **9th in the rolling window** trips. These are not Prysm's “7 directly banned builders” rule.

The integer quorum is `floor(floor(total_active_balance / SLOTS_PER_EPOCH) * numerator / denominator)`, and the weight check is **`>= quorum`**. For live fork-choice evidence Lighthouse uses **justified balances**, matching the weight's units; for historical payments it uses the production state's active balance. The current consensus spec also uses `payment.weight >= quorum`: [quorum helper][spec-quorum], [payment processing][spec-payments]. Prysm instead excludes equality through `balance * 100 <= committeeWeight * 60` in `CouldBuilderWithhold`. Consequently the strict-`>` pseudo-code in section 3.2 is **Prysm parity, not exact spec/Lighthouse parity**; preserve integer operation order if choosing the latter.

Source: [breaker helpers and scans][lh-breaker].

**B. Individual builder offences.** At each slot boundary, `per_slot_task` first recomputes fork choice and then examines **only the canonical head**, requiring `head.slot + 1 == current_slot`. It does **not** wait for a child block to prove an EMPTY extension. It skips this heavy work when too far behind, and checks are Gloas-only. A missed-reveal ban requires all of:

- an external builder, not `BUILDER_INDEX_SELF_BUILD`;
- **no envelope observed locally at or before** `slot_start + get_payload_attestation_due()`;
- **not both** a positive PTC timeliness verdict **and** a positive PTC data-availability verdict;
- known block weight **`>=` the payment quorum** in fork-choice justified-balance units.

The PTC verdicts read the respective vote thresholds **without requiring this node to have received the payload**. This avoids blaming a builder merely because our node missed a reveal that the committee saw as timely and available. Timely PTC votes without data availability do **not** excuse it. A timely locally observed envelope is independently sufficient to avoid a *missed-reveal* ban even if local execution/import takes longer; this is not a check that local execution or data availability succeeded. A later definitive EL-invalid result can still ban it.

Conversely, a **late** envelope does not excuse the offence, even if it was fully imported before the check. That differs from Prysm's “FULL node exists” guard and later `RecordSuccess`. Lighthouse has no success-triggered reset. Unlike the aggregate counter, this individual-ban predicate does **not** require a non-zero bid/payment amount. Sources: [slot-boundary detection][lh-detection], [`should_ban_for_missed_reveal`][lh-breaker], [fork-choice PTC accessors][lh-fc].

There is also a second, separate trigger: a signed, bid-bound envelope definitively rejected by the EL as **`INVALID` or `INVALID_BLOCK_HASH`** records an offence immediately. No attestation quorum or PTC evidence is needed; EL-unreachable/syncing/transient errors do not take this branch. Sources: [envelope import error branch][lh-envelope] and [ban recording][lh-detection].

### 9.3 Ban state, duration and reorg behavior

The in-memory state is effectively:

```text
Map<builderPubkey, [ { offendingBlockRoot, offendingBlockSlot, expiresAtSlot } ]>
```

- Identity is the **builder pubkey**, resolved from the block's builder index in state, not the index alone.
- An entry expires at `detected_at + ban_slots`, with activity while `proposal_slot < expires_at`. Default **32 slots**, minimum `SLOTS_PER_EPOCH`: the CLI rejects a smaller value and the constructor also clamps programmatic configuration to the minimum.
- Repeating the same offending root is a no-op. A different offence adds an independent entry with its own expiry; it does not rewrite the first entry and there is **no 1→256 epoch escalation or 5-epoch failure back-off**.
- An entry only bans a proposal if its production state records the offending root at the offending slot. Reorg **away** from that block: the entry stops applying. Reorg **back** before expiry: it applies again. This is a query-time ancestry check, not deleting history when the global head changes.
- With an unusually long ban beyond the historical-root ring, an unavailable root lookup is treated conservatively as canonical. Do not describe unlimited-length ancestry tracking as exact.
- Expired entries are pruned each slot. The ban-entry gauge counts entries, not distinct builders or ancestry-active bans. Nothing is persisted; restart clears bans. `--builder-fallback-disable-checks` disables both aggregate rules and ban enforcement/production triggers.

Source: [configuration, `ban_builder`, `is_banned`, `prune`][lh-breaker], [CLI][lh-cli].

### 9.4 Enforcement and fallback: selection policy, not a gossip ban

Lighthouse collects configured **direct builder bids and the highest cached gossip bid**, then drops external candidates whose builders are banned on the production chain. Unknown/exiting builders are also filtered for independent validity reasons. Local self-build is never passed through the external filter.

When an aggregate skip rule trips (or evaluating it errors), surviving external candidates are **demoted**, not discarded. Demotion is the first ranking key, above value/boost/other preferences:

```text
individual ban applies  → remove that external candidate
aggregate rule trips   → local build wins if viable, regardless of external value
local build fails      → best surviving, unbanned external candidate can still win
```

**Direct endpoints are still contacted while tripped**, and both direct and gossip bids can be fallback candidates. This is explicit in the merged source and direct-bid ranking unit test, despite the stale PR body. A banned builder never becomes the “last resort”; with no local build and no unbanned candidate, production fails.

There is **no circuit-breaker filter in gossip bid validation/propagation or bid-publishing APIs**, no endpoint→builder association table, no relay-wide/collateral ban, and no “N banned builders means self-build-only” gate in this implementation. Other normal gossip validity rules remain in effect. Also, the pre-Gloas `--builder-fallback-epochs-since-finalization` check is not applied to the Gloas path: beacon finality alone does not establish execution-payload health.

A trade-off to keep visible: the gossip cache keeps just **one highest bid per `(slot, parent)`**. A banned high bidder can occupy that position and be removed only during selection, leaving no second-best gossip candidate to recover. This is an inference from the [cache][lh-cache] plus [production filter][lh-selection], not a demonstrated exploit or new upstream issue. Direct bids/local building remain separate alternatives. It strengthens the need to resolve our section 8.2 gossip-policy choice explicitly rather than assuming both clients behave alike.

Sources: [candidate acquisition/filtering][lh-selection], [ranking and direct/gossip demotion tests][lh-ranking].

### 9.5 Existing tests and limits

I **read**, but did not run, Lighthouse's Rust tests. Documentation research does not establish a fresh passing build. The [integration suite][lh-tests] includes:

- quorum-qualified missed reveal, below-quorum exclusion, deduplication and exact expiry;
- envelope observed exactly at the deadline, late reveal despite successful import, and PTC timely+available versus timely+unavailable;
- `INVALID` and `INVALID_BLOCK_HASH`, including no-quorum invalid-payload evidence and disabled checks;
- ban filtering, and different results for proposals extending the offending chain versus a competing chain;
- consecutive/rolling missed-payload rules, zero-valued self-build exclusion, below-quorum exclusion, skipped beacon slots, roll-off and disabled checks;
- aggregate trip + failed local build still uses an unbanned gossip bid; banned builder cannot be the fallback. The [ranking unit tests][lh-ranking] separately cover demoted direct bids.

Known coverage limits in the design, not claims of bugs:

- Missed-reveal detection observes the head at that single next-slot check. An offence on a fork that becomes canonical later, or a head older than the previous slot, is not retrospectively charged by that detector. Prysm's imported-child evidence has a different coverage/scheduling trade-off.
- PTC/local observation guards reduce false blame for local propagation/execution delay but do not remove the builder-versus-node attestation-view disagreement discussed in section 8.4.
- Historical skip counts can undercount when attestations have not been included on chain, especially across empty slots. The fork-choice supplement only covers the immediately preceding slot.
- Repeated offences merely create overlapping fixed-window bans. Without Prysm's relay association/escalation/systemic distinct-builder gate, this is a materially different deterrence model, not just different default numbers.

### 9.6 Open PRs checked (2026-10-20)

- **[#10099 `produceBlockV4WithBid`](https://github.com/sigp/lighthouse/pull/10099)** — OPEN, head **`e61322dbe5c7624230db6772e7a3a6af976b9816`**. Adds `POST /eth/v4/validator/blocks/{slot}/with_bid` so a VC can supply a bid. I fetched that PR ref and inspected its Gloas path: API-supplied candidates still pass through the same chain-specific ban filter and aggregate demotion. In supplied-bid mode no direct builders are contacted, and gossip is consulted only if the supplied bid fails initial validation; a later ban-filter rejection does not reopen gossip selection. It extends the intake/enforcement surface, not the penalty state machine. Do not present it as merged behavior.
- **[#10395 pre-Gloas builder-setting warnings](https://github.com/sigp/lighthouse/pull/10395)** — OPEN, head **`f5a7c9d332cffc7ed13e16f77a505ecb1f705886`**. Help/book changes only, including marking the finalization fallback flag ineffective after Gloas; no runtime change. It depends on **[#10374 ePBS builder configuration CLI](https://github.com/sigp/lighthouse/pull/10374)** (also OPEN), which changes operator configuration, not ban policy.
- Searched open PRs for circuit-breaker/ban references and checked related builder PRs. I found no separate open PR redesigning Lighthouse's core breaker state machine; this is bounded search evidence, not a claim that every unrelated PR was exhaustively audited. Prysm #17723 and #17080 remain OPEN at this check.

## 10. Prysm versus Lighthouse: actual policy differences

| Aspect | Prysm model (sections 1–2) | Lighthouse merged implementation |
|---|---|---|
| Missed-reveal trigger | Import child at `parent.slot + 1`; no parent FULL node; same-slot support strictly >60% | Next-slot task, previous-slot canonical head; quorum `>=`; no timely local envelope or healthy PTC excuse |
| Need a child block? | Yes, consecutive slot | No; timer/head-based |
| Other-fork evidence | Can charge using an imported noncanonical child | Missed-reveal detector only checks current head |
| Ban identity / scope | Builder index, node-wide (plus relay collateral) | Pubkey + offending root, applies only to chains containing the offence |
| Reveal evidence | Imported FULL payload avoids charge; imported envelope later clears failure state | Timely local observation or PTC timely+available avoids missed-reveal charge; late reveal does not reset |
| Definitive EL-invalid envelope | No separate trigger in the analyzed breaker | Ban immediately, without payment quorum |
| First/repeat penalty | Epoch-boundary first ban; escalates to 256 epochs on critical repeat, 5-epoch back-off | Fixed 32-slot default/minimum-epoch duration per offence; independent entries, no escalation |
| Relay behavior | Ban associated endpoints and collateral indices; skip banned endpoints | No endpoint bans or collateral; endpoint calls continue |
| Gossip bids | Locally blacklisted builder bids IGNOREd, not forwarded | Breaker does not filter gossip; filters candidate at production |
| Systemic fallback trigger | At least 7 directly blacklisted builders | More than 3 consecutive or more than 8 per-epoch-window **charged payload misses**, by default |
| Tripped fallback behavior | Do not request builder API; unblacklisted p2p fallback if local build fails | Request direct bids; demote all unbanned externals; either direct or gossip may save a failed local build |
| Restart | In-memory state cleared | In-memory bans cleared; aggregate history re-derived from chain state |

These are not yet a common client feature-flag model. Matching CLI spelling alone would not align detection, gossip propagation, endpoint traffic or fallback behavior.

## 11. Implications for the Lodestar proposal (recommendations, not implementation approval)

The goal remains the requested Prysm-model design. Lighthouse supplies useful hardening options, but silently porting its whole policy would change that goal. I would amend the design discussion as follows:

1. **Keep the original Prysm model visible**, especially relay association/collateral and escalating penalties. Lighthouse does not supply equivalents. Whether to adopt those or Lighthouse's simpler fixed penalties is an explicit policy decision.
2. **Use slot-based first-ban expiry** as already recommended in section 4.1. Lighthouse is a concrete precedent. Independently choose `>= spec_integer_quorum` versus strict Prysm `>60%`; my recommendation is the spec boundary, using same-slot scores and the same balance units, with exact-equality/rounding tests.
3. **Add an observation/PTC evidence layer before blaming a missed reveal.** Store the first envelope-observed timestamp separately from execution/import completion. Expose PTC timely and data-available verdicts independently of local payload receipt; copy the conjunction, not timeliness alone. This refines the initial section 3.3 predicate. It does not authorize clearing an already recorded late-reveal offence. Decide separately whether a timely locally observed envelope with unavailable blobs should excuse the missed-reveal branch as it does in Lighthouse.
4. **Do not equate imported payload with timely reveal.** If adopting Lighthouse's timing semantics, the early “has FULL → no charge” check in section 3.3 must be replaced by deadline evidence, and section 3.4's `recordSuccess` must not clear a charged offence. Keeping only the section 4.2 late-success guard would still miss a late payload imported *before* detection.
5. **Choose ban scope explicitly.** Pubkey identity avoids index-identity ambiguity; root-bound offences make bans reorg-aware. Root binding should be deliberate if added to the Prysm state machine: global relay bans/collateral need an equally explicit rule when the underlying offence leaves the proposal chain. Do not accidentally combine chain-specific direct bans with irreversible relay collateral.
6. **Keep aggregate protection as a separate layer**, as originally proposed, but distinguish our existing broad EMPTY-rate backstop from Lighthouse's **quorum/non-zero-payment-qualified** misses. Lighthouse intentionally excludes uncharged/zero-value misses; our section 4.5 backstop intentionally catches failures attribution cannot. They should not be presented as equivalent, and adopting its narrower counter could weaken that backstop.
7. **Separate hard bans from aggregate local preference.** Lighthouse's ranking model is a good answer to section 8.5: once an aggregate breaker trips, prefer viable local production while retaining only unbanned external fallbacks. Whether still to dial direct endpoints while tripped is independent from whether an already available external bid can save the slot. This does not change the rule that a hard-banned builder is never fallback.
8. **Consider a separate definitive-invalid-payload offence** once the envelope is authenticated and bound to the committed bid. It must not ban on EL timeouts, `SYNCING`, optimistic status or mere failure to finish validation. Lighthouse demonstrates the extra branch; decide whether it shares the missed-reveal penalty or deserves a distinct policy/metric.
9. **Keep gossip policy an explicit open question.** Original section 3.5 implements Prysm-style IGNORE; Lighthouse does selection-only filtering. If we choose the latter, address single-best-bid pool masking so discarding a banned winner does not erase access to an honest alternative. If bans become chain-specific, a gossip decision made against one head must also account for another proposal parent.

Additional tests worth importing into the section 7 plan: exact quorum equality/rounding; timely observation with slow local execution; late-but-already-imported envelope; PTC timely **and** available versus timely-only; definitive invalid versus transient EL results; reorg away/back with two offences on different forks; exact slot expiry across an epoch boundary; aggregate demotion plus failed local build for both direct and gossip sources; API-supplied bids using every enforcement gate if that endpoint is added.

**My current recommendation:** retain the Prysm-oriented architecture and relay policy as the baseline; take Lighthouse's slot-duration precision, timing/PTC evidence separation and viable-unbanned-fallback ranking into the next design discussion. Ban scope, escalation, gossip propagation and whether to query endpoints while tripped still need explicit client/operator alignment. No Lodestar code or default has been changed by this document.

[lh-breaker]: https://github.com/sigp/lighthouse/blob/7168f324a0458674333a25e9d3fd64de3885183c/beacon_node/beacon_chain/src/circuit_breaker.rs
[lh-detection]: https://github.com/sigp/lighthouse/blob/7168f324a0458674333a25e9d3fd64de3885183c/beacon_node/beacon_chain/src/beacon_chain.rs#L7944
[lh-selection]: https://github.com/sigp/lighthouse/blob/7168f324a0458674333a25e9d3fd64de3885183c/beacon_node/beacon_chain/src/block_production/gloas.rs#L1111
[lh-ranking]: https://github.com/sigp/lighthouse/blob/7168f324a0458674333a25e9d3fd64de3885183c/beacon_node/beacon_chain/src/block_production/bid_selection.rs
[lh-envelope]: https://github.com/sigp/lighthouse/blob/7168f324a0458674333a25e9d3fd64de3885183c/beacon_node/beacon_chain/src/payload_envelope_verification/import.rs#L146
[lh-tests]: https://github.com/sigp/lighthouse/blob/7168f324a0458674333a25e9d3fd64de3885183c/beacon_node/beacon_chain/tests/circuit_breaker.rs
[lh-fc]: https://github.com/sigp/lighthouse/blob/7168f324a0458674333a25e9d3fd64de3885183c/consensus/fork_choice/src/fork_choice.rs#L1638
[lh-cli]: https://github.com/sigp/lighthouse/blob/7168f324a0458674333a25e9d3fd64de3885183c/beacon_node/src/cli.rs#L1462
[lh-cache]: https://github.com/sigp/lighthouse/blob/7168f324a0458674333a25e9d3fd64de3885183c/beacon_node/beacon_chain/src/payload_bid_verification/payload_bid_cache.rs#L30
[spec-quorum]: https://github.com/ethereum/consensus-specs/blob/d9663f85be248c4fd0ae95806da6070e17c2442b/specs/gloas/beacon-chain.md#L1433
[spec-payments]: https://github.com/ethereum/consensus-specs/blob/d9663f85be248c4fd0ae95806da6070e17c2442b/specs/gloas/beacon-chain.md#L1721
[prysm-cache]: https://github.com/OffchainLabs/prysm/blob/9c7f9f9b711f00c9ce933812f26a7252897658f2/beacon-chain/cache/builder_circuit_breaker.go
[prysm-charge]: https://github.com/OffchainLabs/prysm/blob/9c7f9f9b711f00c9ce933812f26a7252897658f2/beacon-chain/blockchain/builder_circuit_breaker.go
[prysm-weight]: https://github.com/OffchainLabs/prysm/blob/9c7f9f9b711f00c9ce933812f26a7252897658f2/beacon-chain/forkchoice/doubly-linked-tree/gloas.go#L582
