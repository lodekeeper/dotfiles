# Live-head verification

Reviewed commit: 611e3f9956a0bf219d3dd3357529bea0d4c1e2a7

- Source inspection confirms all fork/blob/runtime fields are static; only MIN_GENESIS_TIME and deposit chain/network IDs roll by whole reset intervals.
- Node execution of the already-built config (source matches clean HEAD) reproduced both the current staging time and one second before activation: DEPOSIT_CHAIN_ID39438164, MIN_GENESIS_TIME1790276400, genesis1790277000, forkAtSlot0 gloas, maxBlobsAtSlot0 15.
- At1792695600 and1792696200: identity39438165, MIN_GENESIS_TIME1792695600, genesis1792696200, Gloas0, blobs15.
- Parent source has GLOAS_FORK_EPOCH Infinity, Fulu0, blob changes2048/12 and4096/15. Finding accurately identifies unsafe pre-reset use.
- Source-based focused verification: node node_modules/vitest/vitest.mjs run --project unit packages/config/test/unit/networks.test.ts, 10/10 pass, one file,1.30s. The historical rollback test asserts identity only, not old fork/runtime compatibility.
- No source modifications, builds, installs or commits made by this follow-up. No additional lint/types needed for a PR-body/thread-only response. Two exploratory read paths initially failed (wrong test path, absent .agents); corrected reads succeeded.

Disposition: acknowledged operational limitation covered by pre-existing post-reset-only merge/deployment gate, not a false positive and not source-fixed. Original design intentionally excludes iteration-aware scheduling. Upstream finalization, final config check and reset still required.

Follow-up guard scanned all three GitHub discussion surfaces (1issue,1inline,1review body). It exited2 for a metadata false positive: the pinned upstream values.env URL was parsed as a local changed-file path; no genuine diff/title scope mismatch. Existing PR draft-status wording is being corrected separately. Finding remains acknowledged/deferred under the explicit activation gate, not source-fixed.
