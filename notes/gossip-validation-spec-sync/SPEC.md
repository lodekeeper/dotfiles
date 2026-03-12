# Feature: Gossip validation spec sync follow-up for PR #8965

## Problem
Lodestar merged PR #8965 to integrate executable gossip validation spec tests, but consensus-specs PR #4902 continued to evolve before release. The upstream ask is to build the unreleased phase0 gossip reftests locally from the consensus-specs PR branch (`make test k=gossip reftests=true fork=phase0`) and verify Lodestar still passes them.

Current Lodestar spec-test wiring is pinned to released consensus-spec fixtures under `packages/beacon-node/spec-tests`, so this task needs a local fixture-sync workflow for unreleased networking tests.

## Scope
- Generate unreleased **phase0 gossip** reftests from consensus-specs PR #4902 branch.
- Run Lodestar's gossip validation spec tests against those generated fixtures.
- Fix Lodestar behavior and/or test harness assumptions so all generated phase0 gossip validation spec tests pass.
- Push the resulting changes to a branch on `lodekeeper/lodestar`.

Out of scope for this pass:
- Opening a PR
- General spec-test version bumping for all non-networking suites
- Non-phase0 unreleased gossip fixtures unless needed to avoid breaking existing test runner behavior

## Approach
1. Create a fresh Lodestar worktree from `origin/unstable`.
2. Generate local phase0 gossip reftests from `~/consensus-specs` on the PR branch.
3. Bridge those fixtures into Lodestar's spec runner with the smallest possible change:
   - prefer an override/sync path for networking fixtures over changing the global spec-test source for every suite.
4. Run targeted gossip spec tests to identify failures.
5. Fix either:
   - Lodestar gossip validation semantics, or
   - the local test harness / fixture loading logic,
   whichever is actually wrong versus the spec.
6. Run the required quality gates:
   - targeted gossip spec tests against generated fixtures
   - full `test:spec` if the change affects generic spec-test wiring
   - `pnpm lint`
   - `pnpm check-types`

## Likely implementation areas
- `packages/beacon-node/test/spec/specTestVersioning.ts`
- `packages/beacon-node/test/spec/presets/networking.test.ts`
- `packages/beacon-node/test/spec/utils/gossipValidation.ts`
- possibly gossip validation implementations under `packages/beacon-node/src/chain/validation/*`

## Key design constraints
- Do not disturb the released-fixture path for unrelated spec suites unless necessary.
- Keep unreleased gossip-fixture support explicit and localizable.
- Prefer deterministic fixture import/copying over ad-hoc manual path edits.
- Any behavior change in validation code must be justified by the phase0 p2p-interface spec / executable tests, not by making the harness more permissive.

## Test Plan
- Generate phase0 gossip reftests from consensus-specs PR #4902 branch.
- Run the Lodestar networking spec suite against those local fixtures.
- If needed, run the entire Lodestar spec suite to ensure no global regression.
- Run `pnpm lint` and `pnpm check-types` before pushing.

## Acceptance Criteria
- [ ] Local consensus-specs PR #4902 phase0 gossip reftests are generated successfully.
- [ ] Lodestar consumes those generated fixtures for networking gossip tests.
- [ ] All generated phase0 gossip validation spec tests pass.
- [ ] `pnpm lint` passes.
- [ ] `pnpm check-types` passes.
- [ ] Changes are committed and pushed to a branch on `lodekeeper/lodestar`.
