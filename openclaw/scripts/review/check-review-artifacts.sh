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
  --max-age-minutes <n>        Mark artifacts invalid if older than n minutes (optional)
  --require-text <value>       Require each artifact to contain this exact text (repeatable)
  --require-reviewed-head      Require marker "Reviewed commit: <HEAD_SHA>" (resolved from git)
  --head-repo <path>           Repo path for --require-reviewed-head (default: current directory)
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
MAX_AGE_MINUTES=""
ALLOW_EMPTY_NO_FINDINGS=0
AGENTS=()
REQUIRED_TEXTS=()
REQUIRE_REVIEWED_HEAD=0
HEAD_REPO="."

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
    --max-age-minutes)
      MAX_AGE_MINUTES="${2:-}"
      shift 2
      ;;
    --require-text)
      REQUIRED_TEXTS+=("${2:-}")
      shift 2
      ;;
    --require-reviewed-head)
      REQUIRE_REVIEWED_HEAD=1
      shift
      ;;
    --head-repo)
      HEAD_REPO="${2:-}"
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

if [[ -n "$MAX_AGE_MINUTES" ]] && ! [[ "$MAX_AGE_MINUTES" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --max-age-minutes must be a non-negative integer" >&2
  exit 1
fi

for required_text in "${REQUIRED_TEXTS[@]}"; do
  if [[ -z "$required_text" ]]; then
    echo "ERROR: --require-text cannot be empty" >&2
    exit 1
  fi
done

if [[ "$REQUIRE_REVIEWED_HEAD" -eq 1 ]]; then
  if [[ ! -d "$HEAD_REPO" ]]; then
    echo "ERROR: --head-repo path does not exist: $HEAD_REPO" >&2
    exit 1
  fi

  if ! head_sha="$(git -C "$HEAD_REPO" rev-parse HEAD 2>/dev/null)"; then
    echo "ERROR: --require-reviewed-head could not resolve git HEAD in: $HEAD_REPO" >&2
    exit 1
  fi

  REQUIRED_TEXTS+=("Reviewed commit: $head_sha")
fi

mkdir -p "$REPORTS_DIR"

missing=0
invalid=0
stale=0
missing_text=0
ok=0

now_epoch=""
max_age_seconds=""
if [[ -n "$MAX_AGE_MINUTES" ]]; then
  now_epoch="$(date +%s)"
  max_age_seconds=$((MAX_AGE_MINUTES * 60))
fi

echo "Checking reviewer artifacts for PR/slug: $PR"
echo "Reports directory: $REPORTS_DIR"
echo "Expected agents: ${AGENTS[*]}"
if [[ ${#REQUIRED_TEXTS[@]} -gt 0 ]]; then
  echo "Required text markers (${#REQUIRED_TEXTS[@]}):"
  for marker in "${REQUIRED_TEXTS[@]}"; do
    echo "  - $marker"
  done
fi
echo ""

for agent in "${AGENTS[@]}"; do
  path="$REPORTS_DIR/pr-${PR}-${agent}.md"
  if [[ ! -f "$path" ]]; then
    echo "❌ MISSING   $agent -> $path"
    missing=$((missing + 1))
    continue
  fi

  bytes=$(wc -c < "$path" | tr -d ' ')

  accepted_empty_no_findings=0
  if [[ "$bytes" -lt "$MIN_BYTES" ]]; then
    if [[ "$ALLOW_EMPTY_NO_FINDINGS" -eq 1 ]] && grep -qi "no findings" "$path"; then
      accepted_empty_no_findings=1
    else
      echo "❌ INVALID  $agent -> $path (${bytes} bytes, below min ${MIN_BYTES})"
      invalid=$((invalid + 1))
      continue
    fi
  fi

  if [[ -n "$MAX_AGE_MINUTES" ]]; then
    mtime_epoch="$(stat -c %Y "$path" 2>/dev/null || true)"
    if ! [[ "$mtime_epoch" =~ ^[0-9]+$ ]]; then
      echo "❌ INVALID  $agent -> $path (unable to read mtime for age check)"
      invalid=$((invalid + 1))
      continue
    fi

    age_seconds=$((now_epoch - mtime_epoch))
    if [[ "$age_seconds" -lt 0 ]]; then
      age_seconds=0
    fi

    if [[ "$age_seconds" -gt "$max_age_seconds" ]]; then
      age_minutes=$((age_seconds / 60))
      echo "❌ STALE    $agent -> $path (${age_minutes}m old, exceeds ${MAX_AGE_MINUTES}m max age)"
      stale=$((stale + 1))
      continue
    fi
  fi

  missing_marker=""
  for marker in "${REQUIRED_TEXTS[@]}"; do
    if ! grep -Fq -- "$marker" "$path"; then
      missing_marker="$marker"
      break
    fi
  done
  if [[ -n "$missing_marker" ]]; then
    echo "❌ INVALID  $agent -> $path (missing required text marker: $missing_marker)"
    missing_text=$((missing_text + 1))
    continue
  fi

  if [[ "$accepted_empty_no_findings" -eq 1 ]]; then
    echo "✅ OK       $agent -> $path (${bytes} bytes, accepted: contains 'No findings')"
  else
    echo "✅ OK       $agent -> $path (${bytes} bytes)"
  fi
  ok=$((ok + 1))
done

echo ""
echo "Summary: ok=$ok missing=$missing invalid=$invalid stale=$stale missing_text=$missing_text total=${#AGENTS[@]}"

if [[ "$missing" -gt 0 || "$invalid" -gt 0 || "$stale" -gt 0 || "$missing_text" -gt 0 ]]; then
  exit 2
fi

exit 0
