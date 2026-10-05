# Review: Devil's Advocate (Lodestar)

You are a contrarian reviewer for **Lodestar**, a TypeScript Ethereum consensus client. Your job is to challenge the *premise* and *approach* of a change — not its implementation details (other reviewers handle that).

## SCOPE

Challenge the PR on these dimensions ONLY:

1. **Necessity:** Is this change needed at all? What happens if we don't do it? Is the problem it solves real and current, or speculative?
2. **Simpler alternatives:** Is there a fundamentally simpler way to achieve the same goal? Fewer files, fewer abstractions, reusing existing code paths? Could a 5-line fix replace a 200-line refactor?
3. **Root cause vs symptom:** Does this fix the actual problem, or paper over it? Will we need another PR in 2 weeks to fix the real issue?
4. **Spec interpretation:** For consensus-critical code, does the spec actually require this? Quote the spec section. Are we implementing what we *think* the spec says vs what it *actually* says?
5. **Cross-client precedent:** Have other consensus clients (Lighthouse, Prysm, Teku, Nimbus) solved this differently? Is their approach simpler or more battle-tested?
6. **Hidden costs:** What maintenance burden does this introduce? New state to track, new error paths, new edge cases in future forks, new test surface?

## RULES

- **Every objection MUST include a concrete counter-proposal.** "This is wrong" without "here's what I'd do instead" is not useful. If you can't propose an alternative, it's not a real objection — drop it.
- **Quantify when possible.** "This adds complexity" is weak. "This adds 3 new state fields that must be maintained across fork boundaries" is strong.
- **Acknowledge when the approach is sound.** If the PR's approach is genuinely the best option, say so explicitly. Not every PR needs a contrarian take. Returning "no objections — the approach is sound" is a valid and valuable output.
- **Max 3 findings.** Force-rank. Only raise issues worth the author's time.

## EXPLICITLY OUT OF SCOPE (other reviewers handle these)

- ❌ Bug hunting, logic errors, off-by-one (→ Bug Hunter)
- ❌ Code style, naming, formatting (→ Style Enforcer)
- ❌ Security vulnerabilities, DoS vectors (→ Security Engineer)
- ❌ Clean code, readability, maintainability (→ Wise Senior)
- ❌ Package boundaries, layering violations (→ Architect)
- ❌ Malicious code, supply chain threats (→ Defender)

## LODESTAR-SPECIFIC ANGLES

- **Fork-forward thinking:** Will this approach survive the next 2-3 forks? Lodestar's fork progression (phase0 → altair → bellatrix → capella → deneb → electra → fulu → gloas → heze) means every new abstraction must be maintained across fork boundaries. Prefer approaches that don't add per-fork branching.
- **Spec churn risk:** The consensus spec is a moving target. Does this PR couple tightly to a spec detail that's under active discussion? If so, a more abstract approach might save rework.
- **"Just use what Lighthouse does":** Rust clients often have patterns that don't translate well to TypeScript/Node.js. Don't blindly suggest cross-client patterns without considering runtime differences (GC pressure, async model, memory model).
- **EIP maturity:** For EIP implementations, check the EIP's status. Implementing a Draft EIP as if it were Final adds premature complexity.

## OUTPUT FORMAT

```
## Devil's Advocate Review

### Overall Assessment
[One sentence: is the approach fundamentally sound, or is there a better path?]

### Objections (if any, max 3)

#### 1. [Title]
**Challenge:** [What's wrong with the premise/approach]
**Evidence:** [Spec quote, cross-client reference, or concrete reasoning]
**Counter-proposal:** [What to do instead, with enough detail to be actionable]
**Impact if ignored:** [What goes wrong if the author proceeds as-is]

### Verdict
[SOUND — no fundamental issues | RECONSIDER — viable alternatives exist | RETHINK — approach has structural problems]
```


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

---

## PR Context
PR #10263 "fix: optimize builder flows" by twoeths (core maintainer). Head commit: 2e9ac55d6dde395fceed1d4778f7939458471923. CI fully green (unit, spec tests, check-specrefs, lint, types).
Motivation: Gloas builder deposit/exit requests (EIP-8282) previously did a full linear scan of `state.builders` per request (`findBuilderIndexByPubkey`) and another scan per new builder (`addBuilderToRegistry` -> get_index_for_new_builder). A private bounty report showed a FULL parent with 64 builder deposits + 16 builder exits against a ~140k-entry registry takes >12s. This PR builds a transient per-block `IndexedBuilderState` (pubkey->index map + ascending list of reusable-index candidates) once per block when there are builder requests, and uses it for lookups and insertion. It is intentionally block-scoped (registry is mutated per block and indices can be reused, so a global cache is not trivially safe).

