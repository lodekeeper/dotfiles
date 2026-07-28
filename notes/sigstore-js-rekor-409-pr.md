## Summary

- default `TLogClient` to fetching existing Rekor entries on 409 conflicts
- keep explicit `fetchOnConflict: false` behavior unchanged
- add coverage for the default 409 recovery path

## Context

This fixes a retry-after-success failure mode seen by npm provenance publishers. If Rekor commits a create-entry request but the client retries after a timeout or transient retryable failure, the retry receives `409 an equivalent entry already exists`. The client already has recovery logic for that condition, but the default was `fetchOnConflict: false`, so high-level callers such as npm provenance publishing treated the benign duplicate as a fatal `TLOG_CREATE_ENTRY_ERROR`.

Related downstream reports:

- Closes sigstore/sigstore-js#1708
- SocialGouv/code-du-travail-numerique#7419
- apify/apify-shared-js#649
- ChainSafe/lodestar#9703

## Verification

- `npm run build`
- `npm test --workspace @sigstore/sign -- witness/tlog/client.test.ts`
- `npm run lint:check -- --quiet`

Generated with AI assistance.
