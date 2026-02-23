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
| `reviewer-architect` | Architect | GPT-5.3-Codex (thinking: xhigh) | Package boundaries, consensus spec alignment, module coupling. |

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

**For open PRs:**
```bash
gh pr diff <PR_NUMBER> --repo ChainSafe/lodestar
```

**For local changes (pre-PR, dev workflow Phase 4):**
```bash
cd ~/lodestar-<feature>
git diff unstable...HEAD    # diff against base branch
# or for staged changes:
git diff --cached
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

**Note:** For `reviewer-architect`, always pass `thinking: "xhigh"` in the spawn call for deep architectural reasoning.

### 4. Wait for results

All spawned reviewers will announce their findings back to the main session. Wait for ALL to complete before synthesizing.

### 5. Act on findings

> ⛔ **MANDATORY: Post findings as INLINE review comments on the diff.**
> Never post a single large summary comment with all findings. This has been explicitly flagged multiple times.

### 5.1 Output hygiene (Nico requirement)

For any PR review content you post (inline comments or review body):
- Include only reviewer-useful technical feedback.
- Do **not** mention review process internals (multi-persona setup, AI/sub-agents, model names, orchestration steps).
- Do **not** include process narration like "I asked X reviewers" or "agent Y found...".
- If explicitly asked for methodology transparency, provide it separately in chat — not in the PR review text.

**Step 5a: Compute line numbers**

Before posting anything, map each finding to its exact file + line number in the new code. Use this helper to find new-file line numbers from the PR diff:

```python
# Save as /tmp/find-review-lines.py and run with: python3 /tmp/find-review-lines.py
import json, subprocess, re

result = subprocess.run(
    ["gh", "api", f"repos/ChainSafe/lodestar/pulls/<PR>/files?per_page=100",
     "--jq", ".[] | {filename, patch}"],
    capture_output=True, text=True
)

def find_line(patch, search_text):
    lines = patch.split("\n")
    new_line = None
    for line in lines:
        m = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
        if m:
            new_line = int(m.group(1))
            continue
        if new_line is None:
            continue
        if line.startswith('-'):
            continue
        if search_text in line:
            return new_line
        new_line += 1
    return None
```

**Step 5b: Post as a single GitHub review with inline comments**

Use the review API to batch all comments into ONE review submission. Use JSON input (not `-f` flags) so `line` is a proper integer:

```bash
cat > /tmp/review-payload.json << 'EOF'
{
  "commit_id": "<head_sha>",
  "event": "COMMENT",
  "body": "Brief summary of overall assessment + any general/cross-cutting findings not tied to specific lines. DO NOT mention review process details (multi-persona, AI reviewers, sub-agents). Only include info useful to the PR author.",
  "comments": [
    {
      "path": "packages/reqresp/src/file.ts",
      "line": 42,
      "side": "RIGHT",
      "body": "🔴 **Finding title**\n\nExplanation.\n\n```suggestion\nfixed code here\n```"
    }
  ]
}
EOF

gh api repos/ChainSafe/lodestar/pulls/<PR>/reviews \
  --method POST --input /tmp/review-payload.json
```

**Comment format rules:**
- One inline comment per finding, on the exact line it refers to
- Use `🔴` for must-fix, `🟡` for should-fix, `🟢` for suggestions
- Use `suggestion` blocks for concrete code changes (GitHub renders these as committable)
- **General/cross-cutting findings** that aren't tied to a specific line go in the review `body` — that's what it's for
- The review `body` can contain both a brief summary AND general findings (architecture observations, cross-cutting patterns, etc.)
- Deduplicate: if multiple reviewers flag the same line, merge into one comment noting convergence
- Use `-F line=N` or JSON input (not `-f line=N`) — line must be an integer, not a string

**Convergence signals quality:** When multiple reviewers independently flag the same issue from different angles, highlight it — it's likely a real problem.

> ❌ **DO NOT:**
> - Post a single large comment with all findings listed
> - Use `gh pr comment` for review findings
> - Skip the line-number computation step
> - Use `-f line=N` (string) — always use `-F line=N` (integer) or JSON input
> - Mention review process details in the PR comment (multi-persona, AI reviewers, sub-agents, model names) — only include info useful to the PR author

**For local changes (pre-PR, dev workflow Phase 4):**

Don't post to GitHub — there's no PR yet. Instead:
1. Collect all reviewer findings
2. Fix issues directly in the worktree (small fixes → do yourself, large → back to coding agent)
3. Re-run reviewers on the updated diff if changes were significant
4. Only open the PR after the review cycle is clean

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
