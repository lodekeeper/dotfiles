# alpha4-ptc — Tracker

Last updated: 2026-04-12 18:05 UTC

## Goal
Align Lodestar with consensus-specs v1.7.0-alpha.4 only as far as needed to pass the relevant spec tests for merged consensus-specs PR #4979, while keeping lint, typecheck, and build green.

## Constraints from Nico
- Base from fresh `unstable` worktree exactly at commit `2219bb0cb8c2af1770a302e16e95356100764e59`.
- Focus on `ethereum/consensus-specs#4979` only; ignore unrelated alpha.4 changes unless they block target spec tests.
- Do **not** open a PR.
- Do **not** include GitHub references in commit messages.
- Push finished work only to a branch on my fork and report the branch name.
- Prefer existing spec-test skip infrastructure for `#4558`-dependent containers; only add missing SSZ containers if unavoidable, and avoid runtime code changes for that.
- Must also update alpha.4 spec refs / test versions (`ethspecify`, `spec-tests-version.json`).
- Unskip `^gloas/operations/voluntary_exit/pyspec_tests/builder_voluntary_exit__success$`.
- Address twoeths / Tuyen review concerns, especially: do not read PTC committees directly from the state tree during hot-path lookups; use an epoch-cache style approach similar to proposer lookahead.

## Current branch / worktree
- Worktree: `~/lodestar-alpha4-spec-4979`
- Branch: `feat/alpha4-spec-4979`
- Base commit: `2219bb0cb8c2af1770a302e16e95356100764e59`

## Research completed
- Pulled local artifacts under `tmp/alpha4-context/`:
  - `pr-4979.diff`, `pr-4979-comments.json`, `pr-4979-issue-comments.json`
  - `pr-9047.diff`, `pr-9047-comments.json`, `comment-2951596130.json`
  - `pr-12.diff`, `pr-12-comments.json`
- Key spec change from `#4979`:
  - add `ptc_window` to Gloas/Heze state
  - `get_ptc()` reads from cached state window
  - `process_ptc_window()` shifts the window each epoch and computes the new trailing epoch
  - `initialize_ptc_window()` fills previous/current/lookahead epochs on fork/genesis
  - `get_ptc_assignment()` allows up to `current_epoch + MIN_SEED_LOOKAHEAD`
- Key Lodestar implementation constraint from `#9047` / `#12` review:
  - keep hot-path committee reads on `epochCtx`/cache, not state-tree traversal
  - mirror proposer-lookahead pattern where state stores canonical data but epoch cache reads/copies it once
  - avoid leaving `specrefs/functions.yml` in speculative state beyond actual alpha.4 update

## Initial hypothesis
Implement the new `ptcWindow` state field and state-transition maintenance so spec tests pass, but hydrate/read an epoch-cache representation from state (similar to `proposerLookahead`) so runtime lookups continue to use cached arrays rather than repeated `state.ptcWindow[...]` tree access.

## Phase Plan
- [x] Scope clarified with Nico
- [x] Fresh worktree created at exact requested base commit
- [x] Collected spec / review context
- [x] Architecture pass — proceeded with direct implementation after sub-agent auto-reporting proved flaky
- [x] Implementation — core alpha.4 PTC-window patch landed in the worktree
- [~] Spec tests + lint + typecheck + build — `pnpm build` ✅, `pnpm check-types` ✅, `pnpm lint --write` ✅, `pnpm download-spec-tests` ✅, full `pnpm test:spec` still running in process session `tidy-haven` (alpha.4/Gloas suites passing so far)
- [ ] Reviewer pass
- [ ] Push branch to fork and report branch name

## Next Immediate Steps
1. Let the full `pnpm test:spec` run finish and react only if it surfaces a failure.
2. Re-run `pnpm lint --write` if the spec run or any follow-up edits touched files.
3. Commit without GitHub refs, push branch to fork, and report the branch name to Nico.

## Interop/Validation Target
- Relevant alpha.4 spec tests for `#4979` pass.
- `pnpm lint`, `pnpm check-types`, and `pnpm build` pass.

## Spec Compliance Artifacts
- Added canonical `ptcWindow` to Gloas SSZ state types.
- Hydrated previous/current PTC slices into `epochCtx` from `state.ptcWindow` so hot-path reads stay cache-backed.
- Added epoch rotation for `ptcWindow` and initialization on Gloas upgrade / genesis-at-fork path.
- Bumped `spec-tests-version.json` and `specrefs/.ethspecify.yml` to `v1.7.0-alpha.4` and refreshed `specrefs/`.
- Unskipped `gloas/operations/voluntary_exit/pyspec_tests/builder_voluntary_exit__success`.
