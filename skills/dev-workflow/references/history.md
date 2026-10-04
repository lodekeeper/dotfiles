# Dev Workflow — History

Dated iteration log and per-feature learnings, moved out of `SKILL.md` on 2026-10-04. Durable rules live in the SKILL.md procedure; this file is the record.

Superseded since written (2026-10-04 audit): #12–13 — `claude -p --permission-mode bypassPermissions` writes files and skips the trust prompt; the `HEARTBEAT.md` priority entry (#25, EPBS rows) — use a 🔴 `BACKLOG.md` item tagged `[topic:ID]` instead (SKILL.md Phase 2.5).

## Iteration Log

Track what works and what doesn't after each use:

| Date | Feature | What worked | What to improve |
|------|---------|-------------|-----------------|
| 2026-02-15 | pre-validate.mjs | Spec rounds with advisor caught edge cases early; Codex produced working 662-line script | Codex hung on first attempt (long prompt); needed concise retry. Codex doesn't understand project-specific conventions (global vs per-package lint/build) — always verify. Gemini reviewer failed without file access — need to pass code inline. |
| 2026-02-16 | EIP-8025 optional proofs | Deep research phase paid off — studying 54 Lighthouse files + Prysm + kurtosis configs before speccing prevented wrong assumptions. gpt-advisor confirmed interop-first approach in 2 rounds. Phase A (types) done cleanly. | Need Phase 0 (Research) for cross-client interop features. Simple foundation work (types/constants) faster done directly than via Codex. Break big features into sub-phases with verification between each. |
| 2026-02-17 | EIP-8025 kurtosis revalidation (orchestrator test) | Claude CLI produced 406-line validation script from task file spec in ~75s. Parallel execution (Docker + Claude CLI) eliminated wait time. Stayed responsive to notifications throughout. CODING_CONTEXT.md reusable across tasks. | Task files must be in worktree (not /tmp). `--print` doesn't write files. Trust prompt on first run. Always include env-specific constants (slot time etc.) in task file. Review is the bottleneck — consider delegating that too. |
| 2026-02-22 | EPBS devnet-0 interop | Tracker file + HEARTBEAT.md priority entry kept progress across sessions. gpt-advisor caught race hypothesis early. Structured acceptance counters (ISR/PU/lag/etc.) made pass/fail unambiguous. Multiple soak passes caught regressions. | Used `Dockerfile` + `--no-cache` for ALL 15+ rebuilds instead of `Dockerfile.dev` (wasted hours). Sent partial progress updates before all criteria were met. Didn't separate validator vs observer testing early enough — observer was clean while validator had bugs. |

### Learnings from orchestrator test (2026-02-17)
**Context:** First test of the orchestrator workflow. Task: redeploy EIP-8025 3-client kurtosis devnet and validate SSZ mismatch fix. Delegated validation script (406 lines) to Claude CLI, ran Docker build in parallel, deployed/monitored myself. Result: PASS.

**What worked:**
- Task file approach (precise spec → quality output, less review)
- Parallel execution (Docker + Claude CLI simultaneously)
- Staying responsive during builds/waits (handled heartbeats, notifications)
- `CODING_CONTEXT.md` as reusable shared context
- Claude CLI code quality was high (proper error handling, ANSI colors, arg parsing, kurtosis auto-discovery)

**Numbered learnings:**
11. **Task files must be in the worktree** — Claude CLI is sandboxed to `workdir`. Files in `/tmp` are inaccessible. Copy task files and `CODING_CONTEXT.md` into the worktree before spawning.
12. **`--print` mode doesn't create files** — Claude CLI `--print` just outputs text, doesn't actually write files. Use interactive mode (no `--print`) for file creation tasks.
13. **Trust prompt first time** — Claude CLI asks to trust the workspace directory on first run. Need to send Enter to accept before it starts working. Pre-approve by running a trivial command first.
14. **Include environment-specific constants in task files** — Claude defaulted to mainnet values (12s slots) instead of devnet values (6s). Sub-agents don't know deployment-specific parameters unless explicitly told. Always specify slot times, epoch lengths, network configs in the task file.
15. **Parallel work prevents tunnel vision** — by delegating implementation and running ops tasks myself, I stayed available for notifications and heartbeats throughout. This directly solved the "disappear for hours" problem identified earlier.
16. **Review is the bottleneck** — Claude produced 406 lines in ~75s, but I still needed to review it all. For larger delegations, consider also delegating review to sub-agent reviewers (codex-reviewer, gemini-reviewer) to parallelize the quality gate.
17. **Ops tasks (deploy, monitor) stay with me** — things requiring real-time judgment (interpreting logs, debugging devnet issues, checking proof flow timing) aren't good delegation targets. Keep those; delegate the deterministic coding work.

### Learnings from EPBS devnet-0 (2026-02-21 → 2026-02-22)
**Context:** Largest debugging effort so far. Multi-day, 15+ Docker rebuilds, 20+ Kurtosis relaunches, ~36 hours continuous work across sessions. Task: get Lodestar ePBS interop working with Lighthouse in a 50/50 Kurtosis devnet with zero errors.

