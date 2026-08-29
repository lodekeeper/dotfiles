# PR #9914 Review Context — feat: flood publish execution payload bids

- Repo: ChainSafe/lodestar
- Author: markolazic01 (Marko Lazic) — known Lodestar/builder contributor; PR is "Curated from nflaig/lodestar#4" (Nico's work). Not adversarial.
- Base: `unstable`  Head SHA: `83a43eb9198c1ae535e7c1665565050d990397ce`
- Size: +301 / −12, 8 files. PR description is empty ("To be added").
- Fork context: ePBS / Gloas. Builders publish `SignedExecutionPayloadBid` via the beacon API; proposers select bids from a local pool populated by gossip.

## What the PR does (two orthogonal changes)

1. **Flood-publish own execution payload bids over gossip.** Bumps `@libp2p/gossipsub` `^16.1.1` → `^17.1.0` (17.x adds `PublishOpts.floodPublish`, replacing an earlier commit's `selectPeersToPublish` monkeypatch — the monkeypatch was reverted). `network.publishSignedExecutionPayloadBid` now passes `{floodPublish: true}`; `publishGossip` gains an `opts?: PublishOpts` param spread over the base opts. Flood publish = send to every subscribed peer above the publish threshold, not just mesh peers. Rationale in code: bids are tiny + time-critical, the proposer may not be in our mesh or on our head.

2. **New bespoke `validateApiExecutionPayloadBid`.** Previously it just delegated to `validateExecutionPayloadBid` (full gossip validation, returned `{proposerIndex}`). Now it is a standalone function returning `void` that applies ONLY the REJECT-class checks, skipping all IGNORE-class gossip rules. Rationale: own bids are published regardless of IGNORE rules (peers apply those themselves); only REJECT failures get a node penalized, so only those must be enforced locally.

## Key correctness property to verify: REJECT-parity

The safety argument for flood-publishing own bids is: *if a bid passes all REJECT checks locally, well-behaved peers will not REJECT (penalize) it.* This holds ONLY if the API path's REJECT set == the gossip path's REJECT set. I compared them (both at head SHA):

Gossip `validateExecutionPayloadBid` REJECT checks:
1. NOT_LATER_THAN_PARENT (bid.slot > parentBlock.slot)
2. BUILDER_NOT_ELIGIBLE (builderIndex < getBuildersLength)
3. BUILDER_NOT_ELIGIBLE (isActiveBuilder)
4. INVALID_BUILDER_VERSION (builder.version === PAYLOAD_BUILDER_VERSION)
5. NON_ZERO_EXECUTION_PAYMENT (executionPayment === 0)
6. TOO_MANY_KZG_COMMITMENTS (blobKzgCommitments.length <= maxBlobsPerBlock)
7. INVALID_PREV_RANDAO (prevRandao === state randao mix)
8. INVALID_SIGNATURE

API `validateApiExecutionPayloadBid` REJECT checks: **all 8 present.** → REJECT-parity holds at this commit.

IGNORE-class checks the API path skips: INVALID_SLOT (clock disparity), INCOMPATIBLE_WITH_HEAD, BID_ALREADY_KNOWN, NO_MATCHING_PROPOSER_PREFERENCES, UNKNOWN_PARENT_BLOCK_HASH, PROPOSER_PREFERENCES_FEE_RECIPIENT_MISMATCH, PROPOSER_PREFERENCES_GAS_LIMIT_MISMATCH, BID_TOO_LOW (min increment), BID_TOO_HIGH (`canBuilderCoverBid` balance coverage).

## AREAS TO VERIFY / CHALLENGE (confirm or refute — do not take these as given)

**A. Local pool insertion no longer gated by full gossip validation (headline concern).**
An earlier commit in THIS PR gated pool insertion on `validateGossipExecutionPayloadBid` with the comment: *"Only add the bid to the local pool if it passes full gossip validation, a local proposer must never commit to a bid that peers would not accept."* The FINAL version dropped that gate: the handler now does REJECT-only `validateApiExecutionPayloadBid`, then unconditionally `executionPayloadBidPool.add(...)`.
- The pool is keyed by tuple `(slot, parentBlockRoot, parentBlockHash)`, stores highest-value per tuple.
- The proposer (validator/index.ts) selects `getBestBid(slot, headPayloadHash, headBlockRoot)` keyed to ITS OWN head tuple, with **no re-validation** (no canBuilderCoverBid, no gossip checks).
- So head-compatibility is implicitly enforced by tuple-matching. BUT balance-coverage (`canBuilderCoverBid`) and proposer-preference (fee_recipient / gas_limit) checks are tuple-INDEPENDENT.
- Question: can an own bid that fails `canBuilderCoverBid` (value > builder excess balance) or proposer-preference IGNORE checks land under the proposer's exact head tuple and be selected → proposer commits to an uncoverable/mismatched bid → invalid/missed block? Does block production (computeNewStateRoot / state transition) re-validate coverage and reject it earlier? Is this the co-located own-builder+proposer case only? Is dropping commit 1's guard a real regression or intentionally safe?

**B. Empty PR description + MAJOR gossipsub bump (16→17).** No rationale/changelog in the PR. Verify: is `PublishOpts.floodPublish` the sanctioned 17.x API? Any other breaking changes in 16→17 that affect scoring/mesh/pruning behavior in a consensus client? Was this exercised on a devnet? (pnpm-lock shows only the version string changed — plausible but confirm no transitive surprises.)

**C. Thrown IGNORE surfaces to the builder API caller.** The handler does `await validateApiExecutionPayloadBid(...)` with NO try/catch. On unknown parent block or regen failure the function throws an IGNORE `ExecutionPayloadBidError`; on any REJECT it throws too. Both propagate to the API layer → likely HTTP 500 to the operator's own builder, and the bid is not published. For a transient slot-boundary race (parent block not yet imported), is erroring + dropping the own bid the right behavior, given the whole feature is about timeliness? Compare to the earlier "publish regardless even if parent unknown" approach that was reverted.

**D. regen `.catch()` collapses ALL failures to UNKNOWN_BLOCK_ROOT.** `getBlockSlotState(...).catch(() => throw IGNORE UNKNOWN_BLOCK_ROOT)`. Mirrors the gossip path exactly, but any regen error (timeout, corruption) is reported as "unknown block root," which is misleading for debugging. Low priority; is it worth a distinct code / preserving the cause?

**E. Maintainability / drift risk.** The REJECT-parity in (A)'s safety argument is enforced only by copy-paste: the 8 REJECT checks are duplicated between `validateApiExecutionPayloadBid` and `validateExecutionPayloadBid`. If someone later adds a REJECT check to gossip validation and forgets the API path, flood-publish self-penalizes silently. Should the REJECT checks be factored into a shared helper (e.g. `assertBidValidityChecks()`), or at minimum cross-referenced with a prominent comment so they can't drift?

**F. Bare `throw new Error(...)` for non-gloas state.** `if (!isStatePostGloas(state)) throw new Error(...)`. Violates Lodestar's typed-error convention, but it's copied verbatim from the existing gossip path (pre-existing pattern, not introduced here). Note-only.

**G. Test coverage gaps.** `executionPayloadBid.test.ts` covers valid + unknown-parent + regen-fail + not-later-than-parent + non-zero-payment + inactive-builder + wrong-randao + invalid-signature. Missing: TOO_MANY_KZG_COMMITMENTS, INVALID_BUILDER_VERSION, and the out-of-bounds builderIndex branch (only the isActiveBuilder branch of BUILDER_NOT_ELIGIBLE is hit). Also no direct unit test that `network.publishSignedExecutionPayloadBid` sets `floodPublish: true` (floodPublish.test.ts was deleted with the monkeypatch). Worth adding?

---

## SOURCE — full net diff

```diff
diff --git a/packages/beacon-node/package.json b/packages/beacon-node/package.json
index 316469649bf2..2623a0b7f3b1 100644
--- a/packages/beacon-node/package.json
+++ b/packages/beacon-node/package.json
@@ -118,7 +118,7 @@
     "@fastify/swagger-ui": "^5.0.1",
     "@libp2p/bootstrap": "^12.0.30",
     "@libp2p/crypto": "^5.1.23",
-    "@libp2p/gossipsub": "^16.1.1",
+    "@libp2p/gossipsub": "^17.1.0",
     "@libp2p/identify": "^4.1.13",
     "@libp2p/interface": "^3.3.0",
     "@libp2p/mdns": "^12.0.30",
diff --git a/packages/beacon-node/src/api/impl/beacon/blocks/index.ts b/packages/beacon-node/src/api/impl/beacon/blocks/index.ts
index 777f3071f2f1..c432c1993a75 100644
--- a/packages/beacon-node/src/api/impl/beacon/blocks/index.ts
+++ b/packages/beacon-node/src/api/impl/beacon/blocks/index.ts
@@ -1064,6 +1064,7 @@ export function getBeaconBlockApi({
         throw new ApiError(400, `publishExecutionPayloadBid not supported for pre-gloas fork=${fork}`);
       }
 
+      // TODO: skip validation for timely publishing once the builder is proven reliable
       await validateApiExecutionPayloadBid(chain, signedExecutionPayloadBid);
 
       const elapsedSec = chain.clock.secFromSlot(slot, seenTimestampSec);
diff --git a/packages/beacon-node/src/chain/regen/interface.ts b/packages/beacon-node/src/chain/regen/interface.ts
index b662a933ab01..b7c5399bdf35 100644
--- a/packages/beacon-node/src/chain/regen/interface.ts
+++ b/packages/beacon-node/src/chain/regen/interface.ts
@@ -24,6 +24,7 @@ export enum RegenCaller {
   validateApiVoluntaryExit = "validateApiVoluntaryExit",
   publishDeferredVoluntaryExits = "publishDeferredVoluntaryExits",
   validateGossipExecutionPayloadBid = "validateGossipExecutionPayloadBid",
+  validateApiExecutionPayloadBid = "validateApiExecutionPayloadBid",
   validateGossipPayloadAttestationMessage = "validateGossipPayloadAttestationMessage",
   validateGossipProposerPreferences = "validateGossipProposerPreferences",
   onForkChoiceFinalized = "onForkChoiceFinalized",
diff --git a/packages/beacon-node/src/chain/validation/executionPayloadBid.ts b/packages/beacon-node/src/chain/validation/executionPayloadBid.ts
index 4f25150c259d..078eb4d4f293 100644
--- a/packages/beacon-node/src/chain/validation/executionPayloadBid.ts
+++ b/packages/beacon-node/src/chain/validation/executionPayloadBid.ts
@@ -78,11 +78,119 @@ function isBidCompatibleWithHead(
   return buildsOnParentPayload;
 }
 
+/**
+ * Validation for bids submitted via the API by the operator's own builder.
+ *
+ * Only REJECT-class (validity) checks are applied: slot later than parent, zero execution payment,
+ * blob commitment count, builder eligibility and version, prev_randao, and signature. The transient
+ * IGNORE-class gossip rules (head compatibility, first bid per tuple, value increment, proposer
+ * preferences, balance coverage) are not applied, since those only limit forwarding of peers'
+ * messages and the builder may legitimately bid on a branch this node does not consider head.
+ *
+ * Throws on any failed REJECT check. Also throws IGNORE if the bid's parent block is unknown or its
+ * state is unavailable, since the validity checks cannot be evaluated against the parent branch; the
+ * bid is not published in that case.
+ */
 export async function validateApiExecutionPayloadBid(
   chain: IBeaconChain,
   signedExecutionPayloadBid: gloas.SignedExecutionPayloadBid
-): Promise<{proposerIndex: ValidatorIndex}> {
-  return validateExecutionPayloadBid(chain, signedExecutionPayloadBid);
+): Promise<void> {
+  const bid = signedExecutionPayloadBid.message;
+  const bidParentBlockRoot = toRootHex(bid.parentBlockRoot);
+
+  const parentBlock = chain.forkChoice.getBlockHexDefaultStatus(bidParentBlockRoot);
+  if (parentBlock === null) {
+    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
+      code: ExecutionPayloadBidErrorCode.UNKNOWN_BLOCK_ROOT,
+      parentBlockRoot: bidParentBlockRoot,
+    });
+  }
+
+  if (bid.slot <= parentBlock.slot) {
+    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
+      code: ExecutionPayloadBidErrorCode.NOT_LATER_THAN_PARENT,
+      parentSlot: parentBlock.slot,
+      slot: bid.slot,
+    });
+  }
+
+  if (bid.executionPayment !== 0n) {
+    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
+      code: ExecutionPayloadBidErrorCode.NON_ZERO_EXECUTION_PAYMENT,
+      builderIndex: bid.builderIndex,
+      executionPayment: bid.executionPayment,
+    });
+  }
+
+  const blobKzgCommitmentsLen = bid.blobKzgCommitments.length;
+  const maxBlobsPerBlock = chain.config.getMaxBlobsPerBlock(computeEpochAtSlot(bid.slot));
+  if (blobKzgCommitmentsLen > maxBlobsPerBlock) {
+    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
+      code: ExecutionPayloadBidErrorCode.TOO_MANY_KZG_COMMITMENTS,
+      blobKzgCommitmentsLen,
+      commitmentLimit: maxBlobsPerBlock,
+    });
+  }
+
+  const state = await chain.regen
+    .getBlockSlotState(parentBlock, bid.slot, {dontTransferCache: true}, RegenCaller.validateApiExecutionPayloadBid)
+    .catch(() => {
+      throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
+        code: ExecutionPayloadBidErrorCode.UNKNOWN_BLOCK_ROOT,
+        parentBlockRoot: bidParentBlockRoot,
+      });
+    });
+
+  if (!isStatePostGloas(state)) {
+    throw new Error(`Expected gloas+ state for execution payload bid validation, got fork=${state.forkName}`);
+  }
+
+  if (bid.builderIndex >= state.getBuildersLength()) {
+    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
+      code: ExecutionPayloadBidErrorCode.BUILDER_NOT_ELIGIBLE,
+      builderIndex: bid.builderIndex,
+    });
+  }
+
+  const builder = state.getBuilder(bid.builderIndex);
+  if (!isActiveBuilder(builder, state.finalizedCheckpoint.epoch)) {
+    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
+      code: ExecutionPayloadBidErrorCode.BUILDER_NOT_ELIGIBLE,
+      builderIndex: bid.builderIndex,
+    });
+  }
+
+  if (builder.version !== PAYLOAD_BUILDER_VERSION) {
+    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
+      code: ExecutionPayloadBidErrorCode.INVALID_BUILDER_VERSION,
+      builderIndex: bid.builderIndex,
+      version: builder.version,
+      expectedVersion: PAYLOAD_BUILDER_VERSION,
+    });
+  }
+
+  const randaoMix = state.getRandaoMix(computeEpochAtSlot(state.slot));
+  if (!byteArrayEquals(bid.prevRandao, randaoMix)) {
+    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
+      code: ExecutionPayloadBidErrorCode.INVALID_PREV_RANDAO,
+      builderIndex: bid.builderIndex,
+      bidPrevRandao: toHex(bid.prevRandao),
+      expectedPrevRandao: toHex(randaoMix),
+    });
+  }
+
+  const signatureSet = createSingleSignatureSetFromComponents(
+    builder.pubkey,
+    getExecutionPayloadBidSigningRoot(chain.config, bid),
+    signedExecutionPayloadBid.signature
+  );
+  if (!(await chain.bls.verifySignatureSets([signatureSet]))) {
+    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
+      code: ExecutionPayloadBidErrorCode.INVALID_SIGNATURE,
+      builderIndex: bid.builderIndex,
+      slot: bid.slot,
+    });
+  }
 }
 
 export async function validateGossipExecutionPayloadBid(
diff --git a/packages/beacon-node/src/network/network.ts b/packages/beacon-node/src/network/network.ts
index 09591f24f716..8efee78d6f59 100644
--- a/packages/beacon-node/src/network/network.ts
+++ b/packages/beacon-node/src/network/network.ts
@@ -516,7 +516,8 @@ export class Network implements INetwork {
 
     return this.publishGossip<GossipType.execution_payload_bid>(
       {type: GossipType.execution_payload_bid, boundary},
-      signedBid
+      signedBid,
+      {floodPublish: true}
     );
   }
 
@@ -542,17 +543,19 @@ export class Network implements INetwork {
 
   private async publishGossip<K extends GossipType>(
     topic: GossipTopicMap[K],
-    object: GossipTypeMap[K]
+    object: GossipTypeMap[K],
+    opts?: PublishOpts
   ): Promise<number> {
     const topicStr = stringifyGossipTopic(this.config, topic);
     const sszType = getGossipSSZType(topic);
     const messageData = (sszType.serialize as (object: GossipTypeMap[GossipType]) => Uint8Array)(object);
-    const opts: PublishOpts = {
+    const publishOpts: PublishOpts = {
       ignoreDuplicatePublishError: gossipTopicIgnoreDuplicatePublishError[topic.type],
       // Leave undefined unless the topic opts out, so `--network.allowPublishToZeroPeers` still applies
       allowPublishToZeroTopicPeers: gossipTopicAllowPublishToZeroPeers[topic.type] ? true : undefined,
+      ...opts,
     };
-    const sentPeers = await this.core.publishGossip(topicStr, messageData, opts);
+    const sentPeers = await this.core.publishGossip(topicStr, messageData, publishOpts);
 
     this.logger.verbose("Publish to topic", {topic: topicStr, sentPeers, currentSlot: this.clock.currentSlot});
     return sentPeers;
diff --git a/packages/beacon-node/test/unit/api/impl/beacon/blocks/publishExecutionPayloadBid.test.ts b/packages/beacon-node/test/unit/api/impl/beacon/blocks/publishExecutionPayloadBid.test.ts
new file mode 100644
index 000000000000..b485c5d6b3bc
--- /dev/null
+++ b/packages/beacon-node/test/unit/api/impl/beacon/blocks/publishExecutionPayloadBid.test.ts
@@ -0,0 +1,65 @@
+import {beforeEach, describe, expect, it, vi} from "vitest";
+import {createChainForkConfig} from "@lodestar/config";
+import {config as configDef} from "@lodestar/config/default";
+import {ssz} from "@lodestar/types";
+import {getBeaconBlockApi} from "../../../../../../src/api/impl/beacon/blocks/index.js";
+import {
+  ExecutionPayloadBidError,
+  ExecutionPayloadBidErrorCode,
+  GossipAction,
+} from "../../../../../../src/chain/errors/index.js";
+import {validateApiExecutionPayloadBid} from "../../../../../../src/chain/validation/executionPayloadBid.js";
+import {ApiTestModules, getApiTestModules} from "../../../../../utils/api.js";
+
+vi.mock("../../../../../../src/chain/validation/executionPayloadBid.js", () => ({
+  validateApiExecutionPayloadBid: vi.fn(),
+}));
+
+describe("api - beacon - publishExecutionPayloadBid", () => {
+  const config = createChainForkConfig({
+    ...configDef,
+    ALTAIR_FORK_EPOCH: 0,
+    BELLATRIX_FORK_EPOCH: 0,
+    CAPELLA_FORK_EPOCH: 0,
+    DENEB_FORK_EPOCH: 0,
+    ELECTRA_FORK_EPOCH: 0,
+    FULU_FORK_EPOCH: 0,
+    GLOAS_FORK_EPOCH: 0,
+  });
+  let modules: ApiTestModules;
+  const signedBid = ssz.gloas.SignedExecutionPayloadBid.defaultValue();
+  signedBid.message.slot = 1;
+  signedBid.message.builderIndex = 3;
+
+  beforeEach(() => {
+    vi.clearAllMocks();
+    modules = getApiTestModules({config});
+    modules.network.publishSignedExecutionPayloadBid = vi.fn().mockResolvedValue(5);
+    vi.mocked(validateApiExecutionPayloadBid).mockResolvedValue(undefined);
+  });
+
+  it("publishes the bid", async () => {
+    const api = getBeaconBlockApi(modules);
+    await api.publishExecutionPayloadBid({signedExecutionPayloadBid: signedBid});
+
+    expect(modules.network.publishSignedExecutionPayloadBid).toHaveBeenCalledWith(signedBid);
+    expect(modules.chain.executionPayloadBidPool.add).toHaveBeenCalled();
+  });
+
+  it("does not publish a bid that fails the reject checks", async () => {
+    vi.mocked(validateApiExecutionPayloadBid).mockRejectedValue(
+      new ExecutionPayloadBidError(GossipAction.REJECT, {
+        code: ExecutionPayloadBidErrorCode.INVALID_SIGNATURE,
+        builderIndex: 3,
+        slot: 1,
+      })
+    );
+    const api = getBeaconBlockApi(modules);
+    await expect(api.publishExecutionPayloadBid({signedExecutionPayloadBid: signedBid})).rejects.toThrow(
+      ExecutionPayloadBidError
+    );
+
+    expect(modules.network.publishSignedExecutionPayloadBid).not.toHaveBeenCalled();
+    expect(modules.chain.executionPayloadBidPool.add).not.toHaveBeenCalled();
+  });
+});
diff --git a/packages/beacon-node/test/unit/chain/validation/executionPayloadBid.test.ts b/packages/beacon-node/test/unit/chain/validation/executionPayloadBid.test.ts
new file mode 100644
index 000000000000..5cea37ac9ab1
--- /dev/null
+++ b/packages/beacon-node/test/unit/chain/validation/executionPayloadBid.test.ts
@@ -0,0 +1,111 @@
+import {beforeEach, describe, expect, it, vi} from "vitest";
+import {createBeaconConfig, createChainForkConfig} from "@lodestar/config";
+import {config as configDef} from "@lodestar/config/default";
+import {FAR_FUTURE_EPOCH, ForkName} from "@lodestar/params";
+import {IBeaconStateView} from "@lodestar/state-transition";
+import {ssz} from "@lodestar/types";
+import {ExecutionPayloadBidErrorCode} from "../../../../src/chain/errors/index.js";
+import {validateApiExecutionPayloadBid} from "../../../../src/chain/validation/executionPayloadBid.js";
+import {MockedBeaconChain, getMockedBeaconChain} from "../../../mocks/mockedBeaconChain.js";
+import {generateProtoBlock} from "../../../utils/typeGenerator.js";
+
+describe("validateApiExecutionPayloadBid", () => {
+  const config = createBeaconConfig(
+    createChainForkConfig({
+      ...configDef,
+      ALTAIR_FORK_EPOCH: 0,
+      BELLATRIX_FORK_EPOCH: 0,
+      CAPELLA_FORK_EPOCH: 0,
+      DENEB_FORK_EPOCH: 0,
+      ELECTRA_FORK_EPOCH: 0,
+      FULU_FORK_EPOCH: 0,
+      GLOAS_FORK_EPOCH: 0,
+    }),
+    Buffer.alloc(32, 0)
+  );
+  const randaoMix = Buffer.alloc(32, 1);
+  let chain: MockedBeaconChain;
+  let signedBid: ReturnType<typeof ssz.gloas.SignedExecutionPayloadBid.defaultValue>;
+
+  function mockState(overrides: Partial<{builder: ReturnType<typeof ssz.gloas.Builder.defaultValue>}> = {}) {
+    const builder = overrides.builder ?? ssz.gloas.Builder.defaultValue();
+    return {
+      forkName: ForkName.gloas,
+      slot: 2,
+      finalizedCheckpoint: {epoch: 1},
+      getBuildersLength: () => 1,
+      getBuilder: () => builder,
+      getRandaoMix: () => randaoMix,
+    } as unknown as IBeaconStateView;
+  }
+
+  beforeEach(() => {
+    chain = getMockedBeaconChain({config});
+    chain.forkChoice.getBlockHexDefaultStatus.mockReturnValue(generateProtoBlock({slot: 1}));
+    const builder = ssz.gloas.Builder.defaultValue();
+    builder.depositEpoch = 0;
+    builder.withdrawableEpoch = FAR_FUTURE_EPOCH;
+    chain.regen.getBlockSlotState.mockResolvedValue(mockState({builder}));
+    signedBid = ssz.gloas.SignedExecutionPayloadBid.defaultValue();
+    signedBid.message.slot = 2;
+    signedBid.message.prevRandao = randaoMix;
+  });
+
+  it("accepts a valid bid", async () => {
+    expect(await validateApiExecutionPayloadBid(chain, signedBid)).toBeUndefined();
+    expect(chain.bls.verifySignatureSets).toHaveBeenCalledOnce();
+  });
+
+  it("rejects if the parent block is unknown", async () => {
+    chain.forkChoice.getBlockHexDefaultStatus.mockReturnValue(null);
+    await expect(validateApiExecutionPayloadBid(chain, signedBid)).rejects.toMatchObject({
+      type: {code: ExecutionPayloadBidErrorCode.UNKNOWN_BLOCK_ROOT},
+    });
+
+    expect(chain.bls.verifySignatureSets).not.toHaveBeenCalled();
+  });
+
+  it("rejects if the parent state cannot be regenerated", async () => {
+    chain.regen.getBlockSlotState.mockRejectedValue(Error("no state"));
+    await expect(validateApiExecutionPayloadBid(chain, signedBid)).rejects.toMatchObject({
+      type: {code: ExecutionPayloadBidErrorCode.UNKNOWN_BLOCK_ROOT},
+    });
+
+    expect(chain.bls.verifySignatureSets).not.toHaveBeenCalled();
+  });
+
+  it("rejects a bid not later than its parent", async () => {
+    chain.forkChoice.getBlockHexDefaultStatus.mockReturnValue(generateProtoBlock({slot: 2}));
+    await expect(validateApiExecutionPayloadBid(chain, signedBid)).rejects.toMatchObject({
+      type: {code: ExecutionPayloadBidErrorCode.NOT_LATER_THAN_PARENT},
+    });
+  });
+
+  it("rejects a non-zero execution payment", async () => {
+    signedBid.message.executionPayment = 1n;
+    await expect(validateApiExecutionPayloadBid(chain, signedBid)).rejects.toMatchObject({
+      type: {code: ExecutionPayloadBidErrorCode.NON_ZERO_EXECUTION_PAYMENT},
+    });
+  });
+
+  it("rejects an inactive builder", async () => {
+    chain.regen.getBlockSlotState.mockResolvedValue(mockState());
+    await expect(validateApiExecutionPayloadBid(chain, signedBid)).rejects.toMatchObject({
+      type: {code: ExecutionPayloadBidErrorCode.BUILDER_NOT_ELIGIBLE},
+    });
+  });
+
+  it("rejects a wrong randao mix", async () => {
+    signedBid.message.prevRandao = Buffer.alloc(32, 2);
+    await expect(validateApiExecutionPayloadBid(chain, signedBid)).rejects.toMatchObject({
+      type: {code: ExecutionPayloadBidErrorCode.INVALID_PREV_RANDAO},
+    });
+  });
+
+  it("rejects an invalid signature", async () => {
+    vi.mocked(chain.bls.verifySignatureSets).mockResolvedValue(false);
+    await expect(validateApiExecutionPayloadBid(chain, signedBid)).rejects.toMatchObject({
+      type: {code: ExecutionPayloadBidErrorCode.INVALID_SIGNATURE},
+    });
+  });
+});
diff --git a/pnpm-lock.yaml b/pnpm-lock.yaml
index aa330f9d0e3f..da57b78ca23d 100644
--- a/pnpm-lock.yaml
+++ b/pnpm-lock.yaml
@@ -240,8 +240,8 @@ importers:
         specifier: ^5.1.23
         version: 5.1.23
       '@libp2p/gossipsub':
-        specifier: ^16.1.1
-        version: 16.1.1
+        specifier: ^17.1.0
+        version: 17.1.0
       '@libp2p/identify':
         specifier: ^4.1.13
         version: 4.1.13
@@ -2041,8 +2041,8 @@ packages:
   '@libp2p/crypto@5.1.23':
     resolution: {integrity: sha512-u6XVMD1YpUJgjS5MAayrxlzi+hQcj3FHY0wS6/M/T93ntyCW13BmmRzFb2ESamk65PEuSCAChmQeSzRV2sh2rQ==}
 
-  '@libp2p/gossipsub@16.1.1':
-    resolution: {integrity: sha512-GX2eDwn11eiRzfxGZ/c0KcndnQLBAVdnBR3/bQvrd5rFrZhc9wEMJmAwPzzjs1XSNE7xgqMnM5Ky3nM7lCxqbg==}
+  '@libp2p/gossipsub@17.1.0':
+    resolution: {integrity: sha512-azTGmO3ZaF51k+zamIiXfT/LsZiWCKapuhBnDgFbJEGaBY7LwwtR1BL3Kb6BMK+Li1wSXhfZahhxdlH9CHPVcA==}
     engines: {npm: '>=8.7.0'}
 
   '@libp2p/identify@4.1.13':
@@ -7767,7 +7767,7 @@ snapshots:
       uint8arraylist: 3.0.2
       uint8arrays: 6.1.1
 
-  '@libp2p/gossipsub@16.1.1':
+  '@libp2p/gossipsub@17.1.0':
     dependencies:
       '@libp2p/crypto': 5.1.23
       '@libp2p/interface': 3.3.0

```

## SOURCE — validation/executionPayloadBid.ts (FULL, at head)
```ts
import {IForkChoice, ProtoBlock} from "@lodestar/fork-choice";
import {PAYLOAD_BUILDER_VERSION} from "@lodestar/params";
import {
  computeEpochAtSlot,
  createSingleSignatureSetFromComponents,
  getExecutionPayloadBidSigningRoot,
  isActiveBuilder,
  isGasLimitTargetCompatible,
  isStartSlotOfEpoch,
  isStatePostGloas,
} from "@lodestar/state-transition";
import {RootHex, Slot, ValidatorIndex, gloas} from "@lodestar/types";
import {byteArrayEquals, toHex, toRootHex} from "@lodestar/utils";
import {getShufflingDependentRoot} from "../../util/dependentRoot.js";
import {ExecutionPayloadBidError, ExecutionPayloadBidErrorCode, GossipAction} from "../errors/index.js";
import {IBeaconChain} from "../index.js";
import {RegenCaller} from "../regen/index.js";

/**
 * Relative increment over the current highest bid required to forward a bid, in basis points.
 * With 3%, laddering from 1 gwei to 1 ETH takes ~256 bids given the floor and cap below, see
 * https://github.com/ethereum/consensus-specs/pull/4792#issuecomment-3714553549.
 */
const BID_INCREMENT_BPS = 300;
/**
 * Minimum absolute increment (0.0001 ETH). Covers low bid values where the relative increment
 * is tiny and provides weak spam protection.
 */
const BID_INCREMENT_FLOOR_GWEI = 100_000;
/**
 * Maximum absolute increment (0.01 ETH). Bounds the barrier for legitimate competition on
 * high value blocks where the relative increment would suppress closely competing bids.
 */
const BID_INCREMENT_CAP_GWEI = 10_000_000;

/**
 * Return the minimum value a new bid must have to be forwarded given the current highest bid.
 * Division before multiplication to stay within safe integer range for max gwei values.
 */
function getMinBidValue(currentHighestBid: number): number {
  const relativeIncrement = Math.floor(currentHighestBid / 10_000) * BID_INCREMENT_BPS;
  const increment = Math.min(Math.max(BID_INCREMENT_FLOOR_GWEI, relativeIncrement), BID_INCREMENT_CAP_GWEI);
  return currentHighestBid + increment;
}

/**
 * Check whether a bid builds on one of the paths compatible with the local head branch.
 *
 * Building directly on the parent is allowed for proposer-boost reorgs outside epoch boundaries.
 * Otherwise the bid must build on the local head's full or empty payload variant, as selected for its slot.
 */
function isBidCompatibleWithHead(
  forkChoice: IForkChoice,
  head: ProtoBlock,
  bidSlot: Slot,
  bidParentBlockRoot: RootHex,
  bidParentBlockHash: RootHex
): boolean {
  const buildsOnParentBlock = bidParentBlockRoot === head.parentRoot;
  const buildsOnParentPayload = bidParentBlockHash === head.parentBlockHash;

  if (buildsOnParentBlock && buildsOnParentPayload) {
    // The spec allows this at epoch boundaries, but Lodestar does not propagate these bids because validating
    // them requires an epoch transition for a parent state that cannot be used for proposer-boost reorgs.
    return !isStartSlotOfEpoch(bidSlot);
  }

  if (bidParentBlockRoot !== head.blockRoot) {
    return false;
  }

  const buildsOnHeadPayload = bidParentBlockHash === head.executionPayloadBlockHash;

  if (forkChoice.shouldBuildOnFull(head, bidSlot)) {
    return buildsOnHeadPayload;
  }

  return buildsOnParentPayload;
}

/**
 * Validation for bids submitted via the API by the operator's own builder.
 *
 * Only REJECT-class (validity) checks are applied: slot later than parent, zero execution payment,
 * blob commitment count, builder eligibility and version, prev_randao, and signature. The transient
 * IGNORE-class gossip rules (head compatibility, first bid per tuple, value increment, proposer
 * preferences, balance coverage) are not applied, since those only limit forwarding of peers'
 * messages and the builder may legitimately bid on a branch this node does not consider head.
 *
 * Throws on any failed REJECT check. Also throws IGNORE if the bid's parent block is unknown or its
 * state is unavailable, since the validity checks cannot be evaluated against the parent branch; the
 * bid is not published in that case.
 */
export async function validateApiExecutionPayloadBid(
  chain: IBeaconChain,
  signedExecutionPayloadBid: gloas.SignedExecutionPayloadBid
): Promise<void> {
  const bid = signedExecutionPayloadBid.message;
  const bidParentBlockRoot = toRootHex(bid.parentBlockRoot);

  const parentBlock = chain.forkChoice.getBlockHexDefaultStatus(bidParentBlockRoot);
  if (parentBlock === null) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.UNKNOWN_BLOCK_ROOT,
      parentBlockRoot: bidParentBlockRoot,
    });
  }

  if (bid.slot <= parentBlock.slot) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.NOT_LATER_THAN_PARENT,
      parentSlot: parentBlock.slot,
      slot: bid.slot,
    });
  }

  if (bid.executionPayment !== 0n) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.NON_ZERO_EXECUTION_PAYMENT,
      builderIndex: bid.builderIndex,
      executionPayment: bid.executionPayment,
    });
  }

  const blobKzgCommitmentsLen = bid.blobKzgCommitments.length;
  const maxBlobsPerBlock = chain.config.getMaxBlobsPerBlock(computeEpochAtSlot(bid.slot));
  if (blobKzgCommitmentsLen > maxBlobsPerBlock) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.TOO_MANY_KZG_COMMITMENTS,
      blobKzgCommitmentsLen,
      commitmentLimit: maxBlobsPerBlock,
    });
  }

  const state = await chain.regen
    .getBlockSlotState(parentBlock, bid.slot, {dontTransferCache: true}, RegenCaller.validateApiExecutionPayloadBid)
    .catch(() => {
      throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
        code: ExecutionPayloadBidErrorCode.UNKNOWN_BLOCK_ROOT,
        parentBlockRoot: bidParentBlockRoot,
      });
    });

  if (!isStatePostGloas(state)) {
    throw new Error(`Expected gloas+ state for execution payload bid validation, got fork=${state.forkName}`);
  }

  if (bid.builderIndex >= state.getBuildersLength()) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.BUILDER_NOT_ELIGIBLE,
      builderIndex: bid.builderIndex,
    });
  }

  const builder = state.getBuilder(bid.builderIndex);
  if (!isActiveBuilder(builder, state.finalizedCheckpoint.epoch)) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.BUILDER_NOT_ELIGIBLE,
      builderIndex: bid.builderIndex,
    });
  }

  if (builder.version !== PAYLOAD_BUILDER_VERSION) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.INVALID_BUILDER_VERSION,
      builderIndex: bid.builderIndex,
      version: builder.version,
      expectedVersion: PAYLOAD_BUILDER_VERSION,
    });
  }

  const randaoMix = state.getRandaoMix(computeEpochAtSlot(state.slot));
  if (!byteArrayEquals(bid.prevRandao, randaoMix)) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.INVALID_PREV_RANDAO,
      builderIndex: bid.builderIndex,
      bidPrevRandao: toHex(bid.prevRandao),
      expectedPrevRandao: toHex(randaoMix),
    });
  }

  const signatureSet = createSingleSignatureSetFromComponents(
    builder.pubkey,
    getExecutionPayloadBidSigningRoot(chain.config, bid),
    signedExecutionPayloadBid.signature
  );
  if (!(await chain.bls.verifySignatureSets([signatureSet]))) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.INVALID_SIGNATURE,
      builderIndex: bid.builderIndex,
      slot: bid.slot,
    });
  }
}

export async function validateGossipExecutionPayloadBid(
  chain: IBeaconChain,
  signedExecutionPayloadBid: gloas.SignedExecutionPayloadBid
): Promise<{proposerIndex: ValidatorIndex}> {
  return validateExecutionPayloadBid(chain, signedExecutionPayloadBid);
}

async function validateExecutionPayloadBid(
  chain: IBeaconChain,
  signedExecutionPayloadBid: gloas.SignedExecutionPayloadBid
): Promise<{proposerIndex: ValidatorIndex}> {
  const bid = signedExecutionPayloadBid.message;
  const bidParentBlockRoot = toRootHex(bid.parentBlockRoot);
  const bidParentBlockHash = toRootHex(bid.parentBlockHash);

  // [IGNORE] `bid.slot` is the current slot, or the next slot (`bid.slot - 1` is current), allowing for `MAXIMUM_GOSSIP_CLOCK_DISPARITY`.
  if (
    !chain.clock.isCurrentSlotGivenGossipDisparity(bid.slot) &&
    !chain.clock.isCurrentSlotGivenGossipDisparity(bid.slot - 1)
  ) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.INVALID_SLOT,
      builderIndex: bid.builderIndex,
      slot: bid.slot,
    });
  }

  // [IGNORE] The bid is compatible with the current head branch.
  const head = chain.forkChoice.getHead();
  if (!isBidCompatibleWithHead(chain.forkChoice, head, bid.slot, bidParentBlockRoot, bidParentBlockHash)) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.INCOMPATIBLE_WITH_HEAD,
      slot: bid.slot,
      parentBlockRoot: bidParentBlockRoot,
      parentBlockHash: bidParentBlockHash,
      headBlockRoot: head.blockRoot,
    });
  }

  // [IGNORE] this is the first signed bid seen with a valid signature from the given builder for
  // the tuple `(bid.slot, bid.parent_block_hash, bid.parent_block_root)`.
  // Entries are only added after signature verification, so known tuples can be dropped before
  // state regeneration and the other expensive validation steps.
  if (chain.seenExecutionPayloadBids.isKnown(bid.slot, bid.builderIndex, bidParentBlockHash, bidParentBlockRoot)) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.BID_ALREADY_KNOWN,
      builderIndex: bid.builderIndex,
      slot: bid.slot,
      parentBlockRoot: bidParentBlockRoot,
      parentBlockHash: bidParentBlockHash,
    });
  }

  // [IGNORE] `bid.parent_block_root` is the hash tree root of a known beacon block in fork choice.
  // Moved earlier than the spec ordering so we can derive the proposer dependent root for the
  // proposer-preferences lookup below from a known fork-choice block.
  const parentBlock = chain.forkChoice.getBlockHexDefaultStatus(bidParentBlockRoot);
  if (parentBlock === null) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.UNKNOWN_BLOCK_ROOT,
      parentBlockRoot: bidParentBlockRoot,
    });
  }

  // [REJECT] The bid is for a higher slot than its parent block -- i.e.
  // validate that `bid.slot` is greater than the slot of the block with root
  // `bid.parent_block_root`.
  if (bid.slot <= parentBlock.slot) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.NOT_LATER_THAN_PARENT,
      parentSlot: parentBlock.slot,
      slot: bid.slot,
    });
  }

  // [IGNORE] A `SignedProposerPreferences` matching `bid.slot` and the bid's branch has been
  // seen — i.e. `proposal_slot == bid.slot` AND `dependent_root ==
  // get_proposer_dependent_root(parent_state, compute_epoch_at_slot(bid.slot))`.
  const bidEpoch = computeEpochAtSlot(bid.slot);
  // gloas is always post-Fulu, so `get_proposer_dependent_root` is the post-Fulu (deterministic
  // proposer lookahead) form `block_root_at(start_slot(epoch - MIN_SEED_LOOKAHEAD) - 1)` with
  // `MIN_SEED_LOOKAHEAD == 1` — identical to the attester-shuffling dependent root for the same
  // epoch (both 1-epoch lookahead), hence `getShufflingDependentRoot`. `null` on a
  // unknown/finalized-pruned ancestor or genesis edge → degrade to IGNORE below instead of
  // letting a raw `ForkChoiceError` escape the `GossipActionError` contract.
  const dependentRootHex = (() => {
    try {
      return getShufflingDependentRoot(chain.forkChoice, bidEpoch, computeEpochAtSlot(parentBlock.slot), parentBlock);
    } catch {
      return null;
    }
  })();

  if (dependentRootHex === null) {
    // Could not derive the dependent root for this branch (unknown/finalized-pruned ancestor,
    // genesis edge, etc.) → definitionally no matching `SignedProposerPreferences`.
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.NO_MATCHING_PROPOSER_PREFERENCES,
      slot: bid.slot,
      parentBlockRoot: bidParentBlockRoot,
      dependentRoot: "unknown",
    });
  }

  const proposerPreferences = chain.proposerPreferencesPool.get(bid.slot, dependentRootHex);
  if (proposerPreferences === null) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.NO_MATCHING_PROPOSER_PREFERENCES,
      slot: bid.slot,
      parentBlockRoot: bidParentBlockRoot,
      dependentRoot: dependentRootHex,
    });
  }

  // Use the bid's parent branch state for builder checks
  const state = await chain.regen
    .getBlockSlotState(parentBlock, bid.slot, {dontTransferCache: true}, RegenCaller.validateGossipExecutionPayloadBid)
    .catch(() => {
      throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
        code: ExecutionPayloadBidErrorCode.UNKNOWN_BLOCK_ROOT,
        parentBlockRoot: bidParentBlockRoot,
      });
    });

  if (!isStatePostGloas(state)) {
    throw new Error(`Expected gloas+ state for execution payload bid validation, got fork=${state.forkName}`);
  }

  // [REJECT] `bid.builder_index` is within bounds -- i.e. `bid.builder_index < len(state.builders)`.
  // `state.getBuilder` returns a lazy SSZ `getReadonly` view that is not bounds-checked eagerly; an
  // out-of-range index only throws (`LeafNode has no right node`) on deferred field access (e.g. inside
  // `isActiveBuilder`), escaping a try/catch around `getBuilder`. Check the length explicitly instead.
  if (bid.builderIndex >= state.getBuildersLength()) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.BUILDER_NOT_ELIGIBLE,
      builderIndex: bid.builderIndex,
    });
  }

  // [REJECT] `bid.builder_index` is a valid/active builder index -- i.e.
  // `is_active_builder(state, bid.builder_index)` returns `True`.
  const builder = state.getBuilder(bid.builderIndex);
  if (!isActiveBuilder(builder, state.finalizedCheckpoint.epoch)) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.BUILDER_NOT_ELIGIBLE,
      builderIndex: bid.builderIndex,
    });
  }

  // [REJECT] The builder version is `PAYLOAD_BUILDER_VERSION` -- i.e.
  // `state.builders[bid.builder_index].version == PAYLOAD_BUILDER_VERSION`.
  if (builder.version !== PAYLOAD_BUILDER_VERSION) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.INVALID_BUILDER_VERSION,
      builderIndex: bid.builderIndex,
      version: builder.version,
      expectedVersion: PAYLOAD_BUILDER_VERSION,
    });
  }

  // [REJECT] `bid.execution_payment` is zero.
  if (bid.executionPayment !== 0n) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.NON_ZERO_EXECUTION_PAYMENT,
      builderIndex: bid.builderIndex,
      executionPayment: bid.executionPayment,
    });
  }

  // [IGNORE] `bid.fee_recipient == proposer_preferences.fee_recipient`.
  if (!byteArrayEquals(bid.feeRecipient, proposerPreferences.message.feeRecipient)) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.PROPOSER_PREFERENCES_FEE_RECIPIENT_MISMATCH,
      builderIndex: bid.builderIndex,
      bidFeeRecipient: toHex(bid.feeRecipient),
      expectedFeeRecipient: toHex(proposerPreferences.message.feeRecipient),
    });
  }

  // [IGNORE] `bid.parent_block_hash` is the block hash of a known execution payload in fork
  // choice. Looks up the variant of `bid.parent_block_root` whose payload hash matches
  // `bid.parent_block_hash` — works for both FULL parents (FULL variant carries the delivered
  // payload's hash) and EMPTY parents (EMPTY/PENDING variants carry the inherited parent
  // payload's hash, since the new block doesn't have its own payload). Variant carries the
  // executed payload's gas_limit, which we use as `parent_gas_limit` below.
  const parentPayloadVariant = chain.forkChoice.getBlockHexAndBlockHash(bidParentBlockRoot, bidParentBlockHash);
  if (parentPayloadVariant === null || parentPayloadVariant.executionPayloadBlockHash === null) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.UNKNOWN_PARENT_BLOCK_HASH,
      parentBlockHash: bidParentBlockHash,
    });
  }

  // [IGNORE] `is_gas_limit_target_compatible(parent_gas_limit, bid.gas_limit, target_gas_limit)`,
  // where `parent_gas_limit` is the `gas_limit` of the parent execution payload and
  // `target_gas_limit` is `proposer_preferences.target_gas_limit`.
  const bidGasLimit = bid.gasLimit;
  const parentGasLimit = BigInt(parentPayloadVariant.executionPayloadGasLimit);
  const targetGasLimit = proposerPreferences.message.targetGasLimit;
  if (!isGasLimitTargetCompatible(parentGasLimit, bidGasLimit, targetGasLimit)) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.PROPOSER_PREFERENCES_GAS_LIMIT_MISMATCH,
      builderIndex: bid.builderIndex,
      bidGasLimit,
      parentGasLimit,
      targetGasLimit,
    });
  }

  // [REJECT] The length of KZG commitments is less than or equal to the limitation defined in the
  // consensus layer -- i.e. validate that
  // `len(bid.blob_kzg_commitments) <= get_blob_parameters(compute_epoch_at_slot(bid.slot)).max_blobs_per_block`.
  const blobKzgCommitmentsLen = bid.blobKzgCommitments.length;
  const maxBlobsPerBlock = chain.config.getMaxBlobsPerBlock(computeEpochAtSlot(bid.slot));
  if (blobKzgCommitmentsLen > maxBlobsPerBlock) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.TOO_MANY_KZG_COMMITMENTS,
      blobKzgCommitmentsLen,
      commitmentLimit: maxBlobsPerBlock,
    });
  }

  // [IGNORE] this bid is the highest value bid seen for the tuple
  // `(bid.slot, bid.parent_block_hash, bid.parent_block_root)`.
  // As a DoS prevention measure, the bid must also exceed the current highest bid by a minimum
  // increment, see https://github.com/ethereum/consensus-specs/pull/4831. This prevents spam
  // from builders submitting numerous bids with minimal value increments.
  const bestBid = chain.executionPayloadBidPool.getBestBid(bid.slot, bidParentBlockHash, bidParentBlockRoot);
  if (bestBid !== null && bid.value < getMinBidValue(bestBid.signedBid.message.value)) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.BID_TOO_LOW,
      bidValue: bid.value,
      currentHighestBid: bestBid.signedBid.message.value,
    });
  }
  // [IGNORE] `bid.value` is less or equal than the builder's excess balance --
  // i.e. `can_builder_cover_bid(state, builder_index, amount)` returns `True`.
  if (!state.canBuilderCoverBid(bid.builderIndex, bid.value)) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.BID_TOO_HIGH,
      bidValue: bid.value,
      builderBalance: builder.balance,
    });
  }

  // [REJECT] `bid.prev_randao` is the correct RANDAO mix -- i.e. validate that
  // `bid.prev_randao == get_randao_mix(parent_state, get_current_epoch(parent_state))`.
  const randaoMix = state.getRandaoMix(computeEpochAtSlot(state.slot));
  if (!byteArrayEquals(bid.prevRandao, randaoMix)) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.INVALID_PREV_RANDAO,
      builderIndex: bid.builderIndex,
      bidPrevRandao: toHex(bid.prevRandao),
      expectedPrevRandao: toHex(randaoMix),
    });
  }

  // [REJECT] `signed_execution_payload_bid.signature` is valid with respect to the `bid.builder_index`.
  const signatureSet = createSingleSignatureSetFromComponents(
    builder.pubkey,
    getExecutionPayloadBidSigningRoot(chain.config, bid),
    signedExecutionPayloadBid.signature
  );

  if (!(await chain.bls.verifySignatureSets([signatureSet]))) {
    throw new ExecutionPayloadBidError(GossipAction.REJECT, {
      code: ExecutionPayloadBidErrorCode.INVALID_SIGNATURE,
      builderIndex: bid.builderIndex,
      slot: bid.slot,
    });
  }

  // Repeat the seen check after the awaited signature verification to prevent concurrent bids
  // for the same builder and tuple from both passing validation.
  if (chain.seenExecutionPayloadBids.isKnown(bid.slot, bid.builderIndex, bidParentBlockHash, bidParentBlockRoot)) {
    throw new ExecutionPayloadBidError(GossipAction.IGNORE, {
      code: ExecutionPayloadBidErrorCode.BID_ALREADY_KNOWN,
      builderIndex: bid.builderIndex,
      slot: bid.slot,
      parentBlockRoot: bidParentBlockRoot,
      parentBlockHash: bidParentBlockHash,
    });
  }

  // Valid
  chain.seenExecutionPayloadBids.add(bid.slot, bid.builderIndex, bidParentBlockHash, bidParentBlockRoot);

  return {proposerIndex: proposerPreferences.message.validatorIndex};
}
```

## SOURCE — opPools/executionPayloadBidPool.ts (FULL, at head)
```ts
import {Slot, gloas} from "@lodestar/types";
import {MapDef, toRootHex} from "@lodestar/utils";
import {InsertOutcome} from "./types.js";
import {pruneBySlot} from "./utils.js";

