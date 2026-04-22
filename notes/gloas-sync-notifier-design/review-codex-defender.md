# Defender verdict
The converged design is coherent and implementation-ready. It preserves one operator-facing invariant for `exec-block:`, exposes only the genuinely new Gloas signal via `payload: pending|empty`, and degrades honestly with `exec-block: unresolved(<hash>)` instead of inventing certainty. I would defend this design against the earlier `prev-payload:` direction.

# Strongest arguments for the design
- It answers the operator question, not the fork-choice bookkeeping question: `exec-block:` = what the node would currently build on next.
- It keeps the normal path compact again: FULL emits only `exec-block:`, so the happy path looks like pre-Gloas instead of duplicating the same fact twice.
- It exposes real new Gloas information without leaking parent-variant internals: `payload:` only appears for the current head's exceptional states.
- The fallback is trustworthy. `unresolved(<hash>)` makes partial resolution explicit and parser-visible.
- It is small-patchable in the current code: `notifier.ts` already has the `getHeadExecutionInfo()` seam, and `IForkChoice` already exposes anchor-resolution primitives, so this does not require a wider architecture change.

# Remaining weak spots
- The doc must stay absolute that FULL emits no `payload:` row by default; any lingering optional wording reintroduces ambiguity.
- `payload: empty` should remain observational and should not over-claim diagnosis beyond “current head resolved to the no-payload outcome.”
- The atomic snapshot rule should be implemented concretely, not just described abstractly, so `exec-block:` and `payload:` cannot come from different head views.

# Any final refinements before implementation
- Keep the degraded fallback explicit as `exec-block: unresolved(<hash>)`; do not silently change row shape.
- Add a targeted test for same-head `PENDING -> FULL` transition behavior so a changed `exec-block:` with unchanged `head:` is documented and intentional.
- In code comments and PR reply, use the single canonical sentence: `exec-block:` is the execution block the node would currently build on for the next block.

# Is it ready to implement?
Yes. With the cleanup-level contradictions removed from the design doc, this is ready to drive the PR reply and a small notifier implementation patch.
