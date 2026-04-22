# Gloas Sync Notifier Design

Last updated: 2026-04-21 UTC

## Problem

Pre-Gloas, the node notifier exposes a single execution-centric row:

```text
exec-block: valid(<blockNumber> <blockHash>)
```

That row has an implicit operator-facing meaning:

> "What execution block is this beacon head anchored to / what execution block will the next block build on?"

PR #18 introduced a Gloas-specific `payload:` row for the current head's payload lifecycle (`pending` / `empty` / `full`).

PR #19 attempted to add a second row, `prev-payload:`, by resolving the parent beacon block variant through fork-choice and printing its payload status. Nico's feedback was that this is the wrong abstraction: `FULL` / `EMPTY` / `PENDING` are fork-choice-internal details, and the notifier should keep operator-facing semantics close to pre-Gloas `exec-block` instead of surfacing variant bookkeeping.

## First-Principles Analysis

## What `exec-block` meant pre-Gloas

Pre-Gloas, every post-Bellatrix beacon block embeds one execution payload. Therefore:
- the current head's execution payload
- the execution chain head the next block will build on
- the execution payload hash/number logged by the notifier

are all the same object.

So pre-Gloas `exec-block:` was stable and intuitive.

## What Gloas changes

Gloas splits two concepts that were previously identical:

1. **The execution block the current beacon head builds on**
   - determined by the bid's `parent_block_hash`
   - this is the execution chain anchor for the next proposer
2. **The payload lifecycle of the current beacon head itself**
   - `PENDING`: beacon block imported, payload not yet revealed
   - `EMPTY`: payload not revealed / not present
   - `FULL`: payload revealed and imported

Those are different user questions, and conflating them creates notifier confusion.

## Crucial code-level invariant

In Lodestar fork-choice, for Gloas blocks before payload reveal, `ProtoBlock.executionPayloadBlockHash` is already set to the bid's `parent_block_hash`:

```ts
executionPayloadBlockHash: toRootHex(block.body.signedExecutionPayloadBid.message.parentBlockHash)
```

and `executionPayloadNumber` is derived from the parent variant that the block extends.

That means the notifier already has a natural place to represent the execution-chain anchor semantics. The need for a separate `prev-payload:` row is much weaker than initially assumed.

## Design Goals

1. Preserve the operator-facing meaning of `exec-block:` across forks.
2. Surface genuinely new Gloas information without leaking fork-choice internals.
3. Avoid notifier rows whose semantics require understanding FULL / EMPTY / PENDING parent variants.
4. Keep the log line compact and easy to compare across pre-Gloas and Gloas nodes.
5. Define deterministic fallback behavior for partial / degraded resolution so implementations do not improvise.

## Canonical semantic contract

Use this sentence consistently in code comments, review replies, and docs:

> `exec-block:` is the execution block the node would **currently** build on for the next block.

That is the clean cross-fork invariant. Pre-Gloas it coincides with the current head's embedded execution payload. In Gloas it may reflect either the inherited execution anchor (for unresolved/missed payload heads) or the revealed payload block once the head becomes FULL.

For Gloas, `payload:` is an exceptional-state row describing the lifecycle state of the **current head's own payload**, not the build target.

## Semantics table