/**
 * TODO GLOAS: Revisit this value and add rational for choosing it
 */
const SLOTS_RETAINED = 2;

type BlockRootHex = string;
type BlockHashHex = string;

export type PooledExecutionPayloadBid = {
  signedBid: gloas.SignedExecutionPayloadBid;
  /** Time in milliseconds from the slot start when the bid was received */
  receivedMs: number;
};

/**
 * Store the best signed execution payload bid per slot / (parent block root, parent block hash).
 */
export class ExecutionPayloadBidPool {
  private readonly bidByParentHashByParentRootBySlot = new MapDef<
    Slot,
    MapDef<BlockRootHex, Map<BlockHashHex, PooledExecutionPayloadBid>>
  >(() => new MapDef<BlockRootHex, Map<BlockHashHex, PooledExecutionPayloadBid>>(() => new Map()));
  private lowestPermissibleSlot = 0;

  get size(): number {
    let count = 0;
    for (const byParentRoot of this.bidByParentHashByParentRootBySlot.values()) {
      for (const byParentHash of byParentRoot.values()) {
        count += byParentHash.size;
      }
    }
    return count;
  }

  add(bid: gloas.SignedExecutionPayloadBid, receivedMs: number): InsertOutcome {
    const {slot, parentBlockRoot, parentBlockHash, value} = bid.message;
    const lowestPermissibleSlot = this.lowestPermissibleSlot;

    if (slot < lowestPermissibleSlot) {
      return InsertOutcome.Old;
    }

    const parentRootHex = toRootHex(parentBlockRoot);
    const parentHashHex = toRootHex(parentBlockHash);
    const bidByParentHash = this.bidByParentHashByParentRootBySlot.getOrDefault(slot).getOrDefault(parentRootHex);
    const existing = bidByParentHash.get(parentHashHex);

    if (existing) {
      const existingValue = existing.signedBid.message.value;
      const newValue = value;
      if (newValue > existingValue) {
        bidByParentHash.set(parentHashHex, {signedBid: bid, receivedMs});
        return InsertOutcome.NewData;
      }
      return newValue === existingValue ? InsertOutcome.AlreadyKnown : InsertOutcome.NotBetterThan;
    }

    bidByParentHash.set(parentHashHex, {signedBid: bid, receivedMs});
    return InsertOutcome.NewData;
  }

