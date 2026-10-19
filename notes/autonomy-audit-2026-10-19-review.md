# Daily autonomy audit — 2026-10-19

## Evidence and implemented improvement

Recent monitor entries in `memory/2026-10-18.md` repeatedly report guessed Dora client/fork/Swagger paths returning HTTP404 before recovery through live navigation/schema (02:13, 06:13, 14:13, 16:13). The 2026-10-19 00:13 entry records urllib403 recovered with curl. Existing `net-health.sh` does not collect the client/fork APIs; the debug scripts had no dedicated schema-driven collector.

Added `scripts/debug/fetch-dora-snapshot.py`, a standalone read-only evidence collector. Usage:

```bash
panda devnets -o json
panda devnets endpoints <active-id> -o json > endpoints.json
python3 scripts/debug/fetch-dora-snapshot.py --endpoints-json endpoints.json > snapshot.json
```

The caller selects an advertised active ID and owns endpoint freshness. The helper requires the inventory's Dora HTTPS origin, fetches the observed `/api/swagger/doc.json` schema location, and selects unique GET operation IDs `getConsensusClients` and `getNetworkClientHeadForks`. It honors Swagger2 `basePath`, ignores schema `host`/`schemes`, and rejects unsafe/nonliteral paths or required parameters. It fails if the schema contract changes; it does not guess replacements.

Curl ignores ambient curlrc (`-q` first), makes bounded HTTPS GETs without auth, redirects or retries, and requires HTTP200. Both response envelopes/lists/counts must validate before a single complete JSON bundle is printed. The bundle preserves schema, raw client/fork evidence, resolved paths, UTC retrieval time and counts. `transportOk` means successful evidence retrieval only; offline clients, TLS metadata errors and empty lists are not interpreted as health or failure verdicts.

This implements the reusable recovery path, **not an automatic monitor fix**. No monitor prompt/schedule, installed skill, authentication or incident ownership was changed. Helper usage is discoverable in today's `notes/autonomy-gaps.md` snapshot. The pre-existing devnet-debug skill's stale named-target workaround is outside this script change; no skill publication was attempted.

## Verification

- Ten focused, network-free unittest methods pass: relocated operation routes/basePath; missing/duplicate/POST-only operations; Swagger/required/ref-parameter changes; unsafe paths; endpoint-origin validation; explorer evidence versus health; malformed envelopes/counts; curl/UTF-8/JSON/nonfinite-number failures; valid JSON on non-200; fake-curl CLI success and later-call failure without partial stdout.
- Fresh Panda active inventory/endpoints saved as `notes/autonomy-devnets-2026-10-19.json` and `notes/autonomy-dora-endpoints-2026-10-19.json`. The live ID `focil-devnet-1` advertises the Heze Dora origin; no hostname synthesized from the ID.
- Final live smoke: `memory/autonomy-raw/autonomy-dora-snapshot-2026-10-19-final.json` (private; moved from notes/ 2026-10-19 because client entries carry peer IPs), 13 clients and one fork; resolved paths `/api/v1/clients/consensus` and `/api/v1/network/client_head_forks`. This tests live schema selection/retrieval, not network finality or client liveness.
- Full inherited-Gateway prerequisites: **32/32 passed**, 17 unique commands plus 15 cache reuses (`notes/autonomy-preflight-2026-10-19.json`). Exact structured comparison with yesterday's post-change 32-check evidence reports no drift (`notes/autonomy-preflight-comparison-2026-10-19.json`). These checks preceded the new standalone helper; the helper is verified separately by its tests/live smoke.
- The persisted health baseline still lacked yesterday's four bootstrap checks. Its initial four-added-check report is retained in `notes/autonomy-health-drift-2026-10-19.json`; this is baseline bookkeeping, not a new prerequisite outage. Reconciled those four verified additions after asserting no other structured changes; the post-update comparison has no drift. Evidence: `notes/autonomy-health-baseline-reconciled-2026-10-19.json`; original state retained with the baseline files.

## Remaining blockers and proposed fixes

- **PR review:** exact-head artifacts, every open finding reconciled, source/version claims verified, authorized provider delivery. No PR review/posting performed.
- **CI fix:** upstream Actions reruns require a maintainer; prepare authorized local/fork fixes, check all-author duplicates and run the real quality gate on actual patches. Readiness is not a live model verdict. No patch/rerun attempted.
- **Spec implementation:** source cache `aa16bb4c1` is ready, but `generatedFixturesVerified=false`. During the next real spec task capture generation revision, command/selection, artifact inventory and executed cases; run narrow selected tests. No fixture generation/source refresh/Lodestar tests today.
- **Devnet debugging:** Grafana absent in this inherited environment. Panda remains ready; use authoritative endpoint/participant discovery and existing incident ownership/dedup. Use the new helper for public client/fork evidence; a transport failure is not proof that a client is down. Automatic monitor integration remains unimplemented and is not claimed.

## Independent review and preservation

Native reviewer `audit_review` approved the design and independently reran the initial nine tests. It verified initial live evidence against the saved schema/inventory and caught that curl's `--fail` alone accepts HTTP3xx plus Python's exponent-overflow float parsing. Both were corrected with explicit HTTP200 verification, finite-float parsing and serialization inside the guarded all-or-nothing output path; a tenth test covers non-200 JSON. Final independent code/evidence/report review approved with no blockers: the reviewer reran all ten tests, verified final live origin/routes/counts, checked all 32 prerequisite records and unchanged signatures, and reproduced exact historical audit preservation. No reviewer network calls or source edits.

Baseline audit/backlog files are retained in `notes/autonomy-audit-2026-10-19-baseline/`. Today's snapshot is inserted without altering earlier audit history except its top-level Updated/pass marker. Backlog changes are targeted; no archival or whole-file backlog replacement.

Close-out checks passed: consistency (179 snapshots, no contradictions), latest-pair/current-date cadence, no duplicate snapshot dates, exact previous history and preamble preservation, and scoped whitespace checks. The new-file `git diff --no-index --check` checks produced no whitespace diagnostics (their difference exit status is expected for new files).

No config/auth/scheduler changes, service restart, installation, index rebuild, commit/push, skill publication or external post. Changes remain local and uncommitted.
