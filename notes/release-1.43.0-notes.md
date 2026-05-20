## Release notes draft for v1.43.0

Prepend the prose intro below to the existing auto-generated changelog in
https://github.com/ChainSafe/lodestar/releases/tag/v1.43.0 (the changelog
sections under `### Features`, `### Bug Fixes`, etc. stay as-is).

---

Good day Lodestar operators! We've just released v1.43.0 and **recommend** users upgrade for the latest features and best performance. This release leads with a real-world block-import performance fix and another substantial wave of ePBS / Gloas progress.

**Performance fix.** v1.43.0 includes #9352, which dedupes the workspace `@chainsafe/persistent-merkle-tree` instance so the native `hashtree` hasher (configured via `cli/applyPreset.ts`) is wired to the same module ssz uses internally. Earlier v1.43.0-rc builds resolved two copies of PMT through the ssz transitive bump, causing every `hashTreeRoot` going through ssz's `merkleize.js` to fall back to the JS noble hasher and allocate per digest. Operators running the affected unstable line saw elevated minor/incremental GC and the *Import Head Late* metric trending up; that's eliminated by this release. CI now runs `assert_persistent_merkle_tree_dedup.sh` on every PR so the lockfile cannot silently split again on future ssz bumps.

**ePBS / Gloas.** We're another large step closer to the Gloas hard-fork on every front: payload-timeliness committee (PTC) duties are wired through fork choice (#9287, #9211), BAL has been merged into ePBS (#9226), the payload envelope sync flow is in place with range sync support (#9269, #9241), EIP-7843 and the alpha.5 containers are implemented (#9254), the spec test suite has been refreshed to v1.7.0-alpha.6, and the block import pipeline has been refactored so payload processing now defers cleanly to the next block (#9257). Gloas checkpoint sync, genesis handling, and proposer boost behaviour all received targeted fixes this cycle.

**Network and validator UX.** New `beacon_blocks_by_head` reqresp method (#9331), better self-rate-limit handling with peer backoff metadata (#9335, #9034, #9354), and several range-sync correctness fixes (#9361, #9360, #9311). EIP-8061 (increase exit and consolidation churn) is implemented spec-side (#9305). New API endpoints to craft attester slashings from blocks (#9198, community contribution from @markolazic01) and to retrieve signed execution payload envelopes (#9186), plus a new execution-payload-bid SSE event (#9185).

**Operational.** Internal tooling moved to pnpm v11 (#9299); no action required from operators. The CLI `--help` output and docs page now render `--serveHistoricalState` / `--chain.pruneHistory` correctly (#9328, #9334).

[Full Changelog](https://github.com/ChainSafe/lodestar/compare/v1.42.0...v1.43.0)

---

(then the existing `### Features` ... `### Documentation` sections, unchanged)

---

## Discord announcement (channel 741761870033191013)

🚀 **Lodestar v1.43.0 released**

Headline this release is a real-world block-import perf fix: #9352 dedupes `persistent-merkle-tree` so the native `hashtree` hasher actually services ssz's internal merkleizer (the lockfile was silently splitting and falling back to the JS noble hasher, causing GC pressure on mainnet). CI now guards against future re-splits.

Alongside that, another big push on the Gloas / ePBS roadmap — PTC duties wired through fork choice, BAL merged into ePBS, payload envelope sync flow with range sync, EIP-7843 + alpha.5 containers, spec tests refreshed to v1.7.0-alpha.6. Plus EIP-8061 (exit + consolidation churn), new `beacon_blocks_by_head` reqresp, better self-rate-limit handling, and new API endpoints for attester slashings and execution payload envelopes.

**Recommended upgrade for all users.**

📦 Docker: `chainsafe/lodestar:v1.43.0`
📝 Release notes: https://github.com/ChainSafe/lodestar/releases/tag/v1.43.0
