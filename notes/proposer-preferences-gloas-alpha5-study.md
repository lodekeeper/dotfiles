# Proposer Preferences in Gloas alpha.5 — study notes

_Last updated: 2026-04-22 (refreshed against current upstream heads)_

## Scope

Study only, no implementation.

Primary sources used:
- `~/ethereum-repos/consensus-specs` tag `v1.7.0-alpha.5`
- current `~/ethereum-repos/consensus-specs` `origin/master` at `c461e4a69`
- `~/ethereum-repos/beacon-APIs` master + PR `#593`
- current `~/ethereum-repos/beacon-APIs` `origin/master` at `ce1451b`
- `ethereum/consensus-specs` PR `#4777` (merged)
- `ethereum/beacon-APIs` issue `#570` and PR `#593`

## Up-to-date check (current upstream state)

I re-checked the note against current upstream before sharing it.

### consensus-specs status

On current `consensus-specs` `origin/master` (`c461e4a69`), the proposer-preferences parts I traced from `v1.7.0-alpha.5` are still present in the same Gloas files:
- `specs/gloas/p2p-interface.md`
- `specs/gloas/validator.md`
- `specs/gloas/builder.md`
- `specs/gloas/beacon-chain.md`

I diffed those files against `v1.7.0-alpha.5`. For proposer preferences specifically, I did **not** find semantic drift in the parts covered by this note. The only diff in that file set on `master` was an unrelated explanatory note added in `beacon-chain.md` about withdrawal accounting asymmetry.

So the proposer-preferences understanding in this note is still current with upstream spec head.

### beacon-APIs status

On current `beacon-APIs` `origin/master` (`ce1451b`):
- issue `#570` is still **open**
- PR `#593` is still **open**
- PR `#593` is currently marked **behind** base
- `origin/master` still has **no proposer-preferences API surface** merged yet

So as of this refresh, proposer preferences are still in the state of:
- present in consensus-specs,
- proposed in beacon-APIs,
- **not yet merged** into beacon-APIs master.

## Version note: which “alpha.5” matters

`consensus-specs` has multiple `alpha.5` tags. The one that actually contains proposer preferences in Gloas is **`v1.7.0-alpha.5`**.

I checked `v1.6.0-alpha.5` first, but that older Gloas shape still used `execution_payload_header` and does **not** contain proposer preferences. So for this task, `v1.7.0-alpha.5` is the relevant reference.

## Executive summary

Proposer preferences are a **new signed gossip object** in Gloas that lets a proposer pre-announce, for a specific future proposal slot:
- the **fee recipient** that should receive the builder payment, and
- the **gas limit** the proposer wants for that execution payload.

This is not just metadata.
It is part of the **trustless bid path**:
- builders are expected to build bids that match these preferences,
- gossip validation for `execution_payload_bid` depends on the corresponding `SignedProposerPreferences` having been seen, and
- if a proposer does **not** publish preferences for a slot, that effectively means it will **not accept trustless bids** for that slot.

So proposer preferences are not an optional side note; they are part of the gating/signaling mechanism that makes the trustless builder flow work.

## What the spec adds

From `specs/gloas/p2p-interface.md` in `v1.7.0-alpha.5`:

### New containers

```python
class ProposerPreferences(Container):
    proposal_slot: Slot
    validator_index: ValidatorIndex
    fee_recipient: ExecutionAddress
    gas_limit: uint64

class SignedProposerPreferences(Container):
    message: ProposerPreferences
    signature: BLSSignature
```

### New signature domain

From `specs/gloas/beacon-chain.md`:
- `DOMAIN_PROPOSER_PREFERENCES = DomainType('0x0D000000')`

The validator signs the `ProposerPreferences` object using the domain for the epoch of `proposal_slot`.

## Functional intent

The intent is: before the slot arrives, the proposer tells builders:
- “for slot X, if you want me to accept a trustless bid, the payment recipient must be Y”
- “and the bid / produced payload must use gas limit Z”

This gives builders the exact slot-scoped preferences they need before constructing bids.

