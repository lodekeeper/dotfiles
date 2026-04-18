# Test Cases for Deferred Payload Processing (DPR)

Proposed by Potuz during the ePBS breakout call (2026-04-17).

## 1. Epoch-boundary block followed by missing slots

**Setup:** A block at slot 31 (last slot of epoch 0) with a payload containing many requests — in particular consolidation/switch-to-compounding requests.

**Variants — gap duration after slot 31:**

| Case | Missing gap     | Next block slot |
|------|-----------------|-----------------|
| A    | 1 epoch (32 slots)  | Slot 63         |
| B    | 2 epochs (64 slots) | Slot 95         |
| C    | 5 epochs (160 slots)| Slot 191        |

**Variants — next block type:**

| Sub-case | Next block        |
|----------|-------------------|
| i        | Full (with payload) |
| ii       | Empty (no payload)  |

This gives **6 combinations** (A-i, A-ii, B-i, B-ii, C-i, C-ii).

**What to verify:**
- State transition produces identical post-state across all clients
- Deferred requests from slot 31's payload are applied correctly after the gap
- Epoch processing (multiple transitions) does not corrupt or lose pending requests
- Validator balances, effective balances, and registry remain consistent

> *"Most of the problems we found on, that could be bugs on the current implementation, the current specs, are around a boundary block that is missing and then a full epoch or two or even five epochs of missing blocks. Those are the tests that actually trigger most of the problems, including the current problems in the current proposal."* — Potuz

## 2. Switch-to-compounding immediate effective balance change

**Setup:**
- A validator with >32 ETH balance (e.g. 35 ETH) and `0x01` withdrawal credentials (BLS)
- Effective balance is 32 ETH (capped for non-compounding validators)
- The validator submits a **switch-to-compounding request** in the last payload of the epoch (slot 31)

**Why this is insidious:**
- Switch-to-compounding is the **only** request type that immediately applies an effective balance change at the very next epoch boundary
- All other request types (withdrawals, deposits, consolidations) take at least 5 epochs to affect effective balance
- With immediate application, the epoch transition at slot 32 would change the validator's effective balance from 32 to 35 ETH
- This affects balance-dependent computations: proposer lookahead, sync committee, PTC assignments

**What to verify:**
- Under DPR, the request is deferred (not applied until the child block processes it)
- The effective balance does NOT change at the immediate epoch boundary
- The delay is at least one full epoch (not just one slot)
- If there are missed slots after slot 31, the delay can be significantly longer

> *"I think this is already a bug in the spec. I think this is just an attack vector in the spec. But I think my change resolves that issue."* — Potuz
>
> *"If you are in the last slot of the epoch, you get delayed by a whole epoch."* — Nico

## 3. Related observations from the call

- **Dependent root** is fully restored by DPR — no spec changes needed
- **Checkpoint state** semantics are restored — the open 5-month API issue goes away
- **Bandwidth overhead:** execution requests are sent twice (once in payload gossip, once in next beacon block). Estimated ~0.5 MB worst case (2,500 max deposits), before compression. Analysis pending from Raul.
- **Builder payment enforcement:** current PR does not enforce builder payment — builder could get payload included without paying. Needs spec fix.
- **`process_execution_payload` refactor:** Potuz suggested removing it entirely and moving logic to forkchoice handler, since it no longer modifies state. Nico agreed to make this change.
