# PR #10379 final public-text QA

Reviewer: review-wisdom
Reviewed commit: 352a400e0664ad910adc486826379c743d014522

## Decision

Approved with two small precision corrections below. No additional feature review or substantive change requested. No GitHub writes performed.

## Required wording correction

Replace:

> The other 50 tests across the four focused files pass; lint passes on the changed TypeScript files.

With:

> The other 50 tests across the four focused files pass; Biome passes on the eight TypeScript files changed by this commit.

Reason: 18 identity + 8 bidder + 5 revealer + 19 payload-orchestrator cases equals 50 passing tests, with the remaining identity case failing at the confirmed 20,000 ms timeout. The lint claim should name the actual tool and eight-file fix-commit scope; the present wording could imply the full repository lint command or every TypeScript file in the entire PR passed. `git show --name-only 352a400` confirms eight TypeScript files in this fix commit.

## Minor precision correction

In the inline request, replace:

> and retain an assertion that no request occurs at slot 0.

With:

> and assert that no request occurs at slot 0.

Reason: the current test asserts no request immediately before epoch slot 0, then advances into slot 0 and awaits. There is not currently a separate assertion at slot 0 to “retain.” The requested assertion itself is appropriate for the new schedule.

## Anchor verification

`packages/builder/src/identity.ts:149`, side RIGHT, is a suitable and valid changed-line anchor. `git show 352a400 -- packages/builder/src/identity.ts` shows this exact changed return expression adds `+ 1`, moving the scheduled wake-up one slot later. That production change directly invalidates the existing test's unchanged `epochPollMs` and fake-timer advance. The inline body clearly names the associated test, describes its stale expectation, and asks for the test update rather than suggesting the intended production change be reverted. Do not try to anchor to unchanged test lines outside the PR hunks.

The suggested test edits are precise: include the slot-1 offset in the test deadline, set the mock clock to `SLOTS_PER_EPOCH + 1`, and check no request at slot 0. The 20-second reproduced timeout is supported by the parent review's focused execution at the exact head; this QA pass did not rerun tests.

## Claim scope and deferrals

- The body correctly says requested source changes are present subject to two agreed current-round exceptions, and immediately identifies the remaining test failure. It does not give an unconditional approval or claim CI passed.
- Canonical-head tracking and pending payments/withdrawals reconciliation are the two current-round deferred threads. Optionally spelling the former as “`head_v2` canonical-head tracking” would make it even more specific, but the current wording is accurate.
- The final sentence correctly keeps the older transient reveal retry, per-job Engine cancellation and source-idle warning follow-ups separate. It does not imply those were implemented or silently closed.
- The metadata note correctly distinguishes the stale PR-description `--jwtSecret` spelling from the fully renamed source/examples `--execution.jwtSecret`. A general review-body note is appropriate for this metadata item; it is not presented as a new source finding.
- `event: COMMENT` is proportionate for this focused re-review and does not misstate the remaining test failure as approval.
- Public text contains no internal reviewer, agent or methodology narration.

## Corrected public body

> @markolazic01 Checked `352a400` against the discussion. The requested source changes are present, with `head_v2` canonical-head tracking and pending payments/withdrawals reconciliation left as agreed follow-ups. One test still needs updating: the identity fork-boundary case now times out, as noted inline. The other 50 tests across the four focused files pass; Biome passes on the eight TypeScript files changed by this commit.
>
> Small metadata fix: the PR description still lists `--jwtSecret`; it should say `--execution.jwtSecret`.
>
> The older reveal-retry, per-job Engine cancellation and source-idle-warning follow-ups remain separate.

The existing inline body is approved after replacing “retain an assertion” with “assert.”
