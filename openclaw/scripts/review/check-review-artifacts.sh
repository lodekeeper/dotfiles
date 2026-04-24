#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/review/check-review-artifacts.sh --pr <PR_OR_SLUG> --agents <agent-id> [<agent-id> ...] [options]

Checks whether expected reviewer artifact files exist and are non-empty.

Expected file format:
  notes/review-reports/pr-<PR_OR_SLUG>-<agent-id>.md

Options:
  --pr <value>                 PR number or stable slug (required)
  --agents <ids...>            One or more reviewer agent ids (required)
  --reports-dir <path>         Artifact directory (default: ~/.openclaw/workspace/notes/review-reports)
  --min-bytes <n>              Minimum non-empty size threshold (default: 32)
  --allow-empty-no-findings    Accept tiny files if they include "No findings"
  -h, --help                   Show help

Exit codes:
  0 = all artifacts present and valid
  2 = one or more artifacts missing/invalid
  1 = usage/runtime error
EOF
}

PR=""
REPORTS_DIR="$HOME/.openclaw/workspace/notes/review-reports"
MIN_BYTES=32
ALLOW_EMPTY_NO_FINDINGS=0
AGENTS=()

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pr)
      PR="${2:-}"
      shift 2
      ;;
    --agents)
      shift
      while [[ $# -gt 0 && "$1" != --* ]]; do
        AGENTS+=("$1")
        shift
      done
      ;;
    --reports-dir)
      REPORTS_DIR="${2:-}"
      shift 2
      ;;
    --min-bytes)
      MIN_BYTES="${2:-}"
      shift 2
      ;;
    --allow-empty-no-findings)
      ALLOW_EMPTY_NO_FINDINGS=1
      shift
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

if [[ -z "$PR" ]]; then
  echo "ERROR: --pr is required" >&2
  usage
  exit 1
fi

if [[ ${#AGENTS[@]} -eq 0 ]]; then
  echo "ERROR: --agents requires at least one agent id" >&2
  usage
  exit 1
fi

if ! [[ "$MIN_BYTES" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --min-bytes must be a non-negative integer" >&2
  exit 1
fi

mkdir -p "$REPORTS_DIR"

missing=0
invalid=0
ok=0

echo "Checking reviewer artifacts for PR/slug: $PR"
echo "Reports directory: $REPORTS_DIR"
echo "Expected agents: ${AGENTS[*]}"
echo ""

for agent in "${AGENTS[@]}"; do
  path="$REPORTS_DIR/pr-${PR}-${agent}.md"
  if [[ ! -f "$path" ]]; then
    echo "❌ MISSING   $agent -> $path"
    missing=$((missing + 1))
    continue
  fi

  bytes=$(wc -c < "$path" | tr -d ' ')

  if [[ "$bytes" -lt "$MIN_BYTES" ]]; then
    if [[ "$ALLOW_EMPTY_NO_FINDINGS" -eq 1 ]] && grep -qi "no findings" "$path"; then
      echo "✅ OK       $agent -> $path (${bytes} bytes, accepted: contains 'No findings')"
      ok=$((ok + 1))
      continue
    fi

    echo "❌ INVALID  $agent -> $path (${bytes} bytes, below min ${MIN_BYTES})"
    invalid=$((invalid + 1))
    continue
  fi

  echo "✅ OK       $agent -> $path (${bytes} bytes)"
  ok=$((ok + 1))
done

echo ""
echo "Summary: ok=$ok missing=$missing invalid=$invalid total=${#AGENTS[@]}"

if [[ "$missing" -gt 0 || "$invalid" -gt 0 ]]; then
  exit 2
fi

exit 0
