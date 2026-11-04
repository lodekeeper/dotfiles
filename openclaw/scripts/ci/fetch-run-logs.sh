#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  fetch-run-logs.sh <run-id> [--repo owner/repo] [--output <path>] [--job-id <id>]
  fetch-run-logs.sh --check-only [--json]

Fetch failed logs for a GitHub Actions run with a run-log fallback.
Use --job-id to bypass gh run formatting and retrieve raw logs for one completed
job after verifying its run membership. A successful download or line count does
not establish completeness; reconcile the evidence with job steps/annotations.

Examples:
  scripts/ci/fetch-run-logs.sh --check-only
  scripts/ci/fetch-run-logs.sh 23124218154
  scripts/ci/fetch-run-logs.sh 23124218154 --repo ChainSafe/lodestar --output tmp/ci-logs/run-23124218154.log

Options:
  --check-only  Validate local prerequisites without calling GitHub
  --json        Emit machine-readable output for --check-only
  --job-id ID   Fetch raw REST job logs; retain .job.json/.err and failed downloads
EOF
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
GH_ACCESS_GUARD="$WORKSPACE_ROOT/scripts/github/check-github-access.sh"

bail_if_github_suspended() {
  [[ -x "$GH_ACCESS_GUARD" ]] || return 0

  local guard_cmd=("$GH_ACCESS_GUARD")
  if [[ -n "${GITHUB_ACCESS_STATE_FILE:-}" ]]; then
    guard_cmd+=(--state-file "$GITHUB_ACCESS_STATE_FILE")
  fi
  if [[ -n "${GITHUB_ACCESS_MAX_AGE_MINUTES:-}" ]]; then
    guard_cmd+=(--max-age-minutes "$GITHUB_ACCESS_MAX_AGE_MINUTES")
  fi

  local guard_output=""
  local guard_rc=0
  set +e
  guard_output="$(timeout 20s "${guard_cmd[@]}" 2>&1)"
  guard_rc=$?
  set -e

  if [[ "$guard_rc" -eq 2 ]]; then
    echo "GITHUB_SUSPENDED_SKIP"
    exit 4
  fi
}

repo="ChainSafe/lodestar"
out=""
run_id=""
job_id=""
check_only=0
json_output=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only)
      check_only=1
      shift
      ;;
    --json)
      json_output=1
      shift
      ;;
    --repo)
      [[ $# -ge 2 ]] || { echo "--repo requires a value" >&2; exit 1; }
      repo="$2"
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a value" >&2; exit 1; }
      out="$2"
      shift 2
      ;;
    --job-id)
      [[ $# -ge 2 && "$2" =~ ^[0-9]+$ ]] || { echo "--job-id requires a numeric value" >&2; exit 1; }
      job_id="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "$run_id" ]]; then
        echo "Unexpected extra argument: $1" >&2
        usage >&2
        exit 1
      fi
      run_id="$1"
      shift
      ;;
  esac
done

if [[ "$check_only" -eq 1 ]]; then
  gh_path="$(command -v gh 2>/dev/null || true)"
  guard_executable=1
  status="ready"
  ok=1

  if [[ ! -x "$GH_ACCESS_GUARD" ]]; then
    guard_executable=0
  fi

  if [[ -z "$gh_path" ]]; then
    status="missing_gh"
    ok=0
  elif [[ "$guard_executable" -ne 1 ]]; then
    status="missing_github_access_guard"
    ok=0
  fi

  if [[ "$json_output" -eq 1 ]]; then
    python3 - "$ok" "$status" "$repo" "$gh_path" "$GH_ACCESS_GUARD" "$guard_executable" <<'PY'
import json
import sys

ok, status, repo, gh_path, guard, guard_executable = sys.argv[1:]
print(json.dumps({
    "ok": ok == "1",
    "status": status,
    "repo": repo,
    "ghAvailable": bool(gh_path),
    "ghPath": gh_path or None,
    "githubGuard": guard,
    "githubGuardExecutable": guard_executable == "1",
}, sort_keys=True))
PY
  else
    if [[ "$ok" -ne 1 ]]; then
      case "$status" in
        missing_gh)
          echo "ERROR: gh CLI is not available" >&2
          ;;
        missing_github_access_guard)
          echo "ERROR: GitHub access guard is missing or not executable: $GH_ACCESS_GUARD" >&2
          ;;
      esac
      exit 1
    fi
    echo "CI log fetch preflight OK"
    echo "Repo: $repo"
    echo "GitHub guard: $GH_ACCESS_GUARD"
  fi
  exit "$((1 - ok))"
fi

if [[ "$json_output" -eq 1 ]]; then
  echo "ERROR: --json is only supported with --check-only" >&2
  exit 1
fi

if [[ -z "$run_id" ]]; then
  usage >&2
  exit 1
fi

if ! [[ "$run_id" =~ ^[0-9]+$ ]]; then
  echo "Run ID must be numeric: $run_id" >&2
  usage >&2
  exit 1
fi

if [[ -z "$out" ]]; then
  if [[ -n "$job_id" ]]; then
    out="tmp/ci-logs/run-${run_id}-job-${job_id}.log"
  else
    out="tmp/ci-logs/run-${run_id}.log"
  fi
fi

if [[ -d "$out" ]]; then
  echo "Output must be a file path, not a directory: $out" >&2
  exit 1
fi

bail_if_github_suspended

mkdir -p "$(dirname "$out")"
err_file="${out}.err"

if [[ -n "$job_id" ]]; then
  metadata_file="${out}.job.json"
  download_file="${out}.job-${job_id}.download"
  if ! gh api "repos/$repo/actions/jobs/$job_id" >"$metadata_file" 2>"$err_file"; then
    echo "Failed to fetch job metadata; diagnostics: $err_file" >&2
    exit 1
  fi
  if ! python3 - "$metadata_file" "$run_id" "$job_id" <<'PY'
import json
import sys

path, run_id, job_id = sys.argv[1:]
try:
    with open(path, encoding="utf-8") as source:
        job = json.load(source)
    if (not isinstance(job, dict)
            or type(job.get("id")) is not int or job["id"] != int(job_id)
            or type(job.get("run_id")) is not int or job["run_id"] != int(run_id)
            or job.get("status") != "completed"):
        raise ValueError("job ID/run ID mismatch or job is not completed")
except (OSError, ValueError) as exc:
    print(f"Job metadata rejected: {exc}", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    echo "Metadata retained: $metadata_file" >&2
    exit 1
  fi
  if ! gh api "repos/$repo/actions/jobs/$job_id/logs" >"$download_file" 2>>"$err_file"; then
    echo "Failed to fetch raw job logs; retained download/diagnostics: $download_file / $err_file" >&2
    exit 1
  fi
  if [[ ! -s "$download_file" ]]; then
    echo "Raw job log download is empty; existing output unchanged: $out" >&2
    exit 1
  fi
  mv -T -- "$download_file" "$out"
  echo "Saved raw-job logs for job $job_id in run $run_id ($repo)"
  echo "   output: $out"
  echo "   metadata: $metadata_file; diagnostics: $err_file"
  echo "   lines: $(wc -l <"$out"); bytes: $(wc -c <"$out")"
  echo "Job scope only; download success/size does not establish completeness. Reconcile job steps/annotations."
  exit 0
fi

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
echo "gh-formatted logs; success/size does not establish completeness. If evidence conflicts with job steps/annotations, retry with --job-id <id> and a distinct --output path."
