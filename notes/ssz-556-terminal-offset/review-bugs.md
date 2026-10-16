# Independent bug review — SSZ #556 terminal offsets

Verdict: approved; no blocking findings in the tracked source diff, new `offsets.test.ts`, or draft `reply.md`.

- The strict `size < 2 ** 32` threshold is correct: max Uint32 stays on the ordinary path, while the threshold itself and larger sizes preserve the numeric sentinel in Float64 storage. Relative offsets are still added to `start` exactly once.
- Both fixed and variable readers are covered; empty variable arrays retain their zero sentinel. Existing divisibility, first-offset bounds, monotonicity, and array-length validation ordering is unchanged.
- The 12-case regression matrix directly observes child decode boundaries across value/tree, fixed/variable, and threshold-adjacent sizes with nonzero start. The small backing buffer and mocked decoder are intentional dispatch-level tests, not claims of successful physical GiB deserialization. Tree construction is legitimate for the one-element depth-zero setup.
- Normal inputs retain Uint32 storage and the branchless decode loops. The extra allocation branch is per input, not per element. Float64 doubles offset-table memory only for giant inputs; no benchmark claim is made for the union's JIT effects.
- The response accurately distinguishes preserving library behavior from spec-valid giant SSZ. No corrections requested.

Scope: static independent review; parent owns execution gates and the reported negative-control/186-test results. No source edits, commits, pushes, or posts performed.
