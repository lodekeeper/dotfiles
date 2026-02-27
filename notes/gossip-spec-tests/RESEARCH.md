# Gossip Validation Spec Tests — Research Notes

## Spec PR: ethereum/consensus-specs#4902

**Author:** Justin Traglia (EF/c-kzg)
**Branch:** `executable-networking-specs`
**Scope:** Phase0 gossip validation only (follow-up PRs for later forks)
**Tests:** 74 reference tests across 6 gossip topics

### What changed in the spec

The PR transforms the informal English gossip validation rules in `specs/phase0/p2p-interface.md` into executable Python functions:

- `validate_beacon_block_gossip(seen, store, state, signed_beacon_block, current_time_ms)`
- `validate_beacon_aggregate_and_proof_gossip(seen, store, state, signed_aggregate_and_proof, current_time_ms, subnet_id)`
- `validate_beacon_attestation_gossip(seen, store, state, attestation, current_time_ms, subnet_id)`
- `validate_proposer_slashing_gossip(seen, store, state, proposer_slashing)`
- `validate_attester_slashing_gossip(seen, store, state, attester_slashing)`
- `validate_voluntary_exit_gossip(seen, store, state, signed_voluntary_exit)`

New helper types/functions:
- `Seen` class — tracks dedup state (proposer_slots, aggregator_epochs, etc.)
- `compute_time_at_slot_ms(state, slot)` — time in ms at slot start
- `is_valid_attestation_slot_time(state, attestation_slot, current_time_ms)`
- `GossipIgnore` / `GossipReject` exceptions

### Test fixture format

```
tests/<preset>/phase0/networking/gossip_validation/<topic>/<test_name>/
├── meta.yaml           # topic, blocks, current_time_ms, messages, finalized_checkpoint
├── state.ssz_snappy    # BeaconState (genesis_time, validators, finalized_checkpoint)
├── block_<root>.ssz_snappy
├── attestation_<root>.ssz_snappy
├── aggregate_<root>.ssz_snappy
├── proposer_slashing_<root>.ssz_snappy
├── attester_slashing_<root>.ssz_snappy
└── voluntary_exit_<root>.ssz_snappy
```

meta.yaml structure:
```yaml
topic: "beacon_block"
blocks:                   # blocks to import before validation
  - block: "block_0x..."
    failed: false         # optional: if true, track as failed validation
finalized_checkpoint:     # optional override
  epoch: N
  root: "0x..."           # OR block: "block_0x..."
current_time_ms: N        # base time in ms since genesis
messages:
  - offset_ms: N          # time offset from current_time_ms
    subnet_id: N          # optional (for attestation/aggregate topics)
    message: "block_0x..."
    expected: "valid"     # "valid", "ignore", or "reject"
    reason: "..."         # optional
```

### Topics and test counts (from PR description)

6 topics total:
1. `beacon_block` — block gossip validation
2. `beacon_aggregate_and_proof` — aggregate attestation
3. `beacon_attestation` — individual attestation
4. `proposer_slashing`
5. `attester_slashing`
6. `voluntary_exit`

74 total tests.

## Teku Reference Implementation

**Branch:** `jtraglia/teku:executable-networking-specs`
**Approach:** One TestExecutor class per topic, all in `eth-reference-tests/.../phase0/networking/`

### Architecture
- `NetworkingTests.java` — maps handler names to test executors
- `GossipBeaconBlockTestExecutor.java` — sets up StorageSystem, ForkChoice, BlockGossipValidator
- Similar structure for each topic

### Teku's skipped tests (7 total):

**beacon_block (3 skipped):**
- `reject_finalized_checkpoint_not_ancestor` — Teku does this check outside gossip validation
- `reject_parent_failed_validation` — same
- `ignore_slot_not_greater_than_finalized` — same

**beacon_aggregate_and_proof (2 skipped):**
- `reject_block_failed_validation` — check done outside validation
- `ignore_finalized_not_ancestor` — same

**beacon_attestation (2 skipped):**
- `reject_block_failed_validation` — same
- `ignore_already_seen` — same

**proposer_slashing, attester_slashing, voluntary_exit:** All pass (0 skipped)

### Key pattern: Teku bootstraps real infrastructure
- Creates InMemoryStorageSystem with RecentChainData
- Creates real ForkChoice with TickProcessor
- Imports blocks into fork choice (with proper slot timing)
- Uses real gossip validators (BlockGossipValidator, etc.)
- Sets time via `forkChoice.onTick(currentTimeMs)`

