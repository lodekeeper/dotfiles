# PR #10379 final thread reconciliation

Reviewer: review-wisdom
Reviewed commit: 86925723c28f6ae151a9c5308dfbd05d5da2668f

## Assessment

The previous identity timing-test issue is corrected, and the new payload-source wording is applied. No additional code-quality blocker was found in this focused reconciliation. The code dispositions below are compatible with a positive code assessment, subject to the parent's current-head focused checks.

**Do not give unconditional final approval yet: the specifically requested Kurtosis confirmation is still missing from the supplied discussion.** Nico requested a runtime check for timely builder discovery in [4330958984](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330958984); Marko accepted ownership in [4330975745](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330975745), but no result appears in the thread, issue comments or review bodies. This is pending validation of this PR, not another accepted post-merge follow-up.

Nico's subsequent [approval 5592663384](https://github.com/ChainSafe/lodestar/pull/10379#pullrequestreview-5592663384) is on this exact head and says “LGTM, leaving final approval up to @lodekeeper”. It does not explicitly retract the Kurtosis request or report its outcome. A code-only approval could be worded conditionally, but it would be easy to read as clearing the remaining request. Prefer a concise positive code assessment that leaves final sign-off pending Marko's result, then approve once that evidence is supplied or Nico explicitly waives the check.

## Evidence and scope

- Worktree HEAD verified as the exact commit above; worktree clean.
- Read all 23 GraphQL review threads, including resolved and outdated threads and their full comments. Thread pagination and all comment pagination report no next page.
- The 50 GraphQL comment IDs exactly match the 50 REST inline comment IDs. No inline comment is omitted by the thread inventory.
- UI state: 3 resolved/non-outdated threads, 11 unresolved/outdated threads, 9 unresolved/non-outdated threads. UI state is reported separately from substantive disposition below.
- Read all 8 issue comments and 33 review bodies. Neither surface contains the missing Kurtosis outcome or an explicit waiver. The approval body is the only new substantive final-review body after the earlier lodekeeper response.
- Compared the provided `builder-fixes-since-352.diff` against current source. Within the builder/CLI/workflow paths reviewed previously, the changes since `352a400` are the identity test correction and `software` to `engine` wording. The previously verified source fixes and accepted limitations remain unchanged.
- This reviewer did not run tests, install dependencies or mutate source/GitHub. The parent reports current-head CI unit/build/types/lint/spec/sim green and is running focused tests. Those checks do not themselves establish the requested runtime observation in the absence of the relevant output.

## Complete disposition of all 23 review threads

`U` means unresolved, `R` means resolved, `O` means outdated, and `current` means not outdated. These labels describe GitHub's UI only, not whether a request remains unaddressed.

