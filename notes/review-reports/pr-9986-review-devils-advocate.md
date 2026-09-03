Reviewer: review-devils-advocate
Reviewed commit: 0defe10a6788efe3f580eb31394523faac23cd0f

# Devil's Advocate — PR #9986 "test: fail spec tests expecting an error if none is thrown"

## Overall Assessment

**The premise is correct and the approach is sound.** The runner's `shouldError` branch
ran the test fn in a try/catch and `return`ed on throw, but never asserted a throw actually
happened — so any expected-error vector we *wrongly accepted* passed silently. Adding
`expect.unreachable("Expected test function to throw")` is the minimal, correct fix, and it
did its job: it surfaced 22 real conformance gaps. That is exactly the kind of change that
should exist. The accompanying fixes (state-root gating, same-slot guard, sweep OOB throw)
are each narrowly scoped and spec-justified. I verified each against the specs at
`~/consensus-specs` and against the head-SHA Lodestar source.

I could not find a reason to say RECONSIDER or RETHINK. Below are two design-layer points
worth a sentence in the PR thread, plus explicit confirmation on the three questions posed —
but none rise to a blocking objection.

## Confirmation of the three key questions

**(a) `state.slot < block.slot` in the test runner vs. production `process_slots` — the right layer?**
Test-runner layer is defensible *because production already enforces the equivalent invariant
elsewhere*, so this is not masking a production hole:
- Spec `process_slots` does `assert state.slot < slot`. Lodestar's
  `processSlotsWithTransientCache` only throws on `postState.slot > slot`
  (`stateTransition.ts`), so `state.slot === block.slot` is a silent no-op — the divergence
  the PR describes is real *at the state-transition layer*.
- BUT the real block-import path rejects it upstream: `validation/block.ts:149-153`
  `// [REJECT] The block is from a higher slot than its parent` → `if (parentBlock.slot >= blockSlot) throw`,
  and `verifyBlocksSanityChecks.ts` tracks parent slots. Since the pre-state enters
  `stateTransition` at the parent block's slot, `parentBlock.slot < blockSlot` implies
  `state.slot < blockSlot`. So production as a whole already rejects `invalid_same_slot_block_transition`.
- The sanity spec runner intentionally drives `stateTransition` directly, bypassing gossip
  validation, so a runner-level guard is the pragmatic way to exercise the vector. **Sound.**

**(b) A real `throw` in production `processWithdrawals.ts` for a case "not reachable via valid
state transitions" — justified? Any downside?**
Yes, justified; no meaningful downside. This is a *consensus-conformance* fix, not a test-only
one, and it belongs in production:
- Spec `get_builders_sweep_withdrawals` / `get_validators_sweep_withdrawals` index the first
  access with the raw `next_withdrawal_*_index` and only wrap with `% len` *on advance*. An
  out-of-bounds start index makes `state.builders[builder_index]` raise → spec-compliant
  clients reject. Lodestar's old `(next + n) % len` wrapped from `n === 0`, silently accepting.
  A conformant reject vs. a silent accept on the same input is a consensus-split risk, so
  matching the spec in production (not a test assertion) is the correct layer.
- The guard is `n === 0 && next >= len`, i.e. it fires *only* on the exact input where the spec
  errors. Under valid transitions `nextWithdrawal{Builder,Validator}Index` is always maintained
  `% len` (see the `% stateGloas.builders.length` / `% state.validators.length` updates in the
  same file), so it never fires on healthy states. Cost: one extra branch, checked once per
  sweep. **No downside.**

**(c) `expect.unreachable` vs `await expect(fn()).rejects.toThrow()`?**
`expect.unreachable` (with the existing try/catch) is actually the *more robust* primitive here,
not just an equal one. `testFunction` is typed `Result | Promise<Result>` — it may throw
**synchronously**. `expect(testFunction(...)).rejects.toThrow()` evaluates the call in argument
position, so a synchronous throw escapes before `expect` runs and the test errors instead of
passing. The try/catch wraps both sync and async throws uniformly. Keep it as-is. **Sound.**

## Objections (both minor — CONSIDER, not blocking)

### 1. The sanity guard duplicates spec logic in test code rather than in the transition
`sanity.test.ts` hardcodes `if (signedBlock.message.slot <= wrappedState.slot) throw`. This is
spec logic living in a per-test loop. If Lodestar ever added a state-transition-only consumer
(or a future test suite drives `stateTransition` for same-slot input), the invariant wouldn't
travel with it.
- **Counter-proposal:** assert it inside `stateTransition()` itself — `if (block.slot <= state.slot) throw`
  immediately before `processSlotsWithTransientCache`. This is the block-only entry point, matches
  spec `assert state.slot < slot` exactly, benefits every state-transition test without per-test
  guards, and (unlike tightening shared `processSlots` from `>` to `>=`) does **not** risk breaking
  standalone `processSlots(state, state.slot)` no-op callers (regen / prepareNextSlot).
- **Why I did not escalate:** production block import already rejects this at `validation/block.ts:149`,
  so a `stateTransition` assertion would be defense-in-depth/redundant for real traffic. The
  PR's minimal test-only change is a legitimate call. Worth one line in the PR body noting that
  production coverage exists at the validation layer, so nobody later assumes a real hole.

### 2. `verifyStateRoot: true` is correct, but the old gating deserves a regression note
Flipping `verifyStateRoot: verify` → `verifyStateRoot: true` is right — state-root verification
is `assert block.state_root == hash_tree_root(state)` and is unrelated to `bls_setting`. The old
code gated it on `bls_setting === 1`, so an `invalid_incorrect_state_root` vector with
`bls_setting !== 1` passed silently. Note this is *why* `expect.unreachable` alone was
insufficient: without flipping the flag, Lodestar wouldn't throw and `expect.unreachable` would
(correctly) fail — the two changes are coupled and must land together.
- **Counter-proposal:** none needed for the code. Just add a one-line comment at the flag
  (`// state-root check is independent of bls_setting; always verify`) so a future reader doesn't
  "restore" the gating thinking it was a BLS optimization.

## Verdict: **SOUND**

Correct root-cause fix (silent-pass in the runner), minimal surface, each surfaced vector fixed
at the right layer (consensus fixes in production, test-scoping in the runner), spec-verified.
The two points above are polish for the PR thread, not changes I'd block on.
