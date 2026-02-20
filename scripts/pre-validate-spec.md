# Pre-Push Validation Script for Lodestar — Final Spec (v2.1)

## Overview
`scripts/pre-validate.mjs` — A Node.js ESM script that validates local changes before pushing to avoid CI failures. Zero external dependencies.

## CLI Interface

```
Usage: node scripts/pre-validate.mjs [options]

Options:
  --quick                    Skip build, test only changed packages (no dependents)
  --strict                   Full validation: build + test changed + dependents (default)
  --base <ref>               Git diff base ref (see fallback rules below)
  --all                      Run all checks on all packages
  --dry-run                  Print scope and commands without executing
  --ci-order                 Use CI step order (build first, then lint+types). Implies sequential.
  --max-packages <n>         Threshold for global test fallback (default: 8)
  --no-fetch                 Don't fetch origin before computing scope
  --verbose                  Show detailed output
  --help                     Show help
```

## Modes

| Mode | Build | Tests scope | When |
|------|-------|-------------|------|
| `--quick` | Skip | Changed packages only | Fast local iteration |
| `--strict` (default) | Yes | Changed + transitive dependents | Pre-push |
| `--all` | Yes | All packages | Full validation |

## Step Order

### Default (fail-fast for local dev)
1. **Fetch** origin (unless `--no-fetch`)
2. **Detect scope** — compute affected packages
3. **Lint + Type-check** — run in parallel via `Promise.all`
4. **Build** — strict/all mode only
5. **Unit tests** — targeted per affected packages

### `--ci-order` (mirrors CI exactly)
1. Fetch + detect scope
2. Build
3. Lint + Type-check (parallel)
4. Unit tests

## Scope Detection

### Base ref resolution (ordered fallback)
1. `--base <ref>` if provided
2. Current branch upstream (`@{upstream}`) if exists
3. `origin/unstable` (default)

### Changed files
```js
// NUL-delimited for safety, include renames/deletes
execSync('git diff --name-only -z --diff-filter=ACMRD <base>..HEAD')
```

### Path Classification Matrix

| Pattern | Classification | Action |
|---------|---------------|--------|
| `packages/<name>/src/**` | Source change | Test package + transitive dependents (strict) |
| `packages/<name>/test/**` | Test change | Test package only |
| `packages/<name>/package.json` | Package config | Test package + dependents |
| Root: `tsconfig*.json`, `vitest.config.*`, `biome.json`, `pnpm-lock.yaml`, `package.json` | Root config | ALL packages |
| `scripts/**`, `docs/**`, `.github/**`, `*.md` | Non-code | Lint + types only, skip tests |
| Anything else at root | Unknown | Lint + types only |

### Dependency Graph
```js
// Build from packages/*/package.json
// Include: dependencies, devDependencies, peerDependencies, optionalDependencies
// Filter: workspace:* protocol entries only
// Traverse: transitive dependents (reverse graph)
```

### Global Fallback
If `affectedPackages.length > maxPackages` (default 8), run global unit tests instead:
```
pnpm test:unit
```
This avoids N separate test runs being slower than one global run.

## Execution

### Running commands
- Use `child_process.spawn` with array args (no shell interpolation)
- Parallel execution via `Promise.all` for lint + typecheck
- Sequential for build and tests (deterministic output)

### Per-package tests
```js
// Deterministic ordering (sorted by package name)
for (const pkg of affectedPackages.sort()) {
  // Check if package has test:unit script
  if (!pkg.scripts['test:unit']) {
    warn(`⚠️  ${pkg.name} has no test:unit script, skipping`);
    continue;
  }
  exec(`pnpm --filter ${pkg.name} run test:unit`);
}
```

## Output Format

```
🔍 Scope: 3 changed, 5 affected (with dependents)
   Changed: @lodestar/utils, @lodestar/params, @lodestar/config
   Affected: + @lodestar/beacon-node, @lodestar/validator
   Base: origin/unstable (abc1234)

✅ Lint ........... passed (2.1s)
✅ Type check ..... passed (8.3s)
✅ Build .......... passed (12.4s)
✅ @lodestar/utils  passed (1.2s)
✅ @lodestar/params passed (0.8s)
❌ @lodestar/beacon-node FAILED (3.4s)

💥 Validation failed! Fix errors before pushing.
```

## Edge Cases

| Case | Behavior |
|------|----------|
| No changed files | Print "nothing to validate", exit 0 |
| Only docs/non-code | Run lint + types only, skip build + tests |
| Root config changes | Treat as all packages affected |
| No upstream ref | Error with clear message suggesting `--base` |
| Package without `test:unit` | Skip with warning |
| Untracked/unstaged files | Ignored (committed changes only) |
| Build failure | Halt immediately, don't run tests |
| Any step failure | Exit non-zero, print summary |
| NUL bytes in filenames | Handled via `-z` flag |

## File Structure
```
scripts/
  pre-validate.mjs    # Main script (single file, zero deps)
```

## Acceptance Criteria
- [ ] Detects changed packages from git diff (merge-base semantics)
- [ ] Classifies file changes per the path matrix
- [ ] Computes transitive dependents from workspace dependency graph
- [ ] Runs lint + type-check in parallel
- [ ] Builds only in strict mode
- [ ] Runs targeted unit tests per affected package (sorted, deterministic)
- [ ] Falls back to global test run if too many packages affected
- [ ] --quick mode for fast iteration (no build, no dependents)
- [ ] --dry-run shows scope and commands without executing
- [ ] --base configurable with smart fallback chain
- [ ] --no-fetch prevents network calls
- [ ] Colored output with timing per step
- [ ] Exits non-zero on any failure with clear summary
- [ ] Handles all edge cases gracefully
- [ ] Zero external dependencies (Node.js built-ins only)
- [ ] Uses spawn with array args (no shell injection)
- [ ] NUL-delimited git output for filename safety
