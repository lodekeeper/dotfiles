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

# Codex config
if [ -f "$DOTFILES_DIR/config/codex-config.toml" ]; then
  ln -sf "$DOTFILES_DIR/config/codex-config.toml" ~/.codex/config.toml
  echo "  ✓ ~/.codex/config.toml"
fi

# OpenClaw workspace skills
if [ -d "$DOTFILES_DIR/skills" ]; then
  SKILLS_DIR="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}/skills"
  mkdir -p "$SKILLS_DIR"
  for skill in "$DOTFILES_DIR/skills"/*/; do
    skill_name=$(basename "$skill")
    ln -sfn "$skill" "$SKILLS_DIR/$skill_name"
    echo "  ✓ skills/$skill_name"
  done
fi

echo "Done. Agent config linked."

# Git config (identity + signing, no credentials)
if [ -f "$DOTFILES_DIR/config/gitconfig" ] && [ ! -f ~/.gitconfig ]; then
  ln -sf "$DOTFILES_DIR/config/gitconfig" ~/.gitconfig
  echo "  ✓ ~/.gitconfig"
else
  echo "  ⊘ ~/.gitconfig already exists (skipped)"
fi
