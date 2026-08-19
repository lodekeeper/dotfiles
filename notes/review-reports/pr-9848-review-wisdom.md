Reviewer: review-wisdom
Reviewed commit: 18399dae1b828ecf43f5408c8741a1a9743c9a1b

# PR #9848 Maintainability Review

Scope: maintainability/readability/clean-code review only, limited to:
- `packages/builder/src/builder.ts`
- `packages/builder/src/metrics.ts`
- `packages/builder/src/services/builderStatusTracker.ts`
- `packages/builder/test/unit/services/builderStatusTracker.test.ts`
- `packages/cli/src/cmds/builder/handler.ts`
- `packages/cli/src/cmds/builder/options.ts`

## Findings

No maintainability/readability findings.

The changes are small and follow existing Lodestar patterns closely: the builder metrics shape mirrors validator metrics, the CLI metrics setup follows the validator handler's flow, and the status tracker keeps the metrics write near the state/log update it represents. I did not see a clean-code issue substantial enough to raise under the requested review criteria.

## Notes

I did not run tests for this readability-only pass.
