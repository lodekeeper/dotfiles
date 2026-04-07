# Ethereum Gloas ePBS Timing Analysis

**Source:** ChatGPT Deep Research (API extraction)
**Conversation ID:** 69d4502e-9e94-8332-8e82-a204757ac643
**Assistant messages:** 4
**Model:** gpt-5-4-pro
**Status:** finished_successfully
**Total chars:** 10264

---

I’m pulling the current Gloas/EIP-7732 timing definitions and timing functions first so I can map the exact deadlines and message ordering onto the epoch-boundary case, rather than relying on memory.

I’ve confirmed the current draft’s core asymmetry: ordinary attestations are due at 25% of a 12-second slot (3,000 ms), while PTC messages are due at 75% (9,000 ms). The spec also appears to force current-slot attestations to encode `index = 0`, so I’m now checking whether any fork-choice or prior-slot mechanism provides an escape hatch.

I’m also seeing no separate millisecond deadline for “payload reveal by X” in the current draft; the practical constraint is just that it arrives in time for PTC members to vote by their own 9,000 ms cutoff. I’m verifying the exact helper-function edge semantics now, because whether those timely checks are strict or inclusive matters for the boundary-slot analysis.

After checking the current draft Gloas specs, the cleanest reading is: **same-slot ordinary attestations intentionally do not vote FULL vs EMPTY for the slot’s own block.** They vote the root, while the payload dimension stays effectively `PENDING` until later. The validator guide says a same-slot attestation must set `data.index = 0`; fork-choice validation enforces that same rule; the beacon-chain reward logic special-cases same-slot attestations so `data.index == 0` does **not** mean “empty”; and `get_ancestor` returns `PAYLOAD_STATUS_PENDING` when the block is already at the queried slot, with `get_checkpoint_block` then keeping only the root. That is why your epoch-boundary concern is real: the current-slot checkpoint root is not payload-qualified at attestation time. citeturn209050view0turn209050view1turn209050view2turn531213view0

On mainnet preset, `SLOT_DURATION_MS` is 12,000 ms, and slot-component helpers use `basis_points * SLOT_DURATION_MS // 10000`. Gloas sets attestation at 2500 bp, aggregate at 5000 bp, sync message at 2500 bp, contribution at 5000 bp, and payload attestation at 7500 bp, so the concrete deadlines are **3,000 / 6,000 / 3,000 / 6,000 / 9,000 ms** respectively. Ordinary attesters broadcast when they have the valid block or when 3,000 ms have elapsed since slot start, whichever comes first; PTC members broadcast within the first 9,000 ms; and `record_block_timeliness` tracks two separate notions of timeliness for a block, one against the 3,000 ms threshold and one against the 9,000 ms threshold. citeturn978246view0turn682418view8turn863589view0turn682418view9turn682418view1turn252238view1

1. **Could attestation timing be modified so ordinary attesters know payload status before voting? Could the PTC be leveraged first?**

In the **current** spec, no. By the time an ordinary attester must speak (no later than 3,000 ms), there is no protocol-defined PTC outcome yet, because PTC messages are due by 9,000 ms, not 3,000 ms. More importantly, even if a node locally sees the payload envelope early, same-slot ordinary attestations are still required to set `data.index = 0`, so earlier local knowledge does not change the attestation semantics. citeturn682418view1turn209050view0turn209050view1

As a **redesign**, yes, you could do it by delaying ordinary attestations until after payload/PTC, or by moving PTC much earlier, or by creating a separate early PTC certificate that ordinary attesters consume. But that would be a different protocol. Current PTC messages only attest “I saw the envelope / blob data,” not full execution validity, and the EIP rationale explicitly uses PTC to keep execution validation off the hot path. Even fork-choice’s `is_payload_timely` is not “PTC vote only”: it also requires the node to actually have the payload locally. citeturn209050view5turn802282view1turn252238view3

2. **Could the slot structure be reordered, e.g. payload before attestation?**

As a protocol redesign, yes. But that would cut against the main point of Gloas. The EIP rationale says Gloas is trying to remove execution validation from the critical pre-attestation path, giving the next proposer 6 seconds and other validators 9 seconds to validate the payload after the consensus block has already propagated. Moving “payload before ordinary attestation” would put payload propagation and likely more validation work back onto that hot path. citeturn802282view0turn802282view1

One nuance: the current draft does **not** define a separate fixed “payload reveal happens at X ms” phase the same way it defines attestation/PTC deadlines. What it does say is that once the proposer publishes the valid beacon block, the builder is then expected to broadcast the corresponding `SignedExecutionPayloadEnvelope`, and the p2p spec defines how `execution_payload` messages are validated on gossip. So the hard ordering is “block first, then envelope can appear,” but the spec does not give a helper like `get_payload_reveal_due_ms`. Reordering reveal earlier therefore would still not fix the ordinary-attestation issue unless you also changed the same-slot `data.index = 0` rule. citeturn182978view0turn182978view2turn863589view0

