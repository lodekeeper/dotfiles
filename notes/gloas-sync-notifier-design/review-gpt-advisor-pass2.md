# Pass 2 verdict
This is materially better. The abstraction is now mostly clean: `exec-block:` has one operator-facing meaning, `payload:` is reserved for exceptional current-head states, and the degraded fallback is explicit. The earlier FULL-case duplication / parent-variant leakage problem is basically gone.

# Remaining concerns
- There is still one stale contradiction in **Edge Cases → Gloas payload full**: it says to show `payload: full(...)`, which conflicts with the rest of the doc and test plan saying there should be no `payload:` row in the normal FULL case. That should be fixed so implementation does not drift.
- The degraded form `exec-block: <hash>` changes the row shape. That is reasonable, but the doc should explicitly note parser/log-consumer impact so nobody assumes `exec-block:` is always `status(number hash)`.
- Since `exec-block:` may change for the same head root on `PENDING -> FULL`, comments/tests should keep reinforcing that this row is the **current build target**, not a permanent property of the beacon head.

# What got better
- `exec-block:` now has exactly one contract, and it is the right operator-facing one.
- `payload:` is scoped to the only cases where it adds real signal (`pending` / `empty`).
- The FULL happy path is compact again; the duplicate execution info is gone.
- The degraded fallback is now honest instead of implicitly over-claiming certainty.

# Is this design ready?
Yes, with the stale FULL-case edge-case text cleaned up. After that, this looks ready to implement.