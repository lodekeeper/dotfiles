> hmm shouldn't we enforce this rule just for safety reasons, maybe this PR isn't ideal?

There's no real safety reason either way. My caveat overstated the risk. I checked with biome 2.6.3 and tsc:

- The rule skips bigint literals and anything annotated as `bigint`: parameters, locals and type aliases. It still flags bigint values whose type is only inferred, like `block.value > bid.value ? block.value : bid.value` or `const a = getValue()`.
- Applying the fix there doesn't make it to runtime. `Math.max(a, b)` with bigint arguments fails `check-types` with TS2345, so CI catches it. Only an `any`-typed value would throw.
- The fix is unsafe, so `lint:fix` never applies it by itself.

So the cost of this PR is an occasional false-positive warning on a bigint ternary outside state-transition, which needs a `biome-ignore`. That's not a correctness risk. I'm fine merging it as is. Keeping the rule off is also reasonable if those false positives aren't worth the consistency.
