# Electra Consensus Specs — Study Notes

*Studied: 2026-02-18*
*Spec files: `specs/electra/beacon-chain.md`, `specs/electra/p2p-interface.md`, `specs/electra/validator.md`, `specs/electra/fork.md`*
*Lodestar: `packages/state-transition/src/`, `packages/types/src/electra/`*

---

## Overview

Electra is the current mainnet consensus fork. It bundles **5 EIPs**:

1. **EIP-6110**: Supply validator deposits on chain (deposit requests from EL)
2. **EIP-7002**: Execution layer triggerable exits (withdrawal requests from EL)
3. **EIP-7251**: Increase MAX_EFFECTIVE_BALANCE (compounding validators, consolidations)
4. **EIP-7549**: Move committee index outside Attestation (attestation format change)
5. **EIP-7691**: Blob throughput increase (9 blobs per block, 9 subnets)

These are substantial changes — Electra is arguably the most complex fork since Bellatrix (The Merge).

---

## Key Constants & Presets

### New Constants
| Name | Value | Notes |
|------|-------|-------|
| `UNSET_DEPOSIT_REQUESTS_START_INDEX` | `2^64 - 1` | Sentinel: no EL deposits processed yet |
| `FULL_EXIT_REQUEST_AMOUNT` | `0` | Special amount meaning "full exit" |
| `COMPOUNDING_WITHDRAWAL_PREFIX` | `0x02` | New withdrawal credential prefix |
| `DEPOSIT_REQUEST_TYPE` | `0x00` | EIP-7685 request type |
| `WITHDRAWAL_REQUEST_TYPE` | `0x01` | EIP-7685 request type |
| `CONSOLIDATION_REQUEST_TYPE` | `0x02` | EIP-7685 request type |

### Modified/New Presets
| Name | Value | Significance |
|------|-------|-------------|
| `MIN_ACTIVATION_BALANCE` | 32 ETH | Replaces `MAX_EFFECTIVE_BALANCE` for activation threshold |
| `MAX_EFFECTIVE_BALANCE_ELECTRA` | 2048 ETH | For compounding validators (64x increase!) |
| `MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA` | 4096 | Reduced from 32 (harsher slashing) |
| `WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA` | 4096 | Reduced from 512 (bigger rewards) |
| `MAX_ATTESTATIONS_ELECTRA` | 8 | Down from 128 (but each covers multiple committees) |
| `MAX_ATTESTER_SLASHINGS_ELECTRA` | 1 | Down from 2 |
| `MAX_BLOBS_PER_BLOCK_ELECTRA` | 9 | Up from 6 (EIP-7691) |
| `MAX_PENDING_DEPOSITS_PER_EPOCH` | 16 | New queue processing limit |

### Pending Queue Limits (New)
- `PENDING_DEPOSITS_LIMIT`: 134M entries
- `PENDING_PARTIAL_WITHDRAWALS_LIMIT`: 134M entries
- `PENDING_CONSOLIDATIONS_LIMIT`: 262K entries

---

## EIP-7251: MaxEB (Increase MAX_EFFECTIVE_BALANCE)

This is the biggest and most complex change in Electra. It introduces:

### Compounding Validators (`0x02` prefix)
- Validators with `0x02` withdrawal credential prefix can have effective balance up to **2048 ETH**
- Regular `0x01` validators still capped at 32 ETH (`MIN_ACTIVATION_BALANCE`)
- `get_max_effective_balance()` returns 2048 ETH for compounding, 32 ETH for regular

### Validator Consolidations
- Two validators can merge: source's stake moves to target
- Target MUST have compounding (`0x02`) credentials
- Source exits, balance transferred after withdrawable epoch
- Triggered via EL consolidation requests (`ConsolidationRequest`)
- Special case: `source == target` → "switch to compounding" (upgrade `0x01` → `0x02`)

