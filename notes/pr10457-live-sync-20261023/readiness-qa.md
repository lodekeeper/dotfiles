# PR #10457 live Ephemery readiness QA

Reviewer: gpt-advisor
Reviewed commit: 611e3f9956a0bf219d3dd3357529bea0d4c1e2a7

## Interim verdict: pending live catch-up

The saved metadata, final configuration, preset-download, exact-head build and invocation evidence support the requested test scope. They do not yet establish completed sync or justify an unconditional ready-to-merge response. Latest inspected snapshot: 2026-10-23T11:05:02Z, head slot 1278, sync distance 3497, `is_syncing: true`, finalized epoch 37.

## Verified so far

- Local HEAD is the exact reviewed commit. The saved start receipt and startup log identify it, use `--network ephemery --execution.engineMock --supernode`, and show the default genesis URL. No params/genesis/checkpoint override is present.
- Independently re-compared the saved final release YAML against the built exact-head preset using the config serializers and YAML failsafe parsing: 94 supported fields including `CONFIG_NAME`; all 93 other fields match. Only `testnet` versus `ephemery` is normalized. Gloas epoch 0, deposit ID 39438165, genesis 1792696200 and the epoch-0 15-blob schedule agree. No new upstream parameter mismatch found.
- Saved final release metadata identifies `ephemery-165` at upstream merge `9c2cac445414a12d8ed4f8bcec5f004bca70e898`. Release genesis SHA-256 independently matches the saved default-URL probe digest: `12add4420bbcf7a4d1922366e8754b85503912f922866b79fec919f250a1f31f`.
- Build log succeeds; the focused network suite reports 10/10 passing; two-file lint reports no changes. These checks were inspected, not rerun by this reviewer.
- Current-iteration ChainSafe/Ethstaker/Bordel genesis evidence matches time 1792696200 and validators root `0x4190afc8844d015754deb884df1fa4ec8cc8a993061b2e5fe5782f47b2c1cc4d`. The pandaops genesis response is stale iteration 164 and must not establish iteration identity.

## Evidence still needed before final sign-off

1. Caught-up status (`is_syncing: false`, distance zero or an explained near-head/missed-slot gap), then subsequent head and finalized-checkpoint advancement rather than one successful historical import sample.
2. Local genesis identity and current Gloas fork, plus agreement with a fresh current-165 public checkpoint on a common finalized epoch/root. Public checkpoint services need not serve `headers/head`; their 404 responses are not evidence of node failure.
3. Final bounded log review for recurring import/validation failures, a current exact-head/CI check, and the proposed response/body text. No broader test rerun or source change is indicated by the present evidence.

## Claim boundaries

- Engine mock exercises default preset/download/discovery and consensus-layer sync. `is_optimistic: false` and `el_offline: false` under the mock do not prove real execution-payload validation or live EL interoperability. State this limitation explicitly.
- CI is `observed_green`; the 30 OK / 2 skipped counts overlap workflow/check surfaces and are not 30 unique jobs. Required branch-protection coverage is not evaluated.
- Do not imply iteration-aware scheduling, automatic process rollover or pre-reset compatibility was added. No merge is authorized by this test request.

This is a pending report for the initial evidence set; final snapshots and draft response still require QA. No source/GitHub writes or process management performed by this reviewer.
