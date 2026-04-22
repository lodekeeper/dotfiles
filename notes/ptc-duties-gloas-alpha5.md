# PTC duties in Gloas (consensus-specs v1.7.0-alpha.5)

Date: 2026-04-22
Scope: study only, no implementation
Sources:
- `~/ethereum-repos/consensus-specs` tag `v1.7.0-alpha.5`
- `~/ethereum-repos/beacon-APIs` master + `pr-593` for API drift notes

## 1) What the PTC is

In Gloas, some validators are selected per slot into the **Payload Timeliness Committee (PTC)**.
Their job is to attest, within the assigned slot, whether:
- the beacon block for that slot was seen,
- the execution payload envelope for that block was seen (`payload_present`), and
- the blob data for that block was available (`blob_data_available`).

These PTC votes feed fork choice and help decide whether the next proposer should extend the parent block's **full** payload or its **empty** variant.

Relevant constants in alpha.5:
- `PTC_SIZE = 512`
- `PAYLOAD_ATTESTATION_DUE_BPS = 7500` → PTC messages are due by **75% of the slot**
- `PAYLOAD_TIMELY_THRESHOLD = PTC_SIZE // 2 = 256`
- `DATA_AVAILABILITY_TIMELY_THRESHOLD = PTC_SIZE // 2 = 256`

Important nuance: fork choice checks `sum(votes) > threshold`, so this is a **strict majority**, not `>= 256`.

## 2) How the PTC is selected in alpha.5

### Per-slot committee construction

`compute_ptc(state, slot)` does the following:
1. Computes a seed from `get_seed(state, epoch, DOMAIN_PTC_ATTESTER)` and the `slot`.
2. Concatenates **all beacon attester committees for that slot**, in order.
3. Runs `compute_balance_weighted_selection(..., size=PTC_SIZE, shuffle_indices=False)` over that concatenated list.

Implications:
- PTC membership is **slot-local**.
- It is sampled from the full attesting population for that slot, not from a separate validator universe.
- Selection is **balance-weighted**.
- The result is a fixed-length vector of 512 validator indices.

### Cached window / lookahead

`get_ptc(state, slot)` does not recompute the committee directly. It reads from a cached `state.ptc_window`.

The cached window covers:
- the previous epoch,
- the current epoch,
- and future epochs up to `MIN_SEED_LOOKAHEAD`.

At epoch processing, `process_ptc_window(state)` shifts the window forward and computes the newly needed future epoch.

### Validator assignment lookup

Alpha.5 validator duties are expressed through:

```python
def get_ptc_assignment(state, epoch, validator_index) -> Optional[Slot]
```

Key behavior:
- Allowed only for `epoch <= get_current_epoch(state) + MIN_SEED_LOOKAHEAD`
- The validator checks every slot in the target epoch and returns the slot where it is in `get_ptc(state, slot)`
- If no assignment exists, returns `None`

### Operational timing in alpha.5

The validator spec is explicit:
- call `get_ptc_assignment` **at the start of each epoch**
- fetch / plan for the **next epoch** (`current_epoch + 1`)

So, in alpha.5, PTC duties are a **lookahead duty**, not a same-epoch just-in-time duty.

## 3) Validator duty lifecycle in Gloas alpha.5

### Epoch start

At the beginning of epoch `E`, the validator should determine whether it has a PTC assignment in epoch `E + 1`.

### Assigned slot

If the validator is assigned to slot `S`, then during slot `S` it should prepare and broadcast a `PayloadAttestationMessage` before `get_payload_attestation_due_ms()` (75% into the slot).

### Message construction rules

Per the alpha.5 validator spec:
- If the validator has **not seen any beacon block** for the assigned slot, it should **not submit** a PTC attestation.
- `data.beacon_block_root` = hash tree root of the beacon block seen for that slot
- `data.slot` = assigned slot
- `data.payload_present = True` iff a previously seen `SignedExecutionPayloadEnvelope` references that block root
- `data.blob_data_available = True` iff blob data is available for that block
- `payload_attestation_message.validator_index` = the validator's index
- Signature is over **`PayloadAttestationData` only**, using `DOMAIN_PTC_ATTESTER`

