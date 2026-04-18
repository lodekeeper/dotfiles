# Relevant test excerpts for DPR gap analysis

## 1. Existing next-block missed-payload sanity coverage
From `tests/core/pyspec/eth_consensus_specs/test/gloas/sanity/test_blocks.py`:

- `_setup_missed_payload_with_withdrawals(...)`
  - processes Block 1 with a full parent
  - stores `state.payload_expected_withdrawals`
  - intentionally leaves payload undelivered so the next parent is empty
- tests present:
  - `test_missed_payload_next_block_with_withdrawals_satisfying_payload`
  - `test_missed_payload_next_block_with_withdrawals_unsatisfying_payload`
  - `test_missed_payload_next_block_without_withdrawals_satisfying_payload`
  - `test_missed_payload_next_block_without_withdrawals_unsatisfying_payload`

Observation: this covers only the immediate next-block case, not slot-31 boundary gaps of 1/2/5 epochs.

## 2. Existing empty-parent preservation regression
From `tests/core/pyspec/eth_consensus_specs/test/gloas/block_processing/test_process_withdrawals.py`:

- `test_empty_parent_preserves_populated_expected_withdrawals`
  - populates `payload_expected_withdrawals` via a full parent
  - flips parent to empty
  - reruns processing and asserts all relevant state stays unchanged

Observation: good targeted regression for carry-forward semantics, but not a long-gap/multi-epoch scenario.

## 3. Existing liability/accounting unit tests
From `tests/core/pyspec/eth_consensus_specs/test/gloas/unittests/test_withdrawal_liability.py`:

Present tests:
- `test_payload_expected_withdrawals_contribute_to_pending_balance`
- `test_payload_expected_withdrawals_reserve_balance_until_settlement`
- `test_builder_bid_cannot_spend_payload_expected_withdrawals`
- `test_payload_expected_withdrawals_carry_forward_across_empty_parent`
- `test_builder_bid_recovers_after_liability_settlement`
- `test_effective_balance_updates_use_spendable_balance_under_liability`

Observation: these are narrow helper/accounting invariants, not end-to-end multi-block missed-gap tests.

## 4. Existing parent execution request regressions
From `tests/core/pyspec/eth_consensus_specs/test/gloas/block_processing/test_process_parent_execution_payload.py`:

Present tests:
- `test_process_parent_execution_payload__clears_liability_before_parent_withdrawal_request`
- `test_process_parent_execution_payload__clears_liability_before_parent_partial_withdrawal_request`
- `test_process_parent_execution_payload__clears_liability_before_parent_consolidation_request`

Observation: covers stale-liability interaction with deferred parent execution requests, but not Potuz’s slot-31 long-gap matrix or switch-to-compounding delayed effective-balance concern.

## 5. Helper for switch-to-compounding request
From `tests/core/pyspec/eth_consensus_specs/test/helpers/consolidations.py`:

```python
def prepare_switch_to_compounding_request(spec, state, validator_index, address=None):
    validator = state.validators[validator_index]
    if not spec.has_execution_withdrawal_credential(validator):
        set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)

    return spec.ConsolidationRequest(
        source_address=state.validators[validator_index].withdrawal_credentials[12:],
        source_pubkey=state.validators[validator_index].pubkey,
        target_pubkey=state.validators[validator_index].pubkey,
    )
```

Observation: there is already a dedicated helper for switch-to-compounding requests.
