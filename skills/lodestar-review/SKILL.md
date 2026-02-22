---
name: lodestar-review
description: Run multi-persona code reviews on Lodestar PRs. Use when reviewing a PR, diff, or code change in ChainSafe/lodestar. Spawns specialized reviewer agents (bug hunter, security engineer, architect, etc.) with Lodestar-specific context, collects findings, and synthesizes a consolidated report. Covers PR review, code quality assessment, and security analysis for Ethereum consensus client code.
---

# Lodestar Code Review

Multi-persona review system for ChainSafe/lodestar PRs. Each reviewer has a narrow scope with explicit rejection criteria, enhanced with Lodestar-specific knowledge.

## Reviewers

| Agent ID | Role | Model | Focus |
|---|---|---|---|
| `review-bugs` | Bug Hunter | GPT-5.3-Codex | Functional errors, logic flaws, off-by-one. Only ACTUAL broken behavior. |
| `review-defender` | Defender | GPT-5.3-Codex | Malicious code, backdoors, supply chain threats. |
| `review-linter` | Style Enforcer | Gemini 2.5 Pro | Style consistency vs Lodestar conventions. |
| `review-security` | Security Engineer | GPT-5.3-Codex | DoS vectors, peer manipulation, validation bypasses, crypto misuse. |
| `review-wisdom` | Wise Senior | Claude Opus 4.6 | Clean code principles, maintainability, readability. |
| `reviewer-architect` | Architect | Claude Opus 4.6 | Package boundaries, consensus spec alignment, module coupling. |

## Reviewer Selection

Pick reviewers based on PR type:

| PR Type | Reviewers |
|---|---|
| **Any PR** | `review-bugs` (always) |
| **>50 lines changed** | + `review-wisdom` |
| **Feature / new functionality** | + `reviewer-architect` |
| **Networking / API / p2p changes** | + `review-security` |
| **External contributor** | + `review-defender` |
| **Style-heavy / refactor** | + `review-linter` |

Cost is not a concern — use all relevant reviewers.

## Workflow

### 1. Get the diff

```bash
gh pr diff <PR_NUMBER> --repo ChainSafe/lodestar
```

For large diffs (>3000 lines), focus on the most critical files or split into chunks.

### 2. Read persona prompts

Each reviewer's persona is in `references/<agent-id>.md` (relative to this skill directory). Read the persona file before spawning.

### 3. Spawn reviewers

For each selected reviewer, spawn with the persona prepended to the diff:

```
sessions_spawn(
  agentId: "<agent-id>",
  task: "<persona prompt>\n\n---\n\nReview this diff for ChainSafe/lodestar PR #<number> (<title>):\n\n```diff\n<diff>\n```",
  label: "pr<number>-<reviewer-short-name>"
)
```

Spawn all selected reviewers in parallel (no dependencies between them).

### 4. Wait for results

All spawned reviewers will announce their findings back to the main session. Wait for ALL to complete before synthesizing.

### 5. Synthesize consolidated report

Combine findings into a single report:

```
## 🔍 PR #<number> — Review Summary

**Reviewers:** <emoji> <name> · <emoji> <name> · ...

### ✅ / ⚠️ <Category>
<Consolidated findings, noting convergence across reviewers>

### Key Takeaway
<Most actionable finding and recommended next step>
```

**Convergence signals quality:** When multiple reviewers independently flag the same issue from different angles, highlight it — it's likely a real problem.

## Lodestar Context for Reviewers

When constructing the task for each reviewer, append this Lodestar context block after the persona prompt (before the diff). This gives reviewers domain knowledge:

```
## Lodestar Codebase Context

Lodestar is a TypeScript Ethereum consensus client (beacon node + validator client + light client).

### Package Structure
- `beacon-node/` — core beacon chain logic, networking, sync, API server
- `validator/` — validator client (separate process, talks to beacon via API)
- `light-client/` — light client (runs in browsers too)
- `state-transition/` — pure state transition functions (spec implementation)
- `fork-choice/` — proto-array fork choice
- `types/` — SSZ type definitions for all forks
- `params/` — consensus constants and presets
- `config/` — runtime chain configuration
- `api/` — REST API client/server (shared between beacon-node and validator)
- `reqresp/` — libp2p request/response protocol
- `db/` — LevelDB abstraction
- `utils/` — shared utilities

### Fork Progression
phase0 → altair → bellatrix → capella → deneb → electra → fulu → gloas

Fork-aware code uses guards: `isForkPostElectra(fork)`, `isForkPostFulu(fork)`, etc.

### Key Conventions
- ES modules with `.js` extensions on relative imports (even for .ts files)
- Biome for linting/formatting, double quotes, no default exports
- `camelCase` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- Explicit parameter and return types, no `any`
- Prometheus metrics: always suffix with units (`_seconds`, `_bytes`, `_total`)
- Structured logging: `this.logger.debug("msg", {slot, root: toRootHex(root)})`

### Common Pitfalls to Watch For
- **Stale fork choice head:** `getHead()` returns cached ProtoBlock. After modifying proto-array state, must call `recomputeForkChoiceHead()`
- **Holding state references:** BeaconState objects are large tree-backed structures. Don't store beyond immediate use
- **Missing .js extension:** Relative imports must use `.js` for ESM resolution
- **Force push after review:** Never — use incremental commits
- **SSZ value vs view:** Value types (plain JS) vs ViewDU (tree-backed). State uses ViewDU — mutations need `.commit()`
- **Config vs params:** `@lodestar/params` = compile-time constants, `@lodestar/config` = runtime chain config

### Architecture Rules
- Beacon node, validator client, and light client are separate packages with clear boundaries
- Cross-package deps flow downward: beacon-node → state-transition → types → params
- Validator talks to beacon node only via REST API (never import beacon-node internals)
- State transition functions must be pure (no side effects, no network calls)
- Fork choice is its own package — beacon-node consumes it, doesn't extend it
```

## Review Patterns Reference

Read `references/review-patterns.md` for patterns mined from ~2000 real Lodestar review comments. Key insights:

- **nflaig (lead):** Spec citations, forward-compatible naming (avoid fork codenames), type safety, comment-code consistency
- **twoeths:** ProtoBlock variant correctness, state cache keys, function signatures
- **wemeetagain:** Metrics coverage, code simplification, future TODOs
- **ensi321:** Edge case analysis, spec divergence, test correctness, scope enforcement

Use these patterns to calibrate reviewer expectations — e.g., the architect reviewer should flag missing metrics (wemeetagain pattern), and the wisdom reviewer should flag stale comments (nflaig pattern).

## Tips

- For consensus-spec-related changes, cross-reference `~/consensus-specs` for correctness
- For API changes, cross-reference `~/beacon-APIs` (ethereum/beacon-APIs)
- The security reviewer is especially valuable for networking/p2p/reqresp changes — consensus clients are adversarial environments
- The architect reviewer catches cross-package boundary violations that other reviewers miss
- When reviewing ePBS/Gloas code, pay extra attention to ProtoBlock variant handling (twoeths's top concern)
- For any new functionality, check if Prometheus metrics are needed (wemeetagain pattern)
