#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/review/check-review-scope.sh [options]

Options:
  --base <ref>                Base ref for comparison (default: origin/unstable)
  --allow-dirty               Allow staged/unstaged local changes (default: fail when dirty)
  --changed-files-out <path>  Write changed-file list to path
  --diff-out <path>           Write unified diff to path
  -h, --help                  Show this help

Purpose:
  Guard reviewer scope before spawning sub-agents.
  - Verifies you are in a git worktree
  - Verifies the base ref exists
  - Fails fast when the working tree is dirty (unless --allow-dirty)
  - Emits canonical changed-file list + diff for <base>...HEAD
EOF
}

BASE_REF="origin/unstable"
ALLOW_DIRTY=0
CHANGED_FILES_OUT=""
DIFF_OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      BASE_REF="${2:-}"
      shift 2
      ;;
    --allow-dirty)
      ALLOW_DIRTY=1
      shift
      ;;
    --changed-files-out)
      CHANGED_FILES_OUT="${2:-}"
      shift 2
      ;;
    --diff-out)
      DIFF_OUT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: Not inside a git worktree." >&2
  exit 1
fi

if ! git rev-parse --verify "${BASE_REF}^{commit}" >/dev/null 2>&1; then
  echo "ERROR: Base ref '${BASE_REF}' does not exist locally." >&2
  echo "Hint: git fetch origin" >&2
  exit 1
fi

if [[ "$ALLOW_DIRTY" -eq 0 ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: Working tree is dirty. Commit or stash changes before reviewer spawn." >&2
    echo "(Use --allow-dirty only when intentionally reviewing staged/unstaged changes.)" >&2
    exit 2
  fi
fi

BRANCH_NAME="$(git rev-parse --abbrev-ref HEAD)"
CHANGED_FILES="$(git diff --name-only "${BASE_REF}...HEAD")"

if [[ -n "$CHANGED_FILES_OUT" ]]; then
  mkdir -p "$(dirname -- "$CHANGED_FILES_OUT")"
  printf '%s\n' "$CHANGED_FILES" > "$CHANGED_FILES_OUT"
fi

if [[ -n "$DIFF_OUT" ]]; then
  mkdir -p "$(dirname -- "$DIFF_OUT")"
  git diff "${BASE_REF}...HEAD" > "$DIFF_OUT"
fi

FILE_COUNT=0
if [[ -n "$CHANGED_FILES" ]]; then
  FILE_COUNT="$(printf '%s\n' "$CHANGED_FILES" | sed '/^$/d' | wc -l | tr -d ' ')"
fi

{
  echo "Review scope check: OK"
  echo "- branch: ${BRANCH_NAME}"
  echo "- base: ${BASE_REF}"
  echo "- changed files: ${FILE_COUNT}"
  if [[ -n "$CHANGED_FILES_OUT" ]]; then
    echo "- changed-files artifact: ${CHANGED_FILES_OUT}"
  fi
  if [[ -n "$DIFF_OUT" ]]; then
    echo "- diff artifact: ${DIFF_OUT}"
  fi
  echo
  echo "Changed files:"
  if [[ -n "$CHANGED_FILES" ]]; then
    printf '%s\n' "$CHANGED_FILES"
  else
    echo "(none)"
  fi
} >&2

# Keep stdout machine-friendly when caller pipes output.
printf '%s\n' "$CHANGED_FILES"
