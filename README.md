# dotfiles

Agent configuration, scripts, skills, and shared instructions used by [@lodekeeper](https://github.com/lodekeeper).

Inspired by [steipete/agent-scripts](https://github.com/steipete/agent-scripts).

## Structure

```
CLAUDE.md                    # Global Claude Code instructions (~/.claude/CLAUDE.md)
AGENTS.md                    # Global Codex CLI instructions (~/.codex/AGENTS.md)
CODING_CONTEXT.md            # Context file for coding sub-agents
config/
  codex-config.toml          # Codex CLI config (model, trust levels)
lodestar/
  AGENTS.md                  # Lodestar project-level AGENTS.md (reference copy)
scripts/
  update-status.sh           # Dashboard status updater
  deploy.sh                  # Dashboard deploy script
skills/
  dev-workflow/              # Multi-agent dev workflow for complex features
  grafana-loki/              # Query logs from Grafana Loki
  kurtosis-devnet/           # Ethereum multi-client devnets via Kurtosis
  release-metrics/           # Release candidate readiness evaluation
  release-notes/             # Release notes and Discord announcements
setup.sh                     # Symlinks everything into place
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
- `skills/*` → `~/.openclaw/workspace/skills/` (OpenClaw agent skills)

## How It Works

**Global instructions** apply to all projects. Project-specific `CLAUDE.md` / `AGENTS.md` in repo roots extend these.

**Skills** are loaded on demand by OpenClaw when tasks match their description.

**Scripts** are dependency-free helpers used across projects.

## Updating

Edit files here, commit, push. Symlinks mean changes take effect immediately.
