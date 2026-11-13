# Round-2 functional review — pubkey cache fix

Reviewer: review-bugs
Reviewed commit: c45c978f0cc34ad211b89725effb0757362e5435

## Verdict

No functional bugs found.

The two prior functional findings against `4bce44fe3e338e581ce4a1fab1da4d154da26701` are resolved in this revision. This is a functional review, not a separate security approval.

## Source review

Reviewed the cumulative production changes against `b889ef57686034fe35121d8766305abb31eec25b`, the follow-up diff, the changed regression tests, and relevant callers. Findings were restricted to the supplied changed-file list. Host HEAD matched the requested commit and `git status --short` was empty before and after the review.

- **Exceptional signed batches:** `verifyBlocksInEpoch` detects attester-slashing indices outside the initial registry before extraction, waits for the ordered transitions, and passes the preceding post-state for each subsequent block's pubkey resolution. `preState0` remains the epoch context for domains, shufflings, and sync committees. For a same-epoch batch, empty slots between blocks do not insert validators. The ordinary path still submits signatures before starting transitions. Trusted-signature bypass, state-root failures, and the enclosing `finally` abort were traced. Submitted signature promises now receive immediate rejection handlers before the signature loop yields.
- **Checkpoint promotion:** traced both production checkpoint emitters. `importBlock` promotes only after `forkChoice.onBlock` accepts the fully verified block; its checkpoint emission occurs afterwards. Regeneration derives checkpoint states by processing empty slots from accepted/fork-choice-known states and emits synchronously once per epoch boundary, allowing promotion before a later activation boundary. Cached checkpoints derive from those accepted inputs; startup removes previous-process persisted checkpoints. The monotonic finalized-epoch guard, shorter canonical historical states, initial trusted-anchor population, skipped epochs, and candidate pruning were source-traced. No asynchronous promotion or head-state lookup remains.
- **Persisted prefix repair:** `loadPubkeysFile` passes the anchor's serialized registry to native `matchesValidators`, which compares every overlapping compressed pubkey while holding the read lock. An interior mismatch resets the cache before trusted startup sync; a matching suffix beyond the anchor is truncated. The previous endpoint-only acceptance is gone.
- **Other cumulative logic:** reviewed TypeScript and Zig candidate registration, deduplication/compaction/cleanup, per-state hit validation, trust-mode loading parity, historical/load-other-state initialization, indexed-attestation state-backed resolution, deposits and pending deposits, consolidation/withdrawal requests, Gloas builder onboarding, sync-committee indexing, API lookups, and standalone attester-slashing consumers. No additional concrete failure was identified.

## Independently executed checks

Five narrowly targeted application-caller probes used the actual `verifyBlocksInEpoch`, ordered state transitions, `verifyBlocksSignatures`, production `BlsMultiThreadWorkerPool`, and its native BLS worker. Mainnet preset, one warmed worker, 64 trusted anchor validators, a real deposit in block 1, and a mixed active/inactive attester slashing in block 9, slots 65–73. Execution RPC/DA networking and fork-choice import were intentionally outside these probes.

`review2/bug-review-loader.mjs` transpiles current committed TypeScript in memory instead of using stale built JavaScript. It loaded 233 source modules in each parent process; workers inherit the loader. No implementation source was replaced. The native module actually loaded was `/home/openclaw/lodestar-pubkey-cache-fix/bindings/zig-out/lib/bindings.node`, SHA-256 `c43b9ce00f78dd3bdf938737cb7e4c76d434983ce0a257d02f6871ea3363fcf2` (confirmed through the native require cache). Node reported `v26.13.0` in the container.

All artifact paths below are under `/home/openclaw/scratch/pubkey-poison/review2/`.

