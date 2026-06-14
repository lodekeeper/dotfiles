#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/spec/prepr-compliance-gate.sh --check-only
  scripts/spec/prepr-compliance-gate.sh --check-only --json

  scripts/spec/prepr-compliance-gate.sh \
    --tracker notes/<feature>/TRACKER.md \
    --pr-body /tmp/pr-<feature>.md \
    --check "<spec_query>|<ts_file>|<ts_symbol>|<report_out>" \
    [--check "..."] \
    [--summary-out /tmp/spec-compliance-summary.md] \
    [--min-verdict partial]

Runs the full pre-PR spec-compliance bundle in one command:
  1) Generates one or more compliance reports via check-compliance.py
  2) Validates tracker + PR metadata references via check-compliance-artifacts.sh
  3) Emits a single pass/fail summary (stdout + optional markdown file)

Arguments:
  --tracker <path>        Path to notes/<feature>/TRACKER.md
  --pr-body <path>        Path to PR body markdown file
  --check <tuple>         Compliance check tuple (repeatable):
                          "spec_query|ts_file|ts_symbol|report_out"
  --summary-out <path>    Optional markdown summary output path
  --min-verdict <level>   Minimum acceptable verdict: faithful|partial
                          Default: partial
  --skip-spec-checks      Only run artifact presence validation
  --check-only            Validate local prerequisites without requiring PR inputs
  --json                  Emit machine-readable output for --check-only
  -h, --help              Show this help

Exit code:
  0 = all checks passed
  1 = one or more checks failed
EOF
}

fail() {
  echo "❌ $*" >&2
  exit 1
}

expand_path() {
  local p="$1"
  if [[ "$p" == ~* ]]; then
    echo "${p/#\~/$HOME}"
  else
    echo "$p"
  fi
}

verdict_rank() {
  case "$1" in
    faithful) echo 3 ;;
    partial) echo 2 ;;
    mismatch) echo 1 ;;
    insufficient) echo 0 ;;
    *) echo -1 ;;
  esac
}

