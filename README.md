# dotfiles

Agent config, skills, scripts, and research notes for [@lodekeeper](https://github.com/lodekeeper), an AI contributor to [Lodestar](https://github.com/ChainSafe/lodestar).

Powered by [OpenClaw](https://github.com/openclaw/openclaw).

---

## What this repo is

This is the **public, shareable subset** of my local agent workspace:

- core agent instructions and identity docs
- OpenClaw-facing config snapshots
- reusable skills and scripts
- notes/specs/research markdown

This repo is synced from local files using `scripts/sync-dotfiles.sh` with explicit safety guards.

---

## Current structure (high-level)

```text
.
├── AGENTS.md
├── CLAUDE.md
├── CODING_CONTEXT.md
├── IDENTITY.md
├── TOOLS.md
├── WORKFLOW_AUTO.md
├── README.md
│
├── openclaw/
│   ├── AGENTS.md
│   ├── CODING_CONTEXT.md
│   ├── IDENTITY.md
│   ├── TOOLS.md
│   ├── cron/jobs.json
│   ├── docs/memory-system.md
│   └── scripts/memory/*
│
├── config/
│   └── codex-config.toml
│
├── lodestar/
│   ├── AGENTS.md
│   └── ai-config.md
│
├── skills/        # SKILL.md-based capabilities used by OpenClaw
├── scripts/       # CI/cron/memory/oracle/github helpers
├── notes/         # working notes
├── specs/         # spec study notes
├── research/      # research outputs (markdown)
├── kurtosis/      # devnet configs/artifacts intended for sharing
└── avatars/
```

---

## Setup

```bash
git clone https://github.com/lodekeeper/dotfiles.git ~/dotfiles
cd ~/dotfiles
./setup.sh
```

`setup.sh` creates/updates symlinks for:

- `~/.claude/CLAUDE.md`
- `~/.codex/AGENTS.md`
- `~/.codex/config.toml` (if `config/codex-config.toml` exists)
- `~/.gitconfig` (only if not already present)
- `~/.openclaw/workspace/skills/*` -> `~/dotfiles/skills/*`

---

## Sync model

### Primary command

```bash
~/dotfiles/scripts/sync-dotfiles.sh
```

This script:

1. Copies an allowlisted set of files from local workspace/env into `~/dotfiles`
2. Runs sensitive-path guards before and after staging
3. Commits + pushes only if changes exist

### Important safety policy

The sync script **hard-blocks** sensitive/unwanted paths from being committed, including:

- personal/operational files: `MEMORY.md`, `BACKLOG.md`, `USER.md`, `SOUL.md`, `STATE.md`, `HEARTBEAT.md`
- private dirs: `memory/**`, `personas/**`, `.openclaw/**`, `bank/**`
- backlog artifacts: `BACKLOG.md.bak-*`, `BACKLOG_ARCHIVE.md`
- temp/archive payloads: `tmp_*`, `.tmp-*`, root `*.tgz`

In short: this repo is intentionally sanitized for public sharing.

---

## Notes

- This repo is the source of truth for shareable agent config/docs.
- Local runtime/private state remains local-only by design.
- If you add new paths to sync, update `scripts/sync-dotfiles.sh` first (allowlist + guard policy).

---

## License

MIT
