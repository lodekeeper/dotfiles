# PR #8837 — Wisdom Review (Readability / Simplicity / Maintainability)

**Reviewer:** review-wisdom
**Reviewed commit:** 8066f6ba70496be6d7e1ac4cd80c7731ba7b1d04
**PR:** ChainSafe/lodestar#8837 — feat: fast confirmation rule
**Scope:** Files listed in `/tmp/pr8837-files.txt`. Focus on the new `fast-choice/fastConfirmation/*` module plus `safeBlocks.ts`, `forkChoice.ts`, `chain.ts`, and the small surfaces in `interface.ts` / `index.ts`.

The new module is large but spec-aligned and the code is generally clear, well-commented in tricky spots (unit conversions, spec rounding), and consistently typed. Most observations below are about long-term readability — a future maintainer who does not have the spec PDF open should still be able to navigate this code.

---

## 1. Self-documenting names for the descendant-search loops

- **File:Line** — `packages/fork-choice/src/forkChoice/fastConfirmation/utils.ts:3184–3300` (`findLatestConfirmedDescendant`)
- **Principle** — Meaningful names; explicit over implicit.
- **Current** — Two large loop bodies guarded by booleans named `loop1Condition` and `loop2Condition`. Inside, the logger already uses the better names `"Fast confirmation previous-epoch loop ..."` and `"Fast confirmation current-epoch loop ..."`.
- **Suggested** — Rename to convey intent at the call site too, e.g. `shouldAdvanceThroughPreviousEpoch` / `shouldAdvanceThroughCurrentEpoch`. Optionally extract each loop into a small helper (`advanceThroughPreviousEpoch(...)`, `advanceThroughCurrentEpoch(...)`) so the top-level function reads as a 4–5 line orchestration.
- **Why** — `loop1` / `loop2` forces every reader to scroll the body to discover what each branch does. Names that match the log messages give the reader the model up front and let `findLatestConfirmedDescendant` become a one-page algorithm.

## 2. Stop encoding tuples into string keys

- **File:Line** — `packages/fork-choice/src/forkChoice/fastConfirmation/utils.ts:2999–3024` (`getCurrentTargetScore`)
- **Principle** — Explicit data structures over implicit string encoding; avoid serialize/parse round-trips inside a hot loop.
- **Current** — Validators are grouped via `const groupKey = \`${msg.root}:${msg.epoch}\``, then the key is split back with `groupKey.lastIndexOf(":")` and `Number(groupKey.slice(sepIdx + 1))`. Elsewhere the same module uses the reverse order (`${checkpoint.epoch}:${checkpoint.rootHex}`, `${target.epoch}:${target.rootHex}`).
- **Suggested** — Use a nested map and keep the values structured:
  ```ts
  const voteGroups = new Map<RootHex, Map<Epoch, number>>();
  // ...
  for (const [root, byEpoch] of voteGroups) {
    for (const [epoch, weight] of byEpoch) {
      const cp = getCheckpointForBlock(ctx, root, epoch);
      if (cp && cp.epoch === target.epoch && cp.rootHex === target.rootHex) score += weight;
    }
  }
  ```
- **Why** — Eliminates a class of bugs (key-order mismatches), removes the manual parse, and lets a future reader see the shape of the data without re-deriving it from a template literal. The current code is also subtly fragile: if a `RootHex` ever contained a `:`, `lastIndexOf` is correct only because the epoch is appended last — an invariant no name communicates.

## 3. Cache map keyed by a generic `string` instead of the literal union

- **File:Line** — `packages/fork-choice/src/forkChoice/fastConfirmation/types.ts:2298` and `utils.ts:2667–2723`
- **Principle** — Let the type system enforce invariants you already know.
- **Current** —
  ```ts
  voteWeightBySource: Map<string, Map<RootHex, number>>;
  ```
  with a doc comment saying "keyed by sourceKey (\"current\" | \"previous\")", while every call site already uses the literal union `"current" | "previous"`.
- **Suggested** —
  ```ts
  export type BalanceSourceKey = "current" | "previous";
  voteWeightBySource: Map<BalanceSourceKey, Map<RootHex, number>>;
  ```
- **Why** — The intent is currently expressed in a comment; the type signature should carry it. Anyone passing `"latest"` or `"prev"` by mistake would compile today and silently miss the cache.

## 4. Duplicated branches in `ensureVoteMaps`

