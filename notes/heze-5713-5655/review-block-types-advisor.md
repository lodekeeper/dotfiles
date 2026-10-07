# Signed-block envelope final review

Reviewed base: #10293 7079b042fa5
Working diff: packages/types/src/types.ts, packages/validator/src/services/validatorStore.ts, packages/validator/test/unit/services/block.test.ts

Verdict: Approved conditional on compiler/check gates passing. No required code corrections found.

Both shared signed aliases now wrap their existing fork-indexed unsigned message type and preserve the original fork-indexed signature type. Each concrete fork specialization therefore retains its original signed value structure. The aggregate representation accepts the legitimate envelope construction that previously required assertions. All current fork signatures use the same underlying signature representation, so no meaningful message/signature correlation is lost by aggregate indexing.

The implementation removes exactly the production return assertion and the three test-message casts. No executable logic, SSZ definitions, TypesByFork mappings, Heze body field removals, or API serialization is modified. This fixes the source-level aggregate type mismatch rather than tailoring the mocks. Existing mixed full/blinded structural compatibility remains compiler-checked by the unchanged signBlock return annotation.

Parent-reported baseline reproduction: removing only the test casts yields three TS2322 failures involving Heze's missing eth1Data/deposits. This reviewer did not independently execute that reproduction or the verification gates.

Reply draft approved: the explanation correctly distinguishes a union of signed envelopes from an envelope containing a union-valued message and accurately describes the actual diff. Only post the full lint/types/build and focused-test success sentence after all named gates pass. Optional concision: replace the final sentence with exact observed check names/counts if useful; no wording correction required.

Required verification remains workspace type checks, lint, build, and focused block-proposing/signBlock tests. Concrete fork-specialized SSZ values should remain compatible through the existing typed callers; any compiler failure must be resolved without weakening Heze fields or reintroducing assertions.

## Superseding compiler outcome and revised recommendation

The aggregate-envelope alias proposal is rejected by the global compiler gate: seven API errors show SSZ codecs require the exact union of per-fork signed containers. Prior source-only conditional approval does not apply after this failure. Do not weaken serializer contracts or add casts to make that proposal compile.

Approve the revised narrow resolution: restore exported signed aliases and the pre-existing production signBlock return assertion; replace the three mock reconstruction callbacks with mockResolvedValue(signedBlock). Each fixture is already a concrete, valid fork-specific signed SSZ value. Add one-call assertions and assert the signing call's message argument is the exact produced message (prefer toBe on mock.calls[0][1] for identity). Verify pubkey/duty-slot arguments too if not covered elsewhere. Existing publish assertions preserve output coverage in the first two tests; add the signing-input assertion after sleep in the Gloas test.

This is legitimate fixture-based mocking, not another unsafe fork narrowing: concrete outputs satisfy the production contract directly, and explicit input assertions recover the causal check previously implicit in callback reconstruction. It does not claim to fix a production typing defect. The broader issue is TypeScript/Vitest losing input-output union correlation when a mock reconstructs an envelope, while correct serializer contracts intentionally retain exact per-fork unions. A generic signature alone is insufficient because Vitest uses Parameters/ReturnType; a correlated generic/distributive production redesign would add assertions or broader changes without resolving these normalized mocks cleanly.

Communicate that investigation found the shared aliases must stay exact for SSZ serializers, so the tests now use concrete signed fixtures with explicit signing-input assertions. Do not post the earlier claim that shared aliases were fixed or the production assertion removed. Run global type checks again, lint, and the focused block test; no runtime production change is warranted for this review comment.
