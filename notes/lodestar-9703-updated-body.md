## Problem

The `Publish` workflow has been failing on every dev publish since 2026-07-23 with:

```
lerna-lite ERR! TLOG_CREATE_ENTRY_ERROR error creating tlog entry - (409) an equivalent entry already exists in the transparency log with UUID ...
```

Failed across 4+ consecutive commits (#9670, #9699, #9606, #9697) -- no dev release has published since.

## Root cause

npm provenance uploads a signed entry to the Sigstore Rekor transparency log via `@sigstore/sign` (pulled in through `lerna-lite -> libnpmpublish -> sigstore`). In each failed run the Rekor entry was actually **created successfully** (every run shows a *different* UUID), then the client retried the POST and the retry came back `409 (equivalent entry already exists)` -- i.e. **retry-after-success**: Rekor appears to have become slow/flaky, tripping `make-fetch-happen`'s retry.

`@sigstore/sign`'s `TLogClient` already handles this -- on a 409 it can fetch the existing entry instead of erroring -- but only when `fetchOnConflict: true`. The current default is `false`, so the 409 becomes a fatal `TLOG_CREATE_ENTRY_ERROR`. This is identical at every reachable version (`4.0.0`, `4.1.1`, and `main`/`5.x`), so bumping `lerna-lite`/`sigstore` does **not** change the behavior.

## Fix

`pnpm patch sigstore` to flip that flag:

```diff
   new RekorWitness({
     rekorBaseURL: options.rekorURL,
-    fetchOnConflict: false,
+    fetchOnConflict: true,
     retry: options.retry ?? DEFAULT_RETRY,
     timeout: options.timeout ?? DEFAULT_TIMEOUT,
   })
```

On a 409 the client now fetches the already-created entry and the publish proceeds. Provenance is preserved and the attestation is unchanged -- it is the exact entry Rekor already recorded.

## Upstream

Opened upstream sigstore-js tracking and fix:

- Issue: https://github.com/sigstore/sigstore-js/issues/1708
- PR: https://github.com/sigstore/sigstore-js/pull/1709

Similar downstream reports:

- SocialGouv/code-du-travail-numerique#7419
- apify/apify-shared-js#649

## Alternatives considered

- **Bump `lerna-lite`/`sigstore`** -- no effect; `fetchOnConflict: false` is still the default upstream.
- **Disable provenance on dev** -- drops supply-chain provenance; rejected.
- **Re-run the job** -- unreliable while Rekor is returning 409s.
- **Increase timeout** -- may reduce timeout-triggered retries, but does not make the Rekor create-entry operation idempotent across 5xx/429/retry-after-success cases.

## Notes

- First `patchedDependencies` entry in the repo.
- This PR can be reverted once sigstore-js ships the upstream default change and npm/libnpmpublish consumes it.

🤖 Generated with AI assistance
