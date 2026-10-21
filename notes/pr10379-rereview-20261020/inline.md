# inline

## 4263645834 chatgpt-codex-connector[bot] packages/builder/src/builder.ts parent=None 2026-10-13T20:26:10Z
**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Require per-slot payload attributes from the source node**

When `beaconNodeUrl` points at an ordinary Lodestar beacon node, this subscription does not provide per-slot work: `packages/beacon-node/src/chain/options.ts` defaults `emitPayloadAttributes` to false, and `prepareNextSlot.ts` emits without that flag only for slots whose proposer is in the local proposer cache. Since neither the builder CLI nor README requires `--emitPayloadAttributes`, a node without attached validators emits nothing and a node with validators triggers bids only for its own slots, silently leaving this bidder idle or incomplete; validate or document this source-node requirement.

Useful? React with 👍 / 👎.

## 4263645847 chatgpt-codex-connector[bot] packages/builder/src/services/revealer.ts parent=None 2026-10-13T20:26:10Z
**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Retry transient envelope publications before the cutoff**

When this single publication fails transiently while time remains, such as on a disconnect or 5xx response, the selected block is never retried. The builder API client in `packages/cli/src/cmds/builder/handler.ts` does not enable retries, `packages/api/src/utils/client/httpClient.ts` defaults them to 0, and `BlockObserver` records the block root as seen before invoking this callback, so a replay is ignored even though `EnvelopePublisher` permits another identical attempt after failure; retry transient failures within the remaining reveal window to avoid leaving the selected payload unrevealed.

Useful? React with 👍 / 👎.

## 4263645859 chatgpt-codex-connector[bot] packages/cli/src/cmds/builder/handler.ts parent=None 2026-10-13T20:26:11Z
**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Forward job abort signals into execution requests**

When an execution request runs past the prepare deadline or `bidding.getPayloadTimeout`, `EnginePayloadSource` aborts the per-job signal but these adapters discard that signal and call an engine that only has the process-wide shutdown signal. The orchestrator therefore reports a timeout while the HTTP request remains active until the engine transport timeout; a stale forkchoice request also remains in `ExecutionEngineHttp`'s queue and can block later-slot builds. Preserve the per-request signal through an abort-aware engine boundary.

Useful? React with 👍 / 👎.

## 4263645869 chatgpt-codex-connector[bot] packages/cli/src/cmds/builder/options.ts parent=None 2026-10-13T20:26:11Z
**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Apply the advertised execution timeout default**

When the operator omits `--execution.timeout`, Yargs' `defaultDescription` only displays the value in help, so `args["execution.timeout"]` remains undefined. Unlike the beacon command, this handler calls `initializeExecutionEngine` directly without `BeaconNodeOptions.getWithDefaults`, causing the JSON-RPC and REST clients to use their internal 30-second fallback instead of `defaultExecutionEngineHttpOpts.timeout` (12 seconds); set a real option default or apply the fallback in the handler.

Useful? React with 👍 / 👎.

## 4263911629 markolazic01 packages/builder/src/services/revealer.ts parent=4263645847 2026-10-13T20:54:32Z
this is valid and one of the meaningful follow-ups, not doing now to keep the PR minimal

## 4263921195 markolazic01 packages/builder/src/builder.ts parent=4263645834 2026-10-13T20:55:32Z
applied changes only on the builder side, if we should make any BN changes that is to be done separately
cc: @lodekeeper 

## 4263931117 markolazic01 packages/cli/src/cmds/builder/handler.ts parent=4263645859 2026-10-13T20:56:36Z
also meaningful but would increase the review surface properly, think it is not mandatory for the initial version, leaving as a planned follow-up

## 4263932030 markolazic01 packages/cli/src/cmds/builder/options.ts parent=4263645869 2026-10-13T20:56:42Z
applied

