Reviewer: review-wisdom
Reviewed commit: 83a43eb9198c1ae535e7c1665565050d990397ce

# PR #9914 — Wise Senior Engineer review (clean-code / maintainability / comment↔code lens)

Scope: readability, maintainability, comment-vs-code consistency, forward-compatible naming, test
quality. Correctness of the flood-publish safety argument (A/B) is another reviewer's lane; I only
touch it where it bears on how the code *reads*.

Net verdict: the change is clean and idiomatic. No blockers from my lens. One genuine maintainability
smell (E, the drift risk), a couple of readability/semantics nits (C, docstring), and real test gaps
(G). Everything else is 🟢 note-only.

---

## 🟡 1. (E) REJECT checks are copy-pasted between the two validators — parity is load-bearing but unenforced

`packages/beacon-node/src/chain/validation/executionPayloadBid.ts`

The whole safety story ("flood-publishing own bids is safe because the API path enforces exactly the
REJECT checks peers enforce on gossip") rests on `validateApiExecutionPayloadBid` (L117–219) and
`validateExecutionPayloadBid` (L221+) applying the **same** REJECT set. Today they do — but only by
hand-copied `throw new ExecutionPayloadBidError(GossipAction.REJECT, {...})` blocks. Nothing links
them. If someone adds a REJECT check to gossip next quarter and forgets the API path, the node
flood-publishes bids peers will penalize — and it fails silently (no test, no type error).

Worth stressing: the two paths are **already structured differently**, which both proves the copy is
fragile and blocks a naive shared helper:

- API ordering: NOT_LATER_THAN_PARENT → NON_ZERO_PAYMENT → TOO_MANY_KZG → *(state)* → builder
  bounds → active → version → PREV_RANDAO → SIGNATURE.
- Gossip ordering: NOT_LATER_THAN_PARENT → *(state)* → builder bounds → active → version →
  NON_ZERO_PAYMENT → *(IGNOREs)* → TOO_MANY_KZG → *(IGNOREs)* → PREV_RANDAO → SIGNATURE.

The API path deliberately hoists the two cheap REJECTs (payment, KZG) above the expensive `regen`
call — a reasonable optimization — so you can't drop one shared `assertRejectChecks()` into both
without reordering gossip.

**Cleanest fix that fits Lodestar style:** extract each REJECT check as a tiny throwing helper and
call them from both paths in each path's own order. That kills the duplicated throw-bodies (the thing
that actually drifts) while preserving ordering:

```ts
// Shared REJECT-class assertions. Both the gossip and API validators MUST run all of these;
// flood-publishing own bids (API path) is only safe if its REJECT set matches gossip's.
function assertBidSlotLaterThanParent(bid: gloas.ExecutionPayloadBid, parentBlock: ProtoBlock): void { ... }
function assertZeroExecutionPayment(bid: gloas.ExecutionPayloadBid): void { ... }
function assertBlobCommitmentCount(chain: IBeaconChain, bid: gloas.ExecutionPayloadBid): void { ... }
function assertBuilderEligibleAndVersion(state: ..., bid: ...): {builder: gloas.Builder} { ... }
function assertPrevRandao(state: ..., bid: ...): void { ... }
async function assertBidSignature(chain, state, builder, signedBid): Promise<void> { ... }
```

**Minimum acceptable (if a refactor is deemed out of scope for this PR):** add a prominent
cross-reference comment at the top of each REJECT block in *both* functions, e.g.

```ts
// [REJECT] Keep in sync with validateExecutionPayloadBid — see validateApiExecutionPayloadBid.
// Flood-publish safety requires an identical REJECT set across both paths.
```

I'd push for the helper extraction; a comment is a reminder, not a guardrail.

---

## 🟡 2. (C) Handler swallows the IGNORE-vs-REJECT distinction, and nothing says that's intended

`packages/beacon-node/src/api/impl/beacon/blocks/index.ts` (handler ~L1063–1104) +
`executionPayloadBid.ts` L128 / L162 (the two `GossipAction.IGNORE` throws).

`validateApiExecutionPayloadBid` throws `ExecutionPayloadBidError` with a `GossipAction` tag, but the
API handler has no try/catch — every throw, IGNORE or REJECT, propagates identically to the API layer
and the bid is dropped. In a gossip context IGNORE-vs-REJECT drives peer scoring; on the API path that
distinction is **inert** — both just become "operator's own bid didn't publish."

Two readability consequences:

- A transient IGNORE (parent block not yet imported at the slot boundary, or a regen miss) drops the
  own bid and returns an error to the operator's own builder — for a feature whose entire point is
  timeliness. That may well be the intended trade-off (the reverted "publish even if parent unknown"
  approach shows it was considered), but **the handler gives no hint** that an IGNORE here means
  "transient, we chose to drop" vs a REJECT meaning "invalid, correctly rejected." A one-line comment
  at the `validateApiExecutionPayloadBid` call would earn its keep:

  ```ts
  // Throws on any REJECT (invalid bid) and also on transient IGNOREs (unknown parent / regen miss);
  // in both cases we drop rather than publish an own bid we cannot validate against the parent branch.
  await validateApiExecutionPayloadBid(chain, signedExecutionPayloadBid);
  ```

