# Security Review — Lodestar PR #10487

Reviewer: review-security
Reviewed commit: 50c3e241815ffcd1b3f1359936edfd42557b9650

## Scope

- `packages/api/src/beacon/routes/lodestar.ts`
- `packages/api/test/unit/beacon/genericServerTest/lodestar.test.ts`

## No findings

No security vulnerabilities identified.

The production change corrects the historical-summaries response schema to encode Merkle proof nodes as 32-byte values, matching the documented server output. It changes neither request parsing nor authentication, consensus validation, proof verification, or proof-list bounds. The test changes exercise nonempty proof nodes through JSON and SSZ response decoding and introduce no production attack surface.

## Verification

Reviewed the supplied diff and both complete changed files at `origin/pr-10487`; verified that the ref resolves to the reviewed commit above. Static review only; no checkout or pnpm commands were run.
