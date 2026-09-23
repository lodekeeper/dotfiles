# Vouch static-delay vs Lodestar attestation pool findings

Date: 2026-09-22

Context: secondary Vouch instance was expected to stay passive while a primary instance was active, but logs showed the secondary still entered the attestation path and then failed to obtain signatures because Dirk/slashing protection had already recorded an attestation for the same target epoch.

## Short conclusion

The current evidence points to a Vouch/Lodestar observation mismatch, not an immediate double-signing safety issue.

- The primary appears to be active and signing first.
- The secondary still decides to attest and reaches Dirk signing.
- Dirk then refuses the secondary because that target epoch was already signed.
- So Dirk is acting as the safety backstop, but Vouch `static-delay` is not reliably suppressing the secondary before signing.

The most likely code-level reason is that Vouch `static-delay` checks the Beacon API attestation pool, while Lodestar's `GET /eth/v2/beacon/pool/attestations` returns the aggregated attestation pool, not the pre-aggregated single-attestation pool populated by `POST /eth/v2/beacon/pool/attestations`.

That means even if the primary submits a raw single attestation to a shared Lodestar beacon node, the secondary may not observe that raw attestation via the pool GET endpoint quickly enough to stay passive. It may only see later aggregates/gossip, which is too late for the configured delay.

## Live evidence

Observed secondary behavior:

- Secondary Vouch entered attestation duties repeatedly.
- At the signing step, Vouch logged that no signature was available and did not submit an attestation.
- Local Dirk logs around the same slots rejected the secondary client for the same target epoch already having been signed.

Concrete Dirk pattern seen across consecutive epochs:

- 17:43:16 UTC: target epoch `477278` already signed
- 17:48:40 UTC: target epoch `477279` already signed
- 17:52:28 UTC: target epoch `477280` already signed

Interpretation: the primary likely requested/obtained signatures first. The secondary then attempted the same duty, but Dirk correctly refused the duplicate signing path.

## Vouch code path

### `static-delay` waits, then queries attestation pool

In Vouch v1.12.1, `static-delay` documents itself as waiting to see whether another instance already attested/proposed:

- https://github.com/attestantio/vouch/blob/v1.12.1/services/multiinstance/staticdelay/service.go#L14-L16

For attestations, `ShouldAttest`:

- if already active, immediately returns true
- otherwise sleeps until the spec attestation delay
- then sleeps the configured extra `attester-delay`
- queries `AttestationPool` by slot and committee
- if it sees an attestation with one of this instance's validator committee bits set, it stays passive
- if it sees none, it activates and returns true

References:

- Delay and pool check: https://github.com/attestantio/vouch/blob/v1.12.1/services/multiinstance/staticdelay/shouldattest.go#L43-L71
- Bit check and passive decision: https://github.com/attestantio/vouch/blob/v1.12.1/services/multiinstance/staticdelay/shouldattest.go#L77-L95
- Active decision when no attestation is found: https://github.com/attestantio/vouch/blob/v1.12.1/services/multiinstance/staticdelay/shouldattest.go#L100-L103

The spec attestation delay is computed as `SECONDS_PER_SLOT / INTERVALS_PER_SLOT`, which is 4 seconds on mainnet, then Vouch adds the configured `attester-delay`.

- https://github.com/attestantio/vouch/blob/v1.12.1/services/multiinstance/staticdelay/service.go#L112-L145

In the live config, `attester-delay` is 1 second, so the secondary checks around 5 seconds into the slot.

### Combined attestation-pool strategy queries all configured providers

Vouch's combined attestation pool strategy fans out `AttestationPool` requests to its configured beacon node providers and de-duplicates returned attestations by hash tree root.

- Providers configured into service: https://github.com/attestantio/vouch/blob/v1.12.1/strategies/attestationpool/combined/parameters.go#L60-L64
- Fan-out to providers: https://github.com/attestantio/vouch/blob/v1.12.1/strategies/attestationpool/combined/attestationpool.go#L64-L71
- De-dupe into a root-keyed map: https://github.com/attestantio/vouch/blob/v1.12.1/strategies/attestationpool/combined/attestationpool.go#L79-L100
- Return combined result: https://github.com/attestantio/vouch/blob/v1.12.1/strategies/attestationpool/combined/attestationpool.go#L186-L194

So if the relevant attestation is visible through any configured beacon node's pool response, `static-delay` should be able to suppress the secondary.

### Multinode submitter submits to all configured attestation submitters

Vouch's `submitter.style: multinode` starts a submission goroutine for each configured attestation submitter and returns once at least one succeeds.

- One goroutine per submitter: https://github.com/attestantio/vouch/blob/v1.12.1/services/submitter/multinode/submitattestations.go#L45-L58
- Per-submitter API submission: https://github.com/attestantio/vouch/blob/v1.12.1/services/submitter/multinode/submitattestations.go#L96-L115

This means a primary configured with the same reachable beacon node URLs should submit to those shared nodes, not only to one local node.

