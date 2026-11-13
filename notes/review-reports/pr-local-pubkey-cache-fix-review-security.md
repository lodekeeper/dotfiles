# Review Findings — review-security — local-pubkey-cache-fix

Reviewer: review-security
Reviewed commit: 4bce44fe3e338e581ce4a1fab1da4d154da26701
Generated at: 2026-11-13 10:23 UTC

## Summary

Two security findings: one incomplete migration of previously poisoned pubkey snapshots, and one new state-backed signature fallback regression affecting pre-Fulu epoch-batch validation. Both were reproduced with the reviewed source and existing native addon. No worktree files were modified and no build was run.

## 1. Legacy snapshot poison can survive the new startup truncation

- **File:Line:** `packages/cli/src/cmds/beacon/pubkeysFile.ts:39` (with the retained endpoint-only validation at lines 27–36).
- **Vulnerability:** Persistent public-key cache poisoning / incorrect signature-key selection (CWE-347, CWE-20). Truncating only entries beyond the anchor's validator count does not establish that the retained interior agrees with the anchor. The premise that matching endpoints prove a matching append-only registry is exactly what the fork-boundary attack invalidates. This is incomplete remediation of the legacy-cache attack, not a claim that a fresh finalized-only cache can be remotely overwritten or that an attacker must edit a local file.
- **Attack vector:** A remotely induced pre-fix side branch can populate and persist registry order `[..., A, B, C]`, while the canonical branch later has `[..., B, A, C]`. This can happen at Heze with finalized pending deposits ordered as: a churn-consuming top-up, a new 0x00 deposit for A, a deposit for B, a later execution-credential deposit for A, then a deposit for C. The side branch postpones the top-up through a slashing and creates A before Heze. The canonical branch reaches Heze before those additions, skips A's 0x00 deposit, then creates B, A, C. When upgrading/resyncing against the canonical checkpoint while retaining the legacy pubkeys file, both checked endpoints and the validator count match. No truncation/reset removes the swapped interior. Startup `syncPubkeys` trusts the existing overlap, and both STFs' dense-cache shortcuts continue to use the side-branch keys. Valid canonical signatures fail, and signatures under the wrong validator's key can pass. State-backed fallback does not help because these indices are already dense.
- **Severity:** **High** — persistent consensus-validation bypass/liveness failure for an affected legacy snapshot reused with a later canonical anchor. Requires a previously poisoned snapshot and that anchor-selection/resync scenario; fresh finalized-only snapshots are not implicated.
- **Mitigation:** Before trusting a legacy file, compare every retained pubkey with the authenticated anchor and discard/rebuild on any mismatch, or invalidate the legacy file format/version once so pre-fix snapshots cannot be reused. Merely truncating to the anchor count or checking its endpoints is insufficient.

### Executed evidence

Using the existing Heze branch fixture, extended with a second deposit for A using execution credentials and a final deposit for C, real `processSlots` transitions produced:

```text
side:      [A, B, C]
canonical: [B, A, C]
sideCount: 67
canonicalCount: 67
```

A separate minimal native snapshot/load reproduction used the same interior permutation, matching endpoints and equal counts, passed the resulting file through the actual `loadPubkeysFile`, then called the actual startup-style `syncPubkeys`. Results:

```text
loadedSize: 4
anchorIndexOfA: 2
resolvedIndexOfA: 1
interiorMatches: false
validCanonicalValidatorSignatureAccepted: false
wrongSideBranchValidatorSignatureAccepted: true
```

The final two checks used the actual `verifySignatureSet(..., anchor)` with cryptographically valid signatures, showing that supplying state does not repair a poisoned dense entry.

## 2. Resolving block signature sets against the epoch's initial state rejects valid slashings for validators deposited earlier in that batch

- **File:Line:** `packages/state-transition/src/signatureSets/index.ts:99`; the failing fallback dereference is `packages/state-transition/src/util/signatureSets.ts:109`.
- **Vulnerability:** Consensus-valid block rejection / range-sync denial of service caused by resolving against the wrong validator registry (CWE-754).
- **Attack vector:** Before Fulu, a block's legacy deposit can immediately add a validator, including during Electra. Let block 1 add inactive validator N. A later block in the same epoch can validly contain an attester slashing whose two indexed attestations include N and an existing active, slashable validator. Indexed-attestation validity does not require every signer to have been active. Both validators can genuinely sign the conflicting data, so this is valid evidence. Epoch-batch signature verification passes the same `preState0` to `getBlockSignatureSets` for every block, concurrently with STF processing. The new mapping at line 99 now resolves N through that original state. N is not finalized/dense, and N is absent from `preState0`, so `getValidator(N)` throws even though N exists in the later block's actual pre-state. The whole verification batch fails before import. Previously, the globally appended key could satisfy this lookup; the finalized-only cache makes this a new failure. A proposer can place such valid evidence into a supported pre-Fulu chain and prevent affected nodes from range-syncing that epoch normally, despite nodes validating blocks individually accepting it.
- **Severity:** **Medium** — consensus-valid chain-segment rejection and sync liveness failure, limited to supported pre-Fulu processing where validators can be added inside an epoch. It does not assert that Fulu+ epoch-boundary pending deposits have this intra-epoch problem.
- **Mitigation:** Resolve missing keys against each block's actual pre-state (or a verified per-block registry snapshot), not the common epoch-start state. One approach is to defer only the missing-key signature sets until the sequential transition has produced the relevant state; another is to split pre-Fulu batches at registry additions. Do not trust an arbitrary global candidate as a replacement, since that would restore the cross-branch key-selection problem.

### Executed evidence

A standalone source-level reproduction created a dense active key at index 0, a candidate-only inactive key at index 1, and two genuinely signed conflicting indexed attestations containing `[0, 1]`. It established:

```text
validSlashingSignatures: true
activeIntersectionParticipant: true
newParticipantInactive: true
```

`assertValidAttesterSlashing(..., validatorsLen=2, verifySignatures=true, laterBlockState)` succeeded. Passing the same slashing in a block through `getBlockSignatureSets` with the epoch's original one-validator state produced:

```text
validator 1 absent from preState0 with 1 validators
```

Using the actual later two-validator state returned all three signature sets successfully. The production epoch-batch caller was inspected and confirmed to pass `preState0` for every block before sequential state transitions complete.

## Additional scope checks

- Reviewed the full supplied diff and relevant initialization, regeneration, batch-verification, finalization, deposit, API, and slashing call paths.
- Candidate-only lookups compare candidate keys with the requesting state. The beacon state REST lookup additionally rejects a stale orphan state's conflicting dense mapping.
- The new native cache methods use balanced deferred lock release, return owned candidate copies, and do not introduce an evident recursive cache-lock acquisition in the inspected production paths. No separate lock vulnerability was identified.
- Candidate storage has no explicit entry-count/per-key-list bound and retains peak capacity. However, the inspected network ingress constrains new validator keys through authenticated deposit processing or trusted stored states. I did not establish a separate practical attacker-controlled unbounded-growth exploit, so this is not elevated to a finding.
- No full consensus vector suite or build was run. The concrete checks above were isolated Node/tsx executions using existing build products; the reviewed worktree remained clean.
