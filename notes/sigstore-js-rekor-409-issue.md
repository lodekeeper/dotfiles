## Summary

npm provenance publishing can fail with:

```text
TLOG_CREATE_ENTRY_ERROR error creating tlog entry - (409) an equivalent entry already exists in the transparency log
```

This appears to be a retry-after-success path. Rekor accepts and commits the create-entry request, but the client times out, receives a transient network failure, or retries after a retryable response. The retry submits the same equivalent entry, Rekor correctly returns 409, and the signing flow treats that as fatal.

## Current behavior

`TLogClient` defaults `fetchOnConflict` to `false`:

```ts
this.fetchOnConflict = options.fetchOnConflict ?? false;
```

High-level `sigstore.attest()` / npm provenance callers usually do not set this option directly, so a 409 from an already-created Rekor entry becomes `TLOG_CREATE_ENTRY_ERROR` instead of using the existing recovery path.

## Expected behavior

When Rekor returns a 409 with a location for an equivalent existing entry, the default behavior should fetch the existing entry and continue. The existing entry is the entry the client needs in the Sigstore bundle, so this makes the create-entry operation idempotent from the caller's perspective while preserving provenance.

Callers that need fatal conflict behavior can still pass `fetchOnConflict: false` explicitly.

## Downstream reports

Similar downstream failures and analyses:

- SocialGouv/code-du-travail-numerique#7419: https://github.com/SocialGouv/code-du-travail-numerique/issues/7419
- apify/apify-shared-js#649: https://github.com/apify/apify-shared-js/issues/649
- ChainSafe/lodestar#9703: https://github.com/ChainSafe/lodestar/pull/9703

## Proposed fix

Default `TLogClient` to `fetchOnConflict: true`, while preserving explicit `fetchOnConflict: false` for callers that want conflicts to remain fatal.
