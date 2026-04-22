# Gloas Sync Notifier — Converged Design Conclusion

Last updated: 2026-04-21 UTC

## Outcome

After first-principles analysis plus two review rounds with `gpt-advisor` and `devils-advocate`, the converged design is:

1. **Keep `exec-block:`** as the primary execution row.
2. Give `exec-block:` exactly one meaning:
   > the execution block the node would currently build on for the next block
3. **Do not add `prev-payload:`.**
4. **Emit `payload:` only for exceptional Gloas lifecycle states**:
   - `payload: pending`
   - `payload: empty`
5. **Do not emit `payload:` in the normal FULL happy path.**
6. If only the execution anchor hash is known, use the explicit degraded form:
   - `exec-block: unresolved(<hash>)`
7. If both `exec-block:` and `payload:` are emitted, derive them from **one atomic head/fork-choice snapshot**.

## Why this is the best fit

### Pre-Gloas
Pre-Gloas, `exec-block:` effectively meant:
- the head's execution payload
- and the execution block the next block would build on

Those were the same object, so one row was enough.

### Gloas
Gloas introduces current-head payload lifecycle states (`pending`, `empty`, `full`) without changing the operator's need to know what execution block the node would build on next.

So the correct split is:
- `exec-block:` = build target
- `payload:` = exceptional current-head lifecycle only when informative

This preserves operator usefulness without leaking fork-choice-internal FULL/EMPTY/PENDING parent-resolution detail into a separate user-facing abstraction.

## Rejected alternatives

### 1. `prev-payload:` row
Rejected because it leaks fork-choice/internal variant-resolution details into the notifier and makes the output harder to scan.

### 2. Always emit both `exec-block:` and `payload:` including FULL
Rejected after review because it duplicates the same block in the normal case and creates noisy logs.

### 3. Redefine `exec-block:` as both “head anchor” and “next build target”
Rejected because that overloads the row and creates semantic contradictions for Gloas heads that transition from `PENDING` to `FULL`.

## Operator-facing contract

### `exec-block:`
- **Meaning:** the execution block the node would currently build on for the next block
- **Happy-path shape:** `exec-block: <status>(<number> <hash>)`
- **Degraded shape:** `exec-block: unresolved(<hash>)`
- **May change for the same head root** if a Gloas head transitions from `PENDING` to `FULL`; this is expected under the “current build target” contract.

### `payload:`
- **Shown only when non-FULL and informative**
- `payload: pending` = current head payload outcome still unresolved at log time
- `payload: empty` = current head has resolved to the no-payload outcome
- no `payload:` row in the normal FULL case

## Recommended implementation shape

Target file:
- `packages/beacon-node/src/node/notifier.ts`

Recommended code shape:
1. Keep the existing log scheduling behavior.
2. Replace the prior Gloas-specific notifier logic with:
   - a helper that computes `exec-block:` from the current build target
   - a helper that computes `payload:` only for `pending` / `empty`
3. Delete `prev-payload:` logic entirely.
4. Ensure both rows are computed from the same head/fork-choice snapshot.

## Tests to add

1. Pre-Gloas output unchanged.
2. Gloas FULL:
   - `exec-block:` present
   - no `payload:` row
3. Gloas PENDING:
   - `exec-block:` present for inherited build target
   - `payload: pending`
4. Gloas EMPTY:
   - `exec-block:` present for inherited build target
   - `payload: empty`
5. Degraded anchor-resolution case:
   - `exec-block: unresolved(<hash>)`
6. Same-head `PENDING -> FULL` transition:
   - unchanged `head:`
   - changed `exec-block:` is expected
7. No `prev-payload:` row ever emitted.

## Review status

- `gpt-advisor`: aligned after second pass; only requested cleanup-level fixes, now applied.
- `devils-advocate`: aligned after second pass; main objections were fixed by narrowing the `exec-block:` contract and removing FULL-case duplication.
- Codex defender fallback: aligned; it agreed the design is coherent and implementation-ready, and it only called out cleanup-level contradictions in the draft, now fixed.
- ChatGPT Pro defender: remained blocked by stale Oracle auth (`RefreshAccessTokenError`), but Nico explicitly approved the Codex defender fallback instead.

## Practical next step

This design is ready to drive:
- the next PR #19 reply summarizing the intended notifier semantics, and/or
- a small implementation patch in `notifier.ts`

There is no remaining design blocker; the original Oracle defender leg was auth-blocked, but the fallback Codex defender review has now filled that role.
