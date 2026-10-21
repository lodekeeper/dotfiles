# PR10457 pre-reset review

- Source: Codex P1 discussion_r4337576675, routed 2026-10-21 13:47 UTC.
- Live head: 611e3f9956a0bf219d3dd3357529bea0d4c1e2a7.
- Nico renamed and marked ready for review at 13:39:54 UTC. Do not undo his ready status.
- Original design and both reviews explicitly limit the static schedule patch to post-reset merge/deployment, with upstream75 finalized and final config rechecked. No iteration-aware scheduler in scope.
- [x] BACKLOG review task logged before investigation.
- [x] Read all live review and issue comments and timeline.
- [x] Independently reproduce iteration164 Fulu/Gloas mismatch at the live head.
- [x] Peer-check finding disposition and proposed response.
- [x] Clarify merge-timing wording to remove stale draft-status claim, preserving gates.
- [x] Reply in original inline thread, update backlog and notification tracking.

No source changes, merge, deployment, schedule or gateway changes authorized or performed by this follow-up.

## Outcome
- Verified in-thread reply4337710593: https://github.com/ChainSafe/lodestar/pull/10457#discussion_r4337710593.
- Live PR body updated and verified; Nico title/ready state and head611e3f9956a preserved.
- P1 acknowledged, operationally gated; no source fix claimed. No code changes or push.
- Original post-reset-only scope retained; no deployment/merge authorized or performed.
