# Review Findings — review-linter — 9758

Reviewer: review-linter
Reviewed commit: 4b02d4bda1e5af34ac96930cad7d043b6c076854
Generated at: 2026-08-03 15:28 UTC

I reviewed only the files listed for PR #9758 at the requested commit.

## Findings

1. packages/builder/src/builder.ts:35 — exact location also includes lines 36-38 and constructor line 42

Convention — Lodestar enables `noUnusedLocals` in the root `tsconfig.json`; classes should not retain unused private state. Sibling classes either declare constructor parameter properties only when they are read later, or avoid storing unused modules.

Deviation — `Builder` stores private readonly `index`, `config`, `api`, and `logger` fields but never reads them. `pnpm --filter @lodestar/builder check-types` reports TS6133 for all four fields, and Biome also warns that the destructured `metrics` constructor parameter is unused.

Suggestion — Remove these private fields and assignments until the builder uses them, or actually wire them into follow-up behavior. If `metrics` is intentionally reserved for later, do not destructure it yet, or alias it as an intentionally-unused parameter in the local style used by `getMetrics(_register)`.

2. packages/builder/package.json:14

Convention — Lodestar package export maps expose TypeScript sources through the `typescript` condition before `types` and `import`; every other workspace package with a root export uses `"typescript": "./src/index.ts"`.

Deviation — The new builder package uses `"bun": "./src/index.ts"`, making it the only package with this condition and breaking the workspace export-map convention.

Suggestion — Replace the `bun` condition with `typescript` so the export map matches packages such as `@lodestar/validator`, `@lodestar/api`, and `@chainsafe/lodestar`.

3. packages/builder/package.json:56

Convention — Workspace dependencies are kept in sorted package-name order within their scope. For the closest sibling package, `@lodestar/validator` orders `@lodestar/state-transition` before `@lodestar/types` and `@lodestar/utils`.

Deviation — `@lodestar/state-transition` appears after `@lodestar/utils` in the new builder package dependencies.

Suggestion — Move `@lodestar/state-transition` before `@lodestar/types` and `@lodestar/utils`.

4. packages/builder/src/defaults.ts:1

Convention — Lodestar public exports are named exports; public default options in nearby packages are exposed as named `defaultOptions` exports, for example `packages/beacon-node/src/node/options.ts` and `packages/validator/src/services/validatorStore.ts`.

Deviation — The new builder defaults module uses `export default`, and `packages/builder/src/index.ts` re-exports it via `export {default as defaultOptions}`.

Suggestion — Export a named `defaultOptions` constant from `defaults.ts` and re-export that named symbol from `index.ts`.

## Verification

- `pnpm --filter @lodestar/builder lint` completed with one Biome warning for the unused `metrics` constructor parameter.
- `pnpm --filter @lodestar/builder check-types` failed with TS6133 for the unused private fields listed above. The command also printed the local Node v22 warning because the repo expects Node ^24.13.0.
