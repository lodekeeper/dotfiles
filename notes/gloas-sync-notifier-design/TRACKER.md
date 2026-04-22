# Gloas Sync Notifier Design — Tracker

Last updated: 2026-04-21 UTC

## Goal
Design the best notifier update for Gloas, grounded in first principles and Nico's review feedback, before making further code changes to lodekeeper/lodestar PR #19.

## Phase Plan
- [x] Phase 1: gather PR context + first-principles protocol differences
- [x] Phase 2: draft design doc
- [x] Phase 3: review with gpt-advisor
- [x] Phase 4: defender review (Codex fallback used because Oracle auth was stale)
- [x] Phase 5: review with devils-advocate
- [x] Phase 6: iterate to convergence and summarize the recommended approach

## Completed Work
- Recovered PR #18 and PR #19 review context.
- Confirmed Nico's core feedback: notifier should not expose fork-choice-internal FULL/EMPTY/PENDING machinery when the user-visible semantics can stay closer to pre-Gloas `exec-block`.

## Next Immediate Steps
1. Use `CONCLUSION.md` + `DESIGN.md` to drive the next PR #19 reply / implementation plan.
2. Only after that, move into code changes in `notifier.ts`.
3. If anyone later wants an Oracle/ChatGPT-Pro second opinion, re-run it once fresh auth exists; it is no longer a blocker.

## Interop/Validation Target
- Final design should be implementable as a small notifier patch on top of lodekeeper/lodestar PR #19 (or its replacement).
- It should preserve operator-facing semantics across pre-Gloas and Gloas as much as possible.
- Current convergence summary is captured in `CONCLUSION.md`.

## Spec Compliance Artifacts
- N/A (operator notifier design; protocol-adjacent but not a consensus-state transition change)
