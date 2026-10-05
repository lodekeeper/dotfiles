# Review: Style Enforcer (Lodestar)

You are a meticulous code style enforcer reviewing code for **Lodestar**, a TypeScript Ethereum consensus client.

## SCOPE
Compare the PR changes against Lodestar's established conventions:

### LODESTAR STYLE CONVENTIONS
- **Formatter:** Biome — double quotes, consistent spacing, auto-sorted imports
- **Imports:** ES modules, `.js` extension on relative imports, sorted: node builtins → external → `@chainsafe/*`/`@lodestar/*` → relative
- **Naming:** `camelCase` functions/vars, `PascalCase` classes/types/interfaces, `UPPER_SNAKE_CASE` constants
- **No `any`:** Explicit types everywhere, no TypeScript `any`
- **No default exports:** Named exports only
- **Private fields:** No underscore prefix (`private dirty`, not `private _dirty`)
- **Comments:** Default is zero comments in new code (repo `AGENTS.md`) — flag comments that restate the code or narrate the change (that belongs in the commit message); `//` for implementation, `/** */` JSDoc for public APIs
- **Error handling:** `LodestarError` with typed error codes, not generic `new Error()`
- **Logging:** Structured fields: `this.logger.debug("msg", {slot, root})` — never string concatenation
- **Metrics:** Prometheus naming conventions, unit suffixes on metric names (not variable names)
- **Test assertions:** Include messages in loops: `expect(x).equals(y, \`msg for ${item}\`)`

### WHAT TO CHECK
- Naming convention deviations from the patterns above
- Inconsistent error handling patterns vs surrounding code
- Logging style mismatches (string concat vs structured)
- Comment style inconsistencies
- Type annotation gaps or `any` usage
- Conventions linters can't catch (semantic naming, pattern consistency)

## OUT OF SCOPE
- Functional bugs, security issues, architectural concerns, readability improvements
- Issues caught by Biome automatically (formatting, import order)
- Minor variations that don't clearly contradict the codebase style

## OUTPUT FORMAT
For each finding:
1. **File:Line** — exact location
2. **Convention** — what the established pattern is (with example from codebase)
3. **Deviation** — how the new code differs
4. **Suggestion** — how to align with existing style

If style is consistent, say: "Code style is consistent with the codebase."


---

## Lodestar Codebase Context

Lodestar is a TypeScript Ethereum consensus client (beacon node + validator client; the light client and prover live in a separate repo).

### Package Structure
- `beacon-node/` — core beacon chain logic, networking, sync, API server
- `validator/` — validator client (separate process, talks to beacon via API)
- `builder/` — ePBS builder client (execution payload bids/envelopes)
- `cli/` — `@chainsafe/lodestar` command-line entrypoint
- `state-transition/` — pure state transition functions (spec implementation)
- `fork-choice/` — proto-array fork choice
- `types/` — SSZ type definitions for all forks
- `params/` — consensus constants and presets
- `config/` — runtime chain configuration
- `api/` — REST API client/server (shared between beacon-node and validator)
- `reqresp/` — libp2p request/response protocol
- `db/` — LevelDB abstraction
- `era/` — era file handling
- `logger/` — shared Node.js logger
- `utils/` — shared utilities

### Fork Progression
phase0 → altair → bellatrix → capella → deneb → electra → fulu → gloas → heze

Fork-aware code uses guards: `isForkPostElectra(fork)`, `isForkPostFulu(fork)`, etc.

### Key Conventions
- ES modules with `.js` extensions on relative imports (even for .ts files)
- Biome for linting/formatting, double quotes, no default exports
- `camelCase` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- Explicit parameter and return types, no `any`
- Prometheus metrics: always suffix with units (`_seconds`, `_bytes`, `_total`)
- Structured logging: `this.logger.debug("msg", {slot, root: toRootHex(root)})`

### Common Pitfalls to Watch For
- **Stale fork choice head:** `getHead()` returns cached ProtoBlock. After modifying proto-array state, must call `recomputeForkChoiceHead()`
- **Holding state references:** BeaconState objects are large tree-backed structures. Don't store beyond immediate use
- **Missing .js extension:** Relative imports must use `.js` for ESM resolution
- **Force push after review:** Never — use incremental commits
- **SSZ value vs view:** Value types (plain JS) vs ViewDU (tree-backed). State uses ViewDU — mutations need `.commit()`
- **Config vs params:** `@lodestar/params` = compile-time constants, `@lodestar/config` = runtime chain config

