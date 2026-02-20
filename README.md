# dotfiles

Agent configuration, scripts, and shared instructions used by [@lodekeeper](https://github.com/lodekeeper).

Inspired by [steipete/agent-scripts](https://github.com/steipete/agent-scripts).

## Structure

```
CLAUDE.md           # Global Claude Code instructions (~/.claude/CLAUDE.md)
AGENTS.md           # Global Codex CLI instructions (~/.codex/AGENTS.md)
CODING_CONTEXT.md   # Context file for coding sub-agents (Codex/Claude CLI)
setup.sh            # Symlinks config files into place
scripts/
  update-status.sh  # Dashboard status updater
```

## Setup

```bash
git clone https://github.com/lodekeeper/dotfiles.git ~/dotfiles
cd ~/dotfiles && ./setup.sh
```

This symlinks:
- `CLAUDE.md` → `~/.claude/CLAUDE.md` (loaded by Claude Code for every project)
- `AGENTS.md` → `~/.codex/AGENTS.md` (loaded by Codex CLI for every project)

## How It Works

**Global instructions** (this repo) apply to all projects. Project-specific `CLAUDE.md` / `AGENTS.md` files in repo roots extend these globals.

**CODING_CONTEXT.md** is handed to Codex CLI or Claude CLI when spawning implementation tasks. It gives them project-specific context to work independently.

**Scripts** are dependency-free helpers used across projects.

## Updating

Edit files here, commit, push. Symlinks mean tools pick up changes immediately — no re-deploy needed.
