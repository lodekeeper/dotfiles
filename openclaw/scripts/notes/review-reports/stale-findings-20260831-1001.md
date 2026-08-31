# Stale Review Findings Report

Generated: 2026-08-31 10:01 UTC
Threshold: open critical major findings older than 7 days

## PR #8924

```

### PR #8924 — Stale open findings (severity in ['critical', 'major'], updated >= 7d old)

🟠 [411b5a] src/sync/range/chain.ts:142 (review-bugs) — age=175d
   Race condition in batch completion: sleep() called outside of async guard, may interleave with abort signal

Total stale findings: 1
```

## PR #8962

```

### PR #8962 — Stale open findings (severity in ['critical', 'major'], updated >= 7d old)

🔴 [d60f21] packages/beacon-node/src/network/processor/gossipHandlers.ts:626 (review-bugs) — age=168d
   Unhandled promise rejection in gossip handler - will crash beacon node
🔴 [83d888] packages/beacon-node/src/api/impl/beacon/blocks/index.ts:750 (review-bugs) — age=168d
   Unhandled promise rejection in API handler - fire-and-forget processExecutionPayload
🔴 [bf8f9c] packages/beacon-node/src/chain/blocks/writePayloadEnvelopeInputToDb.ts:49 (review-bugs) — age=168d
   Cache pruned on DB write failure - data loss
🟠 [7ccc2f] packages/beacon-node/src/api/impl/beacon/blocks/index.ts:38 (review-linter) — age=168d
   .ts import extension breaks ESM resolution (3 files)
🟠 [3be53c] packages/beacon-node/src/chain/blocks/importExecutionPayload.ts:167 (review-security) — age=168d
   EL SYNCING/ACCEPTED not distinguished from VALID in fork choice

Total stale findings: 5
```

## PR #9382

```

### PR #9382 — Stale open findings (severity in ['critical', 'major'], updated >= 7d old)

🔴 [3f599d] packages/beacon-node/src/execution/engine/http.ts:192 (github-advanced-security[bot]) — age=33d
   ## CodeQL / Polynomial regular expression used on uncontrolled data

This [regular expression](1) that depends on [libra...
🔴 [5ad7a5] packages/beacon-node/src/execution/engine/sszRestClient.ts:70 (github-advanced-security[bot]) — age=33d
   ## CodeQL / Polynomial regular expression used on uncontrolled data

This [regular expression](1) that depends on [libra...
🔴 [7d2b54] packages/beacon-node/src/execution/engine/sszRestEncoding.ts:287 (gemini-code-assist[bot]) — age=33d
   ![critical](https://www.gstatic.com/codereviewagent/critical.svg)

The SSZ encoding for the `getBlobs` request is incorr...
🔴 [489b7d] packages/beacon-node/src/execution/engine/sszRestEncoding.ts:519 (gemini-code-assist[bot]) — age=33d
   ![critical](https://www.gstatic.com/codereviewagent/critical.svg)

The `getBlobs` response decoding incorrectly expects ...
🟠 [e59aaa] packages/beacon-node/src/execution/engine/http.ts:201 (gemini-code-assist[bot]) — age=33d
   ![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)

The `SszRestClient` is initialized using only th...

Total stale findings: 5
```

## PR #9673

```

### PR #9673 — Stale open findings (severity in ['critical', 'major'], updated >= 7d old)

🔴 [ff78a2] packages/beacon-node/src/api/rest/base.ts:64 (nflaig) — age=41d
   agree, not sure it's worth re-triggering the CI for this though, the `qs` note might be useful if someone tries to query...
🟠 [8c2d05] packages/beacon-node/src/api/rest/base.ts:93 (chatgpt-codex-connector[bot]) — age=41d
   **<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Raise the query array limit for ...
🟠 [b43e13] packages/beacon-node/src/api/rest/base.ts:93 (lodekeeper) — age=41d
   Good catch — raised the cap to `NUMBER_OF_COLUMNS` (128) in c1fa18ec1b so a full-custody `getDebugDataColumnSidecars` re...
🟠 [4674f8] packages/beacon-node/src/api/rest/base.ts:64 (spiral-ladder) — age=41d
   nit: not sure if this overexplanation is necessary too, don't need to know `qs` implementation details + this lacks cont...

Total stale findings: 4
```

## PR #9687

```

### PR #9687 — Stale open findings (severity in ['critical', 'major'], updated >= 7d old)

🟠 [9672f5] packages/beacon-node/src/chain/lightClient/index.ts:775 (gemini-code-assist[bot]) — age=26d
   ![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)

In `blockToLightClientHeader`, accessing `blockB...
🟠 [1259b8] packages/state-transition/src/lightClient/spec/utils.ts:498 (gemini-code-assist[bot]) — age=26d
   ![medium](https://www.gstatic.com/codereviewagent/medium-priority.svg)

In `computeBranchRoot`, if the `branch` paramete...

Total stale findings: 2
```

---
**Action required:** Address or acknowledge these stale findings.
Use `track-findings.py resolve <pr> <id> --note '...'` to update status.
