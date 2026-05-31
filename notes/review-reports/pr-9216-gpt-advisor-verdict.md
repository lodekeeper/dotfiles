# PR #9216 - gpt-advisor verdict on Finding 1

## A. Cross-client convention check

Short version: the devils-advocate claim is directionally right about the beacon-APIs contract, but overstated as a cross-client convention. I found no client that has Lodestar's exact "accept a currently gossip-invalid exit, store it in a separate deferred pool, and replay it each epoch" design. However, Prysm is a meaningful counterexample to the blanket "all other clients synchronously reject and require client retry" claim.

### beacon-APIs

`~/beacon-APIs/apis/beacon/pool/voluntary_exits.yaml` defines:

- `POST /eth/v1/beacon/pool/voluntary_exits`
- Description: submit to node's pool, and if it passes validation the node MUST broadcast it.
- Responses: `200` "Voluntary exit is stored in node and broadcasted to network", `400` invalid, `500` internal.
- No `202`, no deferred status, no async status resource, no retry-after/valid-from field.

That makes Lodestar's current behavior of returning undifferentiated `200 OK` for a deferred-but-not-broadcast exit hard to defend as beacon-APIs compatible. The API text does not say "server may queue for future validation"; it says success means stored and broadcasted.

Consensus gossip is also stricter: `~/consensus-specs/specs/phase0/p2p-interface.md` says voluntary-exit gossip validation uses the head state and rejects future epochs / too-young validators. The PR is therefore intentionally creating a local-only holding area for messages that would fail gossip today.

### Lighthouse

Source checked at `sigp/lighthouse@176cce585c1ba979a6210ed79b6b6528596cdb8c`.

- `beacon_node/http_api/src/beacon/pool.rs` routes POST voluntary exits through `chain.verify_voluntary_exit_for_gossip(exit.clone())`.
- `beacon_node/beacon_chain/src/beacon_chain.rs` verifies against `wall_clock_epoch` and head state.
- `consensus/state_processing/src/per_block_processing/verify_exit.rs` rejects `current_epoch < exit.epoch`, too-young validators, pending withdrawals, bad signature, etc.
- On success, Lighthouse publishes and imports into op pool immediately. On transient failure, the REST path returns an invalid-object rejection. I saw no server-side deferred pool.

Verdict: synchronous current-gossip validation; no server-side transient deferral.

### Prysm

Source checked at `OffchainLabs/prysm@c2c8c3f67f3718778611fbdc1223c45175f51af8`.

- `beacon-chain/rpc/eth/beacon/handlers_pool.go::SubmitVoluntaryExit` decodes the exit, fetches head state, then calls `ProcessSlotsIfPossible(ctx, headState, EpochStart(exit.Exit.Epoch))` before `VerifyExitAndSignature`.
- If valid against that processed state, it inserts into `VoluntaryExitsPool` and broadcasts.
- `beacon-chain/operations/voluntaryexits/pool.go::ExitsForInclusion` explicitly skips entries whose `exit.Exit.Epoch > slots.ToEpoch(slot)` and keeps them pending until includable.
- Tests include an `exit2` with `epoch = SHARD_COMMITTEE_PERIOD + 1` accepted with `200 OK`.

This is a real counterexample to "no server-side holding": Prysm accepts future-epoch voluntary exits and holds them in the normal voluntary-exit pool until inclusion time. It is not the same as this PR, though. Prysm does not store an operation that failed validation at the chosen exit epoch, does not maintain a separate transient-failure pool, and does not schedule a later re-broadcast after current gossip validation becomes valid. It also does not solve arbitrary `pendingWithdrawals` with a deferred replay loop.

Verdict: not Lodestar-style deferral, but the absolute cross-client claim is false.

### Teku

Source checked at `Consensys/teku@a3bdf2d0d197b62908653994fcc5815151abf4dd`.

- `data/beaconrestapi/.../PostVoluntaryExit.java` calls `nodeDataProvider.postVoluntaryExit(exit)` and maps `REJECT` to `400`.
- `NodeDataProvider.postVoluntaryExit` performs preliminary checks, then `voluntaryExitPool.addLocal(exit)`.
- `MappedOperationPool.addLocal` validates through `operationValidator.validateForGossip`.
- `statetransition/validation/VoluntaryExitValidator.java` validates against best state and rejects if `spec.validateVoluntaryExit` or signature verification fails.
- Teku does have local-operation re-publication: `MappedOperationPool.updateLocalSubmissions` revalidates and re-publishes accepted local operations after about 2 hours. That is retry for already-accepted local ops, not acceptance of currently invalid transient exits.

