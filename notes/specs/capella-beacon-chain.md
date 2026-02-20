# Capella Beacon Chain — Spec Study Notes

*Spec: `consensus-specs/specs/capella/beacon-chain.md`*
*Studied: 2026-02-17*

## Overview

Capella introduces validator withdrawals — the ability to move ETH from the beacon chain back to the execution layer. Three key features:

1. **Automatic withdrawals** — Validators that are withdrawable get their balances swept to their ETH1 withdrawal address
2. **Partial withdrawals** — Validators with excess balance above `MAX_EFFECTIVE_BALANCE` get the excess withdrawn
3. **BLS-to-execution credential changes** — Validators can switch from BLS withdrawal credentials (0x00) to ETH1 address credentials (0x01) to enable withdrawals
4. **Historical summaries** — Replace `historical_roots` with a new accumulator structure

## New Types

### `Withdrawal`
```
index: WithdrawalIndex
validator_index: ValidatorIndex
address: ExecutionAddress
amount: Gwei
```

### `BLSToExecutionChange` / `SignedBLSToExecutionChange`
Message + BLS signature for changing withdrawal credentials.

### `HistoricalSummary`
Replaces `HistoricalBatch` — contains `block_summary_root` and `state_summary_root`.

## Withdrawal Mechanics

### Sweep Algorithm (`get_expected_withdrawals`)
Each block, the protocol sweeps through validators starting from `next_withdrawal_validator_index`:
- Checks up to `MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP` (16,384) validators
- Creates up to `MAX_WITHDRAWALS_PER_PAYLOAD` (16) withdrawals per block
- **Fully withdrawable**: Has 0x01 credentials, `withdrawable_epoch <= current_epoch`, balance > 0 → withdraw entire balance
- **Partially withdrawable**: Has 0x01 credentials, effective_balance == MAX_EFFECTIVE_BALANCE, balance > MAX_EFFECTIVE_BALANCE → withdraw excess

### Index Updates
After processing:
- `next_withdrawal_index` = last withdrawal's index + 1
- `next_withdrawal_validator_index`:
  - If all 16 withdrawal slots filled: start after last validator processed
  - Otherwise: advance by `MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP` (full sweep happened, just not enough qualified)

### Verification
Block's `execution_payload.withdrawals` MUST exactly match `get_expected_withdrawals()` — deterministic.

## BLS-to-Execution Change
Allows validators with 0x00 (BLS) credentials to switch to 0x01 (ETH1) credentials:
1. Verify validator exists and has BLS prefix
2. Verify `withdrawal_credentials[1:] == hash(from_bls_pubkey)[1:]`
3. Verify BLS signature (fork-agnostic domain using genesis validators root)
4. Set new credentials: `0x01 || 00*11 || to_execution_address`

## State Changes
New fields in `BeaconState`:
- `next_withdrawal_index: WithdrawalIndex` — global withdrawal counter
- `next_withdrawal_validator_index: ValidatorIndex` — sweep cursor
- `historical_summaries: List[HistoricalSummary]` — new accumulator

`historical_roots` is frozen (no new entries appended).

## Lodestar Implementation

### `processWithdrawals`
**Location:** `packages/state-transition/src/block/processWithdrawals.ts`

- Handles Capella through Gloas (EPBS), with fork-specific branches
- For pre-Gloas: Compares expected withdrawals against payload (full or blinded via root comparison)
- For Gloas: Stores expected withdrawals in state for later verification in `processExecutionPayloadEnvelope`
- `applyWithdrawals()`: Simple loop calling `decreaseBalance()` for each withdrawal

### `getExpectedWithdrawals`
**Location:** Same file, line 403+

Comprehensive implementation covering:
- Capella: Basic validator sweep
- Electra: Adds `pendingPartialWithdrawals` queue (EIP-7002 EL-triggered exits)
- Gloas: Adds builder withdrawals and builder sweep

### `processBlsToExecutionChange`
**Location:** `packages/state-transition/src/block/processBlsToExecutionChange.ts`

Clean implementation:
- Validates prefix, pubkey hash match, BLS signature
- `isValidBlsToExecutionChange()` separated out for reuse (gossip validation)
- Uses `@chainsafe/as-sha256` for digest, not the full hash_tree_root

### Historical Summaries
Handled in epoch processing — appends to `historical_summaries` every `SLOTS_PER_HISTORICAL_ROOT` slots.

## Observations

1. **Withdrawal sweep is deterministic** — Both proposer and verifier compute the same withdrawals independently. No need to transmit withdrawal requests; the protocol sweeps automatically.

2. **Evolution through forks is visible** — `processWithdrawals` has grown significantly from Capella → Electra → Gloas, with each fork adding new withdrawal sources (EL-triggered exits, builder payments). The base sweep logic remains the same.

3. **Blinded block support** — Lodestar correctly handles both full payloads (compare withdrawal-by-withdrawal) and blinded payloads (compare `withdrawalsRoot`).

4. **No issues found** — Implementation is clean and well-tested. The withdrawal sweep algorithm matches the spec precisely.

## Cross-references
- Electra extends withdrawals with pending partial withdrawals (EIP-7002)
- Gloas extends with builder withdrawals (EIP-7732)
- Engine API: `engine_forkchoiceUpdatedV2` adds withdrawal `PayloadAttributes`
