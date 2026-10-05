# Architecture review — Lodestar PR #10261

Reviewer: reviewer-architect
Reviewed commit: 6d790d2845a530be1b96bac0eb5fa8a66b784b67

## Findings

No findings.

No architectural concerns — changes align with existing patterns.

## Architectural assessment

- **Shared API contract:** `packages/api/src/beacon/routes/beacon/state.ts` introduces a request-only `ValidatorStatusFilter` union and applies it consistently to GET and POST application arguments and wire types. Response statuses remain fine-grained `ValidatorStatus` values. The public re-export preserves the established typed client/server boundary; no validator-client dependency on beacon-node internals is introduced.
- **Dependency direction and abstraction:** `packages/types/src/utils/validatorStatus.ts` already owns the status taxonomy, classification, and general-status mapping. The new pure matcher composes that existing mapping without importing API or beacon-node code. The beacon-node API implementation consumes the helper through the existing downward dependency on `@lodestar/types`; API-specific request typing stays in `@lodestar/api`.
- **Implementation boundary:** The change remains in the existing beacon-state API implementation. POST still delegates to GET, so both use the same ids-filtering behavior. There are no consensus state-transition changes, new side effects in lower layers, fork-choice extensions, transport-domain leaks, or new infrastructure.
- **Maintenance footprint:** The five-line helper and focused tests are proportionate to the fix. The change preserves the ids-based lookup path rather than requiring a whole-registry scan or a backend-specific abstraction. No structural refactor or native-binding change is necessary for this path.

## Contributor and scope assessment

The verified Nimbus VC v26.10.0 release behavior establishes a live, spec-valid interoperability requirement, not speculative feature work. The patch addresses it within six relevant files. Cursor disclosure and the absence of a linked issue are not evidence of an architectural violation; the concrete incident and bounded implementation do not justify closing or trimming this PR on architectural grounds.

## Validation boundary

This was a read-only source review of the PR ref. Tests, lint, and type checks were not run, and the supplied CI status does not establish that they pass. Normal successful CI remains a merge prerequisite; this report makes no functional or security assurance outside its architectural scope.

MERGE — preserves package/API boundaries; narrowly addresses a verified released-client interoperability break; adds no disproportionate structural maintenance burden.
