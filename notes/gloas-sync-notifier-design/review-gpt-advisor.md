# Verdict
The draft is directionally right and much closer to the abstraction Nico asked for. Keeping `exec-block:` as the stable operator-facing row, adding a separate Gloas-only `payload:` row, and dropping `prev-payload:` is the correct overall shape.

That said, I would not treat this as fully implementation-ready yet. The doc still leaves two important semantics under-specified:
1. the exact operator meaning and transition point of `payload: pending` vs `payload: empty`
2. the exact source and status contract of `exec-block:` for Gloas `PENDING` / `EMPTY` heads

So: approve the direction, but tighten the spec before coding against it.

# Strongest parts
- The core reframing is correct: the notifier should answer operator questions, not expose fork-choice bookkeeping. That directly addresses Nico's feedback.
- Preserving `exec-block:` as the cross-fork anchor row is the best continuity story. Operators already read that field as “what execution block this head is building on / what the next block will build on,” and the draft keeps that mental model intact.
- Splitting out a separate `payload:` row for the current head lifecycle is a good way to expose the genuinely new Gloas signal without overloading `exec-block:`.
- Rejecting `prev-payload:` is the right call. It is noisy, leaks internal FULL/EMPTY/PENDING distinctions, and would make the log harder to reason about in exactly the cases where operators most need clarity.
- The proposed code shape is reasonably contained. Keeping the change centered in `notifier.ts` reduces blast radius and makes the design feel pragmatic rather than theoretical.

# Weakest parts / risks
- The `pending` vs `empty` distinction is still too fuzzy in the doc. Right now `PENDING` is “payload not yet revealed” and `EMPTY` is “payload not revealed / not present,” which is too overlapping to be a reliable user-facing contract. An operator needs to know exactly when a head is still waiting for reveal versus when the slot is definitively a missed/empty outcome.
- The examples assume `exec-block: valid(...)` for Gloas `PENDING` / `EMPTY`, but the doc does not clearly define where that status comes from in those cases. The hash anchor may be known from `parent_block_hash`, but “valid” is a stronger claim than “known parent hash.” If the status is inherited, resolved via fork-choice, or may sometimes be unavailable, the doc should say that explicitly.
- The draft is stronger on hashes than on fallback behavior. It does not specify what happens if the anchor hash is known but the number is not yet resolved, or if parent resolution fails during reorgy / partial-information situations. A notifier spec should define deterministic degraded output, not just the happy path.
- `exec-block:` is described as both “what the current head is anchored to” and “what the next block will build on.” Those are aligned in the intended cases, but the design should pick one canonical wording and use it consistently so later code/comments do not drift.
- The FULL-case duplication is probably acceptable for v1, but the doc still treats it as a bit hand-wavy. If duplication is intentional, say that clearly and frame it as a deliberate semantic redundancy, not just something that happens to be tolerated.
- The test plan is too string-output-centric. It should cover semantic edge cases, not just presence of rows.

# Suggested changes to the design doc
1. Add a small semantics table that explicitly defines, for each head type, all three things:
   - what `exec-block:` represents
   - how its hash/number/status are sourced
   - what `payload:` should print

   At minimum cover:
   - pre-Gloas
   - Gloas FULL
   - Gloas PENDING
   - Gloas EMPTY
   - unresolved / degraded lookup case

2. Tighten the `payload:` lifecycle definitions. The doc should explicitly say when a head moves from `pending` to `empty`, in operator terms, not just internal enum terms. If `empty` means the reveal window is over and no payload will arrive, say that. If it means something narrower, say that instead.

3. Define the `exec-block:` status contract for Gloas non-FULL heads. If the notifier can only guarantee the anchor hash/number but not independently assert `valid`, avoid examples that hardcode `valid(...)`. Either:
   - define exactly how status is inherited/resolved, or
   - define a degraded/unknown form and use that in the spec

4. Specify fallback behavior when anchor resolution is partial or fails. For example: if hash is known but number is unavailable, should the notifier print hash-only, `unknown`, or suppress the row? This should be specified explicitly so implementations do not improvise.

5. Promote the FULL-case duplication decision from “open question” to a concrete recommendation. My suggestion is: keep `payload: full(...)` in the first version for semantic consistency, and revisit terseness later only if operators find the output too noisy.

6. Expand the test plan with semantic edge cases, especially:
   - transition from `pending` to `empty`
   - reorgs around payload reveal
   - partial resolution / unknown number or status
   - confirmation that no user-visible row depends on exposing FULL/EMPTY/PENDING parent resolution details

7. Tighten wording around the canonical meaning of `exec-block:`. I would recommend one sentence used everywhere, e.g.:
   > `exec-block:` is the execution block the current head is anchored to, i.e. the execution parent the next block will build on.

# Final recommendation
I would recommend proceeding with the Option B direction, but not merging the design unchanged. The big architectural call is correct: keep `exec-block:` stable, add `payload:` for current-head lifecycle, and delete `prev-payload:` entirely.

Before implementation, tighten the doc so it is a real semantic spec rather than a good intuition piece. In practice that means nailing down:
- the exact `pending` vs `empty` contract
- the exact status/source/fallback rules for `exec-block:` in Gloas non-FULL cases
- the intended behavior for degraded lookup / reorg edge cases

Once those are explicit, this design should be a solid and reviewable basis for PR #19.