- Reusing `GossipAction.IGNORE/REJECT` as the throw taxonomy in a non-gossip path reads oddly — the
  action verb has no meaning here. It's pragmatic (reuses the existing error type) and I wouldn't
  block on it, but it's the kind of thing nflaig notices. If you keep it, the comment above is what
  makes it legible.

The docstring *does* document the drop ("the bid is not published in that case") — see item 4 — so
intent is captured in the JSDoc; it just isn't visible at the call site where the reader is.

---

## 🟡 3. (G) Test coverage gaps + no assertion that flood-publish is actually requested

Two new test files, good structure, readable `mockState` helper. Gaps:

`test/unit/chain/validation/executionPayloadBid.test.ts` — REJECT branches not exercised:
- **TOO_MANY_KZG_COMMITMENTS** — untested.
- **INVALID_BUILDER_VERSION** — untested (default builder `version === 0 === PAYLOAD_BUILDER_VERSION`,
  so the happy path never varies it; a `builder.version = 1` case is a one-liner).
- **BUILDER_NOT_ELIGIBLE out-of-bounds branch** — only the `isActiveBuilder` branch is hit
  ("rejects an inactive builder"). The `bid.builderIndex >= getBuildersLength()` branch (the one the
  gossip code has a big comment warning about — lazy SSZ view throwing on deferred access) is
  never taken. Set `signedBid.message.builderIndex = 1` against `getBuildersLength: () => 1`.

`test/unit/api/impl/beacon/blocks/publishExecutionPayloadBid.test.ts`:
- Asserts `publishSignedExecutionPayloadBid` was called and `pool.add` was called, but **not
  ordering** (validate → add → publish) and not that a validation failure blocks *both* add and
  publish in the same assertion pass (the reject test covers the not-called side — good).
- Because `floodPublish.test.ts` was deleted with the monkeypatch, **nothing now asserts
  `network.publishSignedExecutionPayloadBid` passes `{floodPublish: true}`.** That's the headline
  behavior change of half this PR and it's untested. Add a focused unit test on `Network`:

  ```ts
  it("flood-publishes execution payload bids", async () => {
    const publishGossip = vi.spyOn(network.core, "publishGossip").mockResolvedValue(0);
    await network.publishSignedExecutionPayloadBid(signedBid);
    expect(publishGossip).toHaveBeenCalledWith(
      expect.any(String),
      expect.any(Uint8Array),
      expect.objectContaining({floodPublish: true})
    );
  });
  ```

Severity 🟡 because the missing floodPublish assertion + missing builder-bounds branch are the two
places a future refactor could silently regress the exact properties this PR exists to add.

---

## 🟢 4. Docstring accuracy — mostly good, one incomplete list; TODO should reference an issue

`executionPayloadBid.ts` L104–116 (JSDoc) and `blocks/index.ts` L1073 (TODO).

- "the bid is not published in that case" (L114–115): **accurate.** The handler awaits validation
  before `pool.add`/`publish` with no try/catch, so any throw prevents publication. Confirmed against
  the handler body. Good.
- The parenthetical list of *skipped* IGNORE rules — "(head compatibility, first bid per tuple, value
  increment, proposer preferences, balance coverage)" — is **incomplete**: it omits the slot/clock
  disparity check (`INVALID_SLOT`) and `UNKNOWN_PARENT_BLOCK_HASH`, both of which the API path also
  skips. The slot-timeliness omission is the notable one: the API path applies **no** slot-window
  check at all, so nothing in this function bounds how stale/future a bid's slot may be (only
  `pool.add`'s `slot < lowestPermissibleSlot` guards staleness downstream). Either add "clock/slot
  window" to the list or, better, say the list is illustrative ("such as ...") so it can't read as
  exhaustive.
- `// TODO: skip validation for timely publishing once the builder is proven reliable`
  (blocks/index.ts L1073) — nflaig likes TODOs tied to a tracking issue. Suggest
  `// TODO(#XXXX): ...` so it doesn't become an orphaned comment.

---

## 🟢 5. (D) regen `.catch()` collapses every failure to UNKNOWN_BLOCK_ROOT and drops the cause

`executionPayloadBid.ts` L160–167.

```ts
.catch(() => {
  throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
    code: ExecutionPayloadBidErrorCode.UNKNOWN_BLOCK_ROOT,
    parentBlockRoot: bidParentBlockRoot,
  });
});
```

