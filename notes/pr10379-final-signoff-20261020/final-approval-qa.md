# PR #10379 final approval QA

Reviewer: review-wisdom
Reviewed commit: 86925723c28f6ae151a9c5308dfbd05d5da2668f

## Decision

**Final APPROVE and a same-thread acknowledgment are justified.** No further code changes or tests are requested by this QA pass. The previous recommendation to wait is superseded by both newly supplied evidence and Nico's explicit decision that further validation may be performed separately and any needed fix shipped as a follow-up.

- Marko's [runtime sample 4331256769](https://github.com/ChainSafe/lodestar/pull/10379#discussion_r4331256769) shows pending identity through slot 32, active identity resolution at slot 33, bid publication for proposal slots 34-37, and successful reveals for slots 34-36. The first bid is published about 5.75 seconds after identity resolution, in the slot preceding proposal slot 34. This sample therefore does **not** show an additional epoch without bidding after discovery.
- This is an author-provided basic run, not an experiment independently executed by lodekeeper. It does not prove the exact on-chain activation instant, every fork/activation ordering, stale-head behavior, reconnect scenario or Sepolia case. No such broad claim is needed for approval.
- Marko explicitly calls it a basic run in `4331319624`, consistent with the bounded interpretation above.
- Nico's [6303722585](https://github.com/ChainSafe/lodestar/pull/10379#issuecomment-6303722585) directly quotes the pending-validation concern and says it can be tested separately and fixed in a follow-up if needed. That removes the earlier interpretation that exhaustive runtime confirmation must precede approval. Record this as an explicit scope/validation decision, not as evidence that untested cases passed.
- Head is unchanged. The parent's already completed 51/51 focused-test result remains applicable; current CI is reported as 22 successful checks and one skipped check. This QA pass neither reran those checks nor claims an independently executed runtime run.

## Draft review

The provided draft is substantively approved. Three small wording refinements improve precision:

1. Replace “bids from slot 34 onward” with “bids for slots 34-37” to keep the observation finite and distinguish proposal slots from the publication time.
2. Replace “no extra epoch of idle bidding” with “no extra epoch without bidding after discovery”; “idle bidding” is contradictory.
3. In the acknowledgment, explicitly include Nico's decision when saying the sign-off concern is cleared. This prevents the basic sample from sounding like proof of all activation cases.

“Current-head CI is green” is conventional and acceptable for 22 successes/one skip. The revised body below states the counts if exactness is preferred. Do not describe all 23 checks as passed.

The reply's `in_reply_to: 4330958984` correctly keeps the acknowledgment in Nico's original Kurtosis-request thread. `APPROVE` targets the exact reviewed commit. No duplicate metadata reminder, fresh feature request or silent closure of older implementation follow-ups is necessary.

## Suggested final public text

Approval:

> Approved at `8692572`. All 51 focused tests pass; current-head CI has 22 successful checks and one skip. Marko's basic run shows identity resolution at slot 33, bids for slots 34-37 and reveals for slots 34-36. Further activation testing can follow separately as Nico agreed; the existing implementation follow-ups remain unchanged.

Same-thread acknowledgment:

> Thanks, the basic run shows pending status through slot 32, active identity resolution at slot 33, bids for slots 34-37 and reveals for slots 34-36. There is no extra epoch without bidding after discovery in this sample. With Nico's agreement to handle further activation testing separately, that clears my remaining sign-off concern.

These statements are bounded to the supplied sample, preserve the explicitly deferred work, and contain no internal methodology narration. No source or GitHub mutations were performed by this reviewer.