## Lodestar Current Spec Test Infrastructure

### Existing networking test runner
File: `packages/beacon-node/test/spec/presets/networking.test.ts`
- Currently handles: `compute_columns_for_custody_group`, `get_custody_groups`
- Simple function-in/function-out pattern
- Uses `specTestIterator` with `RunnerType.default`

### Spec test iteration
File: `packages/beacon-node/test/spec/utils/specTestIterator.ts`
- Walks `tests/<preset>/<fork>/<runner>/<handler>/<suite>/<case>/`
- Runner "networking" is in `coveredTestRunners`
- Two runner types: `RunnerType.default` (simple) and `RunnerType.custom` (full control)

### Spec test utilities
Package: `@lodestar/spec-test-util`
- `describeDirectorySpecTest()` — iterate test cases in a directory
- `InputType.YAML`, `InputType.SSZ_SNAPPY` — file loading
- Download tests from consensus-specs releases

### Test fixtures version
Currently: `v1.7.0-alpha.2`
**The gossip validation tests are NOT in any released version yet** — they're in PR #4902 which hasn't been merged.

## Lodestar Gossip Validation Architecture

### Key difference from Teku
Lodestar's gossip validation is deeply integrated with the chain:
- `validateGossipBlock(config, chain, signedBlock, fork)` — takes `IBeaconChain`
- Chain provides: `clock`, `forkChoice`, `seenBlockProposers`, `regen`, etc.
- Validators are async (return Promises)
- Each validator returns void (throws on error) rather than returning a result code

### Validation files
- `block.ts` → `validateGossipBlock(config, chain, signedBlock, fork)`
- `aggregateAndProof.ts` → `validateGossipAggregateAndProof(...)`
- `attestation.ts` → `validateGossipAttestation(...)`
- `proposerSlashing.ts` → `validateGossipProposerSlashing(...)`
- `attesterSlashing.ts` → `validateGossipAttesterSlashing(...)`
- `voluntaryExit.ts` → `validateGossipVoluntaryExit(...)`

### Error handling
- Throws `BlockGossipError(GossipAction.IGNORE/REJECT, {...})` for blocks
- Throws `AttestationError(GossipAction.IGNORE/REJECT, {...})` for attestations
- GossipAction maps to spec's valid/ignore/reject

## Integration Strategy

### Option A: Lightweight harness (like Teku)
Create a real chain environment (fork choice, seen caches, etc.) per test case, import blocks, then run validation. This tests the actual validation code path.

**Pros:** Tests real code, catches integration bugs
**Cons:** Heavy setup per test, slow, brittle if chain internals change

### Option B: Custom RunnerType with minimal mocking
Create a custom test runner that:
1. Loads state, blocks, and messages from fixtures
2. Sets up a minimal IBeaconChain mock with just enough to run validation
3. Runs validation and checks result

**Pros:** More targeted, faster, less setup
**Cons:** May miss integration issues, needs careful mocking

### Recommended: Option A (like Teku)
Reasons:
1. Teku's approach proved viable — bootstrap real infrastructure
2. Tests the actual validation code path end-to-end
3. More likely to catch real bugs
4. Lodestar already has test utilities for creating test chains

### Implementation plan
1. New handler `gossip_validation` under the `networking` runner
2. Use `RunnerType.custom` for full control over test structure
3. Per-topic test executor functions
4. Bootstrap: create config, state, fork choice, import blocks, set clock
5. For each message: run validation, catch errors, map to valid/ignore/reject
6. Compare against expected result

### Key challenges
1. **Test fixtures not released yet** — need to generate them from PR #4902 branch
2. **Chain bootstrapping** — need to figure out minimal Lodestar chain setup for tests
3. **Clock mocking** — need to set current_time_ms precisely
4. **Seen state** — need to track what's been seen between sequential messages
5. **Block import with failed flag** — need to handle blocks that "failed validation" in store
6. **IBeaconChain interface** — complex, many dependencies, need to determine what to mock vs use real

### Files to create/modify
- `packages/beacon-node/test/spec/presets/networking.test.ts` — extend with gossip_validation handler
- `packages/beacon-node/test/spec/utils/gossipValidation.ts` — new: test harness and executor functions
- Possibly new test utilities for chain bootstrapping

### Similar patterns in Lodestar
- `packages/beacon-node/test/spec/presets/fork_choice.test.ts` — bootstraps chain, imports blocks
  This is the closest analog! Fork choice tests already set up a chain environment.
