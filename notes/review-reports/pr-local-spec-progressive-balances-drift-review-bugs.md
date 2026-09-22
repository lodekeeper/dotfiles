# Review Findings — review-bugs — local-spec-progressive-balances-drift

Reviewer: review-bugs
Reviewed commit: ee7c2aa8ee71d6869ecd2a5556d6b07b2a2440cb
Generated at: 2026-09-21 23:05 UTC

# Review Report: local-spec-progressive-balances-drift

Reviewer: review-bugs
Reviewed commit: ee7c2aa8ee71d6869ecd2a5556d6b07b2a2440cb

## Findings

No findings.

I reviewed the staged diff only for the listed files. The previous expected-error gap is addressed by moving finality, sanity, and transition expected failures out of shared `shouldError` and checking `lodestar_stfn_progressive_balances_mismatches_total` after the attempted transition.
