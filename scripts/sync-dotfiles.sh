#!/bin/bash
# Sync local agent files to the dotfiles repo
# Run periodically or after making local changes
set -e

DOTFILES_DIR="$HOME/dotfiles"
WORKSPACE="$HOME/.openclaw/workspace"

echo "Syncing agent files to dotfiles repo..."

# Global agent instructions (source of truth: dotfiles repo via symlinks)
# These are already symlinked, no sync needed

# OpenClaw workspace files
# NOTE: The dotfiles repo versions (openclaw/) are the source of truth.
# They contain more content than the runtime workspace versions.
# Only sync if the dotfiles version doesn't exist yet.
mkdir -p "$DOTFILES_DIR/openclaw"
for f in AGENTS.md HEARTBEAT.md IDENTITY.md SOUL.md TOOLS.md USER.md; do
  if [ ! -f "$DOTFILES_DIR/openclaw/$f" ]; then
    cp "$WORKSPACE/$f" "$DOTFILES_DIR/openclaw/$f" 2>/dev/null || true
  fi
done

# Cron job configurations (backup)
mkdir -p "$DOTFILES_DIR/openclaw/cron"
cp ~/.openclaw/cron/jobs.json "$DOTFILES_DIR/openclaw/cron/jobs.json" 2>/dev/null || true

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

# All notes (specs, eip8025, epbs, lodekeeper-dash, etc.)
for notes_dir in "$WORKSPACE/notes"/*/; do
  notes_name=$(basename "$notes_dir")
  mkdir -p "$DOTFILES_DIR/notes/$notes_name"
  cp -r "$notes_dir"* "$DOTFILES_DIR/notes/$notes_name/" 2>/dev/null || true
done

# Specs (gloas, peerdas, etc.)
for spec_dir in "$WORKSPACE/specs"/*/; do
  spec_name=$(basename "$spec_dir")
  mkdir -p "$DOTFILES_DIR/specs/$spec_name"
  cp -r "$spec_dir"* "$DOTFILES_DIR/specs/$spec_name/" 2>/dev/null || true
done

# Lodestar ai-config
cp "$WORKSPACE/lodestar-ai-config.md" "$DOTFILES_DIR/lodestar/ai-config.md" 2>/dev/null || true

# Research artifacts (~/research/ → dotfiles/research/)
if [ -d "$HOME/research" ]; then
  for research_dir in "$HOME/research"/*/; do
    research_name=$(basename "$research_dir")
    mkdir -p "$DOTFILES_DIR/research/$research_name"
    # Sync markdown and plan files (skip large raw JSON, Python scripts, venvs)
    find "$research_dir" -maxdepth 2 -name "*.md" -exec cp {} "$DOTFILES_DIR/research/$research_name/" \; 2>/dev/null || true
  done
fi

# Scripts
cp ~/lodekeeper-dash/scripts/update-status.sh "$DOTFILES_DIR/scripts/update-status.sh" 2>/dev/null || true
cp ~/lodekeeper-dash/scripts/deploy.sh "$DOTFILES_DIR/scripts/deploy.sh" 2>/dev/null || true

# Check for changes
cd "$DOTFILES_DIR"
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
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