| Case | `exec-block:` means | `exec-block:` source contract | `payload:` output |
|------|---------------------|-------------------------------|-------------------|
| Pre-Gloas post-Bellatrix | The execution block the next block would build on | Existing pre-Gloas `headInfo.executionStatus` + `executionPayloadNumber` + `executionPayloadBlockHash` | none |
| Gloas FULL head | The execution block the next block would build on (now the head's own revealed payload) | Resolved from FULL head variant | none |
| Gloas PENDING head | The inherited execution parent the next block would currently build on | Derived from the bid's `parent_block_hash`; number/status resolved from the parent variant if available | `payload: pending` |
| Gloas EMPTY head | The inherited execution parent the next block would currently build on | Derived from the bid's `parent_block_hash`; number/status resolved from the parent variant if available | `payload: empty` |
| Degraded / partial lookup | Same intended meaning as above | If hash anchor is known but number/status cannot be resolved, print an explicit degraded form rather than inventing certainty | only if non-FULL lifecycle needs surfacing |

## Options Considered

### Option A — Keep PR #19 shape (`prev-payload:`)

Example:

```text
payload: pending - prev-payload: empty
```

**Pros**
- Explicitly shows the parent beacon block's payload variant.

**Cons**
- Surfaces fork-choice-internal notions (`FULL` / `EMPTY` / `PENDING`) in a user-facing row.
- Duplicates execution-chain information that should remain under `exec-block:` semantics.
- Creates confusing output in the missed-payload case (`prev-payload: empty`) even though the next proposer still builds on a concrete execution block hash.
- Nico explicitly pushed back on this shape.

**Verdict**: reject.

### Option B — Keep `exec-block:` as the primary row, add `payload:` only for exceptional Gloas lifecycle states

Example outputs:

**Pre-Gloas**
```text
Synced - slot: N - head: 0x... - exec-block: valid(19876543 0x123456...) - finalized: ... - peers: 42
```

**Gloas, current head pending**
```text
Synced - slot: N - head: 0x... - exec-block: valid(19876543 0x123456...) - payload: pending - finalized: ... - peers: 42
```

**Gloas, current head empty**
```text
Synced - slot: N - head: 0x... - exec-block: valid(19876543 0x123456...) - payload: empty - finalized: ... - peers: 42
```

**Gloas, current head full**
```text
Synced - slot: N - head: 0x... - exec-block: valid(19876544 0x234567...) - finalized: ... - peers: 42
```

**Pros**
- `exec-block:` keeps a stable operator meaning across forks: what the node would currently build on next.
- `payload:` captures the genuinely new Gloas lifecycle question only when it adds information.
- No need for a user-facing `prev-payload:` row.
- Avoids duplicating the same execution block twice in the common FULL case.

**Cons**
- `exec-block:` can still change for the same beacon head root if a PENDING head later becomes FULL before the next log point; that is semantically acceptable under the "currently build on" contract, but it must be documented.
- Requires a small internal resolution helper so `exec-block` status/hash represent the current build target rather than the head's raw `PayloadSeparated` execution status.

**Verdict**: preferred.

### Option C — Replace `payload:` with only `exec-block:` and hide current-head payload lifecycle entirely

**Pros**
- Minimal log surface.
- Maximum continuity with pre-Gloas.

**Cons**
- Loses the most important genuinely new Gloas observability signal: whether the current head's payload is still pending, was missed, or is full.
- Throws away the value PR #18 was trying to add.

**Verdict**: too lossy.

## Recommended Design

Adopt **Option B**.

### User-facing semantics

- **`exec-block:`** always means:
  > the execution block the node would currently build on for the next block

- **`payload:`** (Gloas only, exceptional states only) means:
  > the lifecycle state of the current head's own payload when that state is still informative (`pending` or `empty`)

This preserves pre-Gloas semantics while making the new Gloas distinction explicit without duplicating the happy-path block twice.

### Tight lifecycle contract for `payload:`

To avoid fuzzy overlap:

- **`payload: pending`** = the beacon head exists, but at log time the node still treats the head's own payload outcome as unresolved.
- **`payload: empty`** = the head has resolved to the no-payload outcome for that slot / variant; from the operator's perspective this is the settled missed/absent case, not merely “still waiting”.
- **No `payload:` row in the FULL happy path by default.** In that case the informative row is `exec-block:`.

This should be expressed in operator terms in comments/docs even if the internal source is `PayloadStatus`.

## Implementation Approach

### 1. Keep PR #18's `payload:` concept

Retain the Gloas-specific `payload:` row as the way to express current-head payload lifecycle.

### 2. Do **not** add `prev-payload:`

Drop the entire PR #19 idea of a second row named `prev-payload:`.

### 3. Rework `getHeadExecutionInfo()` for Gloas

Instead of returning `payload:` directly in Gloas, make it return the execution-chain anchor as `exec-block:`.

Implementation intent:
- Pre-Gloas: unchanged.
- Gloas FULL: `exec-block:` can be derived directly from the FULL head variant.
- Gloas PENDING/EMPTY: resolve the execution block referenced by the head's bid `parent_block_hash` and render that as `exec-block:`.

That helper may internally need fork-choice variant resolution, but it must not leak those details into the log output.

### 3a. `exec-block:` source / fallback contract for Gloas non-FULL heads

For Gloas `PENDING` / `EMPTY` heads, the notifier must not over-claim certainty.

Recommended contract:
- If the execution anchor hash, number, and status are all resolvable from the parent variant, print the full form:
  - `exec-block: <status>(<number> <hash>)`
- If the execution anchor hash is known but number/status are not confidently resolvable, print an explicit degraded form:
  - `exec-block: unresolved(<hash>)`
- Do **not** invent `valid(...)` / `syncing(...)` if the notifier has not actually resolved that status from the relevant parent execution block.
- Only suppress the row entirely when even the anchor hash cannot be recovered.

This preserves honesty without silently changing the shape of the row.

This keeps the row honest while preserving the stable operator-facing meaning.

### 4. Add a separate `getGloasPayloadInfo()`

For post-Gloas heads only, emit:
- `payload: pending`
- `payload: empty`
- no row in the FULL happy path by default

### 5. Row ordering

Recommended order for synced state:

```text
Synced - slot - head - exec-block - payload (only when non-FULL) - finalized - peers
```

This keeps `exec-block` in its legacy place and treats `payload` as an additional Gloas-specific diagnostic only when it adds information.

### 6. Atomic snapshot requirement

If both `exec-block:` and `payload:` are emitted, they must be derived from the same head / fork-choice snapshot. The notifier must not resolve `exec-block:` from one view of the head and `payload:` from a later view after payload reveal state has changed.

## Minimal Code-Change Shape

Likely changes confined to `packages/beacon-node/src/node/notifier.ts`:

- keep / adapt `timeToNextLogPoint()` from PR #18
- replace `getGloasExecutionInfo()` with:
  - `getHeadExecutionInfo(...)` that restores `exec-block:` semantics for all forks
  - `getGloasPayloadInfo(...)` for the current head lifecycle
- remove `getPrevSlotPayloadInfo()` entirely

## Edge Cases

### Pre-merge head
No execution rows.

### Gloas payload pending at log time
Show:
- `exec-block:` for the execution anchor inherited from the bid parent hash
- `payload: pending` for the current head

### Gloas payload missed / empty
Show:
- `exec-block:` for the inherited execution anchor
- `payload: empty`

### Gloas payload full
Show:
- `exec-block:` for the now-current execution payload
- no `payload:` row by default

### Degraded parent-resolution case
If the notifier can only recover the execution anchor hash but not a trustworthy number/status, print a degraded `exec-block:` form rather than inventing stronger semantics.

### Reorg around payload reveal
Design expectation: `payload:` may legitimately flip across notifier ticks as the head changes, but `exec-block:` should remain semantically anchored to the head's execution parent rather than to fork-choice variant names.

### Same head root, payload transition only
For the same beacon head root, `exec-block:` may change if a Gloas head transitions from `PENDING` to `FULL` before the next log point. Under the revised contract this is acceptable: the row means "what the node would currently build on next", not "a value permanently attached to that beacon head root".

### Potential duplication in FULL case
The revised recommendation is to avoid duplication entirely: do not emit a `payload:` row in the normal FULL case. The happy-path synced line should stay compact, with `payload:` reserved for `pending` / `empty` cases where it adds new information.

## Why this is the best fit for Nico's feedback

Nico's core objection was not "never resolve parent execution context internally"; it was "don't expose fork-choice internal detail as the notifier abstraction." This design respects that:

- internal variant resolution may still exist under the hood
- user-visible rows stay at the execution-chain / payload-lifecycle level
- `exec-block` remains the stable cross-fork operator concept

## Test Plan

1. Unit-test pre-Gloas notifier output remains unchanged.
2. Unit-test Gloas FULL output includes:
   - `exec-block: <status>(n hash)`
   - and **no** `payload:` row by default.
3. Unit-test Gloas EMPTY output includes:
   - `exec-block:` anchored to the inherited execution parent
   - `payload: empty`
4. Unit-test Gloas PENDING output includes:
   - `exec-block:` anchored to the inherited execution parent
   - `payload: pending`
5. Unit-test degraded Gloas anchor resolution where only hash is known, ensuring the notifier emits `exec-block: unresolved(<hash>)` rather than inventing status/number.
6. Unit-test same-head `PENDING -> FULL` transition behavior so a changed `exec-block:` without a changed `head:` is expected and documented, not mistaken for a bug.
7. Unit-test that no `prev-payload:` row is emitted.

## Final design decision on degraded fallback

For unresolved Gloas non-FULL heads, prefer the explicit degraded form `exec-block: unresolved(<hash>)` whenever the execution anchor hash is known. Only omit the row when even the anchor hash cannot be recovered.

## Recommendation

Proceed with **Option B**:
- keep `payload:` for the current Gloas head lifecycle
- restore `exec-block:` as the stable execution-anchor row across forks
- drop `prev-payload:` entirely
