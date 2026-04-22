Nico — I dug through this from first principles and ran the design through `gpt-advisor`, `devils-advocate`, and a Codex defender fallback review.

I think the right notifier model is:

- keep **`exec-block:`**
- define it strictly as:
  - **the execution block the node would currently build on for the next block**
- **do not add `prev-payload:`**
- only emit **`payload:`** for exceptional Gloas states:
  - `payload: pending`
  - `payload: empty`
- **do not emit `payload:` in the normal FULL case**
- if only the anchor hash is known, use:
  - `exec-block: unresolved(<hash>)`
- if both `exec-block:` and `payload:` are emitted, derive them from the same atomic head/fork-choice snapshot

Why I think this is the best fit for your feedback:
- it keeps the user-facing abstraction close to pre-Gloas `exec-block`
- it avoids leaking fork-choice-internal FULL/EMPTY/PENDING parent-resolution details into a separate row
- it still exposes the genuinely new Gloas information when it matters (`pending` / `empty`)
- it avoids the noisy FULL-case duplication that my earlier direction had

So the intended synced output shape becomes:

- **pre-Gloas:**
  - `exec-block: valid(n hash)`
- **Gloas FULL:**
  - `exec-block: valid(n hash)`
- **Gloas PENDING:**
  - `exec-block: valid(n hash)` (or `unresolved(hash)` if we only know the anchor hash)
  - `payload: pending`
- **Gloas EMPTY:**
  - `exec-block: valid(n hash)` (or `unresolved(hash)` if needed)
  - `payload: empty`

If this matches what you want, I’ll implement it as a small `notifier.ts` patch and add the targeted tests around:
- FULL = no `payload:` row
- `pending` / `empty` exceptional rows
- degraded `unresolved(<hash>)` fallback
- same-head `PENDING -> FULL` transition behavior
- no `prev-payload:` row ever
