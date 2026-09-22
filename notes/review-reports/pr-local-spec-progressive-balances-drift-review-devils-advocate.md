# Review Findings — review-devils-advocate — local-spec-progressive-balances-drift

Reviewer: review-devils-advocate
Reviewed commit: ee7c2aa8ee71d6869ecd2a5556d6b07b2a2440cb
Generated at: 2026-09-21 23:06 UTC

Reviewer: review-devils-advocate
Reviewed commit: ee7c2aa8ee71d6869ecd2a5556d6b07b2a2440cb

No findings.

The staged approach is sound for the stated goal. The direct STF runners in scope now create isolated state-transition metrics, pass them through the relevant transition paths, and assert `lodestar_stfn_progressive_balances_mismatches_total` remains zero after the attempted transition.

The local handling for expected-error finality, sanity, and transition vectors is also sound: it keeps the invalid-vector expectation inside `testFunction`, checks the metric after the attempted transition, and avoids the shared `shouldError` path swallowing assertion failures. A harness-level hook could reduce repetition, but it would be a broader change than needed here and less attractive for a focused PR follow-up.