  /**
   * Return the highest-value signed bid matching slot, parent block hash, and parent block root.
   * Used for gossip validation and block production.
   */
  getBestBid(
    slot: Slot,
    parentBlockHash: BlockHashHex | null,
    parentBlockRoot: BlockRootHex
  ): PooledExecutionPayloadBid | null {
    if (parentBlockHash === null) return null;
    const bidByParentHash = this.bidByParentHashByParentRootBySlot.get(slot)?.get(parentBlockRoot);
    return bidByParentHash?.get(parentBlockHash) ?? null;
  }

  prune(clockSlot: Slot): void {
    this.lowestPermissibleSlot = pruneBySlot(this.bidByParentHashByParentRootBySlot, clockSlot, SLOTS_RETAINED);
  }
}
```

## SOURCE — handler publishExecutionPayloadBid (blocks/index.ts lines ~1057-1097, at head)
```ts
    async publishExecutionPayloadBid({signedExecutionPayloadBid}) {
      const seenTimestampSec = Date.now() / 1000;
      const bid = signedExecutionPayloadBid.message;
      const slot = bid.slot;
      const fork = config.getForkName(slot);

      if (!isForkPostGloas(fork)) {
        throw new ApiError(400, `publishExecutionPayloadBid not supported for pre-gloas fork=${fork}`);
      }

      // TODO: skip validation for timely publishing once the builder is proven reliable
      await validateApiExecutionPayloadBid(chain, signedExecutionPayloadBid);

      const elapsedSec = chain.clock.secFromSlot(slot, seenTimestampSec);
      metrics?.gossipExecutionPayloadBid.elapsedTimeTillReceived.observe({source: OpSource.api}, elapsedSec);

      try {
        const insertOutcome = chain.executionPayloadBidPool.add(
          signedExecutionPayloadBid,
          Math.floor(elapsedSec * 1000)
        );
        metrics?.opPool.executionPayloadBidPool.apiInsertOutcome.inc({insertOutcome});
      } catch (e) {
        chain.logger.error("Error adding to executionPayloadBid pool", {}, e as Error);
      }

      const sentPeers = await network.publishSignedExecutionPayloadBid(signedExecutionPayloadBid);

      chain.emitter.emit(routes.events.EventType.executionPayloadBid, {
        version: fork,
        data: signedExecutionPayloadBid,
      });

      chain.logger.info("Published execution payload bid", {
        slot,
        builderIndex: bid.builderIndex,
        blockHash: toRootHex(bid.blockHash),
        parentBlockHash: toRootHex(bid.parentBlockHash),
        value: bid.value,
        sentPeers,
      });
    },