A regen timeout, cache miss, or corruption is reported as "unknown block root" — misleading when
debugging why an own bid failed to publish, and the original error/stack is discarded entirely.
It mirrors the gossip path verbatim (L797–804), so consistency argues for leaving it; but since
this is the *own-builder* path where an operator will actually be reading these errors, at minimum
preserve the cause: `.catch((e) => { throw new ExecutionPayloadBidError(..., {..., }); })` — the
current arrow drops `e`. Low priority; flag it, don't block.

---

## 🟢 6. (F) Bare `throw new Error(...)` for non-gloas state — pre-existing convention, note only

`executionPayloadBid.ts` L169–171. Untyped `throw new Error("Expected gloas+ state ...")` violates
Lodestar's typed-error convention, but it is copied verbatim from the gossip path and the identical
pattern already lives in `executionPayloadEnvelope.ts:166` and `payloadAttestationMessage.ts:99`.
So it's an established (if imperfect) house style for these gloas validators, not something this PR
introduces. The only new wrinkle is that this PR now has it in **two** places in one file (API +
gossip). If the item-1 helper extraction happens, this collapses to one occurrence for free.
No action required for this PR.

---

## 🟢 7. Naming / fork-codename leakage — checked, nothing to fix

Looked specifically for "gloas" leaking where a forward-compatible name is preferred. All uses are
canonical: `gloas.SignedExecutionPayloadBid` (SSZ type namespace), `isStatePostGloas` /
`isForkPostGloas` (the established post-fork predicates), `RegenCaller.validateApiExecutionPayloadBid`
(feature-named, not fork-named), and the `Expected gloas+ state` message (a fork name, correctly
rendered as an inclusive "+"). No codename is baked into a public API surface or a name that a later
fork would falsify. Nothing to change.

---

## Summary table

| # | Sev | Area | File | Ask |
|---|-----|------|------|-----|
| 1 | 🟡 | E | executionPayloadBid.ts | Extract shared REJECT-assert helpers (or min: cross-ref comment) to stop parity drift |
| 2 | 🟡 | C | blocks/index.ts + validator | Comment that IGNORE-on-API means "transient, drop own bid" — distinction is otherwise invisible |
| 3 | 🟡 | G | both test files | Add KZG / builder-version / builder-bounds cases + a `{floodPublish:true}` network assertion |
| 4 | 🟢 | docstring | executionPayloadBid.ts / index.ts | Skipped-checks list omits slot/clock + unknown-parent-hash; make it illustrative; TODO→issue ref |
| 5 | 🟢 | D | executionPayloadBid.ts | regen catch loses cause + mislabels all failures as UNKNOWN_BLOCK_ROOT |
| 6 | 🟢 | F | executionPayloadBid.ts | Bare `throw new Error` — pre-existing convention, note only |
| 7 | 🟢 | naming | — | No fork-codename leak; nothing to change |

---

## 🔴 CORRECTNESS (verified by lodekeeper, main-session pass) — signature check passes raw pubkey bytes

`executionPayloadBid.ts:182` (validateApiExecutionPayloadBid), commit 83a43eb.

```ts
const signatureSet = createSingleSignatureSetFromComponents(
  builder.pubkey,                       // <-- raw Uint8Array (48-byte BLSPubkey)
  getExecutionPayloadBidSigningRoot(chain.config, bid),
  signedExecutionPayloadBid.signature
);
```

`createSingleSignatureSetFromComponents(pubkey: PublicKey, ...)` (state-transition/src/util/signatureSets.ts:110) requires a deserialized `PublicKey`. The gossip path passes `PublicKey.fromBytes(builder.pubkey)` (same file, gossip validator). `builder.pubkey` from the SSZ view is a `Uint8Array`, not a `PublicKey` → fails `pnpm check-types` (TS2345), and if it slipped past types would break the signature REJECT gate at runtime. `PublicKey` is already imported in the file. Fix: wrap with `PublicKey.fromBytes(builder.pubkey)`.

CI has NOT caught this: only "Validate PR title" + "reconcile" have run on the PR; the test/type-check matrix is not yet triggered.

## ✅ REJECT-set parity verified (safety argument holds)
All 8 gossip REJECT checks are present in the API path: NOT_LATER_THAN_PARENT, BUILDER_NOT_ELIGIBLE (bounds), BUILDER_NOT_ELIGIBLE (active), INVALID_BUILDER_VERSION, NON_ZERO_EXECUTION_PAYMENT, TOO_MANY_KZG_COMMITMENTS, INVALID_PREV_RANDAO, INVALID_SIGNATURE. So flood-publishing own bids cannot emit a bid peers would REJECT. (Note: wisdom item-4's "skipped INVALID_SLOT/clock disparity" is inaccurate — the gossip validator has no slot-window/clock-disparity check; the only slot check is NOT_LATER_THAN_PARENT, which the API path has.)
