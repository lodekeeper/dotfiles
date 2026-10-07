# Fork forwarding bug review

Reviewer: review-bugs
Reviewed base: c822cc7315a (working one-file diff)
Scope: packages/state-transition/src/epoch/processPendingDeposits.ts

No functional bugs found. Approved.

Both applyPendingDeposit callers pass the fork computed from state.config.getForkSeq(state.slot) at the start of processPendingDeposits. No intervening operation changes state.slot or fork configuration, so the forwarded value matches the replaced lookup. The reordered conjunction preserves the Heze BLS-credential rejection, and existing-validator top-ups remain outside that guard.