```

## SOURCE — proposer bid selection consumer (validator/index.ts, getBestBid call, unstable-ish)
```ts
463:      case BuilderStatus.circuitBreaker:
607:    const parentBlock = chain.getProposerHead(slot);
932:      const parentBlock = chain.getProposerHead(slot);
951:      const isBuildingOnFull = chain.forkChoice.shouldBuildOnFull(parentBlock, slot);
952:      const bidParentBlockHash = isBuildingOnFull ? parentBlock.executionPayloadBlockHash : parentBlock.parentBlockHash;
954:      if (bidParentBlockHash === null) {
957:      const circuitBreakerActive = chain.builderCircuitBreaker.isActive(slot, parentBlock);
962:      if (builderConfig.builders.length > 0 && !circuitBreakerActive) {
969:            fromHex(bidParentBlockHash),
982:        (!circuitBreakerActive &&
983:          chain.executionPayloadBidPool.getBestBid(slot, bidParentBlockHash, parentBlockRootHex) !== null);
987:      const p2pBidPromise: Promise<PooledExecutionPayloadBid | null> = circuitBreakerActive
990:            const p2pBid = chain.executionPayloadBidPool.getBestBid(slot, bidParentBlockHash, parentBlockRootHex);
1018:                  parentBlockHash: bidParentBlockHash,
1135:        circuitBreakerActive,
```
