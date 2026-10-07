# Heze #5713 / #5655 implementation tracker

## Goal
Two independent, ready-for-review Lodestar PRs against `unstable`; implement exact spec changes and preserve earlier forks. Nico requested GPT Sol implementation and parent self-review, overriding separate review-agent workflow.

## Baselines
- Lodestar: `fc618d94e9f` (`origin/unstable`). Main checkout left untouched.
- #5713: `68702a5b201ef974817830fc358baf8fd6035c7b`; local `/home/openclaw/consensus-specs-eip8365-5713` (independent old Heze schema).
- #5655: merged `a5ab894edd2c22494dfe46dc880946d636f5cdf7`; current master `c489a99077c16bad7d75053257c50633d12d314d` at `/home/openclaw/consensus-specs-heze-5713-5655`.
- Worktrees: `/home/openclaw/lodestar-heze-eip8365` and `/home/openclaw/lodestar-heze-eip8015`.

## Progress
- [x] Task registered, upstream diffs captured, acting GitHub user lodekeeper verified.
- [x] No existing open PR matching either EIP found in complete open PR title inventory.
- [x] Isolated worktrees and existing dependency store linked; no dependency installation.
- [~] GPT-6.1 Sol bounded implementers active, one per independent change; parent owns self-review.
- [ ] Generate targeted upstream reftests from exact appropriate spec baselines.
- [ ] Independently validate lint, types, build and relevant tests.
- [ ] Self-review each entire diff + spec compliance.
- [ ] Sign/push commits and create two PRs as lodekeeper.

## Spec Compliance Artifacts
- `notes/heze-5713-5655/spec-compliance-eip8365.md` — faithful, parent self-review +6 upstream /11unit tests passed.

Pending #5655. Validate #5713 `apply_pending_deposit`, #5655 SSZ active-field maps, upgrade, block/epoch processing and operation limits. Local archived vectors are v1.7.0-beta.0 while CI pin is beta.2, so they are not valid evidence for new Heze changes. Generate exact upstream targeted vectors instead; do not depend on broken upstream nightly packaging.

## First PR
- https://github.com/ChainSafe/lodestar/pull/10292 — EIP-8365, ready for review, base unstable, author lodekeeper, signed commit703fcbd4328.
- Parent full repository build/typecheck/lint all pass after isolated validation dependency repair.