| # | Thread / root comment | UI | Substantive disposition at reviewed head | Evidence / action |
| --- | --- | --- | --- | --- |
| 1 | `PRRT_kwDOCD5_Gc6sDBox` / [4263645834](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4263645834) | U, current | **Original requirement fixed; source-idle warning explicitly deferred.** | Source BN flag is documented in `packages/builder/README.md:19` and `packages/cli/src/cmds/builder/options.ts:43-45`, and enabled in `scripts/kurtosis/builder-dev.yaml:9`. No BN-default change was required. lodekeeper `4263994814`, Marko `4264019106` and Kris `4272194399` explicitly retain the active-source/no-attributes warning as follow-up LOD-111. Do not silently close that warning work. |
| 2 | `PRRT_kwDOCD5_Gc6sDBo3` / [4263645847](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4263645847) | U, current | **Explicit older follow-up: transient reveal retries.** | Marko `4263911629` accepts the finding but defers it to keep this PR minimal. `packages/builder/src/services/revealer.ts:73-78` still makes one publication attempt and propagates failure. Not implemented, not a newly discovered blocker. |
| 3 | `PRRT_kwDOCD5_Gc6sDBpA` / [4263645859](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4263645859) | U, O | **Explicit older follow-up: per-job Engine API cancellation.** | Marko `4263931117` explicitly defers the abort-aware Engine boundary. `handler.ts:108-125` still does not pass the per-job signal into Engine requests; initialization at line 105 has the process-wide shutdown signal. Outdated UI does not mean implemented. |
| 4 | `PRRT_kwDOCD5_Gc6sDBpK` / [4263645869](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4263645869) | U, current | **Fixed: advertised execution timeout applied at runtime.** | `packages/cli/src/cmds/builder/handler.ts:96` uses `args["execution.timeout"] ?? defaultExecutionEngineHttpOpts.timeout`. Help at `options.ts:96` displays the same value. This is the old bot P2, and it is addressed despite the unresolved UI. |
| 5 | `PRRT_kwDOCD5_Gc6ufC8C` / [4329223795](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4329223795) | U, O | **Answered and comment fixed: builderalways is configured.** | Marko `4329381940` and lodekeeper `4329397138` explain selection behavior. `builder-dev.yaml:20` sets `--builder.selection=builderalways`; `nightly-builder-smoke.yml:109` now names it explicitly. The smoke assertion asks for at least one win, allowing exceptional local fallback slots. |
| 6 | `PRRT_kwDOCD5_Gc6ufqIh` / [4329488280](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4329488280) | U, O | **Fixed: publication log relative to proposal slot.** | `packages/builder/src/services/bidder.ts:172` uses `clock.secFromSlot(slot)`; preceding-slot deadline calculation remains at lines 95-100. |
| 7 | `PRRT_kwDOCD5_Gc6ufvZ1` / [4329523765](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4329523765) | U, current | **Explicit October 20 follow-up: head_v2 canonical tracking.** | Marko `4330603207` promises a follow-up and lodekeeper `4330703199` acknowledges. `bidder.ts:86,188-189` still fetches proposer duties for the dependent root; `builder.ts:240-243` still has no head_v2 subscription. Keep the agreed epoch-keyed roots/fallback/stale-work design open, not claimed implemented. |
| 8 | `PRRT_kwDOCD5_Gc6ugy3M` / [4329974378](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4329974378) | U, O | **Fixed: generic payload source is not restricted to execution clients.** | `packages/builder/src/builder.ts:56` now says “Payload construction engine, an execution client is one implementation”. This also incorporates the later terminology preference in thread 23. |
| 9 | `PRRT_kwDOCD5_Gc6ug31C` / [4330006169](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330006169) | U, O | **Fixed: default operating admission floor is 1 ETH.** | `defaults.ts:17` uses `MIN_DEPOSIT_AMOUNT`; CLI default at `options.ts:168` and mapping at `handler.ts:144` agree. `bidder.ts:137-138` separately subtracts deposit minimum and unsettled amounts for coverage. |
| 10 | `PRRT_kwDOCD5_Gc6ug4nJ` / [4330011481](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330011481) | U, O | **Fixed: neutral default share is 10,000 bps.** | `defaults.ts:10-11` sets 10,000 bps and zero fixed cost; CLI references the default at `options.ts:126` and maps it at `handler.ts:138`. Existing coverage/max bounds remain. |
| 11 | `PRRT_kwDOCD5_Gc6ug7OS` / [4330028816](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330028816) | U, current | **Answered; source scheduling change present. Separate runtime evidence is still pending in thread 22.** | `identity.ts:116-119` already reads `head`; pending/unknown or stale pre-fork state retries each slot at lines 80-89 and 100-105. The pre-fork epoch wait now targets slot 1 at line 149. The reviewer described per-slot polling as acceptable; a wholesale once-per-epoch optimization was not required. Do not treat this static code answer as proof of timely runtime discovery. |
| 12 | `PRRT_kwDOCD5_Gc6ug8UD` / [4330036023](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330036023) | U, current | **Default question self-corrected; requested JSDoc fixed.** | `revealer.ts:13-17` states latest-start cutoff and the network's `PAYLOAD_ATTESTATION_DUE_BPS`; `builder.ts:64,211` and `options.ts:172-176` agree. Publication is triggered immediately, not delayed to the cutoff or guaranteed complete by it. |
| 13 | `PRRT_kwDOCD5_Gc6uhBzj` / [4330072517](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330072517) | R, current | **Answered/already fixed: removed mixed retry test can stay removed.** | The unclear `NO_PAYLOAD_ID` then permanent-error case is absent. Separate propagation and missing-ID retry coverage remain in `payloadOrchestrator.test.ts:259,271,292`, as lodekeeper `4330400190` explained. No restoration requested. |
| 14 | `PRRT_kwDOCD5_Gc6uhG1B` / [4330106988](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330106988) | U, current | **Explicit October 20 follow-up: pending payments plus withdrawals reconciliation; documentation objection self-retracted.** | Nico `4330114390` acknowledges the README already documents it. Marko `4330664109` intentionally keeps the thread unresolved for visibility. `README.md:24` and `builder.ts:26-30` document delayed debit and both queues; `builder.ts:232` still settles on a three-epoch timer. Keep implementation follow-up open. |
| 15 | `PRRT_kwDOCD5_Gc6uhJ1J` / [4330126819](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330126819) | U, O | **Fixed: CLI source-node description shortened.** | `options.ts:43-45` retains the URL and `--emitPayloadAttributes` setup requirement without explaining fallback slots. The README's fuller explanation is compatible. |
| 16 | `PRRT_kwDOCD5_Gc6uhKtz` / [4330132833](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330132833) | U, O | **Fixed: unnecessary “trusted” adjective removed.** | `options.ts:45` now says “URL of the beacon node”. |
| 17 | `PRRT_kwDOCD5_Gc6uhLp2` / [4330139287](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330139287) | U, O | **Fixed: builder CLI jwtId dropped.** | Builder argument type, option declarations and handler no longer contain `jwtId`. The unrelated generic Engine API option elsewhere is not part of the builder CLI request. |
| 18 | `PRRT_kwDOCD5_Gc6uhN1f` / [4330153831](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330153831) | R, current | **Self-retracted.** | Nico re-read the bidding deadline description and explicitly said it is fine. `options.ts:150-155` remains aligned with preceding-slot timing. No change required. |
| 19 | `PRRT_kwDOCD5_Gc6uhSIg` / [4330182333](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330182333) | U, O | **Fixed in source and runnable examples: execution.jwtSecret namespace.** | `options.ts:24,114`, `handler.ts:99-101`, `README.md:20`, `nightly-builder-smoke.yml:71` and `run-builder.sh:62` all use `execution.jwtSecret`. PR-description metadata remains separately stale and was already reported; do not duplicate that note as a new finding. |
| 20 | `PRRT_kwDOCD5_Gc6uhWE_` / [4330209534](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330209534) | R, current | **Approval-only / no action.** | Rocket reaction to `scripts/kurtosis/builder-dev.yaml`, no requested change. |
| 21 | `PRRT_kwDOCD5_Gc6ui1j8` / [4330846964](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330846964) | U, current | **Fixed: the reported identity fake-timer mismatch.** | Correction introduced in `f09097a1e5b` is retained after upstream merge. `identity.test.ts:203-215` now advances to epoch slot 0, asserts no request, waits to one millisecond before slot 1 and asserts no request, updates mock slot to `SLOTS_PER_EPOCH + 1`, then advances the final millisecond and awaits resolution. The old epoch-slot-0 deadline constant/import are removed. Static fix is sound; parent's focused rerun provides execution evidence. UI remains unresolved but code issue is addressed. |
| 22 | `PRRT_kwDOCD5_Gc6ujGPL` / [4330958984](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330958984) | U, current | **Still needs evidence: timely builder discovery/bidding on Kurtosis.** | Nico cites the Sepolia case where a builder was active for an epoch without bidding and explicitly requests a Kurtosis check. Marko `4330975745` says “will do”, which establishes ownership only. No outcome or waiver in any supplied discussion surface. Existing unit fixes, green general CI or the mere presence of a smoke workflow must not be called this runtime result. Await Marko's outcome rather than run a duplicate test in parallel. |
| 23 | `PRRT_kwDOCD5_Gc6ujKGv` / [4330984467](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330984467) | U, O | **Fixed: “payload construction engine” wording.** | Marko agrees in `4331003211`; source wording change from `7ab` is retained at `builder.ts:56`. No substantive behavior change. |

