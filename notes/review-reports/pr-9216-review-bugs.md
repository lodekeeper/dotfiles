# Review Findings — review-bugs — 9216

Reviewer: review-bugs
Reviewed commit: c20b43554458738457fe5014c466ece010a75311
Generated at: 2026-05-30 17:37 UTC

Reviewer: review-bugs
Reviewed commit: c20b43554458738457fe5014c466ece010a75311

# Findings

1. **packages/beacon-node/src/chain/validation/voluntaryExit.ts:29** — exact location

   **Bug** — `validateApiVoluntaryExit` rejects every exit whose `validatorIndex` is at least `state.validatorCount` before calling the fork-aware `state.getVoluntaryExitValidity`. Gloas builder voluntary exits encode builder indexes by setting `BUILDER_INDEX_FLAG` via `convertBuilderIndexToValidatorIndex`, so their `validatorIndex` is always far above the validator registry length even when the builder exists.

   **Impact** — On Gloas, valid builder voluntary exits submitted through the beacon pool API are rejected as `INACTIVE` and never reach the op pool, deferred pool, or gossip publication path. This regresses the previous `validateVoluntaryExit` path, which let `getVoluntaryExitValidity` classify builder exits before checking validator length.

   **Fix** — Remove this precheck and let `state.getVoluntaryExitValidity` perform the fork-aware validator/builder lookup, or skip the `validatorCount` rejection for Gloas builder-index exits and validate those through the builder path.
