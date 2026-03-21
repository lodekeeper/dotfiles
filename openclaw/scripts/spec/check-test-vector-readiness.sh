#!/usr/bin/env bash
set -euo pipefail

SPEC_REPO="${SPEC_REPO:-$HOME/consensus-specs}"
MAX_AGE_DAYS=14
REQUIRE_FRESH=false

usage() {
  cat <<'EOF'
Usage: check-test-vector-readiness.sh [options]

Validate that consensus-spec test vectors are available locally before running
spec/protocol-facing Lodestar work.

Options:
  --spec-repo <path>       Path to consensus-specs repo (default: ~/consensus-specs)
  --max-age-days <days>    Freshness threshold for tests/ history (default: 14)
  --require-fresh          Exit non-zero when tests/ history is older than threshold
  --help                   Show help

Exit codes:
  0  Ready (vectors present; freshness within threshold or warning-only)
  2  Vectors present but stale and --require-fresh was set
  1  Missing repo/tests data or invalid args
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --spec-repo)
      [[ $# -ge 2 ]] || { echo "Missing value for --spec-repo" >&2; exit 1; }
      SPEC_REPO="$2"
      shift 2
      ;;
    --max-age-days)
      [[ $# -ge 2 ]] || { echo "Missing value for --max-age-days" >&2; exit 1; }
      MAX_AGE_DAYS="$2"
      if ! [[ "$MAX_AGE_DAYS" =~ ^[0-9]+$ ]]; then
        echo "Invalid --max-age-days: $MAX_AGE_DAYS" >&2
        exit 1
      fi
      shift 2
      ;;
    --require-fresh)
      REQUIRE_FRESH=true
      shift
      ;;
    --help|-h)
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

if [[ ! -d "$SPEC_REPO/.git" ]]; then
  echo "❌ consensus-specs repo not found at: $SPEC_REPO" >&2
  echo "   Clone it first: git clone https://github.com/ethereum/consensus-specs.git $SPEC_REPO" >&2
  exit 1
fi

TESTS_DIR="$SPEC_REPO/tests"
if [[ ! -d "$TESTS_DIR" ]]; then
  echo "❌ tests directory missing: $TESTS_DIR" >&2
  echo "   The repo appears incomplete; re-sync consensus-specs." >&2
  exit 1
fi

sample_file="$(find "$TESTS_DIR" -type f -print -quit 2>/dev/null || true)"
if [[ -z "$sample_file" ]]; then
  echo "❌ no test-vector files found under $TESTS_DIR" >&2
  echo "   Re-sync consensus-specs and ensure tests are checked out." >&2
  exit 1
fi

head_sha="$(git -C "$SPEC_REPO" rev-parse --short HEAD)"
head_date="$(git -C "$SPEC_REPO" log -1 --format=%cs HEAD)"

tests_ts="$(git -C "$SPEC_REPO" log -1 --format=%ct -- tests 2>/dev/null || true)"
if [[ -z "$tests_ts" ]]; then
  echo "⚠️  Could not determine last update time for tests/; repo history may be shallow." >&2
  echo "✅ Test vectors appear present (sample: ${sample_file#"$SPEC_REPO/"})"
  echo "ℹ️  consensus-specs HEAD: $head_sha ($head_date)"
  exit 0
fi

now_ts="$(date +%s)"
age_days=$(( (now_ts - tests_ts) / 86400 ))

echo "✅ Test vectors present (sample: ${sample_file#"$SPEC_REPO/"})"
echo "ℹ️  consensus-specs HEAD: $head_sha ($head_date)"
echo "ℹ️  tests/ last-updated age: ${age_days} day(s)"

if (( age_days > MAX_AGE_DAYS )); then
  echo "⚠️  tests/ appears stale (> ${MAX_AGE_DAYS} days)." >&2
  echo "   Suggested refresh: git -C "$SPEC_REPO" fetch origin && git -C "$SPEC_REPO" pull --ff-only" >&2
  if [[ "$REQUIRE_FRESH" == "true" ]]; then
    exit 2
  fi
fi