## Issue-level points and review bodies not represented as extra threads

- Kris's issue comments `6170879724` and `6217598696`, plus lodekeeper `6218096681`, asked that permanent Engine failures not be retried merely because shared engine state says SYNCING. This is already fixed by the specific `"Execution Layer Syncing"` request-error match and rethrow at `handler.ts:117-123`, plus `NO_PAYLOAD_ID`-only orchestrator retry at `payloadOrchestrator.ts:87-88`. No new code blocker or new P2 remains from that discussion.
- The settlement debate in `6170879724`, `6180079709`, `6190285666`, `6217598696` and Marko's `6223540554` is the same documented accounting follow-up as thread 14, not an implemented reconciliation. Both pending queues are necessary; a queued withdrawal does not itself debit balance.
- Marko's `6302417784` requests the re-check of `352a400`, and the lodekeeper review `5592395445` reports the prior timing-test failure and names the deferred work. That failure is now fixed by thread 21's code change.
- No later supplied review body reports new automated findings. The original bot P2 is thread 4 and is fixed. No unresolved-UI count should be used as a proxy for unaddressed code findings.
- Nico's approved review `5592663384` is a positive code opinion, not evidence that Marko completed thread 22.

## Deferral ledger

Keep these as agreed future work, not missing fixes required again by this final review:

