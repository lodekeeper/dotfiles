# CODING_CONTEXT.md — Project Context for Sub-Agents

Hand this file to Codex CLI or Claude CLI when spawning implementation tasks.
It gives them enough context to work independently in a Lodestar worktree.

## Project: Lodestar

- **What:** Ethereum consensus client (beacon node + validator client)
- **Language:** TypeScript (strict mode)
- **Monorepo:** pnpm workspaces, ~20 packages
- **Runtime:** Node.js v24+
- **Key packages:**
  - `packages/beacon-node` — the beacon node (networking, sync, chain, API)
  - `packages/validator` — validator client
  - `packages/state-transition` — state transition logic (STF)
  - `packages/fork-choice` — fork choice implementation
  - `packages/types` — SSZ type definitions
  - `packages/params` — chain parameters/constants
  - `packages/cli` — CLI entry point
  - `packages/reqresp` — request/response protocol (libp2p)

## Build & Test Commands

```bash
# ALWAYS run from worktree root
source ~/.nvm/nvm.sh && nvm use 24

# Before pnpm in a reused worktree; stop if installed directories are shared/unverified
python3 ~/.openclaw/workspace/scripts/review/check-worktree-deps.py --repo "$PWD"

# Build (required before tests)
pnpm build

# Lint (biome — MANDATORY before every commit/push, fast check)
# ⚠️ DO NOT commit or push without passing lint! No exceptions.
pnpm lint

# Type check
pnpm check-types

# Unit tests (specific file)
pnpm vitest run --project unit <path/to/test.ts>

# Unit tests (specific package)
pnpm vitest run --project unit packages/<pkg>/test/unit/
```

Do not invoke pnpm if that check fails: even `pnpm vitest` can reconcile dependencies and prune a shared virtual store. Use an independently prepared worktree-local `node_modules`/virtual store; never link another checkout's `node_modules` or `.pnpm`. Rerun the check after setup changes, immediately before package-manager use. This is an opt-in installed-directory containment check, not dependency/version readiness or protection against later pnpm config overrides; normal package symlinks and the shared content-addressed store are outside its scope. Missing or unsupported metadata needs inspection, not an install/repair attempt. For an already validated test setup, a direct local Vitest JS entrypoint avoids pnpm's reconciliation path; it does not make shared dependencies isolated.

## Spec-Change Evidence

For changes exercised by upstream spec fixtures, record the following in the task's tracker **while generating/installing fixtures and running tests**, before claiming spec compatibility:

1. Read the closest existing fork migration or implementation pattern first; record the reference and keep the change scoped to the requested behavior.
2. Pin the full `consensus-specs` revision. Save the actual generation command, working directory, preset/fork/runner/handler/case selection, source-tree clean/dirty status (preserve the patch and relevant untracked inputs if dirty), exit status and log. For downloaded fixtures, record the immutable bundle reference and checksum instead; an unproven source revision stays explicitly unknown.
3. Save a case-relative artifact inventory with per-file SHA256 hashes **outside the fixture root**, including YAML/config/metadata and SSZ inputs. Record how the selected fixtures were installed into the root consumed by Lodestar's harness; a separate generated directory is not evidence that Lodestar tested it.
4. Record the tested Lodestar HEAD **and** working-tree diff/harness overrides and relevant untracked test inputs. Run the narrowest relevant file/case selection, retaining the exact command, exit status and log. Report actual passed/failed/skipped counts, plus generated-case coverage and named fork/runner/handler/filter exclusions separately. Harness skips may hide whole fixture groups; a skipped-suite placeholder is not a count of skipped fixture cases. Preserve any local-only runner or unskip patch with the evidence without changing tracked skip policy unless requested.
5. Link this evidence in the tracker/PR test summary and state the untested scope. A clean, fresh source cache (`generatedFixturesVerified=false`) proves prerequisites only; neither that cache nor a fixture hash inventory proves generator provenance, coverage or passing tests on its own. Do not reconstruct generation-time proof from later file timestamps or relabel an old run as a current one.

## Reset-Timed Configuration Evidence

For network configuration changes tied to a reset or activation:

1. Pin the upstream config revision and generated artifact, plus the intended network iteration and UTC reset/activation times. Record any normalization or combination of separate identity metadata and runtime parameters. Distinguish automatically rolling identity fields from static fork and blob schedules.
2. Check relevant prior/current/next iteration boundaries for both identity and fork/limit resolution. Record expected behavior and known incompatibilities separately. If pre-reset compatibility is deliberately out of scope, preserve its explicit merge/deployment restriction; do not call that incompatibility source-fixed or add an unrequested scheduler.
3. Record review readiness, merge safety and deployment safety separately in the tracker/PR, with their actual outstanding conditions. Passing CI or “ready for review” does not satisfy upstream-finalization, final-config-parity or reset-timing gates. Recheck applicable conditions using fresh read-only evidence before releasing a gate; merge/deploy only within authorization.