tracker=""
pr_body=""
summary_out=""
min_verdict="partial"
skip_spec_checks=0
check_only=0
json=0
declare -a checks=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tracker)
      [[ $# -ge 2 ]] || fail "Missing value for --tracker"
      tracker="$2"
      shift 2
      ;;
    --pr-body)
      [[ $# -ge 2 ]] || fail "Missing value for --pr-body"
      pr_body="$2"
      shift 2
      ;;
    --check)
      [[ $# -ge 2 ]] || fail "Missing value for --check"
      checks+=("$2")
      shift 2
      ;;
    --summary-out)
      [[ $# -ge 2 ]] || fail "Missing value for --summary-out"
      summary_out="$2"
      shift 2
      ;;
    --min-verdict)
      [[ $# -ge 2 ]] || fail "Missing value for --min-verdict"
      min_verdict="$2"
      shift 2
      ;;
    --skip-spec-checks)
      skip_spec_checks=1
      shift
      ;;
    --check-only)
      check_only=1
      shift
      ;;
    --json)
      json=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

workspace_root="$(cd "$(dirname "$0")/../.." && pwd)"
check_compliance_py="$workspace_root/scripts/spec/check-compliance.py"
check_artifacts_sh="$workspace_root/scripts/spec/check-compliance-artifacts.sh"

if [[ "$check_only" -eq 1 ]]; then
  failures=0
  python_available=0
  check_compliance_present=0
  check_compliance_help_ok=0
  check_artifacts_present=0
  check_artifacts_syntax_ok=0

  if command -v python3 >/dev/null 2>&1; then
    python_available=1
  else
    if [[ "$json" -ne 1 ]]; then
      echo "ERROR: python3 is not available" >&2
    fi
    failures=$((failures + 1))
  fi

  if [[ -f "$check_compliance_py" ]]; then
    check_compliance_present=1
  else
    if [[ "$json" -ne 1 ]]; then
      echo "ERROR: missing helper: $check_compliance_py" >&2
    fi
    failures=$((failures + 1))
  fi

  if [[ -f "$check_artifacts_sh" ]]; then
    check_artifacts_present=1
  else
    if [[ "$json" -ne 1 ]]; then
      echo "ERROR: missing helper: $check_artifacts_sh" >&2
    fi
    failures=$((failures + 1))
  fi

  if [[ "$python_available" -eq 1 && "$check_compliance_present" -eq 1 ]]; then
    if python3 "$check_compliance_py" --help >/dev/null 2>&1; then
      check_compliance_help_ok=1
    else
      if [[ "$json" -ne 1 ]]; then
        echo "ERROR: check-compliance.py help path failed" >&2
      fi
      failures=$((failures + 1))
    fi
  fi

  if [[ "$check_artifacts_present" -eq 1 ]]; then
    if bash -n "$check_artifacts_sh" >/dev/null 2>&1; then
      check_artifacts_syntax_ok=1
    else
      if [[ "$json" -ne 1 ]]; then
        echo "ERROR: check-compliance-artifacts.sh syntax check failed" >&2
      fi
      failures=$((failures + 1))
    fi
  fi

  if [[ "$json" -eq 1 ]]; then
    if [[ "$python_available" -eq 1 ]]; then
      python3 - \
        "$failures" \
        "$workspace_root" \
        "$python_available" \
        "$check_compliance_py" \
        "$check_compliance_present" \
        "$check_compliance_help_ok" \
        "$check_artifacts_sh" \
        "$check_artifacts_present" \
        "$check_artifacts_syntax_ok" <<'PY'
import json
import sys

failures = int(sys.argv[1])
payload = {
    "ok": failures == 0,
    "workspace": sys.argv[2],
    "python3Available": bool(int(sys.argv[3])),
    "helpers": {
        "checkCompliance": {
            "path": sys.argv[4],
            "present": bool(int(sys.argv[5])),
            "helpOk": bool(int(sys.argv[6])),
        },
        "checkComplianceArtifacts": {
            "path": sys.argv[7],
            "present": bool(int(sys.argv[8])),
            "syntaxOk": bool(int(sys.argv[9])),
        },
    },
}
print(json.dumps(payload, sort_keys=True))
PY
    else
      printf '{"helpers":{},"ok":false,"python3Available":false,"workspace":"%s"}\n' "$workspace_root"
    fi

    if [[ "$failures" -ne 0 ]]; then
      exit 2
    fi
    exit 0
  fi

  if [[ "$failures" -ne 0 ]]; then
    exit 2
  fi

  echo "Pre-PR spec compliance gate preflight OK"
  echo "Workspace: $workspace_root"
  echo "Compliance checker: $check_compliance_py"
  echo "Artifact checker: $check_artifacts_sh"
  exit 0
fi

if [[ "$json" -eq 1 ]]; then
  fail "--json is only supported with --check-only"
fi

[[ -n "$tracker" ]] || fail "--tracker is required"
[[ -n "$pr_body" ]] || fail "--pr-body is required"

case "$min_verdict" in
  faithful|partial) ;;
  *) fail "--min-verdict must be 'faithful' or 'partial'" ;;
esac

if [[ "$skip_spec_checks" -eq 0 && "${#checks[@]}" -eq 0 ]]; then
  fail "At least one --check is required unless --skip-spec-checks is set"
fi

tracker="$(expand_path "$tracker")"
pr_body="$(expand_path "$pr_body")"
summary_out="$(expand_path "$summary_out")"

[[ -f "$check_compliance_py" ]] || fail "Missing script: $check_compliance_py"
[[ -f "$check_artifacts_sh" ]] || fail "Missing script: $check_artifacts_sh"

run_ts="$(date -u +"%Y-%m-%d %H:%M:%S UTC")"
min_rank="$(verdict_rank "$min_verdict")"

spec_pass=1
artifact_pass=1

summary_lines=()
summary_lines+=("# Pre-PR Spec Compliance Gate")
summary_lines+=("")
summary_lines+=("Generated: $run_ts")
summary_lines+=("")
summary_lines+=("## Inputs")
summary_lines+=("")
summary_lines+=("- Tracker: \`$tracker\`")
summary_lines+=("- PR body: \`$pr_body\`")
summary_lines+=("- Min verdict: **$min_verdict**")
summary_lines+=("")

if [[ "$skip_spec_checks" -eq 0 ]]; then
  summary_lines+=("## Compliance Reports")
  summary_lines+=("")
  summary_lines+=("| # | Spec Query | TS Symbol | Verdict | Confidence | Report | Status |")
  summary_lines+=("|---|------------|-----------|---------|------------|--------|--------|")

  idx=0
  for tuple in "${checks[@]}"; do
    idx=$((idx + 1))
    IFS='|' read -r spec_query ts_file ts_symbol report_out <<<"$tuple"

    [[ -n "${spec_query:-}" ]] || fail "--check #$idx missing spec_query"
    [[ -n "${ts_file:-}" ]] || fail "--check #$idx missing ts_file"
    [[ -n "${ts_symbol:-}" ]] || fail "--check #$idx missing ts_symbol"
    [[ -n "${report_out:-}" ]] || fail "--check #$idx missing report_out"

    ts_file="$(expand_path "$ts_file")"
    report_out="$(expand_path "$report_out")"

    mkdir -p "$(dirname "$report_out")"

    python3 "$check_compliance_py" \
      --spec-query "$spec_query" \
      --ts-file "$ts_file" \
      --ts-symbol "$ts_symbol" \
      --output "$report_out" \
      >/dev/null

    verdict="$(grep -E '^- \*\*Verdict:\*\*' "$report_out" | sed -E 's/.*\*\*([a-z]+)\*\*.*/\1/' | head -n1 || true)"
    confidence="$(grep -E '^- \*\*Confidence:\*\*' "$report_out" | sed -E 's/.*\*\*Confidence:\*\* ([a-z]+).*/\1/' | head -n1 || true)"

    [[ -n "$verdict" ]] || verdict="insufficient"
    [[ -n "$confidence" ]] || confidence="unknown"

    v_rank="$(verdict_rank "$verdict")"
    status="PASS"
    if [[ "$v_rank" -lt "$min_rank" ]]; then
      status="FAIL"
      spec_pass=0
    fi

    summary_lines+=("| $idx | \`$spec_query\` | \`$ts_symbol\` | $verdict | $confidence | \`$report_out\` | **$status** |")
  done

  summary_lines+=("")
fi

artifact_err=""
if ! artifact_output="$(bash "$check_artifacts_sh" --tracker "$tracker" --pr-body "$pr_body" 2>&1)"; then
  artifact_pass=0
  artifact_err="$artifact_output"
fi

summary_lines+=("## Metadata Presence Check")
summary_lines+=("")
if [[ "$artifact_pass" -eq 1 ]]; then
  summary_lines+=("- Status: **PASS** ✅")
else
  summary_lines+=("- Status: **FAIL** ❌")
  summary_lines+=("- Error:")
  summary_lines+=("\`\`\`")
  summary_lines+=("$artifact_err")
  summary_lines+=("\`\`\`")
fi
summary_lines+=("")

overall_status="PASS"
if [[ "$spec_pass" -eq 0 || "$artifact_pass" -eq 0 ]]; then
  overall_status="FAIL"
fi

summary_lines+=("## Overall")
summary_lines+=("")
if [[ "$overall_status" == "PASS" ]]; then
  summary_lines+=("- **PASS** ✅ — pre-PR compliance gate passed")
else
  summary_lines+=("- **FAIL** ❌ — pre-PR compliance gate failed")
fi
summary_lines+=("")
summary_lines+=("## PR Block Snippet")
summary_lines+=("")
if [[ "$overall_status" == "PASS" ]]; then
  summary_lines+=("\`\`\`markdown")
  summary_lines+=("## Spec Compliance")
  if [[ "$skip_spec_checks" -eq 1 ]]; then
    summary_lines+=("- Artifact: N/A")
    summary_lines+=("- Reason: Spec checks intentionally skipped for this run")
  else
    first_tuple="${checks[0]}"
    IFS='|' read -r _ _ _ first_report_out <<<"$first_tuple"
    first_report_out="$(expand_path "$first_report_out")"
    first_verdict="$(grep -E '^- \*\*Verdict:\*\*' "$first_report_out" | sed -E 's/.*\*\*([a-z]+)\*\*.*/\1/' | head -n1 || true)"
    summary_lines+=("- Artifact: \`$first_report_out\`")
    summary_lines+=("- Verdict: ${first_verdict:-unknown}")
    summary_lines+=("- Notes: prepr-compliance-gate passed (metadata + report checks)")
  fi
  summary_lines+=("\`\`\`")
else
  summary_lines+=("- (No snippet generated because gate failed)")
fi

summary_text="$(printf '%s\n' "${summary_lines[@]}")"

echo "$summary_text"

if [[ -n "$summary_out" ]]; then
  mkdir -p "$(dirname "$summary_out")"
  printf '%s\n' "$summary_text" > "$summary_out"
  echo "Wrote summary: $summary_out"
fi

if [[ "$overall_status" != "PASS" ]]; then
  exit 1
fi
