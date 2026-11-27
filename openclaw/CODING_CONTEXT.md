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
python3 ~/.openclaw/workspace/scripts/review/check-lint-readiness.py --repo "$PWD"
pnpm lint

# Type check
pnpm check-types

# Unit tests (specific file)
pnpm vitest run --project unit <path/to/test.ts>

# Unit tests (specific package)
pnpm vitest run --project unit packages/<pkg>/test/unit/
```

Do not invoke pnpm if that check fails: even `pnpm vitest` can reconcile dependencies and prune a shared virtual store. Use an independently prepared worktree-local `node_modules`/virtual store; never link another checkout's `node_modules` or `.pnpm`. Rerun the check after setup changes, immediately before package-manager use. This is an opt-in installed-directory containment check, not dependency/version readiness or protection against later pnpm config overrides; normal package symlinks and the shared content-addressed store are outside its scope. Missing or unsupported metadata needs inspection, not an install/repair attempt. For an already validated test setup, a direct local Vitest JS entrypoint avoids pnpm's reconciliation path; it does not make shared dependencies isolated.

Before treating local lint as repository verification, inspect the lint-readiness JSON: it compares the declared/root-lockfile Biome metadata with the installed package version and root config bytes with HEAD. A stale version, changed config or unsupported input blocks that metadata check; intentional config changes need review, not automatic reversal. A reduced/compatibility config run is partial evidence, not a repository lint pass. This read-only helper does not execute lint or verify executable provenance, extended config packages, runtime, dependency containment or full CI parity; retain the actual repository lint command/result and relevant overrides. It grants no install or repair authority.

## Shared Verification Process Control

For authorized local verification stops/restarts, prefer the cancellation tool using the retained task-owned job/session handle. Otherwise establish ownership from the task's launch record, verify the exact PID's current start identity, command and workdir, and recheck immediately before signalling. Matching identity alone does not prove ownership. Never choose targets through broad process-name matching, `pkill`/`killall`, or an unverified process group. Group signalling requires verified task ownership of every affected member; otherwise leave processes untouched and report the blocker. This guidance grants no additional stopping or restart authority.

## Implementation Behavior Evidence

For behavior investigations and implementation-validation claims:

1. Name the evidence layer: dependency/library, target binding/component, application caller, or end-to-end. Record the target revision/diff, relevant local overrides and the dependency/version or artifact actually loaded; a library probe alone does not establish target-application behavior.
2. Before a behavior verdict, trace the relevant event-driven and timer/poll/retry entry points and their shared state, including registration/eligibility, cancellation and expiry. Record which delivery orders and recovery paths were source-traced and which were executed; qualify conclusions for relevant untraced paths.
3. For persisted or derived state changes, trace the relevant producers/initializers and consumers, including fresh/genesis initialization versus upgrade/reload paths where applicable. Choose narrow coverage for each materially distinct path and record paths not executed; transition-path coverage alone does not prove initialization correctness.
4. Run the narrowest check through the claimed target entry point. Retain the command, exit status, log, actual test counts where applicable, and the inputs/path exercised. State observed results separately from source-backed conclusions or inference. Component/caller execution and source tracing are not end-to-end runtime proof.
5. If the claimed target path cannot run within the authorized setup, record the blocker and untested scope explicitly and qualify the conclusion. This evidence requirement does not authorize dependency installs, live maintenance or task expansion.

For cache/resource lifecycle changes, trace from insertion/acquisition through relevant early returns, synchronous helper throws and awaited rejections, including work before explicit validation. Identify when ownership transfers to a downstream consumer and which path must release or retain the resource. Choose narrow coverage for materially distinct exceptional exits, handled/converted failures and successful handoffs where relevant; record unexecuted paths. Do not prescribe unconditional `finally` cleanup when handed-off work still owns or needs the resource.

For deferred or unknown-parent cache paths, trace applicable cheap structural/index and slot/time-window admission checks before native verification or retention, where those checks are semantically available. Authentication does not establish bounded cache admission. Reason about attacker-controlled slot/priority keys under the actual eviction ordering; choose narrow coverage for rejection of out-of-range input and retention of legitimate pending input. Record deferred checks and unexecuted paths explicitly.

Before deferring a behavioral failure as pre-existing or unrelated, reproduce it on a comparable baseline through the relevant target entry point, recording both revisions/diffs, relevant inputs and execution ordering, dependency/setup differences, and observed outcomes. Identical arguments or source shape, or library-only/mock evidence, do not establish equivalent baseline behavior. If a comparable baseline is infeasible, mark attribution unverified and record the blocker; this does not authorize setup changes or unrelated fixes.

For failure-scenario fixes, choose verification that reproduces the claimed trigger (e.g. a misbehaving peer or request race), not only healthy operation. Compare the baseline and changed revision with the same trigger and materially comparable configuration, retaining commands, inputs and observed failure/recovery outcomes. Happy-path finality alone does not establish that the failure path is fixed. When practical, verify the targeted regression check fails without the fix and passes with it. If the scenario or baseline cannot run in the authorized setup, record the blocker and untested scope; this requirement does not authorize a new devnet, disruptive traffic, installs or unrelated work.

For runtime-option or soak/benchmark claims, verify the actual launch path, executing runtime and version, relevant effective options and measured process/start identity. Corroborate runtime attribution with that process's executable path and available runtime-specific evidence (e.g. `process.versions.bun`); Node-compatible `process.version`, an unrelated `node -v`, or an image label alone is insufficient. Image/wrapper/deployment state alone is insufficient; failed/skipped tasks may leave restart handlers unapplied. Inspect only relevant non-secret settings, not broad environment dumps. If runtime attribution cannot be verified, mark it unknown; if activation is unverified, qualify the result. This check grants no restart or deployment authority.

## Merge / Conflict / Rollback Evidence

Before resolving an upstream merge conflict, compare the merge base, pre-merge task head and incoming upstream revision, including the upstream change's purpose. Preserve task requirements while incorporating intentional upstream changes; do not select "ours" or "theirs" mechanically. Record the resolution rationale and run narrow affected-behavior checks on the resulting merge tree, retaining its revision/diff and results. Keep earlier verification attributed to its original tree, explicitly naming relevant suites not rerun. Recheck PR title, description and test claims against the resulting diff/head. This guidance does not grant merge, push or deployment authority.

Before a requested revert or rollback, read the current task head/diff and latest applicable owner/reviewer requirements. Map the unwanted behavior to exact hunks/commits; preserve still-required changes even when bundled with the rollback target. Inspect unfamiliar or parallel-worker changes before undoing them. Check the resulting tree/diff against those requirements and run narrow affected-behavior checks. Attribute earlier verification to its original tree and name relevant checks not rerun. Recheck PR title, description and test claims against the resulting diff/head. This guidance grants no additional write, push or deployment authority.

## Spec-Change Evidence

For changes exercised by upstream spec fixtures, record the following in the task's tracker **while generating/installing fixtures and running tests**, before claiming spec compatibility:

1. Read the closest existing fork migration or implementation pattern first; record the reference and keep the change scoped to the requested behavior.
2. Pin the full `consensus-specs` revision. Save the actual generation command, working directory, preset/fork/runner/handler/case selection, source-tree clean/dirty status (preserve the patch and relevant untracked inputs if dirty), exit status and log. For downloaded fixtures, record the immutable bundle reference and checksum instead; an unproven source revision stays explicitly unknown.
3. Save a case-relative artifact inventory with per-file SHA256 hashes **outside the fixture root**, including YAML/config/metadata and SSZ inputs. Record how the selected fixtures were installed into the root consumed by Lodestar's harness; a separate generated directory is not evidence that Lodestar tested it.
4. Record the tested Lodestar HEAD **and** working-tree diff/harness overrides and relevant untracked test inputs. Run the narrowest relevant file/case selection, retaining the exact command, exit status and log. Report actual passed/failed/skipped counts, plus generated-case coverage and named fork/runner/handler/filter exclusions separately. Harness skips may hide whole fixture groups; a skipped-suite placeholder is not a count of skipped fixture cases. Preserve any local-only runner or unskip patch with the evidence without changing tracked skip policy unless requested.
5. Inspect representative fixture inputs and map materially changed input-dependent paths to named cases actually executed. Where relevant, distinguish valid nonempty inputs (e.g. transactions or `extra_data`) from empty/default inputs and rejected cases. Passing counts and a successful negative control establish only their exercised behavior, not coverage of other input paths. Record missing paths as untested; this evidence check does not expand the task into unsolicited fixture generation or implementation.
6. Link this evidence in the tracker/PR test summary and state the untested scope. A clean, fresh source cache (`generatedFixturesVerified=false`) proves prerequisites only; neither that cache nor a fixture hash inventory proves generator provenance, coverage or passing tests on its own. Do not reconstruct generation-time proof from later file timestamps or relabel an old run as a current one.

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

## Storage Maintenance Evidence

For pruning, compaction or storage-latency changes:

1. Pin the backend/version, revision/diff, encoded range boundaries and operation being measured. A fulfilled maintenance API call or empty logical range does not prove physical reclamation or restored seek performance.
2. Reproduce the relevant retained-data state with the real backend. For the long-held-iterator deletion case, retain evidence that plain compaction leaves storage behind and the proposed rewrite removes it. Preserve live boundary/out-of-range records; use deterministic storage assertions, not wall-clock test thresholds.
3. For sentinel-based approaches, verify noncollision, range bounds, write/compact/delete ordering and cleanup. Bounds do not guarantee physical isolation: overlapping storage files may be rewritten. This guidance does not authorize live maintenance or prescribe sentinel use generally.
4. Record comparable before/after measurements of the same operation and range, distinguishing approximate range size from total filesystem size. Report startup latency, archive progress and API sync separately; none alone proves the others recovered.

## Review Suggestion Completeness

Before presenting a GitHub suggestion block as apply-ready, check its effect against the current head, including required imports, types, call-site changes and test expectations outside the selected hunk. Reserve suggestion blocks for self-contained changes. If dependent edits are needed, explain the complete change in prose or provide a complete patch only within existing authorization; put illustrative snippets in ordinary code fences labeled "not apply-as-is", not UI-applicable suggestion blocks.

Distinguish source-inspected completeness from an actually applied and tested patch. After a suggestion is applied or follow-up changes are pushed, verify the affected behavior/checks on the resulting head before renewing a verdict. Keep prior tests and review conclusions attributed to their original revision, and use CI Status Evidence below for current-head CI claims. This guidance grants no write or setup authority.

## CI Status Evidence

When reporting PR CI status or readiness:

1. Collect evidence for the current head: `python3 ~/.openclaw/workspace/scripts/github/check-pr-ci-evidence.py --repo <owner/repo> --pr <n> --expect-workflow "<exact task-relevant workflow name>"` (read-only GETs). Repeat `--expect-workflow` for each task-required workflow display name, not job labels; omitting expectations imposes no coverage requirement. The helper reconciles workflow runs, check runs and status contexts. Cite `headSha`/`observedAt`, the `nonGreen` links and requested `workflowCoverage` results. Exit 0 only means evidence was collected: read `verdict`. Exit 1 / `verdict: unknown` means evidence is incomplete, not green.
2. "0 failing checks" is not "CI green". `gh pr checks` and check-run rollups omit workflow runs that never started, e.g. fork-PR runs awaiting approval (`action_required`). Report `action_required`, pending, cancelled and `no_ci` results explicitly. A superseded cancellation is not a current failure; confirm the replacement result. Skipped/neutral is not an executed test.
3. `observed_green` means nothing current is failing, gated, pending or cancelled and at least one eligible CI item succeeded. Each explicit workflow expectation needs an exact-name successful latest run for at least one eligible workflow/event on this head (`pull_request`/`push`/`merge_group`); an older success cannot satisfy a newer skipped run of the same workflow/event. Unmet expectations yield `insufficient_coverage` unless an observed blocker takes precedence; inspect `workflowCoverage` with either verdict. This does not discover branch-protection requirements or prove job/suite execution. Inspect task-required job/suite outcomes before claiming readiness or removing temporary CI triggers; record explicit owner acceptance for any allowed red result. Unrelated workflows, older-head runs and local tests do not establish current task CI coverage. Keep local verification, CI readiness, review readiness and merge/deployment conditions separate.
4. Evidence collection grants no authority to approve workflows, rerun jobs, change permissions or retrigger CI. Unchanged known blockers do not need repeated alerts.

## Code Style

- **Formatter:** Biome (not Prettier/ESLint)
- **Import order:** Sorted alphabetically by package name (biome enforces this)
- **No default exports** — always use named exports
- **Error types:** Use `LodestarError<T>` with typed error codes (enum + union type)
- **Worker/RPC errors:** Before recommending structured error codes, trace the actual serializer and consuming caller. Fields dropped in transit cannot provide caller-side code handling or observability. Keep serialization changes outside the task unless explicitly in scope.
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
