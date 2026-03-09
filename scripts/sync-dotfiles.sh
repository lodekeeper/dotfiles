#!/bin/bash
# Sync local non-sensitive agent files to dotfiles repo
set -euo pipefail

# Prevent git from hanging on auth prompts in non-TTY (cron) context
export GIT_TERMINAL_PROMPT=0
export GIT_HTTP_CONNECT_TIMEOUT=30
export GIT_HTTP_LOW_SPEED_TIME=30
export GIT_HTTP_LOW_SPEED_LIMIT=1

DOTFILES_DIR="$HOME/dotfiles"
WORKSPACE="$HOME/.openclaw/workspace"

# Sensitive/unwanted path policy (must never be committed)
# Notes:
# - keep research/** and kurtosis/** (explicitly allowed by Nico)
# - block backlog artifacts, memory/personas, bank snapshots, local state dumps,
#   and temporary/archive payloads that should not be published.
SENSITIVE_REGEX='^(BACKLOG\.md|BACKLOG\.md\.bak-.*|BACKLOG_ARCHIVE\.md|STATE\.md|memory/|bank/|\.openclaw/|\.tmp-.*|tmp_.*|.*\.tgz$)'

assert_no_sensitive_changes() {
  local staged unstaged untracked combined
  staged=$(git diff --cached --name-only || true)
  unstaged=$(git diff --name-only || true)
  untracked=$(git ls-files --others --exclude-standard || true)
  combined=$(printf "%s\n%s\n%s\n" "$staged" "$unstaged" "$untracked" | sed '/^$/d' | sort -u)
  if echo "$combined" | grep -E "$SENSITIVE_REGEX" >/dev/null; then
    echo "❌ ABORT: sensitive paths detected in changes:" >&2
    echo "$combined" | grep -E "$SENSITIVE_REGEX" >&2 || true
    exit 1
  fi
}

echo "Syncing non-sensitive files to dotfiles repo..."

mkdir -p "$DOTFILES_DIR/openclaw" "$DOTFILES_DIR/config" "$DOTFILES_DIR/lodestar" "$DOTFILES_DIR/scripts"

# Workspace files (explicit allowlist)
for f in AGENTS.md IDENTITY.md TOOLS.md CODING_CONTEXT.md SOUL.md USER.md HEARTBEAT.md MEMORY.md; do
  [ -f "$WORKSPACE/$f" ] && cp "$WORKSPACE/$f" "$DOTFILES_DIR/openclaw/$f"
done

# Cron config backup
mkdir -p "$DOTFILES_DIR/openclaw/cron"
[ -f "$HOME/.openclaw/cron/jobs.json" ] && cp "$HOME/.openclaw/cron/jobs.json" "$DOTFILES_DIR/openclaw/cron/jobs.json"

# Config/context
[ -f "$HOME/.codex/config.toml" ] && cp "$HOME/.codex/config.toml" "$DOTFILES_DIR/config/codex-config.toml"
[ -f "$HOME/lodestar/AGENTS.md" ] && cp "$HOME/lodestar/AGENTS.md" "$DOTFILES_DIR/lodestar/AGENTS.md"
[ -f "$WORKSPACE/lodestar-ai-config.md" ] && cp "$WORKSPACE/lodestar-ai-config.md" "$DOTFILES_DIR/lodestar/ai-config.md"

# Skills (exclude runtime/state artifacts)
mkdir -p "$DOTFILES_DIR/skills"
for skill_dir in "$WORKSPACE/skills"/*/; do
  [ -d "$skill_dir" ] || continue
  skill_name=$(basename "$skill_dir")
  mkdir -p "$DOTFILES_DIR/skills/$skill_name"
  rsync -a \
    --exclude '__pycache__' \
    --exclude 'state' \
    --exclude '*.db' \
    --exclude '*.pyc' \
    "$skill_dir/" "$DOTFILES_DIR/skills/$skill_name/"
done

# Notes/specs
[ -d "$WORKSPACE/notes" ] && rsync -a "$WORKSPACE/notes/" "$DOTFILES_DIR/notes/"
[ -d "$WORKSPACE/specs" ] && rsync -a "$WORKSPACE/specs/" "$DOTFILES_DIR/specs/"

# Personas (PR review personas)
if [ -d "$WORKSPACE/personas" ]; then
  mkdir -p "$DOTFILES_DIR/personas"
  rsync -a --exclude '__pycache__' "$WORKSPACE/personas/" "$DOTFILES_DIR/personas/"
fi

# Research markdown only
if [ -d "$HOME/research" ]; then
  mkdir -p "$DOTFILES_DIR/research"
  while IFS= read -r -d '' f; do
    rel="${f#$HOME/research/}"
    mkdir -p "$DOTFILES_DIR/research/$(dirname "$rel")"
    cp "$f" "$DOTFILES_DIR/research/$rel"
  done < <(find "$HOME/research" -type f -name '*.md' -print0)
fi

# Scripts (explicit)
[ -f "$HOME/lodekeeper-dash/scripts/update-status.sh" ] && cp "$HOME/lodekeeper-dash/scripts/update-status.sh" "$DOTFILES_DIR/scripts/update-status.sh"
[ -f "$HOME/lodekeeper-dash/scripts/deploy.sh" ] && cp "$HOME/lodekeeper-dash/scripts/deploy.sh" "$DOTFILES_DIR/scripts/deploy.sh"

# Workspace scripts (debug/spec tooling)
mkdir -p "$DOTFILES_DIR/scripts/debug" "$DOTFILES_DIR/scripts/spec"
[ -f "$WORKSPACE/scripts/debug/devnet-triage.sh" ] && cp "$WORKSPACE/scripts/debug/devnet-triage.sh" "$DOTFILES_DIR/scripts/debug/devnet-triage.sh"
[ -f "$WORKSPACE/scripts/spec/extract-spec-section.sh" ] && cp "$WORKSPACE/scripts/spec/extract-spec-section.sh" "$DOTFILES_DIR/scripts/spec/extract-spec-section.sh"

# Research scripts (Cloudflare bypass + Oracle bridge)
mkdir -p "$DOTFILES_DIR/research"
for f in cf-bypass-extended.py cf-bypass-scrapling.py cf-bypass-test.py chatgpt-camoufox.py oracle-bridge-cdp.py oracle-remote-chrome-test.py oracle-stealth-bridge.py; do
  [ -f "$WORKSPACE/research/$f" ] && cp "$WORKSPACE/research/$f" "$DOTFILES_DIR/research/$f"
done

cd "$DOTFILES_DIR"
assert_no_sensitive_changes

if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  echo "No changes to sync."
  exit 0
fi

git add -A
assert_no_sensitive_changes

CHANGED=$(git diff --cached --stat | tail -1)
git commit -S -m "chore: sync non-sensitive local changes

$CHANGED

🤖 Generated with AI assistance"
git push origin main

echo "Synced and pushed (non-sensitive only)."
