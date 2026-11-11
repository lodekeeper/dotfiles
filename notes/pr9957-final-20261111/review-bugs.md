# Bug Hunter — narrow genesis follow-up
Reviewer: review-bugs
Reviewed commit: 4161c5d563c59241460c8a86c22b6609fcf7c953

## Result
No functional bugs found.

## Scope and source-trace conclusions
Reviewed only the new genesis lookahead initialization in `packages/state-transition/src/util/genesis.ts` and its regression test in `packages/beacon-node/test/e2e/interop/genesisState.test.ts`, with relevant helpers traced read-only. Compared against lodekeeper PR #10600 commit `93d239ae9ab73845c12640dbf1e4e8c55ac5339c`.

- Active selection is equivalent to #10600: genesis deposit registration assigns far-future activation and exit epochs; `applyDeposits` activates qualifying validators at epoch zero. No transition between lookahead epochs introduces an activation or exit. Recomputing active indices for epochs zero and one therefore yields the same set as reusing genesis active indices.
- Lookahead runs after deposit balance application, effective-balance recomputation, cache increment updates, and state commit. `computeProposerIndices` receives the post-deposit `epochCtx.effectiveBalanceIncrements`, not the initially empty active-validator cache.
- The inclusive genesis-through-`MIN_SEED_LOOKAHEAD` range matches `ProposerLookahead` vector length. `computeProposerIndices` derives an epoch-specific proposer-domain seed and hashes each absolute slot; genesis initializes every randao mix to the supplied eth1 block hash.
- Fulu and Gloas follow the same initialization branch; Gloas has no slashed genesis validators to exclude. The sampler uses the Electra-or-later balance/randomness path. Later fork-version assignments do not invalidate the seed (which does not use the fork version).
- The regression test builds Electra and Fulu genesis states with identical deposits and randao input. Rebuilding the Electra epoch cache supplies actual post-deposit active indices and balances. Its current/next proposer methods compute expected schedules rather than reading Fulu's lookahead, so the comparison is not tautological. The inherited mainnet Fulu epoch leaves the Electra reference pre-Fulu at epochs zero and one.

## Checks executed / limitations
Executed read-only `git rev-parse HEAD`, `git show` for the reference commit, `git status --short`, and targeted source/diff inspection using `cat`, `sed`, and `rg`. Confirmed the requested HEAD and a clean worktree. One source-discovery `rg` invocation included nonexistent directories and exited 2; relevant type/preset definitions were nevertheless found and inspected in its output. No tests or builds were executed; conclusions are source-only. No dependencies were installed and no source or external state was modified.
