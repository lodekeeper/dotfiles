#!/bin/bash
# Setup script — symlinks agent config files into place
set -e

DOTFILES_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Setting up agent config from $DOTFILES_DIR"

# Claude Code global instructions
mkdir -p ~/.claude
ln -sf "$DOTFILES_DIR/CLAUDE.md" ~/.claude/CLAUDE.md
echo "  ✓ ~/.claude/CLAUDE.md"

# Codex CLI global instructions
mkdir -p ~/.codex
ln -sf "$DOTFILES_DIR/AGENTS.md" ~/.codex/AGENTS.md
echo "  ✓ ~/.codex/AGENTS.md"

echo "Done. Global agent instructions linked."
