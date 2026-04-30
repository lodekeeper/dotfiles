# Besu focil / Heze patch sketch (PR-609 / Bogota enablement)

This follows the repro + root-cause note in `notes/besu-focil-pr609-heze-bugreport-2026-04-29.md` and focuses on the smallest code changes that should make the branch behave correctly.

## Goal
Make Besu `focil` correctly support Heze/Bogota engine methods by:
1. plumbing `bogotaTime` into the protocol schedule
2. only advertising engine methods that are actually enabled
3. threading `inclusionListTransactions` into FCU V5 payload preparation
4. cleaning up inconsistent Amsterdam-vs-Bogota method gating

---

## Patch 1 — wire `bogotaTime` into config + milestone scheduling

### Files
- `config/src/main/java/org/hyperledger/besu/config/GenesisConfigOptions.java`
- `config/src/main/java/org/hyperledger/besu/config/JsonGenesisConfigOptions.java`
- `config/src/main/java/org/hyperledger/besu/config/StubGenesisConfigOptions.java`
- `ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/milestones/MilestoneDefinitions.java`
- tests:
  - `config/src/test/java/org/hyperledger/besu/config/GenesisConfigOptionsTest.java`
  - any schedule-builder tests that assert milestone ordering

### Intended change
Add Bogota exactly the same way Amsterdam is already handled.

### Concrete sketch

#### `GenesisConfigOptions.java`
Add:
```java
OptionalLong getBogotaTime();
```
right after `getAmsterdamTime()`.

#### `JsonGenesisConfigOptions.java`
Add:
```java
@Override
public OptionalLong getBogotaTime() {
  return getOptionalLong("bogotatime");
}
```

Also include it anywhere config values are serialized back out (same pattern as `amsterdamTime`).

#### `StubGenesisConfigOptions.java`
Add:
- field: `private OptionalLong bogotaTime = OptionalLong.empty();`
- getter: `getBogotaTime()`
- builder helper:
```java
public StubGenesisConfigOptions bogotaTime(final long timestamp) {
  bogotaTime = OptionalLong.of(timestamp);
  return this;
}
```
- serialization to the builder map, matching Amsterdam/BPO style

#### `MilestoneDefinitions.java`
Register Bogota after Amsterdam:
```java
createTimestampMilestone(
    MainnetHardforkId.BOGOTA,
    config.getBogotaTime(),
    specFactory::bogotaDefinition),
```

### Expected effect
After this patch, a chainspec with `bogotaTime` should make `protocolSchedule.milestoneFor(BOGOTA)` present, which in turn enables FCU V5 the same way the code already expects.

---

## Patch 2 — advertise only actually-enabled engine methods

### Problem
`EngineExchangeCapabilities` currently returns all `RpcMethod` enum members starting with `engine_`, regardless of whether they were registered in the current `ExecutionEngineJsonRpcMethods` instance.

That violates the spirit of `engine_exchangeCapabilities` and is the direct reason Besu lies about supporting `engine_forkchoiceUpdatedV5` in the failing repro.

### Files
- `ethereum/api/src/main/java/org/hyperledger/besu/ethereum/api/jsonrpc/internal/methods/engine/EngineExchangeCapabilities.java`
- `ethereum/api/src/main/java/org/hyperledger/besu/ethereum/api/jsonrpc/methods/ExecutionEngineJsonRpcMethods.java`
- tests:
  - `ethereum/api/src/test/java/org/hyperledger/besu/ethereum/api/jsonrpc/internal/methods/engine/EngineExchangeCapabilitiesTest.java`
  - `ethereum/api/src/test/java/org/hyperledger/besu/ethereum/api/jsonrpc/methods/ExecutionEngineJsonRpcMethodsTest.java`

### Intended change
Pass the enabled engine-method list into `EngineExchangeCapabilities`, instead of deriving it from the enum.

### Concrete sketch

#### `EngineExchangeCapabilities.java`
Change constructor to accept a supplier or list:
```java
private final Supplier<List<String>> localCapabilitiesSupplier;

public EngineExchangeCapabilities(
    final Vertx vertx,
    final ProtocolContext protocolContext,
    final EngineCallListener engineCallListener,
    final Supplier<List<String>> localCapabilitiesSupplier) {
  super(vertx, protocolContext, engineCallListener);
  this.localCapabilitiesSupplier = localCapabilitiesSupplier;
}
```

Then in `syncResponse()`:
```java
final List<String> localCapabilities = localCapabilitiesSupplier.get();
return respondWith(reqId, localCapabilities);
```

#### `ExecutionEngineJsonRpcMethods.java`
Instead of constructing `EngineExchangeCapabilities` up front from the enum universe, build the actual method list first and then add `EngineExchangeCapabilities` using that same list.

Sketch:
```java
List<JsonRpcMethod> executionEngineApisSupported = new ArrayList<>();

// add normal engine methods first ...

executionEngineApisSupported.add(
    new EngineExchangeCapabilities(
        consensusEngineServer,
        protocolContext,
        engineQosTimer,
        () -> executionEngineApisSupported.stream()
              .map(JsonRpcMethod::getName)
              .filter(name -> name.startsWith("engine_"))
              .filter(name -> !name.equals(RpcMethod.ENGINE_EXCHANGE_CAPABILITIES.getMethodName()))
              .filter(name -> !name.equals(RpcMethod.ENGINE_PREPARE_PAYLOAD_DEBUG.getMethodName()))
              .toList()));
```

This keeps capability exchange aligned with the real enabled method map.

