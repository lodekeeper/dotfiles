# lodekeeper-config

Global configuration files for AI coding agents used by [@lodekeeper](https://github.com/lodekeeper).

## Files

| File | Tool | Location | Description |
|------|------|----------|-------------|
| `CLAUDE.md` | [Claude Code](https://claude.ai/code) | `~/.claude/CLAUDE.md` | Global instructions for Claude CLI |
| `AGENTS.md` | [Codex CLI](https://github.com/openai/codex) | `~/.codex/AGENTS.md` | Global instructions for Codex CLI |

## Setup

```bash
# Clone
git clone https://github.com/lodekeeper/dotfiles.git ~/dotfiles

# Symlink into place
ln -sf ~/dotfiles/CLAUDE.md ~/.claude/CLAUDE.md
ln -sf ~/dotfiles/AGENTS.md ~/.codex/AGENTS.md
```

## How It Works

Both Claude Code and Codex CLI automatically load global instruction files before every session:

- **Claude Code** reads `~/.claude/CLAUDE.md` → applies to all projects
- **Codex CLI** reads `~/.codex/AGENTS.md` → applies to all projects

Project-specific `CLAUDE.md` / `AGENTS.md` files in repo roots extend these globals.

## Notes

These are **my** (Lodekeeper's) global preferences — they apply regardless of which project I'm working in. Project-specific conventions live in each repo's own `CLAUDE.md` / `AGENTS.md`.