Important nuance:
- the validator does **not** sign the `validator_index`, only the data payload
- the network message is a per-validator message; proposers later aggregate multiple matching messages into `PayloadAttestation`

### Gossip rules

`payload_attestation_message` gossip validation requires:
- the slot is the **current slot** (with `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance)
- it is the first valid message from that validator index
- the referenced block is known / passes validation
- the validator index belongs to `get_ptc(state, data.slot)` for the head state at the current slot
- the signature is valid

## 4) What proposers do with PTC messages

When proposing block `N` at slot `S`, the proposer may include aggregate payload attestations for the parent block at slot `S - 1`.

### Inclusion rules

The proposer:
- listens to the global `payload_attestation_message` gossip topic
- groups messages with the same `PayloadAttestationData`
- aggregates them into `PayloadAttestation`
- fills `aggregation_bits` using the validator positions relative to `get_ptc(state, Slot(block_slot - 1))`
- may include up to `MAX_PAYLOAD_ATTESTATIONS`

### Block processing rules

`process_payload_attestation(state, payload_attestation)` checks:
- `data.beacon_block_root == state.latest_block_header.parent_root`
- `data.slot + 1 == state.slot`
- the aggregate signature is valid via `is_valid_indexed_payload_attestation`

So payload attestations are always about the **parent block** and the **previous slot**.

## 5) How PTC affects fork choice

Fork choice stores two per-block vote vectors:
- `payload_timeliness_vote[root]`
- `payload_data_availability_vote[root]`

Each is a `Vector[boolean, PTC_SIZE]`.

When PTC messages arrive, `on_payload_attestation_message(...)` updates the vote bits for the corresponding block root.

Then fork choice derives:
- `is_payload_timely(store, root)`
- `is_payload_data_available(store, root)`

Both require two things:
1. the local node has actually verified / stored the payload envelope (`is_payload_verified(store, root)`), and
2. a strict majority of the PTC voted `True`.

### Why this matters

`should_extend_payload(store, root)` decides whether the next proposer should extend the parent's **full** payload.

It returns true only if:
- the payload is locally verified, and
- both payload timeliness and data availability have the PTC majority,

or proposer-boost fallback conditions apply.

So the PTC is not just informational; it directly affects the full-vs-empty payload branch used by the next proposer and by fork-choice tie-breaking.

## 6) Beacon API surfaces needed for PTC duties

From `~/ethereum-repos/beacon-APIs`:

### A. Get duties

`POST /eth/v1/validator/duties/ptc/{epoch}`

Request body:
- array of validator indices

Response:
- `dependent_root`
- `execution_optimistic`
- `data: PtcDuty[]`

`PtcDuty` currently contains:
- `pubkey`
- `validator_index`
- `slot`

This is the validator-facing assignment surface.

### B. Produce the attestation data to sign

`GET /eth/v1/validator/payload_attestation_data/{slot}`

Returns `PayloadAttestationData`:
- `beacon_block_root`
- `slot`
- `payload_present`
- `blob_data_available`

This effectively moves the local observation logic into the beacon node API surface: the validator client asks the beacon node to produce the exact data object it should sign.

### C. Submit signed PTC messages

`POST /eth/v1/beacon/pool/payload_attestations`

Request body:
- array of `PayloadAttestationMessage`

Node behavior:
- validate each message according to gossip rules
- store in pool
- broadcast globally

Despite the pool path name, the POST is for **messages**, not aggregated `PayloadAttestation` objects.

### D. Proposer / debugging retrieval from pool

`GET /eth/v1/beacon/pool/payload_attestations?slot=...`

Returns aggregated `PayloadAttestation` objects currently known to the node.

This is useful for proposer-side logic and observability.

## 7) Beacon API event / polling support around PTC duties

The API surface already has useful support for the validator-side duty loop:

### Needed for duty stability / refresh

SSE `head` event:
- carries `previous_duty_dependent_root`
- carries `current_duty_dependent_root`

This is how duty consumers check whether previously fetched duties are still valid.

SSE `chain_reorg` event:
- useful for re-fetch / refresh logic when the head changes materially

### Needed for the "wait until payload+blobs are available" step

SSE `execution_payload_available` event:
- explicitly says the node has verified that execution payload + blobs for a block are available and ready for payload attestation

This is the cleanest wake-up signal for PTC validators.

### Optional polling fallback

`GET /eth/v1/beacon/execution_payload_envelope/{block_id}`
- can be used to poll envelope availability for a block

And `producePayloadAttestationData` itself can be polled if an implementation wants the beacon node to decide readiness.

## 8) What looks needed / important in beacon-APIs for alpha.5 specifically

### Already present / broadly sufficient

For alpha.5-style validator duties, the core surfaces basically exist:
- PTC duties endpoint
- payload attestation data production endpoint
- payload attestation message submission endpoint
- pool retrieval endpoint
- head / reorg / execution_payload_available events

So from a surface-area perspective, beacon-APIs is already close to what PTC duties need.

### Important alpha.5 semantic constraint: next-epoch lookahead

This is the main thing I would preserve if implementing against alpha.5:
- the **consensus-specs alpha.5 validator flow is next-epoch oriented**
- duties are planned at epoch start for **`current_epoch + 1`**

That means the duty API should support this lookahead shape and its dependent-root validation logic.

### API drift I noticed

There is already drift between beacon-APIs `master` and `pr-593`:

- `master` says:
  - epoch should only be allowed **1 epoch ahead**
  - duty validation may use `event.current_duty_dependent_root` when `head_epoch + 1 == target_epoch`
  - validator-flow says fetch PTC duties for **epoch + 1**

- `pr-593` changes this toward:
  - duties for the **current epoch** only
  - removes the `current_duty_dependent_root` case from the PTC duties description
  - changes validator-flow text from **next epoch** to **current epoch**

For **alpha.5**, the `master` wording matches the consensus-specs validator text better than `pr-593`.

### Minor documentation debt

Several beacon-APIs schema descriptions / validator-flow links still hardcode links to older alpha tags (for example `v1.7.0-alpha.2`).
That is documentation drift, not a structural blocker, but it is worth cleaning up.

## 9) My current synthesis

If we target **consensus-specs alpha.5** exactly, my mental model is:

1. At epoch start, validator asks for **next epoch** PTC duty.
2. During assigned slot, validator waits until payload+blob availability is known (prefer `execution_payload_available` SSE, or poll).
3. Validator asks beacon node for `PayloadAttestationData(slot)`.
4. Validator signs that data with `DOMAIN_PTC_ATTESTER`.
5. Validator submits `PayloadAttestationMessage`.
6. Beacon node gossips it, proposers aggregate it, and the next slot's proposer may include the aggregate in the block.
7. Fork choice uses those votes plus local payload verification to decide whether the parent payload is timely / blob-available and whether to extend the full payload.

## 10) Biggest takeaways for later Lodestar work

- The PTC duty is **not** just another attester duty; it feeds **payload branch selection** in fork choice.
- The validator-side unit of work is a **single signed `PayloadAttestationMessage`** per assigned slot.
- The proposer-side unit of work is an **aggregated `PayloadAttestation`** for the parent slot's block.
- The clean validator API trio is:
  - `duties/ptc`
  - `payload_attestation_data/{slot}`
  - `beacon/pool/payload_attestations` (submit)
- The main semantic question to keep straight is **alpha.5 next-epoch lookahead** vs later API/spec drift toward **current-epoch** duties.