## When validators broadcast proposer preferences

From `specs/gloas/validator.md` (`v1.7.0-alpha.5`):

A validator **may** broadcast `SignedProposerPreferences` for:
- any **future proposal slots in the current epoch**, and
- **all proposal slots in the next epoch**,

using `state.proposer_lookahead`.

Helper sketch from spec:
- iterate over `state.proposer_lookahead`
- map offsets to slots in current + next epoch
- ignore slots `<= state.slot`
- include only slots where `proposer_index == validator_index`

### Important consequence

If a validator **does not** broadcast proposer preferences for a slot, the spec says this implies the validator will **not accept any trustless bids for that slot**.

That is a strong semantic signal:
- proposer preferences are an **opt-in gate** for trustless bids,
- not merely a convenience field.

## Gossip topic and validation

### New global topic

`proposer_preferences` carries `SignedProposerPreferences`.

### Gossip validation rules

Before forwarding a `signed_proposer_preferences`, the node checks:

1. `proposal_slot` is in the **current or next epoch**.
2. `proposal_slot` has **not already passed**.
3. `validator_index` is actually the proposer for that slot according to the relevant part of `state.proposer_lookahead`.
4. it is the **first valid message** seen for that `(validator_index, proposal_slot)` pair.
5. the BLS signature is valid for that validator.

### Derived behavior

This means the network treats proposer preferences as:
- **slot-specific**,
- **signed by the proposer**,
- **deduplicated by proposer+slot**,
- valid only in a narrow time window.

## How proposer preferences affect builder bids

This is the most important linkage.

From `specs/gloas/p2p-interface.md`, `execution_payload_bid` gossip validation now assumes the node has seen the corresponding proposer preferences for `bid.slot`.

Validation includes:
- the corresponding `SignedProposerPreferences` for `bid.slot` has been seen,
- `bid.fee_recipient` matches the proposer preference,
- `bid.gas_limit` matches the proposer preference.

So proposer preferences are directly coupled to bid validity on gossip.

### Meaning

A trustless builder bid is not just “a builder signed something valuable”.
It must also match the proposer’s slot-bound declared preferences.

This prevents ambiguity and prevents builders from unilaterally choosing:
- where the builder payment goes, or
- what gas limit the proposer is supposed to accept.

## How builders use proposer preferences

From `specs/gloas/builder.md` (`v1.7.0-alpha.5`):

When constructing `ExecutionPayloadBid`, the builder:
- sets `bid.fee_recipient` from the proposer’s `SignedProposerPreferences` for that slot,
- sets `bid.gas_limit` from the proposer’s `SignedProposerPreferences` for that slot.

So builders need access to proposer preferences before producing valid bids.

The spec allows them to obtain this either:
- from the **gossip topic**, or
- via **other off-protocol means**.

## How proposers use builder bids

From `specs/gloas/validator.md`:
- proposers listen to the `execution_payload_bid` gossip topic,
- retain accepted bids,
- select one bid and place it into `block.body.signed_execution_payload_bid`.

The proposer relies on the network / local validation path to ensure the bid matches the declared proposer preferences.

## What `fee_recipient` means here

One subtle but important detail:

The spec note in `validator.md` says the `fee_recipient` encoded in `signed_execution_payload_bid.message` is the address that will receive the **builder payment**.

So in this context, proposer preferences are about the **builder payment recipient** and desired `gas_limit` for the slot.

## Why this is a bigger deal than existing `prepare_beacon_proposer`

The current Beacon API already has `/eth/v1/validator/prepare_beacon_proposer`, but that endpoint is **not the same thing**.

`prepare_beacon_proposer` is:
- unsigned,
- per-validator,
- persistent for some epochs,
- only carries `validator_index + fee_recipient`,
- not slot-specific,
- does not carry `gas_limit`,
- is local VC→BN configuration.

Proposer preferences in Gloas are:
- **signed**,
- **slot-specific**,
- tied to **gossip propagation**,
- include **gas_limit**,
- used to validate **execution payload bids**.

