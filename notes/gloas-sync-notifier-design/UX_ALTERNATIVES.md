# Gloas Notifier UX Alternatives

Last updated: 2026-04-22 UTC

## Context

Semantics are already constrained:
- `exec-block:` should reflect what the node would currently build on next
- notifier should not leak fork-choice-internal parent-variant bookkeeping as a separate user-facing concept
- the remaining open question is purely display/UX: what is the clearest operator-facing way to make repeated execution hashes understandable across Gloas FULL/EMPTY scenarios?

## Baseline current converged design

- `exec-block:` always shown
- `payload:` shown only for exceptional states:
  - `payload: pending`
  - `payload: empty`
- no `payload:` row in FULL happy path
- degraded fallback: `exec-block: unresolved(<hash>)`

### UX strengths
- compact happy path
- preserves legacy `exec-block` feel
- only adds extra noise when something exceptional happens

### UX weakness
- when `exec-block` repeats across slots, the reason may still be implicit unless the non-FULL head also emits `payload: empty`

## Alternative A — Status suffix on exec-block only

Example:
- `exec-block: valid(123 0xabc...)`
- `exec-block: valid(123 0xabc...) [payload=pending]`
- `exec-block: valid(123 0xabc...) [payload=empty]`

### Pros
- one execution row only
- no separate payload line/segment to visually correlate

### Cons
- overloads `exec-block:` with two concepts again
- noisier formatting in the common path if suffix handling drifts
- easier to accidentally let implementation details leak in brackets

## Alternative B — Parent/build-target first, explicit carry-forward annotation

Example:
- `exec-block: valid(123 0xabc...)`
- `exec-block: valid(123 0xabc...) - carried(empty)`
- `exec-block: valid(123 0xabc...) - carried(pending)`

Intent:
- always show the build target
- annotate that the hash repeated because the previous slot ended empty or unresolved

### Pros
- directly addresses Nico's intuition about repeated hash interpretation
- ties the annotation to why the build target did not advance

### Cons
- `carried(empty)` / `carried(full)` is a new operator term that needs explanation
- risks sounding like fork-choice-internal storytelling rather than simple status
- `full` carry-forward is not especially informative in the happy path and may create new questions

## Alternative C — Split current design, but payload row only on non-FULL (current recommendation)

Example:
- FULL: `exec-block: valid(124 0xdef...)`
- PENDING: `exec-block: valid(123 0xabc...) - payload: pending`
- EMPTY: `exec-block: valid(123 0xabc...) - payload: empty`

### Pros
- simplest extension of existing design
- makes repeated hash interpretable in the EMPTY/PENDING cases without new jargon
- avoids duplicating FULL

### Cons
- requires operator to infer that repeated hash + `payload: empty` means "same build target because prior payload did not materialize"

## Alternative D — Explicit build-target + outcome wording

Example:
- `exec-block: valid(123 0xabc...) - payload-outcome: empty`
- `exec-block: valid(123 0xabc...) - payload-outcome: pending`

### Pros
- clearer than bare `payload:` that this is describing current-head outcome, not another execution block
- avoids inventing `prev-payload`

### Cons
- longer / more verbose log text
- may be overkill if plain `payload:` is already understood in context

## Nico idea to evaluate

"Always use the parent hash, but if the previous payload was empty show empty, otherwise full; that way if the hash doesn't change two blocks in a row, you know it didn't change because the proposer built on empty."

Interpretation:
- keep the build-target hash stable as the primary row
- add enough state to explain why it repeated

Main UX appeal:
- repeated hashes become interpretably intentional rather than mysterious

Main risk:
- if expressed as `prev-payload: full|empty`, it reintroduces exactly the extra parent-oriented abstraction we wanted to avoid
- if expressed as a lightweight outcome annotation on the current row, it may still be viable

## Candidate shortlist to compare with gpt-advisor

1. **Current recommendation (Alternative C)**
   - `exec-block` + `payload: pending|empty`
2. **Outcome wording variant (Alternative D)**
   - `exec-block` + `payload-outcome: pending|empty`
3. **Carry-forward wording variant (Alternative B, softened)**
   - `exec-block` + `carried(empty)` only in the EMPTY case

## Current lean before advisor feedback

Best current UX guess:
- keep the current semantics
- prefer either:
  - plain `payload: empty|pending`, or
  - slightly clearer `payload-outcome: empty|pending`
- avoid explicit `prev-payload` / `previous payload was full` wording unless the advisor can show it materially improves interpretability without reopening abstraction debt.
