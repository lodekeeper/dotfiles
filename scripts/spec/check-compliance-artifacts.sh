#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/spec/check-compliance-artifacts.sh --tracker <path> --pr-body <path>

Checks that spec/protocol PR metadata contains compliance references in BOTH:
  1) TRACKER.md ("## Spec Compliance Artifacts" section)
  2) PR body markdown ("## Spec Compliance" section)

Pass criteria:
  - Tracker section exists and includes either:
      - at least one `spec-compliance-*.md` reference, OR
      - explicit N/A with reason
  - PR section exists and includes:
      - `Artifact:` line with either `spec-compliance-*.md` reference OR `N/A`
      - if Artifact is N/A, a `Reason:` line is required
      - if Artifact is a file path, a `Verdict:` line is required

Options:
  --tracker <path>   Path to notes/<feature>/TRACKER.md
  --pr-body <path>   Path to PR body markdown file
  -h, --help         Show this help
EOF
}

fail() {
  echo "❌ $*" >&2
  exit 1
}

ok() {
  echo "✅ $*"
}

extract_h2_section() {
  local file="$1"
  local heading_regex="$2"

  awk -v re="$heading_regex" '
    BEGIN { in_section = 0 }
    {
      line = $0
      lower = tolower(line)
      if (in_section == 0) {
        if (lower ~ re) {
          in_section = 1
          next
        }
      } else {
        if (line ~ /^##[[:space:]]+/) {
          exit
        }
        print line
      }
    }
  ' "$file"
}

has_spec_artifact_ref() {
  local text="$1"
  echo "$text" | grep -Eiq 'spec-compliance-[^[:space:])`]+\.md'
}

has_na_with_reason_like_text() {
  local text="$1"
  # Lightweight: accept either "N/A (reason)" or explicit "Reason:" line.
  echo "$text" | grep -Eiq 'N/?A[[:space:]]*\(|Reason[[:space:]]*:'
}

tracker=""
pr_body=""

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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$tracker" ]] || fail "--tracker is required"
[[ -n "$pr_body" ]] || fail "--pr-body is required"
[[ -f "$tracker" ]] || fail "Tracker file not found: $tracker"
[[ -f "$pr_body" ]] || fail "PR body file not found: $pr_body"

# 1) Tracker checks
tracker_section="$(extract_h2_section "$tracker" '^##[[:space:]]+spec[[:space:]]+compliance[[:space:]]+artifacts.*$')"
[[ -n "${tracker_section//[[:space:]]/}" ]] || fail "Tracker is missing a populated '## Spec Compliance Artifacts' section: $tracker"

if has_spec_artifact_ref "$tracker_section"; then
  ok "Tracker includes spec-compliance artifact reference"
elif has_na_with_reason_like_text "$tracker_section"; then
  ok "Tracker includes explicit N/A/reason in Spec Compliance Artifacts"
else
  fail "Tracker Spec Compliance Artifacts section has no artifact reference or N/A reason"
fi

# 2) PR body checks
pr_section="$(extract_h2_section "$pr_body" '^##[[:space:]]+spec[[:space:]]+compliance[[:space:]]*$')"
[[ -n "${pr_section//[[:space:]]/}" ]] || fail "PR body is missing a populated '## Spec Compliance' section: $pr_body"

artifact_line="$(echo "$pr_section" | grep -Ei '^[[:space:]*-]*Artifact[[:space:]]*:' | head -n1 || true)"
[[ -n "$artifact_line" ]] || fail "PR body Spec Compliance section missing 'Artifact:' line"

if echo "$artifact_line" | grep -Eiq 'N/?A'; then
  echo "$pr_section" | grep -Eiq '^[[:space:]*-]*Reason[[:space:]]*:' || fail "Artifact is N/A but PR Spec Compliance section is missing 'Reason:' line"
  ok "PR body includes Spec Compliance N/A + Reason"
else
  echo "$artifact_line" | grep -Eiq 'spec-compliance-[^[:space:])`]+\.md' || fail "PR body Artifact line must reference spec-compliance-*.md or N/A"
  echo "$pr_section" | grep -Eiq '^[[:space:]*-]*Verdict[[:space:]]*:' || fail "PR body Spec Compliance section missing 'Verdict:' line"
  ok "PR body includes Spec Compliance artifact reference + Verdict"
fi

ok "Compliance artifact presence check passed (tracker + PR body)"