- **File:Line** — `packages/fork-choice/src/forkChoice/fastConfirmation/utils.ts:2681–2700`
- **Principle** — DRY; one path through the function unless the variants are genuinely independent.
- **Current** — Two near-identical loops differ only by (a) iteration source (`activeIndices` vs. `0..balances.length`) and (b) whether `state.getValidator(i).slashed` is checked.
- **Suggested** — Compute the iteration set + the per-index "is slashed?" predicate once, then run a single loop:
  ```ts
  const indices: Iterable<number> = activeIndices ?? balances.keys();
  const isSlashed = state ? (i: number) => state.getValidator(i).slashed : () => false;
  for (const i of indices) {
    if (isSlashed(i)) continue;
    if (equivocating.has(i)) continue;
    const w = balances[i] ?? 0;
    if (w === 0) continue;
    const m = ctx.getLatestMessage(i);
    if (!m) continue;
    voteMap.set(m.root, (voteMap.get(m.root) ?? 0) + w);
  }
  ```
- **Why** — Cuts ~20 lines of mirrored logic; future changes (e.g. adding a new exclusion) only need to happen once. Reduces the chance of one branch silently drifting from the other.

## 5. `confirmed_reset` reason loses the actual cause

- **File:Line** — `packages/fork-choice/src/forkChoice/fastConfirmation/rules.ts:2129–2152` (`resetIfBehindOrNotAncestorOrUnsafe`)
- **Principle** — Structured logging with metadata, not catch-all strings; fail loudly with cause.
- **Current** — Three distinct conditions (`confirmedEpochBehindHead`, `notAncestorOfHead`, `allChildrenNotConfirmed`) collapse into a single `reason: "confirmed_reset"`.
- **Suggested** — Emit which guard fired (e.g. `"reset_behind"`, `"reset_not_ancestor"`, `"reset_chain_unsafe"`), or include the three flags in the metadata. The rule name already lists all three causes — let the result do the same.
- **Why** — When an operator sees a reset in production, the first question is "which of the three?" Without that breakdown, the only path to the answer is reproducing locally with verbose logging.

## 6. Repeated "neutral threshold" object literal

- **File:Line** — `packages/fork-choice/src/forkChoice/fastConfirmation/utils.ts:2884–2904` (`computeSafetyThreshold`)
- **Principle** — DRY; name the concept.
- **Current** — Two early-return paths produce the same `{threshold: Number.POSITIVE_INFINITY, proposerScore: 0, ...}` literal.
- **Suggested** —
  ```ts
  const SAFETY_THRESHOLD_UNREACHABLE = Object.freeze({
    threshold: Number.POSITIVE_INFINITY,
    proposerScore: 0,
    maximumSupport: 0,
    supportDiscount: 0,
    adversarialWeight: 0,
  });
  ```
  and return it (or a shallow copy) from both early exits. Even better, give the return shape a named type.
- **Why** — Encodes the meaning ("we couldn't compute, so no support can clear the bar") in a name, and ensures the two paths can never drift apart silently.

## 7. Optional chaining on a non-optional interface method

- **File:Line** — `packages/fork-choice/src/forkChoice/safeBlocks.ts:3500, 3520`
- **Principle** — Don't hand-wave away type information; if the contract says it exists, call it.
- **Current** — `IForkChoice` now declares `getConfirmedRoot(): RootHex` as a required method (`interface.ts:3477`), yet `safeBlocks.ts` calls `fc.getConfirmedRoot?.()` / `forkChoice.getConfirmedRoot?.()`.
- **Suggested** — Drop the `?.`. If callers in tests pass partial mocks, fix those mocks rather than the contract.
- **Why** — The optional chain misleads readers into thinking some implementations of `IForkChoice` don't have the method; in fact, the interface guarantees they do. It also short-circuits a follow-up bug (a missing `getConfirmedRoot` would silently fall through to the old justified path instead of failing fast).

## 8. `FCR*` re-export aliases

- **File:Line** — `packages/fork-choice/src/index.ts:3617–3627`
- **Principle** — Consistent naming; one canonical identifier per concept.
- **Current** — Internal names are `FastConfirmation*`; the public re-export renames them to `FCR*` (`FCRContext`, `FCRResult`, `IFCRStore`, `getFCRMetrics`, ...).
- **Suggested** — Keep the long names through the public surface, or rename at source. The two names for one concept will keep tripping `grep` and rename refactors.
- **Why** — Today a future reader sees `FCRContext` in beacon-node code and `FastConfirmationContext` in tests for the same type. Searching either yields half the call sites. Aliases like this tend to outlast the convenience that motivated them.

## 9. Dead `stop` field in `FastConfirmationDecision`

- **File:Line** — `packages/fork-choice/src/forkChoice/fastConfirmation/types.ts:2275–2280` and `rules.ts:2213–2216`
- **Principle** — Don't ship optional fields the system never uses.
- **Current** — `FastConfirmationDecision.stop?: boolean` is declared and `runFastConfirmationRules` honors it with `if (decision.stop) break;`, but no rule ever sets it.
- **Suggested** — Remove `stop` and the break, or document why the early-exit hook is part of the public rule API.
- **Why** — Unused extension points become "magic mystery features" — readers wonder when they fire and pessimistically have to assume they might. If the goal is "rules can short-circuit later", say so in a one-line comment so the optionality is intentional.

