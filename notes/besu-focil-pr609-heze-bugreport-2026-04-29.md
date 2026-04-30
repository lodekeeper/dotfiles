# Besu focil / Heze (Bogota) PR-609 support gap — repro + root cause

## Summary
Running a Heze-enabled devnet with `ethpandaops/besu:focil` and `ethpandaops/lodestar:focil` stalls at the Heze boundary because Besu advertises `engine_forkchoiceUpdatedV5` via `engine_exchangeCapabilities` but rejects the real V5 call with `{"code":-32604,"message":"Method not enabled"}`.

This is not just a CL/EL mismatch. The Besu `focil` branch only partially lands execution-apis PR #609 / Bogota support:
- method classes exist (`engine_forkchoiceUpdatedV5`, `engine_newPayloadV6`, `engine_getInclusionListV1`)
- but Bogota is not actually plumbed into the genesis/schedule path
- capabilities are advertised from the enum, not from the enabled method set
- and FCU V5 payload building drops `inclusionListTransactions`

## Repro
Kurtosis config:

```yaml
participants:
  - el_type: besu
    el_image: ethpandaops/besu:focil
    cl_type: lodestar
    cl_image: ethpandaops/lodestar:focil
    supernode: true
    count: 2
network_params:
  genesis_delay: 20
  gloas_fork_epoch: 0
  heze_fork_epoch: 1
  seconds_per_slot: 6
  num_validator_keys_per_node: 256
snooper_enabled: true
additional_services:
  - dora
  - tx_fuzz
  - spamoor
port_publisher:
  additional_services:
    enabled: true
    public_port_start: 65500
spamoor_params:
  spammers:
    - scenario: eoatx
      config:
        throughput: 100
    - scenario: uniswap-swaps
      config:
        throughput: 100
    - scenario: blob-combined
      config:
        throughput: 5
```

Observed Lodestar error:

```text
Failed to run prepareForNextSlot ... JSON RPC error: Method not enabled, engine_forkchoiceUpdatedV5
Req produceBlockV4 error - JSON RPC error: Method not enabled, engine_forkchoiceUpdatedV5
```

Runtime evidence from the repro:
- chain progresses to slot 31, then stalls
- generated CL config has `HEZE_FORK_EPOCH: 1`
- generated Besu chainspec sets `bogotaTime = genesis + 32 * 6s`
- `engine_exchangeCapabilities` includes `engine_forkchoiceUpdatedV5`
- actual `engine_forkchoiceUpdatedV5` call returns `Method not enabled`
- actual `engine_getInclusionListV1` call succeeds

## Branch / image provenance
The running image reports:
- `besu/v26.4-develop-1a6188b/linux-x86_64/openjdk-java-25`

That maps to:
- repo: `besu-eth/besu`
- branch: `focil`
- commit: `1a6188bdfff32c65f39c78de7e0b7707af96de31`

## Root causes in source

### 1) Bogota is not wired into genesis / milestone scheduling
Bogota method enablement depends on `protocolSchedule.milestoneFor(BOGOTA)`, but the branch does not plumb `bogotaTime` into the config/schedule layer.

Relevant files:
- `config/src/main/java/org/hyperledger/besu/config/GenesisConfigOptions.java:311-322`
  - has `getAmsterdamTime()` then jumps to `getFutureEipsTime()`
  - no `getBogotaTime()` accessor
- `config/src/main/java/org/hyperledger/besu/config/JsonGenesisConfigOptions.java:357-368`
  - parses `amsterdamtime`
  - no `bogotatime`
- `ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/milestones/MilestoneDefinitions.java:143-154`
  - registers `AMSTERDAM`
  - then jumps to `FUTURE_EIPS` / `EXPERIMENTAL_EIPS`
  - no `BOGOTA` milestone registration

### 2) FCU V5 is only enabled when `milestoneFor(BOGOTA)` is present
`ExecutionEngineJsonRpcMethods` only registers FCU V5 when Bogota is scheduled:
- `ethereum/api/src/main/java/org/hyperledger/besu/ethereum/api/jsonrpc/methods/ExecutionEngineJsonRpcMethods.java:332-339`

Because Bogota is never scheduled from chainspec, `engine_forkchoiceUpdatedV5` is absent from the enabled method map and real RPC calls fail with `-32604 Method not enabled`.

### 3) `engine_exchangeCapabilities` falsely advertises unsupported methods
`EngineExchangeCapabilities` returns all `RpcMethod` enum entries starting with `engine_`, regardless of whether they were actually registered in `ExecutionEngineJsonRpcMethods`.

Relevant file:
- `ethereum/api/src/main/java/org/hyperledger/besu/ethereum/api/jsonrpc/internal/methods/engine/EngineExchangeCapabilities.java:74-80`

That makes Besu advertise `engine_forkchoiceUpdatedV5` even when the method is not enabled.

### 4) FCU V5 payload building drops `inclusionListTransactions`
Even if FCU V5 were enabled, its payload-build path looks incomplete.

The V5 implementation inherits the V4 flow, which calls `preparePayload(...)` without inclusion-list transactions:
- `ethereum/api/src/main/java/org/hyperledger/besu/ethereum/api/jsonrpc/internal/methods/engine/AbstractEngineForkchoiceUpdatedV4.java:270-280`

By contrast, the older abstract FCU path has the correct overload and passes decoded inclusion-list transactions:
- `ethereum/api/src/main/java/org/hyperledger/besu/ethereum/api/jsonrpc/internal/methods/engine/AbstractEngineForkchoiceUpdated.java:223-232`

So FCU V5 currently validates the presence of `inclusionListTransactions` but does not thread them into payload preparation.

### 5) Method gating is inconsistent across the PR-609 methods
`engine_newPayloadV6` and `engine_getInclusionListV1` are registered under the Amsterdam gate instead of Bogota:
- `ethereum/api/src/main/java/org/hyperledger/besu/ethereum/api/jsonrpc/methods/ExecutionEngineJsonRpcMethods.java:282-329`

That produces a mixed state where some Bogota/FOCIL methods are reachable before Bogota is actually scheduled, while FCU V5 is not.

## Why this breaks Heze support
Lodestar correctly switches to `engine_forkchoiceUpdatedV5` at the Heze/Bogota boundary. Besu claims support for the method in capabilities exchange, but its actual enabled-method map does not include FCU V5 because Bogota scheduling was never wired. The CL therefore selects V5 and the EL rejects it at runtime, halting block production.

## Likely fix set
1. Add `getBogotaTime()` to `GenesisConfigOptions`
2. Parse `bogotatime` in `JsonGenesisConfigOptions`
3. Register `BOGOTA` in `MilestoneDefinitions`
4. Make `engine_exchangeCapabilities` return only actually-enabled engine methods, not all enum values
5. Pass `inclusionListTransactions` through the FCU V5 payload-build path (`preparePayload(..., inclusionListTransactions)`)
6. Re-check whether `engine_newPayloadV6` / `engine_getInclusionListV1` should be gated by Bogota rather than Amsterdam

## Nice-to-have follow-up tests
- dedicated `EngineForkchoiceUpdatedV5` unit/integration tests
- test that capability exchange omits disabled methods
- test a chainspec with `bogotaTime` set and assert FCU V5 is enabled at runtime
- test FCU V5 payload building preserves and uses `inclusionListTransactions`
