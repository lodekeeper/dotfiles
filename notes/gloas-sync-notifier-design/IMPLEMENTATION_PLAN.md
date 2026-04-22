# Gloas Sync Notifier — Implementation Plan

Last updated: 2026-04-21 UTC

## Target
- Repo: `lodekeeper/lodestar`
- PR context: `#19`
- File: `packages/beacon-node/src/node/notifier.ts`

## Goal
Implement the converged notifier design:
- `exec-block:` = execution block the node would currently build on for the next block
- `payload-outcome:` only for Gloas exceptional states (`pending` / `empty`)
- no outcome annotation in normal FULL case
- no `prev-payload:` row
- degraded fallback = `exec-block: unresolved(<hash>)`
- derive rows from one atomic head/fork-choice snapshot

## Code-shape plan

### 1. Snapshot once at the top of the notifier path
Capture the head/fork-choice view once and thread it through helper calls.

Intent:
- avoid recomputing `headInfo` / parent resolution separately for `exec-block:` and `payload-outcome:`
- prevent mixed-snapshot output if the head changes mid-log

### 2. Replace the current Gloas-specific execution helper
Current direction has drifted into exposing current-head payload-status details under execution-related output.

Introduce or reshape helpers around this split:

- `getExecBlockInfo(...)`
  - returns the operator-facing `exec-block:` row
  - pre-Gloas: unchanged semantics
  - Gloas FULL: use the revealed payload block
  - Gloas PENDING / EMPTY: resolve the inherited execution anchor from the bid parent hash / parent variant
  - degraded fallback: `unresolved(<hash>)`

- `getGloasPayloadOutcomeInfo(...)`
  - only for post-Gloas heads
  - returns:
    - `payload-outcome: pending`
    - `payload-outcome: empty`
    - otherwise `null`

### 3. Delete / drop `prev-payload:` logic
Remove the entire user-facing `prev-payload:` direction.

Internal parent-variant resolution may still be used to compute `exec-block:`, but must not surface as a separate abstraction.

### 4. Make degraded fallback explicit
When the anchor hash is known but status/number are not:
- emit `exec-block: unresolved(<hash>)`
- do not silently switch to a bare hash row
- do not invent `valid(...)` / `syncing(...)`

### 5. Keep FULL happy path compact
For Gloas FULL:
- emit only `exec-block:`
- suppress `payload-outcome:`

## Likely helper boundaries in `notifier.ts`

Potential structure:
- `getHeadExecutionInfo(...)` -> renamed or narrowed into current-build-target semantics
- `getGloasPayloadOutcomeInfo(...)` -> exceptional-state-only
- `formatExecBlockResolved(...)`
- `formatExecBlockUnresolved(...)`

## Tests to add/update

1. **Pre-Gloas unchanged**
   - existing `exec-block:` output remains stable

2. **Gloas FULL**
   - `exec-block:` present
   - no `payload-outcome:` annotation

3. **Gloas PENDING**
   - `exec-block:` for inherited execution anchor
   - `payload-outcome: pending`

4. **Gloas EMPTY**
   - `exec-block:` for inherited execution anchor
   - `payload-outcome: empty`

5. **Degraded fallback**
   - only hash known
   - output is exactly `exec-block: unresolved(<hash>)`

6. **Same-head transition**
   - same beacon `head:` root
   - `PENDING -> FULL`
   - changed `exec-block:` is accepted/documented

7. **No `prev-payload:` row**
   - explicitly assert absent in all cases

## Review checklist before code lands
- [ ] `exec-block:` contract is consistent in comments and tests
- [ ] no lingering `payload: full` wording in code/tests
- [ ] no user-facing `prev-payload:` row remains
- [ ] fallback uses explicit `unresolved(<hash>)`
- [ ] `exec-block:` + `payload-outcome:` come from one snapshot

## Minimal patch philosophy
Keep this PR scoped to notifier semantics only.
Do **not** mix in unrelated fork-choice cleanup or payload-status refactors.
