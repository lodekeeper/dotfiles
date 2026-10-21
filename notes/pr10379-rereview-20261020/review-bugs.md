Reviewer: review-bugs
Reviewed commit: 352a400e0664ad910adc486826379c743d014522

# Bounded follow-up verification

Read fixes.diff, inline.md, issues.md, changed-files.txt and relevant source/tests at the exact reviewed commit. Source was read-only; no installs, tests or GitHub mutations were performed. Parent owns test execution.

No functional runtime bugs found in the claimed fixes. One concrete accompanying test regression is identified below.

## Finding: P2, update the fork-wait test for the second-slot wakeup

- File: `packages/builder/test/unit/identity.test.ts:209-211` (with stale `epochPollMs` at line 24; behavioral change in `packages/builder/src/identity.ts:149`).
- Bug: `msToNextEpochPoll` now sleeps until `computeStartSlotAtEpoch(1) + 1`. The existing test advances fake time only through `computeStartSlotAtEpoch(1)`, changes the mocked slot to that epoch's first slot, then awaits the still-pending identity promise. Fake timers do not advance while that promise is awaited.
- Impact: the test `resolves once the Gloas fork is reached` hangs until the test timeout, even though the runtime wakeup is correct.
- Fix: calculate the expected poll time including `+ 1`, advance the mocked clock to that same second slot, then advance fake timers through that deadline before awaiting resolution. Retain an assertion that there was no request at slot 0.
- Verification: established directly from the fake timer sequence and ClockMock; test execution delegated to parent.

## Prior-point disposition

| Prior point | Disposition | Evidence |
| --- | --- | --- |
| Publication log sign relative to proposal slot | Fixed | bidder.ts logs `clock.secFromSlot(slot)`; build deadline still correctly uses preceding slot. |
| Minimum balance default | Fixed | defaults.ts imports MIN_DEPOSIT_AMOUNT; bidder continues subtracting it and unsettled wins from coverable balance. |
| Neutral proportional share | Fixed | default shareBps is 10000, zero fixed cost; CLI uses this default. Policy still applies configured maximum and balance limits. |
| Identity second-slot epoch polling | Runtime fix safe, test update missed | Pre-fork polling wakes at next epoch slot 1. Missing or pending entries and transport failure still retry every next slot. A stale pre-Gloas head returning 400 also retries next slot, so missed epoch-boundary heads do not cause an epoch-long delay. This does not change post-fork absent/pending polling to once per epoch; that optimization is not needed for correctness. |
| execution.jwtSecret namespace and jwtId removal | Fixed | Argument type, option definition and handler read the same namespaced property. README, nightly workflow and run-builder.sh are updated. No old builder `--jwtSecret`/`--jwtId` references found in searched scripts/workflows/builder/CLI tests. |
| Specific SYNCING-only adapter retry | Earlier fix remains correct | handler catches only exact Error message `Execution Layer Syncing`. BN http.ts emits it only for specific SYNCING fcU response with payload attributes. INVALID and default statuses throw different errors, and permanent JSON-RPC errors are not converted based on mutable engine.state. EnginePayloadSource converts null into NO_PAYLOAD_ID, the sole orchestrator retry code. |
| Reveal cutoff description | Fixed | Public revealer JSDoc describes latest start and PAYLOAD_ATTESTATION_DUE_BPS default; builder.ts supplies that fallback. |
| PayloadSource description | Fixed | Builder option now describes payload construction software, not an obligatory EL implementation. |
| Redundant orchestrator case | Already removed | Permanent-error propagation and missing-ID retry cases remain; no lost runtime fix identified. |
| Canonical head_v2 tracking | Explicit owner-deferred follow-up | Owner comment 4330603207 and acknowledgement 4330703199; not a missed claimed fix. Existing duties-root lookup remains. |
| Pending-payment and pending-withdrawal reconciliation | Explicit owner-deferred follow-up | Owner comment 4330664109; README explicitly documents reservation release after three epochs and delayed withdrawals. Existing timer limitation is not newly fixed or a new regression. |
| Reveal retries and request cancellation | Previously deferred | Kris comment 6170879724 explicitly keeps these separate; not claimed fixes in 352a400. |
