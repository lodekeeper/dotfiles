## Motivation

While debugging a `lodestar-besu` node on `glamsterdam-devnet-7` that was following the chain optimistically (CL at head, EL still backfilling), the validator client was observed publishing `SyncCommitteeMessage`s even though `/eth/v1/node/syncing` reported `is_optimistic=true`:

```
info: Published SyncCommitteeMessage slot=143118, count=17
```

The [optimistic sync spec](https://github.com/ethereum/consensus-specs/blob/v1.6.1/sync/optimistic.md#participating-in-sync-committees) says an optimistic validator **MUST NOT** participate in sync committees:

> An optimistic validator MUST NOT participate in sync committees (i.e., sign across the `DOMAIN_SYNC_COMMITTEE`, `DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF` or `DOMAIN_CONTRIBUTION_AND_PROOF` domains).

Attestations (`produceAttestationData`) are already gated on optimistic execution status in the beacon-node API. Sync committee participation is asymmetric: the base **sync committee message** is built in the validator client from the head root (`ChainHeaderTracker` / `getBlockRoot`) and submitted directly, and contribution signing can happen later in the same slot after a new optimistic head arrives. Those VC-side signing paths need to honor the beacon node's optimistic status before signing.

## Description

- Expose the node's optimistic status via `SyncingStatusTracker.isNodeOptimistic()`, derived from the last successful `/eth/v1/node/syncing` poll the tracker already performs every slot. Returns `undefined` when the status is unknown, so callers don't over-suppress.
- In `SyncCommitteeService.runSyncCommitteeTasks`, skip sync committee duties before fetching duties when the node is already optimistic, so `DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF` is not signed while optimistic.
- After waiting for the block, recheck the actual head/root and skip `DOMAIN_SYNC_COMMITTEE` signing if that head is optimistic.
- Before producing sync committee contributions, recheck the head again and skip `DOMAIN_CONTRIBUTION_AND_PROOF` signing if an optimistic head arrived during the contribution wait.
- Replace the now-resolved `TODO/PENDING` comment in `validator/index.ts` with a pointer to the new VC-side gate.

## Steps to test

Added unit coverage in `packages/validator/test/unit/services/syncCommittee.test.ts` asserting that optimistic status suppresses selection-proof signing, sync committee message signing, and contribution-and-proof signing. Existing non-optimistic sync committee behaviour is unchanged.