## 10. `getSupportDiscount` is a transparent pass-through

- **File:Line** — `packages/fork-choice/src/forkChoice/fastConfirmation/utils.ts:2861–2869`
- **Principle** — Avoid indirection that doesn't carry information.
- **Current** —
  ```ts
  export function getSupportDiscount(ctx, store, cache, balanceSource, blockRoot): number {
    return computeEmptySlotSupportDiscount(ctx, store, cache, balanceSource, blockRoot);
  }
  ```
- **Suggested** — Pick one name. If `getSupportDiscount` exists to mirror the spec function, add a one-line comment saying so; otherwise inline it at the single caller (`computeSafetyThreshold`).
- **Why** — A wrapper that does nothing but rename creates a phantom decision point — future readers will look for a behavioral difference and find none.

## 11. Magic constant `COMMITTEE_WEIGHT_ESTIMATION_ADJUSTMENT_FACTOR = 5`

- **File:Line** — `packages/fork-choice/src/forkChoice/fastConfirmation/utils.ts:2352`
- **Principle** — No magic numbers without provenance.
- **Current** — The constant is named well, but there's no link/citation to where the `5` (per-mille adjustment) comes from in the consensus-spec. `adjustCommitteeWeightEstimateToEnsureSafety` explains the unit conversion carefully but never explains the value itself.
- **Suggested** — Add a one-line comment with the spec link (or section name) and the rationale ("rounded-up safety margin from `<spec> §X`"). Same applies to the `999` in the same function — currently it's a generic ceiling-division trick but readers may try to map it to spec text.
- **Why** — Six months from now, "why 5?" is the first question someone tuning this constant will ask. A spec anchor saves them the dig.

## 12. Empty meta object on the FCR failure warning

- **File:Line** — `packages/fork-choice/src/forkChoice/forkChoice.ts:3414`
- **Principle** — Structured logging carries context.
- **Current** — `this.logger?.warn("Fast confirmation failed", {}, err as Error);`
- **Suggested** — Include the current slot, head root, and previous confirmed root in the meta:
  ```ts
  this.logger?.warn(
    "Fast confirmation failed",
    {slot: this.fcStore.currentSlot, head: this.head.blockRoot, confirmedRoot: this.fcStore.confirmedRoot},
    err as Error,
  );
  ```
- **Why** — If this ever fires in production, the empty `{}` forces the operator to correlate the warn with surrounding logs to learn even the slot. Two extra fields make every report self-contained.

---

## Smaller notes (worth a single pass, not blockers)

- **`fastConfirmation/utils.ts:2354–2361` (and friends)** — The "has → get ?? default" caching dance is repeated five times (`getBlock`, `getAncestorRoots`, `getCheckpointState`, `getSlotCommittee`, `isDescendantCached`). Each cache stores a different value shape so a single helper is awkward, but extracting `cache.<x>.get(key)` only once per lookup (instead of `has` + `get`) avoids a double hash and would read cleaner:
  ```ts
  const cached = cache.blockByRoot.get(root);
  if (cached !== undefined) return cached;
  ```
- **`fastConfirmation/utils.ts:2396–2402`, `2453–2457`** — `try { ... } catch { return null/false; }` swallows errors from `ctx.getAncestor`. This is reasonable at a boundary, but a one-line `// getAncestor throws when blockRoot has no ancestor at slot — treat as "no checkpoint"` makes the catch intentional rather than apologetic.
- **`fastConfirmation/fastConfirmationRule.ts:2027–2041`** — `updateFastConfirmationMetrics` sets `confirmedSlot`/`confirmedEpoch` to `0` when the block is missing. `0` is a real slot/epoch; a future dashboard reader may misinterpret it. Consider using `Number.NaN` (Prometheus drops `NaN`) or skipping the `.set` so the gauge stays at its last value.
- **`packages/utils/src/metrics.ts:5260–5276`** — `withObservedDuration` is a nice helper. The `EndTimer = (() => number) | undefined` shape is a little surprising; consider naming the union `MaybeEndTimer` (or making the helper accept `EndTimer | undefined`) so the optionality is in the parameter, not the type alias.
- **`fork-choice/src/forkChoice/forkChoice.ts:3456–3463`** — `getTrackedVotesCount` does a linear scan of `voteNextIndices` each slot. If the call frequency increases, prefer maintaining a counter alongside the array.

---

## Overall

The new fast-confirmation module is cleanly separated from `forkChoice.ts`, the per-slot cache and snapshot abstraction are good factoring choices, and the spec-vs-Lodestar unit-conversion comments are exemplary. The dominant readability risks are (a) string-encoded tuple keys in vote-grouping, (b) the placeholder names in `findLatestConfirmedDescendant`, and (c) the public API surface using both `FastConfirmation*` and `FCR*` names. Addressing those would meaningfully improve the long-term maintainability of an already large and inherently complex algorithm.
