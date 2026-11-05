# PR #9957 — Security review

Reviewer: review-security
Reviewed commit: 258d7d1ca8e6f170adc0c8c9330c07e1fd8a19c0

## Findings

No security vulnerabilities identified.

No concrete security regression was identified for current post-Fulu operation or the Gloas payload-envelope/data-column paths. Intended removal of pre-Fulu blob-sidecar support is excluded from findings.

## Review coverage

- Checked block-input fork classification and data-availability status changes: Fulu still uses `BlockInputColumns`; Gloas still uses `BlockInputNoData`, with payload data tracked separately. The new legacy `NotRequired` result does not replace the Fulu column-availability check.
- Checked execution verification: Fulu versioned hashes are still derived from the block's KZG commitments; Gloas exits the block-payload verification path before that access and retains separate envelope processing.
- Checked range/by-root sync changes, including column validation, Gloas envelope validation, parent-payload handling, and partial-download retries. Removed validation branches applied to legacy blob sidecars, not current data columns.
- Checked engine fetch dispatch and remaining callers: Fulu column inputs and Gloas `PayloadEnvelopeInput` still reach `getBlobsV2` and the existing column reconstruction path.
- Checked removed gossip/reqresp facilities and surviving references for dependencies from supported fork paths. Existing column protocol quotas and peer-penalty handling remain in place. Fulu REST blob reconstruction remains independent of the removed legacy sidecar cache.

Static inspection only. No source changes, package-manager commands, builds, or tests were run, as instructed; supplied CI results were treated as context, not independently reproduced.