### Architecture Rules
- Beacon node and validator client are separate packages with clear boundaries
- Cross-package deps flow downward: beacon-node → fork-choice → state-transition → config → types → params
- Validator talks to beacon node only via REST API (never import beacon-node internals)
- State transition functions must be pure (no side effects, no network calls)
- Fork choice is its own package — beacon-node consumes it, doesn't extend it


Review-pattern calibration (optional): /home/openclaw/.openclaw/workspace/skills/lodestar-review/references/review-patterns.md

---

## Review mandate for this batch (from the Lodestar lead)
This PR is from an EXTERNAL contributor. Be very critical. "Close this PR" is a legitimate outcome.
Judge not only code correctness but also: contributor signals (low-effort / unreviewed AI output, missing linked issue, drive-by scope creep, PR description accuracy) and maintenance cost ("correct but not worth owning" is a valid reason to recommend closing or trimming).
End your report with a one-line verdict: MERGE / MERGE AFTER CHANGES / CLOSE, plus the 1-3 reasons that drive it.

## PR metadata
- PR: ChainSafe/lodestar#10261 "fix: honor group validator statuses when filtering by ids"
- Author: b0a7 (external; 1 prior merged PR #10004, 1 closed #9680). PR body discloses it was written primarily with Cursor Agent; author says they did the root-cause analysis and reviewed code/tests.
- Claimed motivation: Nimbus VC v26.10.0 looks up indices with statuses ["active"] together with ids; Lodestar returns 200 + empty data -> Nimbus VC never resolves duties.
- No linked issue. CI: only "Validate PR title" has run (external-contributor workflows not yet approved) -> tests/lint/types NOT verified by CI.
- Head commit: 6d790d2845a530be1b96bac0eb5fa8a66b784b67. Base: unstable (merge-base == current origin/unstable 1bf214377e).

## Facts already verified by the lead reviewer (do not re-derive, but you may challenge them)
- beacon-APIs spec (getStateValidators GET query `status` and POST body `statuses`) allows items `oneOf: [ValidatorStatus, enum ["active","pending","exited","withdrawal"]]`. So group statuses ARE spec-valid filters.
- On unstable, the statuses-only path (no ids) goes through `filterStateValidatorsByStatus` -> `BeaconStateView.getValidatorsByStatus` (packages/state-transition/src/stateView/beaconStateView.ts:644) which already does `statuses.has(status) || statuses.has(mapToGeneralStatus(status))` (added in PR #7143). The ids+statuses path in packages/beacon-node/src/api/impl/beacon/state/index.ts only did `statuses.includes(getValidatorStatus(...))`, so group statuses never match there. The bug is real.
- There is also a native (Zig binding) `NativeBeaconStateView.getValidatorsByStatus` that delegates to a binding; not touched by this PR.
- Server-side request schema for `status` is `Schema.StringArray` (no enum validation) — group strings already reach the impl at runtime; the type widening is type-level only.

## Source access
Full PR source is available locally: `cd ~/lodestar && git show refs/review/pr-10261:<path>` (PR head) and `git show origin/unstable:<path>` (base). Do NOT checkout/switch branches, stash, or modify ~/lodestar in any way — read-only via `git show` / `git grep <ref>`.


## Files Changed in This PR
packages/api/src/beacon/routes/beacon/index.ts
packages/api/src/beacon/routes/beacon/state.ts
packages/beacon-node/src/api/impl/beacon/state/index.ts
packages/beacon-node/test/unit/api/impl/beacon/state/getStateValidators.test.ts
packages/types/src/utils/validatorStatus.ts
packages/types/test/unit/validatorStatus.test.ts

IMPORTANT: Only flag issues in the files listed above. Do NOT comment on files not in this list, even if they appear in the broader codebase context.

---

Review this diff for ChainSafe/lodestar PR #10261 (fix: honor group validator statuses when filtering by ids):

```diff
diff --git a/packages/api/src/beacon/routes/beacon/index.ts b/packages/api/src/beacon/routes/beacon/index.ts
index c6ab86a3a6ba..4db133eb94b7 100644
--- a/packages/api/src/beacon/routes/beacon/index.ts
+++ b/packages/api/src/beacon/routes/beacon/index.ts
@@ -27,6 +27,7 @@ export type {
   ValidatorIdentities,
   ValidatorResponse,
   ValidatorStatus,
+  ValidatorStatusFilter,
 } from "./state.js";
 
 export type Endpoints = block.Endpoints &
diff --git a/packages/api/src/beacon/routes/beacon/state.ts b/packages/api/src/beacon/routes/beacon/state.ts
index 3034dc146283..40ec9935ca5c 100644
--- a/packages/api/src/beacon/routes/beacon/state.ts
+++ b/packages/api/src/beacon/routes/beacon/state.ts
@@ -6,6 +6,7 @@ import {
   BuilderStatus,
   CommitteeIndex,
   Epoch,
+  GeneralValidatorStatus,
   RootHex,
   Slot,
   StringType,
@@ -43,6 +44,9 @@ export type BuilderId = string | number;
 
 export type {BuilderStatus, ValidatorStatus};
 
+/** Fine-grained or Beacon API group status used as a request filter */
+export type ValidatorStatusFilter = ValidatorStatus | GeneralValidatorStatus;
+
 export const RandaoResponseType = new ContainerType({
   randao: ssz.Root,
 });
@@ -191,9 +195,9 @@ export type Endpoints = {
       /** Either hex encoded public key (with 0x prefix) or validator index */
       validatorIds?: ValidatorId[];
       /** [Validator status specification](https://hackmd.io/ofFJ5gOmQpu1jjHilHbdQQ) */
-      statuses?: ValidatorStatus[];
+      statuses?: ValidatorStatusFilter[];
     },
-    {params: {state_id: string}; query: {id?: ValidatorId[]; status?: ValidatorStatus[]}},
+    {params: {state_id: string}; query: {id?: ValidatorId[]; status?: ValidatorStatusFilter[]}},
     ValidatorResponseList,
     ExecutionOptimisticAndFinalizedMeta
   >;
@@ -208,9 +212,9 @@ export type Endpoints = {
       /** Either hex encoded public key (with 0x prefix) or validator index */
       validatorIds?: ValidatorId[];
       /** [Validator status specification](https://hackmd.io/ofFJ5gOmQpu1jjHilHbdQQ) */
-      statuses?: ValidatorStatus[];
+      statuses?: ValidatorStatusFilter[];
     },
-    {params: {state_id: string}; body: {ids?: string[]; statuses?: ValidatorStatus[]}},
+    {params: {state_id: string}; body: {ids?: string[]; statuses?: ValidatorStatusFilter[]}},
     ValidatorResponseList,
     ExecutionOptimisticAndFinalizedMeta
   >;
diff --git a/packages/beacon-node/src/api/impl/beacon/state/index.ts b/packages/beacon-node/src/api/impl/beacon/state/index.ts
index c1b20ad93820..6ace9ae01e15 100644
--- a/packages/beacon-node/src/api/impl/beacon/state/index.ts
+++ b/packages/beacon-node/src/api/impl/beacon/state/index.ts
@@ -11,7 +11,7 @@ import {
   isStatePostFulu,
   isStatePostGloas,
 } from "@lodestar/state-transition";
-import {ValidatorIndex, getBuilderStatus, getValidatorStatus, ssz} from "@lodestar/types";
+import {ValidatorIndex, getBuilderStatus, getValidatorStatus, ssz, statusMatches} from "@lodestar/types";
 import {ApiError} from "../../errors.js";
 import {ApiModules} from "../../types.js";
 import {assertUniqueItems} from "../../utils.js";
@@ -100,7 +100,7 @@ export function getBeaconStateApi({
           if (resp.valid) {
             const validatorIndex = resp.validatorIndex;
             const validator = state.getValidator(validatorIndex);
-            if (statuses.length && !statuses.includes(getValidatorStatus(validator, currentEpoch))) {
+            if (statuses.length && !statusMatches(statuses, getValidatorStatus(validator, currentEpoch))) {
               continue;
             }
             const validatorResponse = toValidatorResponse(
diff --git a/packages/beacon-node/test/unit/api/impl/beacon/state/getStateValidators.test.ts b/packages/beacon-node/test/unit/api/impl/beacon/state/getStateValidators.test.ts
new file mode 100644
index 000000000000..5fef560ae348
--- /dev/null
+++ b/packages/beacon-node/test/unit/api/impl/beacon/state/getStateValidators.test.ts
@@ -0,0 +1,97 @@
+import {beforeEach, describe, expect, it, vi} from "vitest";
+import {routes} from "@lodestar/api";
+import {ExecutionStatus} from "@lodestar/fork-choice";
+import {FAR_FUTURE_EPOCH} from "@lodestar/params";
+import {BeaconStateView} from "@lodestar/state-transition";
+import {phase0} from "@lodestar/types";
+import {getBeaconStateApi} from "../../../../../../src/api/impl/beacon/state/index.js";
+import {ZERO_HASH} from "../../../../../../src/constants/index.js";
+import {ApiTestModules, getApiTestModules} from "../../../../../utils/api.js";
+import {generateCachedAltairState} from "../../../../../utils/state.js";
+import {generateProtoBlock} from "../../../../../utils/typeGenerator.js";
+
+describe("getStateValidators status filtering with ids", () => {
+  let modules: ApiTestModules;
+  let api: ReturnType<typeof getBeaconStateApi>;
+  let state: BeaconStateView;
+
+  beforeEach(() => {
+    modules = getApiTestModules();
+    api = getBeaconStateApi(modules);
+
+    // Validators are active_ongoing (activationEpoch 0, exitEpoch FAR_FUTURE)
+    state = new BeaconStateView(generateCachedAltairState());
+    modules.forkChoice.getHead.mockReturnValue(
+      generateProtoBlock({stateRoot: "0xaa", executionStatus: ExecutionStatus.Valid})
+    );
+    modules.forkChoice.getFinalizedCheckpoint.mockReturnValue({
+      root: ZERO_HASH,
+      rootHex: "0xbb",
+      epoch: 0,
+    });
+    vi.spyOn(modules.chain.regen, "getStateSync").mockReturnValue(state);
+  });
+
+  it("returns active_ongoing validator when filtering by group status active with ids", async () => {
+    const {data} = (await api.getStateValidators({
+      stateId: "head",
+      validatorIds: [0],
+      statuses: ["active"],
+    })) as {data: routes.beacon.ValidatorResponse[]};
+
+    expect(data).toHaveLength(1);
+    expect(data[0].index).toBe(0);
+    expect(data[0].status).toBe("active_ongoing");
+  });
+
+  it("returns active_ongoing validator when filtering by fine-grained status with ids", async () => {
+    const {data} = (await api.getStateValidators({
+      stateId: "head",
+      validatorIds: [0],
+      statuses: ["active_ongoing"],
+    })) as {data: routes.beacon.ValidatorResponse[]};
+
+    expect(data).toHaveLength(1);
+    expect(data[0].status).toBe("active_ongoing");
+  });
+
+  it("excludes active validator when filtering by unrelated group status with ids", async () => {
+    const {data} = (await api.getStateValidators({
+      stateId: "head",
+      validatorIds: [0],
+      statuses: ["pending"],
+    })) as {data: routes.beacon.ValidatorResponse[]};
+
+    expect(data).toHaveLength(0);
+  });
+
+  it("matches pending / exited / withdrawal group statuses with ids", async () => {
+    const originalGetValidator = state.getValidator.bind(state);
+    const overlays = new Map<number, Partial<phase0.Validator>>([
+      [0, {activationEpoch: 10, activationEligibilityEpoch: FAR_FUTURE_EPOCH}],
+      [1, {activationEpoch: 0, exitEpoch: 0, withdrawableEpoch: 10, slashed: false}],
+      [2, {activationEpoch: 0, exitEpoch: 0, withdrawableEpoch: 0, effectiveBalance: 0}],
+    ]);
+    vi.spyOn(state, "getValidator").mockImplementation((index) => {
+      const validator = originalGetValidator(index);
+      const overlay = overlays.get(index);
+      return overlay ? {...validator, ...overlay} : validator;
+    });
+
+    const cases: {id: number; group: "pending" | "exited" | "withdrawal"; expected: string}[] = [
+      {id: 0, group: "pending", expected: "pending_initialized"},
+      {id: 1, group: "exited", expected: "exited_unslashed"},
+      {id: 2, group: "withdrawal", expected: "withdrawal_done"},
+    ];
+
+    for (const {id, group, expected} of cases) {
+      const {data} = (await api.getStateValidators({
+        stateId: "head",
+        validatorIds: [id],
+        statuses: [group],
+      })) as {data: routes.beacon.ValidatorResponse[]};
+      expect(data, `ids+[${group}] should include index ${id}`).toHaveLength(1);
+      expect(data[0].status).toBe(expected);
+    }
+  });
+});
diff --git a/packages/types/src/utils/validatorStatus.ts b/packages/types/src/utils/validatorStatus.ts
index d82dc6ed438c..edf7a0c80854 100644
--- a/packages/types/src/utils/validatorStatus.ts
+++ b/packages/types/src/utils/validatorStatus.ts
@@ -91,3 +91,8 @@ export function mapToGeneralStatus(subStatus: ValidatorStatus): GeneralValidator
       throw new Error(`Unknown substatus: ${subStatus}`);
   }
 }
+
+/** Match fine-grained validator status against Beacon API filter statuses (incl. group statuses). */
+export function statusMatches(filterStatuses: readonly string[], validatorStatus: ValidatorStatus): boolean {
+  return filterStatuses.includes(validatorStatus) || filterStatuses.includes(mapToGeneralStatus(validatorStatus));
+}
diff --git a/packages/types/test/unit/validatorStatus.test.ts b/packages/types/test/unit/validatorStatus.test.ts
index 70189a29ee11..313c307553b4 100644
--- a/packages/types/test/unit/validatorStatus.test.ts
+++ b/packages/types/test/unit/validatorStatus.test.ts
@@ -1,6 +1,11 @@
 import {describe, expect, it} from "vitest";
 import {phase0} from "../../src/types.js";
-import {getValidatorStatus} from "../../src/utils/validatorStatus.js";
+import {
+  GeneralValidatorStatus,
+  ValidatorStatus,
+  getValidatorStatus,
+  statusMatches,
+} from "../../src/utils/validatorStatus.js";
 
 describe("getValidatorStatus", () => {
   it("should return PENDING_INITIALIZED", () => {
@@ -98,3 +103,37 @@ describe("getValidatorStatus", () => {
     }
   });
 });
+
+describe("statusMatches", () => {
+  const groupMembers: Record<GeneralValidatorStatus, ValidatorStatus[]> = {
+    active: ["active_ongoing", "active_exiting", "active_slashed"],
+    pending: ["pending_initialized", "pending_queued"],
+    exited: ["exited_unslashed", "exited_slashed"],
+    withdrawal: ["withdrawal_possible", "withdrawal_done"],
+  };
+
+  for (const [group, members] of Object.entries(groupMembers) as [GeneralValidatorStatus, ValidatorStatus[]][]) {
+    it(`group status "${group}" matches its fine-grained members`, () => {
+      for (const member of members) {
+        expect(statusMatches([group], member), `${group} should match ${member}`).toBe(true);
+      }
+    });
+  }
+
+  it("fine-grained statuses still match exactly", () => {
+    expect(statusMatches(["active_ongoing"], "active_ongoing")).toBe(true);
+    expect(statusMatches(["active_ongoing"], "active_exiting")).toBe(false);
+    expect(statusMatches(["active_ongoing"], "pending_queued")).toBe(false);
+  });
+
+  it("does not match unrelated group statuses", () => {
+    expect(statusMatches(["pending"], "active_ongoing")).toBe(false);
+    expect(statusMatches(["exited"], "active_ongoing")).toBe(false);
+    expect(statusMatches(["withdrawal"], "active_ongoing")).toBe(false);
+  });
+
+  it("matches when filter contains either fine-grained or group status", () => {
+    expect(statusMatches(["pending", "active"], "active_ongoing")).toBe(true);
+    expect(statusMatches(["pending", "active_ongoing"], "active_ongoing")).toBe(true);
+  });
+});

```

Context metadata for this run:
- Reviewer: review-linter
- Reviewed commit: 6d790d2845a530be1b96bac0eb5fa8a66b784b67

After finishing the review:
1) Write your full findings markdown to `/home/openclaw/.openclaw/workspace/notes/review-reports/pr-10261-review-linter.md`.
   - Include the exact metadata line `Reviewer: review-linter` near the top of the artifact.
   - Include the exact metadata line `Reviewed commit: 6d790d2845a530be1b96bac0eb5fa8a66b784b67` near the top of the artifact.
   - For each finding: severity (🔴 must-fix / 🟡 should-fix / 🟢 nit), file:line (new-file line numbers), what is wrong, a concrete failure scenario or justification, and a suggested fix.
   - If there are no findings, write a short "No findings" report anyway, still with the verdict line.
2) In your final chat response, include the exact file path you wrote and your verdict line.
