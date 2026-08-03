# Review Findings - review-devils-advocate - 9758

Reviewer: review-devils-advocate
Reviewed commit: 4b02d4bda1e5af34ac96930cad7d043b6c076854
Generated at: 2026-08-03 15:35 UTC

## Devil's Advocate Review

### Overall Assessment
The builder direction is reasonable for GLOAS experimentation, but this PR promotes an inert, already-registered-only runtime to public CLI/package surface before the minimum operator workflow exists.

### Objections

#### 1. The public CLI advertises a runnable builder before there is an end-to-end builder duty
**Challenge:** `lodestar builder` is added as a top-level command and docs category, but the runtime only loads a key, fetches genesis/spec, checks identity, starts a clock, and exposes a signer object. There is no loop that produces bids, signs/publishes bids via `publishExecutionPayloadBid`, signs/publishes envelopes, or otherwise performs a builder duty. That makes the first user-facing shape a command named "Run a builder client" whose successful startup does not actually run a builder.
**Evidence:** The CLI command is visible as `command: "builder"` with `describe: "Run a builder client"` in `packages/cli/src/cmds/builder/index.ts:6`. The docs sidebar exposes "Builder Client" in `docs/sidebars.ts:35`. The handler stops after `Builder.init(...)` and registering shutdown callbacks in `packages/cli/src/cmds/builder/handler.ts:37`, while `Builder.init` returns after constructing a clock in `packages/builder/src/builder.ts:78`; the class has no duty scheduler beyond `clock.start(...)` in `packages/builder/src/builder.ts:37`. The new package is also published as `@lodestar/builder` with public exports in `packages/builder/package.json:2` and `packages/builder/src/index.ts:1`.
**Counter-proposal:** Keep the package and command internal/hidden for this PR, or reduce the public merge to the reusable pieces that are already meaningful: `BuilderSigner`, keystore loading tests, and any GLOAS signing helpers. Expose `lodestar builder` and add it to docs only in the PR that includes one complete duty path, for example slot-driven bid creation plus `api.beacon.publishExecutionPayloadBid`, or an explicit `builder sign-*` tool if the current goal is only offline signing.
**Impact if ignored:** Operators and downstream packagers will treat `@lodestar/builder`/`lodestar builder` as a supported product surface while its behavior is still a scaffold. The project then inherits compatibility and docs obligations for a shape that may need to be broken as soon as real bidding/envelope flow lands.

#### 2. Startup requires an already-active builder, but the MVP omits the registration path that makes that possible
**Challenge:** The PR's stated goal is "initial work on the ePBS builder", yet the only runtime path rejects unregistered or non-active keys. That tackles the post-registration symptom, not the first operational problem for any builder key: becoming a builder in the GLOAS registry. For a fresh testnet/operator, the CLI cannot bootstrap the identity it requires.
**Evidence:** `Builder.init` calls `getStateBuilders({stateId: "head", builderIds: [builderSigner.getPubkeyHex()]})` in `packages/builder/src/builder.ts:51`, throws `Builder not registered` when the response is empty at `packages/builder/src/builder.ts:62`, and throws unless status is `active` at `packages/builder/src/builder.ts:68`. The only builder-specific CLI options are beacon node URL, keystore, password, and optional public-key assertion in `packages/cli/src/cmds/builder/options.ts:5`; there is no deposit/registration amount, execution address, builder withdrawal credential helper, or waiting mode.
**Counter-proposal:** Make registration the first visible workflow: either add a `builder register`/`builder deposit` command that prepares or submits the builder deposit request expected by the GLOAS state transition, or make `builder run` explicitly wait for registration/activation with clear status logs and no hard failure. If registration will be handled by separate tooling, leave this PR as library-only and document the external prerequisite before adding the public command.
**Impact if ignored:** The first real user journey becomes a dead end: create/load a keystore, run the command, receive "Builder not registered", then need undocumented external machinery. That will drive follow-up PRs to reshape the CLI around registration anyway.

#### 3. The package freezes a GLOAS alpha surface into public API too early
**Challenge:** This PR exports a package described as "the Ethereum Consensus builder client" while hard-coding GLOAS-only containers and `PAYLOAD_BUILDER_VERSION` into its initial public API. EIP-7732 is still in Review, and the PR README pins consensus-specs `v1.7.0-alpha.13`; treating this as a normal Lodestar package now bakes alpha terminology and method names into release artifacts before the builder interface is stable.
**Evidence:** The signer accepts `gloas.ExecutionPayloadEnvelope` and `gloas.ExecutionPayloadBid` directly in `packages/builder/src/services/builderSigner.ts:17` and `packages/builder/src/services/builderSigner.ts:26`, while startup enforces `PAYLOAD_BUILDER_VERSION` in `packages/builder/src/builder.ts:72`. The package metadata presents it as a normal public package in `packages/builder/package.json:2`, and the README calls it a "Typescript implementation of the Ethereum Consensus builder client" while displaying the alpha consensus-spec badge in `packages/builder/README.md:4`. The current EIP page marks EIP-7732 as Review and says it is being peer-reviewed: https://eips.ethereum.org/EIPS/eip-7732.
**Counter-proposal:** Keep the public surface explicitly experimental until the spec stabilizes: name exports/commands with a GLOAS or experimental prefix, avoid publishing a general `@lodestar/builder` contract yet, or confine the signer to an internal module consumed by tests/devnets. When the GLOAS spec reaches a more stable target, promote the API with a migration point instead of carrying accidental alpha names forever.
**Impact if ignored:** Future spec churn will turn into package-level breaking changes rather than isolated internal rewrites. The cost is not the 820 lines in this PR; it is having downstream code and docs depend on an alpha builder API that Lodestar has not actually committed to supporting.

### Verdict
RECONSIDER - viable alternatives exist.
