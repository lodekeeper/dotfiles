# PR #10815 functional bug review

Reviewer: review-bugs
Reviewed commit: cfb9261cabd2f332aba0f13a5885b7bd709538a3

## Finding 1: Clock disparity advances validator eligibility before the epoch boundary

1. **File:Line**: `packages/beacon-node/src/chain/validation/voluntaryExit.ts:105` (the epoch argument on line 106).
2. **Bug**: The new state regeneration applies the gossip clock allowance to every state-based exit condition, not only the exit message's future-epoch check. During the last 500 ms of epoch 300, `currentSlotWithGossipDisparity` belongs to epoch 301, so this call advances the state to epoch 301. A validator activated at epoch 45 has only 255 completed epochs of activity in the head state and fails `SHARD_COMMITTEE_PERIOD = 256`, but `getVoluntaryExitValidity()` evaluates the advanced state's epoch and returns `valid`. The phase0 and Electra gossip specifications apply `is_future_epoch()` to the message epoch separately and evaluate validator activity duration against the head state. The native Zig implementation also evaluates the activity-duration condition using the supplied state's epoch, so the default native runtime has the same incorrect acceptance.
3. **Impact**: A correctly signed exit for a validator that reaches its minimum active duration at epoch 301 is accepted and forwarded 500 ms before that epoch, while specification-conforming peers reject it as not active long enough.
4. **Fix**: Separate the message's future-epoch check from validator-state checks. Use `currentSlotWithGossipDisparity` only to decide whether the message epoch is in the future, and evaluate activity and minimum active duration against the head state as specified. Do not advance validator eligibility into the next epoch to implement the clock allowance.

### Verification

Executed the PR's gossip-validation function, its actual TypeScript validity helper, and the actual `getHeadStateAtEpoch()` implementation extracted read-only from Git. State regeneration and successful BLS verification were supplied by test doubles. Inputs: head/current epoch 300, validator activation epoch 45, no initiated exit, message epoch 300, and time exactly 500 ms before epoch 301. Results:

- `origin/unstable`: `REJECT:short_time_active`
- Reviewed PR: `ACCEPT`
- Specified head-state check: `REJECT:short_time_active`

Confirmed the matching native activity-duration comparison in `src/state_transition/block/process_voluntary_exit.zig` at lines 91-94. No repository files were modified.