So proposer preferences are not a minor extension of `prepare_beacon_proposer`; they are a different protocol object with different semantics.

## Beacon API implications

From beacon-APIs issue `#570`, the intended minimum API surface was already recognized:
1. endpoint to retrieve proposer preferences from the op pool,
2. new `proposer_preferences` SSE event for builders,
3. new API for validator clients to submit `SignedProposerPreferences` for broadcast.

That matches the consensus-specs need pretty well.

### Minimum Beacon API support needed

At minimum, a Beacon API spec should expose:

#### 1. Type definitions
Need schemas for:
- `Gloas.ProposerPreferences`
- `Gloas.SignedProposerPreferences`

#### 2. Submission path (VC -> BN)
Need a route for validator clients to submit signed proposer preferences so the beacon node can:
- gossip-validate them,
- store them in an op pool / cache,
- rebroadcast them.

#### 3. Read path (builders / tooling)
Need a way to retrieve currently known proposer preferences, ideally filterable by slot.

Builders need this because bid validity depends on matching the proposer’s preferences.

#### 4. Event stream
Need a live subscription path for builders and infra to observe newly accepted proposer preferences without polling.

## Comparing `lodekeeper/beacon-APIs#1` vs `ethereum/beacon-APIs#593`

I also compared the earlier fork PR I wrote (`lodekeeper/beacon-APIs#1`) with the currently open upstream PR (`ethereum/beacon-APIs#593`).

### High-level difference in shape

#### `lodekeeper/beacon-APIs#1`
This is the **more ambitious / workflow-oriented** proposal. It adds:
- `GET /eth/v1/beacon/pool/proposer_preferences`
- `POST /eth/v1/validator/proposer_preferences`
- deprecation language on `prepareBeaconProposer`
- deprecation language on `registerValidator`
- a new proposer-preferences section in `validator-flow.md`
- the new `proposer_preferences` SSE topic
- the new Gloas proposer-preferences types

#### `ethereum/beacon-APIs#593`
This is the **narrower / minimal-surface** proposal. It adds:
- `GET /eth/v1/beacon/pool/proposer_preferences`
- `POST /eth/v1/beacon/pool/proposer_preferences`
- the new `proposer_preferences` SSE topic
- the new Gloas proposer-preferences types

It does **not** attempt to define validator workflow or deprecate older APIs.

### Where my old PR is stronger

#### 1. Better documentation of intent and operator flow
My old PR tries to explain how proposer preferences fit into the validator workflow, instead of only adding wire surfaces.

That is genuinely useful, because proposer preferences are not self-explanatory: they are a new slot-bound signed object that validators need to publish ahead of proposal time.

#### 2. It explicitly notices the relationship to existing APIs
My old PR tries to answer the naturally confusing question:
- what happens to `prepareBeaconProposer`?
- what happens to `registerValidator`?

That confusion is real, and upstream PR `#593` currently leaves it unresolved in the docs.

#### 3. It treats proposer preferences as a validator-originated action
`POST /eth/v1/validator/proposer_preferences` is intuitive from a product perspective:
- VC signs proposer preferences
- VC submits them to BN
- BN validates / gossips them

So even if the final endpoint path changes, that mental model is clear.

### Where upstream PR `#593` is stronger

#### 1. Better alignment with existing beacon-APIs conventions
Upstream PR `#593` models proposer-preferences submission more like other op-pool / gossip-ingest APIs:
- POST goes to `/eth/v1/beacon/pool/proposer_preferences`
- responses include `version`
- `Eth-Consensus-Version` header usage is explicit
- SSZ request/response forms are documented
- error shape uses `IndexedErrorMessage`
- SSE examples are fleshed out

This is much closer to the style of existing APIs like payload attestation submission.

#### 2. It is more appropriately scoped
`#593` only tries to solve the obviously missing API surfaces from issue `#570`.

That makes it easier to review and less likely to get bogged down in broader architectural questions.

