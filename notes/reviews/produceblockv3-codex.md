# Verdict
- Validity: no
- Main risk: The test can fail for harness/setup reasons instead of proving the stale-vs-fresh withdrawals behavior, so it does not reliably guard the regression.
- Best improvement: Build a real CachedBeaconStateGloas (or upgrade a Fulu state), seed `payloadExpectedWithdrawals`, and mock/spyon the module-level `getExpectedWithdrawals()` call instead of nonexistent state methods.

# Notes
This targets the right scenario, but the patch does not line up with Lodestar’s current APIs/control flow. `BeaconStateView` is neither imported nor present in this repo, `generateCachedElectraState()` already returns a cached state, `getPayloadExpectedWithdrawals` is not a state method, and `getExpectedWithdrawals` is a free function, so the spies are attached to the wrong objects. More importantly, `produceBlockBody()` branches on `this.config.getForkName(slot)`: with `GLOAS_FORK_EPOCH: 0` it enters the post-Gloas path that skips `executionEngine.notifyForkchoiceUpdate()` entirely, so the asserted fcU call does not actually prove the empty-parent stale-withdrawals rule. Use a real Gloas state plus the exact branch that still performs fcU in the empty-parent case, then assert stale withdrawals are forwarded and fresh recomputation is not.
