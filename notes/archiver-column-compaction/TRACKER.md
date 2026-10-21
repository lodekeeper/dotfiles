# Legacy column archiver fix

## Goal
Open a minimal reviewed PR against ChainSafe/lodestar unstable that removes obsolete canonical hot-column migration and compacts the deleted legacy hot bucket at startup.

## Authorization
Nico, Discord #lodestar-private, message 1562192470014689341, 2026-10-20 19:55 UTC. PR work only; no live node maintenance or Gateway/monitor changes.

## Worktree
- /home/openclaw/lodestar-archive-column-compaction
- Branch: fix/archive-legacy-column-compaction
- Base: 3da261f88e8 (fresh origin/unstable)
- Main checkout left on its existing branch, untouched.
- Exact-lock dependency cache reused from today's existing validation worktree with worktree-local workspace links. No install or lockfile changes.

## Phase plan
- [x] Confirm current source, no matching open PR found.
- [x] Design review approved (design-review.md).
- [x] Implement regression tests, confirm red (9 expected failures), apply production fix, confirm green (39/39 targeted tests).
- [x] Full lint (1886 files), full types and DB build passed; targeted storage/archiver/upgrade checks passed.
- [x] Independent bug and maintainability reviews approved final diff SHA256 `11cfa04735481a8b69e668689408c6d53f57c15f2a50bb1b86b5d93f9a308f7a`; artifact affinity gate passed.
- [x] Signed canonical-identity commit `9aec7dcad139b61f84eb4bc04a337081407f00f7`, pushed to fork; verified ready-for-review PR https://github.com/ChainSafe/lodestar/pull/10447 as lodekeeper against unstable. Published patch SHA exactly matches both final reviews.

## Design constraints
Preserve cold-column fallback reads, flat-file writes/serving/pruning, noncanonical cleanup, and block/blob/payload archival. Compact even if the hot bucket has no live keys. Compaction may add startup I/O; do not promise a production duration or instantaneous physical reclamation. No timing assertions in tests.

## Spec compliance artifacts
N/A: internal database maintenance and obsolete migration removal; no consensus state transition, wire format, or consensus-spec pseudocode changes. Upstream spec vectors are not the regression target.

## Current owner
Native implementer handles the isolated source/test patch and verification logs; parent reviews and publishes. No agents may post externally or mutate live nodes.

## Published result
PR https://github.com/ChainSafe/lodestar/pull/10447 is OPEN and non-draft. Title/body and five-file diff verified on GitHub. No merge or deployment requested. Local verification only; GitHub CI is not claimed green. No live DB was compacted during this task.

## Late design-review completion reconciled
The delayed native design-review receipt approves with test qualifications already incorporated in published head `9aec7dcad139b61f84eb4bc04a337081407f00f7`: cold fallback preserved; canonical-only Fulu/Gloas negative assertions; already-empty tombstone regression; 1024-column multi-batch deletion ordering; awaited startup compaction; real flat-column serving. Re-read production/test diff and verified the open PR head on GitHub. No code changes, reruns, or duplicate external update required.