Verdict: synchronous reject for transient invalidity; local accepted-op retry exists, but no transient deferral.

### Nimbus

Source checked at `status-im/nimbus-eth2@6fb05f36804d53c2e8e014cfeeea8ad7996a5efe`.

- `beacon_chain/rpc/rest_beacon_api.nim` POST voluntary exits call `node.router.routeSignedVoluntaryExit(exit)`.
- `message_router.nim::routeSignedVoluntaryExit` calls `processSignedVoluntaryExit(MsgSource.api, exit)`.
- `eth2_processor.nim::processSignedVoluntaryExit` calls `validatorChangePool.validateVoluntaryExit`.
- `gossip_validation.nim::validateVoluntaryExit` runs `check_voluntary_exit` against `pool.dag.headState`; errors become reject/ignore, not deferred.

Verdict: synchronous head-state validation; no server-side transient deferral.

### Cross-client conclusion

The defensible statement is narrower than the devils-advocate draft:

"Beacon-APIs does not define a deferred success state for this endpoint, and Lighthouse/Teku/Nimbus reject transiently invalid voluntary exits synchronously. Prysm is the exception: it accepts future-epoch exits by validating at `exit.epoch` and holding them in its normal pool until inclusion. No client I checked implements Lodestar's proposed separate transient-failure pool with per-epoch replay."

Do not post the stronger "no other CL defers server-side" sentence without qualifying Prysm.

## B. Strongest defense of server-side deferral

The best argument for the PR is UX and operational locality, not protocol precedent.

One-shot exit tools are common. A staker may run a CLI once, sign one exit, shut down the machine, and reasonably expect the beacon node to finish the job. Requiring every CLI, staking UI, remote signer integration, institutional workflow, and third-party staking tool to implement `validFromEpoch` semantics creates a long tail of partial implementations. The beacon node already has the canonical state, fork schedule, pending-withdrawal view, clock, gossip publisher, and op pool. Centralizing the retry there can turn "try again tomorrow" into "submit once".

The `pendingWithdrawals` case is especially favorable to server-side logic. The devils draft claims `validFromEpoch` is deterministic, but that is too strong. It depends on future queue draining and missed blocks, and users are poorly positioned to calculate or monitor it. A server-side retry loop avoids exposing a misleading exact epoch for a condition that may be best treated as "retry until it clears".

Prysm and Teku also weaken the philosophical argument that beacon nodes must be purely synchronous submit/broadcast frontends. Prysm already holds future-epoch exits in a local pool; Teku re-publishes accepted local operations periodically. So "the beacon node may take custody of a locally submitted operation and try later" is not alien to the ecosystem. Lodestar's version is broader and riskier, but the UX premise is legitimate.

## C. Strongest attack on the design

The sharpest critique is not "server-side deferral is always the wrong layer". It is:

This PR creates a local quasi-mempool for voluntary exits that currently fail gossip validation, but it does not give that quasi-mempool the contract, validation rigor, durability, or observability that such a component needs.

Specifics:

- It returns the same `200 OK` as immediate publish, even though beacon-APIs describes `200` as stored and broadcasted. For deferred exits, that is not true yet.
- The deferred pool holds operations that the p2p gossip validator would reject today. Promotion therefore must re-run the full current-state API/gossip validation, including signature/domain verification. The current `verifySignature=false` promotion path is not acceptable.
- The pool bypasses the normal duplicate/seen path until insertion time, so repeated submission of the same transient exit can force expensive state/signature work.
- A restart drops all deferred exits. TTL expiry and non-transient eviction are silent from the caller's perspective. This turns "retry later" into "we accepted it and maybe forgot it".
- `pendingWithdrawals` can plausibly exceed a fixed 256-epoch window, and the user has no status endpoint or response field telling them that the node is only making a best-effort attempt.
- The PR exports transient API policy from `@lodestar/state-transition`, which blurs consensus validation reasons with node operation policy.
- The `inactive` carve-out undercuts the UX story. A user who "submitted too early" because the validator is not activated yet still gets the old error, while narrower cases get deferred.