### Balance-Based Churn
- Replaces count-based activation/exit queues with **balance-based churn**
- `get_balance_churn_limit()`: total churn per epoch
- `get_activation_exit_churn_limit()`: capped at 256 ETH/epoch for activations+exits
- `get_consolidation_churn_limit()`: remainder goes to consolidations
- `compute_exit_epoch_and_update_churn()`: tracks balance consumption across epochs
- State fields: `exit_balance_to_consume`, `earliest_exit_epoch`, `consolidation_balance_to_consume`, `earliest_consolidation_epoch`

### Pending Deposits Queue
- Deposits no longer applied immediately — queued in `state.pending_deposits`
- `process_pending_deposits()` runs during epoch processing
- Respects churn limits, finalization, and ordering constraints
- Deposits for exiting validators are **postponed** (re-appended to queue)
- `deposit_balance_to_consume` tracks remaining churn budget

### Modified Proposer/Sync Committee Selection
- Uses 16-bit random value (was 8-bit) for fair selection with high-balance validators
- Probability proportional to `effective_balance / MAX_EFFECTIVE_BALANCE_ELECTRA`

### Modified Slashing
- `MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA = 4096` (was 32 in Bellatrix)
- `WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA = 4096` (was 512)
- Slashing penalty: `effective_balance / 4096` (much smaller fraction)
- Whistleblower reward: `effective_balance / 4096`

### Lodestar Implementation
- **`util/electra.ts`**: `hasCompoundingWithdrawalCredential()`, `hasExecutionWithdrawalCredential()`, `switchToCompoundingValidator()`, `queueExcessActiveBalance()`
- **`epoch/processPendingDeposits.ts`**: Full pending deposits processing with chunked iteration
- **`block/processConsolidationRequest.ts`**: Handles consolidation + switch-to-compounding
- **`block/processWithdrawalRequest.ts`**: Full/partial withdrawal request processing
- **`block/processWithdrawals.ts`**: Modified to handle pending partial withdrawals, `get_max_effective_balance()` for partial withdrawal thresholds
- **`block/initiateValidatorExit.ts`**: Uses balance-based churn
- **`block/slashValidator.ts`**: Updated quotients
- **`epoch/processRegistryUpdates.ts`**: Simplified — activations computed inline
- **`epoch/processEffectiveBalanceUpdates.ts`**: Uses `get_max_effective_balance()`
- **`epoch/processSlashings.ts`**: Updated penalty calculation
- **`slot/upgradeStateToElectra.ts`**: Complex migration — handles pre-activation validators, compounding credential queue, churn initialization

#### Notable Implementation Detail: `upgradeStateToElectra`
The fork transition is the most complex part. It must:
1. Copy all Deneb state fields
2. Initialize new fields (`depositRequestsStartIndex`, churn tracking, etc.)
3. Find `earliestExitEpoch` by scanning all validators
4. Move pre-activation validators (FAR_FUTURE activation) to `pendingDeposits` queue
5. Sort pre-activation by `activationEligibilityEpoch` (deterministic ordering)
6. For compounding validators, queue excess balance above 32 ETH
7. Compute initial churn limits using temporary cached state

---

## EIP-6110: Supply Validator Deposits On Chain

### Key Changes
- Validator deposits come from EL via `DepositRequest` in `ExecutionRequests`
- `deposit_requests_start_index`: tracks first EL deposit seen
- Transition period: old Eth1 bridge deposits processed first, then EL deposits
- Once `eth1_deposit_index >= deposit_requests_start_index`, Eth1 deposits disabled
- `process_deposit_request()`: Creates `PendingDeposit` with `slot = state.slot`
- Bridge deposits use `slot = GENESIS_SLOT` to distinguish

### Lodestar Implementation
- **`block/processDepositRequest.ts`**: Routes to validator or builder (Gloas extension)
- In `processOperations`: `for_ops(body.execution_requests.deposits, process_deposit_request)`
- `apply_deposit()` modified to queue deposits (not apply immediately)

---

## EIP-7002: Execution Layer Triggerable Exits

