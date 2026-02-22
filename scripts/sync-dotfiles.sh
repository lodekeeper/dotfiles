#!/bin/bash
# Sync local agent files to the dotfiles repo
# Run periodically or after making local changes
set -e

DOTFILES_DIR="$HOME/dotfiles"
WORKSPACE="$HOME/.openclaw/workspace"

echo "Syncing agent files to dotfiles repo..."

# Global agent instructions (source of truth: dotfiles repo via symlinks)
# These are already symlinked, no sync needed

# Codex config
cp ~/.codex/config.toml "$DOTFILES_DIR/config/codex-config.toml" 2>/dev/null || true

# Coding context
cp "$WORKSPACE/CODING_CONTEXT.md" "$DOTFILES_DIR/CODING_CONTEXT.md" 2>/dev/null || true

# Lodestar project AGENTS.md
cp ~/lodestar/AGENTS.md "$DOTFILES_DIR/lodestar/AGENTS.md" 2>/dev/null || true

# Skills
for skill_dir in "$WORKSPACE/skills"/*/; do
  skill_name=$(basename "$skill_dir")
  mkdir -p "$DOTFILES_DIR/skills/$skill_name"
  cp -r "$skill_dir"* "$DOTFILES_DIR/skills/$skill_name/" 2>/dev/null || true
done

# All notes (specs, eip8025, epbs, etc.)
for notes_dir in "$WORKSPACE/notes"/*/; do
  notes_name=$(basename "$notes_dir")
  mkdir -p "$DOTFILES_DIR/notes/$notes_name"
  cp -r "$notes_dir"* "$DOTFILES_DIR/notes/$notes_name/" 2>/dev/null || true
done

# Scripts
cp ~/lodekeeper-dash/scripts/update-status.sh "$DOTFILES_DIR/scripts/update-status.sh" 2>/dev/null || true
cp ~/lodekeeper-dash/scripts/deploy.sh "$DOTFILES_DIR/scripts/deploy.sh" 2>/dev/null || true

# Check for changes
cd "$DOTFILES_DIR"
if git diff --quiet && git diff --cached --quiet; then
  echo "No changes to sync."
  exit 0
fi

# Commit and push
git add -A
CHANGED=$(git diff --cached --stat | tail -1)
git commit -S -m "chore: sync local changes

$CHANGED

🤖 Generated with AI assistance"
git push origin main
echo "Synced and pushed."
