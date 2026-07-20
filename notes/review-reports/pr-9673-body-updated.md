## Summary

Fixes #9672.

`GET /eth/v1/beacon/states/{state_id}/validators` (and `.../validator_balances`) returns `400 id must be array` when a validator client sends more than 20 ids as a comma-separated list (`?id=a,b,c,...`). This regressed in v1.44.0 and breaks interop with clients that use comma-separated `id` encoding, notably the Nimbus validator client.

## Root cause

The REST query string is parsed with `qs` using `comma: true` but no explicit `arrayLimit`, so it defaulted to **20**. v1.44.0 bumped `qs` `6.14.1 -> 6.15.2` (#9399), which enforces `arrayLimit` on comma-parsed values: once a comma-separated (or repeated) array exceeds the limit, `qs` converts it into an object (`{0: ..., 1: ...}`), which then fails Ajv `type: "array"` validation and surfaces as `id must be array`. The default cap also applies to the repeated form (`?id=1&id=2&...`).

## Fix

Raise `arrayLimit` to `NUMBER_OF_COLUMNS` (128), the largest array any beacon-API query param can carry -- a full data-column custody set on `getDebugDataColumnSidecars` (`indices`); the validator `id` lists are capped at 64 by the spec. The route schemas set no per-request `maxItems`, so the qs `arrayLimit` is the only cap on query-array length. This is not a DoS boundary (`parseArrays: false` already disables index-based sparse arrays, and the URL/header size limits bound total input), so a single generous global cap is safe.

Also raise the declared `qs` floor to `^6.14.2` in `@lodestar/api` and `@lodestar/beacon-node`, because `arrayLimit` is only enforced for comma-parsed values starting in `qs` 6.14.2. The lockfile already resolves to 6.15.2, so this pins the behavior the fix relies on for consumers that install from the semver range.

The `@lodestar/api` test-server helper (`getTestServer`) mirrors this `arrayLimit` so it stays in parity with the real server.

Generated with AI assistance
