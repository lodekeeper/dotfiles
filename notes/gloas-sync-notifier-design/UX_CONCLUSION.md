# Gloas Notifier UX Conclusion

Last updated: 2026-04-22 UTC

## Winner

Use the existing primary row:
- `exec-block: <status>(<number> <hash>)`

And for exceptional Gloas cases, annotate the **current head outcome** on the same line as:
- `payload-outcome: pending`
- `payload-outcome: empty`

Do **not** introduce:
- `prev-payload:`
- `carried(...)`
- `previous payload was full/empty`

## Recommended display

### Pre-Gloas / normal FULL Gloas
```text
exec-block: valid(124 0xdef...)
```

### Gloas pending
```text
exec-block: valid(123 0xabc...) - payload-outcome: pending
```

### Gloas empty
```text
exec-block: valid(123 0xabc...) - payload-outcome: empty
```

### Degraded partial anchor resolution
```text
exec-block: unresolved(0xabc...) - payload-outcome: pending
```
or
```text
exec-block: unresolved(0xabc...) - payload-outcome: empty
```

## Why this wins

This keeps the notifier UX aligned with all the evaluation criteria:

1. **Stable primary row**
   - `exec-block` remains the single primary execution row.

2. **Happy-path compactness**
   - FULL stays visually identical to the familiar legacy shape.

3. **Repeated-hash interpretability**
   - when the hash repeats, the operator immediately sees whether that happened because the current head outcome is `pending` or `empty`.

4. **Low abstraction debt**
   - no new `prev-payload` / `carry-forward` concept is introduced.

5. **Clearer than bare `payload:`**
   - `payload-outcome:` answers the natural “payload of what?” hesitation that plain `payload:` can trigger in fast log-scanning.

## Why Nico's idea was directionally right

Nico's intuition was correct:
- always show the build target
- also show enough state so repeated hashes are interpretable

But the best surface form is **not** parent-oriented wording.
The better expression is:
- keep the build-target row (`exec-block`)
- annotate the **current head outcome** (`payload-outcome: empty|pending`)

That preserves the UX benefit without teaching the operator a new internal mechanism.

## Final recommendation

For PR #19, the best UX/display shape is:
- **`exec-block` as the stable main row**
- **`payload-outcome: pending|empty` only for exceptional Gloas cases**
- **no payload annotation in the normal FULL case**
- **no `prev-payload` row**