Spec (consensus-specs v1.7.0-beta.2, pinned by Lodestar specrefs) - relevant functions:
- process_builder_deposit_request: ignore non-builder withdrawal credential; if pubkey not in builders -> if valid signature: add_builder_to_registry(state, pubkey, PAYLOAD_BUILDER_VERSION, wc[12:], amount, state.slot); else top-up: if builder.withdrawable_epoch != FAR_FUTURE_EPOCH and builder.balance == 0: builder.withdrawable_epoch = current_epoch + MIN_BUILDER_WITHDRAWABILITY_DELAY; builder.balance += amount.
- add_builder_to_registry: set_or_append_list(state.builders, get_index_for_new_builder(state), Builder(pubkey, version, execution_address, balance=amount, deposit_epoch=compute_epoch_at_slot(slot), withdrawable_epoch=FAR_FUTURE_EPOCH))
- get_index_for_new_builder: first index with withdrawable_epoch <= current_epoch and balance == 0, else len(builders).
- process_builder_exit_request: lookup pubkey (return if absent); return if not is_active_builder, if execution_address != source_address, or if pending balance to withdraw != 0; else initiate_builder_exit.
- apply_parent_execution_payload order: deposits, withdrawals, consolidations, builder_deposits, builder_exits, then settle builder payment.

Full source of the PR head is checked out (read-only, do NOT modify) at ~/lodestar-pr10263 - read surrounding code there as needed (e.g. packages/state-transition/src/util/gloas.ts, packages/state-transition/src/slot/upgradeStateToGloas.ts, packages/state-transition/src/block/processParentExecutionPayload.ts). Verified fact: @chainsafe/ssz 1.8.0 ArrayCompositeTreeViewDU.getReadonly(index) returns the pending mutable view from viewsChanged if one exists, so mutations via builders.get(i) are visible to later builders.getReadonly(i) before commit; getAllReadonlyValues() requires a prior commit().
Consensus-specs reference repo: ~/consensus-specs (read via `git -C ~/consensus-specs show origin/master:specs/gloas/beacon-chain.md`; the working tree may be on another branch).

---

## Files Changed in This PR
packages/beacon-node/test/spec/presets/operations.test.ts
packages/state-transition/src/block/indexedBuilderState.ts
packages/state-transition/src/block/processBuilderDepositRequest.ts
packages/state-transition/src/block/processBuilderExitRequest.ts
packages/state-transition/src/block/processParentExecutionPayload.ts
packages/state-transition/src/index.ts
packages/state-transition/src/util/gloas.ts
packages/state-transition/test/unit/block/processBuilderDepositRequest.test.ts
packages/state-transition/test/unit/block/processBuilderExitRequest.test.ts
packages/state-transition/test/unit/util/gloas.test.ts
specrefs/functions.yml

IMPORTANT: Only flag issues in the files listed above. Do NOT comment on files not in this list, even if they appear in the broader codebase context.

---

Review this diff for ChainSafe/lodestar PR #10263 (fix: optimize builder flows):

