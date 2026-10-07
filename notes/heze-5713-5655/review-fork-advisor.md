# Explicit fork argument review

Reviewed base: c822cc7315a
Working diff: one-file explicit fork argument, packages/state-transition/src/epoch/processPendingDeposits.ts

Verdict: Approved. No required corrections.

Both callers pass the fork already computed at entry, covering withdrawn-validator deposits and normal churn-consuming deposits. The private helper takes fork: ForkSeq first, matching nearby applyDeposit/addValidatorToRegistry conventions. Its Heze guard is equivalent: state.slot does not change during pending-deposit processing, and reordering the pure fork/credential checks does not alter outcomes. Fork-boundary semantics and the public signature remain unchanged. No public caller/spec-runner integration changes are needed for sibling PR #10293.

The intended GitHub reply accurately describes the diff and is approved provided the stated focused deposit tests, six upstream Heze cases, lint, types, and build have actually passed before posting. This reviewer inspected code only and did not independently run those gates.
