# Review Findings - reviewer-architect - PR 9216

Reviewer: reviewer-architect
Reviewed commit: c20b43554458738457fe5014c466ece010a75311

## Findings

### 1. Beacon-node deferral policy is exported from state-transition

**Scope** - `packages/state-transition/src/block/processVoluntaryExit.ts`, `packages/state-transition/src/index.ts`; consumed by `packages/beacon-node/src/chain/validation/voluntaryExit.ts` and `packages/beacon-node/src/chain/opPools/deferredVoluntaryExitPool.ts`.

**Issue** - `isTransientExitValidity()` and `TRANSIENT_EXIT_VALIDITY` encode deferred-publication and operation-pool policy in `@lodestar/state-transition`. The helper is pure, but it is not a consensus spec function; it answers a beacon-node operational question: which validation failures may become valid later without user action.

**Impact** - This expands the state-transition package around consumer policy rather than spec-aligned transition logic. Future fork changes or API deferral-policy changes would require state-transition edits, making it harder to distinguish consensus validation from Lodestar-specific mempool strategy.

**Recommendation** - Keep `VoluntaryExitValidity` and `getVoluntaryExitValidity()` in state-transition, but move transient classification to the beacon-node validation/op-pool domain, for example `chain/validation/voluntaryExit.ts` or a dedicated deferred-exit policy helper. State-transition should expose spec-aligned validity reasons, while beacon-node decides how to act on them.

### 2. Deferred-exit epoch workflow is implemented inside node assembly

**Scope** - `packages/beacon-node/src/node/nodejs.ts`, `packages/beacon-node/src/chain/interface.ts`, `packages/beacon-node/src/chain/chain.ts`.

**Issue** - `BeaconNode.init()` now registers a clock listener that fetches head state, drains the deferred pool, mutates `opPool`, emits API events, publishes gossip, and logs per-exit outcomes. That places voluntary-exit domain workflow in the node composition layer and imports `routes`, `RegenCaller`, and `ClockEvent` into `nodejs.ts` for operation processing. The public `IBeaconChain` interface also exposes the concrete `DeferredVoluntaryExitPool`, so external layers coordinate the pool internals directly.

**Impact** - This couples startup wiring to chain/network operation semantics and makes the deferral lifecycle harder to test, close, and evolve independently. If more deferred or epoch-driven operation flows are added, `nodejs.ts` risks becoming a business-logic hub instead of a module assembly point.

**Recommendation** - Encapsulate the workflow in a dedicated beacon-node component, such as `DeferredVoluntaryExitPublisher`, with explicit dependencies on `chain`, `network`, `clock`, `logger`, and shutdown signal. Alternatively, hide pool draining behind an `IBeaconChain` method and keep only network publication in a network-facing processor. `nodejs.ts` should instantiate and wire the component, not implement the workflow inline.

### 3. API and gossip validation split into duplicated consensus validation paths

**Scope** - `packages/beacon-node/src/chain/validation/voluntaryExit.ts`, invoked from `packages/beacon-node/src/api/impl/beacon/pool/index.ts`.

**Issue** - `validateApiVoluntaryExit()` no longer shares `validateVoluntaryExit()`. It reimplements seen-cache checks, head-state selection, `getVoluntaryExitValidity()`, error mapping, and BLS verification so it can return a deferred result. This creates parallel validation algorithms with different return contracts instead of one shared validation primitive plus caller-specific policy.

**Impact** - Consensus-adjacent voluntary-exit validation can drift between API submission and gossip validation as fork logic changes. The new deferral behavior becomes entangled with core validation steps, increasing maintenance risk across two entry points that should remain aligned.

**Recommendation** - Factor a shared core helper that performs the common validation work and returns structured validation data, such as the computed `VoluntaryExitValidity` and verified signature result. Let gossip map non-valid results to `GossipAction.REJECT`, while API maps transient validity to deferral. This keeps one source for voluntary-exit validation flow while allowing API-specific deferral policy.
