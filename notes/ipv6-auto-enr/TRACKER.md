# IPv6 Auto-ENR Discovery — Tracker

Last updated: 2026-03-15 21:50 UTC

## Goal
Fix dual-stack IPv6 auto-ENR discovery in @chainsafe/discv5 (issue lodestar#8808)

## Phase Plan
- [x] Phase 0: Research (LH/Grandine dual-stack handling)
- [x] Phase 1: Spec & Architecture (gpt-advisor design)
- [x] Phase 2: Worktree setup (~/lodestar-ipv6-enr + ~/discv5 cloned)
- [x] Phase 3: Implementation (Codex CLI in ~/discv5)
- [x] Phase 4: Quality gate (build ✅, lint ✅, 56 tests ✅, reviewer addressed)
- [x] Phase 5a: PR on ChainSafe/discv5 — https://github.com/ChainSafe/discv5/pull/334
- [ ] Phase 5b: Local testing with checkpoint sync + engineMock (after discv5 PR merges)
- [ ] Phase 5c: Bump discv5 in Lodestar + PR on ChainSafe/lodestar

## Completed Work
- Research: Rust sigp/discv5 uses separate ipv4_votes/ipv6_votes HashMaps
- Research: Grandine uses same sigp/discv5 crate as Lighthouse
- Design: gpt-advisor (GPT-5.4) produced minimal fix design
- Spec: /tmp/spec-ipv6-auto-enr.md
- Implementation: 5 files changed, 173 insertions, 57 deletions
- Commit: c1ca032 on fix/dual-stack-ipv6-addr-votes
- PR: ChainSafe/discv5#334

## Next Immediate Steps
1. Wait for discv5 PR review/merge
2. Once merged, bump @chainsafe/discv5 in Lodestar
3. Test locally with checkpoint sync + engineMock on dual-stack host
4. Open Lodestar PR to bump dependency

## Key Files Modified
- packages/discv5/src/service/addrVotes.ts (fix MAX_VOTES eviction)
- packages/discv5/src/service/service.ts (two vote pools, maybeUpdateLocalEnrFromVote)
- packages/discv5/src/util/ip.ts (getSocketAddressOnENRByFamily)
- packages/discv5/test/unit/service/addrVotes.test.ts (+2 tests)
- packages/discv5/test/unit/util/ip.test.ts (+2 tests)