This also makes the 30-LOC structured-error counterproposal look less complete than the devils draft says. A good client-retry design would need non-standard response fields, Lodestar CLI changes, docs for other clients, and careful handling of `pendingWithdrawals` estimates. It is still much smaller than a deferred pool, but it is not free, and it does not give one-shot tools the same UX.

## D. Verdict and PR feedback

Verdict: downgrade Finding 1 from "RECONSIDER, delete the pool and use structured 400" to "server-side deferral is acceptable in principle, but the current contract is not mergeable".

I would not post the devils-advocate critique as-is. The cross-client premise is too broad because Prysm already stores future-epoch exits server-side. The cleaner review is narrower: Lodestar can choose this UX, but once it does, it owns a local deferred-operation pool, not a hidden branch of the submit API. That requires explicit semantics and hardening before merge.

Non-negotiables if accepting the server-side design:

1. Re-run full current-state validation, including signature/domain verification, immediately before op-pool insertion and gossip publication.
2. Add a cheap deferred-pool duplicate check before state regeneration / BLS verification in the API path.
3. Do not return an indistinguishable `200 OK` for deferred exits. Prefer an explicit deferred response such as `202 Accepted` with `{status, reason, expiresAtEpoch}` if Lodestar is willing to extend the beacon-APIs behavior; if not, use another explicit documented signal. The important part is that the caller can tell "published now" from "best-effort deferred".
4. Add operator-visible logging and metrics for deferred insert, promotion, TTL expiry, non-transient eviction, publish failure, and current pool size. TTL drop should be at least warn/info with validator index and last reason.
5. Either persist deferred exits across restart or document and expose the best-effort/in-memory nature in the API response and docs. Silent restart loss is incompatible with "submit once and we will retry".
6. Move transient-classification policy out of `@lodestar/state-transition`, or at least make clear it is beacon-node operation policy rather than consensus validity.
7. Resolve the `inactive` split now or narrow the feature claim. If "submit too early" is the UX target, not-yet-activated validators are part of that story.

Specific PR comment I would post:

> I think the core architectural question here should be narrowed. Beacon-APIs does not define a deferred success state for `POST /eth/v1/beacon/pool/voluntary_exits`: `200` is described as stored and broadcasted, `400` as invalid, and there is no `202`/pending status. Lighthouse, Teku, and Nimbus reject currently gossip-invalid exits synchronously. Prysm is the notable exception: it accepts exits whose `message.epoch` is in the future by validating against that epoch and keeping them in its normal voluntary-exit pool until inclusion, so I would not claim "no client ever holds these server-side." But I also do not see another client with a separate transient-failure pool that replays currently gossip-invalid exits each epoch.
>
> I am okay with Lodestar choosing the "submit once, node retries" UX, especially for one-shot CLI/staking-tool users and `pendingWithdrawals`, but then this needs to be a first-class deferred-operation contract rather than a hidden `200 OK`. Before merge I think we need: full current-state validation including signature/domain before promotion; a cheap duplicate check before expensive API validation; an explicit deferred response/status or documented extension so callers can distinguish published-now from deferred; warn/info + metrics for TTL drops and evictions; and either persistence or a clear best-effort/in-memory contract. Without those, the feature makes the old explicit failure mode worse because the caller is told success even though the operation was neither broadcast nor durably retained.

Fallback if maintainers reject the deferred-pool contract:

Use the structured-error path, but state it honestly as a Lodestar-specific UX improvement rather than an established cross-client convention. The minimal shape is:

- Keep `validateApiVoluntaryExit` returning the `VoluntaryExitValidity`.
- For transient validity, return `400` or `409` with a machine-readable Lodestar extension, for example `{code: "short_time_active", validFromEpoch: "...", retryable: true}`.
- For `earlyEpoch`, `validFromEpoch = exit.message.epoch`.
- For `shortTimeActive`, `validFromEpoch = activation_epoch + SHARD_COMMITTEE_PERIOD`.
- For `pendingWithdrawals`, expose `retryable: true` and either omit exact `validFromEpoch` or label it an estimate.
- Update `lodestar validator voluntary-exit` to sleep/retry or print a precise retry command.

That is simpler and spec-friendlier, but it gives up the main UX win: users and third-party tools still need to stay online or implement retry.
