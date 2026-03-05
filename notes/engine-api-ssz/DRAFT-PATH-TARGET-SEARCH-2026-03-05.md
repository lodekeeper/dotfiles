# Draft-path EL target search — 2026-03-05

## Goal
Find an EL target that serves current draft SSZ REST paths used by Lodestar transport mapping:
- `/engine/v1/client/version`
- `/engine/v1/payloads/bodies/by-range`
- `/engine/v1/payloads/bodies/by-hash`

## Evidence gathered

### 1) Mainline EL images currently expose JSON Engine API, not draft SSZ REST paths
Command:
```bash
for img in ethereum/client-go:stable bbusa/geth:ssz ; do
  docker run --rm $img geth --help | grep -i 'ssz\|authrpc\.ssz' || echo '(no ssz flags)'
done
```
Result:
- `ethereum/client-go:stable`: `(no ssz flags)`
- `bbusa/geth:ssz`: `(no ssz flags)`

Additional help scans:
- `erigontech/erigon:latest`: shows `--authrpc.*` JSON Engine API flags, no SSZ REST flag.
- `nethermind/nethermind:latest`: JSON Engine API options only.
- `ghcr.io/paradigmxyz/reth:latest`: auth Engine API options only.

### 2) geth SSZ PR target (already validated) uses legacy EIP-8161 route names
Target:
- `ethereum/go-ethereum` PR #33926, head `2e357729a3b0d69d2501b8cfaad9478cbfdcdadf`

Source route registration (`eth/catalyst/ssz_rest.go`):
- `POST /engine/v1/get_client_version`
- `POST /engine/v1/get_payload`
- `POST /engine/v1/get_blobs`
- `POST /engine/v1/get_payload_bodies_by_*`-style legacy naming

Not present there:
- `/engine/v1/client/version`
- `/engine/v1/payloads/bodies/by-*`

Runtime behavior already confirmed in env-gated tests:
- draft paths return `404` on currently available bbusa/geth target.
- legacy geth PR endpoint `/engine/v1/get_client_version` returns `200` + binary body.

### 3) Other active EL WIP SSZ PR also uses legacy route names
Target:
- `erigontech/erigon` PR #19551 (`[WIP] SSZ-REST Engine API transport Big Secret`), head `f1bba864e9bbd0660f2d9cfb296950b2d08d9162`

File inspected:
- `execution/engineapi/engine_ssz_rest_server.go`

Registered routes include:
- `POST /engine/v1/get_client_version`
- `POST /engine/v1/get_payload`
- `POST /engine/v1/get_blobs`

No draft-path route registrations found for:
- `/engine/v1/client/version`
- `/engine/v1/payloads/bodies/by-range`
- `/engine/v1/payloads/bodies/by-hash`

### 4) GitHub code-search signal
Global code-search hits for exact draft route strings are currently documentation/spec repositories (not EL runtime server handlers), e.g. `wemeetagain/engine-rest-api` OpenAPI/spec docs.

## Conclusion
As of 2026-03-05, there is **no identified runnable EL target** with active handlers for the current draft SSZ REST route schema used by Lodestar (`client/version`, `payloads/bodies/by-*`).

## Hard blocker
Cannot yet add a **positive negotiated live success assertion on current draft routes** against a real EL implementation, because no compatible EL target is currently available.

## Recommended next step
Track upstream EL implementations for draft-route adoption (geth/erigon/reth/nethermind). Once one exists, add an env-gated live negotiated-success test that exercises `ExecutionEngineHttp.fetchWithSelectedTransport()` over draft routes without fallback.
