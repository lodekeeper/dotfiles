# Review Findings — review-bugs — 10263

Reviewer: review-bugs
Reviewed commit: 2e9ac55d6dde395fceed1d4778f7939458471923
Generated at: 2026-10-05 09:09 UTC

## Findings

No functional bugs found.

## Verification

- Reviewed the entire supplied diff and surrounding builder utilities, fork onboarding, parent-payload processing, operation wrappers, and pinned spec references.
- Confirmed that the index is built after other execution requests and remains scoped to the deposit/exit batch; replacement removes the old pubkey mapping and registers the new one.
- Verified actual `@chainsafe/ssz` 1.8.0 progressive-list behavior: `getReadonly()` sees pending mutable views, and the constructor commits before `getAllReadonlyValues()`.
- Differential execution of unchanged PR processing bodies against a scan-based specification oracle passed 160,000 operations across 2,000 randomized per-block sequences, using real SSZ progressive-list views and both minimal/mainnet epoch lengths and withdrawal delays. Covered zero/nonzero top-ups, invalid deposits, candidate invalidation, index reuse, replaced-pubkey re-registration, exits, and interleaved commits.
- Signature-verification outcomes were controlled in that harness; BLS verification and the repository's unit/spec suites were not rerun. The read-only checkout was not modified.
