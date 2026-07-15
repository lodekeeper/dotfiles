#!/usr/bin/env bash
set -euo pipefail

SPEC_REPO="${SPEC_REPO:-$HOME/consensus-specs}"
MAX_AGE_DAYS=14
REQUIRE_FRESH=false
JSON_OUTPUT=false

usage() {
  cat <<'EOF'
Usage: check-test-vector-readiness.sh [options]

Validate that consensus-spec test vectors are available locally before running
spec/protocol-facing Lodestar work.

Options:
  --spec-repo <path>       Path to consensus-specs repo (default: ~/consensus-specs)
  --max-age-days <days>    Freshness threshold for tests/ history (default: 14)
  --require-fresh          Exit non-zero when tests/ history is older than threshold
  --json                   Emit machine-readable status on stdout
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
    --json)
      JSON_OUTPUT=true
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

TESTS_DIR="$SPEC_REPO/tests"

emit_json() {
  local ok="$1"
  local status="$2"
  local message="$3"
  local sample_file="${4:-}"
  local head_sha="${5:-}"
  local head_date="${6:-}"
  local tests_age_days="${7:-}"

  python3 - \
    "$ok" \
    "$status" \
    "$message" \
    "$SPEC_REPO" \
    "$TESTS_DIR" \
    "$MAX_AGE_DAYS" \
    "$REQUIRE_FRESH" \
    "$sample_file" \
    "$head_sha" \
    "$head_date" \
    "$tests_age_days" <<'PY'
import json
import sys

tests_age_days = sys.argv[11]
payload = {
    "ok": sys.argv[1] == "true",
    "status": sys.argv[2],
    "message": sys.argv[3],
    "specRepo": sys.argv[4],
    "testsDir": sys.argv[5],
    "maxAgeDays": int(sys.argv[6]),
    "requireFresh": sys.argv[7] == "true",
    "sampleFile": sys.argv[8] or None,
    "headSha": sys.argv[9] or None,
    "headDate": sys.argv[10] or None,
    "testsAgeDays": int(tests_age_days) if tests_age_days else None,
}
payload["stale"] = (
    payload["testsAgeDays"] is not None
    and payload["testsAgeDays"] > payload["maxAgeDays"]
)
print(json.dumps(payload, sort_keys=True))
PY
}

if ! git -C "$SPEC_REPO" rev-parse --git-dir >/dev/null 2>&1; then
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    emit_json false "missing_repo" "consensus-specs repo not found"
    exit 1
  fi
  echo "❌ consensus-specs repo not found at: $SPEC_REPO" >&2
  echo "   Clone it first: git clone https://github.com/ethereum/consensus-specs.git $SPEC_REPO" >&2
  exit 1
fi

if [[ ! -d "$TESTS_DIR" ]]; then
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    emit_json false "missing_tests_dir" "tests directory missing"
    exit 1
  fi
  echo "❌ tests directory missing: $TESTS_DIR" >&2
  echo "   The repo appears incomplete; re-sync consensus-specs." >&2
  exit 1
fi

sample_file="$(
  find "$TESTS_DIR" \
    -type f \
    ! -path '*/__pycache__/*' \
    ! -path '*/test-reports/*' \
    ! -name '*.pyc' \
    -print -quit 2>/dev/null || true
)"
if [[ -z "$sample_file" ]]; then
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    emit_json false "no_vectors" "no test-vector files found"
    exit 1
  fi
  echo "❌ no test-vector files found under $TESTS_DIR" >&2
  echo "   Re-sync consensus-specs and ensure tests are checked out." >&2
  exit 1
fi

head_sha="$(git -C "$SPEC_REPO" rev-parse --short HEAD)"
head_date="$(git -C "$SPEC_REPO" log -1 --format=%cs HEAD)"

tests_ts="$(git -C "$SPEC_REPO" log -1 --format=%ct -- tests 2>/dev/null || true)"
if [[ -z "$tests_ts" ]]; then
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    emit_json true "ready_unknown_age" "test vectors present; tests/ age unknown" "${sample_file#"$SPEC_REPO/"}" "$head_sha" "$head_date"
    exit 0
  fi
  echo "⚠️  Could not determine last update time for tests/; repo history may be shallow." >&2
  echo "✅ Test vectors appear present (sample: ${sample_file#"$SPEC_REPO/"})"
  echo "ℹ️  consensus-specs HEAD: $head_sha ($head_date)"
  exit 0
fi

now_ts="$(date +%s)"
age_days=$(( (now_ts - tests_ts) / 86400 ))

if [[ "$JSON_OUTPUT" == "true" ]]; then
  if (( age_days > MAX_AGE_DAYS )) && [[ "$REQUIRE_FRESH" == "true" ]]; then
    emit_json false "stale" "test vectors are older than max-age-days" "${sample_file#"$SPEC_REPO/"}" "$head_sha" "$head_date" "$age_days"
    exit 2
  fi

  if (( age_days > MAX_AGE_DAYS )); then
    emit_json true "stale_warning" "test vectors are older than max-age-days" "${sample_file#"$SPEC_REPO/"}" "$head_sha" "$head_date" "$age_days"
    exit 0
  fi

  emit_json true "ready" "test vectors present and fresh enough" "${sample_file#"$SPEC_REPO/"}" "$head_sha" "$head_date" "$age_days"
  exit 0
fi

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