## 4263994814 lodekeeper packages/builder/src/builder.ts parent=4263645834 2026-10-13T21:03:48Z
No BN change needed in my view. `--emitPayloadAttributes` is the intended knob, and turning it on by default would make every node do per-slot payload attribute work just for builders. The README note plus `builder-dev.yaml` setting the flag on the source BN cover it. The only gap left is the silent idle case. A cheap guard would be for the builder to warn once if it receives head events but no `payload_attributes` for a few slots, which can be a follow-up.


## 4264019106 markolazic01 packages/builder/src/builder.ts parent=4263645834 2026-10-13T21:06:31Z
agree, another interesting follow-up
cc: @krisoshea-eth 

## 4272194399 krisoshea-eth packages/builder/src/builder.ts parent=4263645834 2026-10-14T14:36:33Z
Thanks Marko, happy to pick that up. I’ve added it to LOD-111. I’ll keep it on the Builder side and check that the source is actually active before warning about missing payload attributes, so startup or a disconnect doesn’t produce a misleading warning. No need to change the BN default.

## 4329223795 nflaig .github/workflows/nightly-builder-smoke.yml parent=None 2026-10-20T19:18:03Z
> the builder is the only bidder, it must have won bids and revealed their payloads

hmm what if local payload is more valuable or are we setting `builderalways` cc @lodekeeper can maybe confirm or deny

## 4329381940 markolazic01 .github/workflows/nightly-builder-smoke.yml parent=4329223795 2026-10-20T19:32:44Z
We use `builderalways` in `builder-dev.yaml`, so the bid is picked whenever one is available without comparing values. Without it the local payload wins every slot on the devnet since the builder bids with value 0.

## 4329397138 lodekeeper .github/workflows/nightly-builder-smoke.yml parent=4329223795 2026-10-20T19:34:07Z
Confirmed, local value doesn't matter here. The validators run with `--builder.selection=builderalways` ([builder-dev.yaml#L20](https://github.com/ChainSafe/lodestar/blob/119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b/scripts/kurtosis/builder-dev.yaml#L20)). The VC maps that to `MAX_BUILDER_BOOST_FACTOR` ([validatorStore.ts#L195-L197](https://github.com/ChainSafe/lodestar/blob/119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b/packages/validator/src/services/validatorStore.ts#L195-L197)), and with that factor `selectBlockProductionSourceByBoostFactor` returns the bid whenever a bid block was produced ([utils.ts#L88-L90](https://github.com/ChainSafe/lodestar/blob/119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b/packages/beacon-node/src/api/impl/validator/utils.ts#L88-L90), called at [index.ts#L1223](https://github.com/ChainSafe/lodestar/blob/119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b/packages/beacon-node/src/api/impl/validator/index.ts#L1223)).

Local can still win if the circuit breaker is active, the EL sets `shouldOverrideBuilder`, or no bid arrives before the bid deadline. That's why the check only needs at least one win over ~3 epochs. The comment could name the setting:

```suggestion
          # the builder is the only bidder and the validators use builderalways, so it must have won bids and revealed their payloads
```


## 4329488280 nflaig packages/builder/src/services/bidder.ts parent=None 2026-10-20T19:42:37Z
why `- 1`? this should probably print out a negative value if we published before the proposer slot or a positive value if we published in the slot

## 4329523765 nflaig packages/builder/src/services/bidder.ts parent=None 2026-10-20T19:46:03Z
this is not ideal and a bit hacky, ideally the builder should keep track of their canonical branch via the head event, cc @lodekeeper maybe has anohter idea, but if we just fetch duties to get the root it's definitely a bit wasteful. head event would also allow us to detect reorgs proactively, similar to how the vc does it

## 4329974378 nflaig packages/builder/src/builder.ts parent=None 2026-10-20T20:31:22Z
> Execution client

is too specific, this could be any payload construction software

## 4330006169 nflaig packages/builder/src/defaults.ts parent=None 2026-10-20T20:34:23Z
not sure this makes too much sense, we could just let balance drain to 1 ETH, there is no reason to keep the extra 0.1 ETH around and do nothing

## 4330011481 nflaig packages/builder/src/defaults.ts parent=None 2026-10-20T20:34:58Z
might be better to make the default 0 profit/loss, ie. 10000

