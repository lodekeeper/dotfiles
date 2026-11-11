**Motivation**

`submitBlindedBlock` and `submitBlindedBlockV2` set `retries: 2` with the 12s builder timeout. An attempt that times out already ends after the proposal slot, so the retries can only resend the block once it can no longer be timely. See the discussion on #10526.

**Description**

- Cap each submit attempt at the time left in the block's slot. A deadline signal stops retries at the slot end. Fast failures (5xx, connection errors) are still retried while there is time left
- When the deadline hits, throw a `TimeoutError` that names the slot. Before, it surfaced as `ErrorAborted`, which the REST error handler doesn't log
- Pass the clock to `ExecutionBuilderHttp` for this

Until #10526 lands, an attempt that starts after a fast failure isn't tied to the deadline signal yet and can still run up to its own timeout. With #10526, every attempt is cut off at the slot end.

**AI Assistance Disclosure**

Written with AI assistance (Claude), including the implementation, tests and description.

