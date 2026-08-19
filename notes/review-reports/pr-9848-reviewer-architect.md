# Review Findings - reviewer-architect - PR #9848

Reviewer: reviewer-architect
Reviewed commit: 18399dae1b828ecf43f5408c8741a1a9743c9a1b
Generated at: 2026-08-18 23:16 UTC

Scope: Architecture/package-boundary review only. Reviewed only the requested files:
`packages/builder/src/builder.ts`, `packages/builder/src/metrics.ts`,
`packages/builder/src/services/builderStatusTracker.ts`,
`packages/builder/test/unit/services/builderStatusTracker.test.ts`,
`packages/cli/src/cmds/builder/handler.ts`, and
`packages/cli/src/cmds/builder/options.ts`.

## Findings

1. `packages/builder/src/builder.ts:29` - `BuilderOptions` is exported from `@lodestar/builder`, and the PR makes `metrics` a required field even though metrics are optional instrumentation. That leaks the CLI/observability concern into every programmatic builder initialization and creates an unnecessary public API break: existing callers now have to pass `metrics: null` just to preserve old behavior. The validator package keeps this boundary cleaner by accepting metrics as a separate optional/defaulted argument (`Validator.init(..., metrics = null)` / `initializeFromBeaconNode(..., metrics?)`) rather than making it part of `ValidatorOptions`. Consider changing this to `metrics?: Metrics | null` and normalizing with `opts.metrics ?? null` when constructing `BuilderStatusTracker`; optionally default the tracker constructor parameter too.

## Notes

- I did not flag the builder CLI import from `@lodestar/beacon-node` as a current PR issue. `packages/cli` already depends on `@lodestar/beacon-node`, and validator/bootnode handlers already use the same exported metrics utilities (`RegistryMetricCreator`, `collectNodeJSMetrics`, `getHttpMetricsServer`). This PR does not add a direct `@lodestar/builder` -> `@lodestar/beacon-node` dependency.
- Keeping HTTP metrics server setup in the CLI matches the existing validator/bootnode command pattern: the command owns process lifecycle and the package owns metric definitions.
- The `bc_` metric prefix mirrors the validator client's `vc_` prefix, and the REST API client metric block follows the existing `@lodestar/api` metric contract.
