# Round 2 security review — local pubkey-cache fix

Reviewer: review-security
Reviewed commit: c45c978f0cc34ad211b89725effb0757362e5435

## Verdict

No security vulnerabilities identified.

The two findings in the previous security review are addressed by this exact commit: retained interior pubkey mismatches are rejected at startup, and exceptional epoch batches resolve newly deposited signers against the correct preceding state. This is a local security-review verdict, not a claim that all verification suites are green or that a live network scenario was executed.

## Scope and provenance

- Inspected the cumulative diff against `b889ef57686034fe35121d8766305abb31eec25b`, the follow-up diff against `4bce44fe3e338e581ce4a1fab1da4d154da26701`, and the supplied exact 79-file changed-file list. Verified worktree HEAD before review and checked that the source worktree remained clean.
- Independently traced changed TS and Zig cache code and the surrounding producer/consumer paths relevant to checkpoint promotion, startup/reload, deposits, signature extraction and BLS verification. Read the security persona and coding context.
- Read the prior security report, `FOLLOWUP_REPORT.md`, and `BATCH_BASELINE_REVIEW.md` as evidence to check, not as a substitute for tracing the implementation. The earlier baseline conclusion is corrected: the signed nine-block phase0/Electra regression in 4bce44fe3e was real; delayed native dense-key resolution and signature-loop yielding explain baseline success.
- No source edits, commits, builds, dependency changes, installs, broad suites, live devnet actions or external writes were performed. No further reviewers were spawned.

## Rechecked security boundaries

### Synchronous promotion and checkpoint provenance

`packages/beacon-node/src/chain/blocks/importBlock.ts:160` promotes only after successful fork-choice acceptance. The acceptance path checks current finalized ancestry; a rejected incoming block cannot reach this promotion call. The per-chain gate in `packages/beacon-node/src/chain/chain.ts:670` advances only after the synchronous helper succeeds.

`packages/beacon-node/src/chain/chain.ts:1982` also promotes synchronously on checkpoint events. Both production checkpoint emitters were traced: accepted block import and epoch-by-epoch empty-slot regeneration. The latter starts from an accepted fork-choice parent, an accepted cached block state, or a checkpoint derived from such a state. It does not apply the incoming unverified block's operations before emitting. Full block verification's speculative transitions do not insert their post-states into those caches or emit checkpoint events. Regeneration replay selects accepted fork-choice ancestors and checks regenerated state roots against their stored roots.

The direct checkpoint/pre-state fast paths were traced: runtime insertions have already crossed the synchronous event/promotion boundary, while startup initializes the selected trusted anchor densely. Prior-process persisted checkpoint keys are discarded during startup initialization, so an old speculative checkpoint cannot silently enter this event path through normal reload. Within-process persisted checkpoint reloads originate from the same accepted/checkpoint cache population paths. The explicitly unsafe unfinalized-anchor startup mode remains caller-owned trust; it does not turn arbitrary incoming SSZ into an authenticated anchor.

`packages/state-transition/src/cache/pubkeyCache.ts:46` derives the promoted prefix from the accepted state's registry and finalized epoch, not candidate entries or an asynchronously selected head. Eligibility of the last included validator proves that validator, and consequently its earlier append-only registry prefix, existed by the finalized epoch. The scan may include earlier still-ineligible validators without making their keys speculative. Event-driven promotion covers skipped epochs before newly activated validators reach dense-only proposer/committee consumers.

### State-verified candidates and native ownership

The TS lookup and `src/state_transition/cache/pubkey_cache.zig:255` bound candidate indices by the requesting registry and compare the requested compressed key with that registry entry. A conflicting branch candidate cannot authorize a deposit/request lookup. The REST state lookup additionally checks the dense answer against the requested state for cached orphan states. Signature fallback obtains bytes from the actual state, not from an unverified candidate.

Candidate insertion deduplicates each key/index pair. Finalization pruning retains only indices outside the dense prefix and frees removed small-vector storage; swap-removal does not skip the entry moved into its place. The shared hash key remains aligned with both maps when a snapshot is installed.

