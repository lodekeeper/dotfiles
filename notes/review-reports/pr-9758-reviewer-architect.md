# Review Findings — reviewer-architect — 9758

Reviewer: reviewer-architect
Reviewed commit: 4b02d4bda1e5af34ac96930cad7d043b6c076854
Generated at: 2026-08-03 15:31 UTC

## Findings

### 1. Builder package exports use a non-Lodestar source condition

File: `packages/builder/package.json:14`

**Scope** — The new `@lodestar/builder` package export contract, plus workspace consumers such as `@chainsafe/lodestar` that import `@lodestar/builder`.

**Issue** — The package exposes its source entry with a `"bun"` condition instead of the `"typescript"` condition used by every other Lodestar workspace package. That introduces a package-local tool/runtime condition rather than following the monorepo's established source-resolution contract.

**Impact** — Local TypeScript, tsx, vitest, and docs tooling rely on Lodestar packages resolving source through the same export shape. With this package diverging, consumers can resolve `@lodestar/builder` through `lib` or a Bun-specific path depending on the caller, making the builder package behave differently from validator, beacon-node, api, and the other packages. That weakens the package boundary and makes future builder integration harder to reason about.

**Recommendation** — Change the export condition to `"typescript": "./src/index.ts"` and keep the rest of the export shape aligned with peer packages. If Bun-specific support is desired, discuss it as a repo-wide export policy rather than adding it only to the builder package.

## Architectural Summary

Aside from the export-condition drift above, the new package is included by the existing `packages/*` workspace pattern, the CLI dependency direction is top-level CLI -> builder, and the builder package depends downward on api/config/state-transition/types/utils in a way that matches the validator-client shape for this initial setup.
