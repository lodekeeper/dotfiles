# Stale Review Findings Report

Generated: 2026-04-27 10:01 UTC
Threshold: open critical major findings older than 7 days

## PR #8924

```

### PR #8924 — Stale open findings (severity in ['critical', 'major'], updated >= 7d old)

🟠 [411b5a] src/sync/range/chain.ts:142 (review-bugs) — age=49d
   Race condition in batch completion: sleep() called outside of async guard, may interleave with abort signal

Total stale findings: 1
```

## PR #8962

```

### PR #8962 — Stale open findings (severity in ['critical', 'major'], updated >= 7d old)

🔴 [d60f21] packages/beacon-node/src/network/processor/gossipHandlers.ts:626 (review-bugs) — age=42d
   Unhandled promise rejection in gossip handler - will crash beacon node
🔴 [83d888] packages/beacon-node/src/api/impl/beacon/blocks/index.ts:750 (review-bugs) — age=42d
   Unhandled promise rejection in API handler - fire-and-forget processExecutionPayload
🔴 [bf8f9c] packages/beacon-node/src/chain/blocks/writePayloadEnvelopeInputToDb.ts:49 (review-bugs) — age=42d
   Cache pruned on DB write failure - data loss
🟠 [7ccc2f] packages/beacon-node/src/api/impl/beacon/blocks/index.ts:38 (review-linter) — age=42d
   .ts import extension breaks ESM resolution (3 files)
🟠 [3be53c] packages/beacon-node/src/chain/blocks/importExecutionPayload.ts:167 (review-security) — age=42d
   EL SYNCING/ACCEPTED not distinguished from VALID in fork choice

Total stale findings: 5
```

---
**Action required:** Address or acknowledge these stale findings.
Use `track-findings.py resolve <pr> <id> --note '...'` to update status.