1. **Valid phase0 batch:** PASS, nine post-states, initial registry 64/final registry 65/dense cache 64. All nine ordered transitions complete before the first BLS submission. Fixture SHA-256 `c63d72aec928b0afa19b701ca91f4b9a0470fb6d256b06d6d36702f093962384`, identical to the prior baseline comparison. Log: `bugs-worker-phase0.log`.
2. **Valid Electra batch:** PASS with the same counts and sequencing; the newly added validator has zero balance and one pending deposit, as expected for the real Electra legacy-deposit path. Fixture SHA-256 `ec54d0d449ca8bebc9057c2ebd7fb9490e00090422535950e0170edd596c8f97`, identical to the prior baseline comparison. Log: `bugs-worker-electra.log`.
3. **Conflicting-candidate signature:** expected rejection `BLOCK_ERROR_INVALID_SIGNATURE`. The fixture's slashings are signed with a different key for index 64, that wrong key is inserted as a global candidate, and block/state roots and proposer signatures are built for that fixture. Verification uses the real state's key rather than accepting the candidate's signature. Nine transitions and nine BLS submissions; dense cache remains 64. Log: `bugs-worker-electra-wrong-key-retry.log`.
4. **Incorrect state root:** expected rejection `BLOCK_ERROR_INVALID_STATE_ROOT`. Final block's state root is changed and its proposer signature recomputed. Nine transitions, zero BLS submissions: the failed transition phase does not start the deferred signature phase. Log: `bugs-worker-electra-state-root-retry.log`.
5. **Production verifier closes at the signature-loop yield:** expected rejection `QUEUE_ERROR_QUEUE_ABORTED`, normal harness exit, and no unhandled rejection/crash. The real pool is closed on submission 8; the loop yields with earlier promises already observed. Log: `bugs-worker-electra-close.log`.

Each final probe exited 0; expected negative outcomes are caught and recorded by the harness. A separate Python read-only assertion pass checked all five outcomes, event ordering, dense/initial-registry counts, and absence of unhandled-rejection output.

Exact command pattern (run sequentially):

```sh
docker exec \
  -e BATCH_REF=c45c978f0cc34ad211b89725effb0757362e5435 \
  -e BATCH_FORK=phase0 \
  -e BATCH_SLASH=9 \
  -e BATCH_BLS=worker \
  pkfix-dev node \
  --import /home/openclaw/scratch/pubkey-poison/review2/bug-review-loader.mjs \
  /home/openclaw/scratch/pubkey-poison/batch-baseline-harness.mjs
```

Repeat with `BATCH_FORK=electra`; for the three controls additionally set `BATCH_CONTROL=wrong-key`, `state-root`, or `close`. The loader changes only fixture generation/input or the harness's pool-close trigger for those controls, not application code. Wrong-key fixture generation deliberately skips operation-signature verification so that the invalid fixture can reach the real independent verifier. State-root and close controls otherwise retain the valid fixture.

The first wrong-key and state-root runs each reached an expected application rejection but exited 1 because the old harness tried to JSON-serialize the entire error type containing BigInts. Their original logs are retained (`bugs-worker-electra-wrong-key.log`, `bugs-worker-electra-state-root.log`). The loader's harness-only reporting change records `error.type.code`, and the named retry logs above supersede those reporting failures. A preliminary container metadata query also showed container Git cannot resolve the host worktree's parent `.git` path; revision/cleanliness checks were performed successfully on the host instead.

## Limits / work not performed

- No source/worktree edits, builds, installs, dependency reconciliation, commits, broad test suites, external writes, or additional agents. Only the requested review artifact and scratch loader/logs were written. Existing verify2 was not duplicated.
- Did not independently rerun the native Zig/spec suites, checkpoint/activation regression suites, persisted-file roundtrip tests, or synchronous-verifier unit suites. Their supplied reports/logs were read as supporting evidence, not counted as tests executed by this reviewer.
- Checkpoint provenance/branch/finalization safety and ordinary-path parallel submission were source-traced, not independently exercised through live fork choice or a devnet. Execution-engine/DA failure races were source-traced; the executed abort/error controls are the state-root failure and production-pool close described above.
- The native addon is the existing current artifact, not an independently rebuilt native binary. The probes establish current-source application-caller/BLS-worker behavior, not end-to-end network or complete fork coverage.
