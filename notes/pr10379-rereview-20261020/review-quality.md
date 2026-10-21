# PR #10379 review-point coverage

Reviewer: review-wisdom
Reviewed commit: 352a400e0664ad910adc486826379c743d014522

## Scope and result

Read-only review of `/home/openclaw/lodestar-review-10379-352a400`, with HEAD and a clean worktree verified. Inputs were the provided inline comments, issue comments, review bodies, fixes diff, changed-file list and PR metadata. No source edits, dependency installs, GitHub mutations or test execution were performed by this reviewer.

The requested October 20 source changes are present, except for the two explicitly deferred threads. Items already fixed, self-retracted or approval-only are distinguished below. The statement must not be broadened to say that all historical follow-ups are implemented: transient reveal retries, per-job Engine API cancellation and the source-idle warning also remain deferred.

Code quality is solid: no significant additional maintainability improvements suggested. There is one concrete verification issue associated with the identity timing edit, described below. Consequently, an unconditional clean re-review reply should wait for its correction or focused verification by the main review.

## Concrete verification issue in the requested fix

### P2: Update the fork-boundary identity test for the new slot-1 wake-up

- Location: `packages/builder/src/identity.ts:149`, with the stale expectation in `packages/builder/test/unit/identity.test.ts:195` (both are in `changed-files.txt`).
- The implementation now sleeps until `computeStartSlotAtEpoch(nextEpoch) + 1`.
- The test's `epochPollMs` at line 24 still measures to the first slot of the epoch. Lines 205 and 210 advance only that old amount, set `currentSlot` to `SLOTS_PER_EPOCH`, then line 211 awaits `promise` while fake timers remain one full slot short of the scheduled wake-up.
- With this `ClockMock`, the missing slot is 12,000 ms (`test/unit/utils/clock.ts:12,20`). No later timer advance occurs before the await, so this test cannot resolve normally and is expected to hit Vitest's timeout. This is a static timing conclusion, not a claim that this reviewer ran the test.
- Requested correction: express and assert the second-slot wake-up in this test, including the appropriate `currentSlot` and fake-time advance. Keep the existing per-slot retries for stale pre-fork head state.
- Narrow verification: `pnpm vitest run --project unit packages/builder/test/unit/identity.test.ts -t 'resolves once the Gloas fork is reached'` from a checkout with the existing dependencies available.

## Complete nflaig/lodekeeper coverage map

All 17 nflaig and 15 lodekeeper inline comments are covered in the paired rows below. Both lodekeeper issue comments are also covered. The provided review bodies contain no additional nflaig/lodekeeper review point.

