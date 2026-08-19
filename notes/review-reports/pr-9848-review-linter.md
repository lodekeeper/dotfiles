# Review Findings — review-linter — 9848

Reviewer: review-linter
Reviewed commit: 44d7e415adeb57f2e3d2983a1c596e380296f0b2
Generated at: 2026-08-18 23:09 UTC

Reviewer: review-linter
Reviewed commit: 44d7e415adeb57f2e3d2983a1c596e380296f0b2

Findings:

- packages/builder/src/metrics.ts:32 - The new TypeScript metric property `builderBalanceGwei` includes the unit suffix, and callers use it at packages/builder/src/services/builderStatusTracker.ts:41. Lodestar's metrics convention is to put units in Prometheus metric names, not TypeScript property names. The Prometheus name `bc_balance_gwei` is the right place for the unit; the code property should be unitless, e.g. `builderBalance`, matching the validator convention where properties like `requestTime` map to names like `vc_rest_api_client_request_time_seconds`.

Notes:

- Scope limited to the requested changed files.
- I compared the new builder metrics against `packages/validator/src/metrics.ts` conventions.