Important caveat: Docker-local names like `http://consensus:5052` are host-local. If both primary and secondary configs say `http://consensus:5052` on different machines, those are not the same beacon node.

## Lodestar code path

Checked Lodestar v1.48.0 and current `unstable`; the relevant endpoint behavior matches.

### Pool GET returns aggregated attestations only

`GET /eth/v2/beacon/pool/attestations` is implemented by `getPoolAttestationsV2`. It reads from `chain.aggregatedAttestationPool.getAll(slot)`.

- v1.48.0: https://github.com/ChainSafe/lodestar/blob/v1.48.0/packages/beacon-node/src/api/impl/beacon/pool/index.ts#L40-L54
- unstable: https://github.com/ChainSafe/lodestar/blob/unstable/packages/beacon-node/src/api/impl/beacon/pool/index.ts#L40-L54

It does not include `chain.attestationPool.getAll(...)` from the pre-aggregated single-attestation pool.

### Pool POST stores raw/single attestations elsewhere

`POST /eth/v2/beacon/pool/attestations` validates each submitted attestation, inserts it into `chain.attestationPool`, emits attestation events, and publishes it on gossip.

- Inserts into `chain.attestationPool`: https://github.com/ChainSafe/lodestar/blob/v1.48.0/packages/beacon-node/src/api/impl/beacon/pool/index.ts#L103-L114
- Emits attestation/single-attestation events: https://github.com/ChainSafe/lodestar/blob/v1.48.0/packages/beacon-node/src/api/impl/beacon/pool/index.ts#L121-L135
- Publishes gossip: https://github.com/ChainSafe/lodestar/blob/v1.48.0/packages/beacon-node/src/api/impl/beacon/pool/index.ts#L137-L143

So Lodestar does store/broadcast the primary's raw attestation on POST, but the pool GET path Vouch is using reads the aggregated pool instead.

### Aggregates are separate

Lodestar's validator aggregate endpoint reads aggregate candidates from `chain.attestationPool.getAggregate(...)`, and submitted aggregate-and-proof objects are inserted into `chain.aggregatedAttestationPool`.

- Aggregate lookup from `attestationPool`: https://github.com/ChainSafe/lodestar/blob/v1.48.0/packages/beacon-node/src/api/impl/validator/index.ts#L1569-L1589
- Aggregate insert into `aggregatedAttestationPool`: https://github.com/ChainSafe/lodestar/blob/v1.48.0/packages/beacon-node/src/api/impl/validator/index.ts#L1592-L1620

That separation is useful internally, but it is exactly the split that makes the Beacon API pool GET less useful for Vouch's single-attestation passive check.

## Beacon API wording

The Beacon API describes `GET /eth/v2/beacon/pool/attestations` as retrieving attestations known by the node but not necessarily included in a block.

- https://github.com/ethereum/beacon-APIs/blob/master/apis/beacon/pool/attestations.v2.yaml#L1-L5

The same endpoint file describes POST success as attestations being stored in the pool and broadcast on the appropriate subnet.

- https://github.com/ethereum/beacon-APIs/blob/master/apis/beacon/pool/attestations.v2.yaml#L58-L97

Vouch's expectation is therefore understandable: after the primary submits a valid single attestation to a shared node, a later pool GET should be able to reveal it. Lodestar's current implementation narrows the GET response to aggregated attestations, so this expectation is not met reliably.

## Why this matches the observed failure

Timeline shape:

1. Primary signs and submits an attestation.
2. Dirk records the target epoch as signed.
3. Secondary waits until roughly 5 seconds into the slot.
4. Secondary queries beacon node attestation pools.
5. Lodestar pool GET does not expose the raw single attestation that POST inserted.
6. Secondary sees no matching attestation bit and activates.
7. Secondary asks Dirk for signatures.
8. Dirk refuses because the epoch was already signed.
9. Secondary logs no signatures / no signed attestations / failed to attest.

This explains both observations at once:

- the primary can be active and safe
- the secondary can still try duties because it cannot observe the primary's raw attestation through the pool GET endpoint quickly enough

## Metrics note

Vouch and Dirk expose application metrics on their own `/metrics` endpoints, but in the checked deployment those app metrics were not being scraped into Prometheus. Generic container metrics existed, but no `vouch_*` or `dirk_*` application series were present.

Reason found locally: the Alloy Docker scrape path selects containers with the metrics scrape label, and the Vouch/Dirk containers did not have the required metrics labels.

## Practical options

Operational workaround:

- Increase Vouch `attester-delay` so the secondary has more time to see later aggregates/gossip.
- Downside: slower failover; still depends on aggregate/gossip timing.

Cleaner fixes:

- Lodestar: make `GET /eth/v2/beacon/pool/attestations` include or stitch in pre-aggregated single attestations from `chain.attestationPool`, matching the broader Beacon API "known by the node" expectation.
- Vouch: use a single-attestation/event source for passive detection instead of relying on the aggregated-pool-shaped response from pool GET.
- Deployment: make sure any shared beacon node endpoints are truly shared/reachable from both primary and secondary; do not assume same Docker service names refer to the same node across hosts.

