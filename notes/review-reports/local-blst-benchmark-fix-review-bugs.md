# Local BLST Benchmark Fix Review

Reviewer: review-bugs
Reviewed commit: 4546ac1229590e8558683421b7e079ddd129ee10 + working tree diff

## Scope

- `packages/state-transition/test/perf/block/util.ts`
- `packages/state-transition/test/perf/util/loadState/loadState.test.ts`

## Findings

No findings.

I found no concrete functional bugs in the changed code. The updated benchmark fixtures now use distinct interop pubkeys aligned with their validator indices, which matches the process-wide `lodestar-z` pubkey cache constraints that caused the reported benchmark failures.
