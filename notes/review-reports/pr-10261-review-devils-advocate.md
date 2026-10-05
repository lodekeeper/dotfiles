# PR #10261 — Devil's Advocate Review

Reviewer: review-devils-advocate
Reviewed commit: 6d790d2845a530be1b96bac0eb5fa8a66b784b67

PR: ChainSafe/lodestar#10261 "fix: honor group validator statuses when filtering by ids" (external, b0a7, Cursor-assisted, +153/−7, no linked issue, CI not yet run)

## Devil's Advocate Review

### Overall Assessment
The approach is sound: this is a real, current, severe interop bug. The fix is the same predicate Lighthouse uses. My objections only concern trimming and keeping one source of truth, and none of them blocks the merge.

### Premise check (I tried to kill the PR and couldn't)

**Necessity: confirmed, and worse than the PR body says.**
- Nimbus VC v26.10.0 (`beacon_chain/validator_client/api.nim:1509-1512`) looks up indices with
  `RestValidatorRequest(ids: Opt.some(id), status: Opt.some({ActiveOngoing, ActiveExiting, ActiveSlashed}))`.
- Nimbus's `toList` (`beacon_chain/spec/eth2_apis/rest_types.nim:1486+`) compresses a complete group to its group name (`processSet(activeSet, "active")`). So the wire request really is `statuses: ["active"]` plus ids.
- On unstable, Lodestar's ids path compares only against the fine-grained status. It returns `200 []` for **every** validator.
- Result: Nimbus VC never resolves any index, `needsUpdate()` stays true forever, and **every validator on a Nimbus v26.10.0 VC → Lodestar BN setup misses every duty**. Nimbus logs this only at INF (`pending=N`).
- Background: Nimbus moved to this filter to fix status-im/nimbus-eth2#9176 (filed 2026-10-02). v26.8–v26.9.1 sent `{ActiveOngoing}` → `"active_ongoing"`, which happened to work on Lodestar. The trigger is a few days old and live.
- If we don't merge, Lodestar is the client that breaks a spec-compliant VC.

**Spec:** beacon-APIs `getStateValidators`/`postStateValidators` define status items as `oneOf: [ValidatorStatus, enum ["active","pending","exited","withdrawal"]]`. Group filters are explicitly valid. The lead already verified this and I agree.

**Cross-client precedent:** the PR matches it exactly.
- **Lighthouse** (`beacon_node/http_api/src/validators.rs:55-59`) runs one pipeline for ids and statuses with `statuses.contains(&status) || statuses.contains(&status.superstatus())`. `statusMatches` is a line-for-line port of this.
- **Nimbus BN** expands groups at parse time (`ValidatorFilter.parse("active")` → the 3-member set).
- Either design works. The PR picked the battle-tested one that needs the least code, and it adds no per-fork branching.

**Simpler alternative?** The functional fix is already 1 line (`index.ts:103`). The type widening (`state.ts:48`, `198/200/215/217`) is required: without it, `statuses.includes(mapToGeneralStatus(...))` fails type-check. It is also spec-correct for `@lodestar/api` client consumers. It is type-level only, because the server schema is `Schema.StringArray`. No fundamentally simpler path exists.

**Contributor signals:**
- AI assistance is disclosed. The PR body's root-cause claim is accurate: I verified it against Nimbus source, and it is not hallucinated.
- Scope is tight: no drive-by changes, 2 commits, the second only fixes test typings.
- Missing linked issue: minor, since the PR body carries the repro.
- Blocker before merge: CI (tests/lint/types) has not run because workflows await approval.

### Objections (max 3)