3. **What are the exact Gloas timing constraints?**

The helper deadlines are:

- `get_attestation_due_ms` = **3,000 ms**
- `get_aggregate_due_ms` = **6,000 ms**
- `get_sync_message_due_ms` = **3,000 ms**
- `get_contribution_due_ms` = **6,000 ms**
- `get_payload_attestation_due_ms` = **9,000 ms** citeturn978246view0turn682418view8turn863589view0

There are two finer points that matter for your question. First, validators broadcast ordinary attestations when they have the valid block or when 3,000 ms has elapsed, whichever is earlier. Second, `record_block_timeliness` uses a strict `< threshold` test, so “timely for attestation” means seen **before** 3,000 ms and “timely for PTC” means seen **before** 9,000 ms. Fork-choice also delays the effect of an attestation until the next slot (`current_slot >= attestation.slot + 1`). citeturn682418view9turn252238view1turn863589view0

For payload availability specifically, the beacon state has an `execution_payload_availability` bitvector. The next slot’s bit is reset during `process_slot`, and the current slot’s bit is set to `1` only when `process_execution_payload` succeeds for that slot. Past-slot attestations compare `data.index` against that recorded availability bit; same-slot attestations bypass that check entirely, assert `data.index == 0`, and treat payload matching as true. So the spec really does make “same-slot payload status” unavailable to ordinary attestation logic. citeturn983342view0turn983342view1turn983342view2turn209050view2

4. **Can the previous slot’s PTC vote be used to infer the current slot’s payload status?**

Not for the **current slot’s own payload**. PTC votes are slot-specific: `on_payload_attestation_message` only updates votes when `data.slot == state.slot`, and on wire the PTC message must be for the current slot. So the previous slot’s PTC can certify the previous slot’s block, not the current slot’s block. citeturn252238view5

What the previous slot’s PTC **does** do is influence next-slot handling of the **previous** slot. Gloas uses `should_extend_payload` and `get_payload_status_tiebreaker` to choose between FULL and EMPTY for the previous slot’s root when deciding what to extend in the current slot. Also, the current slot’s block lets you infer the **parent’s** payload status via `get_parent_payload_status`, because the child bid commits to the parent execution block hash. But that only tells you whether slot `N-1` was FULL or EMPTY; it does not tell you whether slot `N` itself will be FULL or EMPTY. citeturn209050view3turn209050view4turn531213view0

5. **Could attesters vote on a deferred payload status, e.g. of the previous epoch’s last slot?**

Not with the current attestation format and semantics. For past-slot votes, `data.index` is interpreted as the payload status of `data.beacon_block_root`; if `data.index == 1`, fork-choice requires the payload to be known locally; and reward processing compares past-slot `data.index` against `state.execution_payload_availability`. Same-slot is special-cased and does not carry payload status at all. So you cannot reuse the existing `index` field to mean “payload status of some older boundary ancestor” without redefining the protocol. citeturn209050view1turn209050view2turn983342view0turn983342view2

What *is* already possible is narrower: if the validator has **not** seen the current epoch-boundary block by its attestation deadline, it can attest to an older head, and then the target/root may indeed be the previous epoch’s last slot, whose payload status is already knowable and can be encoded normally because that block is in the past. But that is just an ordinary attestation to an older head. It is **not** a deferred payload-status vote about the current-slot boundary block. In effect, Gloas already “defers” the payload dimension for same-slot votes by treating it as pending and resolving FULL vs EMPTY later through payload processing and PTC-informed fork-choice. citeturn312882view0turn531213view0turn209050view2

One caveat from the current draft: `p2p-interface.md` appears inconsistent with the validator/fork-choice/beacon-chain specs. The p2p doc currently says to reject same-slot attestations and aggregates with `data.index == 0`, while the validator, fork-choice, and beacon-chain docs all require same-slot `data.index == 0` and special-case it. For the timing question you raised, the latter three documents line up cleanly and strongly indicate the intended behavior is: **ordinary same-slot attestations do not carry current-slot payload status**. citeturn955574view0turn955574view1turn209050view0turn209050view1turn209050view2

So the shortest synthesis is: **under the current Gloas draft, epoch-boundary attesters are not supposed to know or express the current boundary block’s payload status in their ordinary attestation.** The protocol treats that status as pending, resolves it later via payload reveal + PTC, and uses the result starting in the following slot, especially for previous-slot FULL/EMPTY decisions. citeturn531213view0turn209050view2turn209050view3