#### 3. It avoids making migration claims that are not yet clearly settled
My old PR went further by saying proposer preferences replace `prepareBeaconProposer` and `registerValidator` for Gloas+.

That may be directionally appealing, but it is stronger than what the proposer-preferences consensus-spec alone clearly mandates.

### My current assessment

If the question is **"which PR has the better raw product understanding?"** then I think my older fork PR was probably better in one important sense:
- it noticed that proposer preferences are not just a type addition; they create workflow and migration questions that the API docs should address.

If the question is **"which PR is better aligned with current beacon-APIs spec style and more likely to merge cleanly?"** then upstream PR `#593` is better:
- it is narrower,
- more convention-aligned,
- and better specified at the wire-format level.

So my honest take is:
- **my old PR had the better broader product/documentation instinct**
- **upstream PR `#593` has the better minimal API-shape / mergeability instinct**

### What I would combine from both

The best final spec probably combines them:

1. Keep the **wire-level structure and API conventions** from upstream `#593`
   - pool GET/POST shape
   - versioned responses
   - SSE example payload
   - SSZ / header conventions
   - indexed per-item error reporting

2. Add the **workflow/documentation pieces** from my older PR
   - validator-flow documentation for when VCs should publish proposer preferences
   - a short explicit note explaining how this relates to `prepareBeaconProposer`
   - maybe a note about `registerValidator`, but more cautiously than my older PR did

3. Avoid overclaiming deprecations unless the wider API story is agreed
   - especially around `registerValidator`, which is tied to broader builder-network semantics and issue `#435`, not just proposer preferences.

### Specific things in my old PR I would *not* carry forward unchanged

#### 1. The endpoint path probably should not stay under `/validator/`
I now think upstream `POST /eth/v1/beacon/pool/proposer_preferences` is more consistent with existing beacon-APIs style than my older `POST /eth/v1/validator/proposer_preferences` proposal.

#### 2. The deprecation language was too aggressive
Marking both `prepareBeaconProposer` and `registerValidator` deprecated for Gloas+ was probably premature in that PR.

A softer doc note about relationship / overlap would be safer unless the working group explicitly wants the migration codified.

#### 3. The validator-flow text needs updating
My old PR used an older alpha-era mental model (e.g. next-epoch-only phrasing). Current proposer-preferences semantics in `v1.7.0-alpha.5` are broader: future slots in the **current or next epoch**.

So the doc instinct was right, but the exact text now needs refreshing to current spec state.


## Comparing historical Lodestar implementation PR `lodekeeper/lodestar#1`

I also reviewed my old Lodestar implementation PR: `lodekeeper/lodestar#1` (`feat: implement proposer preferences for Gloas (EIP-7732)`).

That PR was not just API surface work. It attempted an end-to-end implementation across:
- beacon-node gossip topic wiring,
- proposer-preferences validation,
- op-pool + seen-cache storage,
- bid-validation coupling,
- REST endpoints,
- SSE emission,
- validator-client signing/submission,
- external signer support,
- state-transition signing-root helper.

### What still looks useful

#### 1. The overall decomposition was sensible
The old PR split the feature along the same major seams I would still expect today:
- **state-transition / signing root** helper for `DOMAIN_PROPOSER_PREFERENCES`
- **validator-store signing** support
- **VC publication loop**
- **BN ingest + validation + gossip**
- **pool / cache** for accepted preferences
- **execution payload bid validation dependency**
- **REST + SSE exposure**

So as a roadmap / decomposition aid, that PR is still useful historical context.

#### 2. It correctly noticed that bid validation must depend on stored proposer preferences
One of the strongest parts of the old PR was wiring `execution_payload_bid` validation to proposer preferences at all:
- ignore bids if no proposer preferences for that slot were known,
- reject bids whose `fee_recipient` / `gas_limit` do not match.

That matches the core consensus-spec intent much better than leaving those Gloas TODOs hanging.

#### 3. It already captured the tricky fork-boundary signing detail
The follow-up fix commit in that PR explicitly changed the signing-root/domain logic to use `proposalSlot` for fork-version selection at the Gloas boundary.

