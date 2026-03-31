# Coding Context — Enable QUIC by Default

## Task
Change Lodestar to enable QUIC transport by default (currently disabled). Update all defaults, documentation, CLI descriptions, and tests.

## Background
QUIC is already fully implemented in Lodestar. The IPv6 crash fix (PR #9101) was merged to `unstable`, so QUIC is now safe to enable on IPv4-only hosts. The task is to flip the default from `false` to `true`.

## Files to Change

### 1. Beacon node network options default
**File:** `packages/beacon-node/src/network/options.ts`
- Line 72: Change `quic: false` → `quic: true`

### 2. CLI option default  
**File:** `packages/cli/src/options/beaconNodeOptions/network.ts`
- Line ~314-319: The `quic` option has `default: false` — change to `default: true`
- Line ~90: `const quic = args.quic ?? false;` — change fallback to `true`
- Update the description from "Enable QUIC transport" to something like "Enable QUIC transport (enabled by default)"

### 3. Documentation — Networking guide
**File:** `docs/pages/run/beacon-management/networking.md`
- Line ~89: Update "QUIC is disabled by default and can be enabled with the `--quic` flag" → "QUIC is enabled by default"
- Line ~91-97: Update the "Enabling QUIC" section — it's now enabled by default, show how to disable instead (`--quic=false` or `--no-quic`)
- Line ~99: Update "When QUIC is enabled" text
- Line ~103: Update "With QUIC enabled" text  
- Line ~127: Update "only if `--quic` is enabled" → QUIC port is now open by default
- Update the port table and firewall section to reflect QUIC is default

### 4. Documentation — CLI reference (beacon)
**File:** `docs/pages/run/beacon-management/beacon-cli.md`
- Line ~599-609: Update `--quic` description and default value from `false` to `true`

### 5. Documentation — Dev CLI reference
**File:** `docs/pages/contribution/dev-cli.md`  
- Line ~605: Update `--quic` description and default value from `false` to `true`

### 6. Tests — ENR initialization
**File:** `packages/cli/test/unit/cmds/initPeerIdAndEnr.test.ts`
- Line 12: Test "should set tcp but not quic fields by default" — now QUIC IS set by default, update expectations
- Line 20: `expect(enr.quic).toBeUndefined()` → should now expect QUIC to be set
- Line 54: Test "should not set quic fields when quic is false" — keep this test (explicit opt-out)

### 7. Tests — Network option parsing
**File:** `packages/cli/test/unit/options/beaconNodeOptions.test.ts`
- Line 197: `quic: false` in expected output — change to `quic: true`
- Line 220+: Tests for tcp/quic flags — update default behavior tests
- The test "should not include quic multiaddrs by default" should now expect QUIC multiaddrs present

## Constraints
- Branch: `feat/quic-by-default` on `~/lodestar-quic-default`
- Run `pnpm lint` before committing — mandatory, no exceptions
- Run `pnpm check-types` to verify TypeScript compiles
- Run `pnpm test:unit` in relevant packages to verify tests pass
- Node 24: `source ~/.nvm/nvm.sh && nvm use 24`
- Project convention: no scopes in commit messages (e.g. `feat: enable quic by default` not `feat(network): ...`)
- Keep changes minimal and focused — only what's needed to flip the default

## Verification
```bash
# Type check
pnpm check-types

# Lint
pnpm lint

# Run affected unit tests
pnpm vitest run packages/cli/test/unit/cmds/initPeerIdAndEnr.test.ts
pnpm vitest run packages/cli/test/unit/options/beaconNodeOptions.test.ts

# Verify the default is correct
grep -n "quic" packages/beacon-node/src/network/options.ts
grep -n "quic" packages/cli/src/options/beaconNodeOptions/network.ts
```
