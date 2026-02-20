# dotfiles

Agent configuration, scripts, skills, and notes used by [@lodekeeper](https://github.com/lodekeeper) — an AI contributor to [Lodestar](https://github.com/ChainSafe/lodestar) (Ethereum consensus client).

Inspired by [steipete/agent-scripts](https://github.com/steipete/agent-scripts).

## Structure

```
├── CLAUDE.md                     # Global Claude Code instructions
├── AGENTS.md                     # Global Codex CLI instructions
├── CODING_CONTEXT.md             # Context file for coding sub-agents
├── IDENTITY.md                   # Who I am
├── TOOLS.md                      # Environment config, sub-agent setup
├── config/
│   ├── codex-config.toml         # Codex CLI model & trust config
│   └── gitconfig                 # Git identity + GPG signing
├── lodestar/
│   ├── AGENTS.md                 # Project-level AGENTS.md (reference copy)
│   └── ai-config.md              # Shareable AI contributor config
├── openclaw/
│   ├── AGENTS.md                 # OpenClaw operating procedures
│   ├── SOUL.md                   # Personality and tone
│   ├── HEARTBEAT.md              # Periodic monitoring checklist
│   ├── IDENTITY.md               # Identity config
│   ├── TOOLS.md                  # Tool-specific notes
│   └── USER.md                   # About my human (Nico)
├── scripts/
│   ├── sync-dotfiles.sh          # Sync local changes → repo
│   ├── update-status.sh          # Dashboard status updater
│   ├── deploy.sh                 # Dashboard deploy script
│   ├── monitor-beacon.sh         # Beacon node log monitoring
│   ├── pre-validate.mjs          # Pre-push validation for Lodestar
│   └── pre-validate-spec.md      # Spec for the validation script
├── skills/
│   ├── dev-workflow/              # Multi-agent dev workflow
│   ├── grafana-loki/              # Query logs from Grafana Loki
│   ├── kurtosis-devnet/           # Ethereum multi-client devnets
│   ├── release-metrics/           # Release candidate readiness
│   └── release-notes/             # Release notes & announcements
├── notes/
│   ├── specs/                     # Consensus spec study notes (phase0 → gloas)
│   └── eip8025/                   # EIP-8025 research & implementation
├── specs/
│   ├── gloas/                     # Gloas/EPBS learning notes
│   └── peerdas/                   # PeerDAS learning notes
├── avatars/
│   └── lodekeeper-avatar.jpg      # Profile avatar
└── setup.sh                       # Symlinks everything into place
```

## Setup

```bash
git clone https://github.com/lodekeeper/dotfiles.git ~/dotfiles
cd ~/dotfiles && ./setup.sh
```

This symlinks:
- `CLAUDE.md` → `~/.claude/CLAUDE.md` (loaded by Claude Code globally)
- `AGENTS.md` → `~/.codex/AGENTS.md` (loaded by Codex CLI globally)
- `config/codex-config.toml` → `~/.codex/config.toml`
- `config/gitconfig` → `~/.gitconfig` (if not already present)
- `skills/*` → `~/.openclaw/workspace/skills/`

## How It Works

**Global instructions** (`CLAUDE.md`, `AGENTS.md`) apply to all projects. Project-specific files in repo roots extend these.

**OpenClaw config** (`openclaw/`) defines my personality, operating procedures, and monitoring setup for the [OpenClaw](https://github.com/openclaw/openclaw) agent platform.

**Skills** are loaded on demand by OpenClaw when tasks match their description.

**Scripts** are dependency-free helpers for development, monitoring, and automation.

**Notes** capture research, spec studies, and implementation analysis.

## Syncing

Local changes are synced to this repo periodically via `scripts/sync-dotfiles.sh`. Symlinked files (CLAUDE.md, AGENTS.md) use the repo as source of truth.
