# PR #8837 Architecture Review

Reviewer: reviewer-architect

Reviewed commit: 8066f6ba70496be6d7e1ac4cd80c7731ba7b1d04

## Findings

### 1. Fork-choice now reaches through a full state-transition state view

**Scope** — `packages/fork-choice/src/forkChoice/fastConfirmation/types.ts`, `packages/fork-choice/src/forkChoice/fastConfirmation/utils.ts`, `packages/beacon-node/src/chain/chain.ts`, `packages/state-transition/src/stateView/interface.ts`, `packages/state-transition/src/stateView/beaconStateView.ts`

**Issue** — Fast confirmation is fork-choice-adjacent in the spec, so `@lodestar/fork-choice` is a reasonable home for the rule orchestration. The implementation, however, makes fork-choice consume `IBeaconStateView` directly through a new `ForkChoiceStateGetter`, then calls state-view operations such as `processSlots()`, committee lookup, shuffling access, validator access, and balance extraction inside `packages/fork-choice`. Beacon-node wires this by passing state-cache lookups into fork-choice, and state-transition's state view is widened to satisfy these fork-choice calls. This deepens an upward dependency from `@lodestar/fork-choice` into `@lodestar/state-transition` and beacon-node state-cache semantics, instead of keeping fork-choice behind its block DAG/vote-store abstraction.

**Impact** — Fork-choice becomes coupled to the full BeaconStateView surface and to the lifetime/availability behavior of beacon-node's state caches. That makes the fork-choice package harder to reason about or reuse independently, and future state-view or cache changes can break fast confirmation even when the fork-choice DAG and vote data contracts remain valid. The widened state-view interface also makes state-transition abstractions carry methods primarily introduced for a higher-level fork-choice feature.

**Recommendation** — Keep the fast-confirmation store/rule orchestration in fork-choice, but move state-derived calculations behind a narrow adapter boundary. For example, have beacon-node or state-transition provide primitive balance, active-validator, and committee data through explicit callbacks or a small provider interface, without exposing `IBeaconStateView` or `processSlots()` to fork-choice. If the spec helpers need state-transition primitives, place those helpers in `@lodestar/state-transition` and let fork-choice consume only the resulting plain data needed for the FCR decision.

### 2. Optional fast-confirmation state is merged into the core fork-choice store contract

**Scope** — `packages/fork-choice/src/forkChoice/store.ts`, `packages/fork-choice/src/forkChoice/fastConfirmation/types.ts`, `packages/fork-choice/src/index.ts`

**Issue** — `IForkChoiceStore` now extends `IFastConfirmationStore`, `ForkChoiceStore` requires a `stateGetter` constructor argument, and all fast-confirmation fields are initialized on every store even though `fastConfirmation` is an optional, hidden chain feature. The package root also exports several FCR internals (`FCRBalanceSource`, `FCRContext`, `IFCRStore`, etc.), making an experimental rule's implementation shape part of the broader fork-choice package contract.

**Impact** — All fork-choice consumers, mocks, tests, and alternative store constructions must now model fast-confirmation fields even when the feature is disabled. This raises coupling across the core fork-choice abstraction and makes future changes to FCR storage or state access more likely to become breaking changes for unrelated fork-choice users.

**Recommendation** — Compose fast-confirmation state as a separate `FastConfirmationStore` owned by `ForkChoice` only when the feature is enabled, initialized from the existing fork-choice store at construction time. Keep `IForkChoiceStore` focused on canonical fork-choice state, expose only stable public methods such as `getConfirmedRoot()` and `getConfirmedBlock()`, and avoid root-level exports of FCR implementation internals unless they are explicitly intended as a supported API.

## Reviewed Non-Findings

- `packages/validator/src/util/params.ts` only adds a config key to the validator's spec-critical parameter comparison. It does not import beacon-node internals or violate the validator/beacon-node REST boundary.
- The new endpoint is placed under `packages/api/src/beacon/routes/lodestar.ts` and implemented in `packages/beacon-node/src/api/impl/lodestar/index.ts`, which matches Lodestar's custom API route pattern for non-standard endpoints.