#### 1. 🟡 should-fix (or ack): `statusMatches` becomes a third copy of the group-match predicate, not the single source of truth
- **Location:** `packages/types/src/utils/validatorStatus.ts:96-97` (and caller `packages/beacon-node/src/api/impl/beacon/state/index.ts:103`)
- **Challenge:** The root cause is not "the ids path forgot groups". The validator-status filter is implemented independently per code path, and the copies drifted.
  - Before: JS `BeaconStateView.getValidatorsByStatus` had it inline (`statuses.has(s) || statuses.has(mapToGeneralStatus(s))`), the ids path didn't, and the native Zig binding is opaque.
  - After: the PR adds a new **public** export to `@lodestar/types` (re-exported via `export * from "./utils/validatorStatus.js"`) with **one** call site. The existing inline copy stays untouched.
  - So the predicate now exists 2× in JS, plus 1× in the native binding, whose group handling I could not verify: the binding ships compiled, only `bindings/src/index.d.ts` is visible.
- **Evidence:** `git grep mapToGeneralStatus refs/review/pr-10261` → `beaconStateView.ts:650` (inline copy) + `validatorStatus.ts:97` (new helper). `statusMatches` also takes `readonly string[]`, not `ValidatorStatusFilter[]`. That is looser than the type the same PR introduces.
- **Counter-proposal (pick one):**
  - **(a) Minimal, no new public API:** drop `statusMatches` and its 34-line types test, and inline at `index.ts:103`, mirroring the existing idiom:
    ```ts
    const status = getValidatorStatus(validator, currentEpoch);
    if (statuses.length && !statuses.includes(status) && !statuses.includes(mapToGeneralStatus(status))) {
      continue;
    }
    ```
  - **(b) Keep the helper and make it real:** keep it, but have the maintainer follow up so that `BeaconStateView.getValidatorsByStatus` calls `statusMatches` too. Also confirm that native `getValidatorsByStatus` honors group statuses; otherwise the statuses-only path breaks once the native state view is enabled.
  - I lean to (b) as a maintainer follow-up: it fixes the real root cause. Accepting the PR as-is is fine if someone owns the follow-up.
- **Impact if ignored:** low today. The next filter change (e.g. a new status or a builder-status group) has to be made in 2–3 places, which is the same class of drift that caused this bug.

#### 2. 🟢 nit: the beacon-node test duplicates types-level coverage through a fragile overlay mock
- **Location:** `packages/beacon-node/test/unit/api/impl/beacon/state/getStateValidators.test.ts:68-96`
- **Challenge:** The regression is "the ids path ignores group statuses". Tests at `:35` (`["active"]` matches) and `:58` (`["pending"]` excludes) pin that.
  - Case `:68` spies on `state.getValidator` and spreads field overlays to synthesize pending, exited and withdrawal validators. That re-tests `getValidatorStatus`/`mapToGeneralStatus` group membership, which `validatorStatus.test.ts:107+` already covers exhaustively for all 9 sub-statuses.
  - It also couples to the implementation detail that the ids path reads validators via `getValidator`. Switching to a bulk or native accessor would break the test without any behaviour change.
- **Counter-proposal:** keep `:35`, `:47` and `:58` (about 45 lines), drop `:68-96`. If extra confidence is wanted, add one assertion that mixes ids with `["active", "pending"]`.
- **Impact if ignored:** about 30 lines of extra mock-heavy test surface that adds no regression protection. Not worth blocking on.

_No third objection. The `ValidatorStatusFilter` type widening is spec-mandated and correct, and there is no spec-churn or fork-forward risk: validator statuses are fork-agnostic, and builder statuses are a separate type and path._

### Verdict
**SOUND**: no fundamental issues. The premise is verified against Nimbus v26.10.0 source, and the predicate matches Lighthouse. Objections 1–2 are trims or follow-ups, not blockers.

**MERGE** (once external-contributor CI is approved and green). Reasons:
1. The bug is real and severe. Nimbus VC v26.10.0 sends `["active"]` + ids (verified in `api.nim:1509` and `rest_types.nim` `toList`), so every validator on a Nimbus VC → Lodestar BN setup misses all duties today.
2. The spec explicitly allows group filters, and the fix is a 1-line port of Lighthouse's `contains(status) || contains(superstatus)`. There is no simpler or more battle-tested alternative.
3. Scope is tight and the PR description is accurate. The only maintenance cost is a small public helper; optionally inline it, or adopt it in `BeaconStateView.getValidatorsByStatus` as a follow-up.
