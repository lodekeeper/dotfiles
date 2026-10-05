# PR #10261 — Security review

Reviewer: review-security
Reviewed commit: 6d790d2845a530be1b96bac0eb5fa8a66b784b67

## No findings

No security vulnerabilities identified.

Reviewed all six changed files against the supplied security scope, using read-only PR source access. No must-fix, should-fix, or nit security findings.

## Security assessment

- `packages/beacon-node/src/api/impl/beacon/state/index.ts:103` changes only response filtering for already-resolved validator IDs. Validator status remains derived from beacon state; request strings do not influence consensus state, fork choice, signature verification, or validator signing. POST delegates to this same implementation at line 146.
- `packages/types/src/utils/validatorStatus.ts:96` performs exact membership checks against the derived fine-grained status and its existing group mapping. The mapping is not applied to attacker-supplied status strings. Unknown filter strings do not introduce a new mapping exception. The helper adds at most a second linear scan of the filter array, with no new allocation or change in asymptotic complexity; this is not a distinct new resource-exhaustion vulnerability.
- `packages/api/src/beacon/routes/beacon/state.ts:48` and the request type changes widen the TypeScript filter contract, not runtime authorization or schema acceptance. Response status remains fine-grained. Group filtering exposes only validator information already available through this public beacon API, not confidential data.
- The added tests cover the motivating active-group case, exact-status matching, exclusion, other groups, and all nine fine-grained group members. No networking, SSZ limits, keymanager authentication, secrets, or peer trust decisions are changed.

## Contributor and verification assessment

The supplied motivation matches the narrow implementation, and the regression tests are relevant. Cursor assistance and the missing linked issue are not evidence of a security defect or grounds to close this focused fix. The small helper and additive request type do not impose substantial security maintenance cost.

This was a source review; no tests, lint, or type checks were executed, and the repository was not modified. The supplied metadata states that external-contributor CI has not run those checks. Obtain passing approved CI before merging; this is a verification gate, not a source-level security finding.

MERGE AFTER CHANGES — obtain passing tests/lint/type checks from approved CI; the fix is narrowly scoped and no security regression was identified.