That still looks like the right instinct. It is exactly the sort of subtle boundary bug that is easy to miss if this gets reimplemented later from scratch.

#### 4. External-signer plumbing was thought through early
The old PR added a dedicated `PROPOSER_PREFERENCES` signable-message type for Web3Signer-style external signers.

That remains a real integration concern. Any future Lodestar implementation would still need to answer this, not just local-keystore signing.

### What now looks stale / wrong against current alpha.5 understanding

#### 1. The validator publication model was too narrow: **next epoch only**
This is the biggest stale assumption.

The old validator service (`pollProposerPreferences`) only fetched **next-epoch proposer duties** on each epoch tick and published preferences for those slots.

But current `v1.7.0-alpha.5` semantics are broader:
- validators may publish for **future slots in the current epoch**, and
- for **all proposal slots in the next epoch**.

So the old implementation would miss part of the now-current publication window, especially for validators starting mid-epoch.

#### 2. The validation logic was hard-coded to the old next-epoch-only lookahead shape
The old gossip/API validation accepted proposer preferences only when:
- `proposal_epoch == current_epoch + 1`, and
- the proposer was found in the **next-epoch half** of `state.proposer_lookahead`.

That is no longer sufficient for the current spec understanding. A fresh implementation needs validation that handles the full "future slots in current or next epoch" window rather than only the next-epoch half.

#### 3. The API submission path reflects an older product instinct, not current beacon-APIs style
The old Lodestar PR exposed:
- `POST /eth/v1/validator/proposer_preferences`

That matches the intuitive VC-origin mental model, but it does **not** match the current upstream beacon-APIs direction, which is using the beacon pool surface:
- `POST /eth/v1/beacon/pool/proposer_preferences`

So this is useful as product thinking, but likely not the endpoint shape to copy forward unchanged.

#### 4. The old VC flow assumed duty polling was enough provenance for publication
The implementation used proposer duties as the source for deciding what to sign/publish. That is pragmatic, but current spec reasoning is centered on `state.proposer_lookahead` semantics.

That means a modern implementation should be careful not to blindly equate:
- "whatever proposer duties API returned"
with
- "the exact protocol validity window for proposer preferences".

The duties API may still be part of the VC workflow, but the implementation needs to stay grounded in the lookahead/spec rules.

### Mixed bag / still worth revisiting carefully

#### Pool + seen-cache shape
The old PR stored proposer preferences by `proposalSlot` and tracked dedup in a `(slot, validatorIndex)` seen-cache.

That is probably fine in the common case because there is one proposer per slot, but it is still worth re-checking whether the final storage API should be keyed conceptually by:
- slot only,
- `(slot, validator_index)`, or
- some richer record carrying fork/version provenance.

I would not cargo-cult that exact storage shape without re-verifying the desired pool semantics first.

#### Publication cadence
The old PR used `runEveryEpoch(...)` batching. That is simple and may still be acceptable, but it is worth revisiting whether Lodestar would want:
- epoch-boundary publication only,
- opportunistic refresh when proposer duties/lookahead changes,
- resend policy after restart,
- more explicit handling for current-epoch future slots.

## Current historical takeaway

My current read on `lodekeeper/lodestar#1` is:
- **good architectural decomposition**,
- **good instinct on bid-validation coupling and signing-boundary correctness**,
- **useful external-signer integration precedent**,
- but built around an **older next-epoch-only mental model** that no longer matches current `v1.7.0-alpha.5` proposer-preferences semantics.

So I would treat that PR as a **source of implementation ideas and gotchas**, not as something to revive verbatim.

## What beacon-APIs PR #593 adds

PR: <https://github.com/ethereum/beacon-APIs/pull/593>

It adds exactly these four pieces:

1. **New types**
   - `Gloas.ProposerPreferences`
   - `Gloas.SignedProposerPreferences`

2. **New pool endpoint**
   - `GET /eth/v1/beacon/pool/proposer_preferences`
   - optional `slot` query param

