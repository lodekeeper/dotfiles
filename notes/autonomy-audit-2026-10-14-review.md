# Daily autonomy audit — 2026-10-14

## Evidenced improvement

The routing helper compared hosted network IDs with generic datasource names. Before the change, live `focil-devnet-1` returned exit 3 (`target-not-found`) although Panda advertised it as active. The helper now discovers exact active IDs with `panda devnets -o json`, requires datasource readiness for remote routes, and reports inventory failures separately from valid absence. Local precedence and no-target generic readiness are preserved. Exact datasource-name compatibility remains; remote substring matches are rejected.

## Verification

- `python3 scripts/debug/test_devnet_routing_readiness.py -v`: 10 tests passed. Includes invalid/empty/inactive inventories, failed commands/timeouts, ambiguous IDs, unavailable datasources, local precedence and no-target readiness.
- Original-code negative control: active-hosted-ID regression fails with exit 3 instead of 0. Baseline retained at `notes/autonomy-audit-2026-10-14-baseline/check-devnet-routing-readiness.py`.
- Fresh inherited-environment Gateway prerequisites: 28/28 checks passed, 16 unique commands / 12 reuses; read-only structured health comparison reports no drift.
- Post-change targeted devnet prerequisites: 6/6 checks passed.
- Read-only live routing: four advertised IDs passed, one nonexistent ID returned exit 3. Evidence: `notes/autonomy-routing-2026-10-14.json`. This tests routing/discovery, not finality or endpoint availability.

## Remaining limits

Actions reruns need an upstream maintainer. Generated fixture provenance/actual selected-case coverage remains unverified. Grafana is unavailable in the inherited execution environment; Panda is available. Public host aliases still require the advertised endpoints lookup; the monitor is not automatically rewired. The existing devnet-debug skill warns against named targets using the old behavior. Workshop declined to update this non-Workshop-owned skill; its documentation correction is a suggested follow-up, not an applied change. No config, scheduler, auth, external post, installation, restart, commit or push.

## Independent review

Design approved by native reviewer `routing_review`. Final code and report review approved. The reviewer independently ran all ten regressions and the original-code negative control, parsed the saved 28/28 and 6/6 prerequisite checks and four success / one absent-target routing results, and verified prior snapshot preservation. The reviewer did not rerun live network probes. Reviewer wording correction incorporated: fixture provenance/coverage is unverified, not a demonstrated blocker; Grafana absence is execution-environment-specific.
