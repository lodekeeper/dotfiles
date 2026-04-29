#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/review/write-review-artifact.sh --pr <PR_OR_SLUG> --agent <agent-id> [options]

Writes a reviewer artifact file with required metadata markers:
  - Reviewer: <agent-id>
  - Reviewed commit: <HEAD_SHA>

Default output path:
  ~/.openclaw/workspace/notes/review-reports/pr-<PR_OR_SLUG>-<agent-id>.md

Body input priority:
  1) --body-file <path>
  2) stdin
  3) fallback "No findings."

Options:
  --pr <value>           PR number or stable slug (required)
  --agent <agent-id>     Reviewer agent id (required)
  --head-repo <path>     Git repo for HEAD SHA (default: current directory)
  --reports-dir <path>   Artifact directory (default: ~/.openclaw/workspace/notes/review-reports)
  --body-file <path>     Read body markdown from file instead of stdin
  --title <text>         Optional markdown H1 title override
  -h, --help             Show help

Exit codes:
  0 = artifact written
  1 = usage/runtime error
EOF
}

PR=""
AGENT=""
HEAD_REPO="."
REPORTS_DIR="$HOME/.openclaw/workspace/notes/review-reports"
BODY_FILE=""
TITLE=""

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
    --agent)
      AGENT="${2:-}"
      shift 2
      ;;
    --head-repo)
      HEAD_REPO="${2:-}"
      shift 2
      ;;
    --reports-dir)
      REPORTS_DIR="${2:-}"
      shift 2
      ;;
    --body-file)
      BODY_FILE="${2:-}"
      shift 2
      ;;
    --title)
      TITLE="${2:-}"
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

if [[ -z "$PR" ]]; then
  echo "ERROR: --pr is required" >&2
  exit 1
fi

if [[ -z "$AGENT" ]]; then
  echo "ERROR: --agent is required" >&2
  exit 1
fi

if [[ ! -d "$HEAD_REPO" ]]; then
  echo "ERROR: --head-repo path does not exist: $HEAD_REPO" >&2
  exit 1
fi

if ! head_sha="$(git -C "$HEAD_REPO" rev-parse HEAD 2>/dev/null)"; then
  echo "ERROR: could not resolve git HEAD in: $HEAD_REPO" >&2
  exit 1
fi

body=""
if [[ -n "$BODY_FILE" ]]; then
  if [[ ! -f "$BODY_FILE" ]]; then
    echo "ERROR: --body-file does not exist: $BODY_FILE" >&2
    exit 1
  fi
  body="$(cat "$BODY_FILE")"
elif [[ ! -t 0 ]]; then
  body="$(cat)"
fi

if [[ -z "${body//[[:space:]]/}" ]]; then
  body="No findings."
fi

mkdir -p "$REPORTS_DIR"
out_path="$REPORTS_DIR/pr-${PR}-${AGENT}.md"

timestamp="$(date -u +"%Y-%m-%d %H:%M UTC")"

if [[ -z "$TITLE" ]]; then
  TITLE="# Review Findings — ${AGENT} — ${PR}"
fi

cat > "$out_path" <<EOF
$TITLE

Reviewer: $AGENT
Reviewed commit: $head_sha
Generated at: $timestamp

$body
EOF

echo "$out_path"
