# Gloas withdrawals proof artifacts

_Last updated: 2026-04-22 12:52 UTC_

This packages the current local-only higher-level proof work from `~/lodestar-gloas-withdrawals` so it can be reused later without reconstructing the commit range from backlog/chat history.

## Commits

Base for this proof series:
- `7358a46c35375a353ea1a8096e7989e6f0b5a0da` — `fix: use stale payloadExpectedWithdrawals when Gloas parent block is empty`

Proof commits on top:
- `45649c5c4ff69e03701fda7977003acbad824cde` — `test: cover Gloas empty-parent withdrawals branch in produceBlockV3`
- `52404aff3f9e74e3755f82402a4e1c5cfd4d2a09` — `test: cover gloas empty-parent withdrawals branch`

## Packaged patch series

Saved as:
- `notes/withdrawals-proof-patches/gloas-withdrawals-proof-series.patch`

Generated from:
- `git -C ~/lodestar-gloas-withdrawals format-patch --stdout 7358a46c35..52404aff3f`

## Diff scope

```text
packages/beacon-node/test/unit/api/impl/validator/produceBlockV3.test.ts | 107 ++++++++++++++++++++-
1 file changed, 106 insertions(+), 1 deletion(-)
```

The patch series only packages the **higher-level production-path regression** proving that the Gloas empty-parent path in `produceBlockBody()` / `notifyForkchoiceUpdate(...)` selects `getPayloadExpectedWithdrawals()` rather than the fresh `getExpectedWithdrawals()` branch.

## Claim boundary

Keep the language narrow and honest:
- **Yes:** branch-selection / method-selection proof at the FCU seam
- **No:** not yet full real-Gloas stale-field provenance proof

Reason: the regression uses a valid cached Electra base state with minimal Gloas behavior layered in, plus mocked withdrawals-source methods.

## Reuse recipes

Cherry-pick the two proof commits onto another branch:

```bash
git cherry-pick 45649c5c4ff69e03701fda7977003acbad824cde 52404aff3f9e74e3755f82402a4e1c5cfd4d2a09
```

Or apply the packaged series:

```bash
git am /home/openclaw/.openclaw/workspace/notes/withdrawals-proof-patches/gloas-withdrawals-proof-series.patch
```

## Suggested handoff sentence

> Local proof artifacts are packaged as commits `45649c5c4f` + `52404aff3f` (and as `notes/withdrawals-proof-patches/gloas-withdrawals-proof-series.patch`). They prove the Gloas empty-parent `produceBlockBody()` path selects `getPayloadExpectedWithdrawals()` at the FCU seam, but should still be described as a branch-selection proof rather than full real-Gloas stale-field provenance.
