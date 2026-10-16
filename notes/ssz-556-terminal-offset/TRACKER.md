# SSZ #556 terminal offset review

- Source: bot inline4295698907, routed2026-10-16T14:27Z, PR8ac6df0.
- Verified new terminal slot truncates2^32 to0. Node24 buffer maximum supports the relevant library path. Actual SSZ spec serializer has total-size<2^32 assertion for fixed and variable arrays alike; do not call giant outer arrays spec-valid.
- Approach: keep Uint32 for size<2^32, Float64 only for larger ranges. Preserve private n+1 contract, empty sentinel, validation ordering and branchless consumers. No wire-format/public API changes.
- Gates passed: SSZ package build/type-check, root lint,186 focused tests/6files.12 boundary dispatch cases cover fixed/variable/value/tree and maxuint32/2^32/+1 with start8. Tiny buffers/stub children avoid GiB allocation. Original-head negative control8failed/4passed.
- Resolved initial format issues and missing unbuilt persistent-ts in dedicated worktree. Main checkout source/branch and untracked benchmarks untouched, no installs.
- Both independent exact-diff/response reviews approve. Reports review-advisor.md,review-bugs.md. Benchmark ordinary path compared to8ac6df0; repeat pending because initial tree delta merits checking, not a no-regression claim.
- Pending: signed incremental push to same branch, update misleading original PR paragraph, in-thread reply, final backlog/checklist/notification state.
- Spec compliance: N/A (internal numeric range handling only; SSZ wire format and serialized offsets unchanged).