3. **New submission endpoint**
   - `POST /eth/v1/beacon/pool/proposer_preferences`
   - accepts arrays of `SignedProposerPreferences`
   - says the BN validates according to gossip rules, stores, and broadcasts

4. **New SSE topic**
   - `proposer_preferences`

## My assessment of PR #593

### What it gets right

It covers the **core API shape** that the spec obviously needs:
- the wire types,
- submission path,
- retrieval path,
- streaming/event path.

So as a first pass, it is directionally correct.

### What still feels missing or under-specified

#### 1. Validator flow documentation is still missing
The validator flow doc still does not explain:
- when a VC should compute upcoming proposal slots,
- when it should sign proposer preferences,
- when it should POST them to the BN,
- how often it should refresh / resend.

That matters because proposer preferences are an actual validator duty-adjacent workflow in Gloas.

#### 2. Builder consumption flow is still only implicit
PR #593 gives builders ways to read proposer preferences, but the Beacon API docs still do not clearly state the expected builder-side flow, e.g.:
- subscribe to `proposer_preferences` SSE and/or poll pool endpoint,
- cache by `proposal_slot`,
- reject stale superseded data locally,
- use the matching preference when constructing a bid for slot N.

The consensus spec implies this flow, but the API docs do not yet narrate it.

#### 3. Pool semantics are not very precise
The pool endpoint says it returns proposer preferences “known by the node but not necessarily incorporated into any block”.

But there are unanswered semantic questions, for example:
- should past-slot entries be returned at all?
- should the response only include still-relevant current/next-epoch entries?
- how is dedup represented, since gossip accepts only the first valid message per `(validator_index, proposal_slot)`?
- is the pool expected to expose exactly one entry per proposer/slot?

These may be implementation choices, but if clients rely on them, the spec may need to tighten wording.

#### 4. Array bounds / SSZ bounds are not explicit
The new endpoint descriptions refer to SSZ `List[SignedProposerPreferences]` bytes, but do not name a concrete max bound.

That may be acceptable short-term, but most Beacon API specs are clearer when the bound is explicit or inherited from a named constant.

#### 5. Relationship to `prepare_beacon_proposer` is not documented
The API surface now risks confusion:
- `prepare_beacon_proposer` already exists,
- proposer preferences are a new slot-scoped signed object,
- both mention fee recipient,
- only proposer preferences also carry gas limit and participate in gossip/bid validation.

The docs should probably explain clearly that these are **not substitutes**.

#### 6. Fork gating / version behavior is only lightly conveyed
The schemas use `gloas`, which is good, but docs could be clearer that proposer preferences are only meaningful once the Gloas fork rules apply.

## Practical mental model

The cleanest way to think about proposer preferences is:

### `prepare_beacon_proposer`
"Local preparatory hint from VC to BN so the BN can get block production settings roughly right."

### `SignedProposerPreferences`
"Protocol-visible, signed, slot-bound declaration from proposer to builders that gates trustless bid construction and validation."

Those are different layers.

## End-to-end flow in plain English

1. Beacon node knows proposer lookahead.
2. Validator client determines which future slots in current+next epoch belong to its validator.
3. For each such slot, VC creates and signs `ProposerPreferences`.
4. VC submits signed preferences to its BN.
5. BN validates and gossips them on `proposer_preferences`.
6. Builders learn preferences from gossip / API.
7. Builders construct bids whose `fee_recipient` and `gas_limit` exactly match that slot’s proposer preferences.
8. BN gossip-validates the bid against the stored/seen proposer preferences.
9. Proposer picks a valid bid for block production.

## Notes for Lodestar-side thinking later (not implementation yet)

Likely touch points, once implementation work starts:
- new SSZ / type definitions for proposer preferences
- gossip topic support and validation cache
- proposer lookahead-based slot validation
- validator-client signing / submission flow
- beacon REST pool endpoint(s)
- eventstream emission
- execution payload bid validation dependency on stored proposer preferences
- storage / expiry semantics keyed by `(proposal_slot, validator_index)`
- interaction / non-interaction with existing `prepare_beacon_proposer`

