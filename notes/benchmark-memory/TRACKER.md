# Benchmark memory / OOM — Tracker

Last updated: 2026-03-31 15:16 UTC

## Goal
Get full `pnpm benchmark` on Lodestar unstable to pass consistently without OOM, with a memory profile that is leaner than the current unstable state.

## Phase Plan
- [x] Identify first-order regressions across merged benchmark PRs
- [x] Validate that `clone(true)` regression was real but insufficient to explain all OOMs
- [x] Reproduce OOM at 4GB and 8GB on CI-equivalent runs
- [x] Architecture consult with gpt-advisor (round 1)
- [~] Converge on fix strategy with more gpt-advisor back-and-forth
- [~] Prototype memory cleanup / cache eviction changes on `fix/benchmark-memory-oom`
- [ ] Implement final lean-path fix + remove incidental regressions
- [ ] Full local benchmark verification on chosen heap target
- [ ] Open PR and keep iterating until benchmark CI is green

## Completed Work
- Merged #9137 / #9138 but benchmark CI still OOMs on unstable.
- Identified main retained-memory regression source: Electra perf-state singletons introduced in #9131.
- Added `clearPerfStateCache()` experiment and called it before heavy benchmark files; this moves the OOM later but does not solve it.
- Confirmed 8GB is not sufficient on unstable CI; `loadState.test.ts` still OOMs there.
- Confirmed 4GB still OOMs locally even with broader cache clearing; latest local 4GB experiment moved the crash to ~227 passing.

## Current Working Hypothesis
The real issue is accumulated retained memory in the single-process benchmark runner:
1. new long-lived Electra singleton states,
2. heavy clone/caching behavior on large-vc paths,
3. benchmark-file/module-level retention that `clearPerfStateCache()` cannot fully clear.

## Branch / Worktree
- Branch: `fix/benchmark-memory-oom`
- Worktree: `~/lodestar`

## Next Immediate Steps
1. Run another gpt-advisor round focused on minimal-risk patch shape.
2. Decide between (a) dedicated lean large-vc helper, (b) stronger cleanup of heavy benchmark files, (c) selective process isolation support.
3. Implement the chosen patch on top of current local branch.
4. Re-run full benchmarks locally and only then open PR.

## Interop/Validation Target
- Full `pnpm benchmark` passes locally on the intended heap target.
- Benchmark CI on unstable stops OOMing.

## Spec Compliance Artifacts
- N/A (test/perf infrastructure change, not consensus-spec behavior)
