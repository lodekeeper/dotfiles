#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: fetch-run-logs.sh <run-id> [--repo owner/repo] [--output <path>]

Fetch failed logs for a GitHub Actions run with a full-log fallback.

Examples:
  scripts/ci/fetch-run-logs.sh 23124218154
  scripts/ci/fetch-run-logs.sh 23124218154 --repo ChainSafe/lodestar --output tmp/ci-logs/run-23124218154.log
EOF
}

if [[ $# -eq 0 ]]; then
  usage >&2
  exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  usage
  exit 0
fi

run_id="$1"
shift

if ! [[ "$run_id" =~ ^[0-9]+$ ]]; then
  echo "Run ID must be numeric: $run_id" >&2
  usage >&2
  exit 1
fi

repo="ChainSafe/lodestar"
out="tmp/ci-logs/run-${run_id}.log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="$2"
      shift 2
      ;;
    --output)
      out="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

mkdir -p "$(dirname "$out")"
err_file="${out}.err"

if gh run view "$run_id" --repo "$repo" --log-failed >"$out" 2>"$err_file"; then
  mode="failed-only"
else
  if gh run view "$run_id" --repo "$repo" --log >"$out" 2>>"$err_file"; then
    mode="full-fallback"
  else
    echo "❌ Failed to fetch run logs for run $run_id ($repo)." >&2
    cat "$err_file" >&2
    exit 1
  fi
fi

lines=$(wc -l <"$out" | tr -d ' ')
bytes=$(wc -c <"$out" | tr -d ' ')

rm -f "$err_file"

echo "✅ Saved $mode logs for run $run_id ($repo)"
echo "   output: $out"
echo "   lines:  $lines"
echo "   bytes:  $bytes"