```diff
diff --git a/packages/beacon-node/test/spec/presets/operations.test.ts b/packages/beacon-node/test/spec/presets/operations.test.ts
index d2d08181da84..b19c24861d5a 100644
--- a/packages/beacon-node/test/spec/presets/operations.test.ts
+++ b/packages/beacon-node/test/spec/presets/operations.test.ts
@@ -11,6 +11,7 @@ import {
   CachedBeaconStateElectra,
   CachedBeaconStateGloas,
   ExecutionPayloadStatus,
+  IndexedBuilderState,
   getBlockRootAtSlot,
 } from "@lodestar/state-transition";
 import * as blockFns from "@lodestar/state-transition/block";
@@ -131,11 +132,17 @@ const operationFns: Record<string, BlockProcessFn<CachedBeaconStateAllForks>> =
   },
 
   builder_deposit_request: (state, testCase: {builder_deposit_request: gloas.BuilderDepositRequest}) => {
-    blockFns.processBuilderDepositRequest(state as CachedBeaconStateGloas, testCase.builder_deposit_request);
+    blockFns.processBuilderDepositRequest(
+      new IndexedBuilderState(state as CachedBeaconStateGloas),
+      testCase.builder_deposit_request
+    );
   },
 
   builder_exit_request: (state, testCase: {builder_exit_request: gloas.BuilderExitRequest}) => {
-    blockFns.processBuilderExitRequest(state as CachedBeaconStateGloas, testCase.builder_exit_request);
+    blockFns.processBuilderExitRequest(
+      new IndexedBuilderState(state as CachedBeaconStateGloas),
+      testCase.builder_exit_request
+    );
   },
 };
 
diff --git a/packages/state-transition/src/block/indexedBuilderState.ts b/packages/state-transition/src/block/indexedBuilderState.ts
new file mode 100644
index 000000000000..0073c9fd35b9
--- /dev/null
+++ b/packages/state-transition/src/block/indexedBuilderState.ts
@@ -0,0 +1,76 @@
+import {FAR_FUTURE_EPOCH} from "@lodestar/params";
+import {BuilderIndex, Epoch, PubkeyHex} from "@lodestar/types";
+import {Builder} from "@lodestar/types/gloas";
+import {toPubkeyHex} from "@lodestar/utils";
+import {CachedBeaconStateGloas} from "../types.js";
+import {computeEpochAtSlot} from "../util/epoch.js";
+import {createBuilderView} from "../util/gloas.js";
+
+/**
+ * This is to make sure we loop through builders once per block processing.
+ * Note that we cannot use this across blocks/slots.
+ */
+export class IndexedBuilderState {
+  private readonly currentEpoch: Epoch;
+  private readonly indexByPubkey = new Map<PubkeyHex, BuilderIndex>();
+  private readonly reusableIndiceCandidates: BuilderIndex[] = [];
+  private nextCandidateIndex = 0;
+
+  constructor(readonly state: CachedBeaconStateGloas) {
+    state.builders.commit();
+    const builders = state.builders.getAllReadonlyValues();
+    this.currentEpoch = computeEpochAtSlot(state.slot);
+    for (const [index, builder] of builders.entries()) {
+      const pubkeyHex = toPubkeyHex(builder.pubkey);
+      this.indexByPubkey.set(pubkeyHex, index);
+      if (canReuseBuilder(builder, this.currentEpoch)) {
+        this.reusableIndiceCandidates.push(index);
+      }
+    }
+  }
+
+  findBuilderIndexByPubkey(pubkey: Uint8Array): BuilderIndex | null {
+    return this.indexByPubkey.get(toPubkeyHex(pubkey)) ?? null;
+  }
+
+  topUp(index: BuilderIndex, amount: number): void {
+    const builder = this.state.builders.get(index);
+    // If the builder has exited and been fully swept (balance drained to 0), reset the
+    // withdrawable epoch so this top-up becomes withdrawable again. Must run before the
+    // balance increase, since the reset is gated on the current balance being 0.
+    if (builder.withdrawableEpoch !== FAR_FUTURE_EPOCH && builder.balance === 0) {
+      builder.withdrawableEpoch = this.currentEpoch + this.state.config.MIN_BUILDER_WITHDRAWABILITY_DELAY;
+    }
+    builder.balance += amount;
+  }
+
+  addBuilderToRegistry(pubkey: Uint8Array, version: number, executionAddress: Uint8Array, amount: number): void {
+    const builder = createBuilderView(pubkey, version, executionAddress, amount, this.currentEpoch);
+    const reusableIndex = this.findReusableBuilderIndex();
+    const index = reusableIndex ?? this.state.builders.length;
+    if (reusableIndex !== null) {
+      const oldBuilder = this.state.builders.getReadonly(index);
+      this.indexByPubkey.delete(toPubkeyHex(oldBuilder.pubkey));
+      this.state.builders.set(index, builder);
+    } else {
+      this.state.builders.push(builder);
+    }
+    this.indexByPubkey.set(toPubkeyHex(pubkey), index);
+  }
+
+  private findReusableBuilderIndex(): BuilderIndex | null {
+    while (this.nextCandidateIndex < this.reusableIndiceCandidates.length) {
+      const index = this.reusableIndiceCandidates[this.nextCandidateIndex++];
+      const builder = this.state.builders.getReadonly(index);
+      // Top-ups can invalidate initial candidates
+      if (canReuseBuilder(builder, this.currentEpoch)) {
+        return index;
+      }
+    }
+    return null;
+  }
+}
+
+function canReuseBuilder(builder: Builder, currentEpoch: Epoch): boolean {
+  return builder.withdrawableEpoch <= currentEpoch && builder.balance === 0;
+}
diff --git a/packages/state-transition/src/block/processBuilderDepositRequest.ts b/packages/state-transition/src/block/processBuilderDepositRequest.ts
index 8896a71af94d..cc51356bfd73 100644
--- a/packages/state-transition/src/block/processBuilderDepositRequest.ts
+++ b/packages/state-transition/src/block/processBuilderDepositRequest.ts
@@ -1,13 +1,7 @@
-import {FAR_FUTURE_EPOCH, PAYLOAD_BUILDER_VERSION} from "@lodestar/params";
+import {PAYLOAD_BUILDER_VERSION} from "@lodestar/params";
 import {gloas} from "@lodestar/types";
-import {CachedBeaconStateGloas} from "../types.js";
-import {computeEpochAtSlot} from "../util/epoch.js";
-import {
-  addBuilderToRegistry,
-  findBuilderIndexByPubkey,
-  isBuilderWithdrawalCredential,
-  isValidBuilderDepositSignature,
-} from "../util/gloas.js";
+import {isBuilderWithdrawalCredential, isValidBuilderDepositSignature} from "../util/gloas.js";
+import {IndexedBuilderState} from "./indexedBuilderState.js";
 
 /**
  * Process a builder deposit request from the execution layer: register a new builder
@@ -16,9 +10,10 @@ import {
  * Spec: https://github.com/ethereum/consensus-specs/blob/v1.7.0-alpha.11/specs/gloas/beacon-chain.md#new-process_builder_deposit_request
  */
 export function processBuilderDepositRequest(
-  state: CachedBeaconStateGloas,
+  indexedState: IndexedBuilderState,
   request: gloas.BuilderDepositRequest
 ): void {
+  const {state} = indexedState;
   const {pubkey, withdrawalCredentials, amount, signature} = request;
 
   // Ignore deposits with unexpected withdrawal credential prefixes.
@@ -26,31 +21,14 @@ export function processBuilderDepositRequest(
     return;
   }
 
-  const builderIndex = findBuilderIndexByPubkey(state, pubkey);
+  const builderIndex = indexedState.findBuilderIndexByPubkey(pubkey);
 
   if (builderIndex === null) {
     if (isValidBuilderDepositSignature(state.config, pubkey, withdrawalCredentials, amount, signature)) {
-      addBuilderToRegistry(
-        state,
-        pubkey,
-        PAYLOAD_BUILDER_VERSION,
-        withdrawalCredentials.subarray(12),
-        amount,
-        state.slot
-      );
+      indexedState.addBuilderToRegistry(pubkey, PAYLOAD_BUILDER_VERSION, withdrawalCredentials.subarray(12), amount);
     }
     return;
   }
 
-  const builder = state.builders.get(builderIndex);
-
-  // If the builder has exited and been fully swept (balance drained to 0), reset the
-  // withdrawable epoch so this top-up becomes withdrawable again. Must run before the
-  // balance increase, since the reset is gated on the current balance being 0.
-  if (builder.withdrawableEpoch !== FAR_FUTURE_EPOCH && builder.balance === 0) {
-    builder.withdrawableEpoch = computeEpochAtSlot(state.slot) + state.config.MIN_BUILDER_WITHDRAWABILITY_DELAY;
-  }
-
-  // Increase balance by deposit amount
-  builder.balance += amount;
+  indexedState.topUp(builderIndex, amount);
 }
diff --git a/packages/state-transition/src/block/processBuilderExitRequest.ts b/packages/state-transition/src/block/processBuilderExitRequest.ts
index 69ee39c9e668..d9bfe50f72b0 100644
--- a/packages/state-transition/src/block/processBuilderExitRequest.ts
+++ b/packages/state-transition/src/block/processBuilderExitRequest.ts
@@ -1,12 +1,7 @@
 import {gloas} from "@lodestar/types";
 import {byteArrayEquals} from "@lodestar/utils";
-import {CachedBeaconStateGloas} from "../types.js";
-import {
-  findBuilderIndexByPubkey,
-  getPendingBalanceToWithdrawForBuilder,
-  initiateBuilderExit,
-  isActiveBuilder,
-} from "../util/gloas.js";
+import {getPendingBalanceToWithdrawForBuilder, initiateBuilderExit, isActiveBuilder} from "../util/gloas.js";
+import {IndexedBuilderState} from "./indexedBuilderState.js";
 
 /**
  * Apply a builder exit request. Authorizes the exit via `source_address` (the builder's
@@ -17,8 +12,9 @@ import {
  *
  * Spec: https://github.com/ethereum/consensus-specs/blob/v1.7.0-alpha.11/specs/gloas/beacon-chain.md#new-process_builder_exit_request
  */
-export function processBuilderExitRequest(state: CachedBeaconStateGloas, request: gloas.BuilderExitRequest): void {
-  const builderIndex = findBuilderIndexByPubkey(state, request.pubkey);
+export function processBuilderExitRequest(indexedState: IndexedBuilderState, request: gloas.BuilderExitRequest): void {
+  const {state} = indexedState;
+  const builderIndex = indexedState.findBuilderIndexByPubkey(request.pubkey);
   if (builderIndex === null) {
     return;
   }
diff --git a/packages/state-transition/src/block/processParentExecutionPayload.ts b/packages/state-transition/src/block/processParentExecutionPayload.ts
index 426696f01327..0e00e018b021 100644
--- a/packages/state-transition/src/block/processParentExecutionPayload.ts
+++ b/packages/state-transition/src/block/processParentExecutionPayload.ts
@@ -3,6 +3,7 @@ import {BeaconBlock, gloas, ssz} from "@lodestar/types";
 import {byteArrayEquals, toRootHex} from "@lodestar/utils";
 import {CachedBeaconStateGloas} from "../types.js";
 import {computeEpochAtSlot} from "../util/epoch.js";
+import {IndexedBuilderState} from "./indexedBuilderState.js";
 import {processBuilderDepositRequest} from "./processBuilderDepositRequest.js";
 import {processBuilderExitRequest} from "./processBuilderExitRequest.js";
 import {processConsolidationRequest} from "./processConsolidationRequest.js";
@@ -67,12 +68,14 @@ export function applyParentExecutionPayload(state: CachedBeaconStateGloas, reque
     processConsolidationRequest(state, consolidation);
   }
 
-  for (const builderDeposit of requests.builderDeposits) {
-    processBuilderDepositRequest(state, builderDeposit);
-  }
-
-  for (const builderExit of requests.builderExits) {
-    processBuilderExitRequest(state, builderExit);
+  if (requests.builderDeposits.length > 0 || requests.builderExits.length > 0) {
+    const indexedState = new IndexedBuilderState(state);
+    for (const builderDeposit of requests.builderDeposits) {
+      processBuilderDepositRequest(indexedState, builderDeposit);
+    }
+    for (const builderExit of requests.builderExits) {
+      processBuilderExitRequest(indexedState, builderExit);
+    }
   }
 
   // Settle the builder payment
diff --git a/packages/state-transition/src/index.ts b/packages/state-transition/src/index.ts
index 5d66d258a8ce..6664905da978 100644
--- a/packages/state-transition/src/index.ts
+++ b/packages/state-transition/src/index.ts
@@ -1,4 +1,5 @@
 export {type BlockExternalData, DataAvailabilityStatus, ExecutionPayloadStatus} from "./block/externalData.js";
+export {IndexedBuilderState} from "./block/indexedBuilderState.js";
 export {getAttestationParticipationStatus, processAttestationsAltair} from "./block/processAttestationsAltair.js";
 export {assertValidAttesterSlashing} from "./block/processAttesterSlashing.js";
 export {isValidBlsToExecutionChange} from "./block/processBlsToExecutionChange.js";
diff --git a/packages/state-transition/src/util/gloas.ts b/packages/state-transition/src/util/gloas.ts
index 43a50c7dedfc..f2788c9ad02c 100644
--- a/packages/state-transition/src/util/gloas.ts
+++ b/packages/state-transition/src/util/gloas.ts
@@ -178,21 +178,6 @@ export function initiateBuilderExit(state: CachedBeaconStateGloas, builderIndex:
   builder.withdrawableEpoch = currentEpoch + state.config.MIN_BUILDER_WITHDRAWABILITY_DELAY;
 }
 
-/**
- * Find the index of a builder by their public key.
- * Returns null if not found.
- *
- * May consider builder pubkey cache if performance becomes an issue.
- */
-export function findBuilderIndexByPubkey(state: CachedBeaconStateGloas, pubkey: Uint8Array): BuilderIndex | null {
-  for (let i = 0; i < state.builders.length; i++) {
-    if (byteArrayEquals(state.builders.getReadonly(i).pubkey, pubkey)) {
-      return i;
-    }
-  }
-  return null;
-}
-
 /**
  * Use cached block roots to avoid repeated state root lookups while matching the spec's is_attestation_same_slot behavior.
  */
@@ -248,41 +233,6 @@ export function getPtcWindowEpochCacheData(state: CachedBeaconStateGloas): {
   };
 }
 
-/**
- * Add a new builder to the builders registry. Reuses slots from exited and fully withdrawn
- * builders when available, otherwise appends.
- *
- * Spec: https://github.com/ethereum/consensus-specs/blob/v1.7.0-alpha.11/specs/gloas/beacon-chain.md#new-add_builder_to_registry
- */
-export function addBuilderToRegistry(
-  state: CachedBeaconStateGloas,
-  pubkey: Uint8Array,
-  version: number,
-  executionAddress: Uint8Array,
-  amount: number,
-  slot: number
-): void {
-  const currentEpoch = computeEpochAtSlot(state.slot);
-  const depositEpoch = computeEpochAtSlot(slot);
-
-  let builderIndex = state.builders.length;
-  for (let i = 0; i < state.builders.length; i++) {
-    const builder = state.builders.getReadonly(i);
-    if (builder.withdrawableEpoch <= currentEpoch && builder.balance === 0) {
-      builderIndex = i;
-      break;
-    }
-  }
-
-  const newBuilder = createBuilderView(pubkey, version, executionAddress, amount, depositEpoch);
-
-  if (builderIndex < state.builders.length) {
-    state.builders.set(builderIndex, newBuilder);
-  } else {
-    state.builders.push(newBuilder);
-  }
-}
-
 /**
  * Append a new builder to the registry without scanning for a reusable slot.
  *
@@ -301,10 +251,9 @@ export function appendBuilderToRegistry(
 }
 
 /**
- * Build a Builder view for registry insertion. Shared by the scan-based {@link addBuilderToRegistry}
- * and the append-only {@link appendBuilderToRegistry} so both paths produce an identical view.
+ * Build a Builder view from builder fields.
  */
-function createBuilderView(
+export function createBuilderView(
   pubkey: Uint8Array,
   version: number,
   executionAddress: Uint8Array,
diff --git a/packages/state-transition/test/unit/block/processBuilderDepositRequest.test.ts b/packages/state-transition/test/unit/block/processBuilderDepositRequest.test.ts
index 551019b5c600..c2a51b10c3de 100644
--- a/packages/state-transition/test/unit/block/processBuilderDepositRequest.test.ts
+++ b/packages/state-transition/test/unit/block/processBuilderDepositRequest.test.ts
@@ -10,6 +10,7 @@ import {
   SLOTS_PER_EPOCH,
 } from "@lodestar/params";
 import {ssz} from "@lodestar/types";
+import {IndexedBuilderState} from "../../../src/block/indexedBuilderState.js";
 
 const isValidBuilderDepositSignatureMock = vi.hoisted(() =>
   // Treat the first byte of the BLS signature as the verification flag so each test can opt in
@@ -102,7 +103,7 @@ describe("processBuilderDepositRequest", () => {
 
     expect(state.builders.length).toBe(0);
 
-    processBuilderDepositRequest(state, request);
+    processBuilderDepositRequest(new IndexedBuilderState(state), request);
 
     expect(isValidBuilderDepositSignatureMock).toHaveBeenCalledTimes(1);
     expect(state.builders.length).toBe(1);
@@ -117,7 +118,7 @@ describe("processBuilderDepositRequest", () => {
     const state = buildGloasState(1);
     const request = makeBuilderDepositRequest({prefix: 0x01});
 
-    processBuilderDepositRequest(state, request);
+    processBuilderDepositRequest(new IndexedBuilderState(state), request);
 
     expect(isValidBuilderDepositSignatureMock).not.toHaveBeenCalled();
     expect(state.builders.length).toBe(0);
@@ -127,7 +128,7 @@ describe("processBuilderDepositRequest", () => {
     const state = buildGloasState(1);
     const request = makeBuilderDepositRequest({signatureFirstByte: 0});
 
-    processBuilderDepositRequest(state, request);
+    processBuilderDepositRequest(new IndexedBuilderState(state), request);
 
     expect(isValidBuilderDepositSignatureMock).toHaveBeenCalledTimes(1);
     expect(state.builders.length).toBe(0);
@@ -159,7 +160,7 @@ describe("processBuilderDepositRequest", () => {
       signatureFirstByte: 0, // would be rejected as invalid PoP, but mustn't be checked
     });
 
-    processBuilderDepositRequest(state, request);
+    processBuilderDepositRequest(new IndexedBuilderState(state), request);
 
     expect(isValidBuilderDepositSignatureMock).not.toHaveBeenCalled();
     expect(state.builders.length).toBe(1);
@@ -191,7 +192,7 @@ describe("processBuilderDepositRequest", () => {
       prefix: 0x01,
     });
 
-    processBuilderDepositRequest(state, request);
+    processBuilderDepositRequest(new IndexedBuilderState(state), request);
 
     expect(isValidBuilderDepositSignatureMock).not.toHaveBeenCalled();
     expect(state.builders.length).toBe(1);
@@ -221,7 +222,7 @@ describe("processBuilderDepositRequest", () => {
 
     const request = makeBuilderDepositRequest({pubkey, executionAddress, amount: 1_000_000_000});
 
-    processBuilderDepositRequest(state, request);
+    processBuilderDepositRequest(new IndexedBuilderState(state), request);
 
     const builder = state.builders.get(0);
     expect(builder.balance).toBe(1_000_000_000);
@@ -250,10 +251,65 @@ describe("processBuilderDepositRequest", () => {
 
     const request = makeBuilderDepositRequest({pubkey, executionAddress, amount: 1_000_000_000});
 
-    processBuilderDepositRequest(state, request);
+    processBuilderDepositRequest(new IndexedBuilderState(state), request);
 
     const builder = state.builders.get(0);
     expect(builder.balance).toBe(2_000_000_000);
     expect(builder.withdrawableEpoch).toBe(1);
   });
 });
+
+describe("indexed builder deposit sequences", () => {
+  function reusableBuilder(pubkey: Uint8Array) {
+    return ssz.gloas.Builder.toViewDU({
+      pubkey,
+      version: PAYLOAD_BUILDER_VERSION,
+      executionAddress: new Uint8Array(20),
+      balance: 0,
+      depositEpoch: 0,
+      withdrawableEpoch: 0,
+    });
+  }
+
+  it.each([0, 1_000_000_000])("skips a candidate after a top-up of %i", (amount) => {
+    const state = buildGloasState(SLOTS_PER_EPOCH * 2);
+    const oldPubkey = new Uint8Array(48).fill(1);
+    const newPubkey = new Uint8Array(48).fill(2);
+    state.builders.push(reusableBuilder(oldPubkey));
+    state.builders.push(reusableBuilder(new Uint8Array(48).fill(3)));
+    const indexed = new IndexedBuilderState(state);
+
+    processBuilderDepositRequest(indexed, makeBuilderDepositRequest({pubkey: oldPubkey, amount}));
+    processBuilderDepositRequest(indexed, makeBuilderDepositRequest({pubkey: newPubkey}));
+    processBuilderDepositRequest(
+      indexed,
+      makeBuilderDepositRequest({pubkey: newPubkey, amount: 7, signatureFirstByte: 0})
+    );
+
+    expect(state.builders.length).toBe(2);
+    expect(indexed.findBuilderIndexByPubkey(oldPubkey)).toBe(0);
+    expect(indexed.findBuilderIndexByPubkey(newPubkey)).toBe(1);
+    expect(indexed.findBuilderIndexByPubkey(new Uint8Array(48).fill(3))).toBeNull();
+    expect(state.builders.getReadonly(0).balance).toBe(amount);
+    expect(state.builders.getReadonly(1).balance).toBe(makeBuilderDepositRequest().amount + 7);
+  });
+
+  it("does not consume candidates for invalid deposits and re-registers replaced pubkeys", () => {
+    const state = buildGloasState(SLOTS_PER_EPOCH * 2);
+    const oldPubkey = new Uint8Array(48).fill(1);
+    const newPubkey = new Uint8Array(48).fill(2);
+    state.builders.push(reusableBuilder(oldPubkey));
+    const indexed = new IndexedBuilderState(state);
+
+    processBuilderDepositRequest(indexed, makeBuilderDepositRequest({pubkey: newPubkey, signatureFirstByte: 0}));
+    expect(indexed.findBuilderIndexByPubkey(oldPubkey)).toBe(0);
+    processBuilderDepositRequest(indexed, makeBuilderDepositRequest({pubkey: newPubkey, amount: 0}));
+    expect(indexed.findBuilderIndexByPubkey(oldPubkey)).toBeNull();
+    processBuilderDepositRequest(indexed, makeBuilderDepositRequest({pubkey: oldPubkey, signatureFirstByte: 0}));
+    expect(state.builders.length).toBe(1);
+    processBuilderDepositRequest(indexed, makeBuilderDepositRequest({pubkey: oldPubkey}));
+    expect(indexed.findBuilderIndexByPubkey(oldPubkey)).toBe(1);
+    expect(state.builders.length).toBe(2);
+    expect(state.builders.getReadonly(0).withdrawableEpoch).toBe(FAR_FUTURE_EPOCH);
+  });
+});
diff --git a/packages/state-transition/test/unit/block/processBuilderExitRequest.test.ts b/packages/state-transition/test/unit/block/processBuilderExitRequest.test.ts
index f0aeb10a5530..14a0e50de145 100644
--- a/packages/state-transition/test/unit/block/processBuilderExitRequest.test.ts
+++ b/packages/state-transition/test/unit/block/processBuilderExitRequest.test.ts
@@ -4,6 +4,7 @@ import {createBeaconConfig} from "@lodestar/config";
 import {getConfig} from "@lodestar/config/test-utils";
 import {FAR_FUTURE_EPOCH, ForkName, PAYLOAD_BUILDER_VERSION, SLOTS_PER_EPOCH} from "@lodestar/params";
 import {ssz} from "@lodestar/types";
+import {IndexedBuilderState} from "../../../src/block/indexedBuilderState.js";
 import {processBuilderExitRequest} from "../../../src/block/processBuilderExitRequest.js";
 import {createCachedBeaconState} from "../../../src/index.js";
 
@@ -77,7 +78,7 @@ describe("processBuilderExitRequest", () => {
   it("drops request for unknown builder pubkey", () => {
     const {state} = buildGloasState();
 
-    processBuilderExitRequest(state, exitRequest());
+    processBuilderExitRequest(new IndexedBuilderState(state), exitRequest());
 
     expect(state.builders.length).toBe(0);
   });
@@ -88,7 +89,7 @@ describe("processBuilderExitRequest", () => {
     const {state} = buildGloasState({finalizedEpoch: 0});
     pushBuilder(state, {depositEpoch: 0});
 
-    processBuilderExitRequest(state, exitRequest());
+    processBuilderExitRequest(new IndexedBuilderState(state), exitRequest());
 
     expect(state.builders.get(0).withdrawableEpoch).toBe(FAR_FUTURE_EPOCH);
   });
@@ -97,7 +98,7 @@ describe("processBuilderExitRequest", () => {
     const {state} = buildGloasState({finalizedEpoch: 5});
     pushBuilder(state, {depositEpoch: 0});
 
-    processBuilderExitRequest(state, exitRequest({sourceAddress: OTHER_EXEC_ADDRESS}));
+    processBuilderExitRequest(new IndexedBuilderState(state), exitRequest({sourceAddress: OTHER_EXEC_ADDRESS}));
 
     expect(state.builders.get(0).withdrawableEpoch).toBe(FAR_FUTURE_EPOCH);
   });
@@ -114,7 +115,7 @@ describe("processBuilderExitRequest", () => {
       })
     );
 
-    processBuilderExitRequest(state, exitRequest());
+    processBuilderExitRequest(new IndexedBuilderState(state), exitRequest());
 
     expect(state.builders.get(0).withdrawableEpoch).toBe(FAR_FUTURE_EPOCH);
   });
@@ -125,7 +126,7 @@ describe("processBuilderExitRequest", () => {
     const {state, config} = buildGloasState({slot: SLOTS_PER_EPOCH * currentEpoch, finalizedEpoch: 5});
     pushBuilder(state, {depositEpoch: 0});
 
-    processBuilderExitRequest(state, exitRequest());
+    processBuilderExitRequest(new IndexedBuilderState(state), exitRequest());
 
     expect(state.builders.get(0).withdrawableEpoch).toBe(currentEpoch + config.MIN_BUILDER_WITHDRAWABILITY_DELAY);
   });
diff --git a/packages/state-transition/test/unit/util/gloas.test.ts b/packages/state-transition/test/unit/util/gloas.test.ts
index 3927291ac5a5..4c084b107320 100644
--- a/packages/state-transition/test/unit/util/gloas.test.ts
+++ b/packages/state-transition/test/unit/util/gloas.test.ts
@@ -4,14 +4,10 @@ import {createBeaconConfig} from "@lodestar/config";
 import {getConfig} from "@lodestar/config/test-utils";
 import {FAR_FUTURE_EPOCH, ForkName, MIN_DEPOSIT_AMOUNT, PAYLOAD_BUILDER_VERSION} from "@lodestar/params";
 import {ssz} from "@lodestar/types";
+import {IndexedBuilderState} from "../../../src/block/indexedBuilderState.js";
 import {createCachedBeaconState} from "../../../src/index.js";
 import {CachedBeaconStateGloas} from "../../../src/types.js";
-import {
-  addBuilderToRegistry,
-  appendBuilderToRegistry,
-  getExpectedGasLimit,
-  isGasLimitTargetCompatible,
-} from "../../../src/util/gloas.js";
+import {appendBuilderToRegistry, getExpectedGasLimit, isGasLimitTargetCompatible} from "../../../src/util/gloas.js";
 
 function buildGloasState(slot = 0): CachedBeaconStateGloas {
   const config = getConfig(ForkName.gloas);
@@ -107,25 +103,23 @@ describe("util / gloas", () => {
   });
 
   describe("appendBuilderToRegistry", () => {
-    // At the fork transition the builders registry is append-only (no reusable slot exists), so the
-    // scan-free appendBuilderToRegistry must produce a byte-identical registry to the scan-based
-    // addBuilderToRegistry. addBuilderToRegistry is the oracle here.
     it("matches addBuilderToRegistry for append-only onboarding", () => {
       const slot = 0; // any slot; both paths compute depositEpoch identically
-      const scanState = buildGloasState(slot);
+      const indexedState = buildGloasState(slot);
       const appendState = buildGloasState(slot);
 
+      const indexed = new IndexedBuilderState(indexedState);
       const n = 256;
       for (let i = 0; i < n; i++) {
         const pubkey = new Uint8Array(48).fill(i & 0xff);
         const execAddr = new Uint8Array(20).fill(i & 0xff);
         const amount = MIN_DEPOSIT_AMOUNT + i; // balance > 0, as for a fresh builder at the fork
 
-        addBuilderToRegistry(scanState, pubkey, PAYLOAD_BUILDER_VERSION, execAddr, amount, slot);
+        indexed.addBuilderToRegistry(pubkey, PAYLOAD_BUILDER_VERSION, execAddr, amount);
         appendBuilderToRegistry(appendState, pubkey, PAYLOAD_BUILDER_VERSION, execAddr, amount, slot);
 
         // byte-for-byte registry equivalence after every onboard
-        expect(appendState.builders.hashTreeRoot()).toEqual(scanState.builders.hashTreeRoot());
+        expect(appendState.builders.hashTreeRoot()).toEqual(indexedState.builders.hashTreeRoot());
       }
 
       expect(appendState.builders.length).toBe(n);
diff --git a/specrefs/functions.yml b/specrefs/functions.yml
index e0f3797da3a5..2565974e5668 100644
--- a/specrefs/functions.yml
+++ b/specrefs/functions.yml
@@ -1,7 +1,7 @@
 - name: add_builder_to_registry#gloas
   sources:
-    - file: packages/state-transition/src/util/gloas.ts
-      search: export function addBuilderToRegistry(
+    - file: packages/state-transition/src/block/indexedBuilderState.ts
+      search: "addBuilderToRegistry(pubkey: Uint8Array,"
   spec: |
     <spec fn="add_builder_to_registry" fork="gloas" hash="16d64e88">
     def add_builder_to_registry(
@@ -4808,8 +4808,8 @@
 
 - name: get_index_for_new_builder#gloas
   sources:
-    - file: packages/state-transition/src/util/gloas.ts
-      search: if (builder.withdrawableEpoch <= currentEpoch && builder.balance === 0) {
+    - file: packages/state-transition/src/block/indexedBuilderState.ts
+      search: "private findReusableBuilderIndex(): BuilderIndex | null {"
   spec: |
     <spec fn="get_index_for_new_builder" fork="gloas" hash="82dfbdb5">
     def get_index_for_new_builder(state: BeaconState) -> BuilderIndex:
@@ -12558,8 +12558,8 @@
   sources:
     - file: packages/state-transition/src/block/processDeposit.ts
       search: stateAltair.inactivityScores.push(
-    - file: packages/state-transition/src/util/gloas.ts
-      search: if (builderIndex < state.builders.length) {
+    - file: packages/state-transition/src/block/indexedBuilderState.ts
+      search: if (reusableIndex !== null) {
   spec: |
     <spec fn="set_or_append_list" fork="altair" hash="45764cd4">
     def set_or_append_list(

```

---

Context metadata for this run:
- Reviewer: review-devils-advocate
- Reviewed commit: 2e9ac55d6dde395fceed1d4778f7939458471923

For every finding give: severity (🔴 must-fix / 🟡 should-fix / 🟢 suggestion), file path, the exact code line text it anchors to, a concrete explanation (for bugs: concrete input/state -> wrong result), and a suggested fix. Do not report things you could not verify against the code. If you find nothing material, say so.

After finishing the review:
1) Write your full findings markdown to `~/.openclaw/workspace/notes/review-reports/pr-10263-review-devils-advocate.md` using:
   `bash ~/.openclaw/workspace/scripts/review/write-review-artifact.sh --pr 10263 --agent review-devils-advocate --head-repo /home/openclaw/lodestar-pr10263 <<'EOF'
<findings markdown>
EOF`
   - Include the exact metadata line `Reviewer: review-devils-advocate` near the top of the artifact.
   - Include the exact metadata line `Reviewed commit: 2e9ac55d6dde395fceed1d4778f7939458471923` near the top of the artifact.
   - If there are no findings, write a short "No findings" report anyway.
2) In your final chat response, include the exact file path you wrote.
