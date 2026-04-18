# Potuz DPR test cases — Tracker

Last updated: 2026-04-17 22:34 UTC

## Goal
Add only the missing consensus-spec test coverage from Potuz's 2026-04-17 DPR checklist, on a branch updated to latest upstream `master`, without duplicating existing tests.

## Phase Plan
- [x] Gather gist requirements / create local note (`notes/potuz-dpr-test-cases.md`)
- [x] Inspect current branch state and existing coverage
- [~] Phase 1 planning / advisor consult
- [ ] Sync work branch with latest upstream `master`
- [ ] Implement only missing tests in spec style
- [ ] Run focused verification
- [ ] Review / clean up / commit

## Current branch state
- Repo: `/home/openclaw/consensus-specs-defer-deduction`
- Branch: `feat/defer-cl-withdrawal-deduction`
- HEAD: `32dd1365c` (`gloas: add withdrawal liability edge-case tests`)
- Working tree: dirty in `tests/core/pyspec/eth_consensus_specs/test/gloas/unittests/test_withdrawal_liability.py`
  - local uncommitted change replaces non-ASCII byte literals with explicit `\x..` escapes
- Upstream divergence after `git fetch origin master`:
  - `origin/master...HEAD` = `15 60`
  - branch is behind current upstream `master`, so final work must merge latest `master`

## Existing coverage I found
### Already present / overlapping
- `tests/core/pyspec/eth_consensus_specs/test/gloas/sanity/test_blocks.py`
  - missed payload → next block acceptance/rejection coverage for stale withdrawals
  - includes only immediate next-block scenarios, not slot-31 + 1/2/5 epoch gaps
- `tests/core/pyspec/eth_consensus_specs/test/gloas/block_processing/test_process_withdrawals.py`
  - `test_empty_parent_preserves_populated_expected_withdrawals`
- `tests/core/pyspec/eth_consensus_specs/test/gloas/unittests/test_withdrawal_liability.py`
  - pending-balance / reserve floor / builder bid / empty-parent carry-forward
  - newly added local edge cases (carry-forward, bid recovers, effective-balance uses spendable balance)
- `tests/core/pyspec/eth_consensus_specs/test/gloas/block_processing/test_process_parent_execution_payload.py`
  - liability clearing before withdrawal / partial-withdrawal / consolidation parent requests

### Gaps that still appear missing
1. **Epoch-boundary + long missed-gap matrix**
   - block at slot 31
   - next block at slot 63 / 95 / 191
   - both full and empty next-block variants
   - verify deferred requests survive epoch processing and apply correctly
2. **Switch-to-compounding delayed effective-balance change**
   - request in slot-31 payload
   - immediate epoch boundary must NOT apply the effective-balance change under DPR
   - delay should persist across missed slots / long gaps

## Candidate test locations
- `tests/core/pyspec/eth_consensus_specs/test/gloas/sanity/test_blocks.py`
  - best fit for multi-block / missed-slot / full-vs-empty child scenarios
- possibly a new dedicated DPR sanity file if the matrix becomes too large
- keep `test_withdrawal_liability.py` for narrow helper / accounting invariants only

## Advisor questions
1. What is the most spec-conventional location/shape for the 6-case slot-31 gap matrix?
2. Should the switch-to-compounding case live in `sanity/` (multi-block behavior) or a more targeted block-processing/epoch-processing test?
3. What is the minimal non-duplicative set of tests that still covers the gist’s risk surface?
4. Given the dirty worktree + behind-master branch, what is the safest sequence: merge `origin/master` first vs finish the byte-literal fix + commit first?

## Next immediate steps
1. Send this tracker + relevant excerpts to `gpt-advisor`
2. Use the advisor result to decide test placement and sequencing
3. Sync branch with upstream `master`
4. Implement only the missing cases and verify cleanly
