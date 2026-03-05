# Engine API SSZ transport — E2E validation log (2026-03-05)

## Scope
Validate negotiated SSZ-vs-JSON fallback behavior against live `bbusa/geth:ssz` and determine why positive SSZ REST responses are not observed.

## Environment
- EL container: `bbusa/geth:ssz`
- Running container: `geth-ssz-test`
- Geth version in container:
  - `Version: 1.17.1-unstable`
  - `Git Commit: a78e707e5f91e52a737042e324d74df436431eac`
  - `Git Commit Date: 20260303`

## What was validated

### 1) `engine_exchangeCapabilities` negotiation works (method-name list)
- Live geth returns `engine_*` method names from `engine_exchangeCapabilities`.
- Added CL-side mapping from `engine_*` method names to SSZ endpoint capabilities for transport selection compatibility.
- Covered by tests:
  - `packages/api/test/unit/client/engineSszMethodMap.test.ts`
  - `packages/api/test/unit/client/engineSszNegotiation.test.ts`

### 2) SSZ path attempt + JSON fallback works end-to-end
- Env-gated live test added:
  - `packages/beacon-node/test/unit/execution/engine/http.sszGethE2e.test.ts`
- With `ENGINE_SSZ_GETH_E2E=1`, test confirms:
  1. Negotiation derives support from real geth capability response.
  2. Client attempts SSZ REST path first for negotiated method.
  3. On unsupported status (404), client falls back to JSON-RPC and succeeds.
  4. If capability is not negotiated, client uses JSON-RPC directly.

### 3) Direct SSZ endpoint probing (curl)
Observed current live container responses:
- `POST /engine/v1/client/version` -> 404
- `POST /engine/v1/payloads/bodies/by-range` -> 404

## Root-cause investigation
Checked geth source at commit `a78e707e...`:
- `eth/catalyst/api.go` `ExchangeCapabilities` returns `engine_*` method names.
- No HTTP `/engine/v1/...` route handlers for SSZ binary endpoints were found in source at this commit.

### Conclusion
Current target (`bbusa/geth:ssz` at commit `a78e707e...`) supports JSON-RPC engine methods and method-name capability exchange, but does **not** expose active SSZ REST endpoints at the tested routes. Therefore, live positive-SSZ success-path assertions are blocked on EL implementation/image update.

## Current test status
- Targeted SSZ transport suite (default): **28/28 pass**
- Live env-gated geth e2e suite: **3/3 pass** with `ENGINE_SSZ_GETH_E2E=1`

## Next step
Once EL exposes active SSZ REST endpoints, add a positive live assertion (SSZ response success without JSON fallback) to `http.sszGethE2e.test.ts`.

### 4) Live fallback assertion tightened
- Updated env-gated e2e test `http.sszGethE2e.test.ts` to capture SSZ HTTP response status for `/engine/v1/client/version` and assert observed `404` before confirming JSON fallback success.
- Confirms fallback trigger is tied to live unsupported SSZ endpoint status, not just absence of SSZ call expectations.

### 5) Added second endpoint-specific live fallback assertion
- Extended env-gated e2e coverage to also validate fallback for `POST /engine/v1/payloads/bodies/by-range` via `engine_getPayloadBodiesByRangeV1`.
- Test now asserts: SSZ endpoint called, live SSZ status includes `404`, and JSON-RPC fallback method invocation succeeds.
- Live env-gated suite now: **4/4 passing** (`ENGINE_SSZ_GETH_E2E=1`).

### 6) 10:29 UTC rerun confirmation
- Re-ran env-gated live suite after adding second endpoint assertion.
- Command: `ENGINE_SSZ_GETH_E2E=1 pnpm vitest packages/beacon-node/test/unit/execution/engine/http.sszGethE2e.test.ts`
- Result: **4/4 pass**.

### 7) Added third endpoint-specific live fallback assertion
- Extended env-gated e2e coverage to also validate fallback for `POST /engine/v1/payloads/bodies/by-hash` via `engine_getPayloadBodiesByHashV1`.
- Test asserts: SSZ endpoint called, live SSZ status includes `404`, and JSON-RPC fallback method invocation succeeds.
- Live env-gated suite now: **5/5 passing** (`ENGINE_SSZ_GETH_E2E=1`).

### 8) Negotiation precondition tightened for live fallback e2e
- Updated negotiation test assertion to require mapped SSZ support for all currently validated fallback endpoints:
  - `POST /engine/v1/client/version`
  - `POST /engine/v1/payloads/bodies/by-range`
  - `POST /engine/v1/payloads/bodies/by-hash`
- Ensures endpoint fallback checks run only after confirming capability-derived endpoint negotiation is active for each covered path.

### 9) Positive live SSZ success assertion (legacy SSZ-REST target)
- Built and ran go-ethereum PR #33926 (`2e357729`) locally with SSZ-REST enabled:
  - `--authrpc.ssz-rest --authrpc.ssz-rest.port 11552`
- Added env-gated positive live assertion test:
  - `packages/beacon-node/test/unit/execution/engine/http.sszPositiveE2e.test.ts`
  - `ENGINE_SSZ_GETH_POSITIVE_E2E=1`
- Assertion verifies live SSZ REST success at `POST /engine/v1/get_client_version`:
  - HTTP status `200`
  - `Content-Type: application/octet-stream`
  - non-empty binary response body
- Evidence run: **1/1 passing**.

Note: this target currently uses legacy EIP-8161 route naming (`get_client_version`) rather than draft execution-apis route naming (`client/version`).

### 10) Draft-path EL target search result (hard blocker)
- Ran a focused target sweep for current draft route schema (`/engine/v1/client/version`, `/engine/v1/payloads/bodies/by-*`).
- Mainline images checked (`ethereum/client-go:stable`, `bbusa/geth:ssz`, `erigontech/erigon:latest`, `nethermind/nethermind:latest`, `ghcr.io/paradigmxyz/reth:latest`) did not yield a runnable draft-path SSZ REST target.
- Inspected active SSZ WIP implementations:
  - geth PR #33926 (`2e357729`) registers legacy `/engine/v1/get_*` route names.
  - erigon PR #19551 (`f1bba864`) also registers legacy `/engine/v1/get_*` route names.
- Detailed evidence: `notes/engine-api-ssz/DRAFT-PATH-TARGET-SEARCH-2026-03-05.md`.

Result: no compatible runnable EL target yet for draft-path positive negotiated assertion. Non-blocking because implementation falls back to JSON-RPC when SSZ endpoints are unsupported.