### Key Changes
- Validators can be exited via EL `WithdrawalRequest`
- Full exit: `amount == FULL_EXIT_REQUEST_AMOUNT (0)`
- Partial withdrawal: specific amount, only for compounding validators
- Source address verification: `withdrawal_credentials[12:]` must match `source_address`
- Pending partial withdrawals tracked in `state.pending_partial_withdrawals`

### Lodestar Implementation
- **`block/processWithdrawalRequest.ts`**: Complete implementation
- Checks: active, not already exiting, sufficient tenure, correct credentials
- Full exit: calls `initiateValidatorExit()` if no pending balance to withdraw
- Partial: checks compounding credentials, sufficient balance, appends to pending queue

---

## EIP-7549: Move Committee Index Outside Attestation

### Key Changes
- `attestation.data.index` always 0 (committee index moved to `committee_bits`)
- `Attestation` now has `committee_bits: Bitvector[MAX_COMMITTEES_PER_SLOT]`
- `aggregation_bits` expanded to `Bitlist[MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]`
- Multiple committees can be aggregated into single `Attestation` (on-chain aggregate)
- Individual attestations sent as `SingleAttestation` on gossip
- `get_attesting_indices()` iterates over set committee bits with offsets

### Impact on Operations
- `MAX_ATTESTATIONS_ELECTRA = 8` (was 128) — each covers multiple committees
- `MAX_ATTESTER_SLASHINGS_ELECTRA = 1` (was 2)
- `IndexedAttestation.attesting_indices` limit: `MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT`

### Lodestar Implementation
- **`block/processAttestationPhase0.ts`**: Fork-gated at `ForkSeq.electra` to handle new format
- Attestation validation: checks `data.index == 0`, committee bits, offset-based aggregation bits

---

## EIP-7691: Blob Throughput Increase

### Key Changes
- `MAX_BLOBS_PER_BLOCK_ELECTRA = 9` (up from 6 in Deneb)
- `BLOB_SIDECAR_SUBNET_COUNT_ELECTRA = 9` (was 6)
- `MAX_REQUEST_BLOB_SIDECARS_ELECTRA = MAX_REQUEST_BLOCKS_DENEB * 9`
- `compute_subnet_for_blob_sidecar`: uses `BLOB_SIDECAR_SUBNET_COUNT_ELECTRA`

### P2P Impact
- BlobSidecarsByRange/Root: response limits updated
- `blob_sidecar_{subnet_id}`: 9 subnets instead of 6
- Block validation: KZG commitments checked against new limit

---

## EIP-7685: Execution Requests Framework

New container `ExecutionRequests` bundles all EL→CL requests:
```
ExecutionRequests {
  deposits: List[DepositRequest, 8192]
  withdrawals: List[WithdrawalRequest, 16]
  consolidations: List[ConsolidationRequest, 2]
}
```

- Part of `BeaconBlockBody`
- Passed to `NewPayloadRequest` for Engine API
- `get_execution_requests_list()`: serializes for EIP-7685 wire format (type byte + SSZ)
- `is_valid_block_hash()` and `notify_new_payload()` receive `execution_requests_list`

---

## P2P Changes Summary

### Gossip
- `beacon_block`: Electra blocks (with execution_requests)
- `beacon_aggregate_and_proof`: Uses new `Attestation` with `committee_bits`
- `beacon_attestation_{subnet_id}`: Now propagates `SingleAttestation` objects
- `blob_sidecar_{subnet_id}`: 9 subnets, updated limits

### Req/Resp
- `BeaconBlocksByRange/Root v2`: Electra fork version added to context enum
- `BlobSidecarsByRange/Root v1`: Updated limits (`MAX_REQUEST_BLOB_SIDECARS_ELECTRA`)

---

## Validator Changes Summary

### Block Construction
- `GetPayloadResponse` includes `execution_requests: Sequence[bytes]`
- `get_execution_requests()` parses EIP-7685 typed request list
- `get_eth1_pending_deposit_count()` replaces old deposit count logic
- Eth1 voting: can freeze once `eth1_deposit_index == deposit_requests_start_index`

