# Review Findings — review-bugs — local-pubkey-cache-fix

Reviewer: review-bugs
Reviewed commit: 4bce44fe3e338e581ce4a1fab1da4d154da26701
Generated at: 2026-11-13 10:20 UTC

Reviewer: review-bugs
Reviewed commit: 4bce44fe3e338e581ce4a1fab1da4d154da26701

## Findings

### 1. Resolving every block's missing keys against the batch's initial state rejects valid later slashings

**File:Line:** `packages/state-transition/src/signatureSets/index.ts:99`

**Bug:** The new unconditional `resolveSignatureSet(signatureSet, state)` assumes that `state` contains every validator referenced by the block. In the production batch-verification caller, however, `state` is `preState0` for *every* block in the epoch, not the pre-state of the corresponding block. Before Fulu, a deposit in an earlier block of that batch can create a new validator. A later block can legally include an attester slashing whose participants include both an existing active validator and this new inactive validator: indexed-attestation validation does not require every participant to be active, and slashing the active participant satisfies the slashing operation. The new key is candidate-only and absent from `preState0`, so resolution reads a nonexistent validator and throws instead of verifying the valid slashing.

**Verified behavior:** Ran a read-only Node reproduction using the current built state-transition code, an actual phase0 `CachedBeaconState` with 64 active validators, and `addValidatorToRegistry` on its clone to model the earlier block's deposit. Constructed two different, correctly signed indexed attestations with participants `[0, 64]`. `assertValidAttesterSlashing(..., 65, slashing, true, postDepositState)` passed. `getBlockSignatureSets(..., preState0, laterBlock, [])` threw `TypeError: Cannot read properties of undefined (reading 'pubkey')`, through `getValidatorPubkey -> resolveSignatureSet`. The identical call with the later state succeeded with four signature sets. The dense cache remained size 64, while the later state had 65 validators.

**Impact:** Valid same-epoch block batches are rejected during range/historical sync, including pre-Electra and Electra deposit processing. Running the state transition in parallel does not fix this: the initial state's registry remains unchanged, and the BLS jobs are deliberately constructed before those transitions.

**Fix:** Resolve missing participant keys against the corresponding block's pre-state, including validators deposited in preceding blocks, rather than against `preState0`. Preserve per-epoch shuffling/domain inputs separately if needed, and add a regression with a deposit followed by a valid mixed active/inactive attester slashing in one verification batch.

### 2. Truncating only by anchor length leaves legacy branch-poisoned keys inside the retained prefix

**File:Line:** `packages/cli/src/cmds/beacon/pubkeysFile.ts:39`

**Bug:** The legacy-file repair retains the entire overlapping prefix after checking only its first and last pubkey. Divergent branches can have the same validator count and matching endpoint keys while assigning different indices to interior keys. This is possible at Heze with finalized pending deposits ordered `A(0x00), B(0x01), A(0x01), C(0x01)`: the pre-fork branch creates `A, B, C`, whereas the canonical post-fork branch skips the first A deposit and creates `B, A, C`. Both registries end at C. Loading the old side-branch cache therefore passes both endpoint checks, and the new truncation does not remove either poisoned entry. Trusted startup `syncPubkeys` does not compare existing entries, so it preserves this incorrect dense prefix.

**Verified behavior:** Ran the existing minimal-preset Heze fork fixture with the additional correctly signed A(0x01) and C(0x01) deposits. Actual state transitions produced side indices `A=64, B=65, C=66` and canonical indices `A=65, B=64, C=66`, both with 67 validators. Saved the side registry through the native pubkeys file API, reset the cache, and called the changed `loadPubkeysFile` with the canonical state's bytes. It reported a successful 67-key load. Afterwards `getValidatorIndex(canonical, B, pubkeyCache)` returned **65**, although B is `canonical.validators[64]`; `getValidatorPubkey(canonical, 64, pubkeyCache)` returned A instead of B.

**Impact:** The migration leaves the original persistent cache poisoning in place for a concrete valid fork-boundary sequence. Canonical pubkey/index lookups and BLS verification use the wrong validator keys after restart. This is an incomplete repair of the legacy-file poisoning addressed by this change; no file corruption or untrusted snapshot is required.

**Fix:** Validate the retained legacy prefix against the anchor's pubkeys, not just its endpoints; discard/rebuild the cache upon any mismatch. Alternatively distinguish snapshots that are guaranteed to contain only finalized validators and rebuild unversioned legacy snapshots from the trusted anchor.

## Review verification

- Read the full supplied diff and surrounding TypeScript/Zig/native-binding code.
- Both findings were reproduced locally with executable, correctly signed fixtures; no source files were changed and no builds were run.
- Worktree HEAD matched the requested commit, and `git status --short` remained clean after the reproductions.