| Date | Feature | What worked | What to improve |
|------|---------|-------------|-----------------|
| 2026-02-22 | EPBS devnet-0 interop | Tracker file + HEARTBEAT.md priority entry kept progress across sessions. gpt-advisor caught race hypothesis early. Structured acceptance counters (ISR/PU/lag/etc.) made pass/fail unambiguous. Multiple soak passes caught regressions. | Used `Dockerfile` + `--no-cache` for ALL 15+ rebuilds instead of `Dockerfile.dev` (wasted hours). Sent partial progress updates before all criteria were met. Didn't separate validator vs observer testing early enough — observer was clean while validator had bugs. |
| 2026-03-01 | lodeloop integration | Added lodeloop (~/lodeloop) as Phase 3 Option A for multi-story features. Keeps Codex as default. Direct CLI remains Option B for single tasks. GPT-5.2-pro review caught 14 issues, all fixed in v0.2.0. | Not yet tested on a real Lodestar task — first real test will validate story sizing, verification gate config, and circuit breaker thresholds. |

**Numbered learnings:**
18. **Use `Dockerfile.dev` for iterative builds** — production `Dockerfile` + `--no-cache` is for debugging build issues, not source changes. `Dockerfile.dev` caches dependency layers and rebuilds in seconds. I wasted hours on unnecessary full rebuilds. Already documented in kurtosis skill — follow your own docs.
19. **Production path ≠ observer path** — the hardest bugs (state root mismatches in `produceBlockWrapper`) only appeared on the validator/producer node. Observer nodes showed zero errors. Always test both roles separately with targeted log checks.
20. **Only report when ALL acceptance criteria are met** — Nico's rule. Don't send "ISR=0 but still some lag" updates. Iterate silently, report once when everything's green. Partial updates waste reviewer time and create noise.
21. **Define acceptance counters upfront** — before any soak, list the exact log patterns/metrics that must be zero. Makes pass/fail unambiguous and prevents goalpost-moving.
22. **Sub-agent review during debugging, not just before PR** — gpt-advisor identified the gossip race condition hypothesis from log patterns while I was still instrumenting. Get second opinions early in the debug cycle, not just at the end.
23. **Stale object references after in-place mutations** — fork-choice status updates (PENDING→FULL) don't automatically propagate to all code paths holding references to the old object. After any state mutation, trace all consumers to verify they see the updated state. This was the root cause of the `BLOCK_ERROR_INVALID_STATE_ROOT` in block production.
24. **Timeline reconstruction for race conditions** — when multiple async paths interact (gossip handler, sync, import, verification), reconstruct the exact event ordering from timestamps. Simple log grepping misses the crucial "which happened first" context.
25. **Tracker + HEARTBEAT.md priority entry = multi-session continuity** — `notes/epbs-devnet-0/TRACKER.md` was the single source of truth across 10+ sessions. The `HEARTBEAT.md` top-priority entry ensured every heartbeat resumed work instead of just monitoring. Without both, progress would have stalled between sessions.
26. **Multiple soak passes are necessary** — first clean soak may pass, then a second reveals edge cases. Run extended soaks (hours) and at different topologies (2-node, 4-node, different client ratios). Short soaks give false confidence.
27. **Alt-port configs for Kurtosis** — Docker port collisions with other services are common on shared servers. Always use non-default port ranges to avoid bind failures.

### Learnings from first run (2026-02-15)
1. **Keep Codex prompts concise** — long specs can cause hangs. Summarize requirements, don't paste full spec tables.
2. **Codex doesn't know project conventions** — it assumed per-package lint/build but Lodestar uses global `biome check` and `pnpm -r build`. Always review output against project norms.
3. **Sub-agent reviewers need code inline** — gemini-reviewer can't access gists/files. Pass key code sections in the task prompt.
4. **2 advisor rounds was sufficient** — round 1 caught major design issues (bash→Node, dependency graph), round 2 tightened details. Diminishing returns after 3.
5. **Phase 4 self-review is critical** — caught 2 bugs Codex missed. Never skip.

### Learnings from EIP-8025 (2026-02-16, in progress)
6. **Add Phase 0: Research for interop features** — when matching other client implementations, invest heavily in reading their code before writing the spec. For EIP-8025, studying Lighthouse (54 files), Prysm, and kurtosis configs revealed critical wire format divergences from the consensus spec that would have been wrong assumptions otherwise.
7. **Foundation commits can be done directly** — simple type definitions, constants, and boilerplate don't benefit from Codex. Save Codex for complex logic (networking, state management). I did Phase A (SSZ types + constants) manually in ~30 min vs the overhead of setting up a Codex session.
8. **Break large features into sub-phases** — instead of one massive Codex handoff, split into A/B/C/... phases with build verification between each. Each phase should be a committable, testable unit. Prevents compounding errors.
9. **Spec should document wire format divergences** — for interop features, explicitly note where devnet wire format differs from the formal spec. This prevents future confusion and helps when migrating to spec-compliant types later.
10. **Research artifacts are valuable** — save deep-dive notes (e.g., `notes/eip8025/LIGHTHOUSE-DEEP-DIVE.md`, `LODESTAR-MAPPING.md`) alongside the spec. Future contributors (including future-me) need this context.
