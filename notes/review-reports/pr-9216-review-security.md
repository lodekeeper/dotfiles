# Review Findings — review-security — 9216

Reviewer: review-security
Reviewed commit: c20b43554458738457fe5014c466ece010a75311
Generated at: 2026-05-30 17:55 UTC

## Findings

1. **packages/beacon-node/src/chain/opPools/deferredVoluntaryExitPool.ts:40** — **Vulnerability:** CWE-347 / validation bypass: deferred exits are promoted using validity-only rechecks (`verifySignature=false`).

   **Attack vector:** `validateApiVoluntaryExit()` accepts transient exits after a one-time BLS check against the head state at submission. When the epoch listener drains the pool, `retrieveProcessableExits()` treats `state.getVoluntaryExitValidity(entry.exit, false) === valid` as sufficient, and `nodejs.ts` immediately inserts/publishes the exit as prevalidated. This skips rechecking the voluntary-exit signature/domain at the actual publication epoch. On pre-Deneb or custom fork schedules, an `earlyEpoch` exit can be signed so it verifies under the submission fork but is invalid under the future fork where it becomes includable; Lodestar can then gossip and insert it into the op pool as if it were valid, risking invalid block production or poisoning `hasSeenVoluntaryExit` for that validator.

   **Severity:** High

   **Mitigation:** Before moving a deferred exit into `opPool` or publishing it, re-run the full current-state validation including BLS signature verification, or at minimum verify `getVoluntaryExitSignatureSet()` against the current state plus the same fork-domain includability guard used by block production. Drop entries that fail the current signature/domain check.

2. **packages/beacon-node/src/chain/validation/voluntaryExit.ts:21** — **Vulnerability:** CWE-400 uncontrolled resource consumption: deferred-pool duplicates are not rejected before expensive validation.

   **Attack vector:** The API validator only checks `chain.opPool.hasSeenVoluntaryExit()` before fetching/regenerating state and running prioritized BLS verification. A transient exit already stored in `deferredVoluntaryExitPool` is not in `opPool`, so the same signed payload can be resubmitted repeatedly; each duplicate reaches the expensive signature verification path and is rejected only later when `deferredVoluntaryExitPool.insert()` sees the duplicate. A client that can reach the Beacon REST API and has any currently-transient signed exit can use this as a CPU amplification path until the entry expires or becomes valid.

   **Severity:** Medium

   **Mitigation:** Add a cheap `has()`/`hasSeenVoluntaryExit()` check on `DeferredVoluntaryExitPool` and perform it in `validateApiVoluntaryExit()` before state regeneration and BLS verification, returning the same duplicate/ignore behavior used for `opPool` entries. Consider rate-limiting repeated failed inserts as defense in depth.
