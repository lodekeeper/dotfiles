Reviewer: review-bugs
Reviewed commit: 0defe10a6788efe3f580eb31394523faac23cd0f

No findings.

Review notes:
- `describeDirectorySpecTest()` now fails `shouldError` cases that complete normally. `expect.unreachable()` is available in Vitest 4.0.7 and is placed outside the `try/catch`, so the intentional failure is not swallowed.
- The sanity block runner's slot precheck matches the consensus `process_slots` assertion (`state.slot < block.slot`) and only rejects same-slot or older-slot blocks that the spec state transition would reject.
- Forcing `verifyStateRoot: true` does not appear to reject valid sanity/random vectors: the generators set block `state_root` from the post-state, while BLS gating remains limited to proposer/signature checks.
- The builder and validator sweep OOB guards run after the per-loop withdrawal-limit break, matching the spec's order where the list index is only accessed after the limit check. They also keep the existing no-builders/no-loop behavior.