## 4330028816 nflaig packages/builder/src/identity.ts parent=None 2026-10-20T20:36:54Z
this meant we discover builder 1 epoch too late but could be optimized by polling at slot 1 of the epoch with the head state advanced, polling each slot as done right now isn't needed but also not too big of a deal I suppose

## 4330036023 nflaig packages/builder/src/services/revealer.ts parent=None 2026-10-20T20:37:40Z
~~what's the default of this @lodekeeper~~ ah it's `PAYLOAD_ATTESTATION_DUE_BPS` might wanna make that more explicit

## 4330072517 nflaig packages/builder/test/unit/services/payloadOrchestrator.test.ts parent=None 2026-10-20T20:41:30Z
not sure what that even means based on the test description, so likely fine to delete it

## 4330106988 nflaig packages/builder/README.md parent=None 2026-10-20T20:44:47Z
might able to optimize this by using apis from https://github.com/ethereum/beacon-APIs/pull/655

## 4330114390 nflaig packages/builder/README.md parent=4330106988 2026-10-20T20:45:34Z
> Reconciling against the pending payments and withdrawals of the state is a follow-up.

should have read the last part, literally says it here

## 4330126819 nflaig packages/cli/src/cmds/builder/options.ts parent=None 2026-10-20T20:46:52Z
>  otherwise the builder only bids on slots the beacon node itself proposes

this doesn't need to be explicitly noted

## 4330132833 nflaig packages/cli/src/cmds/builder/options.ts parent=None 2026-10-20T20:47:30Z
> Url to a trusted beacon node

"trusted" is that how it documented for the validator client? i think this is mostly assumed in all cases

## 4330139287 nflaig packages/cli/src/cmds/builder/options.ts parent=None 2026-10-20T20:48:10Z
do we need this? seems useless

## 4330153831 nflaig packages/cli/src/cmds/builder/options.ts parent=None 2026-10-20T20:49:39Z
~~describtion doesn't really explain what the flag does?~~ nvm, re-read and it seems fine

## 4330182333 nflaig packages/cli/src/cmds/builder/options.ts parent=None 2026-10-20T20:52:46Z
would be better to namespace this, ie. `execution.jwtSecret`

## 4330209534 nflaig scripts/kurtosis/builder-dev.yaml parent=None 2026-10-20T20:55:43Z
🚀 

## 4330397995 lodekeeper packages/builder/src/services/bidder.ts parent=4329488280 2026-10-20T21:15:02Z
`clock.secFromSlot(slot)` gives the sign convention you want: negative before the proposal slot, positive after it starts. `slot - 1` measures from the build slot instead. Keep the preceding slot in the deadline calculation, but log publication relative to the proposal slot.

