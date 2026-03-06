# Engine API SSZ transport — EL target validation matrix (2026-03-05)

Goal: find an EL image/revision with active SSZ REST endpoints for positive live-SSZ success-path assertions.

## Common test setup
- authrpc enabled on mapped port
- JWT auth via `/tmp/geth-jwt.hex`
- Probed endpoints:
  - `POST /engine/v1/client/version`
  - `POST /engine/v1/payloads/bodies/by-range`
  - `POST /engine/v1/payloads/bodies/by-hash`
- Negotiation probe:
  - JSON-RPC `engine_exchangeCapabilities` with SSZ endpoint capability strings

## Results

| Image | engine_exchangeCapabilities | SSZ REST endpoint result | Verdict |
|---|---|---|---|
| `bbusa/geth:ssz` | returns `engine_*` method names | all tested endpoints return `404` | ❌ no positive SSZ path |
| `bbusa/geth:grpc-otel` | returns `engine_*` method names | all tested endpoints return `404` | ❌ no positive SSZ path |
| `ethereum/client-go:stable` | returns `engine_*` method names | all tested endpoints return `404` | ❌ no positive SSZ path |
| `go-ethereum` PR #33926 local build (`2e357729`) with `--authrpc.ssz-rest` | serves active SSZ REST on port 11552 | `POST /engine/v1/get_client_version` returns `200` + binary body | ✅ positive live SSZ path (legacy endpoint schema) |

## Conclusion
All currently tested EL image candidates expose JSON-RPC Engine API methods and capability exchange, but none serve active SSZ REST endpoints at the tested routes.

## Next action
- Acquire/build an EL image revision that actually wires SSZ REST routes.
- Once available, extend `http.sszGethE2e.test.ts` with at least one positive SSZ-success assertion (no JSON fallback call for that endpoint).