### Attestation
- Validators create `SingleAttestation` (not bitfield-based)
- `data.index = 0`, committee index in `committee_index` field
- `attester_index` identifies the validator

### Aggregation
- `compute_on_chain_aggregate()`: merges network aggregates from different committees
- Sorted by committee index, bitfields concatenated, committee_bits set

---

## BeaconState Changes

**9 new fields** added to `BeaconState`:
1. `deposit_requests_start_index: uint64` (EIP-6110)
2. `deposit_balance_to_consume: Gwei` (EIP-7251)
3. `exit_balance_to_consume: Gwei` (EIP-7251)
4. `earliest_exit_epoch: Epoch` (EIP-7251)
5. `consolidation_balance_to_consume: Gwei` (EIP-7251)
6. `earliest_consolidation_epoch: Epoch` (EIP-7251)
7. `pending_deposits: List[PendingDeposit, 134M]` (EIP-7251)
8. `pending_partial_withdrawals: List[PendingPartialWithdrawal, 134M]` (EIP-7251)
9. `pending_consolidations: List[PendingConsolidation, 262K]` (EIP-7251)

---

## Epoch Processing Changes

Modified `process_epoch` order:
1. `process_justification_and_finalization` (unchanged)
2. `process_inactivity_updates` (unchanged)
3. `process_rewards_and_penalties` (unchanged)
4. `process_registry_updates` (**modified**: inline activation, balance-based churn)
5. `process_slashings` (**modified**: new penalty calculation)
6. `process_eth1_data_reset` (unchanged)
7. **`process_pending_deposits`** (NEW: processes deposit queue)
8. **`process_pending_consolidations`** (NEW: moves consolidated balances)
9. `process_effective_balance_updates` (**modified**: `get_max_effective_balance`)
10. Remaining resets (unchanged)

---

## Spec Compliance Assessment

### Lodestar matches spec faithfully:
- ✅ All 5 EIPs implemented
- ✅ Pending deposits queue with churn limiting
- ✅ Consolidation flow (full + switch-to-compounding)
- ✅ Withdrawal requests (full exit + partial)
- ✅ Attestation format change (SingleAttestation on gossip, committee_bits on-chain)
- ✅ Blob throughput increase (9 blobs, 9 subnets)
- ✅ Execution requests framework (EIP-7685)
- ✅ Fork upgrade migration (`upgradeStateToElectra`)

### Notable Implementation Choices:
1. **Chunked pending deposit iteration**: `processPendingDeposits` reads deposits in chunks of 100 to avoid loading entire list at once — practical optimization not in spec
2. **`isValidatorKnown` helper**: Since pubkey2index is shared across states, validators may exist in index but not in current state — Lodestar adds explicit bounds checking
3. **Gloas extensions**: `processDepositRequest` already routes builder deposits (Gloas fork extends Electra)
4. **`applyDepositForBuilder`**: Added in preparation for Gloas, handles builder-specific deposit routing
5. **TODO comments**: Several `TODO Electra` markers remain in codebase for potential optimizations (e.g., caching pendingPartialWithdrawals, batch push to pendingDeposits)

### No spec compliance issues found.

---

## Cross-Fork Complexity Notes

Electra's interaction with the existing system is intricate:
- **Deposit transition**: Dual-path (Eth1 bridge + EL requests) with ordering constraints
- **Withdrawal refactoring**: Pending partial withdrawals + validator sweep + churn limits
- **State size growth**: 9 new state fields, 3 potentially large lists (hundreds of millions of entries)
- **Attestation format**: Requires coordination between gossip (SingleAttestation) and on-chain (committee-aggregate Attestation) representations

This fork significantly increases the state transition complexity and the beacon state size. The pending queues (deposits, withdrawals, consolidations) add new epoch-processing workload proportional to queue length.