1. **This round:** `head_v2` canonical tracking, guarded fallback and branch-change revalidation (thread 7).
2. **This round:** reconciliation against pending payments and pending withdrawals, replacing timer-only settlement (thread 14; also the older issue-level accounting discussion).
3. **Older:** transient envelope-publication retries within the reveal window (thread 2).
4. **Older:** per-job Engine request/queue cancellation through an abort-aware boundary (thread 3).
5. **Older:** active source/no-payload-attributes warning, LOD-111 (remaining follow-up in thread 1).

**Not part of this deferral ledger:** the Kurtosis runtime request in thread 22. It is still an outstanding validation action with an owner and no reported outcome, not accepted future implementation work.

## Metadata

The supplied current `pr.json` still lists `--jwtSecret` in the description's CLI bullet. Source and examples are correctly renamed to `--execution.jwtSecret`. This metadata drift was already reported publicly in review `5592395445`; it does not justify another duplicate comment or treating the source rename as incomplete.

## What closes the remaining evidence gap

Marko should report the requested Kurtosis run's outcome with enough timing context to establish that builder identity becomes active/discovered and bidding begins promptly, rather than silently losing an extra epoch. Relevant run/log/slot evidence can answer this; a promise to run it cannot. If the existing current-head automated runtime run actually exercises and demonstrates that case, its specific result could serve the same purpose, but no such result is present in the supplied discussion. No invented elapsed-time threshold is imposed here.

This does not require reopening the accepted follow-ups or adding a new feature. If Nico explicitly waives the runtime request, record that as a waiver rather than claiming it passed.

## Proposed concise public assessment

> The slot-1 identity test is fixed at `8692572`, and the remaining code points are addressed or explicitly deferred. Before final sign-off, please post the result of the [Kurtosis discovery check](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4330958984) you agreed to: confirm the builder is discovered and starts bidding promptly once active. I don't see that result in the thread yet.

Use a comment, not an unconditional approval, while that result is outstanding. After the runtime evidence is supplied and the parent's focused checks pass, the approval can concisely confirm the fix and runtime result without repeating every historical follow-up or the already-reported metadata note.
