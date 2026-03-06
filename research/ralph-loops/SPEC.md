# lodeloop — Autonomous Coding Agent Loop

**Version:** 0.1.0
**Author:** Lodekeeper
**Date:** 2026-03-01

---

## Overview

`lodeloop` is a CLI tool that wraps AI coding agents (Codex CLI, Claude CLI) in an autonomous verification loop. It runs the agent repeatedly until all tasks pass verification gates, with built-in circuit breaking, progress tracking, and notification support.

**Key difference from existing tools:** Designed for an AI orchestrator (Lodekeeper/OpenClaw), not for human terminal use. The orchestrator spawns `lodeloop` as a background process, receives notifications on completion/failure, and reviews the output.

## Design Principles

1. **Simple core, composable parts** — The loop is a bash script. Task files, verification, and progress are separate concerns.
2. **Git is the source of truth** — Progress = git commits. No progress = no new commits.
3. **Fail fast, fail loud** — Circuit breaker kills stuck loops. Notifications surface failures immediately.
4. **Agent-agnostic** — Works with any coding CLI that accepts a prompt and exits.
5. **Project-agnostic** — Verification gates are configurable per-project.

## Architecture

```
lodeloop
├── lodeloop.sh              # Main loop runner
├── lib/
│   ├── circuit_breaker.sh   # Stagnation detection (CLOSED → HALF_OPEN → OPEN)
│   ├── progress.sh          # Git-based progress tracking
│   ├── verify.sh            # Verification gate runner
│   ├── notify.sh            # Completion/failure notification
│   └── prompt.sh            # Prompt template builder
├── templates/
│   ├── agent-prompt.md      # Default agent prompt template
│   └── task.json.example    # Example task file
├── AGENTS.md                # Conventions for the coding agent
├── README.md
└── LICENSE
```

## Core Loop

```
for iteration in 1..MAX_ITERATIONS:
  1. Record git HEAD as loop_start_sha
  2. Build prompt from task.json + progress.md + AGENTS.md
  3. Run coding agent with prompt
  4. Run verification gates (typecheck, lint, test)
  5. If gates pass:
     - Commit changes (if not already committed by agent)
     - Mark completed stories in task.json
     - Append to progress.md
  6. If gates fail:
     - Record failure context
     - Inject failure info into next iteration's prompt
  7. Check completion (all stories passes=true?)
     - Yes → notify success, exit 0
  8. Check circuit breaker (stagnation?)
     - OPEN → notify failure, exit 1
  9. Sleep briefly, continue
```

## Task File (task.json)

```json
{
  "project": "lodestar",
  "feature": "EIP-7782 6-second slots",
  "branch": "feat/eip7782-6s-slots",
  "workdir": "~/lodestar-eip7782",
  "agent": "codex",
  "verify": {
    "commands": [
      "pnpm check-types",
      "pnpm lint",
      "pnpm test:unit"
    ],
    "timeout": 300
  },
  "context_files": [
    "CODING_CONTEXT.md",
    "AGENTS.md"
  ],
  "stories": [
    {
      "id": "S1",
      "title": "Update SECONDS_PER_SLOT config",
      "description": "Change SECONDS_PER_SLOT from 12 to 6 in all config presets",
      "acceptance": [
        "SECONDS_PER_SLOT is 6 in mainnet, minimal, and devnet presets",
        "Typecheck passes"
      ],
      "passes": false,
      "notes": ""
    },
    {
      "id": "S2",
      "title": "Update slot timing in beacon node",
      "description": "Adjust slot processing timing to use 6-second slots",
      "acceptance": [
        "SlotClock uses 6-second intervals",
        "Attestation deadlines adjusted proportionally",
        "Unit tests pass"
      ],
      "passes": false,
      "notes": ""
    }
  ]
}
```

## Agent Prompt Template

The prompt injected each iteration:

```markdown
# Task

You are implementing a feature for {project}. Work on ONE story per iteration.

## Context Files
{context_file_contents}

## Task File
{task_json}

## Progress So Far
{progress_md}

## Previous Failures (if any)
{failure_context}

## Instructions

1. Read the task file above. Pick the highest-priority story where `passes: false`.
2. Implement that single story.
3. Run verification: {verify_commands}
4. If verification passes, commit with: `feat({project}): {story_id} - {story_title}`
5. If verification fails, fix the issues and try again within this iteration.
6. Update your progress — append what you did, what you learned, any gotchas.

## Rules
- ONE story per iteration. Do not work on multiple stories.
- Do NOT modify task.json — the loop runner handles that.
- Always run verification before committing.
- Follow the coding conventions in AGENTS.md / CODING_CONTEXT.md.
```

## Verification Gates

Verification is a sequence of commands defined in `task.json`. All must pass (exit 0) for the iteration to be considered successful.

```bash
verify() {
  for cmd in "${VERIFY_COMMANDS[@]}"; do
    echo "🔍 Running: $cmd"
    if ! eval "$cmd"; then
      echo "❌ Verification failed: $cmd"
      return 1
    fi
  done
  echo "✅ All verification gates passed"
  return 0
}
```

**Timeout:** Each verification command has a configurable timeout (default 300s). If exceeded, the iteration is marked as failed.

## Progress Tracking (progress.md)

Append-only file tracking what happened each iteration:

```markdown
## Codebase Patterns
- Use `BeaconConfig` for all timing constants
- Tests use vitest, run with `pnpm test:unit`

---

## Iteration 1 — 2026-03-01T12:00:00Z — S1
- Updated SECONDS_PER_SLOT in mainnet, minimal, devnet presets
- Files: packages/config/src/presets/*.ts
- Verification: ✅ typecheck, ✅ lint, ✅ test
- Learnings: Config presets are in packages/config/src/presets/, each preset exports a full BeaconConfig object

---

## Iteration 2 — 2026-03-01T12:05:00Z — S2
- Updated SlotClock to use configurable slot duration
- Files: packages/beacon-node/src/chain/clock.ts
- Verification: ❌ test (3 failures in clock.test.ts)
- Failure context: Tests hardcode 12-second expectations
```

## Circuit Breaker

Three-state circuit breaker (inspired by frankbria/ralph-claude-code):

| State | Condition | Behavior |
|---|---|---|
| **CLOSED** | Normal operation | Continue looping |
| **HALF_OPEN** | 2 consecutive iterations with no git commits | Continue but monitor |
| **OPEN** | 3+ consecutive iterations with no commits, OR same error 5x | Stop, notify failure |

**Progress detection:**
- Primary: New git commits since loop_start_sha
- Secondary: File changes in working tree (staged or unstaged)
- Tertiary: Agent explicitly reports completion

**State file:** `.lodeloop/circuit.json`

```json
{
  "state": "CLOSED",
  "consecutive_no_progress": 0,
  "consecutive_same_error": 0,
  "last_progress_iteration": 0,
  "total_opens": 0,
  "reason": ""
}
```

## Notifications

On completion or circuit breaker open, `lodeloop` writes a result file and optionally sends a notification.

**Result file:** `.lodeloop/result.json`

```json
{
  "status": "complete|failed|max_iterations",
  "iterations": 5,
  "stories_completed": 4,
  "stories_total": 4,
  "duration_seconds": 1200,
  "last_error": "",
  "timestamp": "2026-03-01T12:30:00Z"
}
```

**Notification hook:** If `--notify` is set, runs a user-defined command on completion:
```bash
lodeloop --notify "openclaw notify 'lodeloop finished: {status}'"
```

## CLI Interface

```
Usage: lodeloop [OPTIONS] <task.json>

Arguments:
  <task.json>           Path to task file

Options:
  -n, --max-iterations  Maximum iterations (default: 20)
  -a, --agent           Agent to use: codex|claude (default: codex)
  -t, --timeout         Per-iteration timeout in seconds (default: 600)
  --notify              Command to run on completion (supports {status}, {iterations} placeholders)
  --dry-run             Print prompt and exit without running
  --resume              Resume from existing progress.md
  --reset               Reset circuit breaker and progress
  --status              Show current loop status and exit
  --verbose             Show agent output in real-time

Environment:
  LODELOOP_AGENT        Default agent (codex|claude)
  LODELOOP_MAX_ITER     Default max iterations
  LODELOOP_TIMEOUT      Default per-iteration timeout
```

## Agent Configuration

### Codex CLI
```bash
source ~/.nvm/nvm.sh && nvm use 24 2>/dev/null
codex exec --full-auto "$PROMPT"
```

### Claude CLI
```bash
claude -p "$PROMPT" --allowedTools "Bash(.*)" "Read" "Write" "Edit"
```

## Integration with Lodekeeper Workflow

### How I (Lodekeeper) use this:

1. **Task creation:** I generate `task.json` from a BACKLOG.md item or PR request
2. **Launch:** Spawn lodeloop in a worktree via `exec pty:true background:true`
3. **Monitor:** Check `.lodeloop/result.json` or receive notification
4. **Review:** Read progress.md, check git log, run final verification
5. **Ship:** If everything looks good, push and create PR

### Example orchestration:
```bash
# 1. Create task file for the feature
cat > ~/lodestar-eip7782/.lodeloop/task.json << 'EOF'
{ ... }
EOF

# 2. Launch in background
cd ~/lodestar-eip7782
lodeloop --agent codex --max-iterations 15 \
  --notify "echo 'DONE: {status}' >> /tmp/lodeloop-results" \
  .lodeloop/task.json

# 3. Check status (from another session)
lodeloop --status .lodeloop/task.json
```

## What This Tool Does NOT Do

- **PRD generation** — I (the orchestrator) create task files. The tool just executes them.
- **PR creation** — I handle git push and PR creation after reviewing output.
- **Multi-repo coordination** — One loop per worktree. Parallelism is my job.
- **Model selection** — I choose the agent. The tool just wraps it.
- **Web dashboard** — I have the lodekeeper-dash for monitoring.

## Testing Strategy

- **Unit tests:** Circuit breaker state transitions, progress detection, prompt building
- **Integration tests:** Full loop with a mock agent (echo script that modifies files)
- **Manual tests:** Run against a real Lodestar worktree with Codex CLI

## Future Extensions (not in v0.1)

- [ ] Multi-story parallelism (split stories across agents)
- [ ] Automatic task.json generation from BACKLOG.md
- [ ] Cost tracking (token usage per iteration)
- [ ] Webhook notifications (POST to URL)
- [ ] Story dependency graph (don't start S3 until S1 passes)