## 4330398394 lodekeeper packages/builder/src/services/bidder.ts parent=4329523765 2026-10-20T21:15:05Z
Agree. I'd use a small builder-local `head_v2` tracker: it already carries `current_epoch_dependent_root` and `next_epoch_dependent_root` for the head block's epoch and the following epoch ([event contract](https://github.com/ChainSafe/lodestar/blob/119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b/packages/api/src/beacon/routes/events.ts#L108)). That covers next-epoch proposals without fetching the full duties response per build. Key those roots by the event's epoch, not the clock epoch, since slots can be skipped.

Keep the duties call as a startup/reconnect or missing-epoch fallback, without letting an older fallback result overwrite newer event data. On relevant branch changes, recheck the captured preferences and whether that parent/variant is still a valid build target before publishing; discard only obsolete work. Keep the payload-attributes parent root/hash as the build target, not the duty-dependent root. `head_v2` also reports same-block payload-status changes, unlike legacy `head`.

## 4330398704 lodekeeper packages/builder/src/builder.ts parent=4329974378 2026-10-20T21:15:07Z
“Payload construction software” fits this interface better. The Engine API adapter is one implementation of `PayloadSource`, not a requirement that every source be an execution client.

## 4330398933 lodekeeper packages/builder/src/defaults.ts parent=4330006169 2026-10-20T21:15:09Z
The extra 0.1 ETH is only an admission threshold. `coverableGwei` already subtracts `MIN_DEPOSIT_AMOUNT` and unsettled bids, so that floor does not need another 0.1 ETH cushion. A 1 ETH default would leave any additional operating headroom opt-in.

## 4330399211 lodekeeper packages/builder/src/defaults.ts parent=4330011481 2026-10-20T21:15:11Z
10000 makes sense as the neutral default: with zero fixed cost, it uses 100% of the reported payload value as the proportional bid rather than reserving a 10% margin. The configured maximum and coverable-balance check still apply; operators can opt into a smaller share or a fixed cost.

## 4330399626 lodekeeper packages/builder/src/identity.ts parent=4330028816 2026-10-20T21:15:13Z
At this head it already requests `stateId: "head"` and retries each slot, so a slot-0 read of the previous head state is retried rather than waiting another whole epoch. For a once-per-epoch poll, slot 1 is a better target, provided the head has actually advanced; otherwise it still needs a retry rather than treating that read as final.

## 4330399881 lodekeeper packages/builder/src/services/revealer.ts parent=4330036023 2026-10-20T21:15:15Z
Yes, `Builder.init` resolves it as `opts.reveal.cutoffBps ?? config.PAYLOAD_ATTESTATION_DUE_BPS` ([source](https://github.com/ChainSafe/lodestar/blob/119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b/packages/builder/src/builder.ts#L211)). I'd copy “Defaults to the network's PAYLOAD_ATTESTATION_DUE_BPS” into this field's JSDoc, as the public builder option and CLI description already do.

It is a latest-start cutoff: a matching block triggers the reveal immediately, not at that point in the slot. It does not guarantee publication finishes before the cutoff.

## 4330400190 lodekeeper packages/builder/test/unit/services/payloadOrchestrator.test.ts parent=4330072517 2026-10-20T21:15:17Z
That removed case was specifically `NO_PAYLOAD_ID` on the first preparation attempt, then a permanent error on the second, checking that retries stop. It is already absent from the new version; the separate permanent-error propagation and missing-payload-ID retry tests remain.

## 4330400581 lodekeeper packages/cli/src/cmds/builder/options.ts parent=4330126819 2026-10-20T21:15:19Z
The shorter version can just be “URL of the beacon node. It must run with `--emitPayloadAttributes` to emit payload attributes for every slot.” That keeps the setup requirement without explaining the fallback behavior here.

## 4330400856 lodekeeper packages/cli/src/cmds/builder/options.ts parent=4330132833 2026-10-20T21:15:21Z
The VC currently says “Addresses to connect to BeaconNode”, without “trusted” ([source](https://github.com/ChainSafe/lodestar/blob/119fda5f3bbe03e0b2d26b6e6bd3ce4b4ccebe4b/packages/cli/src/cmds/validator/options.ts#L201)). “URL of the beacon node” would be consistent here.

## 4330401194 lodekeeper packages/cli/src/cmds/builder/options.ts parent=4330139287 2026-10-20T21:15:23Z
This only supplies the optional JWT `id` claim; the adapter does not otherwise use it. I would leave `jwtId` out of the builder CLI unless there is a concrete consumer for that identifier.

## 4330401475 lodekeeper packages/cli/src/cmds/builder/options.ts parent=4330182333 2026-10-20T21:15:25Z
Yes, `execution.jwtSecret` would match the other execution options. The CLI argument type and handler mapping need the same rename; `execution.jwtId` too if that option is retained.

## 4330603207 markolazic01 packages/builder/src/services/bidder.ts parent=4329523765 2026-10-20T21:37:24Z
will do a follow-up for this one

## 4330664109 markolazic01 packages/builder/README.md parent=4330106988 2026-10-20T21:44:02Z
leaving this unresolved for visibility, we should make that follow-up

## 4330703199 lodekeeper packages/builder/src/services/bidder.ts parent=4329523765 2026-10-20T21:48:45Z
Thanks, noted for the follow-up.

