# Review Findings — review-security — 10263

Reviewer: review-security
Reviewed commit: 2e9ac55d6dde395fceed1d4778f7939458471923
Generated at: 2026-10-05 09:08 UTC

## No findings

No security vulnerabilities identified.

Reviewed the supplied full PR diff and surrounding builder processing code against the pinned consensus specification. The block-scoped pubkey map preserves signature gating for new registrations and address authorization for exits. Replaced pubkeys are removed before later lookups, reusable indices retain ascending selection order, and candidates invalidated by top-ups are checked against the latest SSZ mutable view. No verified validation bypass, state-root divergence, or material new denial-of-service vulnerability was found in the changed files.

Verification: 500 deterministic adversarial deposit/exit sequences passed 19,718 per-operation state-root and pubkey-index comparisons against an independent specification model. This exercised the actual PR-head indexed state, deposit/exit processors, and builder helper implementations using @chainsafe/ssz 1.8.0 TreeViewDU. Scenarios included zero/nonzero top-ups, rejected credentials and signatures, index reuse, replaced pubkeys, unauthorized exits, inactive builders, and pending withdrawals. Cryptographic verification results were stubbed solely to exercise the unchanged signature-gating branches; this was not a cryptographic implementation test. The standard Vitest suite was not rerun because the read-only PR checkout has no installed dependencies.

The PR checkout was not modified.