## Async Retry / Coalescing Evidence

When changing async request deduplication, retries or in-flight trigger handling:

1. Read the actual helper contract and callers. Promise fulfillment is not necessarily success: helpers may catch errors or resolve with null/missing/partial results. Identify the observable completion condition, not just `.catch()`.
2. Trace triggers before, during and after an in-flight request. Preserve still-actionable triggers with an eligibility-aware, bounded trailing retry where required; suppress redundant work after success, and honor retry limits, cancellation and terminal/stale-target guards.
3. Use controlled deferred promises to test event ordering without sleeps: start request A, deliver trigger B while A is pending, settle A, then assert required work and request counts. Cover relevant success, rejection and handled-miss/null paths, plus no-trigger, repeated-trigger and terminal-state cases.
4. For a race regression, verify the targeted test fails with the original behavior and passes with the fix when practical. Record the exact tested revision/diff, command and result; a test of a rejecting mock alone does not prove a helper's fulfilled-but-incomplete path.

## CI Status Evidence

When reporting PR CI status or readiness:

1. Collect evidence for the current head: `python3 ~/.openclaw/workspace/scripts/github/check-pr-ci-evidence.py --repo <owner/repo> --pr <n>` (read-only GETs). It reconciles workflow runs, check runs and status contexts and records `headSha`/`observedAt`; cite those and the `nonGreen` links. Exit 0 only means evidence was collected: read `verdict`. Exit 1 / `verdict: unknown` means evidence is incomplete, not green.
2. "0 failing checks" is not "CI green". `gh pr checks` and check-run rollups omit workflow runs that never started, e.g. fork-PR runs awaiting approval (`action_required`). Report `action_required`, pending, cancelled and `no_ci` results explicitly. A superseded cancellation is not a current failure; confirm the replacement result. Skipped/neutral is not an executed test.
3. `observed_green` means nothing current is failing, gated, pending or cancelled and at least one CI item (a `pull_request`/`push`/`merge_group` workflow run, a non-Actions check run or a status context) succeeded. It does not evaluate required-check coverage or prove that the relevant tests ran. Successful unrelated workflows, older-head runs and local tests do not establish current PR CI success. Keep local verification, CI readiness, review readiness and merge/deployment conditions separate.
4. Evidence collection grants no authority to approve workflows, rerun jobs, change permissions or retrigger CI. Unchanged known blockers do not need repeated alerts.

## Code Style

- **Formatter:** Biome (not Prettier/ESLint)
- **Import order:** Sorted alphabetically by package name (biome enforces this)
- **No default exports** — always use named exports
- **Error types:** Use `LodestarError<T>` with typed error codes (enum + union type)
- **Logging:** `this.logger.debug/verbose/info/warn/error` — structured with metadata objects
- **Metrics:** Prometheus-style via `this.metrics?.someMetric.inc({label: value})`

## Git Conventions

- **Commit messages:** Conventional commits — `fix:`, `feat:`, `chore:`, `refactor:`, `test:`
- **Sign commits:** `git commit -S -m "..."`
- **AI disclosure:** Add `🤖 Generated with AI assistance` to commit messages
- **Push to fork:** `git push fork <branch-name>`
- **PR target:** Usually `unstable` (or specific feature branch if noted)

## SSZ Types Pattern

```typescript
// Types defined in packages/types/src/<fork>/
export const MyType = new ContainerType({
  field1: UintNumberType,
  field2: RootType,
}, {typeName: "MyType"});
```

## Network Protocol Pattern

- Gossip topics: `packages/beacon-node/src/network/gossip/`
- Req/resp: `packages/beacon-node/src/network/reqresp/`
- Handlers: `packages/beacon-node/src/network/processor/gossipHandlers.ts`

## Key Patterns

- **Fork-aware code:** Use `isForkPostDeneb()`, `isForkPostFulu()` etc.
- **Config access:** `config.getForkName(slot)`, `config.getForkTypes(slot)`
- **Async patterns:** Prefer `async/await`, use `wrapError()` for error-or-result patterns
- **State access:** Via `chain.getHeadState()`, never hold references to old states

## ⚠️ Pre-Push Checklist (MANDATORY)

Before EVERY commit and push, run these in order:
1. `pnpm lint` — fast, catches formatting/import issues. **Must pass. No exceptions.**
2. `pnpm check-types` — catches type errors
3. Build if you changed exports: `pnpm build`

If lint fails, fix it before committing. `pnpm lint --write` auto-fixes most issues.

## Important: What NOT to do

- Don't modify files outside your worktree
- Don't run `pnpm install` unless told to (already done in worktree setup)
- Don't reformat files you didn't change (biome might want to, resist)
- Don't add dependencies without explicit approval
- **Don't commit or push without passing `pnpm lint`** — this is a hard rule from Nico