| Review comment IDs | Point | Status at reviewed head and source evidence |
| --- | --- | --- |
| lodekeeper `4263994814` (reply to bot `4263645834`) | Document the source BN's `--emitPayloadAttributes` requirement; no BN-default change; warn on silent idle later | **Requirement already fixed before this latest commit; idle warning explicitly deferred.** `packages/builder/README.md:19`, `packages/cli/src/cmds/builder/options.ts:43`, and `scripts/kurtosis/builder-dev.yaml:9` retain the flag. `builder.ts:240` subscribes to block, proposer-preferences and payload-attributes events, not a head/source-idle guard. Marko agreed to the warning follow-up in `4264019106`, and Kris named LOD-111 in `4272194399`. |
| nflaig `4329223795`; lodekeeper `4329397138` | Does builderalways actually make the zero-value builder win; name the setting in smoke-test comment | **Addressed.** `scripts/kurtosis/builder-dev.yaml:20` still sets `--builder.selection=builderalways`; `.github/workflows/nightly-builder-smoke.yml:109` now explicitly names it. The test requires at least one bid and win at lines 121-125, not every slot winning. |
| nflaig `4329488280`; lodekeeper `4330397995` | Publication logging must be relative to proposal slot, while build deadline remains in preceding slot | **Fixed in latest commit.** `packages/builder/src/services/bidder.ts:172` now uses `clock.secFromSlot(slot)`; lines 95-100 retain the preceding-slot deadline calculation. |
| nflaig `4329523765`; lodekeeper `4330398394`, `4330703199` | Track canonical branch with epoch-keyed `head_v2` dependent roots, guarded fallback and revalidation of stale work | **October 20 follow-up 1, not implemented.** `bidder.ts:86,188` still fetches proposer duties for each coalesced build; `builder.ts:240` still has no head_v2 subscription. Marko explicitly deferred this in `4330603207`; `4330703199` only acknowledges that agreement. The deferred design retains the payload-attributes parent root/hash as the build target, keys roots by event epoch, protects newer event data from older fallback completion, and rechecks only potentially obsolete parent/variant/preferences on branch changes. |
| nflaig `4329974378`; lodekeeper `4330398704` | Describe the generic PayloadSource as payload construction software, not necessarily an execution client | **Fixed in latest commit.** `packages/builder/src/builder.ts:56` now says exactly that an execution client is one implementation. The CLI/README still require an EL for the supplied Engine API adapter, which is compatible with the generic interface. |
| nflaig `4330006169`; lodekeeper `4330398933` | Lower default admission floor to the deposit minimum, without the extra 0.1 ETH | **Fixed in latest commit.** `packages/builder/src/defaults.ts:17` uses `MIN_DEPOSIT_AMOUNT`, which is 1,000,000,000 Gwei in both presets. The CLI default at `options.ts:168` references it, the handler passes it at line 144, and `bidder.ts:137-138` still separately subtracts deposit minimum and unsettled bids. |
| nflaig `4330011481`; lodekeeper `4330399211` | Use neutral 100% share by default | **Fixed in latest commit.** `defaults.ts:10` is `10_000`, with zero fixed cost at line 11. `options.ts:126` and `handler.ts:138` use that option; existing policy limits and coverable-balance enforcement are unchanged. |
| nflaig `4330028816`; lodekeeper `4330399626` | Avoid an epoch-late identity read; slot-1 polling is an optional optimization with retry if head has not advanced | **Original correctness concern already addressed; optional optimization not required in full.** `identity.ts:116-119` queries `stateId: "head"`; stale pre-fork 400 retries at lines 80-89 and pending/unknown retries at lines 100-105 remain per slot. The latest edit moves the pre-Gloas epoch wait at line 72 to next-epoch slot 1 through lines 147-149. It does not convert all identity polling to once per epoch, nor is that necessary to satisfy the non-blocking comment. The accompanying existing fork-boundary test needs the update noted above. |
| nflaig `4330036023`; lodekeeper `4330399881` | State reveal's default explicitly and distinguish latest-start cutoff from scheduled publication/completion deadline | **Fixed in latest commit.** `services/revealer.ts:13-17` says latest start and network `PAYLOAD_ATTESTATION_DUE_BPS`; `builder.ts:64,211` and `options.ts:172-176` agree. `revealer.ts:58-64` rejects arrivals after cutoff and line 74 publishes immediately without waiting for the cutoff or guaranteeing completion by then. nflaig retracted only the question about what the default is, not the documentation suggestion. |
| nflaig `4330072517`; lodekeeper `4330400190` | The unclear mixed retry/permanent-error test can remain deleted | **Already addressed before latest commit; no new change needed.** The mixed test is absent. `services/payloadOrchestrator.test.ts:259` still covers immediate permanent-error propagation, line 271 covers missing-ID retry success, and line 292 covers a fixed retry deadline. Source retry selection remains `PayloadSourceErrorCode.NO_PAYLOAD_ID` only at `payloadOrchestrator.ts:87-88`. |
| nflaig `4330106988`, `4330114390` | Replace timer settlement with pending-state APIs; then acknowledge README already calls this a follow-up | **October 20 follow-up 2, not implemented.** `README.md:24` explicitly calls for pending payments and withdrawals reconciliation. `builder.ts:26-30,232` still uses the three-epoch timer, and `bidLedger.ts:193-205` still marks old wins settled. nflaig self-corrected the documentation objection in `4330114390`; Marko retained the unresolved thread for follow-up visibility in `4330664109`. |
| nflaig `4330126819`; lodekeeper `4330400581` | Shorten source-BN CLI description while retaining setup requirement | **Fixed in latest commit.** `options.ts:43-45` now retains only URL and the `--emitPayloadAttributes` requirement, dropping the fallback explanation from the CLI description. README can legitimately keep its fuller setup explanation. |
| nflaig `4330132833`; lodekeeper `4330400856` | Remove unnecessary “trusted” wording | **Fixed in latest commit.** `options.ts:45` is “URL of the beacon node”, without “trusted”. |
| nflaig `4330139287`; lodekeeper `4330401194` | Drop unused builder CLI `jwtId` | **Fixed in latest commit.** No `jwtId` remains in the builder command's argument type, option declarations or handler. The optional generic Engine API JWT identifier elsewhere in the repository is not the builder CLI feature under review. |
| nflaig `4330153831` | Retracted concern about bidding deadline flag description | **Self-retracted; no change required.** `options.ts:150-155` describes the slot before the proposal slot and agrees with `bidder.ts:95-100`. |
| nflaig `4330182333`; lodekeeper `4330401475` | Namespace JWT secret and update type/handler/consumers consistently | **Source rename complete in latest commit.** `options.ts:24,114`, `handler.ts:99-101`, `README.md:20`, `nightly-builder-smoke.yml:71`, and `run-builder.sh:62` all use `execution.jwtSecret`. No builder-related `--jwtSecret` or `jwtId` usage remains in these paths. See the non-source metadata note below. |
| nflaig `4330209534` | Rocket reaction on builder devnet configuration | **Approval-only; no change requested.** `scripts/kurtosis/builder-dev.yaml` retains the reviewed configuration. |
| lodekeeper issue comment `6190285666` | A queued withdrawal does not immediately debit builder balance; reconcile both pending queues | **Earlier settlement clarification, now documented and still deferred.** `README.md:24` and `builder.ts:26-30` retain the exact delayed-debit limitation, including both pending payments and pending withdrawals. It is the same accounting follow-up as the October 20 README thread, not an additional implemented fix. |
| lodekeeper issue comment `6218096681` | Do not infer request retryability from shared engine state, which also maps permanent failures to SYNCING | **Already fixed before latest commit.** `handler.ts:117-123` now handles only the specific `"Execution Layer Syncing"` error and rethrows everything else. It never checks `engine.state`. The Engine implementation throws that exact message in its request's SYNCING branch (`packages/beacon-node/src/execution/engine/http.ts:379-382`) and uses different errors for INVALID/unknown status. `payloadOrchestrator.ts:87-88` retries only the missing-ID path. This is the acknowledged minimal fix, not a request for a fresh typed-error redesign. |

