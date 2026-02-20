# Bellatrix — Beacon Chain Spec Notes

## Overview
Bellatrix introduces the "merge" — integrating execution layer (PoW) into the consensus layer (PoS). Key additions:
- `ExecutionPayload` container in `BeaconBlockBody`
- `ExecutionPayloadHeader` cached in `BeaconState`
- Merge transition predicates
- Penalty parameter updates to maximum security values

## Key Spec Changes

### New Containers
- **ExecutionPayload**: parentHash, feeRecipient, stateRoot, receiptsRoot, logsBloom, prevRandao, blockNumber, gasLimit, gasUsed, timestamp, extraData, baseFeePerGas, blockHash, transactions
- **ExecutionPayloadHeader**: Same minus transactions, plus transactionsRoot
- Mapping: `fee_recipient`=beneficiary, `prev_randao`=difficulty, `block_number`=number (yellow paper names)

### Merge Transition Predicates
1. `is_merge_transition_complete` — latest_execution_payload_header ≠ default
2. `is_merge_transition_block` — NOT complete AND current payload ≠ default
3. `is_execution_enabled` — transition complete OR transition block

### Penalty Parameters (maximally punitive)
- `INACTIVITY_PENALTY_QUOTIENT_BELLATRIX` = 2^24 (was 2^26 in Altair)
- `MIN_SLASHING_PENALTY_QUOTIENT_BELLATRIX` = 2^5 (was 2^7 in Altair)
- `PROPORTIONAL_SLASHING_MULTIPLIER_BELLATRIX` = 3 (was 2 in Altair)

### process_execution_payload
1. Verify parent hash consistency (if merge complete)
2. Verify prev_randao matches current epoch's randao mix
3. Verify timestamp matches computed time at slot
4. Call execution engine `verify_and_notify_new_payload`
5. Cache payload header in state

**Important ordering**: process_execution_payload BEFORE process_randao (depends on previous randao mix)

### Terminal Total Difficulty
- `TERMINAL_TOTAL_DIFFICULTY` = 58750000000000000000000 (mainnet, Sept 15, 2022)

## Lodestar Implementation

### Merge Predicates (`packages/state-transition/src/util/execution.ts`)
- `isMergeTransitionComplete()` — SSZ equality check against default value
  - **Optimization**: Post-Capella states always return true (all networks completed merge before Capella)
- `isExecutionEnabled()` — Supports both full and blinded payloads
  - Handles blinded blocks by checking payload header instead
- Type guards: `isExecutionStateType`, `isCapellaStateType`, `isExecutionBlockBodyType`

### process_execution_payload (`packages/state-transition/src/block/processExecutionPayload.ts`)
- Matches spec closely with these deviations:
  - **Async Engine API**: Execution engine validation is external/async, passed in as `externalData.executionPayloadStatus` (valid/invalid/preMerge)
  - **Blinded block support**: Handles both full and blinded payloads
  - **Post-Deneb checks**: Validates blobKzgCommitments length against maxBlobsPerBlock
  - Uses `executionPayloadToPayloadHeader()` to convert full payload → header for state caching
  - State update uses ViewDU (efficient SSZ tree backing)

### executionPayloadToPayloadHeader
- Converts full payload to header by computing `transactionsRoot` via `hashTreeRoot(payload.transactions)`
- Fork-aware: adds `withdrawalsRoot` for Capella, `blobGasUsed`/`excessBlobGas` for Deneb

## Findings
- ✅ Implementation is spec-compliant
- ✅ Good optimization for post-Capella merge check
- ✅ Clean separation of sync state transition from async EL validation
- ✅ Blinded block support well-integrated throughout
- No issues found worth a PR

## Next
- [ ] Bellatrix fork choice (POS transition, `is_valid_terminal_pow_block`)
