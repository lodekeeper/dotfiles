# Gloas voluntary exit — BeaconStateView refactor

Last updated: 2026-03-18 13:08 UTC

## Goal
Refactor voluntary-exit signature verification helpers to use a BeaconStateView-compatible path instead of direct cached-state assumptions, addressing twoeths' review on PR #9039.

## Outcome
Opened follow-up PR:
- **PR #9061** — https://github.com/ChainSafe/lodestar/pull/9061
- **Base:** `nflaig/gloas-voluntary-exit`
- **Head:** `lodekeeper:feat/gloas-voluntary-exit-beaconstateview`
- **Commit:** `3b47bcf30d`

## What changed
- Use `BeaconStateView` at beacon-node voluntary-exit signature call sites
- Remove `isGloasCachedStateType()` from voluntary-exit dispatch path
- Keep builder pubkey lookup inside the signature helper via `getBuilder()`
- Keep validator helper on minimal input (`stateSlot`)
- Fix fork-boundary bug in batch block signature verification by dispatching off `signedBlock.message.slot`

## Validation
- `pnpm build`
- `pnpm check-types`
- `pnpm vitest run packages/state-transition/test/unit/signatureSets/signatureSets.test.ts packages/beacon-node/test/unit/chain/validation/voluntaryExit.test.ts`

## Notes
- I intentionally did **not** add new builder-index bounds checks in the signature-set path. That behavior is consistent with the repo-wide existing voluntary-exit/indexed-signature pattern and was explicitly discussed on the original PR.
- The key behavioral fix beyond the architectural refactor was the fork-boundary dispatch bug found in review.
