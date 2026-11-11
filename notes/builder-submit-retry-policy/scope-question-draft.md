One policy detail before I change the submit path: should slot end abort an in-flight submission, or only prevent starting further retries? A late successful response can still be useful, especially when reconstructing the legacy full block. I lean toward preserving the first attempt’s configured timeout, while allowing at most two retries only within the signed block’s slot and bounding those retries by the remaining budget.

I found no competing PR. Enforcing a shared cancellation deadline will depend on #10526’s signal fix. I won’t change `getHeader` or the post-Gloas builder API.