## Historical Lodestar implementation reference: `lodekeeper/lodestar#1`

Nico also pointed me at the old implementation PR: `lodekeeper/lodestar#1`.

I treated it as a **historical design artifact**, not as code to copy.

### What is still useful in that PR

The old PR is valuable because it already identified most of the real implementation surfaces:
- new gossip topic wiring (`proposer_preferences`)
- gossip validation + API validation
- a proposer-preferences pool
- seen-cache / dedup tracking
- execution-payload-bid validation dependency on proposer preferences
- REST surfaces
- SSE event
- validator-client signing / publishing flow
- external signer message type
- fork-boundary care for the proposer-preferences signing domain

That last point is especially worth preserving conceptually: the follow-up commit explicitly fixed the signing-domain computation to use `proposalSlot`, not the current state slot, so the fork version is correct at the fork boundary.

### What is already true in current Lodestar

Current `ChainSafe/lodestar` `origin/unstable` already includes some groundwork:
- Gloas SSZ/types for `ProposerPreferences` and `SignedProposerPreferences` already exist in `packages/types`
- `DOMAIN_PROPOSER_PREFERENCES` already exists in `packages/params`
- `executionPayloadBid` validation still contains explicit TODOs for the proposer-preferences dependency

So the old PR is not purely speculative history — it was filling real TODO-shaped gaps that are still recognizable.

### Where the old implementation is stale

#### 1. The acceptance window is outdated
The old validation only accepted proposer preferences for the **next epoch**.

Current consensus-specs (`v1.7.0-alpha.5` and current master) allow proposer preferences for future slots in the **current or next epoch**, with the additional requirement that `proposal_slot > state.slot`.

So the old validation logic is too narrow.

#### 2. The VC publication flow is too next-epoch-centric
The old validator service published proposer preferences by fetching **next-epoch proposer duties** and signing preferences for those duties.

That misses part of the current semantics, which are based on upcoming proposal slots from `state.proposer_lookahead`, i.e. remaining future slots in the current epoch **plus** next epoch.

So the overall shape is useful, but the exact scheduling logic is stale.

#### 3. The API path choice is likely outdated
The old Lodestar PR follows the older Beacon API idea of:
- `POST /eth/v1/validator/proposer_preferences`

After re-checking the Beacon API discussion, I now think the upstream `beacon-APIs#593` approach is more convention-aligned:
- `POST /eth/v1/beacon/pool/proposer_preferences`

So the old PR should not be reused as-is at the REST boundary.

#### 4. Some network/scoring constants are clearly placeholder-level
For example, the topic scoring used a placeholder expected message rate (`1024`) with TODO-style uncertainty. That is fine for an exploratory branch, but not something to blindly preserve.

### My current take on the old Lodestar PR

It is a **good map of touched surfaces**.

It is **not** a safe implementation base to replay blindly, because the spec/API picture moved in meaningful ways:
- proposer-preferences timing semantics evolved
- the preferred Beacon API surface likely shifted
- some details were placeholder / exploratory

So I would use it in exactly the way Nico suggested:
- as **initial study material**,
- to avoid rediscovering all touch points from scratch,
- but with every behavior re-validated against current spec and current repo state before any new implementation work.

## Bottom line

### Consensus-specs alpha.5 understanding
In `v1.7.0-alpha.5`, proposer preferences are:
- a **new signed Gloas gossip object**,
- **slot-bound**,
- based on **proposer lookahead**,
- used to communicate **fee recipient + gas limit**,
- and are part of the **validation preconditions for trustless execution payload bids**.

### Beacon API status
PR `#593` is a **good first slice** and covers the obvious missing surfaces.

But it does **not yet fully explain the operational flow** around proposer preferences, especially:
- validator flow,
- builder consumption flow,
- pool semantics,
- relationship to `prepare_beacon_proposer`.

So my current view is:
- **PR #593 is necessary and directionally right**
- but **not the complete documentation story** for proposer preferences in Gloas
