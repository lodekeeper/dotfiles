Nico — I dug through this from first principles and ran the design through `gpt-advisor`, `devils-advocate`, and a Codex defender fallback review.

The semantics converged first, and then I did a separate UX/display pass on top. The UX winner is slightly better than my earlier wording:

- keep **`exec-block:`** as the stable primary row
- define it strictly as:
  - **the execution block the node would currently build on for the next block**
- **do not add `prev-payload:`**
- for exceptional Gloas cases, annotate the same line with:
  - **`payload-outcome: pending`**
  - **`payload-outcome: empty`**
- **do not emit any payload annotation in the normal FULL case**
- if only the anchor hash is known, use:
  - `exec-block: unresolved(<hash>)`
- if both `exec-block:` and the outcome annotation are emitted, derive them from the same atomic head/fork-choice snapshot

Why I think this is the best fit for your feedback:
- it keeps the user-facing abstraction close to pre-Gloas `exec-block`
- it avoids leaking fork-choice-internal FULL/EMPTY/PENDING parent-resolution details into a separate row
- it still explains repeated execution hashes when the current head is `pending` / `empty`
- it avoids the noisy FULL-case duplication that my earlier direction had
- `payload-outcome:` is clearer UX than bare `payload:` because it answers the natural “payload of what?” hesitation in fast log-scanning

So the intended synced output shape becomes:

- **pre-Gloas / normal FULL Gloas:**
  - `exec-block: valid(n hash)`
- **Gloas PENDING:**
  - `exec-block: valid(n hash)` (or `unresolved(hash)` if we only know the anchor hash)
  - `payload-outcome: pending`
- **Gloas EMPTY:**
  - `exec-block: valid(n hash)` (or `unresolved(hash)` if needed)
  - `payload-outcome: empty`

So Nico’s intuition was directionally right — always show the build target and make repeated hashes interpretable — but the best wording is **current-head outcome annotation**, not a parent-oriented `prev-payload` / carry-forward concept.

If this matches what you want, I’ll implement it as a small `notifier.ts` patch and add targeted tests around:
- FULL = no outcome annotation
- `pending` / `empty` exceptional annotations
- degraded `unresolved(<hash>)` fallback
- same-head `PENDING -> FULL` transition behavior
- no `prev-payload:` row ever
