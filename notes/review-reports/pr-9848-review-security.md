# Security Review — PR #9848

Reviewer: review-security
Reviewed commit: 18399dae1b828ecf43f5408c8741a1a9743c9a1b
Generated at: 2026-08-18 23:18 UTC

## Findings

No security vulnerabilities identified in the reviewed diff.

## Scope

Reviewed only the requested files:

- `packages/builder/src/builder.ts`
- `packages/builder/src/metrics.ts`
- `packages/builder/src/services/builderStatusTracker.ts`
- `packages/builder/test/unit/services/builderStatusTracker.test.ts`
- `packages/cli/src/cmds/builder/handler.ts`
- `packages/cli/src/cmds/builder/options.ts`

Security focus areas checked: metrics HTTP server enablement and bind defaults, unauthenticated metrics exposure risk, information disclosure through metric labels, sensitive URL handling, label-cardinality DoS risk, and builder status/balance exposure.

Notes:

- Builder metrics remain opt-in via `--metrics`; when enabled without explicit overrides, the new CLI code falls back to `127.0.0.1:5065`.
- The REST client `baseUrl` metric labels are populated by the existing `HttpClient` `printableUrl` value, which uses `toPrintableUrl()` and reduces URLs to origin only, stripping userinfo, path, and query data.
- Metric labels added here are bounded by local config/static route IDs rather than remote beacon-node responses, so I did not find a new untrusted-cardinality path.
