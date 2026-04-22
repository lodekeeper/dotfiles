# Codex CLI review — produceBlockV3 Gloas withdrawals regression

Validity: mixed  
Main risk: The test proves the branch chooses `getPayloadExpectedWithdrawals()` in a forced Gloas empty-parent setup, but it can still pass even if real Gloas `payloadExpectedWithdrawals` plumbing is broken.  
Best improvement: Use a minimal real `CachedBeaconStateGloas` fixture and stop mocking `getPayloadExpectedWithdrawals()` / `getExpectedWithdrawals()` so the assertion covers actual stale-field provenance.

Notes:
- It does hit the right seam: `produceBlockBody()` reaches `notifyForkchoiceUpdate()` and the asserted `withdrawals` value is taken from the Gloas empty-parent path, not the fresh-withdrawals path.
- It does not fully prove "stale `state.payloadExpectedWithdrawals`" as stated, because `getPayloadExpectedWithdrawals()` itself is mocked; that only proves method selection over `getExpectedWithdrawals()`.
- The main false-positive / over-mocking risk is the Electra-backed `BeaconStateView` with patched `forkName`, `latestBlockHash`, and `latestExecutionPayloadBid`, which bypasses real Gloas state invariants.