### Expected effect
If Bogota is absent, `engine_forkchoiceUpdatedV5` is neither enabled nor advertised.
If Bogota is present, it is both enabled and advertised.

---

## Patch 3 — thread inclusion-list txs through FCU V5 payload preparation

### Problem
`EngineForkchoiceUpdatedV5` validates `inclusionListTransactions`, but the inherited V4 payload-build path calls:
```java
preparePayload(..., parentBeaconBlockRoot, slotNumber)
```
without the inclusion-list transaction argument.

That means the method can be enabled yet still fail to honor PR-609 semantics during payload building.

### Files
- `ethereum/api/src/main/java/org/hyperledger/besu/ethereum/api/jsonrpc/internal/methods/engine/AbstractEngineForkchoiceUpdatedV4.java`
- optionally `EngineForkchoiceUpdatedV5.java` if you want the override localized there
- tests:
  - existing/new FCU V5 tests
  - possibly extend `InclusionListWorkflowIntegrationTest`

### Intended change
Use the `preparePayload(..., inclusionListTransactions)` overload in the V4/V5 abstract path when the payload attributes include them.

### Concrete sketch
The easiest minimally-invasive change is to reuse the same helper already present in `AbstractEngineForkchoiceUpdated`:
```java
validateAndDecodeInclusionListTransactions(payloadAttributes.getInclusionListTransactions())
```

Then swap:
```java
mergeCoordinator.preparePayload(
    newHead,
    payloadAttributes.getTimestamp(),
    payloadAttributes.getPrevRandao(),
    payloadAttributes.getSuggestedFeeRecipient(),
    finalWithdrawals,
    Optional.ofNullable(payloadAttributes.getParentBeaconBlockRoot()),
    Optional.ofNullable(payloadAttributes.getSlotNumber()))
```
for:
```java
mergeCoordinator.preparePayload(
    newHead,
    payloadAttributes.getTimestamp(),
    payloadAttributes.getPrevRandao(),
    payloadAttributes.getSuggestedFeeRecipient(),
    finalWithdrawals,
    Optional.ofNullable(payloadAttributes.getParentBeaconBlockRoot()),
    Optional.ofNullable(payloadAttributes.getSlotNumber()),
    validateAndDecodeInclusionListTransactions(
        payloadAttributes.getInclusionListTransactions()))
```

If `AbstractEngineForkchoiceUpdatedV4` does not currently expose that helper, either:
- move the helper upward into a shared base/helper utility, or
- duplicate a small decode helper locally (less elegant, but smaller diff)

### Expected effect
FCU V5 will no longer just validate IL presence; it will actually pass the IL txs into `MergeCoordinator.preparePayload(...)`, where Besu already knows how to build the minimal block and the better async block using those transactions.

---

## Patch 4 — fix inconsistent method gating

### Problem
Current gating is mixed:
- `engine_newPayloadV6` and `engine_getInclusionListV1` are under the Amsterdam gate
- `engine_forkchoiceUpdatedV5` is under the Bogota gate

That leaves Besu in a weird partially-Bogota state.

### Files
- `ethereum/api/src/main/java/org/hyperledger/besu/ethereum/api/jsonrpc/methods/ExecutionEngineJsonRpcMethods.java`

### Intended change
Decide whether PR-609 methods should be fully Bogota-gated, and make the registration consistent.

### Conservative recommendation
Move these under the Bogota gate together:
- `EngineForkchoiceUpdatedV5`
- `EngineNewPayloadV6`
- `EngineGetInclusionListV1`

Potentially also review whether any Amsterdam-gated method must reject at runtime post-Bogota only (that part is already partially handled by fork-validation logic).

### Concrete shape
Keep Amsterdam-gated methods for Amsterdam-only functionality, then add a separate Bogota block for the PR-609/Bogota additions.

---

## Suggested test updates

### 1) Config parsing test
In `GenesisConfigOptionsTest` add:
```java
@Test
void shouldGetBogotaTime() {
  final GenesisConfigOptions config = fromConfigOptions(singletonMap("bogotaTime", 1670470144));
  assertThat(config.getBogotaTime()).hasValue(1670470144);
}
```

### 2) Capability exchange test
Add a test where `ExecutionEngineJsonRpcMethods` is created with:
- Amsterdam present
- Bogota absent

Then assert:
- `engine_getInclusionListV1` / `engine_newPayloadV6` behavior matches the intended gate
- `engine_forkchoiceUpdatedV5` is absent from the actual engine-method map
- `engine_exchangeCapabilities` also omits it

### 3) FCU V5 IL passthrough test
Add/extend a test that:
- constructs payload attributes with `inclusionListTransactions`
- invokes FCU V5
- verifies `mergeCoordinator.preparePayload(..., inclusionListTransactions)` is called with the decoded tx list

### 4) End-to-end schedule test
Create a protocol schedule with `bogotaTime` set and assert:
- `milestoneFor(BOGOTA)` is present
- FCU V5 becomes enabled
- capability exchange includes FCU V5 only in that scheduled case

---

## Minimal implementation order
If someone wants the least risky sequence:

1. **Patch 1** — `bogotaTime` plumbing
2. **Patch 2** — truthful capability exchange
3. **Patch 3** — FCU V5 IL passthrough
4. **Patch 4** — gating cleanup
5. tests last (or alongside each step)

That order gets the runtime failure fixed first, then the semantic correctness tightened.

---

## My read on severity
This is a real interop blocker, not just cleanup:
- it breaks Heze/Bogota devnets at the boundary
- it violates capability-exchange expectations
- and it leaves FCU V5 semantically incomplete even once enabled