## Earlier bot points and historical follow-ups

These prevent the phrase “except two follow-ups” from silently closing older agreed work:

| Earlier point | Disposition at reviewed head |
| --- | --- |
| `4263645834`: per-slot payload attributes | Setup requirement is documented and enabled in the devnet; see the `4263994814` row. **Source-idle warning remains deferred** via `4264019106` and LOD-111. |
| `4263645847`: retry transient envelope publication before reveal cutoff | **Still deferred**, explicitly accepted by Marko in `4263911629`. `revealer.ts:73-78` still makes one publication attempt and propagates failure; it does not retry inside the reveal window. |
| `4263645859`: forward per-job abort signals through Engine requests | **Still deferred**, explicitly accepted by Marko in `4263931117`. `handler.ts:108` and line 125 adapt Engine calls without forwarding their per-job signal; line 105 initializes the engine with only the process-wide shutdown signal. The payload-source/orchestrator layer supporting a signal does not make the Engine HTTP calls request-cancellable. |
| `4263645869`: apply advertised execution timeout | **Already fixed.** `handler.ts:96` uses `args["execution.timeout"] ?? defaultExecutionEngineHttpOpts.timeout`, while `options.ts:96` displays the same default. A help-only default is safe here because the handler applies the runtime fallback. |
| Kris's October 14/16 requests to distinguish permanent failures from SYNCING (`6170879724`, `6217598696`) | The exact-error adapter and selective orchestrator retry already address the minimal request. This is the same fix confirmed for lodekeeper's `6218096681`, not another deferred item. |
| Kris's accounting requests (`6170879724`, `6217598696`) | The timer is not replaced. The README and constant now document its limitation, as promised by Marko in `6223540554`; the pending-payments plus withdrawals work remains explicitly deferred. |

## Docs/options/defaults alignment

- Source, README, workflow and run-script JWT spelling align on `--execution.jwtSecret`; the builder CLI no longer exposes `jwtId`.
- No obsolete 1.1-ETH or 9000-share default remains in the inspected default/CLI/documentation chain. Test fixtures can still choose explicit non-default shares without contradicting the defaults.
- The minimum-balance default remains a raw operating-admission threshold, with coverable-balance accounting separately protecting the deposit minimum and current unsettled reservations.
- Reveal JSDoc, public option type, runtime resolution and CLI help agree on the network-derived default and latest-start behavior.
- Source-BN requirements align across README, CLI help and devnet source-node flags.
- **Non-source metadata drift:** the supplied `pr.json` description still advertises `--jwtSecret` in its CLI additions bullet. It also presents timer settlement without the README's explicit caveat. This is outside `changed-files.txt`, so it is not a new code finding or merge blocker in this report. The source rename is complete, but a claim that all user-visible documentation is renamed should be qualified until the PR description is corrected.

## Proposed concise public response

The current timing-test mismatch prevents an unconditional “everything addressed” response. A concise response that reflects the present reviewed head is:

> The requested changes are in place at `352a400`, with canonical-head tracking and pending payments/withdrawals reconciliation left as agreed follow-ups. One test needs updating for the identity polling change: `resolves once the Gloas fork is reached` still advances only to epoch slot 0, but the new wake-up is slot 1, so it awaits an unresolved promise under fake timers. Please update that timing assertion. Reveal retries, per-job Engine cancellation and the source-idle warning remain the previously agreed follow-ups.

After the identity test is corrected and focused verification passes, the clean version would be:

> Checked the updated head: the requested changes are addressed. The two follow-ups from this round are `head_v2` canonical tracking and reconciliation against pending payments plus withdrawals. The older reveal-retry, Engine cancellation and source-idle-warning follow-ups remain separate.
