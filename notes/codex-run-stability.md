# Codex Run Stability: OOM vs Timeout/SIGKILL

Date: 2026-02-27

## Verdict
Prior "OOM-killed" Codex runs were primarily timeout/SIGKILL from exec supervision, not confirmed memory OOM.

## Evidence
- Process summary in `~/.openclaw/agents/main/sessions/adfdb1d1-43bf-48ba-850f-b96128afd130.jsonl` shows hard-cut runtimes and kill signals:
  - `mellow-cedar`: `runtimeMs=30045`, `exitSignal=9`, command included `codex exec --full-auto ...`
  - `gentle-haven`: `runtimeMs=30072`, `exitSignal=9`, command included `codex exec --full-auto ...`
  - `tender-fjord`: `runtimeMs=180068`, `exitSignal=SIGKILL`, command `pnpm check-types -w packages/beacon-node ...`
- Another process log for `tender-fjord` captured only `Now using node v24.13.0`, then `exitSignal=SIGKILL`, consistent with supervisor kill before useful output.
- Repeated OpenClaw `exec` errors in same session: `Command aborted by signal SIGKILL`.
- No matching kernel/OOM signature found in Codex rollout logs for these runs (`code 137`, `Out of memory`, `Killed process ...` not present as kill cause for those sessions).

## Root Cause
Launches used long-running commands under implicit/low exec watchdog windows (observed ~30s and ~180s). OpenClaw killed processes with SIGKILL at timeout boundaries, which was interpreted as OOM.

## Recommended Launch Templates
Use PTY + background + explicit timeout for long tasks. Avoid inline `| tail` in the launched command.

### 1) Recommended (explicit timeout)
```bash
exec pty:true workdir:~/lodestar-gossip-tests background:true timeout:3600 \
  command:"source ~/.nvm/nvm.sh && nvm use 24 2>/dev/null && codex exec --full-auto 'Read CODING_CONTEXT.md, then TASK.md, implement task, run tests, then openclaw gateway wake --text \"Done: <summary>\" --mode now'"
```

### 2) Recommended (no timeout override)
```bash
exec pty:true workdir:~/lodestar-gossip-tests background:true \
  command:"source ~/.nvm/nvm.sh && nvm use 24 2>/dev/null && codex exec --full-auto 'Read CODING_CONTEXT.md, then TASK.md, implement task, run tests, then openclaw gateway wake --text \"Done: <summary>\" --mode now'"
```

### 3) Heavy non-agent task with explicit budget
```bash
exec pty:true workdir:~/lodestar-gossip-tests timeout:1800 \
  command:"source ~/.nvm/nvm.sh && nvm use 24 2>/dev/null && pnpm check-types -w packages/beacon-node"
```

## Monitoring Tips
- Immediately record session id and monitor with:
  - `process action:poll sessionId:<id>`
  - `process action:log sessionId:<id>`
- If runtime clusters at exact boundaries (e.g., ~30s, ~180s), treat as timeout first.
- Inspect `exitSignal` + `runtimeMs` before calling it OOM.
- For true memory diagnosis, run targeted command with memory telemetry:
  - `/usr/bin/time -v <command>`
- Keep wake hook in prompt so completion is explicit:
  - `openclaw gateway wake --text "Done: <summary>" --mode now`

## Anti-Patterns That Caused Failures
- Running long Codex jobs under short watchdog windows:
  - `codex exec --full-auto ...` killed at ~30s (`mellow-cedar`, `gentle-haven`).
- Running heavy checks under too-short timeout:
  - `pnpm check-types ...` killed at ~180s (`tender-fjord`).
- Piping launched command output to `tail` (`| tail -5`, `| tail -40`) which hid context and made kill reason ambiguous.
- Labeling SIGKILL as OOM without checking `runtimeMs`/`exitSignal` pattern.

## Launch-Template Fixes (Actionable)
- Set explicit timeout by task class in templates:
  - Codex implementation tasks: `timeout:3600` to `timeout:7200`
  - Typecheck/build/test sweeps: `timeout:1200` to `timeout:3600`
  - Quick probes: `timeout:30` to `timeout:120`
- Default to `pty:true` for coding agents.
- Default to `background:true` + `process action:log/poll` for tasks expected to exceed ~30s.
- Remove `| tail` from launch commands; use `process action:log` for controlled output.
