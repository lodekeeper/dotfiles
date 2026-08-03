# Review Findings — review-wisdom — 9758

Reviewer: review-wisdom
Reviewed commit: 4b02d4bda1e5af34ac96930cad7d043b6c076854
Generated at: 2026-08-03 15:27 UTC

Reviewed only the changed files listed for PR #9758.

1. **packages/builder/src/builder.ts:42** — exact location

   **Principle** — Simplicity / clear ownership

   **Current** — `BuilderModules` and the constructor accept `metrics`, `logger`, `index`, `config`, and `api`, but the current class behavior only starts the clock, exposes the signer, and aborts the controller. `metrics` is destructured without being retained or used, while several private fields are stored ahead of any behavior that reads them.

   **Suggested** — Keep the initial `Builder` state to the fields it actively owns today, or wire the stored modules into named responsibilities as they land. For example, defer `metrics` and other future-facing fields until the first metric/service uses them, and make the constructor input mirror the current object invariants.

   **Why** — A new package becomes easier to grow when its first object has a small, truthful surface. Future contributors can see which dependencies are real invariants versus placeholders, and tests do not have to construct modules whose purpose is not yet observable.

2. **packages/builder/src/builder.ts:65** — exact location

   **Principle** — Function design / testability

   **Current** — `Builder.init()` performs genesis fetch, spec comparison, signer construction, active-builder lookup, status validation, version validation, clock creation, and object construction in one flow. The builder-specific checks are only expressed as a sequence of local variables and throws inside the larger bootstrap method.

   **Suggested** — Extract the builder lookup and validation into a small helper with a name like `getActiveBuilderStatus()` or `assertBuilderRegistration()`, returning the validated `BuilderResponse`. Keep `init()` as the high-level orchestration of genesis, config, signer, status, and clock setup.

   **Why** — Named steps make the startup story easier to scan and give the builder-status rules a narrow unit-test target as more Gloas builder conditions are added.

3. **packages/builder/src/genesis.ts:8** — exact location

   **Principle** — Maintainability / DRY

   **Current** — The new builder package adds a `waitForGenesis()` implementation that is identical to the existing validator-side genesis polling helper, including the poll interval, logging branches, and retry behavior.

   **Suggested** — Share one implementation through an appropriate common module/export, or otherwise make the duplication intentionally temporary with a clear follow-up note.

   **Why** — Genesis polling is a cross-client lifecycle concern. Keeping one implementation avoids future drift in retry timing, abort behavior, and log shape when the beacon-node API behavior changes.
