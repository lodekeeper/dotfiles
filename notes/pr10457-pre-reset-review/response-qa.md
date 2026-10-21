# PR #10457 pre-reset disposition QA

Reviewer: gpt-advisor
Reviewed commit: 611e3f9956a0bf219d3dd3357529bea0d4c1e2a7

## Verdict

Approved: `reply-draft.md` and `pr-body-updated.md` accurately acknowledge the P1 and preserve the original post-reset-only merge/deployment scope. No source change is necessary for that scope. The pre-reset incompatibility is real and remains present in the code; it is operationally gated, not source-fixed or a false positive.

## Checks

- Exact-head source rolls only genesis/deposit identity; Gloas at epoch 0 and the 15-blob schedule remain static. The identity-only historical tests do not establish Fulu compatibility.
- Original design, functional review and submitted body already prohibited iteration-164 deployment and required upstream finalization, final iteration-165 config verification and the reset before merge.
- The timestamp labels are correct: October 22, 2026 at 19:00 UTC is `MIN_GENESIS_TIME`; slot 0 is 19:10 UTC. These planned times do not independently establish that a reset occurred or the upstream config is final.
- Revised body removes the stale draft/status wording without undoing Nico's ready-for-review state or relaxing the gates. It does not claim live sync, genesis generation or cross-client interoperability.
- No need to expand this response into an iteration-aware scheduler. A pre-reset merge/deployment requirement would require a different implementation, but none is authorized here.

## Small wording refinements

In the inline reply, replace bare `upstream #75` with `[ephemery-genesis #75](https://github.com/ephemery-testnet/ephemery-genesis/pull/75)` so GitHub does not link Lodestar issue #75. Prefer “Keeping the existing post-reset-only merge/deployment scope; iteration-aware scheduling remains out of scope” to “deferred-switch approach,” which could sound like an activation mechanism exists in code. No other correction is required.

Do not describe the finding as code-fixed or the merge gate as satisfied. The final “I have clarified” sentence is accurate only after the body update is successfully verified.

Read-only source/text QA; no tests rerun, GitHub writes, source edits, installs or deployment actions performed by this reviewer.