Reviewed new native exclusive/shared lock paths and cleanup: lock release is deferred; candidate copies returned to NAPI are owned and freed; movable map pointers do not escape a released lock; candidate state reads do not recursively acquire the cache lock. Cache storage uses the existing page allocator and temporary NAPI arrays use the C allocator. Snapshot replacement retains ownership through the staged cache, and candidate storage is disposed on reset/install/deinit. No concrete new lock, ownership or remotely exploitable resource-exhaustion failure was established.

### Full persisted-prefix validation

`packages/cli/src/cmds/beacon/pubkeysFile.ts:27` compares the complete retained overlap with the selected anchor before retaining any loaded keys; mismatch resets the entire cache, and an excess suffix is truncated. `src/state_transition/cache/pubkey_cache.zig:270` checks validator-record alignment and compares every overlapping 48-byte key under one shared lock. Equal counts and matching endpoints therefore no longer conceal an interior branch permutation. The overlap-only comparison is correct: a shorter saved cache will be extended from the anchor, while entries beyond a shorter anchor are discarded. Snapshot framing/checksum handling remains separate from semantic anchor matching.

### Exceptional signed batches and invalid inputs

`packages/beacon-node/src/chain/blocks/verifyBlock.ts:180` detects slashings with indices outside the initial registry before signature extraction. Only those exceptional batches wait for ordered state transitions. `packages/beacon-node/src/chain/blocks/verifyBlocksSignatures.ts:50` uses `preState0` for block zero and `postStates[i-1]` for subsequent registry lookups, while preserving the common epoch state for domains, shuffling and sync committees. A slashing cannot borrow a validator introduced later in the same block or on another candidate branch.

Ordinary batches still queue signatures before transitions; exceptional batches still require the BLS result before successful return/import. Invalid candidate-key signatures are not trusted merely because transition/state-root processing completed. Structural validation rejects absent/out-of-bounds slashing indices. The normal trusted `validSignatures` option remains explicit. New per-promise rejection handlers prevent a verifier rejection during the yielding submission loop from becoming an unhandled rejection, without converting failure into success. Exceptional processing is bounded by the existing same-epoch batch/operation limits; it introduces no independent retry or unbounded-work loop.

Native indexed-attestation fallback verifies registry bounds and resolves only missing dense keys from that state's validators; attester-slashing and attestation callers pass the actual validator view. Dense-only active-signer paths retain their existing contract, now supported by synchronous checkpoint promotion.

## Executed verification and checked evidence

Independent execution, exact command from the reviewed worktree:

```sh
docker exec pkfix-dev node node_modules/vitest/vitest.mjs run --project unit packages/cli/test/unit/cmds/pubkeysFile.test.ts --maxWorkers=1 --reporter=dot
```

Result: **exit 0, 7/7 passed**, one file, 3.52 seconds. Log: `/home/openclaw/scratch/pubkey-poison/review2/security-snapshot-tests.log`. This includes real native snapshot save/load, interior swap reset followed by canonical reconstruction, truncation, missing file and capacity rejection.

An earlier invocation of the same direct Vitest entrypoint selected only `packages/beacon-node/test/unit/chain/blocks/pubkeyBatch.test.ts` and the CLI pubkeys-file test, with one worker. Its completion output was not retained, so it is not counted as an independently confirmed pass. No production-worker batch probe was run by this reviewer; the parent assigned that distinct verification to the bug reviewer.

Separately inspected the parent's current `verify2/bn-unit.log`: all **10 signed batch cases passed** (phase0/Electra, both inline/batch-verification settings, wrong candidate signatures, trusted-signature option and absent indices). Read the actual test construction and assertions, including valid deposits/Merkle proofs, proposer/RANDAO signatures, conflicting indexed attestations and reset between fixture generation and replay. Also checked the saved checkpoint/import regression result and its TS/native test bodies. These are attributed existing-run results, not executions by this reviewer.

No independent full Zig/spec suite, worker-pool batch execution, live-network reproduction, new performance benchmark or source-mutation negative control was performed in this re-review. Parent-owned exact-head verification remains the shipping gate.
