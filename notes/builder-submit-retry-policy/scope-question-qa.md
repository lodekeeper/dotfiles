# Scope-question QA

Good concise question: it isolates a real product ambiguity without asserting late responses are useless. The configured first-attempt timeout proposal is clearly a preference, not a settled requirement. No need to mention abandoned draft/test environment in the public question.

One wording change recommended before posting: “I’ll keep this separate from #10526’s signal fix” can imply the proposed strict retry budget is independently enforceable on unstable. It is not, due to SSZ→JSON fallback signal leakage even with retries0. Say “I’ll keep the policy change focused on the submit calls; enforcing a shared cancellation deadline will depend on #10526’s signal fix.” This distinguishes scope separation from independence.

Suggested final draft:

> One policy detail before I change the submit path: should slot end abort an in-flight submission, or only prevent starting further retries? A late successful response can still be useful, especially when reconstructing the legacy full block. I lean toward preserving the first attempt’s configured timeout, while allowing at most two retries only within the signed block’s slot and bounding those retries by the remaining budget.
>
> I found no competing PR. I’ll keep this focused on the submit calls, with no changes to `getHeader` or the post-Gloas builder API. Enforcing a shared cancellation deadline will depend on #10526’s signal fix.

“Within the signed block’s slot” correctly excludes future-slot retries too; implementation must either explicitly restrict retries to start-of-slot through end-of-slot or use “before the signed block’s slot ends” if only an upper bound is intended. For ordinary valid submissions the distinction does not matter. No additional question is needed now.
